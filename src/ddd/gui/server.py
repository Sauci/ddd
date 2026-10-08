"""The web server of ``ddd gui``: the compiled pages and the JSON API, on this computer by default.

Any web page open in the same browser can send requests to a server on the loopback address, so
this one trusts nothing it did not hand out itself:

* the address the command prints carries a token; the page trades it, or the launch's
  one-time code, at ``/open`` for the token it keeps, and sends it as
  ``Authorization: Bearer`` on every request to the API; no cookie is set or read, since a
  browser sends a cookie to every port of 127.0.0.1. The browser ``ddd gui`` opens for the
  reader is launched on that one-time code rather than the token itself, so the token
  never sits on a command line for another local process to read;
* a request has to name this server's own host and port, which refuses a page whose domain was
  re-pointed at the loopback address;
* in a browser that sends ``Sec-Fetch-Site`` (Chrome 76, Firefox 90, Safari 16.4 and later),
  every request has to say, with it, that it came from this page or from no page at all, and,
  if it names an ``Origin``, that the ``Origin`` is this server's, so a page on another port
  of this address is refused however it asks, ``GET /open`` excepted, which is routed before
  this check ever runs. An older browser sends neither header on a plain request, so this
  does not catch it there;
* a request that changes anything has to come from this server's own origin, as json;
* no page of it can be framed, and only a script served from this origin runs (a server that
  used the same port earlier could have served this origin; see ``docs/gui_security.rst``);
* no more than sixty-four connections are answered at once; past that, the thread that accepts
  connections refuses the next itself, so no flood of connections can exhaust the machine's
  threads;
* on loopback, an IPv6 address is held beside the IPv4 socket, on the very same port, and never
  listened on - ``[::1]`` on Linux and macOS, or on Windows the wildcard ``[::]`` in its place -
  so no other program can listen on ``localhost`` there, and a browser trying ``[::1]`` first
  falls back to 127.0.0.1, measured on Linux and Windows and never on macOS, rather than reaching
  a stranger;
* a ``POST`` refused before its body is read has that body read and thrown away, at most
  1,048,576 bytes of it, rather than left unread; where its length cannot be read this way, the
  connection closes behind the answer instead, draining for at most two seconds or until the
  sender stops, whichever is first. Closing one with bytes still unread resets it on Windows,
  which can lose the refusal before it reaches the browser.

The pages are served with an explicit content type per extension. The platform's guess is not
used: on Windows ``mimetypes`` reads the registry, which can map ``.js`` to ``text/plain``, and a
browser told ``nosniff`` then refuses to run the page at all.

See ``docs/gui_security.rst`` for the threat model this is reviewed against.
"""

from __future__ import annotations

import contextlib
import errno
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
from ddd.file_names import device_named
from ddd.gui.api import Api
from ddd.gui.session import Session

TOKEN_BYTES: Final = 32
"""Random bytes in the long-lived token, and in each single-use launch code: the same
strength, since either one alone signs a browser in."""

CODE_SECONDS: Final = 60
"""How long an unredeemed launch code stays valid: long enough for a slow browser to start and
ask, short enough that a code a local reader of ``/proc`` raced from the launch cannot be tried
for long."""

MAX_BODY: Final = 1024 * 1024
"""The largest request body accepted; an edit of a description file is a few hundred bytes."""

LINGER_SECONDS: Final = 2.0
"""How long a connection closed with a body still arriving is drained before its close (P18-31):
long enough for the client to read the answer it was written first, short enough that a sender
who never stops holds its thread no longer than that."""

OPEN_BODY: Final = 1024
"""The largest body ``POST /open`` accepts, far tighter than :data:`MAX_BODY`: a sign-in body
naming a code or the token is about sixty bytes, and anyone who reaches the port can post one,
no token needed. A longer body is refused before it is parsed, so no json parser ever runs on
a body big or deep enough to matter (:func:`_secret_of`)."""

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

_EXCLUSIVE: Final = sys.platform == "win32"
"""Whether a socket is bound with ``SO_EXCLUSIVEADDRUSE``: on Windows, where one bound without it
can be shared by another that sets ``SO_REUSEADDR``. A flag, so that the suite takes both
branches on every platform (``test_nothing_in_the_suite_skips``)."""

_WILDCARD: Final = sys.platform == "win32"
"""Whether the IPv6 hold is the wildcard ``[::]``, in place of ``[::1]`` (ruling P19a-14): on
Windows. There run 37737377854 measured a stranger's ``[::]`` binding beside an exclusive
``[::1]`` hold - and a program listening on ``[::]`` would take the connections the hold never
accepts - and run 37741191678 the server's own exclusive ``[::]`` refused beside its own
exclusive ``[::1]``, so the two cannot both be held. An exclusive wildcard is what Microsoft
documents refusing every other bind of its port, specific addresses included; run 37744112657
measured it refusing a stranger's ``[::1]`` too, on Windows 3.12, 3.13 and 3.14. Linux holds
``[::1]``, which refuses a stranger's ``[::]`` as well. A flag of its own rather than
:data:`_EXCLUSIVE`, which Windows sets too: the two rest on different measurements, and the suite
flips this one alone to hold the wildcard on Linux, where Windows' exclusive option is refused."""

PORT_TRIES: Final = 5
"""How many ports ``--port 0`` is tried on before the IPv6 hold refused on each of them is a
refusal."""

_SO_EXCLUSIVEADDRUSE: Final[int] = getattr(socket, "SO_EXCLUSIVEADDRUSE", -5)
"""Windows' own option, which typeshed declares on win32 alone, so read rather than named for mypy
on every platform; -5 is its value there, ``~SO_REUSEADDR``. Used only where :data:`_EXCLUSIVE`."""

_IPV6_HELD: Final = (
    "another program holds [{address}]:{port}, where a browser opening localhost:{port} would "
    "reach it"
)
"""What :class:`IPv6HeldError` says: ``[::1]``, or ``[::]``, refused as a port another socket
holds."""

_IPV6_UNHELD: Final = "cannot hold [{address}]:{port} beside it: {error}"
"""What a hold that failed for any other reason says, the system's own words after it
(P19a-12): no proof of another program, and no server without its hold either."""

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
    says; :func:`_held_beside` reads it for whether IPv6 is held beside the port. Neither
    sees a name: ``run`` resolves ``--host`` with ``socket.getaddrinfo`` before either asks
    this, so a hosts file that redefines ``localhost`` is judged by what it resolves
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


def _linger(connection: socket.socket) -> None:
    """Shut the writing side of a connection closed with a body still arriving, and drain what
    arrives before the close - until the client closes, :data:`LINGER_SECONDS` pass, or
    :data:`MAX_BODY` bytes have been read, whichever is first - so that the close is no reset
    that could throw the answer away before the client reads it (P18-31). The time is counted
    once, from the start, and no read asks for more than what is left of :data:`MAX_BODY`
    (P19a-11). Run on the connection's own thread (:meth:`_Handler.finish`), never on the one
    that accepts (:func:`_refuse`), which every other connection waits behind. A client already
    gone is let go without a word."""
    with contextlib.suppress(OSError):
        connection.shutdown(socket.SHUT_WR)
        deadline = time.monotonic() + LINGER_SECONDS
        drained = 0
        while drained < MAX_BODY:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            connection.settimeout(left)
            chunk = connection.recv(min(65536, MAX_BODY - drained))
            if not chunk:
                return
            drained += len(chunk)


class IPv6HeldError(OSError):
    """The IPv6 address ``ddd gui`` holds on its port - ``[::1]``, or ``[::]`` on Windows - held
    by another program."""


def _held_beside(host: str, port: int) -> socket.socket | None:
    """The IPv6 hold, bound on ``port`` beside a loopback ``host`` and never listened on (spec
    §6.2): ``[::1]``, or where :data:`_WILDCARD` the wildcard ``[::]`` in its place. No other
    program can then take ``localhost`` there, and a browser trying ``[::1]`` first is refused,
    and falls back to ``127.0.0.1`` - measured on Linux and Windows, never on macOS.

    ``None`` where nothing need or can be held: a host beyond loopback, or where the system says
    there is no IPv6 loopback - ``EAFNOSUPPORT`` making the socket, ``EADDRNOTAVAIL`` binding
    ``[::1]``. A wildcard is not refused for a missing address: in a network namespace with no
    IPv6 address at all, ``[::1]`` was refused ``EADDRNOTAVAIL`` and ``[::]`` bound (Linux,
    measured). Raises :class:`IPv6HeldError` for a port another socket holds: ``EADDRINUSE``, or
    ``EACCES``, the errno CPython gives Windows' ``WSAEACCES``. Any other error is proof of
    neither, and raises an ``OSError`` naming the address, the system's own words after it
    (P19a-12): a server that cannot make its hold does not start without it. Each refusal's
    message is the same on every system; the error the system raised is its cause.

    ``IPV6_V6ONLY``, so that it never touches IPv4. Never ``SO_REUSEADDR``: Linux lets two
    sockets share a port nobody listens on when both set it, and the other could then listen
    there. ``SO_EXCLUSIVEADDRUSE`` on Windows (:data:`_EXCLUSIVE`), where a socket bound without
    it can be shared by any that sets ``SO_REUSEADDR``."""
    if not is_loopback(host):
        return None
    address = "::1"
    if _WILDCARD:
        address = "::"
    try:
        held = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    except OSError as error:
        if error.errno == errno.EAFNOSUPPORT:
            return None
        raise OSError(_IPV6_UNHELD.format(address=address, port=port, error=error)) from error
    try:
        held.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        if _EXCLUSIVE:
            held.setsockopt(socket.SOL_SOCKET, _SO_EXCLUSIVEADDRUSE, 1)
        held.bind((address, port))
    except OSError as error:
        held.close()
        if error.errno == errno.EADDRNOTAVAIL:
            return None
        if error.errno in (errno.EADDRINUSE, errno.EACCES):
            raise IPv6HeldError(_IPV6_HELD.format(address=address, port=port)) from error
        raise OSError(_IPV6_UNHELD.format(address=address, port=port, error=error)) from error
    return held


class GuiServer(ThreadingHTTPServer):
    """The server one run of ``ddd gui`` answers on."""

    daemon_threads = True

    allow_reuse_address = sys.platform != "win32"
    """Not on Windows, where the socket option lets a second server bind a port the first still
    listens on, so a taken ``--port`` would be shared instead of refused."""

    held: socket.socket | None = None
    """The IPv6 hold, ``[::1]`` or on Windows ``[::]``, bound on this server's port and never
    listened on (:func:`_held_beside`), closed with the server; ``None`` where nothing is held -
    beyond loopback, or with no IPv6 loopback, and before the hold is made."""

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
        try:
            self.held = _held_beside(host, self.port)
        except BaseException:
            # Whatever the hold raises, as TCPServer.__init__ does around its own bind: the
            # IPv4 socket is closed here, never left to the collector.
            self.server_close()
            raise
        self.api = api
        self.static = static.resolve()
        self.token = secrets.token_urlsafe(TOKEN_BYTES)
        self._clock = clock
        self._code: tuple[str, float] | None = None
        self._redeemed: str | None = None
        self._code_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(connections)
        """One for each connection being answered. Bounded: a slot given back when every slot
        is already free raises, rather than raising the cap."""

    def server_bind(self) -> None:
        """Bind as ``http.server`` does - exclusively on Windows (:data:`_EXCLUSIVE`), so that no
        program can share the port by setting ``SO_REUSEADDR``. Set before the bind, as Windows
        requires."""
        if _EXCLUSIVE:
            self.socket.setsockopt(socket.SOL_SOCKET, _SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def server_close(self) -> None:
        """Close the socket served on, and the IPv6 hold beside it - that one even where closing
        the first raises."""
        try:
            super().server_close()
        finally:
            if self.held is not None:
                self.held.close()

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
        return code

    def redeem_code(self, given: str) -> bool:
        """Whether ``given`` is the one outstanding launch code, presented before it expired.

        Spends it the moment its value matches - whether or not it had already expired - so
        a second presentation, even of the right value, never succeeds again; and remembers it
        only where it signs a browser in (:meth:`code_redeemed`). Compared in constant time,
        like the token.
        """
        with self._code_lock:
            pending = self._code
            if pending is None:
                return False
            code, expires = pending
            if not hmac.compare_digest(given.encode("utf-8"), code.encode("utf-8")):
                return False
            self._code = None
            if self._clock() >= expires:
                return False
            self._redeemed = code
            return True

    def code_redeemed(self, given: str) -> bool:
        """Whether ``given`` is the launch code that signed a browser in. Used only to decide
        what a refusal to sign in prints - never whether to sign in, which is
        :meth:`redeem_code` alone. A code that expired unused signed nobody in, and is no sign
        of anyone."""
        with self._code_lock:
            redeemed = self._redeemed
        return redeemed is not None and hmac.compare_digest(
            given.encode("utf-8"), redeemed.encode("utf-8")
        )

    @property
    def address(self) -> str:
        """The address to open; the token in it is what the page signs in with.

        Always ``127.0.0.1``, whatever ``host`` this server binds: pasted into a browser on
        this computer, it reaches the process when ``host`` is ``127.0.0.1`` itself or
        ``0.0.0.0`` - every interface, loopback included - and not when ``host`` names one
        interface that is neither, such as ``127.0.0.2`` or a specific address of a network
        this computer is also on: that interface alone answers, and this is a different one.
        """
        return f"http://127.0.0.1:{self.port}/open?token={self.token}"

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

    _body_read = False
    """Whether the request being answered has had its body read. A ``POST`` answered before it
    has, whatever the answer - misdirected, refused at the gate, sent to a page - has its body
    read then, and thrown away (:meth:`_send`): left on the connection, it would be read as the
    next request. One too long to read, of no length to read by, or sent with a
    ``Transfer-Encoding`` is answered ``Connection: close`` instead, and its connection drained
    as it closes (:meth:`finish`). A body sent ``Transfer-Encoding: chunked`` that reaches
    :meth:`_body` is never read, though it counts as read: it has no ``Content-Length``, which
    this server takes for a body of none, so what it sends is read as the next request."""

    _linger = False
    """Whether this connection is closed with a request's body unread - too long to read, of no
    length to read by, or sent with a ``Transfer-Encoding``. Its answer is written, its writing
    side shut, and what still arrives drained before the close (:meth:`finish`), so that the
    close is no reset."""

    def _declared(self) -> int | None:
        """The length a body refused before it is read is drained by (:meth:`_send`): its
        ``Content-Length`` (:meth:`_content_length`). ``None`` - its connection closed after the
        answer instead - for one that is no length, one past :data:`MAX_BODY`, or any
        ``Transfer-Encoding`` (P19a-10): a chunked body has no ``Content-Length``, and drained as
        a length of none, it would be left on the connection, to be read as the next request."""
        if "Transfer-Encoding" in self.headers:
            return None
        return self._content_length()

    def _content_length(self) -> int | None:
        """The length the request's ``Content-Length`` spells, if it is one this server reads: a
        length, of at most :data:`MAX_BODY` - and ``0`` with no ``Content-Length`` at all.
        ``None`` for one that is no length, or one past :data:`MAX_BODY`."""
        length = self.headers.get("Content-Length", "0")
        if not (length.isascii() and length.isdecimal()):
            return None
        # Leading zeros are stripped before int() reads anything: int() refuses a string of more
        # than 4,300 digits whatever their value - by default; sys.get_int_max_str_digits() says
        # how many. What is left is past MAX_BODY if it has more digits than MAX_BODY's seven,
        # which settles it without converting it, and is read as its value otherwise: zeros
        # alone, however many, are a length of 0.
        significant = length.lstrip("0") or "0"
        if len(significant) > len(str(MAX_BODY)) or int(significant) > MAX_BODY:
            return None
        return int(significant)

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
        terminal, where whoever reads the page's message is sent, every character a terminal
        does not print as itself escaped (:func:`_shown`). A page that went away
        mid-answer is let go as before: there is nobody left to answer, and nothing worth
        printing, whether it closed the connection or only stopped reading it.
        """
        self._body_read = False
        try:
            self._route(method)
        except (ConnectionError, TimeoutError):
            raise
        except Exception:
            # self.path, not urlsplit(self.path).path: splitting again would drop the query
            # and fragment this prints along with the path, and self.path is anyone's text
            # regardless - an escape sequence in it would otherwise reach the terminal raw,
            # this one read for exactly that.
            print(f"ddd gui: {method} {self.path!r} failed:", file=sys.stderr)
            print(_shown(traceback.format_exc()), end="", file=sys.stderr)
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
            # from or whether it carries this server's token.
            self._send_json(400, {"error": "bad-request", "message": _NOT_A_TARGET})
            return
        if method == "GET" and url.path == "/open":
            # The page itself, which signs itself in: it reads the code or the token from this
            # address, posts it to /open, and keeps the token it is answered. Nothing is checked
            # or spent on a GET, so a browser's prefetch of the launch address spends no code.
            # The address holds a secret, so the answer is never stored.
            self._page("/", {"Cache-Control": "no-store"})
            return
        api = url.path.startswith("/api/")
        if self._from_elsewhere():
            if api:
                self._send_json(403, {"error": "forbidden", "message": _ELSEWHERE})
            else:
                self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        if url.path == "/open":
            # A POST alone: GET /open was answered above, before the gate. The sign-in needs
            # no credential, being where the page gets one, but it is a POST like any other:
            # this server's own page, as json.
            if not self._from_this_page():
                self._send_json(403, {"error": "forbidden", "message": _FORBIDDEN})
                return
            body = self._body()
            if body is None:
                return
            # Drained by _body() (part 18's P18-31), then refused on its length before _exchange
            # hands it to a parser: a body past OPEN_BODY never reaches json.loads, so no parser
            # runs on one big or deep enough to overflow a C stack and end the process. Anyone
            # who reaches the port can post here, no token needed, and a sign-in is sixty bytes.
            if len(body) > OPEN_BODY:
                self._send_json(413, {"error": "too-large", "message": _OPEN_TOO_LARGE})
                return
            self._exchange(body)
            return
        if not api:
            if method == "GET":
                self._page(url.path)
            else:
                self._send_json(405, {"error": "method-not-allowed", "message": _PAGES_ARE_READ})
            return
        if not self._signed_in():
            self._send_json(401, {"error": "unauthorised", "message": _SIGN_IN})
            return
        if method == "POST" and not self._from_this_page():
            self._send_json(403, {"error": "forbidden", "message": _FORBIDDEN})
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

    def _exchange(self, body: bytes) -> None:
        """``POST /open``: a launch code, or the token itself, traded for the token the page
        keeps and sends as ``Authorization: Bearer``. A code is spent the moment its value
        matches. One that already signed a browser in prints the terminal's warning when it is
        presented again, since the page that won it cleans it from its address and never
        presents it twice."""
        secret = _secret_of(body)
        if secret is None:
            self._send_json(400, {"error": "bad-request", "message": _OPEN_TAKES})
            return
        kind, given = secret
        if kind == "token":
            signed_in = hmac.compare_digest(given.encode("utf-8"), self._gui.token.encode("utf-8"))
        else:
            signed_in = self._gui.redeem_code(given)
            if not signed_in and self._gui.code_redeemed(given):
                print(_CODE_REUSED, file=sys.stderr)
        if signed_in:
            self._send_json(200, {"token": self._gui.token})
        else:
            self._send_json(403, {"error": "forbidden", "message": _SIGN_IN})

    def _signed_in(self) -> bool:
        """Whether the request carries this server's token as ``Authorization: Bearer``: the
        scheme in any case, as HTTP has it, then one space, then the token, compared in
        constant time. A cookie is no credential: a browser sends every cookie of 127.0.0.1 to
        every port of it, and so to every other server there."""
        scheme, _, given = self.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            given.encode("utf-8"), self._gui.token.encode("utf-8")
        )

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
        from a page served on another port of this address, which a browser counts as the same
        site, ports aside. Every browser sends the header since 2023 (Chrome 76, Firefox 90,
        Safari 16.4). An ``Origin`` other than this server's is refused too, for a browser older
        than those. A client that sends neither - a script, ``curl``, these tests - is let past
        this check: a page needs no credential, and the API needs the token.

        For the API this is a second defence. The first is that a page elsewhere has no token
        to send: no cookie holds it, and that page cannot send ``Authorization`` without a CORS
        preflight, which this server never grants.
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
        # By its Content-Length alone, not _declared: a body sent with a Transfer-Encoding that
        # comes this far is read as one of none, as it always was (P19a-10 left it so).
        size = self._content_length()
        if size is None:
            message = f"a request body is at most {MAX_BODY} bytes"
            self._send_json(413, {"error": "too-large", "message": message})
            return None
        body = self.rfile.read(size)
        self._body_read = True
        return body

    def _page(self, path: str, headers: dict[str, str] | None = None) -> None:
        """Answer the file of the compiled pages a path names, or ``index.html``, whose router
        makes a screen of any other path.

        A page path is plain names under the pages, split on ``/``. A name that is empty, ``.``
        or ``..``, or that holds a NUL character, a backslash or a colon - on Windows a
        separator, a drive or a stream - names no file, and is never looked up; nor, on any
        system, does a name Windows keeps for a device (:func:`ddd.file_names.device_named`, the
        rule a file an edit creates is refused by too), which it would open as that device. Nor
        does a name that is a symbolic link or a junction, or one past a name that is not a
        directory: so nothing outside the pages is served, and a path of thousands of names is
        looked up no deeper than the pages go.

        Nothing a path names is resolved. Resolving it touched the file system before anything
        checked where it led: a loop of links raised on Python 3.12, and on Windows a network
        or device spelling was opened.
        """
        static = self._gui.static
        target = static / "index.html"
        found = static
        # os.path's questions, not pathlib's: on Python 3.12 and 3.13 Path.is_dir, is_symlink
        # and is_file re-raise an error such as ENAMETOOLONG, a name over 255 bytes, where
        # os.path's answer false for whatever they cannot read, and never raise.
        for name in unquote(path).lstrip("/").split("/"):
            if name in ("", ".", "..") or "\\" in name or ":" in name or "\0" in name:
                break
            if device_named(name) is not None:
                break
            if not os.path.isdir(found):  # noqa: PTH112
                break
            found /= name
            if os.path.islink(found) or os.path.isjunction(found):  # noqa: PTH114
                break
        else:
            if os.path.isfile(found):  # noqa: PTH113
                target = found
        kind = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), kind, headers)

    def _send(
        self, status: int, data: bytes, kind: str, headers: dict[str, str] | None = None
    ) -> None:
        own = dict(headers or {})
        if self.command == "POST" and not self._body_read:
            # Refused before its body was read. A body this server would have read is read now
            # and thrown away: nothing of it is then read as the next request, and nothing is
            # left unread to make closing the connection a reset (P18-31). One it would not - too
            # long, of no length to read by, or sent with a Transfer-Encoding - is left: the
            # answer says Connection: close, sent as a header, which also has the base class
            # close the connection once this is written, and what still arrives is drained
            # before the close (finish).
            declared = self._declared()
            if declared is None:
                own["Connection"] = "close"
                self._linger = True
            else:
                self.rfile.read(declared)
                self._body_read = True
        self.send_response(status)
        for name, value in _head(kind, len(data), own).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def finish(self) -> None:
        """Close the files the connection was read and written through, then - if its last
        answer left a body unread - drain it before the server closes it (:func:`_linger`)."""
        super().finish()
        if self._linger:
            _linger(self.request)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        # Python writes NaN and Infinity unless told not to, and no browser's parser reads them:
        # a value that slips through fails here, and is answered as the failure it is.
        data = json.dumps(body, allow_nan=False).encode("utf-8")
        self._send(status, data, CONTENT_TYPES[".json"], {"Cache-Control": "no-store"})


_ELSEWHERE: Final = "ddd gui answers its own page alone, opened from the address it printed"
_SIGN_IN: Final = "open the address ddd gui printed in its terminal"
_OPEN_TAKES: Final = "/open takes json naming one of code and token, and nothing else"
_OPEN_TOO_LARGE: Final = f"/open takes a body of at most {OPEN_BODY} bytes"
_FORBIDDEN: Final = "only this server's own page may change anything, and only as json"
_PAGES_ARE_READ: Final = "pages are read with GET"
_NOT_A_TARGET: Final = "the request's target cannot be read"
_INTERNAL: Final = "ddd gui failed on this request; the terminal it runs in shows why"
_CODE_REUSED: Final = (
    "ddd gui: a launch code that already signed a browser in was presented again; if your "
    "browser is not signed in, another process on this computer may have signed in with it "
    "first and now holds the token itself, so restart ddd gui rather than open the address it "
    "printed"
)


def _secret_of(body: bytes) -> tuple[str, str] | None:
    """What ``POST /open`` was given: ``("code", <code>)`` or ``("token", <token>)``, or
    ``None`` for anything but a json object of exactly one of the two, its value text that
    UTF-8 can encode.

    Each object is read as the tuple of its pairs, and json reads an array as a list, so a
    tuple is an object, and a name given twice is two pairs. Read into a dict, an object kept
    the last of a repeated name, and ``{"token": "x", "token": <the token>}`` signed in.

    A lone surrogate is text UTF-8 cannot encode, which json spells as an escape, or as the
    bytes it decodes anyway. Comparing a secret encodes it, so one raised there, and was
    answered 500. A body nested deeper than python's own parser goes raises
    ``RecursionError``, which is no ``ValueError``, and is refused as any other malformed body.

    ``POST /open`` caps the body at :data:`OPEN_BODY` bytes before this runs (:meth:`_route`),
    far below any nesting that could exhaust the C stack, so the ``RecursionError`` catch is
    defence in depth rather than what holds that line."""
    try:
        given = json.loads(body, object_pairs_hook=tuple)
    except (ValueError, RecursionError):
        return None
    if not isinstance(given, tuple) or len(given) != 1:
        return None
    ((kind, value),) = given
    if kind not in ("code", "token") or not isinstance(value, str):
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return kind, value


def _shown(text: str) -> str:
    """``text`` as it may reach a terminal: every character that does not print as itself - a
    control character, the ``ESC`` an escape sequence begins with among them, or one that turns
    the text after it around - written as its escape, ``\\x1b``; a newline is kept, and every other
    line break, a carriage return among them, escaped too. What a failure's traceback is printed
    through: an exception's own message is anyone's text once it carries a request's."""
    return "".join(
        character
        if character == "\n" or character.isprintable()
        else character.encode("unicode_escape").decode("ascii")
        for character in text
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
        # A loop that never ends but by its break or a return: one over range(PORT_TRIES) would
        # end its last pass at one of them too, and leave its exhaustion a branch nothing takes.
        attempt = 1
        while True:
            try:
                server = GuiServer(Api(session, project), pages, port, address)
                break
            except IPv6HeldError as error:
                # --port 0 picked a port whose IPv6 hold - [::1], or [::] on Windows - another
                # program holds: another pick is another port. A port given is that port, or
                # nothing.
                if port != 0 or attempt == PORT_TRIES:
                    return _refused(address, port, error)
                attempt += 1
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
