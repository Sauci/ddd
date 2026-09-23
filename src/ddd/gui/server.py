"""The web server of ``ddd gui``: the compiled pages and the JSON API, on this computer by default.

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
import ipaddress
import json
import secrets
import socket
import sys
import traceback
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

IDLE_SECONDS: Final = 30
"""How long a connection that carries nothing is kept open before it is closed.

Longer than any gap a page of this server leaves: the slowest thing it does is wait for a
revision, and the connection that waits is never idle - the server is holding the answer, and
the page asks again the moment it arrives. A tab that has gone away leaves its connections
behind, and this is what takes their threads back."""

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


def is_loopback(address: str) -> bool:
    """Whether a numeric address can only mean this computer: 127.0.0.0/8, or ``::1``.

    ``run`` below reads this, once, to decide what answering beyond the default,
    ``127.0.0.1``, changes: whether a browser is opened, and what the one warning it prints
    says. It never sees a name: ``run`` resolves ``--host`` with ``socket.getaddrinfo`` before
    calling this, so a hosts file that redefines ``localhost`` is judged by what it resolves
    to and not by its spelling, and ``LOCALHOST`` or ``localhost.`` are judged the same way as
    ``localhost`` rather than by a spelling this function would have to special-case. Anything
    ``ipaddress`` cannot parse - a name, such as ``localhost`` itself, reaching this function
    directly, or an address malformed enough that no interface could carry it - answers
    ``False`` rather than raising, which matters only to this function's own tests: every
    caller in this module already hands it what a real resolution produced.
    """
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


class GuiServer(ThreadingHTTPServer):
    """The server one run of ``ddd gui`` answers on."""

    daemon_threads = True

    allow_reuse_address = sys.platform != "win32"
    """Not on Windows, where the socket option lets a second server bind a port the first still
    listens on, so a taken ``--port`` would be shared instead of refused."""

    def __init__(self, api: Api, static: Path, port: int = 0, host: str = "127.0.0.1") -> None:
        super().__init__((host, port), _Handler)
        self.api = api
        self.static = static.resolve()
        self.token = secrets.token_urlsafe(32)

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def address(self) -> str:
        """The address to open; the token in it is what the cookie is given for.

        Always ``127.0.0.1``, whatever ``host`` this server binds: pasted into a browser on
        this computer, it reaches the process when ``host`` is ``127.0.0.1`` itself or
        ``0.0.0.0`` - every interface, loopback included - and not when ``host`` names one
        interface that is neither, such as ``127.0.0.2`` or a specific address of a network
        this computer is also on: that interface alone answers, and this is a different one.
        """
        return f"http://127.0.0.1:{self.port}/open?token={self.token}"

    @property
    def cookie(self) -> str:
        """The name of the cookie this server signs a page in with."""
        return f"{COOKIE}-{self.port}"

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A page that went away mid-answer - a reload, a closed tab - is not an error to print."""
        if not isinstance(sys.exc_info()[1], ConnectionError | TimeoutError):
            super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    """Keep the connection open for the next request, rather than closing after every answer.

    A page asks this server twenty-odd times to open a panel, and under HTTP/1.0 each ask cost a
    connection of its own. On windows that ran the machine out of the ports it hands connections:
    a suite of browser journeys, all of them against 127.0.0.1, was refused one with
    ``ERR_NO_BUFFER_SPACE`` at a point that moved from run to run. The same twenty asks now share
    the handful of connections the browser keeps. Every answer here carries a ``Content-Length``,
    which is what lets the page tell one from the next on a connection it reads twice."""

    timeout = IDLE_SECONDS
    """Applied to the socket, so a connection nobody is using does not hold its thread."""

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
        """Answer a request, and answer it as json even when answering it fails.

        Left to the base class, a failure printed its traceback and dropped the connection, and
        the page then said the server was not answering - or, waiting for a revision, that it
        had stopped - about a server that was running. The traceback still goes to the terminal,
        where whoever reads the page's message is sent. A page that went away mid-answer is let
        go as before: there is nobody left to answer, and nothing worth printing, whether it
        closed the connection or only stopped reading it.
        """
        try:
            self._route(method)
        except (ConnectionError, TimeoutError):
            raise
        except Exception:
            print(f"ddd gui: {method} {urlsplit(self.path).path} failed:", file=sys.stderr)
            traceback.print_exc()
            self._send_json(500, {"error": "internal", "message": _INTERNAL})

    def _route(self, method: str) -> None:
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
        # Blank values kept: clearing a unit's description asks for `description=`, which means
        # the empty text, where a parameter left out means nothing was given. Every handler that
        # reads a parameter answers a blank one as it answers a missing one, as it did when
        # blank values were dropped here.
        query = parse_qs(url.query, keep_blank_values=True)
        reply = self._gui.api.handle(method, url.path, query, body)
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
        # Python writes NaN and Infinity unless told not to, and no browser's parser reads them:
        # a value that slips through fails here, and is answered as the failure it is.
        data = json.dumps(body, allow_nan=False).encode("utf-8")
        self._send(status, data, CONTENT_TYPES[".json"], {"Cache-Control": "no-store"})


_SIGN_IN: Final = "open the address ddd gui printed in its terminal"
_FORBIDDEN: Final = "only this server's own page may change anything, and only as json"
_PAGES_ARE_READ: Final = "pages are read with GET"
_INTERNAL: Final = "ddd gui failed on this request; the terminal it runs in shows why"


def _refused(value: str, port: int, error: Exception) -> int:
    """A usage error naming what could not be served and the port, the same shape whether
    resolving ``--host`` or binding what it resolved to is what failed."""
    print(f"ddd: cannot serve {value} on port {port}: {error}", file=sys.stderr)
    return EXIT_USAGE


def run(
    project: Path | None,
    build_directories: Sequence[Path],
    port: int,
    *,
    host: str = "127.0.0.1",
    open_browser: bool,
    static: Path | None = None,
) -> int:
    """Serve until interrupted; the exit code of ``ddd gui``."""
    # Resolved once, before anything else is decided from it: a hosts file that redefines
    # ``localhost`` is then judged by the address it resolves to and not by its spelling, in
    # both directions. The server is IPv4 only, hence AF_INET; asking only for that also
    # turns ``--host ::1`` from a bind failure that blamed the port into a plain refusal here,
    # naming the address. A malformed or non-ASCII host used to reach the bind unresolved and
    # raise past every usage-error handler - a bare TypeError, exit 1 with a traceback -
    # where getaddrinfo instead raises a UnicodeEncodeError (a ValueError) or a gaierror (an
    # OSError), both ordinary usage errors.
    try:
        # str(): a general sockaddr's first element is typed str | int for every address
        # family this could be, and AF_INET's is always the former.
        address = str(socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0])
    except (OSError, ValueError) as error:
        return _refused(host, port, error)
    beyond_loopback = not is_loopback(address)
    if port == 0 and beyond_loopback:
        print(
            f"ddd: --host resolves to {address}, beyond this computer's loopback; --port 0 "
            "lets the system pick a free one there, which cannot be published in advance, "
            "so give a fixed --port too",
            file=sys.stderr,
        )
        return EXIT_USAGE
    pages = static_directory() if static is None else static
    if not (pages / "index.html").is_file():
        print(
            f"ddd: this installation has no compiled pages for ddd gui in {pages}; a released "
            "ddd-tool carries them, and so does the wheel ci builds for every branch it runs on; "
            "a source checkout builds them with 'npm ci' and 'npm run build' in its gui directory",
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
        server = GuiServer(Api(session, project), pages, port, address)
    except OSError as error:
        return _refused(address, port, error)
    print(f"ddd gui (preview) serving {server.address}", flush=True)
    if beyond_loopback:
        # No browser to open in a container, and nothing left to protect this with either:
        # the Host and Origin allow-lists above still only admit 127.0.0.1 and localhost, so
        # a client that merely reaches the port could forge both. The token in the address
        # this just printed is what is left, hence publishing the port on the host's loopback
        # alone rather than trusting the network between here and there.
        print(
            f"ddd gui: listening on {address}:{server.port}, beyond this computer's loopback; "
            f"publish it on the host's loopback only, -p 127.0.0.1:{server.port}:{server.port}, "
            "since the token in the address is what keeps others out",
            file=sys.stderr,
        )
    elif open_browser:
        webbrowser.open(server.address)
    session.start_polling()
    try:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    finally:
        session.stop()
        server.server_close()
    return EXIT_OK
