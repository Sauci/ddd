"""The server of ddd gui, over real HTTP: who may ask, what is served, and how it starts."""

from __future__ import annotations

import dataclasses
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
from collections.abc import Callable, Iterator
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
    project,
    stopped,
    write_tree,
)
from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.editing import fingerprint
from ddd.gui import api as api_module
from ddd.gui import server as module
from ddd.gui.api import Api, Reply
from ddd.gui.server import (
    _ELSEWHERE,
    _FORBIDDEN,
    BUSY,
    CODE_SECONDS,
    MAX_BODY,
    MAX_CONNECTIONS,
    REFUSAL_SECONDS,
    SECURITY_HEADERS,
    SIGN_IN_PAGE,
    SIGNED_IN_PAGE,
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


def cookie(server: GuiServer) -> str:
    """The name a server signs a page in under, which carries its port."""
    return f"ddd-gui-{server.port}"


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
        sent["Cookie"] = f"{cookie(server)}={server.token}"
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
        + f"Cookie: {cookie(server)}={server.token}\r\n".encode("ascii")
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
    def test_the_token_is_swapped_for_a_strict_cookie_and_the_project_page(self, server) -> None:
        response, data = ask(server, "GET", f"/open?token={server.token}", signed_in=False)
        assert response.status == 200
        assert response.getheader("Location") is None
        assert response.getheader("Set-Cookie") == (
            f"ddd-gui-{server.port}={server.token}; HttpOnly; SameSite=Strict; Path=/"
        )
        assert response.getheader("Content-Type") == "text/html; charset=utf-8"
        # Its URL holds the token: a shared cache must never store it, nor a browser replay
        # it from history.
        assert response.getheader("Cache-Control") == "no-store"
        assert data == SIGNED_IN_PAGE.format(target="/project").encode("utf-8")

    def test_the_page_refreshes_to_its_target_without_a_script(self) -> None:
        """/open may be reached cross-site - the token or a launch code pasted or clicked
        from anywhere - and a SameSite=Strict cookie does not reliably follow a redirect
        chain that began cross-site; a refresh this page makes itself is a fresh,
        same-origin navigation, which the cookie does follow. A meta refresh, not a script:
        no script is needed, so none is written, and the content security policy has
        nothing to permit either way. The link below the refresh is the fallback for a
        browser that blocks it, such as Firefox's accessibility.blockautorefresh."""
        page = SIGNED_IN_PAGE.format(target="/project")
        assert '<meta http-equiv="refresh" content="0; url=/project">' in page
        assert '<a href="/project">Open ddd gui</a>' in page
        assert "<script" not in page

    def test_a_project_being_analysed_signs_in_to_its_own_page(
        self, project_file: Path, pages: Path
    ) -> None:
        session = Gated(project_file.parent)
        session.start()
        try:
            session.open(project_file)
            begun(session)
            for server in serving(Api(session, project_file), pages):
                response, data = ask(server, "GET", f"/open?token={server.token}", signed_in=False)
                assert (response.status, data) == (
                    200,
                    SIGNED_IN_PAGE.format(target="/project").encode("utf-8"),
                )
                assert session.revision is None
        finally:
            session.gate.set()
            stopped(session)

    def test_without_an_open_project_the_page_refreshes_to_the_start_page(
        self, project_file, pages
    ) -> None:
        for started in serving(Api(Session(project_file.parent)), pages):
            _, data = ask(started, "GET", f"/open?token={started.token}", signed_in=False)
            assert data == SIGNED_IN_PAGE.format(target="/").encode("utf-8")

    @pytest.mark.parametrize("signed_in", [False, True])
    @pytest.mark.parametrize("query", ["", "?token=wrong", "?token=%C3%A9"])
    def test_a_wrong_or_missing_token_is_refused(self, server, query, signed_in, capsys) -> None:
        """Refused whether or not the request already carries this server's cookie: the
        cookie alone does not turn a wrong or missing token into a sign-in, which only the
        exception for a code the ruling names - never a token - does."""
        response, data = ask(server, "GET", f"/open{query}", signed_in=signed_in)
        assert response.status == 403
        assert b"Open the address" in data
        # A refusal's URL held the guess that failed: just as worth never storing or replaying.
        assert response.getheader("Cache-Control") == "no-store"
        assert capsys.readouterr().err == ""

    def test_a_code_is_as_strong_as_the_token(self, server) -> None:
        """The ruling's two numbers, pinned by literal: 32 random bytes behind each - the
        strength secrets.token_urlsafe(32) always renders as a 43-character string."""
        assert TOKEN_BYTES == 32
        assert len(server.issue_code()) == 43
        assert len(server.token) == 43

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

    def test_a_code_signs_a_browser_in_exactly_as_the_token_does(self, server) -> None:
        code = server.issue_code()
        response, data = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert response.status == 200
        assert response.getheader("Set-Cookie") == (
            f"ddd-gui-{server.port}={server.token}; HttpOnly; SameSite=Strict; Path=/"
        )
        assert data == SIGNED_IN_PAGE.format(target="/project").encode("utf-8")

    def test_a_code_signs_in_once_and_a_second_presentation_is_refused(
        self, server, capsys
    ) -> None:
        code = server.issue_code()
        first, _ = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert first.status == 200
        assert capsys.readouterr().err == ""
        second, data = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert second.status == 403
        assert b"Open the address" in data
        assert capsys.readouterr().err == (
            "ddd gui: a launch code arrived that was already spent, or had simply expired; "
            "if your browser did not just sign in on its own, something else on this "
            "computer may have used it instead, so restart ddd gui if your browser is not "
            "signed in\n"
        )

    def test_a_wrong_code_is_refused_and_leaves_the_right_one_waiting(self, server, capsys) -> None:
        """A guess that is not the one outstanding code is refused on its own, and does not
        spend that code: a stranger trying codes cannot grief the browser the launch is
        waiting for. It prints nothing: unlike a spent or expired code, it was never the
        real one."""
        code = server.issue_code()
        wrong, data = ask(server, "GET", "/open?code=wrong", signed_in=False)
        assert wrong.status == 403
        assert b"Open the address" in data
        assert capsys.readouterr().err == ""
        right, _ = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert right.status == 200

    def test_a_spent_code_already_signed_in_answers_the_page_not_a_refusal(
        self, server, capsys
    ) -> None:
        """A browser's own prefetch of the /open?code= address, or its navigating there a
        second time once the first already set the cookie, presents a code that by then
        looks exactly like a stranger's guess - the cookie already carried is what tells the
        two apart, and only it is let through to the page rather than a 403. Nothing is
        printed: this request carries the cookie, so it is not the case the terminal line
        warns about."""
        code = server.issue_code()
        first, _ = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert first.status == 200
        second, data = ask(server, "GET", f"/open?code={code}")  # signed_in=True by default
        assert second.status == 200
        assert data == SIGNED_IN_PAGE.format(target="/project").encode("utf-8")
        assert capsys.readouterr().err == ""

    def test_the_tokens_own_value_is_not_accepted_as_a_code(self, server) -> None:
        server.issue_code()  # a code is pending during the window that matters
        response, data = ask(server, "GET", f"/open?code={server.token}", signed_in=False)
        assert response.status == 403
        assert b"Open the address" in data

    def test_an_unused_code_expires_after_60_seconds(self, project_file, pages, capsys) -> None:
        assert CODE_SECONDS == 60
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS
            response, data = ask(started, "GET", f"/open?code={code}", signed_in=False)
            assert response.status == 403
            assert b"Open the address" in data
            assert capsys.readouterr().err == (
                "ddd gui: a launch code arrived that was already spent, or had simply "
                "expired; if your browser did not just sign in on its own, something else "
                "on this computer may have used it instead, so restart ddd gui if your "
                "browser is not signed in\n"
            )

    def test_a_code_still_signs_in_a_moment_before_60_seconds(self, project_file, pages) -> None:
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS - 1
            response, _ = ask(started, "GET", f"/open?code={code}", signed_in=False)
            assert response.status == 200

    def test_the_api_without_the_cookie_is_unauthorised(self, server) -> None:
        response, data = ask(server, "GET", "/api/session", signed_in=False)
        assert response.status == 401
        assert json.loads(data)["error"] == "unauthorised"

    def test_a_page_without_the_cookie_says_where_to_sign_in(self, server) -> None:
        response, data = ask(server, "GET", "/", signed_in=False)
        assert (response.status, b"Open the address" in data) == (401, True)
        assert response.getheader("Content-Type") == "text/html; charset=utf-8"

    def test_a_cookie_with_another_value_is_not_signed_in(self, server) -> None:
        forged = {"Cookie": f"{cookie(server)}=forged"}
        response, _ = ask(server, "GET", "/api/session", signed_in=False, headers=forged)
        assert response.status == 401

    def test_a_second_server_signs_in_under_a_name_of_its_own(
        self, server, project_file, pages
    ) -> None:
        """A browser sends every cookie of 127.0.0.1 to every port. Under one name, opening a
        second ddd gui replaced the first one's cookie and signed its page out - and a second
        server is how two projects are looked at side by side."""
        for other in serving(Api(Session(project_file.parent)), pages):
            both = {"Cookie": f"{cookie(other)}={other.token}; {cookie(server)}={server.token}"}
            for asked in (server, other):
                response, _ = ask(asked, "GET", "/api/session", signed_in=False, headers=both)
                assert response.status == 200
            theirs = {"Cookie": f"{cookie(other)}={other.token}"}
            response, _ = ask(server, "GET", "/api/session", signed_in=False, headers=theirs)
            assert response.status == 401

    @pytest.mark.parametrize("path", ["/api/session", "/project"])
    @pytest.mark.parametrize("foreign", FOREIGN_COOKIES)
    def test_a_cookie_another_app_set_does_not_get_in_the_way(self, server, path, foreign) -> None:
        """The standard library's cookie parser stopped reading at the first two of these, in
        silence, which signed the page out; it raised at the third, which left every request
        unanswered."""
        sent = {"Cookie": f"{foreign}; {cookie(server)}={server.token}"}
        response, _ = ask(server, "GET", path, signed_in=False, headers=sent)
        assert response.status == 200

    def test_cookies_of_other_apps_alone_are_not_signed_in(self, server) -> None:
        sent = {"Cookie": "; ".join(FOREIGN_COOKIES)}
        response, data = ask(server, "GET", "/api/session", signed_in=False, headers=sent)
        assert (response.status, json.loads(data)["error"]) == (401, "unauthorised")

    def test_a_stale_cookie_of_this_servers_name_beside_the_right_one_signs_in(
        self, server
    ) -> None:
        sent = {"Cookie": f"{cookie(server)}={server.token}; {cookie(server)}=stale"}
        response, _ = ask(server, "GET", "/api/session", signed_in=False, headers=sent)
        assert response.status == 200


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
        sends it this server's SameSite=Strict cookie: probed against a1da6ce, its GET of
        /api/compare ran the comparison, plugins and all."""
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

    def test_another_page_is_refused_before_the_cookie_is_read(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", signed_in=False, headers={"Sec-Fetch-Site": "same-site"}
        )
        assert response.status == 403

    def test_a_post_from_another_page_is_refused_before_the_cookie_is_read(self, server) -> None:
        """The POST sibling of test_another_page_is_refused_before_the_cookie_is_read: the gate
        runs before ``_signed_in`` and before the POST rule alike, so a POST marked same-site
        is refused by the gate's own sentence, not by ``_FORBIDDEN``, without ever reaching the
        cookie."""
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
        """A sign-in is answered wherever the address was opened from, since the token or the
        code is what ``/open`` checks - never ``Sec-Fetch-Site`` or ``Origin``. ``cross-site``
        is kept as the value a browser marks least trustworthy; a real launch arrives marked
        ``none`` instead (a navigation the opener started), which signs in just the same."""
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
        since ``_route`` answers ``/open`` before the gate is ever reached, for a code exactly
        as for the token - neither header is read there either."""
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

    def test_a_content_length_of_more_than_4300_digits_is_too_large_not_500(
        self, server, capsys
    ) -> None:
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
        connection.putheader("Cookie", f"{cookie(server)}={server.token}")
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
            f"Cookie: {cookie(server)}={server.token}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        status, _ = raw_answer(server, sent)
        assert status == 500
        printed = capsys.readouterr().err
        assert f"GET {path!r}" in printed
        assert "\x1b" not in printed

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


def looked_up(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every path ``ddd.gui.server`` asks ``os.path`` about from here on, in the order asked:
    the module's ``os`` swapped for one whose ``path`` records each question's path before
    answering it. That module's questions alone - anything else in the process that asks the
    file system something is not what these tests are about - and only the four ``_page``
    asks: a fifth fails the request, rather than going unrecorded."""
    asked: list[str] = []

    def recording(question: Callable[[Any], bool]) -> Callable[[Any], bool]:
        def recorded(path: Any) -> bool:
            asked.append(os.fspath(path))
            return question(path)

        return recorded

    questions = {
        name: recording(getattr(os.path, name))
        for name in ("isdir", "isfile", "isjunction", "islink")
    }
    path = types.SimpleNamespace(**questions)
    monkeypatch.setattr(module, "os", types.SimpleNamespace(path=path))
    return asked


def looped(first: Path, second: Path) -> None:
    """Two links naming each other, so that nothing is ever found through either. Made with
    :func:`directory_link`, which is a junction on Windows - where no link can name itself, a
    junction's target having to exist when it is made, and its own name not to."""
    second.mkdir()
    directory_link(first, second)
    second.rmdir()
    directory_link(second, first)


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
    token needed, since the gate and the cookie are both later than this."""

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
        request would, past this check - here as far as the cookie, which it does not carry."""
        sent = (
            f"GET http://127.0.0.1:{server.port}/ HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        assert status_of(server, sent) == 401


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
        # lets it be told from the next.
        signed_in = {"Cookie": f"{cookie(server)}={server.token}"}
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        try:
            asked = [
                self.again(connection, server, f"/open?token={server.token}"),
                self.again(connection, server, "/", **signed_in),
                self.again(connection, server, "/api/session", **signed_in),
                self.again(connection, server, "/api/nothing", **signed_in),
            ]
        finally:
            connection.close()
        assert [response.status for response, _ in asked] == [200, 200, 200, 404]
        assert [response.version for response, _ in asked] == [11, 11, 11, 11]
        assert [response.will_close for response, _ in asked] == [False] * 4
        assert asked[0][1] == SIGNED_IN_PAGE.format(target="/project").encode("utf-8")
        assert asked[1][1] == b"stand-in"
        assert json.loads(asked[2][1])["version"] == ddd.__version__

    def test_a_connection_nobody_is_using_is_closed(self, server, monkeypatch) -> None:
        # Its own deadline rather than IDLE_SECONDS: what is asserted is that the socket carries
        # one at all, and a test that waits half a minute to say so asserts nothing more.
        monkeypatch.setattr(module._Handler, "timeout", 0.05)
        signed_in = {"Cookie": f"{cookie(server)}={server.token}"}
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
    "GET /api/state?after=7 HTTP/1.1\r\n"
    "Host: 127.0.0.1:8123\r\n"
    "Connection: keep-alive\r\n"
    'sec-ch-ua: "Chromium";v="153", "Not.A/Brand";v="99"\r\n'
    "sec-ch-ua-mobile: ?0\r\n"
    'sec-ch-ua-platform: "Linux"\r\n'
    "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36\r\n"
    "Accept: */*\r\n"
    "Sec-Fetch-Site: same-origin\r\n"
    "Sec-Fetch-Mode: cors\r\n"
    "Sec-Fetch-Dest: empty\r\n"
    "Accept-Encoding: gzip, deflate, br, zstd\r\n"
    "Accept-Language: en-GB,en;q=0.9\r\n"
    f"Cookie: ddd-gui-8123={'t' * 43}; "
    + "; ".join(f"app-{n}-session={'s' * 120}" for n in range(32))
    + "\r\n\r\n"
).encode("ascii")
"""A request the size a browser sends this server, about 5 KB: its usual headers, and a cookie
header carrying, beside this server's own, what other apps on 127.0.0.1 have set - a browser
sends every one of them to every port."""


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
                    "Cookie": f"{cookie(server)}={server.token}",
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
    server's: the length of its request line and the number of its headers. Pinned here, each
    on a connection of its own, so that a server that stopped answering them would be caught.

    A refused request is sent only as far as the line it is refused at: a connection closed
    with bytes it never read is reset, and the answer can be lost with it."""

    def test_a_request_line_of_more_than_65536_bytes_is_answered_414(self, server) -> None:
        assert status_of(server, request_line(65537)) == 414

    def test_a_request_line_of_65536_bytes_is_read(self, server) -> None:
        end = f"Host: 127.0.0.1:{server.port}\r\nConnection: close\r\n\r\n".encode("ascii")
        assert status_of(server, request_line(65536) + end) == 401

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


class TestTheLaunch:
    def test_the_browser_is_handed_a_fresh_code_and_never_the_token(self, server) -> None:
        opened: list[str] = []
        assert launched(server, opened.append) is None
        (address,) = opened
        code = code_from(f"ddd gui (preview) serving {server.address}", address)
        response, data = ask(server, "GET", f"/open?code={code}", signed_in=False)
        assert (response.status, data) == (
            200,
            SIGNED_IN_PAGE.format(target="/project").encode("utf-8"),
        )


def test_the_windows_server_does_not_share_a_port() -> None:
    assert GuiServer.allow_reuse_address is (sys.platform != "win32")
