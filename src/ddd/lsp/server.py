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

Only ``didOpen`` and ``didSave`` refresh. Nothing is analysed per keystroke: the files are
read from disk, so the editor and the server agree exactly at the moment of a save, and a
half-typed document never produces a screenful of findings about a mistake nobody has finished
making yet.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Final
from urllib.parse import urlparse
from urllib.request import url2pathname

from ddd import __version__
from ddd.build_info import BuildInfo
from ddd.loading import Workspace
from ddd.lsp.diagnostics import collect
from ddd.lsp.discovery import discover
from ddd.lsp.edits import QUICK_FIX, actions
from ddd.lsp.hover import describe, describe_constant, describe_external, resolve
from ddd.lsp.navigation import (
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
    METHOD_NOT_FOUND,
    REQUEST_FAILED,
    MessageError,
    ProtocolError,
    error,
    notification,
    read_message,
    response,
    write_message,
)
from ddd.lsp.ranges import Document, read

_REFRESHING: Final = frozenset({"textDocument/didOpen", "textDocument/didSave"})
"""The two moments the text on disk is known to be the text on screen."""

_DEFINITION: Final = "textDocument/definition"
_NAVIGATING: Final = frozenset({_DEFINITION, "textDocument/references"})
_HOVER: Final = "textDocument/hover"
_PREPARE_RENAME: Final = "textDocument/prepareRename"
_RENAME: Final = "textDocument/rename"
_CODE_ACTION: Final = "textDocument/codeAction"


def uri_to_path(uri: str) -> Path:
    """The file a ``file://`` uri names, undoing the escaping a client applies to it.

    ``url2pathname`` unescapes on its way, so nothing may unescape before it: doing both
    decoded a percent sequence twice and named a different file, which made this the inverse
    of ``Path.as_uri()`` for every path except the ones that actually needed escaping. A
    document called ``a%20b.ddd.json`` came back as ``a b.ddd.json``, and the diagnostics
    published for it went out under a uri the client could match to nothing on screen.
    """
    parsed = urlparse(uri)
    path = url2pathname(parsed.path)
    if parsed.netloc and parsed.netloc != "localhost":
        # file://server/share/...: a network share, whose host is the start of the path.
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
        self._announced: tuple[tuple[str, str], ...] | None = None
        """What was last said about the configured projects, so it is not said every save."""

        self._builds: list[BuildInfo] | None = None
        """The build records, found once and kept until the next refresh.

        Finding them means walking every configured build directory looking for the record,
        and a build directory holds tens of thousands of object files. Doing that per hover -
        which is what asking :func:`discover` in each handler amounted to - put a directory
        walk behind a gesture that is supposed to feel like a tooltip.
        """

        self._projects: dict[Path, list[Workspace]] = {}
        """The projects containing each document, loaded once and kept until the next refresh.

        The same reasoning one level up: answering a hover used to read and validate every
        description file of every image the component is linked into, twice over - the
        external type lookup and the resolution each walked the projects from scratch.

        Keeping them is sound precisely because of what this server already promises: it reads
        from disk at open and at save and nowhere else, which is what its ``textDocumentSync``
        tells the client. Between two saves the answer cannot have changed, so the second
        question is entitled to the first one's answer; :meth:`_forget` is where that stops.
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
                # notification gets nothing, which is what a notification always gets - and
                # either way the next message is still read.
                write_message(self.writer, error(message.get("id"), fault.code, str(fault)))
                continue
            if not keep_going:
                return 0

    def _handle(self, message: dict[str, Any]) -> bool:
        """Act on one message; ``False`` means the client asked the server to exit."""
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            self._initialise(message.get("params") or {})
            write_message(self.writer, response(request_id, self._capabilities()))
        elif method == "shutdown":
            write_message(self.writer, response(request_id, None))
        elif method == "exit":
            return False
        elif method in _REFRESHING:
            self.refresh(self._document(message))
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

    def _document(self, message: dict[str, Any]) -> Path:
        """The file a request is about."""
        params = _field(message.get("params"), dict, "params")
        target = _field(params.get("textDocument"), dict, "params.textDocument")
        return uri_to_path(_field(target.get("uri"), str, "params.textDocument.uri"))

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
            self._builds = [
                info for root in self.roots for info in discover(root, self.build_directories)
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

    def _projects_of(self, document: Path) -> list[Workspace]:
        """The projects containing a document, loaded once per refresh."""
        found = self._projects.get(document)
        if found is None:
            found = workspaces(self._builds_now(), document, self._root_for(document))
            self._projects[document] = found
        return found

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
        checked, but only for what one file can settle - so a missing record looks exactly
        like a project with nothing wrong with it, and the difference is invisible. Twice now
        that has been read as the checks having stopped working.

        A record naming a project that is not there gets said out loud, because it is the way
        this goes wrong in practice: a record written inside a container names a path that
        exists only in the container, and is then found, read and quietly of no use.
        """
        current = tuple((info.image, info.project) for info in builds)
        if current == self._announced:
            return
        self._announced = current
        if not builds:
            self._log(
                "no ddd-build.json found: every file is checked on its own, so findings that "
                "need the whole project - a missing producer, two components disagreeing - "
                "are not reported. Configure the build, or pass -b <build directory>."
            )
            return
        for info in builds:
            known = Path(info.project).is_file()
            self._log(
                f"{info.image or 'build'}: {info.project}"
                + ("" if known else "  <- no such file, so this project cannot be analysed")
            )

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
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        found: list[Site] = []
        for workspace in self._projects_of(path):
            built = index(workspace)
            if method == _DEFINITION:
                found.extend(definition(built, document, path, pointer))
            else:
                found.extend(references(built, document, pointer))
        return locations(found, cache)

    def _hover(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """What the variable under the cursor turned out to be, once the project is resolved.

        ``None`` where there is nothing to say - a description, a number, whitespace, or a
        name no component declares - which a client shows by doing nothing at all.
        """
        path = self._document(message)
        document = read(path, {})
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
        document = read(path, {})
        pointer = document.pointer_at(self._at(message))
        subject = renameable_at(document, pointer)
        if subject is None:
            return None
        span = document.text_range_of(pointer)
        return None if span is None else {"range": span, "placeholder": subject[1]}

    def _answer_rename(self, request_id: Any, message: dict[str, Any]) -> None:
        """Rewrite a name everywhere the project writes it, or say why it cannot be.

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing.
        """
        path = self._document(message)
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        params = _field(message.get("params"), dict, "params")
        wanted = _field(params.get("newName"), str, "params.newName")
        changes: dict[str, list[dict[str, Any]]] = {}
        # A component linked into two images is in two projects, and both of them mention the
        # same characters. Sending that edit twice is not a duplicate an editor tolerates: it
        # is two overlapping rewrites of one range.
        seen: set[tuple[str, int, int]] = set()
        subject = renameable_at(document, pointer)
        for workspace in self._projects_of(path):
            built = index(workspace)
            refused = rename_problem(built, wanted, subject[0] if subject else "variable")
            if refused is not None:
                write_message(self.writer, error(request_id, REQUEST_FAILED, refused))
                return
            for uri, edits in rename_edits(built, document, pointer, wanted, cache).items():
                for edit in edits:
                    start = edit["range"]["start"]
                    where = (uri, start["line"], start["character"])
                    if where not in seen:
                        seen.add(where)
                        changes.setdefault(uri, []).append(edit)
        # The edits rewrite the very files every answer above was read out of, so anything
        # kept from before them now describes the past.
        self._forget()
        write_message(self.writer, response(request_id, {"changes": changes}))

    def _actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """What can be offered for the key under the cursor.

        The range a client sends covers a selection rather than a point, so the start of it is
        what decides: an author asking for a fix has put the caret on the thing they mean.
        """
        path = self._document(message)
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message, "range"))
        params = _field(message.get("params"), dict, "params")
        reported = params.get("context", {}).get("diagnostics", [])
        offered: list[dict[str, Any]] = []
        for workspace in self._projects_of(path):
            offered.extend(actions(index(workspace), path, document, pointer, cache, reported))
        return offered

    def _initialise(self, params: dict[str, Any]) -> None:
        """Take the workspace folders from whichever of the two ways the client offers them."""
        folders = params.get("workspaceFolders") or []
        if folders:
            self.roots = [uri_to_path(folder["uri"]) for folder in folders]
        elif params.get("rootUri"):
            self.roots = [uri_to_path(params["rootUri"])]

    def _capabilities(self) -> dict[str, Any]:
        return {
            # change 0 is TextDocumentSyncKind.None: the server reads files from disk, so
            # sending it every keystroke would be traffic nothing looks at.
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 0, "save": True},
                "definitionProvider": True,
                "referencesProvider": True,
                "hoverProvider": True,
                "renameProvider": {"prepareProvider": True},
                "codeActionProvider": {"codeActionKinds": [QUICK_FIX]},
            },
            "serverInfo": {"name": "ddd", "version": __version__},
        }

    def _publish(self, path: Path, findings: list[dict[str, Any]]) -> None:
        write_message(
            self.writer,
            notification(
                "textDocument/publishDiagnostics",
                {"uri": path.as_uri(), "diagnostics": findings},
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
