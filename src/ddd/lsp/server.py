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
from ddd.lsp.diagnostics import collect
from ddd.lsp.discovery import discover
from ddd.lsp.hover import describe, resolve
from ddd.lsp.navigation import (
    Site,
    definition,
    index,
    locations,
    references,
    subject_at,
    workspaces,
)
from ddd.lsp.protocol import (
    METHOD_NOT_FOUND,
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

    def run(self) -> int:
        """Serve until the client says to stop, or stops talking."""
        while True:
            message = read_message(self.reader)
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
        reports = collect(discover(self.root, self.build_directories), [document])
        # Only files with something to say, plus the ones that had something to say last time
        # and no longer do - those need an empty list to withdraw what is on screen.
        current = {path for path, findings in reports.items() if findings}
        for path in sorted(current | self._published):
            self._publish(path, reports.get(path, []))
        self._published = current

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
        for workspace in workspaces(discover(self.root, self.build_directories), path):
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
        name = subject_at(document, pointer)
        if name is None:
            return None
        dictionary = resolve(discover(self.root, self.build_directories), path)
        described = describe(dictionary, name) if dictionary else None
        if described is None:
            return None
        return {
            "contents": {"kind": "markdown", "value": described},
            "range": document.range_of(pointer),
        }

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
