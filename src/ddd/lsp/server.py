"""The language server itself: a loop, six messages, and no opinions of its own.

Everything that decides anything lives in :mod:`ddd.lsp.diagnostics` and
:mod:`ddd.lsp.discovery`; what is left here is translation. That split is deliberate, because
this is the layer a test can only reach through a protocol: keeping it thin keeps the thinking
somewhere that can be tested directly.

There is no net around the analysis, and that is not an oversight. The front end reports
through a diagnostic bag rather than raising - the developer documentation states it as a
rule - so a project that cannot be read, or whose plugin raises out of a hook, produces
findings, not an exception. A server that wrapped it in a catch-all would be insuring against
a thing the design already prevents, and would hide it if that ever stopped being true.

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
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Final
from urllib.parse import urlparse
from urllib.request import url2pathname

from ddd import __version__
from ddd.build_info import BuildInfo
from ddd.lsp.diagnostics import collect
from ddd.lsp.discovery import discover
from ddd.lsp.edits import QUICK_FIX, actions
from ddd.lsp.hover import describe, describe_constant, describe_external, describe_type, resolve
from ddd.lsp.navigation import (
    Loaded,
    Site,
    constant_at,
    definition,
    index,
    locations,
    references,
    rename_edits,
    rename_problem,
    renameable_at,
    subject_at,
    type_at,
    workspaces,
)
from ddd.lsp.protocol import (
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
from ddd.lsp.ranges import Document, read

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
    are somebody else's bytes and not this server's invariant. The analysis stays unguarded
    on purpose - the module docstring says why - but a frame that arrives without the
    ``params`` every editor sends is not a defect in the checks, and taking the conversation
    down over one costs the reader every DDD finding on screen until they restart the server.
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

        self._builds: list[BuildInfo] | None = None
        """The build records, found once and kept until the next refresh.

        Finding them means walking every configured build directory looking for the record,
        and a build directory holds tens of thousands of object files. Doing that per hover -
        which is what asking :func:`discover` in each handler amounted to - put a directory
        walk behind a gesture that is supposed to feel like a tooltip.
        """

        self._projects: dict[Path, list[Loaded]] = {}
        """The projects containing each document, loaded once and kept until the next refresh.

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
        the json-rpc refusal it defines a code for, and the loop reads on. Only broken
        framing ends the run, because after it nothing on the stream can be trusted - and
        that is said once on stderr, where the log goes, never on stdout, which is the wire.
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
            if not keep_going:
                # An exit that was prepared for is a clean end and anything else is not, which
                # is the one thing an exit code can tell a client that is watching the process.
                return 0 if self._shutting_down else 1

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
        """The uri to answer under for a file: the client's own, where it gave one."""
        return self._spelled.get(path.resolve(), path.as_uri())

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
        for document in sorted(self._open) or touched:
            self.refresh(document)

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
        """The build records, found once per refresh rather than once per keypress."""
        if self._builds is None:
            self._refused = {}
            self._builds = [
                info
                for root in self.roots
                for info in discover(root, self.build_directories, self._refused)
            ]
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

    def _projects_of(self, document: Path) -> list[Loaded]:
        """The projects containing a document, loaded once per refresh."""
        found = self._projects.get(document)
        if found is None:
            found = workspaces(self._builds_now(), document, self._root_for(document))
            self._projects[document] = found
        return found

    @staticmethod
    def _unreadable(loaded: Loaded) -> str | None:
        """Why this project may not be edited yet, or nothing when it may.

        A project is indexed from what loaded, so a file a ``schema`` error dropped mid edit
        declares nothing as far as the index knows: a rename then rewrites every other file
        and leaves that one holding the old name, and a quick fix offers to remove a key "no
        other declaration has" while the unloaded producer has exactly that key. Refused whole
        rather than performed in part, which is the answer a drifted buffer already gets.
        """
        if not loaded.unreadable:
            return None
        names = ", ".join(sorted(path.name for path in loaded.unreadable))
        verb = "has" if len(loaded.unreadable) == 1 else "have"
        return (
            f"{names} {verb} an error that stopped the project reading it, so the rest of the "
            "project cannot be edited around it; fix it and try again"
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
        # Only files with something to say, plus the ones that had something to say last time
        # and no longer do - those need an empty list to withdraw what is on screen.
        current = {path for path, findings in reports.items() if findings}
        for path in sorted(current | self._published):
            self._publish(path, reports.get(path, []))
        self._published = current

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
        """Rewrite a name everywhere the project writes it, or say why it cannot be.

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing. A drifted buffer is refused
        along with the rest of the rename rather than skipped on its own: writing every other
        file and leaving that one alone is the half-renamed project the refusal exists to
        prevent, and it would happen silently, because the client asked for one rename, not a
        rename of everything except what it could not reach.
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        params = _field(message.get("params"), dict, "params")
        wanted = _field(params.get("newName"), str, "params.newName")
        changes: dict[str, list[dict[str, Any]]] = {}
        # A component linked into two images is in two projects, and both of them mention the
        # same characters. Sending that edit twice is not a duplicate an editor tolerates: it
        # is two overlapping rewrites of one range.
        seen: set[tuple[str, int, int]] = set()
        drifted: set[Path] = set()
        subject = renameable_at(document, pointer)
        for loaded in self._projects_of(path):
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                write_message(self.writer, error(request_id, REQUEST_FAILED, unreadable))
                return
            built = index(loaded.workspace)
            refused = rename_problem(built, wanted, subject[0] if subject else "variable")
            if refused is not None:
                write_message(self.writer, error(request_id, REQUEST_FAILED, refused))
                return
            edited = rename_edits(built, document, pointer, wanted, cache)
            drifted.update(edited.drifted)
            for uri, edits in edited.changes.items():
                for edit in edits:
                    start = edit["range"]["start"]
                    where = (uri, start["line"], start["character"])
                    if where not in seen:
                        seen.add(where)
                        changes.setdefault(uri, []).append(edit)
        if drifted:
            names = ", ".join(sorted(p.name for p in drifted))
            verb = "has" if len(drifted) == 1 else "have"
            msg = (
                f"{names} {verb} unsaved changes that moved a declaration this rename would "
                "touch; save it and rename again"
            )
            write_message(self.writer, error(request_id, REQUEST_FAILED, msg))
            return
        # The edits rewrite the very files every answer above was read out of, so anything
        # kept from before them now describes the past.
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(changes)))

    def _actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """What can be offered for the key under the cursor.

        The range a client sends covers a selection rather than a point, so the start of it is
        what decides: an author asking for a fix has put the caret on the thing they mean.
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message, "range"))
        params = _field(message.get("params"), dict, "params")
        context = _field(params.get("context"), dict, "params.context")
        reported = context.get("diagnostics", [])
        offered: list[dict[str, Any]] = []
        for loaded in self._projects_of(path):
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                raise MessageError(REQUEST_FAILED, unreadable)
            offered.extend(
                actions(index(loaded.workspace), path, document, pointer, cache, reported)
            )
        for action in offered:
            action["edit"] = self._workspace_edit(action["edit"]["changes"])
        return offered

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
