"""The server of ddd gui, over real HTTP: who may ask, what is served, and how it starts."""

from __future__ import annotations

import dataclasses
import errno
import http.client
import json
import os
import select
import shutil
import socket
import sys
import threading
import time
import types
from collections.abc import Callable, Collection, Iterator
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, quote, urlsplit

import pytest

import ddd
from conftest import (
    EXAMPLES,
    Gated,
    begun,
    component,
    declare,
    directory_link,
    looped,
    project,
    write_tree,
)
from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.editing import fingerprint
from ddd.file_names import device_named
from ddd.gui import api as api_module
from ddd.gui import server as module
from ddd.gui.api import Api, Reply
from ddd.gui.server import (
    _CODE_REUSED,
    _ELSEWHERE,
    _FORBIDDEN,
    _OPEN_TAKES,
    _OPEN_TOO_LARGE,
    _SIGN_IN,
    BUSY,
    CODE_SECONDS,
    LINGER_SECONDS,
    MAX_BODY,
    MAX_CONNECTIONS,
    OPEN_BODY,
    REFUSAL_SECONDS,
    SECURITY_HEADERS,
    SIGN_IN_PAGE,
    TOKEN_BYTES,
    GuiServer,
    is_loopback,
    launched,
    run,
    static_directory,
)
from ddd.gui.session import Revision, Session

FOREIGN_COOKIES = ('prefs={"lang":"en"}', "arr[0]=1", "user@site=1", "lonely")
"""Cookies other apps on 127.0.0.1 leave in a browser, which sends them to every port."""


@pytest.fixture
def pages(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("stand-in", encoding="utf-8")
    (static / "app.js").write_text("export {};", encoding="utf-8")
    (static / "data.bin").write_bytes(b"\x00")
    (tmp_path / "secret.txt").write_text("not for the page", encoding="utf-8")
    return static


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    write_tree(
        tmp_path / "project",
        {
            "p.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
        },
    )
    return tmp_path / "project" / "p.ddd.json"


def bounded_run(*arguments: Any, **keywords: Any) -> int:
    """``run``, on a thread of its own joined with a timeout: where it starts the analyser, it
    stops by joining that thread without one, and an analysis that never ends fails the test
    rather than hanging the suite."""
    outcome: list[int | BaseException] = []

    def running() -> None:
        try:
            outcome.append(run(*arguments, **keywords))
        except BaseException as error:  # handed to the test's own thread, which raises it
            outcome.append(error)

    thread = threading.Thread(target=running, name="run", daemon=True)
    thread.start()
    thread.join(timeout=10)
    assert not thread.is_alive(), "run did not return"
    (answer,) = outcome
    if isinstance(answer, BaseException):
        raise answer
    return answer


def serving(
    api: Api,
    static: Path,
    *,
    clock: Callable[[], float] = time.monotonic,
    connections: int = MAX_CONNECTIONS,
) -> Iterator[GuiServer]:
    server = GuiServer(api, static, clock=clock, connections=connections)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def server(project_file: Path, pages: Path) -> Iterator[GuiServer]:
    session = Session(project_file.parent)
    session.open(project_file)
    yield from serving(Api(session, project_file, wait_seconds=0.05), pages)


def ask(
    server: GuiServer,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    host: str | None = None,
    origin: str | None = None,
    signed_in: bool = True,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> tuple[http.client.HTTPResponse, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    sent = {"Host": host or f"127.0.0.1:{server.port}"}
    if signed_in:
        sent["Authorization"] = f"Bearer {server.token}"
    if origin is not None:
        sent["Origin"] = origin
    if body is not None:
        sent["Content-Type"] = content_type
    sent.update(headers or {})
    connection.request(method, path, body=body, headers=sent)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


def exchange(
    server: GuiServer, given: object, **keywords: Any
) -> tuple[http.client.HTTPResponse, bytes]:
    """``POST /open`` as the page posts it: from this server's own origin, as json, with no
    credential, since the sign-in is where the page gets one."""
    return ask(
        server,
        "POST",
        "/open",
        body=json.dumps(given).encode("utf-8"),
        origin=f"http://127.0.0.1:{server.port}",
        signed_in=False,
        **keywords,
    )


REFUSED: Final = {"error": "forbidden", "message": _SIGN_IN}
"""What ``POST /open`` answers a secret that signs nothing in."""


def raw_answer(server: GuiServer, sent: bytes) -> tuple[int, bytes]:
    """The status and body ``server`` answers ``sent`` with, over a connection of its own,
    read to its end. For bytes ``http.client`` itself refuses to send - a request line that
    is not well-formed, say - which is exactly what a hostile request is not."""
    with socket.create_connection(("127.0.0.1", server.port), timeout=10) as connection:
        connection.sendall(sent)
        with connection.makefile("rb") as answer:
            data = answer.read()
    head, _, body = data.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), body


def posted(server: GuiServer, length: str, body: bytes = b"") -> bytes:
    """A signed-in ``POST /api/edit`` from this server's own page, as json, carrying ``body``
    under a ``Content-Length`` spelled ``length`` - whatever ``body`` holds - and asking for
    the connection to close after its answer, for :func:`raw_answer` to read to its end."""
    return (
        b"POST /api/edit HTTP/1.1\r\n"
        + f"Host: 127.0.0.1:{server.port}\r\n".encode("ascii")
        + f"Authorization: Bearer {server.token}\r\n".encode("ascii")
        + f"Origin: http://127.0.0.1:{server.port}\r\n".encode("ascii")
        + b"Content-Type: application/json\r\n"
        + f"Content-Length: {length}\r\nConnection: close\r\n\r\n".encode("ascii")
        + body
    )


def answering_session(monkeypatch: pytest.MonkeyPatch, answer: Callable[..., object]) -> None:
    """``GET /api/session`` answered by ``answer`` instead, for one test: its route in the api's
    table replaced by one that differs in nothing else."""
    monkeypatch.setattr(
        api_module,
        "ROUTES",
        tuple(
            dataclasses.replace(route, answer=answer) if route.path == "/api/session" else route
            for route in api_module.ROUTES
        ),
    )


class FakeClock:
    """A clock a test can move without sleeping; ``GuiServer``'s own default is
    ``time.monotonic``."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class Opened:
    """A stand-in for ``webbrowser.open``: records what it is given, and signals once it is.

    A launch now runs its opener off the thread that serves (so a browser that never returns
    cannot hold that up), so a test cannot assume the call already happened just because
    ``run()`` has returned - it waits for this instead.
    """

    def __init__(self) -> None:
        self.addresses: list[str] = []
        self._called = threading.Event()

    def __call__(self, address: str) -> None:
        self.addresses.append(address)
        self._called.set()

    def wait(self, timeout: float = 5) -> str:
        assert self._called.wait(timeout=timeout), "the browser was never opened"
        (address,) = self.addresses
        return address


def code_from(printed_line: str, opened_address: str) -> str:
    """The single-use launch code a launch handed the browser: an address of this server's
    own - the same port as the one the printed line carries, naming ``/open``, its query
    exactly one fresh code - never the long-lived token the printed address carries, not as
    the code and not anywhere else in the address either. Answers the code."""
    printed = urlsplit(printed_line.rsplit(" ", 1)[1])
    opened = urlsplit(opened_address)
    assert (opened.scheme, opened.hostname, opened.port, opened.path) == (
        printed.scheme,
        printed.hostname,
        printed.port,
        "/open",
    )
    token = parse_qs(printed.query)["token"][0]
    assert token not in opened_address
    code = parse_qs(opened.query)["code"][0]
    assert parse_qs(opened.query) == {"code": [code]}
    return code


class TestSigningIn:
    def test_a_code_is_as_strong_as_the_token(self, server) -> None:
        """The ruling's two numbers, pinned by literal: 32 random bytes behind each - the
        strength secrets.token_urlsafe(32) always renders as a 43-character string."""
        assert TOKEN_BYTES == 32
        assert len(server.issue_code()) == 43
        assert len(server.token) == 43

    def test_a_code_expires_60_seconds_after_it_is_issued(self) -> None:
        """Pinned by its literal: the tests of an expired code move their clocks by
        ``CODE_SECONDS`` itself, and would drift along with any change to it."""
        assert CODE_SECONDS == 60

    def test_redeem_code_holds_the_lock_across_the_compare(self, server, monkeypatch) -> None:
        """The read, the compare and the clear are one atomic step: two concurrent
        presentations of the same code cannot both see it still pending."""
        code = server.issue_code()
        locked_during_compare: list[bool] = []
        real_compare_digest = module.hmac.compare_digest

        def recording_compare_digest(a: bytes, b: bytes) -> bool:
            locked_during_compare.append(server._code_lock.locked())
            return real_compare_digest(a, b)

        monkeypatch.setattr(module.hmac, "compare_digest", recording_compare_digest)
        assert server.redeem_code(code) is True
        assert locked_during_compare == [True]

    def test_redeem_code_spends_the_code_before_it_lets_the_lock_go(
        self, server, monkeypatch
    ) -> None:
        """The spend is the single use itself: cleared once the lock was let go, two concurrent
        presentations of the same code could both find it pending and both sign in. What the
        code stands at, as the lock is let go, recorded by a lock that records it."""
        code = server.issue_code()
        lock = server._code_lock
        at_release: list[object] = []

        class Recording:
            def __enter__(self) -> None:
                lock.acquire()

            def __exit__(self, *raised: object) -> None:
                at_release.append(server._code)
                lock.release()

        monkeypatch.setattr(server, "_code_lock", Recording())
        assert server.redeem_code(code) is True
        assert at_release == [None]

    def test_the_api_without_the_token_is_unauthorised(self, server) -> None:
        """Pinned by its literal text: the other tests of this refusal compare its message
        against the imported ``_SIGN_IN``, which would drift along with any rewording of it, or
        read its status alone."""
        response, data = ask(server, "GET", "/api/session", signed_in=False)
        assert (response.status, json.loads(data)) == (
            401,
            {
                "error": "unauthorised",
                "message": "open the address ddd gui printed in its terminal",
            },
        )


class TestTheSignInExchange:
    """``POST /open``: the token, or a launch code, traded for the token the page then keeps
    and sends as ``Authorization: Bearer``."""

    def test_the_token_is_answered_with_itself(self, server) -> None:
        response, data = exchange(server, {"token": server.token})
        assert (response.status, json.loads(data)) == (200, {"token": server.token})
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Set-Cookie") is None

    def test_a_launch_code_is_traded_for_the_token_once(self, server, capsys) -> None:
        code = server.issue_code()
        response, data = exchange(server, {"code": code})
        assert (response.status, json.loads(data)) == (200, {"token": server.token})
        assert capsys.readouterr().err == ""
        again, data = exchange(server, {"code": code})
        assert (again.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == f"{_CODE_REUSED}\n"

    def test_a_code_presented_again_says_why_to_restart(self, server, capsys) -> None:
        """Its winner holds the token itself, which a restart takes from it and the printed
        address does not. Pinned by its literal text: the test above compares against the
        imported ``_CODE_REUSED``, which would drift along with any rewording of it."""
        code = server.issue_code()
        assert exchange(server, {"code": code})[0].status == 200
        exchange(server, {"code": code})
        assert capsys.readouterr().err == (
            "ddd gui: a launch code that already signed a browser in was presented again; if "
            "your browser is not signed in, another process on this computer may have signed "
            "in with it first and now holds the token itself, so restart ddd gui rather than "
            "open the address it printed\n"
        )

    def test_a_wrong_code_is_refused_and_leaves_the_right_one_waiting(self, server, capsys) -> None:
        code = server.issue_code()
        response, data = exchange(server, {"code": "wrong"})
        assert (response.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == ""
        assert exchange(server, {"code": code})[0].status == 200

    def test_the_tokens_own_value_is_no_code(self, server) -> None:
        server.issue_code()
        response, data = exchange(server, {"code": server.token})
        assert (response.status, json.loads(data)) == (403, REFUSED)

    def test_a_code_to_a_server_that_issued_none_is_refused_without_a_word(
        self, server, capsys
    ) -> None:
        response, data = exchange(server, {"code": "anything"})
        assert (response.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == ""

    def test_an_expired_code_is_refused_without_a_word(self, project_file, pages, capsys) -> None:
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS
            response, data = exchange(started, {"code": code})
            assert (response.status, json.loads(data)) == (403, REFUSED)
            assert capsys.readouterr().err == ""

    def test_a_code_still_signs_in_a_moment_before_its_60_seconds(
        self, project_file, pages
    ) -> None:
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS - 1
            assert exchange(started, {"code": code})[0].status == 200

    def test_a_wrong_token_is_refused(self, server) -> None:
        response, data = exchange(server, {"token": "wrong"})
        assert (response.status, json.loads(data)) == (403, REFUSED)

    @pytest.mark.parametrize(
        "given",
        [
            {},
            {"code": "a", "token": "b"},
            {"code": 1},
            {"other": "x"},
            ["code"],
            [["code", "x"]],
            "code",
            None,
        ],
        ids=[
            "empty",
            "both",
            "a-number",
            "a-stray-key",
            "a-list",
            "a-pair-in-a-list",
            "a-string",
            "null",
        ],
    )
    def test_anything_but_one_secret_is_refused(self, server, given) -> None:
        response, data = exchange(server, given)
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )

    def test_the_refusal_says_what_open_takes(self, server) -> None:
        """Pinned by its literal text: comparing against the imported ``_OPEN_TAKES`` instead
        would drift along with any rewording of it, and catch nothing."""
        _, data = exchange(server, {})
        assert json.loads(data) == {
            "error": "bad-request",
            "message": "/open takes json naming one of code and token, and nothing else",
        }

    @pytest.mark.parametrize(
        "body",
        [b"code=x", b"\xc3\x28", b"[" * 512 + b"]" * 512],
        ids=["a-form", "not-utf-8", "nested-within-the-limit"],
    )
    def test_a_body_that_is_no_json_object_is_refused_not_failed(self, server, body) -> None:
        """The parse refusal, pinned on a body within ``OPEN_BODY``: 512 nested arrays are 1024
        bytes exactly, so they reach ``_secret_of``, parse to a list rather than an object, and
        are refused 400. A body deep enough to trouble a parser is refused on its size first,
        before any parser runs - that case is ``test_a_body_too_deep_to_parse_meets_the_cap``."""
        response, data = ask(
            server,
            "POST",
            "/open",
            body=body,
            origin=f"http://127.0.0.1:{server.port}",
            signed_in=False,
        )
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )

    @pytest.mark.parametrize(
        ("kind", "signed_in_once"),
        [("token", False), ("code", False), ("code", True)],
        ids=["the-token", "a-code-while-one-is-pending", "a-code-once-one-signed-in"],
    )
    def test_a_value_utf_8_cannot_encode_is_refused_not_failed(
        self, server, kind, signed_in_once, capsys
    ) -> None:
        """A lone surrogate, which json spells as an escape and ``json.loads`` reads back as text
        that UTF-8 cannot encode. Comparing it encoded it, which raised: a 500, and a traceback
        on the terminal. A code is issued first, as in a real run, since with none pending or
        redeemed a code is refused before anything encodes it."""
        code = server.issue_code()
        if signed_in_once:
            assert exchange(server, {"code": code})[0].status == 200
        response, data = exchange(server, {kind: chr(0xD800)})
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )
        assert capsys.readouterr().err == ""

    def test_a_name_given_twice_counts_twice(self, server) -> None:
        """Read into a dict, the object kept the last of a repeated name and was exactly one
        secret, so this one signed in. Sent as bytes: ``json.dumps`` cannot repeat a name."""
        response, data = ask(
            server,
            "POST",
            "/open",
            body=f'{{"token": "x", "token": "{server.token}"}}'.encode("ascii"),
            origin=f"http://127.0.0.1:{server.port}",
            signed_in=False,
        )
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )

    def test_another_page_is_refused_at_the_gate(self, server) -> None:
        """Refused as the gate refuses every path outside the API, with the sign-in page: the
        gate is as it was, and ``/open`` is no ``/api/`` path."""
        response, data = exchange(
            server, {"token": server.token}, headers={"Sec-Fetch-Site": "same-site"}
        )
        assert (response.status, data) == (403, SIGN_IN_PAGE)
        assert response.getheader("Content-Type") == "text/html; charset=utf-8"

    @pytest.mark.parametrize(
        ("origin", "kind"),
        [(None, "application/json"), ("own", "text/plain")],
        ids=["no-origin", "not-json"],
    )
    def test_it_is_a_post_like_any_other(self, server, origin, kind) -> None:
        response, data = ask(
            server,
            "POST",
            "/open",
            body=json.dumps({"token": server.token}).encode("utf-8"),
            origin=None if origin is None else f"http://127.0.0.1:{server.port}",
            content_type=kind,
            signed_in=False,
        )
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _FORBIDDEN},
        )

    def test_a_body_past_the_limit_is_refused_before_it_is_read(self, server) -> None:
        """At most ``MAX_BODY``, as every ``POST`` here: refused on its length, and its
        connection closed, since the body is left unread on it."""
        response, data = exchange(
            server, {"token": server.token}, headers={"Content-Length": str(MAX_BODY + 1)}
        )
        assert (response.status, json.loads(data)) == (
            413,
            {"error": "too-large", "message": f"a request body is at most {MAX_BODY} bytes"},
        )
        assert response.getheader("Connection") == "close"

    def _open(self, server, body: bytes) -> tuple[http.client.HTTPResponse, bytes]:
        """``POST /open`` from this server's own page, as json, carrying ``body`` as it is -
        not json-encoded the way :func:`exchange` would, since these bodies are raw."""
        return ask(
            server,
            "POST",
            "/open",
            body=body,
            origin=f"http://127.0.0.1:{server.port}",
            signed_in=False,
        )

    def test_a_body_at_the_open_limit_is_read(self, server) -> None:
        """``OPEN_BODY`` bytes exactly - a valid sign-in padded with the spaces json ignores -
        is read and answered 200: the cap is the boundary, not below it."""
        body = json.dumps({"token": server.token}).encode("utf-8")
        body += b" " * (OPEN_BODY - len(body))
        assert len(body) == OPEN_BODY
        response, data = self._open(server, body)
        assert (response.status, json.loads(data)) == (200, {"token": server.token})

    def test_a_body_past_the_open_limit_is_refused_before_it_is_parsed(self, server) -> None:
        """One byte past the cap, still a valid sign-in but for its length, is refused 413 - so
        the token in it, which would otherwise sign in, never gets parsed."""
        body = json.dumps({"token": server.token}).encode("utf-8")
        body += b" " * (OPEN_BODY + 1 - len(body))
        assert len(body) == OPEN_BODY + 1
        response, data = self._open(server, body)
        assert (response.status, json.loads(data)) == (
            413,
            {"error": "too-large", "message": _OPEN_TOO_LARGE},
        )

    def test_a_body_too_deep_to_parse_meets_the_cap(self, server) -> None:
        """A body nested far past any json parser's depth is refused on its size, before
        ``_secret_of`` hands it to one: a C-stack overflow in the parser, which would end the
        whole process rather than fail one request, cannot be reached here on any platform."""
        response, data = self._open(server, b"[" * 100_000 + b"]" * 100_000)
        assert (response.status, json.loads(data)) == (
            413,
            {"error": "too-large", "message": _OPEN_TOO_LARGE},
        )

    def test_a_parser_out_of_its_depth_is_a_malformed_body(self, monkeypatch) -> None:
        """``_secret_of``'s ``RecursionError`` catch, held although no body within ``OPEN_BODY``
        nests deep enough to reach it on the pythons measured: the parser is stubbed to raise
        what one out of its depth raises, which is no ``ValueError``."""

        def out_of_depth(*_args: object, **_kwargs: object) -> object:
            raise RecursionError("maximum recursion depth exceeded while decoding a JSON array")

        monkeypatch.setattr(module.json, "loads", out_of_depth)
        assert module._secret_of(b'{"token": "x"}') is None

    def test_the_open_body_refusal_says_what_it_takes(self, server) -> None:
        """Pinned by its literal text, ``OPEN_BODY``'s value among it: the tests above compare
        against the imported ``_OPEN_TOO_LARGE``, which would drift along with any rewording of
        it or any change to the limit, and catch neither."""
        _, data = self._open(server, b"x" * (OPEN_BODY + 1))
        assert json.loads(data) == {
            "error": "too-large",
            "message": "/open takes a body of at most 1024 bytes",
        }


class TestTheBearerHeader:
    """The API takes the token as ``Authorization: Bearer``: the scheme in any case, as HTTP
    has it, then one space, then the token, compared in constant time."""

    @pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
    def test_the_token_as_a_bearer_signs_a_request_in(self, server, scheme) -> None:
        response, _ = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={"Authorization": f"{scheme} {server.token}"},
        )
        assert response.status == 200

    @pytest.mark.parametrize(
        "spelled",
        ["Bearer wrong", "Bearer  {token}", "Basic {token}", "{token}", "Bearer"],
        ids=["a-wrong-token", "two-spaces", "another-scheme", "no-scheme", "no-token"],
    )
    def test_anything_else_is_unauthorised(self, server, spelled) -> None:
        response, data = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={"Authorization": spelled.format(token=server.token)},
        )
        assert (response.status, json.loads(data)) == (
            401,
            {"error": "unauthorised", "message": _SIGN_IN},
        )

    def test_no_cross_origin_preflight_is_answered(self, server) -> None:
        """A page on another origin can send ``Authorization`` only past a CORS preflight,
        which this server answers with nothing a browser accepts."""
        response, _ = ask(
            server,
            "OPTIONS",
            "/api/session",
            signed_in=False,
            headers={
                "Origin": "http://127.0.0.1:9",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status == 501
        assert [
            n for n, _ in response.getheaders() if n.lower().startswith("access-control-")
        ] == []


class TestACookie:
    """A cookie is no credential: a browser sends every cookie of 127.0.0.1 to every port of
    it, and so to every other server there (part 18b)."""

    @pytest.mark.parametrize(
        "cookie",
        ["ddd-gui-{port}={token}", "ddd-gui={token}", "{foreign}; ddd-gui-{port}={token}"],
        ids=["this-servers-old-name", "the-name-before-ports", "beside-others"],
    )
    def test_a_cookie_holding_the_token_is_no_credential(self, server, cookie) -> None:
        response, data = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={
                "Cookie": cookie.format(
                    port=server.port, token=server.token, foreign='prefs={"lang":"en"}'
                )
            },
        )
        assert (response.status, json.loads(data)) == (
            401,
            {"error": "unauthorised", "message": _SIGN_IN},
        )

    def test_cookies_beside_the_header_are_passed_over(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", headers={"Cookie": "; ".join(FOREIGN_COOKIES)}
        )
        assert response.status == 200


class TestTheAddressPrinted:
    """``GET /open`` answers the page itself, which signs itself in, and checks and spends
    nothing: a browser's prefetch of the launch address spends no code."""

    @pytest.mark.parametrize(
        "query",
        ["code={code}", "token={token}", "code=wrong", ""],
        ids=["the-launch", "the-printed-address", "a-wrong-code", "nothing"],
    )
    def test_open_answers_the_page_and_spends_nothing(self, server, pages, query) -> None:
        code = server.issue_code()
        response, data = ask(
            server,
            "GET",
            "/open?" + query.format(code=code, token=server.token),
            signed_in=False,
        )
        assert response.status == 200
        assert data == (pages / "index.html").read_bytes()
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Set-Cookie") is None
        assert exchange(server, {"code": code})[0].status == 200

    @pytest.mark.parametrize("path", ["/", "/project", "/app.js"])
    def test_a_page_needs_no_credential(self, server, pages, path) -> None:
        response, _ = ask(server, "GET", path, signed_in=False)
        assert response.status == 200

    def test_no_answer_sets_a_cookie(self, server) -> None:
        answers = [
            ask(server, "GET", f"/open?token={server.token}", signed_in=False)[0],
            exchange(server, {"token": server.token})[0],
            ask(server, "GET", "/project", signed_in=False)[0],
            ask(server, "GET", "/api/session")[0],
        ]
        assert [answer.getheader("Set-Cookie") for answer in answers] == [None] * 4


class TestWhoMayAsk:
    def test_a_foreign_host_is_refused(self, server) -> None:
        response, _ = ask(server, "GET", "/api/session", host=f"evil.example:{server.port}")
        assert response.status == 421

    def test_localhost_is_this_server_too(self, server) -> None:
        response, _ = ask(server, "GET", "/api/session", host=f"localhost:{server.port}")
        assert response.status == 200

    @pytest.mark.parametrize("site", ["same-site", "cross-site"])
    @pytest.mark.parametrize("path", ["/api/session", "/api/compare?baseline=x"])
    def test_an_api_request_from_another_page_is_refused(self, server, site, path) -> None:
        """A page served from another port of 127.0.0.1 is the same site to a browser, which
        sent it this server's SameSite=Strict cookie while the token was one: probed against
        a1da6ce, its GET of /api/compare ran the comparison, plugins and all. Such a page has
        no token any more, and the gate refuses it even carrying the token."""
        response, data = ask(server, "GET", path, headers={"Sec-Fetch-Site": site})
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _ELSEWHERE},
        )

    def test_the_elsewhere_refusal_names_the_address_printed(self, server) -> None:
        """Pinned by its literal text: comparing against the imported ``_ELSEWHERE`` constant
        instead would drift along with any mutation to its wording, and catch nothing."""
        _, data = ask(server, "GET", "/api/session", headers={"Sec-Fetch-Site": "same-site"})
        assert json.loads(data) == {
            "error": "forbidden",
            "message": "ddd gui answers its own page alone, opened from the address it printed",
        }

    def test_a_page_requested_from_another_page_says_where_to_sign_in(self, server) -> None:
        response, data = ask(server, "GET", "/project", headers={"Sec-Fetch-Site": "same-site"})
        assert (response.status, data) == (403, SIGN_IN_PAGE)
        assert response.getheader("Content-Type") == "text/html; charset=utf-8"

    def test_the_sign_in_page_names_the_address_printed(self, server) -> None:
        """Pinned by its literal text: the tests that meet it compare against the imported
        ``SIGN_IN_PAGE``, which would drift along with any rewording of it."""
        _, data = ask(server, "GET", "/project", headers={"Sec-Fetch-Site": "same-site"})
        assert data == (
            b'<!doctype html><html lang="en"><meta charset="utf-8"><title>ddd gui</title>'
            b"<p>Open the address <code>ddd gui</code> printed in its terminal.</p></html>"
        )

    @pytest.mark.parametrize("site", [None, "same-origin", "none"])
    @pytest.mark.parametrize("origin", ["http://127.0.0.1:1", "http://evil.example", "null"])
    def test_a_get_carrying_another_origin_is_refused(self, server, origin, site) -> None:
        headers = None if site is None else {"Sec-Fetch-Site": site}
        response, data = ask(server, "GET", "/api/session", origin=origin, headers=headers)
        assert (response.status, json.loads(data)["message"]) == (403, _ELSEWHERE)

    @pytest.mark.parametrize("site", ["same-origin", "none"])
    def test_this_page_and_an_address_typed_are_answered(self, server, site) -> None:
        response, _ = ask(server, "GET", "/api/session", headers={"Sec-Fetch-Site": site})
        assert response.status == 200

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
    def test_this_servers_own_origin_is_answered(self, server, host) -> None:
        response, _ = ask(server, "GET", "/api/session", origin=f"http://{host}:{server.port}")
        assert response.status == 200

    def test_another_page_is_refused_before_the_token_is_read(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", signed_in=False, headers={"Sec-Fetch-Site": "same-site"}
        )
        assert response.status == 403

    def test_a_post_from_another_page_is_refused_before_the_token_is_read(self, server) -> None:
        """The POST sibling of test_another_page_is_refused_before_the_token_is_read: the gate
        runs before ``_signed_in`` and before the POST rule alike, so a POST marked same-site
        is refused by the gate's own sentence, not by ``_FORBIDDEN``, without ever reaching the
        token."""
        response, data = ask(
            server,
            "POST",
            "/api/open",
            body=b"{}",
            signed_in=False,
            headers={"Sec-Fetch-Site": "same-site"},
        )
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _ELSEWHERE},
        )

    def test_signing_in_is_answered_wherever_the_address_was_opened_from(self, server) -> None:
        """The address is answered wherever it was opened from: ``GET /open`` answers the
        page, which signs itself in, and reads neither ``Sec-Fetch-Site`` nor ``Origin``.
        ``cross-site`` is kept as the value a browser marks least trustworthy; a real launch
        arrives marked ``none`` instead (a navigation the opener started), which is answered
        just the same."""
        response, _ = ask(
            server,
            "GET",
            f"/open?token={server.token}",
            signed_in=False,
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert response.status == 200

    def test_a_launch_code_is_answered_wherever_it_was_presented_from(self, server) -> None:
        """The sibling of test_signing_in_is_answered_wherever_the_address_was_opened_from, for
        a single-use launch code rather than the long-lived token: presented cross-site too,
        since ``_route`` answers ``GET /open`` before the gate is ever reached, for a code
        exactly as for the token - neither header is read there either."""
        response, _ = ask(
            server,
            "GET",
            f"/open?code={server.issue_code()}",
            signed_in=False,
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert response.status == 200

    @pytest.mark.parametrize(
        ("origin", "content_type", "message"),
        [
            # No Origin and no Sec-Fetch-Site: the gate lets it through, same as a script or
            # curl would; the POST rule (step 5) is what refuses it, with _FORBIDDEN.
            (None, "application/json", _FORBIDDEN),
            # A foreign Origin, no Sec-Fetch-Site: the gate (step 3) catches it first, with
            # _ELSEWHERE - before the POST rule is ever reached.
            ("http://evil.example", "application/json", _ELSEWHERE),
            ("http://127.0.0.1:1", "application/json", _ELSEWHERE),
            # This server's own Origin, but the wrong content type: the gate lets it through,
            # and the POST rule (step 5) refuses it, with _FORBIDDEN.
            ("OWN", "text/plain", _FORBIDDEN),
        ],
    )
    def test_a_change_from_anywhere_but_this_page_is_forbidden(
        self, server, origin, content_type, message
    ) -> None:
        own = f"http://127.0.0.1:{server.port}"
        response, data = ask(
            server,
            "POST",
            "/api/open",
            body=b"{}",
            origin=own if origin == "OWN" else origin,
            content_type=content_type,
        )
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": message},
        )

    def test_a_change_from_this_page_is_answered(self, server) -> None:
        response, _ = ask(
            server,
            "POST",
            "/api/open",
            body=b"{}",
            origin=f"http://localhost:{server.port}",
            content_type="application/json; charset=utf-8",
        )
        assert response.status == 400  # reached the API, which wants a path

    def test_a_body_larger_than_allowed_is_refused(self, server) -> None:
        response, _ = ask(
            server,
            "POST",
            "/api/edit",
            body=b"{}",
            origin=f"http://127.0.0.1:{server.port}",
            headers={"Content-Length": str(MAX_BODY + 1)},
        )
        assert response.status == 413

    def test_a_content_length_of_4301_nines_is_too_large_not_500(self, server, capsys) -> None:
        """``int()`` itself refuses a string of more than 4,300 digit characters, whatever
        they are, raising the same ``ValueError`` the hostile walk pins over a query's own
        numbers (``MAX_DIGITS``, ``queries.py``), which ``_body`` read straight into ``int()``
        unguarded. No body is sent: 4,301 nines is refused before ``_body`` reads one."""
        status, body = raw_answer(server, posted(server, "9" * 4301))
        assert (status, json.loads(body)) == (
            413,
            {"error": "too-large", "message": f"a request body is at most {MAX_BODY} bytes"},
        )
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize(
        ("length", "body"), [("0" * 4301, b""), ("00000002", b"{}")], ids=["zeros", "00000002"]
    )
    def test_leading_zeros_aside_a_length_is_read_as_its_value(
        self, server, length, body, capsys
    ) -> None:
        """Zeros alone are a length of 0, however many there are, and zeros before a length
        are no part of it: each is answered exactly as the same request spelling its length
        plainly. ``00000002`` converted before ``_body`` stripped anything, so it pins that a
        length is not refused for its digits alone, eight of them where ``MAX_BODY`` has
        seven."""
        plainly = raw_answer(server, posted(server, str(len(body)), body))
        assert raw_answer(server, posted(server, length, body)) == plainly
        assert capsys.readouterr().err == ""

    def test_a_length_that_is_not_one_is_a_bad_request(self, server) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        connection.putrequest("POST", "/api/edit", skip_host=True)
        connection.putheader("Host", f"127.0.0.1:{server.port}")
        connection.putheader("Authorization", f"Bearer {server.token}")
        connection.putheader("Origin", f"http://127.0.0.1:{server.port}")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "ten")
        connection.endheaders()
        assert connection.getresponse().status == 400
        connection.close()


class TestWhatIsServed:
    def test_every_response_carries_the_security_headers(self, server) -> None:
        for method, path in (("GET", "/"), ("GET", "/api/session"), ("GET", "/api/nothing")):
            response, _ = ask(server, method, path)
            policy = response.getheader("Content-Security-Policy")
            assert policy is not None and "frame-ancestors 'none'" in policy
            assert response.getheader("X-Content-Type-Options") == "nosniff"
            assert response.getheader("Referrer-Policy") == "no-referrer"

    def test_the_api_is_never_cached_and_the_pages_are_not_told_so(self, server) -> None:
        assert ask(server, "GET", "/api/session")[0].getheader("Cache-Control") == "no-store"
        assert ask(server, "GET", "/")[0].getheader("Cache-Control") is None

    @pytest.mark.parametrize(
        ("path", "kind", "text"),
        [
            ("/", "text/html; charset=utf-8", b"stand-in"),
            ("/app.js", "text/javascript; charset=utf-8", b"export {};"),
            ("/data.bin", "application/octet-stream", b"\x00"),
            ("/project", "text/html; charset=utf-8", b"stand-in"),
            ("/../secret.txt", "text/html; charset=utf-8", b"stand-in"),
            ("/%2e%2e/secret.txt", "text/html; charset=utf-8", b"stand-in"),
        ],
    )
    def test_a_page_is_served_with_its_own_content_type_or_the_index(
        self, server, path, kind, text
    ) -> None:
        response, data = ask(server, "GET", path)
        assert (response.status, response.getheader("Content-Type"), data) == (200, kind, text)

    def test_a_page_is_not_posted_to(self, server) -> None:
        response, _ = ask(
            server, "POST", "/project", body=b"{}", origin=f"http://127.0.0.1:{server.port}"
        )
        assert response.status == 405

    def test_an_edit_goes_all_the_way_to_the_file(self, server, project_file) -> None:
        target = project_file.parent / "a.ddd.json"
        before = target.read_bytes()
        edit = {
            "changes": [
                {
                    "file": target.as_posix(),
                    "fingerprint": fingerprint(before),
                    "operations": [
                        {
                            "op": "set",
                            "pointer": "component.interface[0].definition.unit",
                            "raw": '"Hz"',
                        }
                    ],
                }
            ],
            "label": "the unit of Speed",
        }
        response, data = ask(
            server,
            "POST",
            "/api/edit",
            body=json.dumps(edit).encode("utf-8"),
            origin=f"http://127.0.0.1:{server.port}",
        )
        assert response.status == 200, data
        assert target.read_bytes() == before.replace(b'"unit": "rpm"', b'"unit": "Hz"')

    def test_a_request_that_fails_unexpectedly_is_answered_and_its_traceback_printed(
        self, server, monkeypatch, capsys
    ) -> None:
        """Answered as json like every other error. The connection used to drop instead, and the
        page then said the server was not answering - or, waiting for a revision, had stopped -
        about a server that was running."""

        def failing(api: Api, query: object, body: object) -> None:
            raise RuntimeError("a defect")

        answering_session(monkeypatch, failing)
        response, data = ask(server, "GET", "/api/session")
        assert response.status == 500
        assert response.getheader("Cache-Control") == "no-store"
        assert json.loads(data) == {
            "error": "internal",
            "message": "ddd gui failed on this request; the terminal it runs in shows why",
        }
        printed = capsys.readouterr().err
        assert "GET '/api/session'" in printed
        assert "RuntimeError: a defect" in printed

    def test_a_failure_is_printed_with_its_target_escaped(
        self, server, monkeypatch, capsys
    ) -> None:
        """``self.path`` is anyone's text, and an escape sequence in it printed raw would
        reach the terminal the page tells the reader to watch. Reaching this honestly, with
        an ordinary route still dispatched and still made to fail, needs something a route
        match never sees: a fragment, which ``urlsplit`` carries past the dispatcher unread,
        yet which ``self.path`` - the whole target, unsplit - still holds when this prints
        it."""

        def failing(api: Api, query: object, body: object) -> None:
            raise RuntimeError("a defect")

        answering_session(monkeypatch, failing)
        path = "/api/session#\x1b"
        sent = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{server.port}\r\n"
            f"Authorization: Bearer {server.token}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        status, _ = raw_answer(server, sent)
        assert status == 500
        printed = capsys.readouterr().err
        assert f"GET {path!r}" in printed
        assert "\x1b" not in printed

    def test_a_failure_is_printed_with_its_traceback_escaped(
        self, server, monkeypatch, capsys
    ) -> None:
        """An exception's own message is printed as it stands, and one that carried request
        text into it through ``str()`` - none does today, each formats it with ``%r`` - would
        put an escape sequence on the terminal raw: the title's, the screen cleared, the text
        that follows turned around. Every character a terminal does not print as itself is
        written as its escape instead, but the line breaks a traceback is made of."""

        def failing(api: Api, query: object, body: object) -> None:
            raise RuntimeError("a defect \x1b]0;owned\x07 \x1b[2J\u202e\r\tend")

        answering_session(monkeypatch, failing)
        response, _ = ask(server, "GET", "/api/session")
        assert response.status == 500
        printed = capsys.readouterr().err
        assert "RuntimeError: a defect \\x1b]0;owned\\x07 \\x1b[2J\\u202e\\r\\tend\n" in printed
        assert [c for c in printed if not (c == "\n" or c.isprintable())] == []

    def test_an_answer_json_cannot_spell_is_a_failure_rather_than_a_body_no_page_reads(
        self, server, monkeypatch, capsys
    ) -> None:
        """Python writes ``NaN`` by default, which no browser's parser reads."""

        def slipped(api: Api, query: object, body: object) -> Reply:
            return Reply(200, {"limit": float("nan")})

        answering_session(monkeypatch, slipped)
        response, data = ask(server, "GET", "/api/session")
        assert (response.status, json.loads(data)["error"]) == (500, "internal")
        assert "ValueError: Out of range float values are not JSON compliant" in (
            capsys.readouterr().err
        )

    def test_a_page_that_goes_away_while_it_is_answered_is_let_go(
        self, server, monkeypatch, capsys
    ) -> None:
        def gone(api: Api, query: object, body: object) -> None:
            raise ConnectionAbortedError("the tab was closed")

        answering_session(monkeypatch, gone)
        with pytest.raises(http.client.RemoteDisconnected):
            ask(server, "GET", "/api/session")
        assert capsys.readouterr().err == ""

    def test_a_page_that_stops_reading_mid_answer_is_let_go_too(
        self, server, monkeypatch, capsys
    ) -> None:
        """A connection left open is given up on rather than held, so the socket carries a
        deadline now - and a page that stopped reading trips it the way a closed tab trips the
        one above. Neither is a defect of this server's, and neither is printed."""

        def stalled(api: Api, query: object, body: object) -> None:
            raise TimeoutError("the page stopped reading")

        answering_session(monkeypatch, stalled)
        with pytest.raises(http.client.RemoteDisconnected):
            ask(server, "GET", "/api/session")
        assert capsys.readouterr().err == ""

    def test_a_page_that_went_away_mid_answer_is_not_reported(self, server, capsys) -> None:
        try:
            raise ConnectionResetError("the tab was closed")
        except ConnectionResetError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""

    def test_a_page_that_stopped_reading_is_not_reported_either(self, server, capsys) -> None:
        try:
            raise TimeoutError("the page stopped reading")
        except TimeoutError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""

    def test_any_other_failure_of_a_request_is_reported(self, server, capsys) -> None:
        try:
            raise ValueError("a defect")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert "ValueError: a defect" in capsys.readouterr().err

    def test_the_installed_pages_are_looked_for_beside_the_package(self) -> None:
        assert static_directory() == Path(ddd.__file__).parent / "gui" / "static"


INDEX: Final = (200, "text/html; charset=utf-8", b"stand-in")
"""The ``pages`` fixture's ``index.html``, as it is answered: what a path naming no file of the
pages is served."""


def served(server: GuiServer, path: str) -> tuple[int, str | None, bytes]:
    """What a signed-in ``GET`` of ``path`` is answered: its status, its type and its body."""
    response, data = ask(server, "GET", path)
    return response.status, response.getheader("Content-Type"), data


def looked_up(monkeypatch: pytest.MonkeyPatch, links: Collection[Path] = ()) -> list[str]:
    """Every path ``ddd.gui.server`` asks ``os.path`` about from here on, in the order asked:
    the module's ``os`` swapped for one whose ``path`` records each question's path before
    answering it. That module's questions alone - anything else in the process that asks the
    file system something is not what these tests are about - and only the four ``_page``
    asks: a fifth fails the request, rather than going unrecorded.

    Each of ``links`` is answered a symbolic link, whatever it is on disk: a link to a file,
    which an ordinary account cannot make on Windows."""
    asked: list[str] = []
    linked = {os.fspath(link) for link in links}

    def recording(question: Callable[[Any], bool]) -> Callable[[Any], bool]:
        def recorded(path: Any) -> bool:
            asked.append(os.fspath(path))
            return question(path)

        return recorded

    answers = {name: getattr(os.path, name) for name in ("isdir", "isfile", "isjunction", "islink")}
    on_disk = answers["islink"]

    def islink(path: Any) -> bool:
        return os.fspath(path) in linked or on_disk(path)

    answers["islink"] = islink
    questions = {name: recording(answer) for name, answer in answers.items()}
    path = types.SimpleNamespace(**questions)
    monkeypatch.setattr(module, "os", types.SimpleNamespace(path=path))
    return asked


class TestAPagePath:
    """A page path is read as plain names under the pages, and nothing it names is resolved.

    It used to be resolved, then statted, and each step had a way to fail, answered 500 with a
    traceback: on POSIX a NUL made ``Path.resolve()`` raise ``ValueError``; on 3.12 and 3.13 a
    name over 255 bytes made ``Path.is_file()`` raise ``OSError``; on 3.12 a loop of links
    made ``resolve()`` raise ``RuntimeError``, and a long chain of links ``RecursionError``.
    On Windows, resolving opened a network or device spelling before anything checked where
    it led. Every path here that names no file is answered the index, as any unknown path is,
    with nothing printed."""

    @pytest.fixture
    def assets(self, pages: Path) -> Path:
        """A directory of the pages, as the compiled pages' ``assets`` is, holding a script."""
        (pages / "assets").mkdir()
        (pages / "assets" / "index.js").write_text("export {};", encoding="utf-8")
        return pages / "assets"

    def test_a_file_nested_in_the_pages_is_served_with_its_own_type(self, server, assets) -> None:
        assert served(server, "/assets/index.js") == (
            200,
            "text/javascript; charset=utf-8",
            b"export {};",
        )

    @pytest.mark.parametrize(
        "path",
        [
            "/%00",
            "/a%00b.js",
            "/../secret.txt",
            "/%2e%2e/secret.txt",
            "/./app.js",
            "/%5C%5Chost%5Cshare%5Cx",
            "/%5C%5C.%5Cpipe%5Cname",
            "/C:%5Cx",
            "/C:x",
        ],
    )
    def test_a_name_that_is_not_plain_names_no_file_and_is_never_looked_up(
        self, server, path, monkeypatch, capsys
    ) -> None:
        """A NUL, a dot segment, a backslash or a colon - the last two spell a network path, a
        device or a drive on Windows - makes the path name no file before anything asks the
        file system about it, even where the file it would name is there (``app.js``,
        ``secret.txt``)."""
        asked = looked_up(monkeypatch)
        assert served(server, path) == INDEX
        assert asked == []
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize(
        "path", ["/" + "a" * 300, "/assets/", "/app.js/", "/assets//index.js", "/app.js/x"]
    )
    def test_a_path_with_no_file_of_its_own_is_answered_the_index(
        self, server, assets, path, capsys
    ) -> None:
        """A name too long for a file system to hold; an empty one, after a trailing slash -
        whether a directory or a file comes before it - or between two slashes, though
        ``assets/index.js`` is there; and a name under a file."""
        assert served(server, path) == INDEX
        assert capsys.readouterr().err == ""

    def test_a_loop_of_links_beside_the_pages_is_answered_the_index(
        self, server, pages, capsys
    ) -> None:
        """A browser takes ``..`` out of a path; a client of the token holder's own may send it
        as it is, as ``http.client`` does here."""
        looped(pages.parent / "loop", pages.parent / "pool")
        assert served(server, "/../loop") == INDEX
        assert capsys.readouterr().err == ""

    def test_a_loop_of_links_inside_the_pages_is_answered_the_index(
        self, server, pages, capsys
    ) -> None:
        looped(pages / "loop", pages / "pool")
        assert served(server, "/loop") == INDEX
        assert capsys.readouterr().err == ""

    def test_a_link_inside_the_pages_to_a_directory_outside_them_is_never_followed(
        self, server, pages, capsys
    ) -> None:
        """The confinement spec section 2 keeps, which ``resolve()`` and ``is_relative_to``
        gave before: a file outside the pages is never served, here ``secret.txt``, reached
        through a link inside them. A link to a directory, which is a junction on Windows: a
        link to a file needs a privilege there that an ordinary account does not hold."""
        directory_link(pages / "outside", pages.parent)
        assert served(server, "/outside/secret.txt") == INDEX
        assert capsys.readouterr().err == ""

    def test_a_last_name_that_is_a_link_is_not_served(
        self, server, pages, monkeypatch, capsys
    ) -> None:
        """The link check is made of the name a path ends in, as well as of each name it steps
        into: a link to a file outside the pages is that last name. ``app.js``, the pages' own
        script, answered a link by ``looked_up`` - a link to a file needs a privilege on Windows
        that an ordinary account does not hold - is not served, where it otherwise is."""
        looked_up(monkeypatch, links=[pages / "app.js"])
        assert served(server, "/app.js") == INDEX
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize(
        "path",
        ["/COM1", "/nul.js", "/con", "/Lpt9.txt", "/aux.", "/assets/CON", "/CONIN$", "/conout$.js"],
    )
    def test_a_name_windows_keeps_for_a_device_names_no_file_on_any_system(
        self, server, pages, assets, path, monkeypatch, capsys
    ) -> None:
        """Windows opens a device for such a name, in any directory, whatever its extension or
        case: ``COM1`` a serial port, ``NUL`` the null device, ``CONIN$`` the console's own
        input. It is never looked up, on any system; and where it can be an ordinary file, on
        any system but Windows, that file is not served either."""
        if sys.platform != "win32":
            (pages / path[1:]).write_text("a device, on Windows", encoding="utf-8")
        asked = looked_up(monkeypatch)
        assert served(server, path) == INDEX
        assert set(asked) <= {str(pages), str(pages / "assets")}
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize(
        "device",
        [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM0",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "COM¹",
            "COM²",
            "COM³",
            "LPT0",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
            "LPT¹",
            "LPT²",
            "LPT³",
            "CONIN$",
            "CONOUT$",
        ],
    )
    def test_every_name_windows_keeps_for_a_device_is_one_however_it_is_spelled(
        self, device
    ) -> None:
        """In any case, with any extension, with the spaces or dots Windows takes off the end
        of a name, and with a colon after it, which Windows cuts a device's name at as well."""
        spellings = [
            device,
            device.lower(),
            device.title(),
            f"{device}.txt",
            f"{device.lower()}.tar.gz",
            f"{device}.",
            f"{device} ",
            f"{device} .js",
            f"{device}:",
            f"{device.lower()}:stream",
        ]
        assert {device_named(name) for name in spellings} == {device}

    @pytest.mark.parametrize(
        "name",
        [
            "console",
            "com10",
            "COM",
            "lpt",
            "nul_",
            "xaux",
            "aux-1.js",
            ".con",
            "COM⁴",
            "app.js",
            "CONIN",
            "conout",
            "CONIN$x",
        ],
    )
    def test_a_name_merely_like_one_is_none(self, name) -> None:
        assert device_named(name) is None

    def test_a_path_is_looked_up_no_deeper_than_the_pages_go(
        self, server, monkeypatch, capsys
    ) -> None:
        """A request line of 65,536 bytes holds up to 32,760 names. Asked about one after
        another, each a longer path than the last, that many took forty seconds on the
        development PC; but a name past one that is not a directory names no file, and is
        never asked about."""
        asked = looked_up(monkeypatch)
        assert served(server, "/" + "a/" * 30_000 + "a") == INDEX
        assert set(asked) == {str(server.static), str(server.static / "a")}
        assert capsys.readouterr().err == ""


class TestAMalformedAbsoluteFormTarget:
    """The absolute form of a target names its host before its path - ``http://host/path`` -
    and a malformed one, a bracket opened for an IPv6 address and never closed, makes
    ``urlsplit`` itself raise. That used to happen after the Host check, but before the gate
    ever read where the request claims to come from, and before anything answered it:
    ``_answer``'s catch-all split the same text again to print it, raised the same way, and
    socketserver printed a traceback and closed the connection with nothing written - no
    token needed, since the gate and the token's check are both later than this."""

    @pytest.mark.parametrize(
        "line",
        [
            b"GET http://[/ HTTP/1.1",
            b"GET http://[/api/session HTTP/1.1",
            b"GET http://[x]/ HTTP/1.1",
        ],
    )
    def test_an_unsplittable_get_is_answered_400(self, server, line, capsys) -> None:
        sent = line + (
            f"\r\nHost: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n".encode("ascii")
        )
        status, body = raw_answer(server, sent)
        assert (status, json.loads(body)) == (
            400,
            {"error": "bad-request", "message": "the request's target cannot be read"},
        )
        assert capsys.readouterr().err == ""

    def test_an_unsplittable_post_is_answered_400_too(self, server, capsys) -> None:
        sent = b"POST http://[/project HTTP/1.1\r\n" + (
            f"Host: 127.0.0.1:{server.port}\r\nContent-Length: 0\r\n"
            "Connection: close\r\n\r\n".encode("ascii")
        )
        status, body = raw_answer(server, sent)
        assert (status, json.loads(body)) == (
            400,
            {"error": "bad-request", "message": "the request's target cannot be read"},
        )
        assert capsys.readouterr().err == ""

    def test_a_well_formed_absolute_form_target_reaches_the_gate_instead(self, server) -> None:
        """The control: an absolute-form target ``urlsplit`` can read goes on as any other
        request would, past this check - here as far as the page itself, which needs no
        credential."""
        sent = (
            f"GET http://127.0.0.1:{server.port}/ HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        assert status_of(server, sent) == 200


def every_answer(server: GuiServer, sent: bytes) -> bytes:
    """Everything ``server`` writes back to ``sent``, on a connection of its own that asks to be
    kept open, read until the server closes it - or until five seconds pass with nothing more,
    the server holding it open for another request."""
    received = b""
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as connection:
        connection.sendall(sent)
        try:
            while chunk := connection.recv(65536):
                received += chunk
        except TimeoutError:
            pass
    return received


class Sending:
    """A client end for ``_linger`` that never stops sending and never closes, on a clock of its
    own: every read is answered at once, with as many bytes as it asks for up to ``each``, and
    moves ``clock`` on by ``every`` seconds. It notes every deadline it is given and every size
    it is asked for - and fails the test at its thousandth read, rather than send for ever to a
    lingering close that never stops reading."""

    READS: Final = 1000

    def __init__(self, clock: FakeClock, each: int, every: float) -> None:
        self.clock = clock
        self.each = each
        self.every = every
        self.deadlines: list[float | None] = []
        self.asked: list[int] = []

    def shutdown(self, how: int) -> None:
        """Nothing to shut: what is asserted is what is read, and for how long."""

    def settimeout(self, value: float | None) -> None:
        self.deadlines.append(value)

    def recv(self, size: int) -> bytes:
        self.asked.append(size)
        # An AssertionError, which the lingering close lets through: it suppresses OSError.
        assert len(self.asked) < self.READS, "the lingering close never stopped reading"
        self.clock.now += self.every
        return b"x" * min(size, self.each)


class TestABodyLeftUnread:
    """A ``POST`` refused before its body is read left that body on the connection, where the
    server read it as the next request and answered that too. Such a refusal now reads the body
    its ``Content-Length`` declares first, and throws it away: nothing of it is ever read as a
    request, and nothing is left unread to reset the connection (P18-31) - a reset that can
    throw the answer away before the client reads it. A body this server would not read - too
    long, of no length to read by, or sent with a ``Transfer-Encoding`` - is left: the answer
    says ``Connection: close``, and what still arrives is drained before the close. The smuggled
    request carries no token, so this was never more than a confusion - but the body is anyone's
    text."""

    SMUGGLED: Final = b"GET /api/session HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"

    @pytest.fixture(autouse=True)
    def briefly_idle(self, monkeypatch) -> None:
        """A connection left open closes after half a second idle, rather than thirty, so that
        reading one to its end - kept open, or held for a request that never comes - ends
        soon either way."""
        monkeypatch.setattr(module._Handler, "timeout", 0.5)

    @staticmethod
    def following(server: GuiServer) -> bytes:
        """A signed-in ``GET`` of the session, sent down the same connection after a refused
        ``POST``: answered ``200`` only if it is read as a request of its own."""
        return (
            f"GET /api/session HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Authorization: Bearer {server.token}\r\n\r\n"
        ).encode("ascii")

    @pytest.mark.parametrize(
        ("target", "headers", "status"),
        [
            ("/api/edit", "", 401),
            ("/api/edit", "SIGNED Sec-Fetch-Site: cross-site\r\n", 403),
            ("/api/edit", "SIGNED OWN Content-Type: text/plain\r\n", 403),
            ("/index.html", "SIGNED OWN Content-Type: application/json\r\n", 405),
            ("http://[/api/edit", "", 400),
        ],
        ids=["unsigned", "from-elsewhere", "not-json", "to-a-page", "an-unsplittable-target"],
    )
    def test_a_post_refused_before_its_body_is_read_drains_it_and_keeps_its_connection(
        self, server, target, headers, status
    ) -> None:
        """The body - here a request smuggled inside it - is read as body and thrown away:
        answered once, the connection kept, and the next request on it answered as itself."""
        signed = f"Authorization: Bearer {server.token}\r\n"
        own = f"Origin: http://127.0.0.1:{server.port}\r\n"
        headers = headers.replace("SIGNED ", signed).replace("OWN ", own)
        refused = (
            f"POST {target} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n{headers}"
            f"Content-Length: {len(self.SMUGGLED)}\r\n\r\n"
        ).encode("ascii") + self.SMUGGLED
        answered = every_answer(server, refused + self.following(server))
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.startswith(f"HTTP/1.1 {status} ".encode("ascii"))
        assert b"\r\nConnection: close\r\n" not in answered
        assert b"HTTP/1.1 200 " in answered.partition(b"\r\n\r\n")[2]

    @pytest.mark.parametrize(
        ("length", "status"),
        [(str(MAX_BODY + 1), 413), ("ten", 400)],
        ids=["too-long", "no-length"],
    )
    def test_a_post_whose_length_is_refused_is_answered_once_and_closed(
        self, server, length, status
    ) -> None:
        """Its body is never read, whatever follows: too long to read, or of no length to read
        by."""
        sent = posted(server, length).replace(b"Connection: close\r\n", b"") + self.SMUGGLED
        answered = every_answer(server, sent)
        assert answered.count(b"HTTP/1.1 ") == 1
        assert answered.startswith(f"HTTP/1.1 {status} ".encode("ascii"))
        assert b"\r\nConnection: close\r\n" in answered.partition(b"\r\n\r\n")[0]

    @pytest.mark.parametrize(
        "encoding", ["chunked", "gzip, chunked", "gzip"], ids=["chunked", "gzip-chunked", "gzip"]
    )
    def test_a_refused_post_sent_with_a_transfer_encoding_is_answered_once_and_closed(
        self, server, encoding
    ) -> None:
        """A body sent with any ``Transfer-Encoding`` - chunked, chunked after another coding,
        or another coding alone - has no ``Content-Length`` to be read by: refused before it is
        read, it is left, and the connection closed after the answer, as one too long is
        (P19a-10). Drained as a length of none instead, the connection would be kept and what
        follows read as the next request - its first chunk's size line, here, answered with the
        base class's bare 400 page. Nothing follows the one answer's body."""
        chunked = f"{len(self.SMUGGLED):x}\r\n".encode("ascii") + self.SMUGGLED + b"\r\n0\r\n\r\n"
        refused = (
            f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Transfer-Encoding: {encoding}\r\n\r\n"
        ).encode("ascii") + chunked
        head, _, rest = every_answer(server, refused).partition(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 401 ")
        assert b"\r\nConnection: close\r\n" in head
        assert rest == json.dumps({"error": "unauthorised", "message": _SIGN_IN}).encode()

    def test_a_chunked_post_let_through_to_its_body_reads_it_as_one_of_none(self, server) -> None:
        """P19a-10 leaves it so: let through to :meth:`_body`, it has its body read by its
        ``Content-Length``, of which it has none - answered by the api as an edit of nothing,
        and its connection kept - rather than refused for the length it does not declare."""
        sent = (
            f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Authorization: Bearer {server.token}\r\n"
            f"Origin: http://127.0.0.1:{server.port}\r\nContent-Type: application/json\r\n"
            "Transfer-Encoding: chunked\r\n\r\n"
        ).encode("ascii")
        head, _, rest = every_answer(server, sent).partition(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 400 ")
        assert b"\r\nConnection: close\r\n" not in head
        assert json.loads(rest) == {
            "error": "bad-request",
            "message": "Invalid JSON: EOF while parsing a value at line 1 column 0",
        }

    def test_a_post_too_long_to_read_keeps_its_answer_while_more_of_its_body_arrives(
        self, server
    ) -> None:
        """Refused before a byte of its body is read, its answer arrived but not yet read when 64
        KiB of that body are sent: what arrives is taken - drained before the close
        (``finish``), not refused with a reset - and the answer is read whole after it (P18-31).

        Before the drain (``b4ee603``, run 37720964591), this read is where windows lost the
        answer: on python 3.12 and 3.14 it raised ``ConnectionAbortedError`` (WinError 10053)
        without a byte of it, and 3.13 read it whole. Linux read it whole on all three, since it
        delivers what it holds before a reset, and shows the reset at the sender instead: one of
        these sends fails (``BrokenPipeError``), which pins the lingering close there. A thread
        still sending 4 MiB while the answer is read, as a browser posting a large body would,
        never lost the answer on any of the six legs: hence this order, which no thread's timing
        decides."""
        head = posted(server, str(MAX_BODY + 1)).replace(b"Connection: close\r\n", b"")
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as connection:
            connection.sendall(head)
            arrived(connection)  # the answer, written before a byte of the body was read
            for _ in range(64):
                connection.sendall(b"x" * 1024)  # taken, where a reset fails it
            answered = read_to_the_end(connection)
        assert answered.startswith(b"HTTP/1.1 413 ")
        assert answered.endswith(
            json.dumps(
                {"error": "too-large", "message": f"a request body is at most {MAX_BODY} bytes"}
            ).encode()
        )

    def test_a_misdirected_post_drains_its_body_and_keeps_its_connection(self, server) -> None:
        """Refused before anything else is read of it, its ``Host`` being another's: drained,
        answered once, and the connection kept for the next request."""
        refused = (
            f"POST /api/edit HTTP/1.1\r\nHost: example.com:{server.port}\r\n"
            f"Content-Length: {len(self.SMUGGLED)}\r\n\r\n"
        ).encode("ascii") + self.SMUGGLED
        answered = every_answer(server, refused + self.following(server))
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.startswith(b"HTTP/1.1 421 ")
        assert b"\r\nConnection: close\r\n" not in answered
        assert b"HTTP/1.1 200 " in answered.partition(b"\r\n\r\n")[2]

    def test_a_refused_post_without_a_content_length_keeps_its_connection(self, server) -> None:
        """With neither a ``Content-Length`` nor a ``Transfer-Encoding``, a body is one of none,
        up to ``MAX_BODY`` like any other: read at once, the refusal answered once, and the
        connection kept for the next request - not closed as one of no length to read by is."""
        refused = f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n\r\n".encode(
            "ascii"
        )
        answered = every_answer(server, refused + self.following(server))
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.startswith(b"HTTP/1.1 401 ")
        assert b"\r\nConnection: close\r\n" not in answered
        assert b"HTTP/1.1 200 " in answered.partition(b"\r\n\r\n")[2]

    def test_a_post_whose_body_was_read_keeps_its_connection(self, server) -> None:
        """Answered whatever its body says, as one request, and the connection kept for the
        next, which here follows it at once: a refusal of what the body holds reads the body
        first."""
        body = b"{}"
        sent = posted(server, str(len(body)), body).replace(b"Connection: close\r\n", b"")
        answered = every_answer(server, sent + self.SMUGGLED)
        assert answered.count(b"HTTP/1.1 ") == 2
        assert b"\r\nConnection: close\r\n" not in answered

    def test_a_post_refused_after_one_whose_body_was_read_is_drained_too(self, server) -> None:
        """Down one connection: whether a body was read is each request's own, so the second
        ``POST``'s body is drained, not taken for read because the first one's was - which
        would leave the request smuggled in it to be answered as a third."""
        body = b"{}"
        read = posted(server, str(len(body)), body).replace(b"Connection: close\r\n", b"")
        refused = (
            f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Content-Length: {len(self.SMUGGLED)}\r\n\r\n"
        ).encode("ascii") + self.SMUGGLED
        answered = every_answer(server, read + refused)
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.partition(b"\r\n\r\n")[2].count(b"HTTP/1.1 401 ") == 1
        assert b"\r\nConnection: close\r\n" not in answered

    def test_a_refused_post_whose_answer_fails_is_drained_once(
        self, server, monkeypatch, capsys
    ) -> None:
        """Its body drained, then its answer failing: answered ``500``, as any failure is, and
        that answer drains nothing more. The body counts as read once it is drained, so the next
        request on the connection is read as itself, not as more of this one's body."""
        send_response = module._Handler.send_response
        failed: list[int] = []

        def failing_once(handler: Any, status: int, message: str | None = None) -> None:
            if not failed:
                failed.append(status)
                raise RuntimeError("an answer that failed")
            send_response(handler, status, message)

        monkeypatch.setattr(module._Handler, "send_response", failing_once)
        refused = (
            f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Content-Length: {len(self.SMUGGLED)}\r\n\r\n"
        ).encode("ascii") + self.SMUGGLED
        answered = every_answer(server, refused + self.following(server))
        assert failed == [401]
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.startswith(b"HTTP/1.1 500 ")
        assert b"HTTP/1.1 200 " in answered.partition(b"\r\n\r\n")[2]
        assert "RuntimeError: an answer that failed" in capsys.readouterr().err

    def test_a_refused_post_whose_body_never_comes_is_closed_after_the_idle_time(
        self, project_file, pages
    ) -> None:
        """Declared 100 bytes, sent 10: the drain waits for the rest no longer than any
        connection waits, then closes it unanswered - no answer was written - and gives its
        slot back. On a server of one slot, so that the slot taken here is free again only
        once that connection's thread has let it go."""
        api = Held(Session(project_file.parent))
        api.release.set()  # never asked: the request is refused before the api is
        for server in serving(api, pages, connections=1):
            sent = (
                f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
                "Content-Length: 100\r\n\r\n"
            ).encode("ascii") + b"x" * 10
            with socket.create_connection(("127.0.0.1", server.port), timeout=10) as connection:
                connection.sendall(sent)
                # Closed once the idle time patched in has passed - within four times it - and
                # not merely within the ten seconds this test would wait for anything.
                connection.settimeout(4 * module._Handler.timeout)
                assert connection.recv(65536) == b""
            assert server.slots.acquire(timeout=10)
            server.slots.release()

    def test_only_a_connection_closed_with_a_body_unread_lingers(
        self, project_file, pages, monkeypatch
    ) -> None:
        """Every other connection is closed at once when its last answer is done - here one its
        client closed - and gives its slot back: a lingering close would hold that slot up to
        two seconds more. One closed with a body unread lingers, once. On a server of one slot,
        so that the slot back means that connection's thread has finished."""
        lingered: list[object] = []
        monkeypatch.setattr(module, "_linger", lingered.append)
        api = Held(Session(project_file.parent))
        api.release.set()
        for server in serving(api, pages, connections=1):
            assert ask(server, "GET", "/api/session")[0].status == 200
            assert server.slots.acquire(timeout=10)
            server.slots.release()
            assert lingered == []
            assert raw_answer(server, posted(server, str(MAX_BODY + 1)))[0] == 413
            assert server.slots.acquire(timeout=10)
            server.slots.release()
            assert len(lingered) == 1

    @staticmethod
    def lingered(end: socket.socket) -> None:
        """``_linger`` on ``end``, on a thread of its own given ten seconds to return, and what
        it raised raised again here: a lingering close that never ends fails the test rather than
        hanging the suite, and one that raises fails it rather than warning."""
        raised: list[BaseException] = []

        def lingering() -> None:
            try:
                module._linger(end)
            except BaseException as error:  # handed to the test's own thread, which raises it
                raised.append(error)

        thread = threading.Thread(target=lingering, daemon=True)
        thread.start()
        thread.join(10)
        assert not thread.is_alive(), "the lingering close did not end"
        if raised:
            raise raised[0]

    def test_the_lingering_close_ends_at_the_clients_end_of_file(self, monkeypatch) -> None:
        """It shuts the writing side first, so that the client reads the end of the answer while
        the connection is still open, then drains what arrives up to the client's own end of
        file - which ends it at once, long before its time is up."""
        monkeypatch.setattr(module, "LINGER_SECONDS", 60)
        ours, theirs = socket.socketpair()
        with ours, theirs:
            theirs.sendall(b"x" * 10)
            theirs.shutdown(socket.SHUT_WR)
            self.lingered(ours)
            theirs.settimeout(10)
            assert theirs.recv(1) == b""  # its writing side, shut
            ours.settimeout(10)
            assert ours.recv(1) == b""  # everything before the end of file, drained

    def test_the_lingering_close_waits_no_longer_than_its_time(self, monkeypatch) -> None:
        """Two seconds, shortened here: what a client sent is drained, and a client that then
        sends nothing more, and never closes, is let go when the time is up."""
        assert LINGER_SECONDS == 2.0
        monkeypatch.setattr(module, "LINGER_SECONDS", 0.05)
        ours, theirs = socket.socketpair()
        with ours, theirs:
            theirs.sendall(b"x" * 10)
            arrived_in_full(ours, b"x" * 10)
            self.lingered(ours)
            ours.setblocking(False)
            with pytest.raises(BlockingIOError):
                ours.recv(1)  # drained, and no end of file either: the client never closed

    def test_the_lingering_close_reads_nothing_once_its_time_is_up(self, monkeypatch) -> None:
        """A client still sending when the time is up is read no further - here the time is up
        before anything is read, and what arrived is left for the close - its writing side
        shut all the same."""
        monkeypatch.setattr(module, "LINGER_SECONDS", 0)
        ours, theirs = socket.socketpair()
        with ours, theirs:
            theirs.sendall(b"x" * 10)
            arrived_in_full(ours, b"x" * 10)
            self.lingered(ours)
            ours.settimeout(10)
            assert ours.recv(65536) == b"x" * 10
            theirs.settimeout(10)
            assert theirs.recv(1) == b""

    def test_the_lingering_close_drains_no_more_than_max_body(self, monkeypatch) -> None:
        """A client that has sent more than ``MAX_BODY`` bytes - four here - is read those four
        and no more, though its time is not up and it never closed: the rest is left for the
        close (P19a-11)."""
        monkeypatch.setattr(module, "MAX_BODY", 4)
        monkeypatch.setattr(module, "LINGER_SECONDS", 60)
        ours, theirs = socket.socketpair()
        with ours, theirs:
            theirs.sendall(b"x" * 10)
            arrived_in_full(ours, b"x" * 10)
            self.lingered(ours)
            ours.setblocking(False)
            assert ours.recv(65536) == b"x" * 6

    def test_the_lingering_close_ends_when_its_time_is_up_however_the_client_keeps_sending(
        self, monkeypatch
    ) -> None:
        """Its two seconds are counted once, from the start, and not afresh with every read: a
        client sending a byte every half second, for ever, is read four times, each read given
        what is left of the two seconds, and let go when they are up. A deadline set afresh on
        each read would hold it as long as it trickled, and each read given the whole two
        seconds, up to twice as long."""
        clock = FakeClock()
        monkeypatch.setattr(module, "time", types.SimpleNamespace(monotonic=clock))
        monkeypatch.setattr(module, "MAX_BODY", 64)  # so that a deadline never kept still ends
        trickling = Sending(clock, each=1, every=0.5)
        module._linger(trickling)
        assert trickling.deadlines == [2.0, 1.5, 1.0, 0.5]

    def test_the_lingering_close_reads_64_kib_at_a_time_and_max_body_at_most(
        self, monkeypatch
    ) -> None:
        """A client sending faster than it is read is read 64 KiB at a time, and never asked for
        more than what is left of ``MAX_BODY`` - 100,000 bytes here - so that the lingering
        close reads ``MAX_BODY`` bytes at most (P19a-11), its time never up meanwhile."""
        clock = FakeClock()
        monkeypatch.setattr(module, "time", types.SimpleNamespace(monotonic=clock))
        monkeypatch.setattr(module, "MAX_BODY", 100_000)
        flooding = Sending(clock, each=1 << 20, every=0)
        module._linger(flooding)
        assert flooding.asked == [65536, 100_000 - 65536]


class TestOneConnectionCarriesManyAsks:
    """Opening a panel asks this server twenty-odd times. Under HTTP/1.0 each ask cost a
    connection of its own, and a suite of browser journeys against 127.0.0.1 ran a windows
    machine out of the ports to make them with, at a point that moved from run to run."""

    @staticmethod
    def again(connection: http.client.HTTPConnection, server: GuiServer, path: str, **sent: str):
        """One more ask down a connection already open."""
        headers = {"Host": f"127.0.0.1:{server.port}", **sent}
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        return response, response.read()

    def test_the_open_page_a_static_page_and_the_api_are_answered_down_the_same_one(
        self, server
    ) -> None:
        # /open answers a page, not a redirect: two of these are pages, bytes that are not
        # json, and two are the api's json - the shapes a connection read twice has to tell
        # apart, in the order a browser meets them. Each says how long it is, which is what
        # lets it be told from the next. The token goes with the api's asks alone, as the page
        # sends it: a page needs no credential.
        signed_in = {"Authorization": f"Bearer {server.token}"}
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        try:
            asked = [
                self.again(connection, server, f"/open?token={server.token}"),
                self.again(connection, server, "/"),
                self.again(connection, server, "/api/session", **signed_in),
                self.again(connection, server, "/api/nothing", **signed_in),
            ]
        finally:
            connection.close()
        assert [response.status for response, _ in asked] == [200, 200, 200, 404]
        assert [response.version for response, _ in asked] == [11, 11, 11, 11]
        assert [response.will_close for response, _ in asked] == [False] * 4
        assert asked[0][1] == b"stand-in"
        assert asked[1][1] == b"stand-in"
        assert json.loads(asked[2][1])["version"] == ddd.__version__

    def test_a_connection_nobody_is_using_is_closed(self, server, monkeypatch) -> None:
        # Its own deadline rather than IDLE_SECONDS: what is asserted is that the socket carries
        # one at all, and a test that waits half a minute to say so asserts nothing more.
        monkeypatch.setattr(module._Handler, "timeout", 0.05)
        signed_in = {"Authorization": f"Bearer {server.token}"}
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        try:
            assert self.again(connection, server, "/api/session", **signed_in)[0].status == 200
            # Asked for until it is refused rather than after a fixed wait, which on a loaded
            # machine is a coin toss either way.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    self.again(connection, server, "/api/session", **signed_in)
                except (http.client.HTTPException, OSError):
                    break
                time.sleep(0.05)
            else:
                pytest.fail("the connection was held open")
        finally:
            connection.close()


class Held:
    """A stand-in for the API: every request waits until the test lets it go."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.asked = threading.Semaphore(0)
        self.release = threading.Event()

    def handle(self, method, path, query, body):
        self.asked.release()
        assert self.release.wait(10), "the test never let the request go"
        return Reply(200, {"held": True})


def _cannot_start(self) -> None:
    raise RuntimeError("can't start new thread")


def _recording(started: list[threading.Thread]) -> Callable[[threading.Thread], None]:
    """``threading.Thread.start``, noting in ``started`` every thread it is asked to start."""
    start = threading.Thread.start

    def recorded(thread: threading.Thread) -> None:
        started.append(thread)
        start(thread)

    return recorded


def _noting(
    taken: list[tuple[bool, float | None]], acquire: Callable[..., bool]
) -> Callable[..., bool]:
    """A semaphore's ``acquire``, noting in ``taken`` how each call asked for a slot: whether
    it would wait for one, and for how long."""

    def noted(blocking: bool = True, timeout: float | None = None) -> bool:
        taken.append((blocking, timeout))
        return acquire(blocking, timeout)

    return noted


class Deadlines:
    """A connection's server end that notes every deadline it is given, and passes everything
    else to the socket it stands in for."""

    def __init__(self, end: socket.socket) -> None:
        self.end = end
        self.deadlines: list[float | None] = []

    def settimeout(self, value: float | None) -> None:
        self.deadlines.append(value)
        self.end.settimeout(value)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.end, name)


def filled(end: socket.socket) -> None:
    """Send from ``end`` until it can send no more, its peer reading none of it - or fail at
    64 MiB rather than send forever."""
    end.setblocking(False)
    chunk = bytes(65536)
    for _ in range(1024):
        try:
            end.send(chunk)
        except BlockingIOError:
            return
    pytest.fail("the connection took 64 MiB and was still not full")


def arrived(end: socket.socket) -> None:
    """Wait, ten seconds at most, until what the other end of a pair sent, or its going away,
    can be read at ``end``: at once on a unix socket, and a moment later on Windows, where
    ``socket.socketpair`` is two TCP sockets over loopback."""
    readable, _, _ = select.select([end], [], [], 10)
    assert readable == [end], "nothing arrived"


def arrived_in_full(end: socket.socket, sent: bytes) -> None:
    """Wait, ten seconds at most, until all of ``sent`` can be read at ``end`` - peeked, so that
    it is all still there for a refusal to drain. A unix socket has it at once. On Windows,
    where ``socket.socketpair`` is two TCP sockets over loopback, a request of a few KB can
    arrive in pieces, and a drain that read only the first would pass where it should fail."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        arrived(end)
        if len(end.recv(len(sent), socket.MSG_PEEK)) == len(sent):
            return
    pytest.fail("the request never arrived in full")


def read_to_the_end(end: socket.socket) -> bytes:
    """All that ``end`` reads until the other end closes, given ten seconds to."""
    end.settimeout(10)
    with end.makefile("rb") as reading:
        return reading.read()


def refused(server: GuiServer, sent: bytes) -> bytes:
    """What a client that sent ``sent`` reads once ``server`` is handed the other end of their
    socket pair, as the accepting thread hands it a connection: ``sent`` arrived in full first,
    so the drain meets all of it, and the answer read to its end. The server's end carries a
    deadline of its own, so that a refusal that waited to read fails rather than hangs."""
    ours, theirs = socket.socketpair()
    with ours, theirs:
        if sent:
            theirs.sendall(sent)
            arrived_in_full(ours, sent)
        ours.settimeout(10)
        server.process_request(ours, ("127.0.0.1", 0))
        return read_to_the_end(theirs)


BROWSERS_REQUEST: Final = (
    "GET /project HTTP/1.1\r\n"
    "Host: 127.0.0.1:8123\r\n"
    "Connection: keep-alive\r\n"
    'sec-ch-ua: "Chromium";v="153", "Not.A/Brand";v="99"\r\n'
    "sec-ch-ua-mobile: ?0\r\n"
    'sec-ch-ua-platform: "Linux"\r\n'
    "Upgrade-Insecure-Requests: 1\r\n"
    "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36\r\n"
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7\r\n"
    "Sec-Fetch-Site: none\r\n"
    "Sec-Fetch-Mode: navigate\r\n"
    "Sec-Fetch-User: ?1\r\n"
    "Sec-Fetch-Dest: document\r\n"
    "Accept-Encoding: gzip, deflate, br, zstd\r\n"
    "Accept-Language: en-GB,en;q=0.9\r\n"
    "Cookie: " + "; ".join(f"app-{n}-session={'s' * 120}" for n in range(32)) + "\r\n\r\n"
).encode("ascii")
"""A request the size a browser sends this server, about 5 KB: a page asked for by its address,
with a browser's usual headers and a cookie header carrying what other apps on 127.0.0.1 have
set - a browser sends every one of them to every port. This server sets no cookie of its own,
and its page asks the API with none at all."""


class TestTheCap:
    """Spec §6: a connection takes one of sixty-four slots before it gets a thread, and with
    none free the thread that accepts it answers 503 itself and closes it, starting no thread.

    The refusal is read off a ``socket.socketpair`` handed to ``process_request`` directly,
    rather than a sixty-fifth network connection: whether a refused client reads its answer
    before the close would then turn on whether its request had arrived when it was accepted,
    a race no assertion can pin (the plan's ruling 2)."""

    @pytest.fixture
    def one_slot(self, project_file: Path, pages: Path) -> Iterator[GuiServer]:
        """A server of one slot that serves nothing itself: each test hands
        ``process_request`` its connections, as the accepting thread would."""
        server = GuiServer(Held(Session(project_file.parent)), pages, connections=1)
        try:
            yield server
        finally:
            server.server_close()

    def test_the_cap_is_sixty_four_connections(self) -> None:
        assert MAX_CONNECTIONS == 64

    def test_a_server_takes_sixty_four_connections_at_once_unless_told_otherwise(
        self, project_file, pages
    ) -> None:
        server = GuiServer(Held(Session(project_file.parent)), pages)
        try:
            taken = [server.slots.acquire(blocking=False) for _ in range(65)]
            assert taken == [True] * 64 + [False]
            for _ in range(64):
                server.slots.release()
            # Bounded: a slot given back twice is an error, never a sixty-fifth slot.
            with pytest.raises(ValueError, match="Semaphore released too many times"):
                server.slots.release()
        finally:
            server.server_close()

    def test_a_connection_past_the_cap_is_answered_503_by_the_accepting_thread(
        self, project_file, pages, monkeypatch
    ) -> None:
        api = Held(Session(project_file.parent))
        try:
            for server in serving(api, pages, connections=2):
                taken: list[tuple[bool, float | None]] = []
                started: list[threading.Thread] = []
                with monkeypatch.context() as watching:
                    watching.setattr(server.slots, "acquire", _noting(taken, server.slots.acquire))
                    held = [
                        threading.Thread(
                            target=ask, args=(server, "GET", "/api/session"), daemon=True
                        )
                        for _ in range(2)
                    ]
                    for each in held:
                        each.start()
                    for _ in held:
                        assert api.asked.acquire(timeout=10)
                    watching.setattr(threading.Thread, "start", _recording(started))
                    answer = refused(server, BROWSERS_REQUEST)
                assert started == []  # no thread was started for it
                # Every slot asked for without waiting, for the two connections answered and the
                # one refused alike: every other connection is accepted behind this thread.
                assert taken == [(False, None)] * 3
                head, _, data = answer.partition(b"\r\n\r\n")
                status, *fields = head.decode("latin-1").split("\r\n")
                assert status == "HTTP/1.1 503 Service Unavailable"
                expected = {
                    **SECURITY_HEADERS,
                    "Cache-Control": "no-store",
                    "Retry-After": "1",
                    "Content-Type": "application/json; charset=utf-8",
                    "Content-Length": str(len(data)),
                    "Connection": "close",
                }
                assert sorted(tuple(field.split(": ", 1)) for field in fields) == sorted(
                    expected.items()
                )
                assert json.loads(data) == {"error": "busy", "message": BUSY}
                api.release.set()
                for each in held:
                    each.join(10)
                    assert not each.is_alive()
                # A slot is given back on its connection's own thread once the connection has
                # closed, a moment after its client read the answer: waited for, not assumed.
                assert server.slots.acquire(timeout=10)
                server.slots.release()
                response, data = ask(server, "GET", "/api/session")  # a slot is free again
                assert (response.status, json.loads(data)) == (200, {"held": True})
        finally:
            api.release.set()

    def test_at_the_cap_itself_the_sixty_fifth_is_refused_and_a_freed_slot_serves_the_next(
        self, project_file, pages
    ) -> None:
        """Spec §9's case at the real cap: a server built without ``connections``, sixty-four
        connections held by a handler waiting on an event. They are opened one at a time, each
        held before the next is opened: the server listens with a backlog of five, and a burst
        past it waits on Linux and may be refused on Windows."""
        api = Held(Session(project_file.parent))
        server = GuiServer(api, pages)
        serving_thread = threading.Thread(target=server.serve_forever, daemon=True)
        serving_thread.start()
        try:
            held = []
            for _ in range(64):
                each = threading.Thread(
                    target=ask, args=(server, "GET", "/api/session"), daemon=True
                )
                each.start()
                held.append(each)
                assert api.asked.acquire(timeout=10)
            answer = refused(server, BROWSERS_REQUEST)
            assert answer.split(b"\r\n", 1)[0] == b"HTTP/1.1 503 Service Unavailable"
            api.release.set()
            for each in held:
                each.join(10)
                assert not each.is_alive()
            assert server.slots.acquire(timeout=10)
            server.slots.release()
            assert ask(server, "GET", "/api/session")[0].status == 200
        finally:
            api.release.set()
            server.shutdown()
            server.server_close()
            serving_thread.join(10)

    def test_the_refusal_says_the_server_is_busy_and_to_ask_again(self) -> None:
        """Pinned by its literal text: the 503's own test compares against the imported
        ``BUSY``, which would drift along with any change to its wording."""
        assert BUSY == (
            "ddd gui is answering as many connections as it takes at once; ask again in a moment"
        )

    def test_a_thread_that_cannot_start_gives_its_slot_back(self, one_slot, monkeypatch) -> None:
        monkeypatch.setattr(threading.Thread, "start", _cannot_start)
        ours, theirs = socket.socketpair()
        with ours, theirs, pytest.raises(RuntimeError, match="can't start new thread"):
            one_slot.process_request(ours, ("127.0.0.1", 0))
        monkeypatch.undo()
        assert one_slot.slots.acquire(blocking=False)  # the one slot is free

    def test_a_connection_that_has_sent_nothing_yet_is_refused_without_waiting_for_it(
        self, one_slot
    ) -> None:
        """What has arrived is drained and nothing more is waited for: the thread that writes
        the refusal is the one every other connection is accepted on."""
        assert one_slot.slots.acquire(blocking=False)  # the one slot, taken
        answer = refused(one_slot, b"")
        assert answer.split(b"\r\n", 1)[0] == b"HTTP/1.1 503 Service Unavailable"
        assert not one_slot.slots.acquire(blocking=False)  # none taken, none given back

    @pytest.mark.parametrize("left", ["closed", "reset"])
    def test_a_client_gone_before_its_refusal_is_let_go_quietly(self, one_slot, left) -> None:
        """Gone by closing, which fails the refusal's write on a unix socket, or by resetting -
        closing with bytes it never read - which fails the read before the write. Neither
        failure leaves the accepting thread."""
        assert one_slot.slots.acquire(blocking=False)
        ours, theirs = socket.socketpair()
        with ours:
            if left == "reset":
                ours.sendall(b"never read")
            theirs.close()
            arrived(ours)
            one_slot.process_request(ours, ("127.0.0.1", 0))
            assert ours.fileno() == -1  # closed all the same

    def test_a_client_that_does_not_read_its_refusal_cannot_hold_the_accepting_thread(
        self, one_slot, monkeypatch
    ) -> None:
        """The refusal is given a second to be written, shortened here, and the deadline it is
        written under is the one noted. A connection just accepted takes its few hundred bytes
        at once, so this one is filled first, standing in for a connection that will not take
        them."""
        assert REFUSAL_SECONDS == 1
        monkeypatch.setattr(module, "REFUSAL_SECONDS", 0.05)
        assert one_slot.slots.acquire(blocking=False)
        ours, theirs = socket.socketpair()
        with ours, theirs:
            filled(ours)
            noted = Deadlines(ours)
            refusing = threading.Thread(
                target=one_slot.process_request, args=(noted, ("127.0.0.1", 0)), daemon=True
            )
            refusing.start()
            refusing.join(10)
            assert not refusing.is_alive(), "the refusal waited on a client that never reads"
            assert noted.deadlines == [0.05]  # REFUSAL_SECONDS, read as it stands
            assert ours.fileno() == -1  # given up on, and closed

    def test_a_connection_nobody_is_using_gives_its_slot_back(
        self, project_file, pages, monkeypatch
    ) -> None:
        """Spec §6: a connection kept open and left idle still gives its slot up once the
        deadline every connection is given has passed - shortened here, as in
        ``TestOneConnectionCarriesManyAsks``."""
        monkeypatch.setattr(module._Handler, "timeout", 0.05)
        api = Held(Session(project_file.parent))
        api.release.set()
        for server in serving(api, pages, connections=1):
            idle = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
            try:
                signed_in = {
                    "Host": f"127.0.0.1:{server.port}",
                    "Authorization": f"Bearer {server.token}",
                }
                idle.request("GET", "/api/session", headers=signed_in)
                response = idle.getresponse()
                response.read()
                assert (response.status, response.will_close) == (200, False)
                # Kept open, and asked nothing more: closed by the server, its slot given back.
                assert server.slots.acquire(timeout=10)
                server.slots.release()
                assert ask(server, "GET", "/api/session")[0].status == 200
            finally:
                idle.close()


def request_line(length: int) -> bytes:
    """A ``GET`` of the session whose request line, its CRLF included, is ``length`` bytes."""
    start, end = b"GET /api/session?", b" HTTP/1.1\r\n"
    line = start + b"x" * (length - len(start) - len(end)) + end
    assert len(line) == length
    return line


def header_line(length: int, name: bytes = b"X-Pad", filler: bytes = b"x") -> bytes:
    """A header line ``name`` whose value is ``filler`` over and over, ``length`` bytes long
    with its CRLF; nothing reads an ``X-Pad``."""
    start, end = name + b": ", b"\r\n"
    line = start + filler * (length - len(start) - len(end)) + end
    assert len(line) == length
    return line


def headed(server: GuiServer, count: int, *, ended: bool = True) -> bytes:
    """A ``GET`` of the session with ``count`` header lines, ``Host`` and ``Connection: close``
    among them: ended by the blank line, or cut off after the last of them."""
    lines = [f"Host: 127.0.0.1:{server.port}", "Connection: close"]
    lines += [f"X-Header-{n}: {n}" for n in range(count - len(lines))]
    sent = "GET /api/session HTTP/1.1\r\n" + "".join(f"{line}\r\n" for line in lines)
    return (sent + "\r\n" if ended else sent).encode("ascii")


def status_of(server: GuiServer, sent: bytes) -> int:
    """The status ``server`` answers ``sent`` with, over a connection of its own, read to its
    end."""
    return raw_answer(server, sent)[0]


class TestTheStandardLibrarysLimits:
    """Spec §6 leaves a request's own size to the standard library, ahead of anything of this
    server's: the length of its request line and of each header line, and the number of its
    headers. Pinned here, each on a connection of its own, so that a server that stopped
    answering them would be caught.

    A refused request is sent only as far as the line it is refused at: a connection closed
    with bytes it never read is reset, and the answer can be lost with it."""

    def test_a_request_line_of_more_than_65536_bytes_is_answered_414(self, server) -> None:
        assert status_of(server, request_line(65537)) == 414

    def test_a_request_line_of_65536_bytes_is_read(self, server) -> None:
        end = f"Host: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n".encode("ascii")
        assert status_of(server, request_line(65536) + end) == 401

    @pytest.mark.parametrize(
        ("name", "filler"), [(b"X-Pad", b"x"), (b"Content-Length", b"9")], ids=["any", "a-length"]
    )
    def test_a_header_line_of_more_than_65536_bytes_is_answered_431(
        self, server, name, filler
    ) -> None:
        """Whatever header it is: a ``Content-Length`` written with too many nines for its line
        is refused here, before this server reads it as a length, too large or not."""
        sent = b"POST /api/edit HTTP/1.1\r\n" + header_line(65537, name, filler)
        assert status_of(server, sent) == 431

    def test_a_header_line_of_65536_bytes_is_read(self, server) -> None:
        end = f"Host: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n".encode("ascii")
        sent = b"GET /api/session HTTP/1.1\r\n" + header_line(65536) + end
        assert status_of(server, sent) == 401

    def test_a_request_of_101_headers_is_answered_431(self, server) -> None:
        assert status_of(server, headed(server, 101, ended=False)) == 431

    def test_a_request_of_100_headers_is_answered_431(self, server) -> None:
        """The security page states this one, in round numbers: the blank line that ends the
        headers is itself counted, so a hundred header lines already carry it past the
        standard library's own limit."""
        assert status_of(server, headed(server, 100)) == 431

    def test_a_request_of_99_headers_is_read(self, server) -> None:
        """Not 100: the standard library counts the blank line that ends the headers among its
        hundred, on python 3.12 to 3.14."""
        assert status_of(server, headed(server, 99)) == 401


def answered(
    server: GuiServer, method: str, path: str, body: object = None, status: int = 200
) -> dict[str, Any]:
    """A request's json answer, which has to come with ``status``."""
    sent = None if body is None else json.dumps(body).encode("utf-8")
    origin = None if body is None else f"http://127.0.0.1:{server.port}"
    response, data = ask(server, method, path, body=sent, origin=origin)
    assert response.status == status, data
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    answer: dict[str, Any] = json.loads(data)
    return answer


@pytest.fixture
def demo(tmp_path: Path, pages: Path) -> Iterator[tuple[GuiServer, Path]]:
    """ddd gui serving a copy of examples/demo, and where the copy is: at revision 2, opening
    making two analyses of the demo, since it does not stamp its sub-project's own component
    before the first reads it."""
    root = tmp_path / "demo"
    shutil.copytree(EXAMPLES / "demo", root)
    session = Session(root)
    session.open(root / "demo.ddd.json")
    for server in serving(Api(session, root / "demo.ddd.json", wait_seconds=0.05), pages):
        yield server, root.resolve()


class TestEveryEndpointOnTheDemo:
    """Spec 6.11: every endpoint through real HTTP, on a copy of examples/demo."""

    COMPONENTS: Final = {"Controller", "SensorHub", "UserInterface", "EventLogger"}

    def test_the_session_names_the_demo(self, demo) -> None:
        server, root = demo
        body = answered(server, "GET", "/api/session")
        assert body["project"] == {"path": f"{root.as_posix()}/demo.ddd.json", "name": "DemoDevice"}
        assert (body["version"], body["preview"], body["builds"]) == (ddd.__version__, True, [])

    def test_the_projects_found_include_the_demo(self, demo) -> None:
        server, root = demo
        body = answered(server, "GET", "/api/projects")
        assert body["root"] == root.as_posix()
        assert {"path": f"{root.as_posix()}/demo.ddd.json", "name": "DemoDevice", "images": []} in (
            body["projects"]
        )
        assert body["refused"] == []

    def test_the_demo_is_opened_again(self, demo) -> None:
        server, root = demo
        body = answered(server, "POST", "/api/open", {"path": f"{root.as_posix()}/demo.ddd.json"})
        assert body["project"]["name"] == "DemoDevice"
        assert answered(server, "GET", "/api/state")["revision"] == 4

    def test_the_state_lists_the_components_loaded_and_clean(self, demo) -> None:
        server, _ = demo
        body = answered(server, "GET", "/api/state")
        components = [f for f in body["files"] if f["kind"] == "component"]
        assert {f["name"] for f in components} == self.COMPONENTS
        assert all(f["loaded"] and f["findings"]["error"] == 0 for f in components)
        assert body["counts"]["error"] == 0
        findings = answered(server, "GET", "/api/findings")["findings"]
        assert not [f for f in findings if f["severity"] == "error"]
        waited = answered(server, "GET", f"/api/state?after={body['version']}")
        assert (waited["version"], waited["revision"]) == (body["version"], body["revision"])

    def test_a_component_is_read_with_its_fingerprint(self, demo) -> None:
        server, root = demo
        controller = root / "components" / "controller.ddd.json"
        body = answered(server, "GET", f"/api/file?path={quote(controller.as_posix())}")
        assert body["data"]["component"]["name"] == "Controller"
        assert (body["fingerprint"], body["error"]) == (fingerprint(controller.read_bytes()), None)

    def test_the_dictionary_is_the_demos(self, demo) -> None:
        server, _ = demo
        body = answered(server, "GET", "/api/dictionary")
        assert (body["revision"], body["dictionary"]["name"]) == (2, "DemoDevice")

    def test_the_checks_are_listed(self, demo) -> None:
        server, _ = demo
        listed = {entry["check"] for entry in answered(server, "GET", "/api/checks")["checks"]}
        assert {"definition-mismatch", "json-syntax"} <= listed

    def test_the_graph_lists_the_demos_modules_and_flows(self, demo) -> None:
        server, _ = demo
        body = answered(server, "GET", "/api/graph")
        assert set(body) == {"revision", "dictionary", "modules", "flows"}
        assert {m["name"] for m in body["modules"]} == self.COMPONENTS
        assert body["dictionary"] is True
        assert body["flows"]

    def test_an_edit_changes_the_units_value_alone_and_both_sides_disagree(self, demo) -> None:
        server, root = demo
        controller = root / "components" / "controller.ddd.json"
        before = controller.read_bytes()
        edit = {
            "changes": [
                {
                    "file": controller.as_posix(),
                    "fingerprint": fingerprint(before),
                    "operations": [
                        {
                            "op": "set",
                            "pointer": "component.interface[0].definition.unit",
                            "raw": '"rpm"',
                        }
                    ],
                }
            ],
            "label": "the unit of ValueA",
        }
        body = answered(server, "POST", "/api/edit", edit)
        after = controller.read_bytes()
        assert after == before.replace(b'"unit": "%"', b'"unit": "rpm"', 1)
        assert body == {
            "edit": 1,
            "files": [{"path": controller.as_posix(), "fingerprint": fingerprint(after)}],
        }
        findings = answered(server, "GET", "/api/findings")["findings"]
        disagreeing = {
            Path(f["file"]).name for f in findings if f["check"] == "definition-mismatch"
        }
        assert disagreeing == {"controller.ddd.json", "sensor_hub.ddd.json"}

    def test_the_declarable_names_and_a_plan_of_one(self, demo) -> None:
        server, root = demo
        controller = (root / "components" / "controller.ddd.json").as_posix()
        answer = answered(server, "GET", f"/api/declarable?file={quote(controller)}")
        assert [entry["name"] for entry in answer["names"]][:2] == ["BlockA", "CurveB"]
        assert next(form["kind"] for form in answer["kinds"]) == "measurement"
        # Every field of the reply crosses the wire, `constants` included - empty here because
        # examples/demo declares none, but present, which is what the page reads a value
        # block's dimension rows from.
        assert answer["constants"] == []
        planned = answered(
            server,
            "GET",
            f"/api/declaration-plan?action=read&file={quote(controller)}&name=ValueC&scope=input",
        )
        assert len(planned["changes"]) == 1

    def test_the_values_of_a_curve_and_a_plan_of_one(self, demo) -> None:
        server, _ = demo
        answer = answered(server, "GET", "/api/values?name=CurveA")
        assert answer["rows"] == [[1200, 900, 800, 750, 700, 650]]
        planned = answered(server, "GET", "/api/value-plan?name=CurveA&at=%5B2%5D&raw=750")
        assert len(planned["changes"]) == 1

    def test_a_whole_curve_planned_over_http(self, demo) -> None:
        server, _ = demo
        planned = answered(
            server, "GET", "/api/values-plan?name=CurveA&raw=1300,950,850,800,750,700"
        )
        assert len(planned["changes"]) == 1


class TestBlankParameters:
    """A parameter given with no value reaches the api as the empty text, which each route reads
    as it always has: clearing a unit's description sends ``description=``, a blank ``raw`` takes
    a key away, and each route below refuses a blank key it requires as one left out."""

    @pytest.fixture
    def described(self, tmp_path: Path, pages: Path) -> Iterator[tuple[GuiServer, Path]]:
        """ddd gui serving a project whose vocabulary describes its one unit."""
        root = tmp_path / "described"
        write_tree(
            root,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": [{"unit": "rpm", "description": "rotational speed"}]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        session = Session(root)
        session.open(root / "p.ddd.json")
        for server in serving(Api(session, root / "p.ddd.json", wait_seconds=0.05), pages):
            yield server, root.resolve()

    def test_an_empty_description_clears_the_units_description(self, described) -> None:
        server, root = described
        plan = answered(server, "GET", "/api/unit-plan?action=describe&unit=rpm&description=")
        (change,) = plan["changes"]
        assert change["operations"] == [
            {"op": "set", "pointer": "units[0].description", "raw": '""'}
        ]
        edit = {
            "changes": [{key: change[key] for key in ("file", "fingerprint", "operations")}],
            "label": "the description of rpm",
        }
        answered(server, "POST", "/api/edit", edit)
        units = json.loads((root / "units.ddd.json").read_text(encoding="utf-8"))["units"]
        assert units == [{"unit": "rpm", "description": ""}]

    @pytest.mark.parametrize(
        ("path", "sentence"),
        [
            ("/api/variable?name=", "variable takes ?name="),
            ("/api/type?name=", "type takes ?name="),
            ("/api/constant?name=", "constant takes ?name="),
            ("/api/section?name=", "section takes ?name="),
            ("/api/raster?name=", "raster takes ?name="),
            ("/api/values?name=", "values takes ?name="),
            ("/api/unit?name=", "unit takes ?name="),
            ("/api/file?path=", "file takes ?path="),
            ("/api/declarable?file=", "declarable takes ?file="),
            ("/api/compare?baseline=", "compare takes ?baseline="),
            (
                "/api/settle?name=&key=unit",
                "settle takes ?name= and ?key=, and ?raw= unless the key goes",
            ),
            (
                "/api/fix?file=&pointer=&check=missing-id",
                "fix takes ?file=, ?pointer= and ?check=",
            ),
            (
                "/api/unit-plan?action=",
                "unit-plan takes ?action= one of rename, add, describe, remove, adopt",
            ),
            ("/api/unit-plan?action=rename&unit=&to=rpm", "rename takes ?unit= and ?to="),
        ],
    )
    def test_any_other_blank_parameter_is_refused_as_a_missing_one(
        self, server, path, sentence
    ) -> None:
        assert answered(server, "GET", path, status=400) == {
            "error": "bad-request",
            "message": sentence,
        }

    def test_a_blank_raw_takes_the_key_out_as_a_missing_one_does(self, server) -> None:
        changes = answered(server, "GET", "/api/settle?name=Speed&key=unit&raw=")["changes"]
        assert [change["operations"] for change in changes] == [
            [{"op": "remove", "pointer": "component.interface[0].definition.unit", "raw": None}]
        ]


class TestAMalformedQueryOverTheWire:
    """What spec §2 sent over HTTP, read off the request line as the page's own requests are:
    ``%00`` decoded into a NUL, and a number of more digits than one holds."""

    def test_a_file_filter_holding_a_nul_is_refused_not_failed(self, server) -> None:
        assert answered(server, "GET", "/api/findings?file=%00", status=400) == {
            "error": "bad-request",
            "message": "findings takes ?file= as a file's path",
        }

    def test_a_version_of_too_many_digits_is_answered_at_once(self, server, monkeypatch) -> None:
        def never_waited(after: int, timeout: float) -> None:
            raise AssertionError(f"waited for a version past {after}")

        monkeypatch.setattr(server.api.session, "wait", never_waited)
        version = f"/api/state?after={'1' * 4301}"
        assert answered(server, "GET", version)["revision"] == 1

    def test_a_key_given_twice_is_refused_by_the_route_s_name(self, server) -> None:
        assert answered(server, "GET", "/api/findings?offset=0&offset=1", status=400) == {
            "error": "bad-request",
            "message": "findings takes ?offset= once",
        }


class TestAProjectWithAFileThatDoesNotParse:
    """Spec 6.10: the project still opens, the file is marked as not loaded, its findings say
    why, and reading it answers the reason instead of a document."""

    @pytest.fixture
    def broken(self, tmp_path: Path, pages: Path) -> Iterator[tuple[GuiServer, Path]]:
        root = tmp_path / "project"
        write_tree(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": '{"component": {"name": "B",',
            },
        )
        session = Session(root)
        session.open(root / "p.ddd.json")
        for server in serving(Api(session, root / "p.ddd.json", wait_seconds=0.05), pages):
            yield server, root.resolve()

    def test_the_state_marks_the_file_not_loaded_and_says_why(self, broken) -> None:
        server, root = broken
        body = answered(server, "GET", "/api/state")
        files = {Path(f["path"]).name: f for f in body["files"]}
        assert (files["a.ddd.json"]["loaded"], files["b.ddd.json"]["loaded"]) == (True, False)
        assert files["b.ddd.json"]["findings"]["error"] == 1
        findings = answered(server, "GET", "/api/findings")["findings"]
        why = [f for f in findings if f["file"] == (root / "b.ddd.json").as_posix()]
        assert [f["check"] for f in why] == ["json-syntax"]

    def test_its_findings_are_asked_a_page_at_a_time_through_the_address(self, broken) -> None:
        """The query read off the request line - a file's path encoded as the page encodes it -
        and a query the endpoint refuses, refused in its own sentence."""
        server, root = broken
        b = quote((root / "b.ddd.json").as_posix(), safe="")
        page = answered(server, "GET", f"/api/findings?offset=0&limit=1&file={b}")
        assert (page["total"], [f["check"] for f in page["findings"]]) == (1, ["json-syntax"])
        refused = answered(server, "GET", "/api/findings?limit=0", status=400)
        assert refused == {
            "error": "bad-request",
            "message": "findings takes ?limit= as a whole number from 1",
        }

    def test_the_file_is_answered_as_the_reason_it_does_not_parse(self, broken) -> None:
        server, root = broken
        target = root / "b.ddd.json"
        body = answered(server, "GET", f"/api/file?path={quote(target.as_posix())}")
        assert (body["data"], body["fingerprint"]) == (None, fingerprint(target.read_bytes()))
        assert body["error"].startswith(f"{target} is not json: ")


class TestLoopback:
    """Classifies a numeric address alone; resolving a name to one is run()'s job, with
    socket.getaddrinfo, before this ever sees it."""

    @pytest.mark.parametrize("address", ["127.0.0.1", "127.0.0.2", "::1"])
    def test_a_loopback_address_is_loopback(self, address: str) -> None:
        assert is_loopback(address) is True

    @pytest.mark.parametrize(
        "address",
        ["0.0.0.0", "::", "192.168.1.10", "example.com", "localhost", "LOCALHOST", ""],
    )
    def test_anything_that_is_not_a_loopback_address_is_not(self, address: str) -> None:
        """Not even ``localhost``: a name is not a numeric address, whatever it usually
        resolves to, and this function never resolves one."""
        assert is_loopback(address) is False

    def test_a_malformed_address_is_answered_false_rather_than_raised(self) -> None:
        assert is_loopback("300.300.300.300") is False


class TestRunning:
    def test_an_installation_without_compiled_pages_is_a_usage_error(
        self, tmp_path, capsys
    ) -> None:
        """Node builds the pages and nothing that installs them needs it, so the message says
        where it looked and what already carries them before the two commands that build them."""
        assert run(None, [], 0, open_browser=False, static=tmp_path) == EXIT_USAGE
        message = capsys.readouterr().err
        looked = message.index(f"no compiled pages for ddd gui in {tmp_path};")
        released = message.index("a released ddd-tool carries them")
        wheel = message.index("the wheel ci builds for every branch it runs on")
        built = message.index("with 'npm ci' and 'npm run build' in its gui directory")
        assert looked < released < wheel < built
        assert not set("*`|") & set(message), "markup in a message printed to a terminal"

    def test_a_file_that_is_not_a_project_is_a_usage_error(
        self, project_file, pages, capsys
    ) -> None:
        result = run(project_file.parent / "a.ddd.json", [], 0, open_browser=False, static=pages)
        assert result == EXIT_USAGE
        assert "is not a project description" in capsys.readouterr().err

    def test_a_taken_port_is_a_usage_error(self, pages, capsys) -> None:
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen()
            port = taken.getsockname()[1]
            assert run(None, [], port, open_browser=False, static=pages) == EXIT_USAGE
        assert f"cannot serve 127.0.0.1 on port {port}" in capsys.readouterr().err

    def test_a_fixed_port_is_required_beyond_loopback(self, pages, capsys) -> None:
        """``--port 0`` lets the system pick one, which a container cannot publish in advance."""
        result = run(None, [], 0, open_browser=False, static=pages, host="0.0.0.0")
        assert result == EXIT_USAGE
        assert capsys.readouterr().err == (
            "ddd: --host resolves to 0.0.0.0, beyond this computer's loopback; --port 0 lets "
            "the system pick a free one there, which cannot be published in advance, so give "
            "a fixed --port too\n"
        )

    def test_an_unbindable_address_is_a_usage_error_like_a_taken_port(
        self, pages, capsys, monkeypatch
    ) -> None:
        """Not an address of this machine, or malformed: refused the way a taken port is.

        203.0.113.5 is a documentation-only address (RFC 5737): never assigned to a real
        machine, so it stands for one this computer cannot bind, but asking a real socket to
        try could still hang or answer differently depending on the network this test runs
        on. The construction is patched instead, standing in for whatever the platform's
        socket would have refused; it resolves to itself (it is already numeric), so it is
        what run() hands the fake, unlike the raw --host of a name that resolves elsewhere.
        """

        def refuses_the_address(self, api, static, port=0, host="127.0.0.1"):
            raise OSError("Cannot assign requested address")

        monkeypatch.setattr(GuiServer, "__init__", refuses_the_address)
        result = run(None, [], 8123, open_browser=False, static=pages, host="203.0.113.5")
        assert result == EXIT_USAGE
        message = capsys.readouterr().err
        assert message == (
            "ddd: cannot serve 203.0.113.5 on port 8123: Cannot assign requested address\n"
        )

    def test_a_host_that_cannot_be_resolved_is_a_usage_error_not_a_crash(
        self, pages, capsys
    ) -> None:
        """A non-ASCII --host used to reach the bind unresolved and raise a bare TypeError
        past every usage-error handler, exit 1 with a traceback. Resolving it explicitly,
        instead of leaving that to the bind, turns the same address into a plain
        UnicodeEncodeError - a ValueError - caught here like any other usage error."""
        result = run(None, [], 8123, open_browser=False, static=pages, host="é..x")
        assert result == EXIT_USAGE
        message = capsys.readouterr().err
        assert message.startswith("ddd: cannot serve é..x on port 8123:")

    def test_an_address_that_cannot_be_resolved_at_all_is_a_usage_error_not_a_crash(
        self, pages, monkeypatch, capsys
    ) -> None:
        """--host ::1 has no AF_INET address at all, so getaddrinfo raises gaierror - an
        OSError, not the ValueError a malformed or non-ASCII host raises. Both have to be
        caught here: narrowed to ValueError alone, this would propagate uncaught, past
        run() and past main()'s own usage-error handling, naming neither the host nor the
        port anywhere."""

        def getaddrinfo(host, port, family, kind):
            raise socket.gaierror("getaddrinfo failed")

        monkeypatch.setattr(module.socket, "getaddrinfo", getaddrinfo)
        result = run(None, [], 8123, open_browser=False, static=pages, host="::1")
        assert result == EXIT_USAGE
        assert capsys.readouterr().err == "ddd: cannot serve ::1 on port 8123: getaddrinfo failed\n"

    def test_beyond_loopback_it_warns_once_and_opens_no_browser(
        self, pages, monkeypatch, capsys
    ) -> None:
        """The Host and Origin allow-lists still admit only 127.0.0.1 and localhost, so beyond
        loopback the token in the printed address is the only thing keeping another client
        out - and there is no browser to open in a container anyway."""
        real_init = GuiServer.__init__
        received: list[tuple[str, int]] = []
        created: list[GuiServer] = []

        def binds_loopback_but_reports_beyond_it(self, api, static, port=0, host="127.0.0.1"):
            received.append((host, port))
            # A real bind of 0.0.0.0 can raise a firewall dialog on Windows and block the
            # run; this test is about what run() does with the address it was actually
            # given, not about asking a real socket to answer on every interface. The real
            # bind stays on 127.0.0.1, and server_address is overwritten afterwards to
            # stand in for the wider one - otherwise nothing here could tell a printed
            # address that is always 127.0.0.1 apart from one that merely happens to be,
            # because it was never bound to anything else.
            real_init(self, api, static, 0)
            self.server_address = ("0.0.0.0", self.server_address[1])
            created.append(self)

        monkeypatch.setattr(GuiServer, "__init__", binds_loopback_but_reports_beyond_it)
        monkeypatch.setattr(Session, "start", lambda self: None)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: None)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        opened: list[str] = []
        monkeypatch.setattr(module.webbrowser, "open", opened.append)

        result = run(None, [], 8123, open_browser=True, static=pages, host="0.0.0.0")

        assert result == EXIT_OK
        assert received == [("0.0.0.0", 8123)]
        (server,) = created
        captured = capsys.readouterr()
        (line,) = captured.out.splitlines()
        assert line == (
            f"ddd gui (preview) serving http://127.0.0.1:{server.port}/open?token={server.token}"
        )
        assert captured.err == (
            f"ddd gui: listening on 0.0.0.0:{server.port}, beyond this computer's loopback; "
            f"publish it on the host's loopback only, -p 127.0.0.1:{server.port}:{server.port}, "
            "since the token in the address is what keeps others out\n"
        )
        assert opened == []

    def test_localhost_resolving_to_loopback_is_loopback(
        self, project_file, pages, monkeypatch, capsys
    ) -> None:
        """is_loopback never sees the string 'localhost': run() resolves it first, with
        socket.getaddrinfo, so a hosts file could redirect it and this would still answer
        correctly - proven here by resolving it to 127.0.0.1 itself, not by trusting the
        spelling."""

        def getaddrinfo(host, port, family, kind):
            assert (host, family, kind) == ("localhost", socket.AF_INET, socket.SOCK_STREAM)
            return [(family, kind, 0, "", ("127.0.0.1", port))]

        monkeypatch.setattr(module.socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(Session, "start", lambda self: None)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: None)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        opener = Opened()
        monkeypatch.setattr(module.webbrowser, "open", opener)

        result = run(project_file, [], 0, open_browser=True, static=pages, host="localhost")

        assert result == EXIT_OK
        (line,) = capsys.readouterr().out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")
        code_from(line, opener.wait())

    def test_uppercase_localhost_resolving_to_loopback_is_loopback(
        self, pages, monkeypatch, capsys
    ) -> None:
        """The review that found this asked for it directly: LOCALHOST resolves like
        localhost, since a resolver does not care about case, and this now reads the
        resolver rather than the spelling of --host."""

        def getaddrinfo(host, port, family, kind):
            assert host == "LOCALHOST"
            return [(family, kind, 0, "", ("127.0.0.1", port))]

        monkeypatch.setattr(module.socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        result = run(None, [], 0, open_browser=False, static=pages, host="LOCALHOST")
        assert result == EXIT_OK
        assert capsys.readouterr().err == ""

    def test_localhost_resolving_beyond_loopback_needs_a_fixed_port(
        self, pages, monkeypatch, capsys
    ) -> None:
        """A hosts file that points localhost at a LAN address is judged by that address,
        not by the name: the default port is refused exactly as --host 0.0.0.0 is."""

        def getaddrinfo(host, port, family, kind):
            return [(family, kind, 0, "", ("192.168.1.50", port))]

        monkeypatch.setattr(module.socket, "getaddrinfo", getaddrinfo)
        result = run(None, [], 0, open_browser=False, static=pages, host="localhost")
        assert result == EXIT_USAGE
        assert capsys.readouterr().err == (
            "ddd: --host resolves to 192.168.1.50, beyond this computer's loopback; --port 0 "
            "lets the system pick a free one there, which cannot be published in advance, so "
            "give a fixed --port too\n"
        )

    def test_localhost_resolving_beyond_loopback_warns_and_opens_no_browser(
        self, pages, monkeypatch, capsys
    ) -> None:
        """Same as ``localhost`` resolving to a LAN address above, but with a fixed port: it
        serves, warns once and opens no browser, exactly as --host 0.0.0.0 does."""

        def getaddrinfo(host, port, family, kind):
            return [(family, kind, 0, "", ("192.168.1.50", port))]

        real_init = GuiServer.__init__
        received: list[tuple[str, int]] = []

        def binds_loopback_for_real(self, api, static, port=0, host="127.0.0.1"):
            received.append((host, port))
            # Never 192.168.1.50 for real, for the same reason as every such fake in this
            # file: this is about what run() decides from the address, not about a real
            # socket answering on a LAN interface in a test.
            real_init(self, api, static, 0)

        monkeypatch.setattr(module.socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(GuiServer, "__init__", binds_loopback_for_real)
        monkeypatch.setattr(Session, "start", lambda self: None)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: None)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        opened: list[str] = []
        monkeypatch.setattr(module.webbrowser, "open", opened.append)

        result = run(None, [], 8123, open_browser=True, static=pages, host="localhost")

        assert result == EXIT_OK
        assert received == [("192.168.1.50", 8123)]
        assert "listening on 192.168.1.50:" in capsys.readouterr().err
        assert opened == []

    @pytest.mark.parametrize("open_browser", [True, False])
    def test_it_prints_its_address_serves_and_exits_cleanly_when_interrupted(
        self, project_file, pages, monkeypatch, capsys, open_browser
    ) -> None:
        opener = Opened()
        stopped: list[bool] = []
        monkeypatch.setattr(module.webbrowser, "open", opener)
        monkeypatch.setattr(Session, "start", lambda self: None)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: stopped.append(True))

        def interrupted(self, poll_interval=0.5):
            raise KeyboardInterrupt

        monkeypatch.setattr(GuiServer, "serve_forever", interrupted)
        assert run(project_file, [], 0, open_browser=open_browser, static=pages) == EXIT_OK
        (line,) = capsys.readouterr().out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")
        assert "/open?token=" in line
        if open_browser:
            code_from(line, opener.wait())
        else:
            assert opener.addresses == []
        assert stopped == [True]

    def test_a_browser_that_never_returns_does_not_hold_up_serving(
        self, project_file, pages, monkeypatch
    ) -> None:
        """A BROWSER line with no trailing '&' makes webbrowser.open build a GenericBrowser,
        whose open() waits for the browser to exit (p.wait()) before returning - and headless
        Chrome never exits on its own. A console browser such as lynx or w3m waits the same
        way. The launch now runs its opener off the thread that serves, so a browser that
        blocks here - simulated with an Event nothing sets - never holds run() up before it
        reaches serve_forever()."""
        monkeypatch.setattr(Session, "start", lambda self: None)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: None)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        entered = threading.Event()
        released = threading.Event()
        opened: list[str] = []
        daemon: list[bool] = []

        def never_returns(address: str) -> None:
            opened.append(address)
            daemon.append(threading.current_thread().daemon)
            entered.set()
            # Well beyond bounded_run's own 10 s join: the ablation that calls this opener
            # on the serving thread itself must lose that race by a wide margin, not by the
            # milliseconds between thread.start() and join() - only the ablation's kill, not
            # this passing run, waits anywhere near this long; it is released long before.
            released.wait(timeout=30)

        monkeypatch.setattr(module.webbrowser, "open", never_returns)

        assert bounded_run(project_file, [], 0, open_browser=True, static=pages) == EXIT_OK
        assert entered.wait(timeout=5), "the opener was never called"
        assert len(opened) == 1
        assert daemon == [True]  # so it never holds ddd gui from exiting either
        released.set()

    def test_a_server_shut_down_from_elsewhere_also_ends_cleanly(self, pages, monkeypatch) -> None:
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert run(None, [], 0, open_browser=False, static=pages) == EXIT_OK

    def test_every_way_out_ends_the_analyser_and_the_poller(
        self, project_file, pages, monkeypatch, capsys
    ) -> None:
        """Both are started before the project is opened, so a way out before anything is served
        - a file that is no project, an address that cannot be bound - has them to end as much
        as the server shutting down has."""

        def running() -> list[str]:
            names = ("ddd-gui-analyse", "ddd-gui-poll")
            return sorted(thread.name for thread in threading.enumerate() if thread.name in names)

        before = running()
        not_a_project = project_file.parent / "a.ddd.json"
        assert bounded_run(not_a_project, [], 0, open_browser=False, static=pages) == EXIT_USAGE
        assert running() == before

        def refuses_the_address(self, api, static, port=0, host="127.0.0.1"):
            raise OSError("Cannot assign requested address")

        with monkeypatch.context() as refusing:
            refusing.setattr(GuiServer, "__init__", refuses_the_address)
            assert bounded_run(project_file, [], 8123, open_browser=False, static=pages) == (
                EXIT_USAGE
            )
        assert running() == before

        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert bounded_run(project_file, [], 0, open_browser=False, static=pages) == EXIT_OK
        assert running() == before

    def test_it_serves_while_the_projects_first_analysis_runs(
        self, project_file, pages, monkeypatch, capsys
    ) -> None:
        """The first analysis runs on the analyser's thread, and the address is printed and
        served at once: the project open, no revision of it yet, its analysis still running."""
        monkeypatch.setattr(module, "Session", Gated)
        served: list[tuple[Path | None, Revision | None, bool]] = []

        def serve(self, poll_interval=0.5):
            session = self.api.session
            begun(session)
            served.append((session.project, session.revision, session.snapshot().analysing))
            session.gate.set()

        monkeypatch.setattr(GuiServer, "serve_forever", serve)
        assert bounded_run(project_file, [], 0, open_browser=False, static=pages) == EXIT_OK
        assert served == [(project_file.resolve(), None, True)]
        (line,) = capsys.readouterr().out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")


def free_port() -> int:
    """A port of 127.0.0.1 that nothing holds, picked by the system and let go at once: for a
    test that must name a port before anything serves on it."""
    with socket.socket() as picked:
        picked.bind(("127.0.0.1", 0))
        return int(picked.getsockname()[1])


def holding(port: int) -> socket.socket:
    """A stranger's socket bound on ``[::1]`` at ``port``, with no option set, and never listened
    on: another program holding ``localhost`` there. The caller closes it."""
    stranger = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        stranger.bind(("::1", port))
    except OSError:
        stranger.close()
        raise
    return stranger


class TestIPv6Held:
    """Spec §6.2: on loopback, ``ddd gui`` binds ``[::1]`` on its port beside its IPv4 socket, and
    never listens there. A browser opening ``localhost:<port>`` tries ``[::1]`` first: part 18b's
    final review measured a program listening there receive the pasted address, token and all,
    in Chrome 153, three times of three. Real sockets, except where a test says otherwise."""

    @pytest.fixture
    def started(self, tmp_path: Path, pages: Path) -> Iterator[GuiServer]:
        """A server on a port of the system's choosing, serving nothing: the hold is made as it
        binds, before anything is served."""
        server = GuiServer(Api(Session(tmp_path)), pages)
        try:
            yield server
        finally:
            server.server_close()

    @staticmethod
    def binds(address: str, reusing: bool, port: int) -> bool:
        """Whether a stranger's ``IPV6_V6ONLY`` socket binds ``address`` at ``port``, with
        ``SO_REUSEADDR`` set or not."""
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as stranger:
            stranger.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            if reusing:
                stranger.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                stranger.bind((address, port))
            except OSError:
                return False
            return True

    def test_ipv6_is_held_beside_the_port(self, started) -> None:
        """A stranger cannot bind ``[::1]`` there, not even with ``SO_REUSEADDR`` - which Linux
        honours for a port nobody listens on only when both sockets set it, and which Windows
        honours over any socket not bound with ``SO_EXCLUSIVEADDRUSE`` - nor ``[::]``, whose
        listener would take the connections the hold never accepts: Microsoft documents that
        an exclusive bind of a specific address shuts a wildcard bind out, where Windows'
        default lets the two share the port. A connection there is refused: bound, and never
        listened on. The hold reads ``IPV6_V6ONLY``, but Linux turns that on itself for any
        socket bound to ``::1`` (a fresh socket there reads 0, and 1 once bound), so the
        option's own call is pinned by the tests that note each option set."""
        strangers = [(address, reusing) for address in ("::1", "::") for reusing in (False, True)]
        let_in = [stranger for stranger in strangers if self.binds(*stranger, started.port)]
        assert let_in == []
        # Refused at once on Linux, and after about two seconds of retries on Windows.
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("::1", started.port), timeout=10).close()
        assert started.held is not None
        assert started.held.getsockname()[:2] == ("::1", started.port)
        assert started.held.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1

    def test_the_ipv4_port_is_not_shared_either(self, started) -> None:
        """Windows lets a socket that sets ``SO_REUSEADDR`` bind a port another socket listens
        on, unless that one was bound with ``SO_EXCLUSIVEADDRUSE``. Linux shares no port that a
        socket listens on, so this holds there with or without the option."""
        with socket.socket() as stranger:
            stranger.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError):
                stranger.bind(("127.0.0.1", started.port))

    def test_the_hold_ends_with_the_server(self, tmp_path, pages) -> None:
        server = GuiServer(Api(Session(tmp_path)), pages)
        try:
            assert server.held is not None
        finally:
            server.server_close()
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as after:
            after.bind(("::1", server.port))

    def test_the_ipv4_port_is_let_go_when_ipv6_is_held(self, tmp_path, pages) -> None:
        """A server refused for ``[::1]`` closes the IPv4 socket it had bound, rather than leave
        it to the collector: bound again here while the refusal, and so the server it was
        raised in, is still held, as ``run`` holds it while it says why."""
        port = free_port()
        with holding(port):
            with pytest.raises(module.IPv6HeldError) as refused:
                GuiServer(Api(Session(tmp_path)), pages, port)
            with socket.socket() as after:
                after.bind(("127.0.0.1", port))
        assert isinstance(refused.value.__cause__, OSError)

    def test_a_fixed_port_held_on_ipv6_is_refused_naming_it(
        self, pages, monkeypatch, capsys
    ) -> None:
        """Spec §6.2: refused as a taken ``--port`` is, naming ``[::1]``. A port given is that
        port or nothing, so it is tried once. Each of these tests of the retry runs ``run``
        bounded, so that a loop that never ends fails it rather than hang the suite."""
        port = free_port()
        held_beside = module._held_beside
        asked: list[int] = []

        def counted(host: str, at: int) -> socket.socket | None:
            asked.append(at)
            return held_beside(host, at)

        monkeypatch.setattr(module, "_held_beside", counted)
        with holding(port):
            assert bounded_run(None, (), port, open_browser=False, static=pages) == EXIT_USAGE
        assert asked == [port]
        assert capsys.readouterr().err == (
            f"ddd: cannot serve 127.0.0.1 on port {port}: another program holds [::1]:{port}, "
            f"where a browser opening localhost:{port} would reach it\n"
        )

    def test_port_zero_tries_again_when_ipv6_is_held(self, pages, monkeypatch, capsys) -> None:
        """Spec §6.2: ``--port 0`` serves on a port free on both addresses. The first pick held,
        it picks again, and says nothing of the first."""
        held_beside = module._held_beside
        asked: list[int] = []

        def held_the_first_time(host: str, at: int) -> socket.socket | None:
            asked.append(at)
            if len(asked) == 1:
                raise module.IPv6HeldError(module._IPV6_HELD.format(port=at))
            return held_beside(host, at)

        served: list[tuple[int, tuple[str, int]]] = []

        def serve(self, poll_interval=0.5):
            served.append((self.port, self.held.getsockname()[:2]))

        monkeypatch.setattr(module, "_held_beside", held_the_first_time)
        monkeypatch.setattr(GuiServer, "serve_forever", serve)
        assert bounded_run(None, (), 0, open_browser=False, static=pages) == EXIT_OK
        assert len(asked) == 2
        assert served == [(asked[1], ("::1", asked[1]))]
        captured = capsys.readouterr()
        (line,) = captured.out.splitlines()
        assert line.startswith(f"ddd gui (preview) serving http://127.0.0.1:{asked[1]}/open?")
        assert captured.err == ""

    def test_port_zero_gives_up_after_its_tries(self, pages, monkeypatch, capsys) -> None:
        """Every pick held, by a stranger bound there before the server looks: refused after
        ``PORT_TRIES`` picks, naming the last."""
        held_beside = module._held_beside
        asked: list[int] = []
        strangers: dict[int, socket.socket] = {}

        def always_held(host: str, at: int) -> socket.socket | None:
            asked.append(at)
            if at not in strangers:
                strangers[at] = holding(at)
            return held_beside(host, at)

        monkeypatch.setattr(module, "_held_beside", always_held)
        try:
            assert bounded_run(None, (), 0, open_browser=False, static=pages) == EXIT_USAGE
        finally:
            for stranger in strangers.values():
                stranger.close()
        assert len(asked) == module.PORT_TRIES
        last = asked[-1]
        assert capsys.readouterr().err == (
            f"ddd: cannot serve 127.0.0.1 on port 0: another program holds [::1]:{last}, "
            f"where a browser opening localhost:{last} would reach it\n"
        )

    @pytest.mark.parametrize("missing", ["the-family", "the-address"])
    def test_no_ipv6_loopback_holds_nothing_and_says_nothing(
        self, pages, monkeypatch, capsys, missing
    ) -> None:
        """A computer with no IPv6 - no ``AF_INET6`` at all, or no ``::1`` to bind - has no
        ``[::1]`` for a browser to try first: nothing is held, and nothing said of it. Through a
        socket that refuses either, as such a computer does."""
        port = free_port()
        families: list[int] = []
        made: list[socket.socket] = []

        class WithoutIPv6(socket.socket):
            def __init__(self, family: int = -1, *rest: Any, **keywords: Any) -> None:
                families.append(family)
                if missing == "the-family" and family == socket.AF_INET6:
                    raise OSError(errno.EAFNOSUPPORT, "Address family not supported by protocol")
                super().__init__(family, *rest, **keywords)
                made.append(self)

            def bind(self, address: Any) -> None:
                if self.family == socket.AF_INET6:
                    raise OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address")
                super().bind(address)

        served: list[socket.socket | None] = []
        monkeypatch.setattr(socket, "socket", WithoutIPv6)
        monkeypatch.setattr(
            GuiServer, "serve_forever", lambda self, poll_interval=0.5: served.append(self.held)
        )
        assert module._held_beside("127.0.0.1", port) is None
        assert run(None, (), 0, open_browser=False, static=pages) == EXIT_OK
        assert served == [None]
        assert families.count(socket.AF_INET6) == 2
        # Each socket that could not bind ::1 is closed, not left to the collector.
        bound_nothing = [one.fileno() for one in made if one.family == socket.AF_INET6]
        assert bound_nothing == ([] if missing == "the-family" else [-1, -1])
        captured = capsys.readouterr()
        (line,) = captured.out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")
        assert captured.err == ""

    @pytest.mark.parametrize(
        ("refusal", "held"),
        [(errno.EADDRINUSE, True), (errno.EACCES, True), (errno.EPERM, False)],
        ids=["in-use", "access", "not-permitted"],
    )
    def test_a_socket_refused_its_bind_is_closed(self, monkeypatch, refusal, held) -> None:
        """Through a socket whose bind is refused. ``EADDRINUSE`` and ``EACCES`` - the errno
        CPython gives Windows' ``WSAEACCES`` - are a port another socket holds; any other refusal
        says nothing of a program, and is raised as an ``OSError`` naming ``[::1]`` (P19a-12).
        Either way the socket is closed, and the system's own refusal is the cause."""
        made: list[socket.socket] = []

        class Refused(socket.socket):
            def bind(self, address: Any) -> None:
                made.append(self)
                raise OSError(refusal, os.strerror(refusal))

        monkeypatch.setattr(socket, "socket", Refused)
        with pytest.raises(OSError) as raised:
            module._held_beside("127.0.0.1", 8123)
        assert isinstance(raised.value, module.IPv6HeldError) is held
        assert isinstance(raised.value.__cause__, OSError)
        assert raised.value.__cause__.errno == refusal
        assert [one.fileno() for one in made] == [-1]

    def test_a_hold_that_cannot_be_made_refuses_the_start(self, pages, monkeypatch, capsys) -> None:
        """P19a-12: nothing is held in silence only where the system says there is no IPv6
        loopback. Any other error making the hold's socket - here too many files open - refuses
        the start in the system's own words, naming ``[::1]``, and is not retried on ``--port 0``,
        where another pick would meet it again. The IPv4 port is let go before the refusal is
        printed, while the error still holds the server it was raised in."""
        real_socket = socket.socket
        made: list[int] = []
        bound: list[int] = []

        class TooManyFiles(socket.socket):
            def __init__(self, family: int = -1, *rest: Any, **keywords: Any) -> None:
                made.append(family)
                if family == socket.AF_INET6:
                    raise OSError(errno.EMFILE, "Too many open files")
                super().__init__(family, *rest, **keywords)

            def bind(self, address: Any) -> None:
                super().bind(address)
                bound.append(self.getsockname()[1])

        refused = module._refused

        def bound_again_first(value: str, port: int, error: Exception) -> int:
            with real_socket() as again:
                again.bind(("127.0.0.1", bound[-1]))
            return refused(value, port, error)

        monkeypatch.setattr(socket, "socket", TooManyFiles)
        monkeypatch.setattr(module, "_refused", bound_again_first)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert bounded_run(None, (), 0, open_browser=False, static=pages) == EXIT_USAGE
        assert made == [socket.AF_INET, socket.AF_INET6]
        (port,) = bound
        assert capsys.readouterr().err == (
            f"ddd: cannot serve 127.0.0.1 on port 0: cannot hold [::1]:{port} beside it: "
            "[Errno 24] Too many open files\n"
        )

    def test_a_socket_that_cannot_be_made_is_raised_as_the_cause(self, monkeypatch) -> None:
        """The refusal ``run`` prints for a hold that cannot be made keeps the system's error as
        its cause, and is no held port, which ``--port 0`` would pick again for."""

        class TooManyFiles(socket.socket):
            def __init__(self, family: int = -1, *rest: Any, **keywords: Any) -> None:
                if family == socket.AF_INET6:
                    raise OSError(errno.EMFILE, "Too many open files")
                super().__init__(family, *rest, **keywords)

        monkeypatch.setattr(socket, "socket", TooManyFiles)
        with pytest.raises(OSError) as raised:
            module._held_beside("127.0.0.1", 8123)
        assert not isinstance(raised.value, module.IPv6HeldError)
        assert isinstance(raised.value.__cause__, OSError)
        assert raised.value.__cause__.errno == errno.EMFILE

    def test_a_hold_refused_for_another_reason_refuses_the_start(
        self, pages, monkeypatch, capsys
    ) -> None:
        """P19a-12: only a port another socket holds is held. A bind of ``::1`` refused for any
        other reason - here ``EPERM``, as a security module or a cgroup's bind hook answers - is
        no proof of another program: it refuses the start in the system's own words, naming
        ``[::1]``, and is not retried on ``--port 0``."""
        asked: list[int] = []

        class NotPermitted(socket.socket):
            def bind(self, address: Any) -> None:
                if self.family == socket.AF_INET6:
                    asked.append(address[1])
                    raise OSError(errno.EPERM, "Operation not permitted")
                super().bind(address)

        monkeypatch.setattr(socket, "socket", NotPermitted)
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert bounded_run(None, (), 0, open_browser=False, static=pages) == EXIT_USAGE
        (port,) = asked
        assert capsys.readouterr().err == (
            f"ddd: cannot serve 127.0.0.1 on port 0: cannot hold [::1]:{port} beside it: "
            "[Errno 1] Operation not permitted\n"
        )

    def test_the_hold_is_closed_though_the_ipv4_socket_will_not_close(
        self, tmp_path, pages
    ) -> None:
        """Closed with the server on every path, a failing close of the IPv4 socket included."""
        server = GuiServer(Api(Session(tmp_path)), pages)
        served_on = server.socket

        class Unclosable:
            def close(self) -> None:
                raise OSError(errno.EBADF, "Bad file descriptor")

        server.socket = Unclosable()
        try:
            with pytest.raises(OSError, match="Bad file descriptor"):
                server.server_close()
            assert server.held is not None
            assert server.held.fileno() == -1
        finally:
            served_on.close()

    def test_beyond_loopback_holds_nothing(self) -> None:
        """``--host`` beyond loopback, as in a container: the browser is on the host, and the
        container's own ``[::1]`` is out of its reach."""
        port = free_port()
        assert module._held_beside("0.0.0.0", port) is None
        assert module._held_beside("192.0.2.1", port) is None

    @staticmethod
    def given(
        tmp_path: Path, pages: Path, monkeypatch: pytest.MonkeyPatch, *, exclusive: bool
    ) -> dict[int, list[tuple[Any, ...]]]:
        """What each socket of a server is given, by family: every option set on it, then its
        bind. Through a socket that notes each, and sets each but Windows' own exclusive option,
        whose value Linux refuses."""
        given: dict[int, list[tuple[Any, ...]]] = {socket.AF_INET: [], socket.AF_INET6: []}

        class Noting(socket.socket):
            def setsockopt(self, level: int, option: int, value: Any, *rest: Any) -> None:
                given[self.family].append((level, option, value))
                if (level, option) != (socket.SOL_SOCKET, module._SO_EXCLUSIVEADDRUSE):
                    super().setsockopt(level, option, value, *rest)

            def bind(self, address: Any) -> None:
                given[self.family].append(("bind",))
                super().bind(address)

        monkeypatch.setattr(module, "_EXCLUSIVE", exclusive)
        monkeypatch.setattr(socket, "socket", Noting)
        GuiServer(Api(Session(tmp_path)), pages).server_close()
        return given

    @staticmethod
    def reusing() -> list[tuple[Any, ...]]:
        """``SO_REUSEADDR``, where ``http.server`` sets it on the socket it serves on: everywhere
        but Windows (``test_the_windows_server_does_not_share_a_port``)."""
        if GuiServer.allow_reuse_address:
            return [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
        return []

    def test_windows_binds_both_sockets_exclusively(self, tmp_path, pages, monkeypatch) -> None:
        """Spec §6.2: on Windows, both sockets take ``SO_EXCLUSIVEADDRUSE`` before their bind, so
        that no program can share either port through ``SO_REUSEADDR``. The ``[::1]`` socket
        never sets ``SO_REUSEADDR`` itself."""
        given = self.given(tmp_path, pages, monkeypatch, exclusive=True)
        exclusive = (socket.SOL_SOCKET, module._SO_EXCLUSIVEADDRUSE, 1)
        reusing = self.reusing()
        assert given[socket.AF_INET] == [exclusive, *reusing, ("bind",)]
        assert given[socket.AF_INET6] == [
            (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1),
            exclusive,
            ("bind",),
        ]

    def test_elsewhere_neither_socket_is_bound_exclusively(
        self, tmp_path, pages, monkeypatch
    ) -> None:
        given = self.given(tmp_path, pages, monkeypatch, exclusive=False)
        reusing = self.reusing()
        assert given[socket.AF_INET] == [*reusing, ("bind",)]
        assert given[socket.AF_INET6] == [(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1), ("bind",)]

    def test_a_port_served_on_is_served_on_again_at_once(self, tmp_path, pages) -> None:
        """A fixed ``--port`` given again the moment ``ddd gui`` stopped. Microsoft documents that
        a port whose listening socket was bound with ``SO_EXCLUSIVEADDRUSE`` cannot be bound
        again while a connection it accepted is still active. Here the server closes first,
        having answered ``Connection: close`` to a client that reads to its end, so the server's
        end of that connection waits out ``TIME_WAIT`` on the port itself - measured with ``ss``
        on Linux, where ``SO_REUSEADDR`` is what lets the port be bound again."""
        first = GuiServer(Api(Session(tmp_path)), pages)
        asked = f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{first.port}\r\nConnection: close\r\n\r\n"
        thread = threading.Thread(target=first.serve_forever, daemon=True)
        thread.start()
        try:
            status, _ = raw_answer(first, asked.encode("ascii"))
        finally:
            first.shutdown()
            first.server_close()
            thread.join(timeout=10)
        assert status == 200
        again = GuiServer(Api(Session(tmp_path)), pages, first.port)
        try:
            assert again.held is not None
        finally:
            again.server_close()

    def test_sockets_are_bound_exclusively_on_windows_alone(self) -> None:
        assert module._EXCLUSIVE is (sys.platform == "win32")

    def test_the_exclusive_option_is_windows_own(self) -> None:
        """``~SO_REUSEADDR`` on Windows, where ``SO_REUSEADDR`` is 4: read from the socket module
        there, and the same value named elsewhere, where only this suite sets it."""
        assert module._SO_EXCLUSIVEADDRUSE == -5

    def test_port_zero_is_tried_on_five_ports(self) -> None:
        assert module.PORT_TRIES == 5


class TestTheLaunch:
    def test_the_browser_is_handed_a_fresh_code_and_never_the_token(self, server) -> None:
        opened: list[str] = []
        assert launched(server, opened.append) is None
        (address,) = opened
        code = code_from(f"ddd gui (preview) serving {server.address}", address)
        response, data = exchange(server, {"code": code})
        assert (response.status, json.loads(data)) == (200, {"token": server.token})


def test_the_windows_server_does_not_share_a_port() -> None:
    assert GuiServer.allow_reuse_address is (sys.platform != "win32")
