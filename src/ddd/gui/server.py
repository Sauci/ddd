"""The web server of ``ddd gui``: the compiled pages and the JSON API, on this computer only.

Any web page open in the same browser can send requests to a server on the loopback address, so
this one trusts nothing it did not hand out itself:

* the address the command prints carries a token, which ``/open`` swaps for a cookie every other
  request has to present - ``SameSite=Strict``, so a request another site makes does not carry
  it;
* a request has to name this server's own host and port, which refuses a page whose domain was
  re-pointed at the loopback address;
* a request that changes anything has to come from this server's own origin, as json;
* no page of it can be framed, and only its own scripts run.

The pages are served with an explicit content type per extension. The platform's guess is not
used: on Windows ``mimetypes`` reads the registry, which can map ``.js`` to ``text/plain``, and a
browser told ``nosniff`` then refuses to run the page at all.
"""

from __future__ import annotations

import contextlib
import hmac
import json
import secrets
import sys
import webbrowser
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import parse_qs, unquote, urlsplit

from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.gui.api import Api
from ddd.gui.session import Session

COOKIE: Final = "ddd-gui"
"""What the cookie a server signs a page in with is called, followed by ``-`` and the server's
port: a browser sends every cookie of 127.0.0.1 to every port, so under one name a second
``ddd gui`` replaced the first one's cookie and signed its page out."""

MAX_BODY: Final = 1024 * 1024
"""The largest request body accepted; an edit of a description file is a few hundred bytes."""

CONTENT_TYPES: Final = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
}

SECURITY_HEADERS: Final = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

SIGN_IN_PAGE: Final = (
    b'<!doctype html><html lang="en"><meta charset="utf-8"><title>ddd gui</title>'
    b"<p>Open the address <code>ddd gui</code> printed in its terminal.</p></html>"
)


def static_directory() -> Path:
    """Where the compiled pages are installed: ``static`` beside this module."""
    return Path(str(resources.files("ddd.gui").joinpath("static")))


class GuiServer(ThreadingHTTPServer):
    """The server one run of ``ddd gui`` answers on."""

    daemon_threads = True

    allow_reuse_address = sys.platform != "win32"
    """Not on Windows, where the socket option lets a second server bind a port the first still
    listens on, so a taken ``--port`` would be shared instead of refused."""

    def __init__(self, api: Api, static: Path, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.api = api
        self.static = static.resolve()
        self.token = secrets.token_urlsafe(32)

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def address(self) -> str:
        """The address to open; the token in it is what the cookie is given for."""
        return f"http://127.0.0.1:{self.port}/open?token={self.token}"

    @property
    def cookie(self) -> str:
        """The name of the cookie this server signs a page in with."""
        return f"{COOKIE}-{self.port}"

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A page that went away mid-answer - a reload, a closed tab - is not an error to print."""
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # the name the base class dispatches GET to
        self._answer("GET")

    def do_POST(self) -> None:  # the name the base class dispatches POST to
        self._answer("POST")

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: a request log in the terminal would bury the one line that matters."""

    @property
    def _gui(self) -> GuiServer:
        return cast(GuiServer, self.server)

    def _answer(self, method: str) -> None:
        port = self._gui.port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self._send(421, b"misdirected request", CONTENT_TYPES[".txt"])
            return
        url = urlsplit(self.path)
        if method == "GET" and url.path == "/open":
            self._sign_in(parse_qs(url.query))
            return
        api = url.path.startswith("/api/")
        if not self._signed_in():
            if api:
                self._send_json(401, {"error": "unauthorised", "message": _SIGN_IN})
            else:
                self._send(401, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        if method == "POST" and not self._from_this_page():
            self._send_json(403, {"error": "forbidden", "message": _FORBIDDEN})
            return
        if not api:
            if method == "GET":
                self._page(url.path)
            else:
                self._send_json(405, {"error": "method-not-allowed", "message": _PAGES_ARE_READ})
            return
        body = None
        if method == "POST":
            body = self._body()
            if body is None:
                return
        reply = self._gui.api.handle(method, url.path, parse_qs(url.query), body)
        self._send_json(reply.status, reply.body)

    def _sign_in(self, query: dict[str, list[str]]) -> None:
        given = (query.get("token") or [""])[0]
        if not hmac.compare_digest(given.encode("utf-8"), self._gui.token.encode("utf-8")):
            self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        target = "/project" if self._gui.api.session.revision is not None else "/"
        cookie = f"{self._gui.cookie}={self._gui.token}; HttpOnly; SameSite=Strict; Path=/"
        self._send(303, b"", CONTENT_TYPES[".txt"], {"Location": target, "Set-Cookie": cookie})

    def _signed_in(self) -> bool:
        """Whether the request carries this server's cookie with the token in it.

        The header is read by hand: the browser sends this server every cookie any app on
        127.0.0.1 has set, and ``http.cookies.SimpleCookie`` gives up on many of them. It stopped
        reading at ``prefs={"lang":"en"}`` or ``arr[0]=1`` without a word, which signed the page
        out behind a cookie that came first, and raised at ``user@site=1``, which left every
        request unanswered. A pair is split at its first ``=``; one not named for this server is
        passed over whatever it holds, and every one that is gets its value compared.
        """
        name = self._gui.cookie
        token = self._gui.token.encode("utf-8")
        for pair in self.headers.get("Cookie", "").split(";"):
            key, _, value = pair.strip().partition("=")
            if key == name and hmac.compare_digest(value.encode("utf-8"), token):
                return True
        return False

    def _from_this_page(self) -> bool:
        port = self._gui.port
        origin = self.headers.get("Origin")
        kind = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        own = (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
        return origin in own and kind == "application/json"

    def _body(self) -> bytes | None:
        length = self.headers.get("Content-Length", "0")
        if not (length.isascii() and length.isdecimal()):
            self._send_json(400, {"error": "bad-request", "message": "Content-Length is no length"})
            return None
        if int(length) > MAX_BODY:
            message = f"a request body is at most {MAX_BODY} bytes"
            self._send_json(413, {"error": "too-large", "message": message})
            return None
        return self.rfile.read(int(length))

    def _page(self, path: str) -> None:
        static = self._gui.static
        requested = (static / unquote(path).lstrip("/")).resolve()
        target = (
            requested
            if requested.is_relative_to(static) and requested.is_file()
            else static / "index.html"
        )
        kind = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), kind)

    def _send(
        self, status: int, data: bytes, kind: str, headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        for name, value in {**SECURITY_HEADERS, **(headers or {})}.items():
            self.send_header(name, value)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self._send(status, data, CONTENT_TYPES[".json"], {"Cache-Control": "no-store"})


_SIGN_IN: Final = "open the address ddd gui printed in its terminal"
_FORBIDDEN: Final = "only this server's own page may change anything, and only as json"
_PAGES_ARE_READ: Final = "pages are read with GET"


def run(
    project: Path | None,
    build_directories: Sequence[Path],
    port: int,
    *,
    open_browser: bool,
    static: Path | None = None,
) -> int:
    """Serve until interrupted; the exit code of ``ddd gui``."""
    pages = static_directory() if static is None else static
    if not (pages / "index.html").is_file():
        print(
            "ddd: this installation has no compiled pages for ddd gui; build them in the gui "
            "directory of a source checkout with 'npm ci' and 'npm run build'",
            file=sys.stderr,
        )
        return EXIT_USAGE
    session = Session(Path.cwd(), build_directories)
    if project is not None:
        try:
            session.open(project)
        except ValueError as error:
            print(f"ddd: {error}", file=sys.stderr)
            return EXIT_USAGE
    try:
        server = GuiServer(Api(session, project), pages, port)
    except OSError as error:
        print(f"ddd: cannot serve on port {port}: {error}", file=sys.stderr)
        return EXIT_USAGE
    print(f"ddd gui (preview) serving {server.address}", flush=True)
    if open_browser:
        webbrowser.open(server.address)
    session.start_polling()
    try:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    finally:
        session.stop()
        server.server_close()
    return EXIT_OK
