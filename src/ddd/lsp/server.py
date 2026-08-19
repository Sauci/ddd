"""The language server itself: a loop, six messages, and no opinions of its own.

Everything that decides anything lives in :mod:`ddd.lsp.diagnostics` and
:mod:`ddd.lsp.discovery`; what is left here is translation. That split is deliberate, because
this is the layer a test can only reach through a protocol: keeping it thin keeps the thinking
somewhere that can be tested directly.

There is no net around the analysis, and that is not an oversight. The front end reports
through a diagnostic bag rather than raising - the developer documentation states it as a
rule - so a project that cannot be read produces findings, not an exception. A server that
wrapped it in a catch-all would be insuring against a thing the design already prevents, and
would hide it if that ever stopped being true.

Only ``didOpen`` and ``didSave`` refresh. Nothing is analysed per keystroke: the files are
read from disk, so the editor and the server agree exactly at the moment of a save, and a
half-typed document never produces a screenful of findings about a mistake nobody has finished
making yet.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Final
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ddd import __version__
from ddd.build_info import BuildInfo
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
    subject_at,
    type_at,
    variable_at,
    workspaces,
)
from ddd.lsp.protocol import (
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
    """The file a ``file://`` uri names, undoing the escaping a client applies to it."""
    return Path(url2pathname(unquote(urlparse(uri).path)))


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
        self.root = root or Path.cwd()
        self.build_directories = list(build_directories)
        self._published: set[Path] = set()
        self._announced: tuple[tuple[str, str], ...] | None = None
        """What was last said about the configured projects, so it is not said every save."""

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
            if message is None or not self._handle(message):
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
            self.refresh(uri_to_path(message["params"]["textDocument"]["uri"]))
        elif method in _NAVIGATING:
            write_message(self.writer, response(request_id, self._navigate(method, message)))
        elif method == _HOVER:
            write_message(self.writer, response(request_id, self._hover(message["params"])))
        elif method == _PREPARE_RENAME:
            prepared = self._prepare_rename(message["params"])
            write_message(self.writer, response(request_id, prepared))
        elif method == _RENAME:
            self._answer_rename(request_id, message["params"])
        elif method == _CODE_ACTION:
            write_message(self.writer, response(request_id, self._actions(message["params"])))
        elif request_id is not None:
            # A request always gets an answer, even a refusal: a client that is still waiting
            # on one looks exactly like a server that has died.
            write_message(
                self.writer, error(request_id, METHOD_NOT_FOUND, f"unsupported method {method}")
            )
        return True

    def refresh(self, document: Path) -> None:
        """Re-run the checks and publish what they say about every file involved.

        Every configured build is run, not only the one that claims this document. A component
        linked into two images is in two projects and they need not agree, and the answer to
        which one the reader cares about is "both": whichever is broken is broken.
        """
        builds = discover(self.root, self.build_directories)
        self._announce(builds)
        # A record naming a project that is not there is dropped rather than analysed. Running
        # it produces one finding, "file does not exist", published against a file nobody can
        # open - and the thing actually wrong is the record, which the log has just said.
        reports = collect(
            [info for info in builds if Path(info.project).is_file()], [document], self.root
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
        params = message["params"]
        path = uri_to_path(params["textDocument"]["uri"])
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(params["position"])
        found: list[Site] = []
        for workspace in workspaces(discover(self.root, self.build_directories), path, self.root):
            built = index(workspace)
            if method == _DEFINITION:
                found.extend(definition(built, document, path, pointer))
            else:
                found.extend(references(built, document, pointer))
        return locations(found, cache)

    def _hover(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """What the variable under the cursor turned out to be, once the project is resolved.

        ``None`` where there is nothing to say - a description, a number, whitespace, or a
        name no component declares - which a client shows by doing nothing at all.
        """
        path = uri_to_path(params["textDocument"]["uri"])
        document = read(path, {})
        pointer = document.pointer_at(params["position"])
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
        builds = discover(self.root, self.build_directories)
        described = None
        if named_type is not None:
            described = describe_external(builds, path, named_type, self.root)
        if described is None and (constant is not None or name is not None):
            dictionary = resolve(builds, path, self.root)
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

    def _prepare_rename(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Whether a rename may start here, and over which characters.

        Narrow where hovering is wide, and for a reason rather than out of caution: the editor
        opens its rename box *over the range this returns*. From a datatype, the only honest
        range would be a name several lines away, and a box appearing somewhere the pointer is
        not is worse than no box at all.
        """
        path = uri_to_path(params["textDocument"]["uri"])
        document = read(path, {})
        pointer = document.pointer_at(params["position"])
        name = variable_at(document, pointer)
        if name is None:
            return None
        span = document.text_range_of(pointer)
        return None if span is None else {"range": span, "placeholder": name}

    def _answer_rename(self, request_id: Any, params: dict[str, Any]) -> None:
        """Rewrite a name everywhere the project writes it, or say why it cannot be.

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing.
        """
        path = uri_to_path(params["textDocument"]["uri"])
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(params["position"])
        wanted = params["newName"]
        changes: dict[str, list[dict[str, Any]]] = {}
        # A component linked into two images is in two projects, and both of them mention the
        # same characters. Sending that edit twice is not a duplicate an editor tolerates: it
        # is two overlapping rewrites of one range.
        seen: set[tuple[str, int, int]] = set()
        for workspace in workspaces(discover(self.root, self.build_directories), path, self.root):
            built = index(workspace)
            refused = rename_problem(built, wanted)
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
        write_message(self.writer, response(request_id, {"changes": changes}))

    def _actions(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """What can be offered for the key under the cursor.

        The range a client sends covers a selection rather than a point, so the start of it is
        what decides: an author asking for a fix has put the caret on the thing they mean.
        """
        path = uri_to_path(params["textDocument"]["uri"])
        cache: dict[Path, Document] = {}
        document = read(path, cache)
        pointer = document.pointer_at(params["range"]["start"])
        reported = params.get("context", {}).get("diagnostics", [])
        offered: list[dict[str, Any]] = []
        for workspace in workspaces(discover(self.root, self.build_directories), path, self.root):
            offered.extend(actions(index(workspace), path, document, pointer, cache, reported))
        return offered

    def _initialise(self, params: dict[str, Any]) -> None:
        """Take the workspace root from whichever of the two ways the client offers it."""
        folders = params.get("workspaceFolders") or []
        if folders:
            self.root = uri_to_path(folders[0]["uri"])
        elif params.get("rootUri"):
            self.root = uri_to_path(params["rootUri"])

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
    why nothing in DDD prints there except through :func:`write_message`.
    """
    return Server(sys.stdin.buffer, sys.stdout.buffer, build_directories=build_directories).run()
