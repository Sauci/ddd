"""The web server of ``ddd gui``: the compiled pages and the JSON API, on this computer by default.

Any web page open in the same browser can send requests to a server on the loopback address, so
this one trusts nothing it did not hand out itself:

* the address the command prints carries a token, which ``/open`` swaps for a cookie every other
  request has to present - ``SameSite=Strict``, so a request another site makes does not carry
  it; the browser ``ddd gui`` opens for the reader is launched on a one-time code instead, so
  the token itself never sits on a command line for another local process to read;
* a request has to name this server's own host and port, which refuses a page whose domain was
  re-pointed at the loopback address;
* in a browser that sends ``Sec-Fetch-Site`` (Chrome 76, Firefox 90, Safari 16.4 and later),
  every request has to say, with it, that it came from this page or from no page at all, and,
  if it names an ``Origin``, that the ``Origin`` is this server's - checked before the cookie,
  so a page on another port of this address is refused however it asks, ``/open`` excepted,
  which is routed before this check ever runs. An older browser sends neither header on a
  plain request, so this does not catch it there;
* a request that changes anything has to come from this server's own origin, as json;
* no page of it can be framed, and only its own scripts run;
* no more than sixty-four connections are answered at once; past that, the thread that accepts
  connections refuses the next itself, so no flood of connections can exhaust the machine's
  threads.

The pages are served with an explicit content type per extension. The platform's guess is not
used: on Windows ``mimetypes`` reads the registry, which can map ``.js`` to ``text/plain``, and a
browser told ``nosniff`` then refuses to run the page at all.

See ``docs/gui_security.rst`` for the threat model this is reviewed against.
"""

from __future__ import annotations

import contextlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from collections.abc import Callable, Sequence
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

TOKEN_BYTES: Final = 32
"""Random bytes in the long-lived token, and in each single-use launch code: the same
strength, since either one alone signs a browser in."""

CODE_SECONDS: Final = 60
"""How long an unredeemed launch code stays valid: long enough for a slow browser to start and
ask, short enough that a code a local reader of ``/proc`` raced from the launch cannot be tried
for long."""

MAX_BODY: Final = 1024 * 1024
"""The largest request body accepted; an edit of a description file is a few hundred bytes."""

IDLE_SECONDS: Final = 30
"""How long a connection that carries nothing is kept open before it is closed.

Longer than any gap a page of this server leaves: the slowest thing it does is wait for the
state to change, and the connection that waits is never idle - the server is holding the
answer, and the page asks again the moment it arrives. A tab that has gone away leaves its
connections behind, and this is what takes their threads back."""

MAX_CONNECTIONS: Final = 64
"""How many connections are answered at once, each on a thread of its own; the next is refused.

A browser opens at most six connections to one host, across all its tabs, so the page never
comes near this: sixty-four leaves room for ten browser profiles and some scripts. Without
it, the threads grew with whatever was asked: probed against ``7d7aaed``, three hundred long
polls at once took the server from 4 threads to 275."""

BUSY: Final = "ddd gui is answering as many connections as it takes at once; ask again in a moment"
"""What a connection past :data:`MAX_CONNECTIONS` is answered, with a ``503``."""

REFUSAL_SECONDS: Final = 1
"""How long the thread that accepts connections waits to write a refusal into a connection that
will not take it, before giving that connection up: every other connection waits behind that
thread meanwhile. A connection just accepted takes the refusal's few hundred bytes at once, so
in practice it never waits at all."""

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

SIGNED_IN_PAGE: Final = (
    '<!doctype html><html lang="en"><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0; url={target}"><title>ddd gui</title>'
    '<p><a href="{target}">Open ddd gui</a></p></html>'
)
"""What ``/open`` answers once it has set the cookie: a page that refreshes to the project, or
to the start page. Not a redirect: ``/open`` is reached however the token or a launch code got
there - pasted, clicked from somewhere else, or a browser opened straight on it - and a
``SameSite=Strict`` cookie does not reliably follow a redirect chain that began cross-site,
where a refresh this page makes itself is a fresh, same-origin navigation, which the cookie
does follow. A meta refresh rather than a script: no script is needed, so none is written, and
the fallback link below it is for a browser that blocks the refresh itself."""


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


def _head(kind: str, length: int, headers: dict[str, str] | None = None) -> dict[str, str]:
    """The headers of an answer, in the order they are sent: the security headers, the
    answer's own, then the type and length of what it carries. Read by every answer
    :meth:`_Handler._send` writes and by the refusal :func:`_refuse` writes by hand alike, so
    that the two cannot drift apart. The answers ``http.server`` writes itself with
    ``send_error``, to a request it cannot read or does not handle (400, 414, 431, 501, 505),
    do not come through here."""
    return {
        **SECURITY_HEADERS,
        **(headers or {}),
        "Content-Type": kind,
        "Content-Length": str(length),
    }


def _refuse(request: socket.socket) -> None:
    """Write the 503 a connection past the cap gets, and give up on one that will not take it.

    Written on the thread that accepts connections, which every other connection waits behind,
    so nothing here waits on the client for long: what it has sent so far is drained without
    waiting for more - closing with it unread would reset the connection, and could throw the
    answer away before the client read it - and the answer is given :data:`REFUSAL_SECONDS` to
    be written. A client already gone is let go without a word, as one that goes away
    mid-answer is (:meth:`GuiServer.handle_error`)."""
    data = json.dumps({"error": "busy", "message": BUSY}).encode("utf-8")
    own = {"Cache-Control": "no-store", "Retry-After": "1", "Connection": "close"}
    head = _head(CONTENT_TYPES[".json"], len(data), own)
    lines = "".join(f"{name}: {value}\r\n" for name, value in head.items())
    with contextlib.suppress(OSError):
        request.setblocking(False)
        with contextlib.suppress(BlockingIOError):
            request.recv(65536)
        request.settimeout(REFUSAL_SECONDS)
        request.sendall(f"HTTP/1.1 503 Service Unavailable\r\n{lines}\r\n".encode("latin-1") + data)


class GuiServer(ThreadingHTTPServer):
    """The server one run of ``ddd gui`` answers on."""

    daemon_threads = True

    allow_reuse_address = sys.platform != "win32"
    """Not on Windows, where the socket option lets a second server bind a port the first still
    listens on, so a taken ``--port`` would be shared instead of refused."""

    def __init__(
        self,
        api: Api,
        static: Path,
        port: int = 0,
        host: str = "127.0.0.1",
        *,
        clock: Callable[[], float] = time.monotonic,
        connections: int = MAX_CONNECTIONS,
    ) -> None:
        super().__init__((host, port), _Handler)
        self.api = api
        self.static = static.resolve()
        self.token = secrets.token_urlsafe(TOKEN_BYTES)
        self._clock = clock
        self._code: tuple[str, float] | None = None
        self._last_code: str | None = None
        self._code_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(connections)
        """One for each connection being answered. Bounded: a slot given back when every slot
        is already free raises, rather than raising the cap."""

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def issue_code(self) -> str:
        """Mint a single-use code that signs a browser in exactly as the long-lived token
        does, valid for :data:`CODE_SECONDS` from now or until redeemed, whichever is first.
        Replaces whatever code was issued before it: only the launch that just started should
        be able to use one."""
        code = secrets.token_urlsafe(TOKEN_BYTES)
        with self._code_lock:
            self._code = (code, self._clock() + CODE_SECONDS)
            self._last_code = code
        return code

    def redeem_code(self, given: str) -> bool:
        """Whether ``given`` is the one outstanding launch code, presented before it expired.

        Spends it the moment its value matches - whether or not it had already expired - so
        a second presentation, even of the right value, never succeeds again. Compared in
        constant time, like the token.
        """
        with self._code_lock:
            pending = self._code
            if pending is None:
                return False
            code, expires = pending
            if not hmac.compare_digest(given.encode("utf-8"), code.encode("utf-8")):
                return False
            self._code = None
            return self._clock() < expires

    def code_known(self, given: str) -> bool:
        """Whether ``given`` is the value of the launch code most recently issued, whether or
        not it has since been redeemed or has expired. Used only to decide what a refusal to
        sign in prints - never whether to sign in, which is :meth:`redeem_code` alone."""
        with self._code_lock:
            known = self._last_code
        return known is not None and hmac.compare_digest(
            given.encode("utf-8"), known.encode("utf-8")
        )

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

    def process_request(self, request: Any, client_address: Any) -> None:
        """Answer on a thread of its own if a slot is free; else refuse from this thread.

        The refusal is written here, on the thread that accepts, so that a connection past the
        cap starts no thread: what it reads first is drained without waiting, so that closing
        does not reset the connection before the client reads its answer."""
        if not self.slots.acquire(blocking=False):
            _refuse(request)
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            # The thread never started, so nothing else will give its slot back. Not
            # BaseException: an interrupt that lands after the thread has started would then
            # give the slot back twice, once here and once by the thread. This way the worst is
            # one slot leaked by a server that is being stopped anyway.
            self.slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        """Answer one connection on its own thread, and give its slot back however that ends."""
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

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
        the page then said the server was not answering - or, waiting for the state to change,
        that it had stopped - about a server that was running. The traceback still goes to the
        terminal, where whoever reads the page's message is sent. A page that went away
        mid-answer is let go as before: there is nobody left to answer, and nothing worth
        printing, whether it closed the connection or only stopped reading it.
        """
        try:
            self._route(method)
        except (ConnectionError, TimeoutError):
            raise
        except Exception:
            # self.path, never split again to print it: a target that reaches here unanswered
            # already broke by not splitting (below), and the path is anyone's text regardless
            # - an escape sequence in it would otherwise reach the terminal raw, this one read
            # for exactly that.
            print(f"ddd gui: {method} {self.path!r} failed:", file=sys.stderr)
            traceback.print_exc()
            self._send_json(500, {"error": "internal", "message": _INTERNAL})

    def _route(self, method: str) -> None:
        port = self._gui.port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self._send(421, b"misdirected request", CONTENT_TYPES[".txt"])
            return
        try:
            url = urlsplit(self.path)
        except ValueError:
            # The absolute form of a target names its host before its path, and a malformed
            # one - a bracket opened for an IPv6 address and never closed, say - makes urlsplit
            # itself raise, before anything here has read where the request claims to come
            # from or whether it carries this server's cookie.
            self._send_json(400, {"error": "bad-request", "message": _NOT_A_TARGET})
            return
        if method == "GET" and url.path == "/open":
            self._sign_in(parse_qs(url.query))
            return
        api = url.path.startswith("/api/")
        if self._from_elsewhere():
            if api:
                self._send_json(403, {"error": "forbidden", "message": _ELSEWHERE})
            else:
                self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
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
        # Blank values kept: what a blank means is each route's own to say - the empty text for
        # a unit's description, the whole file for a fix's place in it, the key taken away for a
        # settled value, and, for most keys a route requires, the refusal of one left out. Every
        # value is kept too, a key given twice included, for the api to refuse
        # (`ddd.gui.routes.one_value_each`).
        query = parse_qs(url.query, keep_blank_values=True)
        reply = self._gui.api.handle(method, url.path, query, body)
        self._send_json(reply.status, reply.body)

    def _sign_in(self, query: dict[str, list[str]]) -> None:
        given_token = (query.get("token") or [""])[0]
        given_code = (query.get("code") or [""])[0]
        just_signed_in = hmac.compare_digest(
            given_token.encode("utf-8"), self._gui.token.encode("utf-8")
        )
        if not just_signed_in and given_code:
            just_signed_in = self._gui.redeem_code(given_code)
        # Its URL holds a secret - the token, or the code - so neither this page nor a
        # refusal of it may be cached and replayed from a shared cache or browser history.
        headers = {"Cache-Control": "no-store"}
        if just_signed_in:
            headers["Set-Cookie"] = (
                f"{self._gui.cookie}={self._gui.token}; HttpOnly; SameSite=Strict; Path=/"
            )
        elif not (given_code and self._signed_in()):
            # Exactly which requests get the signed-in page instead of this refusal: one
            # naming a code that did not redeem - wrong, spent or expired alike - that
            # already carries this server's valid cookie, as a browser's own prefetch of
            # the /open?code= address does, or its navigating there a second time after the
            # first already won the cookie. A request with no code at all, or a wrong
            # token, refuses here regardless of the cookie.
            if given_code and self._gui.code_known(given_code):
                # Known, so it did redeem once, or was still waiting to and has now timed
                # out - either way, this request carries none of the cookie that would have
                # meant it was the browser that won it.
                print(_CODE_REUSED, file=sys.stderr)
            self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"], headers)
            return
        # A project open goes to its page, analysed yet or not: the page says it is being
        # analysed until its first analysis lands.
        target = "/project" if self._gui.api.session.project is not None else "/"
        page = SIGNED_IN_PAGE.format(target=target).encode("utf-8")
        self._send(200, page, CONTENT_TYPES[".html"], headers)

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

    def _own_origins(self) -> tuple[str, str]:
        """This server's own origin, spelled the two ways a browser may carry it: by
        127.0.0.1 and by localhost, both at this server's port. What :meth:`_from_elsewhere`
        and :meth:`_from_this_page` both compare a request's ``Origin`` against, kept in this
        one place rather than each holding a literal tuple of its own."""
        port = self._gui.port
        return (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def _from_elsewhere(self) -> bool:
        """Whether the request says it came from somewhere other than this server's own page.

        A browser marks every request it sends with ``Sec-Fetch-Site``: ``same-origin`` from
        this server's own page, ``none`` for an address typed or a bookmark, and ``same-site``
        from a page served on another port of this address - which also carries this server's
        ``SameSite=Strict`` cookie, a cookie belonging to an address and not to a port. Every
        browser sends it since 2023 (Chrome 76, Firefox 90, Safari 16.4). An ``Origin`` other
        than this server's is refused too, for a browser older than those. A client that sends
        neither - a script, ``curl``, these tests - goes on to the cookie, so the token still
        decides.
        """
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            return True
        origin = self.headers.get("Origin")
        if origin is None:
            return False
        return origin not in self._own_origins()

    def _from_this_page(self) -> bool:
        origin = self.headers.get("Origin")
        kind = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        return origin in self._own_origins() and kind == "application/json"

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
        try:
            requested: Path | None = (static / unquote(path).lstrip("/")).resolve()
        except ValueError:
            # A NUL character, say: no file on this computer can be named by one, which
            # makes it one more path with no file of its own rather than a failure - the
            # client-side router turns it into a screen the same way it does an unknown one.
            requested = None
        # os.path.isfile, not Path.is_file: a name over 255 bytes raises ENAMETOOLONG from the
        # stat it makes, which isfile has always caught alongside ValueError, on every Python
        # this runs on - pathlib.Path.is_file only started doing the same on 3.14, and on 3.12
        # and 3.13 re-raises it, one more path with no file of its own answered as a failure.
        target = (
            requested
            if requested is not None
            and requested.is_relative_to(static)
            and os.path.isfile(requested)  # noqa: PTH113 - Path.is_file is the bug, see above
            else static / "index.html"
        )
        kind = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), kind)

    def _send(
        self, status: int, data: bytes, kind: str, headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        for name, value in _head(kind, len(data), headers).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        # Python writes NaN and Infinity unless told not to, and no browser's parser reads them:
        # a value that slips through fails here, and is answered as the failure it is.
        data = json.dumps(body, allow_nan=False).encode("utf-8")
        self._send(status, data, CONTENT_TYPES[".json"], {"Cache-Control": "no-store"})


_ELSEWHERE: Final = "ddd gui answers its own page alone, opened from the address it printed"
_SIGN_IN: Final = "open the address ddd gui printed in its terminal"
_FORBIDDEN: Final = "only this server's own page may change anything, and only as json"
_PAGES_ARE_READ: Final = "pages are read with GET"
_NOT_A_TARGET: Final = "the request's target cannot be read"
_INTERNAL: Final = "ddd gui failed on this request; the terminal it runs in shows why"
_CODE_REUSED: Final = (
    "ddd gui: a launch code arrived that was already spent, or had simply expired; if your "
    "browser did not just sign in on its own, something else on this computer may have used "
    "it instead, so restart ddd gui if your browser is not signed in"
)


def _refused(value: str, port: int, error: Exception) -> int:
    """A usage error naming what could not be served and the port, the same shape whether
    resolving ``--host`` or binding what it resolved to is what failed."""
    print(f"ddd: cannot serve {value} on port {port}: {error}", file=sys.stderr)
    return EXIT_USAGE


def launched(server: GuiServer, opener: Callable[[str], object]) -> None:
    """Open a one-time address in a browser, instead of handing it the long-lived token.

    ``webbrowser.open(address)`` starts the browser with the address as an argument, and a
    process's arguments are readable by every user of the computer, in ``/proc`` on Linux:
    the long-lived token would be theirs for the asking while the launch ran. A single-use
    launch code stands in for it instead, minted fresh by :meth:`GuiServer.issue_code` -
    worthless the moment it is redeemed, or :data:`CODE_SECONDS` after it was minted,
    whichever comes first.

    Not a file: a sandboxed browser (a snap, a flatpak) has its own private temporary
    directory, and cannot open one written to this computer's. An address of this server's
    own reaches it the same way the printed one, pasted, would.
    """
    opener(f"http://127.0.0.1:{server.port}/open?code={server.issue_code()}")


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
    # Started before the project is opened, so that its first analysis runs on the analyser's
    # own thread while the address is printed and served, and stopped on every way out of here,
    # which ends that thread and the poller's.
    session.start()
    try:
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
            # the Host and Origin allow-lists above still only admit 127.0.0.1 and localhost,
            # so a client that merely reaches the port could forge both. The token in the
            # address this just printed is what is left, hence publishing the port on the
            # host's loopback alone rather than trusting the network between here and there.
            print(
                f"ddd gui: listening on {address}:{server.port}, beyond this computer's "
                "loopback; publish it on the host's loopback only, "
                f"-p 127.0.0.1:{server.port}:{server.port}, since the token in the address is "
                "what keeps others out",
                file=sys.stderr,
            )
        elif open_browser:
            # On a thread of its own: an opener that waits for the browser to exit
            # (GenericBrowser.open's p.wait(), for a BROWSER line with no trailing '&', or
            # for a console browser such as lynx or w3m) would otherwise hold this up before
            # serve_forever() below is ever reached, leaving the socket bound but nothing
            # answered until that browser did.
            threading.Thread(
                target=launched, args=(server, webbrowser.open), daemon=True, name="ddd-gui-open"
            ).start()
        try:
            with contextlib.suppress(KeyboardInterrupt):
                server.serve_forever()
        finally:
            server.server_close()
    finally:
        session.stop()
    return EXIT_OK
