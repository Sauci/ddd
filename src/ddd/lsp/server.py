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

Only ``didOpen`` and ``didSave`` refresh. Nothing is analysed per keystroke: the analysis
reads the files from disk, so the editor and the server agree exactly at the moment of a
save, and a half-typed document never produces a screenful of findings about a mistake
nobody has finished making yet. The *text* of every open document is nonetheless kept, and
kept current through ``didChange``: a position the client sends, and an edit the client
will apply, are about what is on screen, and an edit computed from a stale file and applied
to a buffer with one extra line rewrote an unrelated line.
"""

from __future__ import annotations

import contextlib
import re
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Final
from urllib.parse import urlparse
from urllib.request import url2pathname

from ddd import __version__
from ddd.build_info import BuildInfo
from ddd.lsp.diagnostics import collect
from ddd.lsp.discovery import build_files, load_builds
from ddd.lsp.edits import QUICK_FIX, UNKNOWN_UNIT, actions
from ddd.lsp.hover import describe, describe_constant, describe_external, describe_type, resolve
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
    response,
    write_message,
)
from ddd.lsp.ranges import Document, differs_from_disk, read
from ddd.lsp.units import UnitRefusalError, rename_unit, text_edits, unit_drift, unit_project

_DID_OPEN: Final = "textDocument/didOpen"
_DID_CHANGE: Final = "textDocument/didChange"
_DID_CLOSE: Final = "textDocument/didClose"
_DID_SAVE: Final = "textDocument/didSave"
"""A save is the moment the text on disk is known to be the text on screen."""

_DID_CHANGE_WATCHED: Final = "workspace/didChangeWatchedFiles"
"""A description changed on disk without passing through the editor.

The other half of "the findings are the disk's": a build writes description files, a branch
switch rewrites all of them, and neither is a document event. The extension registers the
watcher and says exactly this in its own comment; the notification simply had nowhere to land.
"""

_DEFINITION: Final = "textDocument/definition"
_NAVIGATING: Final = frozenset({_DEFINITION, "textDocument/references"})
_HOVER: Final = "textDocument/hover"
_PREPARE_RENAME: Final = "textDocument/prepareRename"
_RENAME: Final = "textDocument/rename"
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
    return Path(path)


def _field[T](value: Any, wanted: type[T], named: str) -> T:
    """One field of the client's message, or a refusal that names what was wrong with it.

    Every field a handler reads goes through here rather than being indexed, because these
    are somebody else's bytes and not this server's invariant. A field that is wrong is the
    client's mistake rather than a defect of the server, and is answered as one: refused with
    the invalid-parameters error naming it, and nothing written to stderr, where the net the
    module docstring describes writes the trace of a defect. Indexed instead, a frame without
    the ``params`` every editor sends would reach that net as the server's own defect, with no
    field named.
    """
    if not isinstance(value, wanted):
        msg = f"'{named}' is missing or is not {wanted.__name__}"
        raise MessageError(INVALID_PARAMS, msg)
    return value


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
        self.roots: list[Path] = [root or Path.cwd()]
        """The workspace folders, first one first; a multi-root workspace has several."""
        self.build_directories = list(build_directories)
        self._published: set[Path] = set()
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

        self._open: dict[Path, tuple[str, int | None]] = {}
        """The text and version of every open document, keyed by its resolved path.

        What positions and edits are computed against. The analysis still reads the disk - a
        finding is about what is saved - but a rename box opens where the caret is, and the
        edit that follows is applied to the buffer, so both have to be read from it.
        """

        self._versioned_edits = False
        """Whether the client takes ``documentChanges``, which carry the version an edit is for."""

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

    def run(self) -> int:
        """Serve until the client says to stop, or stops talking.

        One bad frame is not the end of the conversation: a body that is not a request gets
        the json-rpc refusal it defines a code for, and the loop reads on, as it does past a
        message the server failed to answer (:meth:`_defect`). Only broken framing ends the
        run, because after it nothing on the stream can be trusted - and that is said once on
        stderr, where the log goes, never on stdout, which is the wire.
        """
        while True:
            try:
                message = read_message(self.reader)
            except MessageError as fault:
                write_message(self.writer, error(None, fault.code, str(fault)))
                continue
            except ProtocolError as fault:
                print(f"ddd: {fault}", file=sys.stderr)
                return 1
            if message is None:
                return 0
            try:
                keep_going = self._handle(message)
            except MessageError as fault:
                # The frame was read and the method understood; what the client sent with it
                # was not the shape the method takes. A request gets that as its answer and a
                # notification gets nothing, which is what a notification always gets - a
                # message with no ``id`` is a notification, and answering one with an error
                # under ``"id": null`` is a line in the client's output channel that names no
                # request the reader can go and look at. Either way the next message is still
                # read.
                if "id" in message:
                    write_message(self.writer, error(message["id"], fault.code, str(fault)))
                continue
            except Exception as fault:
                # Anything else is a defect of this server's own in answering this one message,
                # which costs that answer and not the session (the module docstring).
                self._defect(message, fault)
                continue
            if not keep_going:
                # An exit that was prepared for is a clean end and anything else is not, which
                # is the one thing an exit code can tell a client that is watching the process.
                return 0 if self._shutting_down else 1

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
        """Act on one message; ``False`` means the client asked the server to exit."""
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
            self._initialise(message.get("params") or {})
            self._initialised = True
            write_message(self.writer, response(request_id, self._capabilities()))
        elif method == "shutdown":
            self._shutting_down = True
            write_message(self.writer, response(request_id, None))
        elif method == _DID_OPEN:
            self._remember(message)
            self.refresh(self._opened(message))
        elif method == _DID_CHANGE:
            self._remember(message)
        elif method == _DID_CLOSE:
            self._open.pop(self._document(message).resolve(), None)
        elif method == _DID_SAVE:
            self.refresh(self._document(message))
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
        """Check again, because what was read from disk is no longer what is on it.

        Every open document, rather than the files that changed: a document is published
        through the project above it, so a change in a file nobody has open is precisely the
        case that moves a finding onto one somebody does. With nothing open there is still a
        Problems list on screen describing the project as it was, and the changed files are
        the only roots there are to check it from.
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
        for document in sorted(self._open) or [path for path in touched if path.exists()]:
            self.refresh(document)
        self._withdraw_deleted()

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
        """The position a request is about, which a code action sends as the start of a range."""
        params = _field(message.get("params"), dict, "params")
        where = _field(params.get(key), dict, f"params.{key}")
        if key == "range":
            where = _field(where.get("start"), dict, "params.range.start")
        for axis in ("line", "character"):
            _field(where.get(axis), int, f"params.{key}.{axis}")
        return where

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
            for root in self.roots:
                for record in build_files(root, self.build_directories):
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
                descriptions = Descriptions()
            projects = workspaces(
                self._builds_now(), document, self._root_for(document), descriptions
            )
            found = self._projects[document] = (projects, dict(descriptions.failed))
        return found

    def _reach(self, document: Path) -> Reach:
        """Every project a rename started from ``document`` reaches, each description read at
        most once for it."""
        descriptions = Descriptions()
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

        Called wherever the files may no longer be what they were: at every refresh, which is
        a save or an open, and after a rename, which rewrites them from here.
        """
        self._builds = None
        self._projects.clear()

    def refresh(self, document: Path) -> None:
        """Re-run the checks and publish what they say about every file involved.

        Every configured build is run, not only the one that claims this document. A component
        linked into two images is in two projects and they need not agree, and the answer to
        which one the reader cares about is "both": whichever is broken is broken.
        """
        self._forget()
        builds = self._builds_now()
        self._announce(builds)
        # A record naming a project that is not there is dropped rather than analysed. Running
        # it produces one finding, "file does not exist", published against a file nobody can
        # open - and the thing actually wrong is the record, which the log has just said.
        reports = collect(
            [info for info in builds if Path(info.project).is_file()],
            [document],
            self._root_for(document),
        )
        # Only files with something to say, plus the ones this run reported on that had
        # something to say last time and no longer do - those need an empty list to withdraw
        # what is on screen. A file this run never reported on keeps what it has: with no record
        # covering it, a run looks at the document and the project above it, and says nothing
        # of another project, which is not the same as saying it is fine.
        current = {path for path, findings in reports.items() if findings}
        for path in sorted(current | (self._published & set(reports))):
            self._publish(path, reports.get(path, []))
        self._published = (self._published - set(reports)) | current
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
            self._published.discard(path)

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
        if described is None and (constant is not None or name is not None):
            dictionary = resolve(projects)
            if dictionary is not None:
                if constant is not None:
                    described = describe_constant(dictionary, constant)
                if described is None and name is not None:
                    described = describe(dictionary, name)
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

    def _workspace_edit(self, changes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        """The edits in the shape the client asked for.

        ``documentChanges`` names, for each file, the version of the text the edit was
        computed against, so a client that has typed since refuses the edit instead of
        applying it to a text it was not meant for. A document that is not open has no
        version, which the protocol spells ``null``. The plain ``changes`` form stays for a
        client that did not announce the other, because it is the only one it can apply.

        The one funnel both a rename and a quick fix pass through, which is why the client's
        spelling is put back here: an edit is applied to the document the uri names, and the
        one on screen is the one the client opened.
        """
        changes = {self._respell(uri): edits for uri, edits in changes.items()}
        if not self._versioned_edits:
            return {"changes": changes}
        return {
            "documentChanges": [
                {
                    "textDocument": {"uri": uri, "version": self._version_of(uri_to_path(uri))},
                    "edits": edits,
                }
                for uri, edits in changes.items()
            ]
        }

    def _answer_rename(self, request_id: Any, message: dict[str, Any]) -> None:
        """Rewrite a name wherever a project the rename reaches writes it, or say why it cannot
        be.

        The projects reached are the document's, and then every project holding a file their
        edits rewrite, until none is new (:class:`~ddd.lsp.navigation.Reach`): a writer linked
        into two images is rewritten for both, so the reader of the image the document is not
        in is rewritten too. Every one of them is asked each refusal before anything is
        answered, and the refusal one of them gives names its image where the document is not
        in it (:meth:`_refuse`).

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing. A drifted buffer is refused
        along with the rest of the rename rather than skipped on its own: writing every other
        file and leaving that one alone is the half-renamed project the refusal exists to
        prevent, and it would happen silently, because the client asked for one rename, not a
        rename of everything except what it could not reach.

        A unit is renamed by :meth:`_rename_unit` instead: its rename is a plan that rewrites
        the vocabulary as well, and merges two spellings where a variable's would collide.

        Before any of that, a description the search could not read is named
        (:meth:`_refused_unread`), and where no project is known only a local's rename goes on
        (:meth:`_refused_alone`).
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        params = _field(message.get("params"), dict, "params")
        wanted = _field(params.get("newName"), str, "params.newName")
        subject = renameable_at(document, pointer)
        if subject is not None and subject[0] == "unit":
            self._rename_unit(request_id, path, subject[1], wanted, cache)
            return
        changes: dict[str, list[dict[str, Any]]] = {}
        seen: set[tuple[str, int, int]] = set()
        drifted: set[Path] = set()
        reach = self._reach(path)
        if self._refused_unread(request_id, reach) or self._refused_alone(
            request_id, path, reach, subject
        ):
            return
        for loaded in reach:
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                self._refuse(request_id, reach, loaded, unreadable)
                return
            built = index(loaded.workspace)
            refused = rename_problem(built, wanted, subject[0] if subject else "variable")
            if refused is not None:
                self._refuse(request_id, reach, loaded, refused)
                return
            edited = rename_edits(built, document, pointer, wanted, cache)
            drifted.update(edited.drifted)
            self._gather(changes, seen, edited.changes)
            reach.touch([*map(uri_to_path, edited.changes), *edited.drifted])
        if self._refused_unread(request_id, reach) or self._refused_unseen(request_id, reach):
            return
        if drifted:
            refusal = self._drifted(drifted, "moved a declaration")
            write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
            return
        if self._refused_empty(request_id, changes):
            return
        # The edits rewrite the very files every answer above was read out of, so anything
        # kept from before them now describes the past.
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(changes)))

    def _rename_unit(
        self, request_id: Any, path: Path, old: str, new: str, cache: dict[Path, Document]
    ) -> None:
        """Respell a unit everywhere each project the rename reaches states or lists it, or say
        why it cannot be.

        The projects reached are a variable's (:meth:`_answer_rename`): the document's, and
        every project holding a file their plans write, until none is new. A project whose
        buffer moved the unit is not planned, so the files it would write are not known and it
        leads to no other project; the rename is refused for that buffer whatever else it
        reaches.

        The plan is :func:`ddd.lsp.units.rename_unit`'s, the one ``ddd gui`` previews and
        applies, so an editor and the page cannot disagree about what a rename reaches or when
        it merges two spellings; its refusal is answered as a variable's is. The plan refuses
        while a file of the project did not load, and only then: one that loaded with an error
        is in the index, and a unit its units file lists twice is renamed at both entries. A
        buffer that no longer holds the unit where the index found it refuses the rename before
        the plan is made: the plan's pointers are the disk's, and made in that buffer they would
        respell whatever sits there now.
        """
        changes: dict[str, list[dict[str, Any]]] = {}
        seen: set[tuple[str, int, int]] = set()
        drifted: set[Path] = set()
        reach = self._reach(path)
        if self._refused_unread(request_id, reach) or self._refused_alone(
            request_id, path, reach, ("unit", old)
        ):
            return
        for loaded in reach:
            built = index(loaded.workspace)
            moved = unit_drift(built, old, cache)
            if moved:
                drifted.update(moved)
                continue
            project = unit_project(loaded.path, loaded.unloaded, cache)
            try:
                plan = rename_unit(built, project, old, new, cache)
            except UnitRefusalError as refused:
                self._refuse(request_id, reach, loaded, refused.message)
                return
            edits = text_edits(plan, cache)
            self._gather(changes, seen, edits)
            reach.touch(map(uri_to_path, edits))
        if self._refused_unread(request_id, reach) or self._refused_unseen(request_id, reach):
            return
        if drifted:
            refusal = self._drifted(drifted, "moved or respelled a unit")
            write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
            return
        if self._refused_empty(request_id, changes):
            return
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(changes)))

    def _refuse(self, request_id: Any, reach: Reach, loaded: Loaded, refusal: str) -> None:
        """Answer a rename with one of its projects' refusals, naming the image it comes from
        where that is not the reader's own: asked from image one, a name "already declared by
        this project" in image two sends the reader looking in the wrong one."""
        image = reach.image(loaded)
        if image is not None:
            refusal = f"in {image}, which this rename reaches too: {refusal}"
        write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))

    def _refused_unread(self, request_id: Any, reach: Reach) -> bool:
        """Refuse a rename that meets a description it could not read, and say whether it did.

        Asked before the first project is looked at, for the descriptions the search for the
        document's projects met, and again once the reach is complete, for those the closure met:
        a description a plugin stops may hold the file the rename rewrites, and the rename would
        then rewrite one image and leave the other naming what is gone. The component alone is
        what the search answers where its project cannot be read, so it is asked before
        :meth:`_refused_alone`, which would blame the wrong thing.
        """
        if not reach.unread:
            return False
        description, reason = min(reach.unread.items())
        refusal = (
            f"{reach.named(description)} could not be read, so this rename cannot tell what it "
            f"reaches: {reason}"
        )
        write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
        return True

    def _refused_alone(
        self, request_id: Any, path: Path, reach: Reach, subject: tuple[str, str] | None
    ) -> bool:
        """Refuse a rename of anything but a local while no project is known for the document,
        and say whether it did.

        A component read on its own has no writer for its inputs and no reader for its outputs,
        and no type, constant, section, raster or unit but its own: a rename of any of them would
        rewrite that one file and leave every other file that spells the name holding it, saying
        nothing. A local is spelled where it is declared and nowhere else, so its rename is whole.
        """
        if subject is None or not is_alone(path, reach.projects, self._builds_now()):
            return False
        if subject[0] == "variable" and is_local(index(reach.projects[0].workspace), subject[1]):
            return False
        refusal = (
            f"no project is known for {path.name}: only a local variable can be renamed without "
            "one, because a rename has to reach every file that spells the name - put a project "
            "file above it that includes it, or configure the build (ddd-build.json)"
        )
        write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
        return True

    def _refused_unseen(self, request_id: Any, reach: Reach) -> bool:
        """Refuse a rename while an open document of a project it reaches holds
        what its file on disk does not, and say whether it did.

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
            return False
        names = ", ".join(sorted(path.name for path in differing))
        verb, them = ("has", "it") if len(differing) == 1 else ("have", "them")
        refusal = (
            f"{names} {verb} unsaved changes this rename would not see; save {them} and rename "
            "again"
        )
        write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
        return True

    def _refused_empty(self, request_id: Any, changes: dict[str, Any]) -> bool:
        """Refuse a rename that rewrites nothing, and say whether it did.

        An empty answer is applied by a client without a word, so the box closes on a rename
        that did nothing: the reader is told instead that no saved file spells the name.
        """
        if changes:
            return False
        refusal = "nothing on disk spells that name, so this rename would change nothing"
        write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
        return True

    @staticmethod
    def _gather(
        changes: dict[str, list[dict[str, Any]]],
        seen: set[tuple[str, int, int]],
        found: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Add one project's edits to a rename's, each place once.

        A component linked into two images is in two projects, and both of them mention the
        same characters. Sending that edit twice is not a duplicate an editor tolerates: it is
        two overlapping rewrites of one range.
        """
        for uri, edits in found.items():
            for edit in edits:
                start = edit["range"]["start"]
                where = (uri, start["line"], start["character"])
                if where not in seen:
                    seen.add(where)
                    changes.setdefault(uri, []).append(edit)

    @staticmethod
    def _drifted(drifted: set[Path], changed: str) -> str:
        """Why a rename is refused while a buffer no longer holds what the index found in it,
        naming every such file."""
        names = ", ".join(sorted(path.name for path in drifted))
        verb = "has" if len(drifted) == 1 else "have"
        return (
            f"{names} {verb} unsaved changes that {changed} this rename would touch; save it "
            "and rename again"
        )

    def _actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """What can be offered for the key under the cursor.

        The range a client sends covers a selection rather than a point, so the start of it is
        what decides: an author asking for a fix has put the caret on the thing they mean.
        Nothing is offered while a file of the document's projects did not load
        (:meth:`_withheld`).
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message, "range"))
        params = _field(message.get("params"), dict, "params")
        context = _field(params.get("context"), dict, "params.context")
        reported = context.get("diagnostics", [])
        # A unit is fixed from the project's units files, and telling which files those are
        # reads every file the description includes. A client asks for actions at every move
        # of the caret, so they are looked for only when it sent a finding about a unit.
        about_units = any(entry.get("code") in UNKNOWN_UNIT for entry in reported)
        offered: list[dict[str, Any]] = []
        projects = self._projects_of(path)
        if self._withheld(projects):
            return offered
        for loaded in projects:
            project = unit_project(loaded.path, loaded.unloaded, cache) if about_units else None
            offered.extend(
                actions(index(loaded.workspace), path, document, pointer, cache, reported, project)
            )
        for action in offered:
            action["edit"] = self._workspace_edit(action["edit"]["changes"])
        return offered

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
        """Take the workspace folders from whichever of the two ways the client offers them."""
        folders = params.get("workspaceFolders") or []
        if folders:
            self.roots = [
                uri_to_path(
                    _field(
                        _field(folder, dict, "params.workspaceFolders[]").get("uri"),
                        str,
                        "params.workspaceFolders[].uri",
                    )
                )
                for folder in folders
            ]
        elif params.get("rootUri"):
            self.roots = [uri_to_path(params["rootUri"])]
        capabilities = params.get("capabilities")
        workspace = capabilities.get("workspace") if isinstance(capabilities, dict) else None
        edit = workspace.get("workspaceEdit") if isinstance(workspace, dict) else None
        self._versioned_edits = isinstance(edit, dict) and edit.get("documentChanges") is True

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
            },
            "serverInfo": {"name": "ddd", "version": __version__},
        }

    def _publish(self, path: Path, findings: list[dict[str, Any]]) -> None:
        for finding in findings:
            for related in finding.get("relatedInformation", ()):
                # The other side of a conflict is somewhere the reader clicks, so it needs the
                # client's spelling as much as the finding itself does.
                related["location"]["uri"] = self._respell(related["location"]["uri"])
        write_message(
            self.writer,
            notification(
                "textDocument/publishDiagnostics",
                {"uri": self._uri(path), "diagnostics": findings},
            ),
        )


def serve(build_directories: Sequence[Path] = ()) -> int:
    """Run a server on this process's stdin and stdout.

    The binary buffers, because the protocol counts bytes; and stdout is the wire, which is
    why nothing in DDD prints there except through :func:`write_message`. A plugin, or a
    library it imports, is under no such discipline, so the wire is taken before anything
    else can write to it and ``sys.stdout`` points at stderr for the rest of the process.
    """
    wire = sys.stdout.buffer
    with contextlib.redirect_stdout(sys.stderr):
        return Server(sys.stdin.buffer, wire, build_directories=build_directories).run()
