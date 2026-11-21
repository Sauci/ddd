"""The language server itself: a loop, six messages, and no opinions of its own.

Everything that decides anything lives in :mod:`ddd.lsp.diagnostics` and
:mod:`ddd.lsp.discovery`; what is left here is translation. That split is deliberate, because
this is the layer a test can only reach through a protocol: keeping it thin keeps the thinking
somewhere that can be tested directly.

Each message is answered inside a net. The front end reports through a diagnostic bag rather
than raising - the developer documentation states it as a rule - so a project that cannot be
read, or whose plugin raises out of a hook, produces findings, not an exception. What turns
those findings into answers is code like any other, though, and a hover that raised on an init
nobody had foreseen ended the session: every finding on screen went with it, and a client stops
restarting a server that the next hover ends again. So a message the server fails on through a
defect of its own costs that answer and nothing more - a request is answered with the
protocol's internal error, a notification with nothing, as ever - and the trace goes to stderr,
the server's log, where a defect is seen rather than hidden. Only ``Exception`` is caught, so an
interrupt still ends the run.

Only ``didOpen``, ``didSave``, a watched change and a change of the workspace folders refresh,
and what they mark is checked together. The stream is read ahead on a thread of its own, which
is what tells the messages that came together from one not sent yet: once a message marks a
document, the messages already waiting behind it are handled, and every document marked by
then is checked, each project once - before a request among them is answered, and without
waiting for a message that has not arrived (:meth:`Server._serve`). Nothing is analysed per
keystroke: the analysis reads the files from disk, so the editor and the server agree exactly
at the moment of a save, and a half-typed document never produces a screenful of findings
about a mistake nobody has finished making yet. The *text* of every open document is
nonetheless kept, and kept current through ``didChange``: a position the client sends, an edit
the client will apply and the place a finding is drawn are about what is on screen. An edit
computed from a stale file and applied to a buffer with one extra line rewrote an unrelated
line, and a finding drawn at the file's line in such a buffer underlined another key.
"""

from __future__ import annotations

import bisect
import contextlib
import io
import queue
import re
import sys
import threading
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import IO, Any, Final, Protocol
from urllib.parse import urlparse
from urllib.request import url2pathname

from ddd import __version__
from ddd.build_info import BUILD_INFO_FILENAME, BuildInfo
from ddd.editing import EditError
from ddd.ir import DataDictionary
from ddd.loading import DDD_SUFFIX
from ddd.lsp.diagnostics import collect
from ddd.lsp.discovery import build_files, load_builds
from ddd.lsp.edits import QUICK_FIX, UNKNOWN_UNIT, Asked, Elsewhere, actions_across
from ddd.lsp.hover import (
    describe_across,
    describe_constant,
    describe_external,
    describe_type,
    resolve,
)
from ddd.lsp.navigation import (
    Descriptions,
    Loaded,
    Reach,
    Site,
    constant_at,
    definition,
    index,
    is_alone,
    is_local,
    locations,
    named_by_a_header,
    read_project,
    references,
    rename_edits,
    rename_problem,
    renameable_at,
    subject_at,
    told_apart,
    type_at,
    workspaces,
)
from ddd.lsp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    REQUEST_FAILED,
    SERVER_NOT_INITIALIZED,
    MessageError,
    ProtocolError,
    error,
    notification,
    read_message,
    request,
    response,
    write_message,
)
from ddd.lsp.ranges import Document, differs_from_disk, read
from ddd.lsp.units import (
    UnitPlan,
    UnitRefusalError,
    rename_unit,
    text_edits,
    unit_drift,
    unit_project,
)

_DID_OPEN: Final = "textDocument/didOpen"
_DID_CHANGE: Final = "textDocument/didChange"
_DID_CLOSE: Final = "textDocument/didClose"
_DID_SAVE: Final = "textDocument/didSave"
"""A save is the moment the text on disk is known to be the text on screen."""

_DID_CHANGE_WATCHED: Final = "workspace/didChangeWatchedFiles"
"""A description or a build record changed on disk without passing through the editor.

The other half of "the findings are the disk's": a build writes description files, a branch
switch rewrites all of them, a configure rewrites the record, and none of them is a document
event. The server asks the client to watch them (:meth:`Server._watch`).
"""

_INITIALIZED: Final = "initialized"
"""The client has the answer to ``initialize``: the protocol's moment to register a capability."""

_REGISTER: Final = "client/registerCapability"
_WATCHER: Final = "ddd-watch"
"""The id of the server's one registration, the watcher, and of the request that asks for it."""

_WATCHED: Final = (f"**/*{DDD_SUFFIX}", f"**/{BUILD_INFO_FILENAME}")
"""What the watcher watches: every description of the workspace, and every build record."""

_DID_CHANGE_FOLDERS: Final = "workspace/didChangeWorkspaceFolders"
"""The client added workspace folders, or removed some, while the session runs."""

_DEFINITION: Final = "textDocument/definition"
_NAVIGATING: Final = frozenset({_DEFINITION, "textDocument/references"})
_HOVER: Final = "textDocument/hover"
_PREPARE_RENAME: Final = "textDocument/prepareRename"
_RENAME: Final = "textDocument/rename"
_CONFIRM: Final = "ddd-confirm"
_CODE_ACTION: Final = "textDocument/codeAction"


_ESCAPED_DRIVE: Final = re.compile(r"^/([A-Za-z])%3[Aa](?=/)")
"""``/c%3A/...``: a drive letter whose colon the client escaped, which VS Code always does.

Only where more path follows - VS Code never sends the drive alone - and only where there is
a drive position to escape at all: the leading slash this matches is the one ``file:///...``
puts before a drive, which a network share's host takes the place of instead.
"""


def uri_to_path(uri: str) -> Path:
    """The file a ``file://`` uri names, undoing the escaping a client applies to it.

    ``url2pathname`` unescapes on its way, so nothing may unescape before it: doing both
    decoded a percent sequence twice and named a different file, which made this the inverse
    of ``Path.as_uri()`` for every path except the ones that actually needed escaping. A
    document called ``a%20b.ddd.json`` came back as ``a b.ddd.json``, and the diagnostics
    published for it went out under a uri the client could match to nothing on screen.

    The one exception is the drive colon. ``Path.as_uri()`` writes ``file:///C:/...`` and
    VS Code sends ``file:///c%3A/...``, and ``url2pathname`` decides whether there is a drive
    by looking for a literal colon *before* it unquotes - so the escaped spelling was read as
    no drive at all and came back as the relative path ``/c:/...``, which names no file and
    cannot be turned back into a uri. The server died on the first document a Windows client
    opened. Only that colon is restored here; everything else stays escaped for the call.

    Any other scheme is refused rather than read for whatever path-like text it holds. An
    ``untitled:Untitled-1`` came back as the bare relative name, which then resolved against
    the server's working directory and published ``file-not-found`` for a phantom file in the
    workspace. There is nothing on disk to check, and saying so is the honest answer. The
    extension sends only ``file:`` (``extension.ts`` registers that scheme alone); another
    client need not.

    So is a path no file system can be asked about (:func:`_nameable`): a null character,
    escaped as ``%00`` or not, ended every request that read the document, with ``embedded
    null character``. Asked of the path as it is handed on, a network share's host in front of
    it: asked before the host was put there, a host holding one reached the file system all the
    same.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        msg = (
            f"'{uri}' is not a file: uri; this server checks descriptions on disk and has "
            f"nothing to say about a document that is not on it"
        )
        raise MessageError(INVALID_PARAMS, msg)
    path = parsed.path
    if not parsed.netloc or parsed.netloc == "localhost":
        path = _ESCAPED_DRIVE.sub(r"/\1:", path)
    path = url2pathname(path)
    if parsed.netloc and parsed.netloc != "localhost":
        # file://server/share/...: a network share, whose host is the start of the path - its
        # first segment is a share name, never a drive, however much it may look like one.
        path = f"//{parsed.netloc}{path}"
    if not _nameable(path):
        msg = (
            f"'{uri}' cannot name a file: its path holds a null character or a lone surrogate, "
            "which no file name holds"
        )
        raise MessageError(INVALID_PARAMS, msg)
    return Path(path)


def _nameable(path: str) -> bool:
    """Whether a file system can be asked about ``path`` at all.

    Not where it holds a null character, which ends a name early wherever a name is passed on;
    nor where it holds a surrogate standing alone, ``\\ud800`` written into the uri's json, which
    no utf-8 spells. Asked by encoding it as python encodes a name on posix, where a surrogate
    that decoding the uri made of a byte that is not utf-8 stands for that byte, and asked so on
    every platform alike: a uri is text, and a lone surrogate is none.
    """
    if "\x00" in path:
        return False
    try:
        path.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:
        return False
    return True


def _field[T](value: Any, wanted: type[T], named: str) -> T:
    """One field of the client's message, or a refusal that names what was wrong with it.

    Every field a handler reads goes through here rather than being indexed, because these
    are somebody else's bytes and not this server's invariant - but for what a notification
    carries beside its document, which is read for what it holds (:meth:`Server._remember`). A
    field that is wrong is the client's mistake rather than a defect of the server, and is
    answered as one: refused with the invalid-parameters error naming it, and nothing written to
    stderr, where the net the module docstring describes writes the trace of a defect. Indexed
    instead, a frame without the ``params`` every editor sends would reach that net as the
    server's own defect, with no field named.

    A field the protocol lets a client leave out is asked for with its default, and so is one it
    requires and this server tolerates the absence of - a handshake's ``capabilities`` and
    ``rootUri``, a code action context's ``diagnostics``; one it lets the client send as null is
    asked for only where it is not null; any other value of another shape is refused. ``true`` is
    no number, although python counts a ``bool`` an ``int``.
    """
    if not isinstance(value, wanted) or (wanted is int and isinstance(value, bool)):
        msg = f"'{named}' is missing or is not {wanted.__name__}"
        raise MessageError(INVALID_PARAMS, msg)
    return value


def _count(value: Any, named: str) -> int:
    """One coordinate of a position the client sent: a count from zero, as the protocol's
    ``uinteger`` is. A line before the first ended a hover with ``IndexError``, every request
    at a position reading it the same way."""
    count = _field(value, int, named)
    if count < 0:
        msg = f"'{named}' is {count}; a position counts lines and characters from 0"
        raise MessageError(INVALID_PARAMS, msg)
    return count


def _reported(context: dict[str, Any]) -> list[dict[str, Any]]:
    """The findings a code action is asked about: a list of them, left out where it asks about
    none, each an object whose ``code``, where it states one, is a number or a string - another
    server's findings among them, which are told from this one's by that code. A finding that is
    no object, or a code of another shape, raised: it ended the session, and inside the net it
    cost the answer, naming no field."""
    named = "params.context.diagnostics"
    reported = _field(context.get("diagnostics", []), list, named)
    for entry in reported:
        code = _field(entry, dict, f"{named}[]").get("code", "")
        if isinstance(code, bool) or not isinstance(code, int | str):
            msg = f"'{named}[].code' is not int or str"
            raise MessageError(INVALID_PARAMS, msg)
    return reported


def _named_folders(value: Any, named: str) -> list[Path]:
    """The workspace folders a list of the client's names, each by its uri: what ``initialize``
    names, and what a change of the folders adds or removes."""
    return [
        uri_to_path(_field(_field(folder, dict, f"{named}[]").get("uri"), str, f"{named}[].uri"))
        for folder in _field(value, list, named)
    ]


def _answered(message: dict[str, Any]) -> bool:
    """Whether the server answers a message: a request carries an ``id`` and a ``method``. One
    carrying an ``id`` and no ``method`` is the client's answer to a request of the server's, and
    is answered nothing (:meth:`Server._act`)."""
    return "id" in message and "method" in message


type _Span = tuple[tuple[int, int], tuple[int, int]]
"""Where a text edit lies: its start and its end, each a line and a character."""


def _span(edit: dict[str, Any]) -> _Span:
    start, end = edit["range"]["start"], edit["range"]["end"]
    return (start["line"], start["character"]), (end["line"], end["character"])


def _meet(one: _Span, other: _Span) -> bool:
    """Whether two edits of one text cannot both be applied, as a client applies a file's edits
    all at once: where they overlap, or insert at one place, which of the two comes first nothing
    says."""
    return (one[0] < other[1] and other[0] < one[1]) or one[0] == one[1] == other[0] == other[1]


@dataclass(frozen=True, slots=True)
class _Made:
    """One edit a rename has gathered for a file (:meth:`Server._gather`)."""

    span: _Span
    text: str
    by: Loaded
    """The project whose plan made it."""


type _Read = dict[str, Any] | Exception | None
"""One thing the reading thread took off the stream (:meth:`Server.run`): a message; a frame
holding none, a :class:`~ddd.lsp.protocol.MessageError` to answer; what ended the reading, broken
framing or whatever else the stream raised; or ``None``, the end of the stream."""


class _Inbox(Protocol):
    """Where the server takes what was read from: the queue the reading thread fills."""

    def get(self) -> _Read:
        """The next thing read, waited for where none is queued."""
        ...

    def qsize(self) -> int:
        """How many things read are queued and not taken yet."""
        ...


class Server:
    """One conversation with one language client."""

    def __init__(
        self,
        reader: IO[bytes],
        writer: IO[bytes],
        root: Path | None = None,
        build_directories: Sequence[Path] = (),
    ) -> None:
        self.reader = reader
        self.writer = writer
        self._started_in = root or Path.cwd()
        """The folder the server answers in while the client names none (:attr:`roots`)."""
        self._folders: list[Path] = []
        """The workspace folders the client names, first one first, as it adds and removes them."""
        self.build_directories = list(build_directories)
        self._published: dict[Path, str] = {}
        """Each file whose findings are on screen, by its resolved path, with the uri they went out
        under: a file goes out under its resolved spelling until the client opens it under another,
        and its findings are then withdrawn under the first, where nothing would publish again
        (:meth:`_publish`)."""
        self._announced: tuple[str, ...] | None = None
        """What was last said about the configured projects, so it is not said every save."""

        self._refused: dict[Path, str] = {}
        """Record -> why this version cannot use it, found alongside the usable ones."""

        self._told: dict[Path, set[str]] = {}
        """Project description -> why the quick fixes are withheld from it, as the log has been
        told (:meth:`_withheld`), until a refresh reads the project whole (:meth:`_mended`)."""

        self._builds: list[BuildInfo] | None = None
        """The build records, found once and kept until the next refresh.

        Finding them means walking every configured build directory looking for the record,
        and a build directory holds tens of thousands of object files. Doing that per hover -
        which is what asking :func:`discover` in each handler amounted to - put a directory
        walk behind a gesture that is supposed to feel like a tooltip.
        """

        self._projects: dict[Path, tuple[list[Loaded], dict[Path, str]]] = {}
        """The projects containing each document, loaded once and kept until the next refresh,
        each with why the descriptions the search for them could not read could not be read.

        The same reasoning one level up: answering a hover used to read and validate every
        description file of every image the component is linked into, twice over - the
        external type lookup and the resolution each walked the projects from scratch.

        Keeping them is sound precisely because of what this server already promises: it reads
        from disk at open and at save and nowhere else, which is what its ``textDocumentSync``
        tells the client. Between two saves the answer cannot have changed, so the second
        question is entitled to the first one's answer; :meth:`_forget` is where that stops.
        """

        self._described = Descriptions()
        """Every description read since :meth:`_forget`, by the path it resolves to, as each
        question reads them (:meth:`_descriptions`): kept for the reason the projects are, one
        level down. The quick fixes reach the projects holding each file they write, as a rename
        does (:meth:`_holding`), and a client asks for them at every move of the caret: read
        anew for each request, every build's description and every candidate above those files
        was read again at each move.
        """

        self._dictionaries: dict[Path, DataDictionary | None] = {}
        """Project description -> what a hover resolved that project to, kept until
        :meth:`_forget` for the reason the projects are: every hover resolved the whole project
        again.

        Resolved for the hover, as :func:`~ddd.lsp.hover.resolve` makes it, rather than taken
        from a check: a check analyses no project whose read reported an error, and a hover
        resolves what did load all the same. Kept per description, so that each project a hover
        answers from is resolved once.
        """

        self._open: dict[Path, tuple[str, int | None]] = {}
        """The text and version of every open document, keyed by its resolved path.

        What positions and edits are computed against. The analysis still reads the disk - a
        finding is about what is saved - but a rename box opens where the caret is, and the
        edit that follows is applied to the buffer, so both have to be read from it.
        """

        self._versioned_edits = False
        """Whether the client takes ``documentChanges``, which carry the version an edit is for."""

        self._annotated_edits = False
        """Whether the client also announced ``changeAnnotationSupport``.

        An annotated text edit exists only inside ``documentChanges``, so this is read apart
        from the other and counts only beside it (:meth:`_workspace_edit`).
        """

        self._registers = False
        """Whether the client takes the registration of a watcher while the session runs, which it
        announces as ``workspace.didChangeWatchedFiles.dynamicRegistration``."""

        self._watching = False
        """Whether the server has asked the client for its watcher (:meth:`_watch`)."""

        self._initialised = False
        """Whether the client has said what the workspace is, which it does exactly once.

        Before it has, nothing it asks can be answered against the right folders: the roots
        are still this process's defaults, so a hover would be resolved through whatever
        project happens to sit above the working directory. The protocol gives that refusal
        its own code, and gives the client the obligation to ask again after ``initialize``.
        """

        self._shutting_down = False
        """Whether the client has asked the server to wind down.

        After it has, the client has stopped reading answers, so serving a request is work for
        nobody - and the exit code says which of the two ways the run ended: the planned one,
        or a stop nobody asked to prepare.
        """

        self._spelled: dict[Path, str] = {}
        """Resolved path -> the uri the client used for it, for every document it opened.

        A client's uri need not be the one ``Path.as_uri()`` writes for the file it names: a
        workspace opened through a junction, a ``subst`` or mapped drive, a symlinked
        directory or with a different case spells every path in it differently from the disk,
        and the loader resolves everything it reads. A client keys what it draws on the uri
        *string*, so publishing the resolved spelling sends the squiggles to a resource it is
        not showing and hands a rename to a document that is not on screen.

        Only what the client opened is in here, because only for those has it said how it
        spells them. Every other file keeps the resolved spelling, which is the only one
        anybody knows.
        """

        self._marked: list[tuple[str, Path]] = []
        """Each document the next check checks, by its resolved path, with the method that
        marked it, in the order they were marked; a document marked twice is checked once.

        ``didOpen``, ``didSave`` and a watched change mark their documents rather than checking
        them, and the marked documents are checked together (:meth:`_serve`): with ten documents
        open, a save and the watch event that follows it were eleven analyses of one project.
        """

    def run(self) -> int:
        """Serve until the client says to stop, or stops talking.

        The stream is read on a thread of its own into a queue, and the messages are handled
        here, one at a time (:meth:`_serve`). Reading ahead is what tells a message queued
        behind another from one not sent yet: a blocking read of the stream cannot, and a pipe
        has no portable way to look ahead. The thread is a daemon, since it is still waiting
        for the next frame when the run ends.

        One bad frame is not the end of the conversation: a body that is not a request gets
        the json-rpc refusal it defines a code for, and the loop reads on, as it does past a
        message the server failed to answer (:meth:`_defect`). Only broken framing ends the
        run, because after it nothing on the stream can be trusted - and that is said once on
        stderr, where the log goes, never on stdout, which is the wire.
        """
        inbox: queue.SimpleQueue[_Read] = queue.SimpleQueue()
        threading.Thread(target=self._read, args=(inbox,), daemon=True, name="ddd-lsp-read").start()
        return self._serve(inbox)

    def _read(self, inbox: queue.SimpleQueue[_Read]) -> None:
        """Read every frame of the stream into ``inbox``, in order, until the reading ends.

        Run on the reading thread, which only reads: everything the server writes is written
        on the server's thread, in order. A frame holding no message is handed over to be
        answered there, and so is what ended the reading - the end of the stream, broken
        framing, or anything else the stream raised - so that the run ends as it always has.
        """
        while True:
            try:
                message = read_message(self.reader)
            except MessageError as fault:
                inbox.put(fault)
                continue
            except Exception as fault:
                inbox.put(fault)
                return
            inbox.put(message)
            if message is None:
                return

    def _serve(self, inbox: _Inbox) -> int:
        """Handle what the reading thread queued, one message at a time, and check the documents
        the messages mark together.

        The marked documents are checked once every message that was already queued behind the
        first of them is handled, so a save and the watch event the editor sends for it are one
        check, and so are the ``didOpen`` an editor sends for each file it opens to apply a
        rename. Two things come first: a message that is answered, and the end of the run, since
        an answer may be about what the check finds, and a check due when the run ends is still
        owed - the client's answer to a request of the server's is answered nothing, and does not
        come first (:func:`_answered`). Nothing waits for a message that has not arrived: a check
        held until the queue empties would wait for as long as a client sends ``didChange`` at
        every keystroke.
        """
        behind = 0  # the messages queued behind the first marked document, not handled yet
        while True:
            read = inbox.get()
            if not isinstance(read, dict) or _answered(read):
                self._settle()
            if read is None:
                return 0
            if isinstance(read, ProtocolError):
                print(f"ddd: {read}", file=sys.stderr)
                return 1
            if isinstance(read, MessageError):
                write_message(self.writer, error(None, read.code, str(read)))
                continue
            if isinstance(read, Exception):
                raise read
            batched = bool(self._marked)
            if not self._take(read):
                self._settle()
                # An exit that was prepared for is a clean end and anything else is not, which
                # is the one thing an exit code can tell a client that is watching the process.
                return 0 if self._shutting_down else 1
            if self._marked:
                behind = behind - 1 if batched else inbox.qsize()
                if behind <= 0:
                    self._settle()

    def _take(self, message: dict[str, Any]) -> bool:
        """Act on one message inside the net; ``False`` means the client asked the server to
        exit.

        What the message marks is left for :meth:`_serve` to check, which does that inside the
        net as well (:meth:`_settle`).
        """
        try:
            return self._act(message)
        except MessageError as fault:
            # The frame was read and the method understood; what the client sent with it was
            # not the shape the method takes. A request gets that as its answer and a
            # notification gets nothing, which is what a notification always gets - a message
            # with no ``id`` is a notification, and answering one with an error under
            # ``"id": null`` is a line in the client's output channel that names no request the
            # reader can go and look at. Either way the next message is still read.
            if "id" in message:
                write_message(self.writer, error(message["id"], fault.code, str(fault)))
        except Exception as fault:
            # Anything else is a defect of this server's own in answering this one message,
            # which costs that answer and not the session (the module docstring).
            self._defect(message, fault)
        return True

    def _settle(self) -> None:
        """Check the marked documents inside the net.

        A defect in that check is answered as one in a notification is, since only
        notifications mark: with nothing, and its trace on stderr naming the methods that marked
        the documents. They are unmarked before the check runs, so the next message does not
        meet the same defect again.
        """
        marking = ", ".join(dict.fromkeys(method for method, _ in self._marked))
        try:
            self._refresh_marked()
        except Exception as fault:
            self._defect({"method": marking}, fault)

    def _defect(self, message: dict[str, Any], fault: Exception) -> None:
        """Answer a message this server failed on through a defect of its own, and say so.

        The trace goes to stderr, which a client keeps as the server's log. A request is
        answered with the protocol's internal error, naming the method and the fault, which a
        client shows as a failed request; a notification is answered with nothing, as ever.
        """
        method = message.get("method")
        print(
            f"ddd: {method} failed on a defect of this server, and the session goes on",
            file=sys.stderr,
        )
        traceback.print_exception(fault, file=sys.stderr)
        if "id" in message:
            failed = (
                f"{method} failed on a defect of ddd ({type(fault).__name__}: {fault}); the trace "
                "is in the server's log"
            )
            write_message(self.writer, error(message["id"], INTERNAL_ERROR, failed))

    def _out_of_turn(self, method: Any) -> tuple[int, str] | None:
        """Why this message may not be acted on where the conversation has got to.

        The protocol puts a beginning and an end on a session and says what happens outside
        them, and both halves matter here rather than being ceremony. Before ``initialize``
        the workspace folders are this process's defaults, so an answer given then is an
        answer about the wrong project; after ``shutdown`` the client has stopped listening,
        so an answer is work done for nobody. ``exit`` is outside all of it - a client that
        gave up before saying hello still gets a server that goes away.
        """
        if not self._initialised:
            if method == "initialize":
                return None
            return (
                SERVER_NOT_INITIALIZED,
                f"'{method}' arrived before 'initialize'; the server does not know what the "
                f"workspace is yet, so ask again once it has answered",
            )
        if method == "initialize":
            return (INVALID_REQUEST, "this session is already initialized")
        if self._shutting_down:
            return (
                INVALID_REQUEST,
                f"'{method}' arrived after 'shutdown'; this session is winding down and takes "
                f"nothing further",
            )
        return None

    def _handle(self, message: dict[str, Any]) -> bool:
        """Act on one message and check what it marked, outside the net; ``False`` means the
        client asked the server to exit.

        What :meth:`_serve` does with a message nothing is queued behind, one message at a time:
        each call that marks a document checks it before returning.
        """
        keep_going = self._act(message)
        self._refresh_marked()
        return keep_going

    def _refresh_marked(self) -> None:
        """Check every marked document together, and unmark them first.

        A marked path that is neither on disk nor open is not checked: it is deleted, whether a
        watch event reported it so or it went after it was marked, and a run started from it is
        what reports a file that does not exist (:meth:`_withdraw_deleted`).
        """
        marked, self._marked = self._marked, []
        documents = [
            path
            for path in dict.fromkeys(path for _, path in marked)
            if path.exists() or path in self._open
        ]
        if documents:
            self.refresh(*documents)

    def _act(self, message: dict[str, Any]) -> bool:
        """Act on one message, marking the documents it asks to be checked rather than checking
        them; ``False`` means the client asked the server to exit.

        A message naming no method is answered nothing: carrying an ``id``, it is the client's
        answer to a request of the server's (:meth:`_watch`). It was refused - as a request of a
        method named ``None``, or as one arriving before ``initialize`` or after ``shutdown`` -
        and the client showed an error in its log about a message it had sent right.
        """
        if "method" not in message:
            return True
        method = message.get("method")
        request_id = message.get("id")
        if method == "exit":
            return False
        refusal = self._out_of_turn(method)
        if refusal is not None:
            # A notification gets nothing, here as everywhere else; the protocol names the
            # dropping of an early one outright.
            if request_id is not None:
                write_message(self.writer, error(request_id, *refusal))
            return True
        if method == "initialize":
            self._initialise(_field(message.get("params", {}), dict, "params"))
            self._initialised = True
            write_message(self.writer, response(request_id, self._capabilities()))
        elif method == _INITIALIZED:
            self._watch()
        elif method == _DID_CHANGE_FOLDERS:
            self._folders_changed(message)
        elif method == "shutdown":
            self._shutting_down = True
            write_message(self.writer, response(request_id, None))
        elif method == _DID_OPEN:
            self._remember(message)
            self._mark(_DID_OPEN, self._opened(message))
        elif method == _DID_CHANGE:
            self._remember(message)
        elif method == _DID_CLOSE:
            self._open.pop(self._document(message).resolve(), None)
        elif method == _DID_SAVE:
            self._mark(_DID_SAVE, self._document(message))
        elif method == _DID_CHANGE_WATCHED:
            self._watched(message)
        elif method in _NAVIGATING:
            write_message(self.writer, response(request_id, self._navigate(method, message)))
        elif method == _HOVER:
            write_message(self.writer, response(request_id, self._hover(message)))
        elif method == _PREPARE_RENAME:
            prepared = self._prepare_rename(message)
            write_message(self.writer, response(request_id, prepared))
        elif method == _RENAME:
            self._answer_rename(request_id, message)
        elif method == _CODE_ACTION:
            write_message(self.writer, response(request_id, self._actions(message)))
        elif request_id is not None:
            # A request always gets an answer, even a refusal: a client that is still waiting
            # on one looks exactly like a server that has died.
            write_message(
                self.writer, error(request_id, METHOD_NOT_FOUND, f"unsupported method {method}")
            )
        return True

    def _document_uri(self, message: dict[str, Any]) -> str:
        """The document a request is about, exactly as the client spelled it."""
        params = _field(message.get("params"), dict, "params")
        target = _field(params.get("textDocument"), dict, "params.textDocument")
        return _field(target.get("uri"), str, "params.textDocument.uri")

    def _document(self, message: dict[str, Any]) -> Path:
        """The file a request is about."""
        return uri_to_path(self._document_uri(message))

    def _opened(self, message: dict[str, Any]) -> Path:
        """The document the client just opened, noted down under the words it used for it."""
        spelling = self._document_uri(message)
        path = uri_to_path(spelling)
        self._spelled[path.resolve()] = spelling
        return path

    def _uri(self, path: Path) -> str:
        """The uri to answer under for a file: the client's own, where it gave one, and otherwise
        the one its resolved path makes - the only spelling known for a file the client never
        opened, and the only one a uri can be built from where the path is relative."""
        resolved = path.resolve()
        spelled = self._spelled.get(resolved)
        return resolved.as_uri() if spelled is None else spelled

    def _respell(self, uri: str) -> str:
        """The same, for a uri already built from a resolved path somewhere below."""
        return self._spelled.get(uri_to_path(uri).resolve(), uri)

    def _remember(self, message: dict[str, Any]) -> None:
        """Keep what the client says the document now contains.

        ``didOpen`` carries the whole text; ``didChange`` carries it too, because the server
        asks for full-content synchronisation (``change: 1``): a description file is small,
        and applying incremental edits to a kept copy is a second place to get a position
        wrong. An entry carrying a ``range`` is an incremental change sent anyway - a client
        that did not honour ``change: 1`` - and its text is a fragment rather than the
        document, so it is left alone rather than stored as if it were one; the last known
        text stays in charge until a compliant change or a save corrects it. A notification
        without text - a client that sends none - leaves the disk copy in charge too, which is
        what the server did for everything before it kept buffers.
        """
        params = _field(message.get("params"), dict, "params")
        target = _field(params.get("textDocument"), dict, "params.textDocument")
        path = uri_to_path(_field(target.get("uri"), str, "params.textDocument.uri")).resolve()
        version = target.get("version")
        text = target.get("text")
        changes = params.get("contentChanges")
        if (
            isinstance(changes, list)
            and changes
            and isinstance(changes[-1], dict)
            and "range" not in changes[-1]
        ):
            text = changes[-1].get("text")
        if isinstance(text, str):
            self._open[path] = (text, version if isinstance(version, int) else None)

    def _watched(self, message: dict[str, Any]) -> None:
        """Mark for a check again, because what was read from disk is no longer what is on it.

        Every open document, rather than the files that changed: a document is published
        through the project above it, so a change in a file nobody has open is precisely the
        case that moves a finding onto one somebody does. With nothing open there is still a
        Problems list on screen describing the project as it was. The descriptions that changed
        are roots to check it from, but for one deleted (:meth:`_refresh_marked`); a build record
        that changed changes which projects there are and their severities, so every file whose
        findings are on screen is checked again, under the records the next check searches for
        (:meth:`_mark` forgets what was found). A record is never checked as a description, nor is
        anything else the client reports that is none: so checked, it was read as a component and
        given a finding of its own.

        Marked, and checked together: checked one at a time, ten open documents of one project
        were ten analyses of it, at every save the editor's watcher reports.
        """
        params = _field(message.get("params"), dict, "params")
        changes = _field(params.get("changes"), list, "params.changes")
        touched = [
            uri_to_path(
                _field(
                    _field(change, dict, "params.changes[]").get("uri"),
                    str,
                    "params.changes[].uri",
                )
            )
            for change in changes
        ]
        documents = sorted(self._open)
        if not documents:
            documents = [path for path in touched if path.name.lower().endswith(DDD_SUFFIX)]
            if any(path.name == BUILD_INFO_FILENAME for path in touched):
                documents.extend(sorted(self._published))
        self._mark(_DID_CHANGE_WATCHED, *documents)
        self._withdraw_deleted()

    def _watch(self) -> None:
        """Ask the client to watch every description and every build record, once, where it takes
        a registration while the session runs (:attr:`_registers`).

        The watcher was the extension's, so a client launching the server itself heard of no file
        changed behind the editor, and the extension's watched the descriptions alone: a
        configure rewriting only a build record left the old severities on screen until the next
        save. A client that takes no registration is asked for nothing and gets no watch events,
        as it got none from the server before. Asked again, a client would watch twice, and send
        every change twice.
        """
        if not self._registers or self._watching:
            return
        self._watching = True
        registration = {
            "id": _WATCHER,
            "method": _DID_CHANGE_WATCHED,
            "registerOptions": {"watchers": [{"globPattern": glob} for glob in _WATCHED]},
        }
        write_message(self.writer, request(_WATCHER, _REGISTER, {"registrations": [registration]}))

    def _folders_changed(self, message: dict[str, Any]) -> None:
        """Follow the workspace folders the client adds and removes while the session runs, and
        mark for a check again what the change moves.

        A folder added is walked by the search for build records and by the search above a
        document as if the client had named it at ``initialize``, and a folder removed as if it
        had never been named: a document of a folder added later was checked as one outside every
        folder, on its own, though its project was there to be found. What was published under a
        removed folder alone is withdrawn, since no check need report on it again and its findings
        would then stay on screen for good - but for an open document, which is checked again with
        the others, as one outside every folder where no folder that stays holds it. What is on
        screen and stays is checked again as well, open document or none: the findings of a file
        outside the folder, or under one that stays, may be the removed folder's checks alone.

        Every field is read before any is kept, as at ``initialize``: a change refused for one
        folder takes none of the others.
        """
        params = _field(message.get("params"), dict, "params")
        event = _field(params.get("event"), dict, "params.event")
        added = _named_folders(event.get("added"), "params.event.added")
        gone = {
            folder.resolve()
            for folder in _named_folders(event.get("removed"), "params.event.removed")
        }
        kept = [folder for folder in self._folders if folder.resolve() not in gone]
        self._folders = kept + added
        roots = [root.resolve() for root in self.roots]
        for path in sorted(self._published):
            if (
                path not in self._open
                and not gone.isdisjoint(path.parents)
                and all(root not in path.parents for root in roots)
            ):
                self._publish(path, [])
        self._mark(_DID_CHANGE_FOLDERS, *sorted({*self._open, *self._published}))

    def _mark(self, method: str, *documents: Path) -> None:
        """Mark documents for the next check, which checks them together, and drop at once what
        was read from disk (:meth:`_forget`): a file saved or watched changing is no longer what
        was read, and one opened is about to be read again."""
        self._forget()
        self._marked.extend((method, document.resolve()) for document in documents)

    def _cache(self, path: Path | None = None) -> dict[Path, Document]:
        """A document cache seeded with every open buffer, under both spellings of its path.

        The index is built from resolved paths and a request names the path the client
        spelled, so the buffer is filed under both; anything not open is read from disk on
        first use, as before.
        """
        cache: dict[Path, Document] = {}
        for resolved, (text, _) in self._open.items():
            cache[resolved] = Document(text)
        if path is not None and path.resolve() in cache:
            cache[path] = cache[path.resolve()]
        return cache

    def _version_of(self, path: Path) -> int | None:
        """The version the client last announced for a document, or ``None`` if it is not open."""
        entry = self._open.get(path.resolve())
        return entry[1] if entry is not None else None

    def _at(self, message: dict[str, Any], key: str = "position") -> dict[str, int]:
        """The position a request is about, which a code action sends as the start of a range,
        each of its coordinates named where it is refused as the field it is."""
        params = _field(message.get("params"), dict, "params")
        named = f"params.{key}"
        where = _field(params.get(key), dict, named)
        if key == "range":
            named = "params.range.start"
            where = _field(where.get("start"), dict, named)
        return {axis: _count(where.get(axis), f"{named}.{axis}") for axis in ("line", "character")}

    def _builds_now(self) -> list[BuildInfo]:
        """The build records, found once per refresh rather than once per keypress.

        A record naming its project by a relative path is refused here, and its reason
        announced as any record's this version cannot use is. ``ddd build-info`` writes the path
        absolute, because whoever reads a record is not in the directory the build ran in: a
        relative one names a file under whatever directory reads it, so it was analysed from
        this server's working directory, and a finding filed at it had no uri, which ended the
        session. Refused by the server rather than where every record is read, which ``ddd gui``
        does too.

        Relative is a path with no root, whose file depends on the directory reading it. A root
        without a drive is kept: on Windows it is what a record written in a container names,
        ``/work/...``, which is then said to be no such file, as before.
        """
        if self._builds is None:
            self._refused = {}
            self._builds = []
            # Each record once, however many folders reach it: a ``-b`` naming one directory from
            # every folder, as an absolute one does, found its record once per folder, and the
            # project was announced and analysed as often.
            records = dict.fromkeys(
                record
                for root in self.roots
                for record in build_files(root, self.build_directories)
            )
            for record in records:
                for info in load_builds([record], self._refused):
                    if Path(info.project).root:
                        self._builds.append(info)
                    else:
                        self._refused[record] = (
                            f"its project '{info.project}' is a relative path, which a build "
                            "never writes: it names a different file from each directory the "
                            "record is read in"
                        )
        return self._builds

    @property
    def roots(self) -> list[Path]:
        """The workspace folders, first one first - a multi-root workspace has several - as the
        client names them and as it adds and removes them; while it names none, the folder the
        server was started in, where a relative ``-b`` is read too (:meth:`_builds_now`)."""
        return self._folders or [self._started_in]

    @property
    def root(self) -> Path:
        """The first workspace folder: where the build records are looked for by default."""
        return self.roots[0]

    def _root_for(self, document: Path) -> Path:
        """The workspace folder the document is under, else the first one.

        What bounds the search for a project above the document: with several folders open,
        the one that does not contain the file would stop that search at its first step.
        """
        resolved = document.resolve()
        for root in self.roots:
            if root.resolve() in resolved.parents:
                return root
        return self.roots[0]

    def _projects_of(
        self, document: Path, descriptions: Descriptions | None = None
    ) -> list[Loaded]:
        """The projects containing a document, loaded once per refresh; where they are loaded
        now, ``descriptions`` takes what the search reads (:func:`~ddd.lsp.navigation.workspaces`).
        """
        return self._searched(document, descriptions)[0]

    def _searched(
        self, document: Path, descriptions: Descriptions | None = None
    ) -> tuple[list[Loaded], dict[Path, str]]:
        """:meth:`_projects_of`, with why each description the search could not read could not
        be read."""
        found = self._projects.get(document)
        if found is None:
            if descriptions is None:
                descriptions = self._descriptions()
            projects = workspaces(
                self._builds_now(), document, self._root_for(document), descriptions
            )
            found = self._projects[document] = (projects, dict(descriptions.failed))
        return found

    def _reach(self, document: Path) -> Reach:
        """Every project a rename, or a quick fix, started from ``document`` reaches, each
        description read at most once for it - and once since :meth:`_forget`, whatever asked."""
        descriptions = self._descriptions()
        start, failed = self._searched(document, descriptions)
        descriptions.failed.update(failed)
        return Reach(self._builds_now(), start, self._root_for, descriptions)

    @staticmethod
    def _unreadable(loaded: Loaded) -> str | None:
        """Why this project may not be edited yet, or nothing when it may.

        A project is indexed from what loaded, so a file a ``schema`` error dropped mid edit
        declares nothing as far as the index knows: a rename then rewrites every other file
        and leaves that one holding the old name, and a quick fix offers to remove a key "no
        other declaration has" while the unloaded producer has exactly that key. Refused whole
        rather than performed in part, which is the answer a drifted buffer already gets: a
        rename with this sentence, and the quick fixes by offering none (:meth:`_withheld`).

        Each file is said to be what it is. One that did not load - a ``schema`` error dropped
        it, it holds no text, or an include names it and it is not there - did not load; one
        that loaded with an error, as the files holding a block for a plugin that does not
        import do, has an error, which stops the project being analysed and did not stop it
        reading the file. Two files of one name are told apart by their paths
        (:func:`~ddd.lsp.navigation.told_apart`).
        """
        if not loaded.unreadable:
            return None
        named = dict(zip(loaded.unreadable, told_apart(loaded.unreadable), strict=True))
        unloaded = sorted(named[path] for path in loaded.unloaded)
        erring = sorted(named[path] for path in loaded.unreadable if path not in loaded.unloaded)
        said = [f"{', '.join(unloaded)} did not load"] if unloaded else []
        if erring:
            verb = "has" if len(erring) == 1 else "have"
            said.append(
                f"{', '.join(erring)} {verb} an error that stops the project being analysed"
            )
        them = "it" if len(loaded.unreadable) == 1 else "them"
        return (
            f"{' and '.join(said)}, so the rest of the project cannot be edited around {them}; "
            f"fix {them} and try again"
        )

    def _forget(self) -> None:
        """Drop what was read from disk, because it is about to be read again.

        Called wherever the files may no longer be what they were: at every message that marks
        a document for a check - an open, a save, a watched change - and at the check itself,
        and after a rename, which rewrites them from here.
        """
        self._builds = None
        self._projects.clear()
        self._described = Descriptions()
        self._dictionaries.clear()

    def _descriptions(self) -> Descriptions:
        """What the next question reads descriptions through: every description read since
        :meth:`_forget`, kept (:attr:`_described`). One a plugin stopped is read again, so that
        why it could not be read is the question's own (:attr:`~ddd.lsp.navigation.Reach.unread`):
        a rename is refused naming only a description its own search met.
        """
        kept = self._described
        for stopped in kept.failed:
            # Read, or restored from the search that read it (:meth:`_reach`), which a question
            # since may have read again already.
            kept.pop(stopped, None)
        kept.failed.clear()
        return kept

    def refresh(self, *documents: Path) -> None:
        """Re-run the checks over these documents and publish what they say about every file
        involved.

        Every configured build is run, not only the one that claims a document. A component
        linked into two images is in two projects and they need not agree, and the answer to
        which one the reader cares about is "both": whichever is broken is broken.

        The documents are checked together, each project once however many of them it holds or
        answers for (:func:`~ddd.lsp.diagnostics.collect`), each searched for above within the
        workspace folder holding it. What is found is the disk's, and an open document's
        findings are drawn in its buffer, as it stands on screen.
        """
        self._forget()
        builds = self._builds_now()
        self._announce(builds)
        # A record naming a project that is not there is dropped rather than analysed. Running
        # it produces one finding, "file does not exist", published against a file nobody can
        # open - and the thing actually wrong is the record, which the log has just said.
        reports = collect(
            [info for info in builds if Path(info.project).is_file()],
            documents,
            self._root_for,
            self._cache(),
        )
        # Only files with something to say, plus the ones this run reported on that had
        # something to say last time and no longer do - those need an empty list to withdraw
        # what is on screen. A file this run never reported on keeps what it has: with no record
        # covering it, a run looks at the document and the project above it, and says nothing
        # of another project, which is not the same as saying it is fine.
        current = {path for path, findings in reports.items() if findings}
        for path in sorted(current | (self._published.keys() & set(reports))):
            self._publish(path, reports.get(path, []))
        self._withdraw_deleted()
        self._mended()

    def _mended(self) -> None:
        """Forget why the quick fixes were withheld from each project this refresh reads whole.

        A reason stops standing when a refresh finds the project read whole, which is when its
        files can have changed. A mend saved and then a second break saved, with no request for
        the quick fixes between the two, is therefore said again at the next request, rather than
        taken for the first break standing still. Only a project something was said of is read
        again, so a refresh while nothing is withheld reads what it read before.
        """
        for path in sorted(self._told):
            loaded = read_project(path)
            if loaded is not None and not loaded.unreadable:
                del self._told[path]

    def _withdraw_deleted(self) -> None:
        """Empty the list of a file that is no longer there, once.

        A document the client has open is not gone, whatever the disk holds: a new file is
        checked from its buffer before it is ever saved.

        No run reports on a deleted file again, so without this its findings would stay on
        screen for good. Nothing is checked from its path: a run started there is what
        published a finding about a file that does not exist.
        """
        for path in sorted(
            path
            for path in self._published
            if not path.exists() and path.resolve() not in self._open
        ):
            self._publish(path, [])

    def _announce(self, builds: Sequence[BuildInfo]) -> None:
        """Say which projects were found, once, and again whenever that changes.

        Silence is the failure mode this guards against. A file no build claims is still
        checked - through a project file above it where there is one, and only for what one
        file can settle where there is not - so a missing record looks much like a project
        with nothing wrong with it, and the difference is invisible. Twice now that has been
        read as the checks having stopped working.

        A record naming a project that is not there gets said out loud, because it is the way
        this goes wrong in practice: a record written inside a container names a path that
        exists only in the container, and is then found, read and quietly of no use. A record
        this version cannot make sense of is the same thing one step earlier, and it is named
        here rather than left to the silence for the same reason.
        """
        lines = [
            f"{path}: {reason}; this record is ignored, so the project it names is not analysed"
            for path, reason in sorted(self._refused.items())
        ]
        lines.extend(
            f"{info.image or 'build'}: {info.project}"
            + (
                ""
                if Path(info.project).is_file()
                else "  <- no such file, so this project cannot be analysed"
            )
            for info in builds
        )
        if not lines:
            lines.append(
                "no ddd-build.json found: a file is checked through a project file above it "
                "that includes it, and on its own when there is none - so findings that need "
                "the whole project - a missing producer, two components disagreeing - are "
                "reported only as far as such a project reaches, and under the default "
                "severities rather than the build's. Configure the build, or pass "
                "-b <build directory>."
            )
        current = tuple(lines)
        if current == self._announced:
            return
        self._announced = current
        for line in lines:
            self._log(line)

    def _log(self, message: str) -> None:
        """Put a line in the client's log, where somebody looks when nothing is happening."""
        write_message(
            self.writer, notification("window/logMessage", {"type": 3, "message": message})
        )

    def _navigate(self, method: str, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Answer "where is this defined" and "where else is it used".

        Both questions are the same walk: work out which value the cursor is on, then ask each
        project that contains the file where that name is written down. A cursor on nothing
        answerable - a description, a number, whitespace - gives an empty list, which a client
        reads as "no jump from here" and shows as nothing happening.
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        found: list[Site] = []
        for loaded in self._projects_of(path):
            built = index(loaded.workspace)
            if method == _DEFINITION:
                found.extend(definition(built, document, path, pointer))
            else:
                found.extend(references(built, document, pointer))
        answers = locations(found, cache)
        for answer in answers:
            answer["uri"] = self._respell(answer["uri"])
        return answers

    def _hover(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """What the variable under the cursor turned out to be, once the project is resolved.

        ``None`` where there is nothing to say - a description, a number, whitespace, or a
        name no component declares - which a client shows by doing nothing at all.
        """
        path = self._document(message)
        document = read(path, self._cache(path))
        pointer = document.pointer_at(self._at(message))
        # A dimension spelled as a constant name is about the constant, not about the
        # object dimensioned by it - the reference wins over the declaration holding it,
        # exactly as an axis reference does for navigation. A type name answers as an
        # external type where it is one: such a type resolves to nothing on purpose, so the
        # dictionary cannot say what the workspace states outright - the name and the header.
        constant = constant_at(document, pointer)
        named_type = type_at(document, pointer)
        name = subject_at(document, pointer)
        if constant is None and named_type is None and name is None:
            return None
        projects = self._projects_of(path)
        described = None
        if named_type is not None:
            described = describe_external(projects, named_type)
        if described is None and constant is not None:
            # The first project's answer, as the summary of an object is: the others are resolved
            # only to say who writes an object and who reads it (:meth:`_summary`).
            dictionaries = map(self._dictionary_of, projects)
            first = next((found for found in dictionaries if found is not None), None)
            if first is not None:
                described = describe_constant(first, constant)
        if described is None and name is not None:
            described = self._summary(path, projects, name)
        if described is None and named_type is not None:
            # Last, and after the object: from a component a ``typename`` is about the
            # variable that names it. Inside a types file there is no variable to describe,
            # and the type's own entry answered nothing at all - the one place a name is
            # defined said less about it than anywhere else.
            described = describe_type(projects, named_type)
        if described is None:
            return None
        return {
            "contents": {"kind": "markdown", "value": described},
            "range": document.range_of(pointer),
        }

    def _dictionary_of(self, loaded: Loaded) -> DataDictionary | None:
        """What a hover answers from in one project holding the document: the project resolved as
        :func:`~ddd.lsp.hover.resolve` resolves it, once per description until :meth:`_forget`;
        ``None`` where a plugin stopped resolving it."""
        description = loaded.path.resolve()
        if description not in self._dictionaries:
            self._dictionaries[description] = resolve([loaded])
        return self._dictionaries[description]

    def _summary(self, path: Path, projects: Sequence[Loaded], name: str) -> str | None:
        """What a hover says of the data object ``name``, for every project holding ``path``
        (:func:`~ddd.lsp.hover.describe_across`), or nothing where none of them resolves.

        Who writes it and who reads it is every project's, as find references lists them, and so
        are the files that did not load. A project a plugin stopped resolving says nothing of
        either, and is named under them by what a rename's refusal names a project by
        (:meth:`~ddd.lsp.navigation.Reach.described`): left out in silence, a writer whose only
        reader is in that project was read by nobody.
        """
        resolved = [(loaded, self._dictionary_of(loaded)) for loaded in projects]
        dictionaries = [dictionary for _, dictionary in resolved if dictionary is not None]
        if not dictionaries:
            return None
        stopped = [loaded for loaded, dictionary in resolved if dictionary is None]
        named = []
        if stopped:
            reach = self._reach(path)
            named = [reach.described(loaded) for loaded in stopped]
        first, *others = dictionaries
        return describe_across(
            first,
            name,
            others=others,
            unloaded=sorted({file for loaded in projects for file in loaded.unloaded}),
            stopped=named,
        )

    def _prepare_rename(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Whether a rename may start here, and over which characters.

        Narrow where hovering is wide, and for a reason rather than out of caution: the editor
        opens its rename box *over the range this returns*. From a datatype, the only honest
        range would be a name several lines away, and a box appearing somewhere the pointer is
        not is worse than no box at all.
        """
        path = self._document(message)
        document = read(path, self._cache(path))
        pointer = document.pointer_at(self._at(message))
        subject = renameable_at(document, pointer)
        if subject is None:
            return None
        span = document.text_range_of(pointer)
        return None if span is None else {"range": span, "placeholder": subject[1]}

    def _workspace_edit(
        self, changes: dict[str, list[dict[str, Any]]], label: str
    ) -> dict[str, Any]:
        """The edits in the shape the client asked for.

        ``documentChanges`` names, for each file, the version of the text the edit was
        computed against, so a client that has typed since refuses the edit instead of
        applying it to a text it was not meant for. A document that is not open has no
        version, which the protocol spells ``null``. The plain ``changes`` form stays for a
        client that did not announce the other, because it is the only one it can apply.

        The one funnel both a rename and a quick fix pass through, which is why the client's
        spelling is put back here: an edit is applied to the document the uri names, and the
        one on screen is the one the client opened.

        An edit reaching two files or more is marked ``needsConfirmation`` for a client that
        announced both ``documentChanges`` and ``changeAnnotationSupport``, ``label`` naming it:
        a client applies an edit it is handed and saves every file it touched, unless it is
        marked, and then it shows the edit first, where the reader can leave a file out. Every
        text edit of it names the one annotation; any other client gets the edit unmarked,
        because an annotation is outside what it negotiated.
        """
        changes = {self._respell(uri): edits for uri, edits in changes.items()}
        if not self._versioned_edits:
            return {"changes": changes}
        annotated = self._annotated_edits and len(changes) > 1
        result: dict[str, Any] = {
            "documentChanges": [
                {
                    "textDocument": {"uri": uri, "version": self._version_of(uri_to_path(uri))},
                    "edits": [{**edit, "annotationId": _CONFIRM} for edit in edits]
                    if annotated
                    else edits,
                }
                for uri, edits in changes.items()
            ]
        }
        if annotated:
            result["changeAnnotations"] = {_CONFIRM: {"label": label, "needsConfirmation": True}}
        return result

    def _answer_rename(self, request_id: Any, message: dict[str, Any]) -> None:
        """Rewrite a name wherever a project the rename reaches writes it, or say why it cannot
        be.

        The projects reached are the document's, and then every project holding a file their
        edits rewrite, until none is new (:class:`~ddd.lsp.navigation.Reach`): a writer linked
        into two images is rewritten for both, so the reader of the image the document is not
        in is rewritten too. Every one of them is asked each refusal before anything is
        answered, and the refusal one of them gives names its image where the document is not
        in it (:meth:`_in_image`).

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing. A drifted buffer is refused
        along with the rest of the rename rather than skipped on its own: writing every other
        file and leaving that one alone is the half-renamed project the refusal exists to
        prevent, and it would happen silently, because the client asked for one rename, not a
        rename of everything except what it could not reach.

        A unit is renamed by :meth:`_unit_rename` instead: its rename is a plan that rewrites
        the vocabulary as well, and merges two spellings where a variable's would collide.

        Before any of that, a description the search could not read is named
        (:meth:`_unread_refusal`), and where no project is known only a local's rename goes on
        (:meth:`_alone_refusal`).
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        params = _field(message.get("params"), dict, "params")
        wanted = _field(params.get("newName"), str, "params.newName")
        subject = renameable_at(document, pointer)
        if subject is not None and subject[0] == "unit":
            planned = self._unit_rename(path, subject[1], wanted, cache)
        else:
            planned = self._name_rename(path, document, pointer, wanted, subject, cache)
        if isinstance(planned, str):
            write_message(self.writer, error(request_id, REQUEST_FAILED, planned))
            return
        # The edits rewrite the very files every answer above was read out of, so anything
        # kept from before them now describes the past.
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(planned, "Rename")))

    def _name_rename(
        self,
        path: Path,
        document: Document,
        pointer: str,
        wanted: str,
        subject: tuple[str, str] | None,
        cache: dict[Path, Document],
    ) -> dict[str, list[dict[str, Any]]] | str:
        """The edits of a rename of anything but a unit, by file uri, over every project it
        reaches, or why it is refused (:meth:`_answer_rename`): among the refusals each project is
        asked, a type it declares an external one, whose name is its header's
        (:func:`~ddd.lsp.navigation.named_by_a_header`)."""
        changes: dict[str, list[dict[str, Any]]] = {}
        made: dict[str, list[_Made]] = {}
        drifted: set[Path] = set()
        reach = self._reach(path)
        refused = self._unread_refusal(reach) or self._alone_refusal(path, reach, subject)
        if refused is not None:
            return refused
        kind, old = subject or ("variable", "")
        for loaded in reach:
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                return self._in_image(reach, loaded, unreadable)
            built = index(loaded.workspace)
            problem = named_by_a_header(built, kind, old) or rename_problem(built, wanted, kind)
            if problem is not None:
                return self._in_image(reach, loaded, problem)
            edited = rename_edits(built, document, pointer, wanted, cache)
            drifted.update(edited.drifted)
            # A name is written alike wherever every project reads one file alike, so two
            # projects' edits of it never differ - a unit's plans can (:meth:`_unit_rename`).
            clash = self._gather(changes, made, edited.changes, loaded)
            assert clash is None, clash
            reach.touch([*map(uri_to_path, edited.changes), *edited.drifted])
        refused = self._unread_refusal(reach) or self._unseen_refusal(reach)
        if refused is not None:
            return refused
        if drifted:
            return self._drifted(drifted, "moved a declaration")
        return self._empty_refusal(changes) or changes

    def _unit_rename(
        self, path: Path, old: str, new: str, cache: dict[Path, Document]
    ) -> dict[str, list[dict[str, Any]]] | str:
        """The edits respelling a unit everywhere each project the rename reaches states or lists
        it, by file uri, or why it is refused: Rename Symbol's, and the quick fix's that respells
        an unknown unit (:func:`~ddd.lsp.edits.actions_across`), which is the same rename.

        The projects reached are a variable's (:meth:`_answer_rename`): the document's, and
        every project holding a file their plans write, until none is new. A project whose
        buffer moved the unit is not planned, so the files it would write are not known and it
        leads to no other project; the rename is refused for that buffer whatever else it
        reaches.

        The plan is :func:`ddd.lsp.units.rename_unit`'s, the one ``ddd gui`` previews and
        applies for one project, so that for any one project an editor and the page merge two
        spellings alike; its refusal is answered as a variable's is. The plan refuses while a
        file of the project did not load, and only then: one that loaded with an error is in the
        index, and a unit its units file lists twice is renamed at both entries. A file that no
        longer holds the unit where the index found it - one changed on disk since it was read,
        an open document that differs having been refused first (:meth:`_unseen_refusal`) - is
        not planned in: the plan's pointers are the disk's, and made in that text they would
        respell whatever sits there now, so the rename is refused for it (:meth:`_drifted`). A
        text the engine cannot make the plan in refuses it too, once the plan is made, as it is
        rendered as text edits (:meth:`_rendered`).

        Two projects planning one place of a file they share differently refuse it, both named
        (:meth:`_two_ways`): two images sharing a units file, of which one lists the unit renamed
        onto and the other does not, take the entry out in one plan and respell it in the other.
        Sent as one, the plan reached second was dropped there, or the two overlapped.
        """
        changes: dict[str, list[dict[str, Any]]] = {}
        made: dict[str, list[_Made]] = {}
        drifted: set[Path] = set()
        listing: set[Path] = set()
        reach = self._reach(path)
        refused = self._unread_refusal(reach) or self._alone_refusal(path, reach, ("unit", old))
        if refused is not None:
            return refused
        for loaded in reach:
            built = index(loaded.workspace)
            moved = unit_drift(built, old, cache)
            if moved:
                drifted.update(moved)
                continue
            project = unit_project(loaded.path, loaded.unloaded, cache)
            try:
                plan = rename_unit(built, project, old, new, cache)
            except UnitRefusalError as unplanned:
                return self._in_image(reach, loaded, unplanned.message)
            if new in built.vocabulary:
                listing.add(loaded.path.resolve())
            edits, unmade = self._rendered(plan, cache)
            if unmade:
                drifted.update(unmade)
                continue
            clash = self._gather(changes, made, edits, loaded)
            if clash is not None:
                file, first = clash
                return self._two_ways(reach, file, (first, loaded), listing, old, new)
            reach.touch(map(uri_to_path, edits))
        refused = self._unread_refusal(reach) or self._unseen_refusal(reach)
        if refused is not None:
            return refused
        if drifted:
            return self._drifted(drifted, "moved or respelled a unit")
        return self._empty_refusal(changes) or changes

    @staticmethod
    def _rendered(
        plan: UnitPlan, cache: dict[Path, Document]
    ) -> tuple[dict[str, list[dict[str, Any]]], set[Path]]:
        """A unit's plan as text edits by file uri, made file by file, and the files whose text the
        edit engine cannot make it in.

        The plan's places held the unit as the parse reads them (:func:`~ddd.lsp.units.unit_drift`),
        and the engine cuts where the scan records them. A text spelling one of those pointers as
        a key - ``"units[2]"`` after the list - records that member there: a merge taking two
        entries of one units file out took the member with the first, across the list's end, and
        found nothing at the second. The loader takes no file holding such a key, so the text is
        not the one the project was read from - an open document that differs from its file, or a
        file changed on disk since it was read - and the rename is refused for it as for a text
        that moved what the index found. Raised, the engine's refusal answered Rename Symbol with
        an error, and the whole lightbulb with it, where a quick fix renaming a unit is this
        rename (:meth:`_renamed`).
        """
        edits: dict[str, list[dict[str, Any]]] = {}
        unmade: set[Path] = set()
        for planned in plan.edits:
            try:
                edits.update(text_edits(UnitPlan((planned,)), cache))
            except EditError:
                unmade.add(planned.path)
        return edits, unmade

    @staticmethod
    def _in_image(reach: Reach, loaded: Loaded, refusal: str) -> str:
        """One of a rename's projects' refusals, naming the image it comes from where that is not
        the reader's own: asked from image one, a name "already declared by this project" in
        image two sends the reader looking in the wrong one."""
        image = reach.image(loaded)
        if image is not None:
            refusal = f"in {image}, which this rename reaches too: {refusal}"
        return refusal

    @staticmethod
    def _two_ways(
        reach: Reach, file: str, both: tuple[Loaded, Loaded], listing: set[Path], old: str, new: str
    ) -> str:
        """Why a unit's rename is refused where two projects it reaches plan one place of a file
        differently, each named as a refusal names an image
        (:meth:`~ddd.lsp.navigation.Reach.described`).

        Two plans of a unit differ by the vocabulary alone: one of the two projects lists the unit
        renamed onto - in ``listing``, by description - and merges the old spelling into it, and
        the other respells the old one, at the entry of the units file the two share."""
        merging, respelling = sorted(both, key=lambda each: each.path.resolve() not in listing)
        return (
            f"{reach.described(merging)} lists '{new}' and {reach.described(respelling)} does not, "
            f"so this rename would rewrite {uri_to_path(file).name} two ways, merging '{old}' into "
            f"'{new}' for the one and respelling it for the other: list '{new}' in both or in "
            "neither, and rename again"
        )

    def _unread_refusal(self, reach: Reach) -> str | None:
        """Why a rename that meets a description it could not read is refused, or nothing where
        it met none.

        Asked before the first project is looked at, for the descriptions the search for the
        document's projects met, and again once the reach is complete, for those the closure met:
        a description a plugin stops may hold the file the rename rewrites, and the rename would
        then rewrite one image and leave the other naming what is gone. The component alone is
        what the search answers where its project cannot be read, so it is asked before
        :meth:`_alone_refusal`, which would blame the wrong thing.
        """
        if not reach.unread:
            return None
        description, reason = min(reach.unread.items())
        return (
            f"{reach.named(description)} could not be read, so this rename cannot tell what it "
            f"reaches: {reason}"
        )

    def _alone_refusal(
        self, path: Path, reach: Reach, subject: tuple[str, str] | None
    ) -> str | None:
        """Why a rename of anything but a local is refused while no project is known for the
        document, or nothing where it may go on.

        A component read on its own has no writer for its inputs and no reader for its outputs,
        and no type, constant, section, raster or unit but its own: a rename of any of them would
        rewrite that one file and leave every other file that spells the name holding it, saying
        nothing. A local is spelled where it is declared and nowhere else, so its rename is whole.
        """
        if subject is None or not is_alone(path, reach.projects, self._builds_now()):
            return None
        if subject[0] == "variable" and is_local(index(reach.projects[0].workspace), subject[1]):
            return None
        return (
            f"no project is known for {path.name}: only a local variable can be renamed without "
            "one, because a rename has to reach every file that spells the name - put a project "
            "file above it that includes it, or configure the build (ddd-build.json)"
        )

    def _unseen_refusal(self, reach: Reach) -> str | None:
        """Why a rename is refused while an open document of a project it reaches holds what its
        file on disk does not, or nothing where none does.

        A rename is planned from the disk, whatever the buffers hold: what a buffer added -
        a mention typed and not saved - is invisible to it, so it is left naming what the rest
        was renamed from, or it declares the name the rename is onto and the two merge. Asked
        once the reach is complete, since a project reached late holds documents too, and
        before the drift refusal, which a buffer that differs would otherwise reach first as
        a moved site and name no more than the sites it moved.
        """
        sources: set[Path] = set()
        for loaded in reach.projects:
            sources.update(loaded.workspace.read_paths)
        differing = {
            path
            for path, (text, _) in self._open.items()
            if path in sources and differs_from_disk(path, text)
        }
        if not differing:
            return None
        names = ", ".join(sorted(path.name for path in differing))
        verb, them = ("has", "it") if len(differing) == 1 else ("have", "them")
        return (
            f"{names} {verb} unsaved changes this rename would not see; save {them} and rename "
            "again"
        )

    @staticmethod
    def _empty_refusal(changes: dict[str, Any]) -> str | None:
        """Why a rename that rewrites nothing is refused, or nothing where it rewrites a file.

        An empty answer is applied by a client without a word, so the box closes on a rename
        that did nothing: the reader is told instead that no saved file spells the name.
        """
        if changes:
            return None
        return "nothing on disk spells that name, so this rename would change nothing"

    @staticmethod
    def _gather(
        changes: dict[str, list[dict[str, Any]]],
        made: dict[str, list[_Made]],
        found: dict[str, list[dict[str, Any]]],
        origin: Loaded,
    ) -> tuple[str, Loaded] | None:
        """Add one project's edits to a rename's, each place once; or, where one of them meets an
        edit another project made of that file and is not that edit, the file and the project
        that made the other.

        A component linked into two images is in two projects, and both of them mention the
        same characters. Sending that edit twice is not a duplicate an editor tolerates: it is
        two overlapping rewrites of one range. Nor is keeping one of two edits that differ at one
        place, which an edit was told apart from another by its start alone: of two images'
        plans that differ there, the one reached second was dropped where the two began at one
        character, and the two overlapped where they did not.

        ``made`` holds each file's edits gathered so far, by where they lie, with the project
        that made each: a client applies a file's edits all at once, so an edit meeting none of
        its neighbours there meets none of them.
        """
        for uri, edits in found.items():
            kept = made.setdefault(uri, [])
            for edit in edits:
                span = _span(edit)
                at = bisect.bisect_left(kept, span, key=lambda each: each.span)
                beside = kept[max(at - 1, 0) : at + 1]
                if any(each.span == span and each.text == edit["newText"] for each in beside):
                    continue
                meeting = next((each for each in beside if _meet(each.span, span)), None)
                if meeting is not None:
                    return uri, meeting.by
                kept.insert(at, _Made(span, edit["newText"], origin))
                changes.setdefault(uri, []).append(edit)
        return None

    @staticmethod
    def _drifted(drifted: set[Path], changed: str) -> str:
        """Why a rename is refused while a file no longer holds what the index found in it,
        naming every such file.

        Asked after the unsaved changes of an open document (:meth:`_unseen_refusal`), which a
        document that differs from its file would otherwise reach first as a moved site, so no
        file here has any: it changed on disk since the project was read, and is read again
        at the next open or save, or on the editor's report of the change.
        """
        names = ", ".join(sorted(path.name for path in drifted))
        verb = "has" if len(drifted) == 1 else "have"
        return (
            f"{names} {verb} changed on disk since the project was read, which {changed} this "
            "rename would touch; rename again once it has been read again"
        )

    def _actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """What can be offered for the key under the cursor.

        The range a client sends covers a selection rather than a point, so the start of it is
        what decides: an author asking for a fix has put the caret on the thing they mean.

        Asked of every project holding the document, each fix once, and of every project holding
        a file a fix writes there, until none is new (:func:`~ddd.lsp.edits.actions_across`):
        the closure a rename reaches by (:meth:`_holding`), and a unit's rename planned as Rename
        Symbol plans it (:meth:`_unit_rename`). Nothing is offered while a file of a project the
        fixes reach did not load (:meth:`_withheld`).
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message, "range"))
        params = _field(message.get("params"), dict, "params")
        reported = _reported(_field(params.get("context"), dict, "params.context"))
        # A unit is fixed from the project's units files, and telling which files those are
        # reads every file the description includes. A client asks for actions at every move
        # of the caret, so they are looked for only when it sent a finding about a unit.
        about_units = any(entry.get("code") in UNKNOWN_UNIT for entry in reported)
        reach = self._reach(path)
        if self._withheld(reach.projects):
            return []
        asked = {
            loaded.path.resolve(): Asked(
                loaded.path.resolve(),
                index(loaded.workspace),
                unit_project(loaded.path, loaded.unloaded, cache) if about_units else None,
            )
            for loaded in reach.projects
        }
        elsewhere = Elsewhere(
            partial(self._holding, reach, asked, set(reach.unread)),
            partial(self._renamed, path, cache),
        )
        offered = actions_across(
            list(asked.values()), path, document, pointer, cache, reported, elsewhere
        )
        if offered is None:
            return []
        for action in offered:
            action["edit"] = self._workspace_edit(action["edit"]["changes"], action["title"])
        return offered

    def _holding(
        self, reach: Reach, asked: dict[Path, Asked], unread: set[Path], files: set[Path]
    ) -> list[Asked] | None:
        """Every project of ``reach`` holding one of ``files``, those holding them that it reaches
        only now included, each indexed once; or ``None`` where one reached now may not be
        edited, which withholds every fix.

        A project reached now may not be edited where a file of it did not load, as a project
        holding the document may not (:meth:`_withheld`), or where the closure met a description
        it could not read, which may hold one of the files, as a rename is refused for it
        (:meth:`_unread_refusal`) - one the search for the document's own projects met is the
        search's, and stops none of its fixes, as ever.
        """
        before = len(reach.projects)
        reach.touch(files)
        if self._withheld(reach.projects[before:]) or not unread.issuperset(reach.unread):
            return None
        for loaded in reach.projects[before:]:
            key = loaded.path.resolve()
            asked[key] = Asked(key, index(loaded.workspace))
        return [
            asked[loaded.path.resolve()]
            for loaded in reach.projects
            if not files.isdisjoint(loaded.workspace.sources())
        ]

    def _renamed(
        self, path: Path, cache: dict[Path, Document], unit: str, new: str
    ) -> dict[str, list[dict[str, Any]]] | None:
        """``unit`` respelled ``new`` everywhere its rename from ``path`` reaches, as Rename
        Symbol respells it (:meth:`_unit_rename`), or ``None`` where that rename is refused."""
        planned = self._unit_rename(path, unit, new, cache)
        return None if isinstance(planned, str) else planned

    def _withheld(self, projects: Sequence[Loaded]) -> bool:
        """Whether the quick fixes are withheld because a file of one of these projects did not
        load, saying why in the log where that has not been said.

        Withheld rather than refused with an error: a client asks for them at every move of the
        caret, and shows an error answer as a failed request each time, naming no file, where the
        reason is the unread file's own finding. The log says it once for as long as it stands -
        again only once a refresh has read whole every project it was said for (:meth:`_mended`),
        and one is then found broken anew: said at every request it is the flood the error
        answers were, and said once a session it would hide the second break.
        """
        withheld = False
        for loaded in projects:
            reason = self._unreadable(loaded)
            if reason is None:
                continue
            withheld = True
            if not any(reason in told for told in self._told.values()):
                self._log(f"no quick fix is offered: {reason}")
            self._told.setdefault(loaded.path, set()).add(reason)
        return withheld

    def _initialise(self, params: dict[str, Any]) -> None:
        """Take the workspace folders from whichever of the two ways the client offers them, the
        shapes of edit it says it applies, and whether it takes a watcher while the session runs.

        Every field is read before any is kept, so a handshake refused for one of them leaves the
        session as it was: the folders of one were taken before its capabilities were refused,
        and the session stayed in them. The protocol lets a client send both ways of naming the
        folders as null and leave out any step of its capabilities, and requires ``rootUri`` and
        the capabilities themselves all the same: a handshake without the capabilities announces
        nothing, and one with neither way of naming folders names none (:func:`_field`).
        """
        folders = params.get("workspaceFolders")
        roots = _named_folders([] if folders is None else folders, "params.workspaceFolders")
        root = params.get("rootUri")
        if root is not None and _field(root, str, "params.rootUri"):
            # Read for its path whether or not it is the folder taken: a uri no file system takes
            # is refused beside named folders as it is alone.
            rooted = uri_to_path(root)
            roots = roots or [rooted]
        capabilities = _field(params.get("capabilities", {}), dict, "params.capabilities")
        named = "params.capabilities.workspace"
        workspace = _field(capabilities.get("workspace", {}), dict, named)
        editing = f"{named}.workspaceEdit"
        edit = _field(workspace.get("workspaceEdit", {}), dict, editing)
        versioned = _field(edit.get("documentChanges", False), bool, f"{editing}.documentChanges")
        annotated = "changeAnnotationSupport" in edit
        if annotated:
            _field(edit["changeAnnotationSupport"], dict, f"{editing}.changeAnnotationSupport")
        watching = f"{named}.didChangeWatchedFiles"
        watched = _field(workspace.get("didChangeWatchedFiles", {}), dict, watching)
        registers = _field(
            watched.get("dynamicRegistration", False), bool, f"{watching}.dynamicRegistration"
        )
        self._folders = roots
        self._versioned_edits = versioned
        self._annotated_edits = annotated
        self._registers = registers

    def _capabilities(self) -> dict[str, Any]:
        return {
            # change 1 is TextDocumentSyncKind.Full: the analysis reads from disk on open and
            # save, but positions and edits are computed against the buffer, so the server
            # has to be told what the buffer holds. Full rather than incremental because a
            # description file is small and applying deltas is a second place to be wrong.
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 1, "save": True},
                "definitionProvider": True,
                "referencesProvider": True,
                "hoverProvider": True,
                "renameProvider": {"prepareProvider": True},
                "codeActionProvider": {"codeActionKinds": [QUICK_FIX]},
                # Without it a client sends no change of its folders, and a document of a folder
                # added after the start was checked as one outside every folder
                # (:meth:`_folders_changed`).
                "workspace": {"workspaceFolders": {"supported": True, "changeNotifications": True}},
            },
            "serverInfo": {"name": "ddd", "version": __version__},
        }

    def _publish(self, path: Path, findings: list[dict[str, Any]]) -> None:
        """Send one file's findings, under the spelling the client knows it by, and note what is on
        screen for it (:attr:`_published`).

        Where what is on screen went out under another spelling - the resolved one, before the
        client opened the file through a junction or a link - it is withdrawn there first: a
        client keys what it draws on the uri string, so the old set stayed on screen beside the
        new one, and stayed there once the file was fixed, under a uri nothing published again.
        """
        uri = self._uri(path)
        shown = self._published.pop(path, None)
        if shown is not None and shown != uri:
            self._diagnostics(shown, [])
        for finding in findings:
            for related in finding.get("relatedInformation", ()):
                # The other side of a conflict is somewhere the reader clicks, so it needs the
                # client's spelling as much as the finding itself does.
                related["location"]["uri"] = self._respell(related["location"]["uri"])
        self._diagnostics(uri, findings)
        if findings:
            self._published[path] = uri

    def _diagnostics(self, uri: str, findings: list[dict[str, Any]]) -> None:
        write_message(
            self.writer,
            notification("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": findings}),
        )


def serve(build_directories: Sequence[Path] = ()) -> int:
    """Run a server on this process's stdin and stdout.

    The binary buffers, because the protocol counts bytes; and stdout is the wire, which is
    why nothing in DDD prints there except through :func:`write_message`. A plugin, or a
    library it imports, is under no such discipline, so the wire is taken before anything
    else can write to it and ``sys.stdout`` points at stderr for the rest of the process.

    Stdin is read through a reader of the server's own over its descriptor, never through
    ``sys.stdin.buffer``. The reading thread is still waiting for a frame when the run ends
    (:meth:`Server.run`), and on its way out the interpreter closes ``sys.stdin``, which waits
    for the lock that read holds and then aborts the process, after an ``exit`` the client
    sent while it kept the pipe open. A reader nothing closes is left to the end of the
    process instead. A stdin that is no descriptor is read as it is.
    """
    wire = sys.stdout.buffer
    stdin = sys.stdin.buffer
    try:
        reader: IO[bytes] = open(stdin.fileno(), "rb", closefd=False)  # noqa: SIM115 - never closed
    except io.UnsupportedOperation:
        reader = stdin
    with contextlib.redirect_stdout(sys.stderr):
        return Server(reader, wire, build_directories=build_directories).run()
