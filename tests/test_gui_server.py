"""The server of ddd gui, over real HTTP: who may ask, what is served, and how it starts."""

from __future__ import annotations

import http.client
import json
import shutil
import socket
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

import pytest

import ddd
from conftest import EXAMPLES, component, declare, project, write_tree
from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.editing import fingerprint
from ddd.gui import api as api_module
from ddd.gui import server as module
from ddd.gui.api import Api, Reply
from ddd.gui.server import MAX_BODY, GuiServer, run, static_directory
from ddd.gui.session import Session

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


def serving(api: Api, static: Path) -> Iterator[GuiServer]:
    server = GuiServer(api, static)
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


class TestSigningIn:
    def test_the_token_is_swapped_for_a_strict_cookie_and_the_project_page(self, server) -> None:
        response, _ = ask(server, "GET", f"/open?token={server.token}", signed_in=False)
        assert response.status == 303
        assert response.getheader("Location") == "/project"
        assert response.getheader("Set-Cookie") == (
            f"ddd-gui-{server.port}={server.token}; HttpOnly; SameSite=Strict; Path=/"
        )

    def test_without_an_open_project_the_redirect_is_to_the_start_page(
        self, project_file, pages
    ) -> None:
        for started in serving(Api(Session(project_file.parent)), pages):
            response, _ = ask(started, "GET", f"/open?token={started.token}", signed_in=False)
            assert response.getheader("Location") == "/"

    @pytest.mark.parametrize("query", ["", "?token=wrong", "?token=%C3%A9"])
    def test_a_wrong_or_missing_token_is_refused(self, server, query) -> None:
        response, data = ask(server, "GET", f"/open{query}", signed_in=False)
        assert response.status == 403
        assert b"Open the address" in data

    def test_the_api_without_the_cookie_is_unauthorised(self, server) -> None:
        response, data = ask(server, "GET", "/api/session", signed_in=False)
        assert response.status == 401
        assert json.loads(data)["error"] == "unauthorised"

    def test_a_page_without_the_cookie_says_where_to_sign_in(self, server) -> None:
        response, data = ask(server, "GET", "/", signed_in=False)
        assert (response.status, b"Open the address" in data) == (401, True)

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

    @pytest.mark.parametrize(
        ("origin", "content_type"),
        [
            (None, "application/json"),
            ("http://evil.example", "application/json"),
            ("http://127.0.0.1:1", "application/json"),
            ("OWN", "text/plain"),
        ],
    )
    def test_a_change_from_anywhere_but_this_page_is_forbidden(
        self, server, origin, content_type
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
        assert (response.status, json.loads(data)["error"]) == (403, "forbidden")

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
            ]
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

        monkeypatch.setitem(api_module._ROUTES, "/api/session", ("GET", failing))
        response, data = ask(server, "GET", "/api/session")
        assert response.status == 500
        assert response.getheader("Cache-Control") == "no-store"
        assert json.loads(data) == {
            "error": "internal",
            "message": "ddd gui failed on this request; the terminal it runs in shows why",
        }
        printed = capsys.readouterr().err
        assert "GET /api/session" in printed
        assert "RuntimeError: a defect" in printed

    def test_an_answer_json_cannot_spell_is_a_failure_rather_than_a_body_no_page_reads(
        self, server, monkeypatch, capsys
    ) -> None:
        """Python writes ``NaN`` by default, which no browser's parser reads."""

        def slipped(api: Api, query: object, body: object) -> Reply:
            return Reply(200, {"limit": float("nan")})

        monkeypatch.setitem(api_module._ROUTES, "/api/session", ("GET", slipped))
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

        monkeypatch.setitem(api_module._ROUTES, "/api/session", ("GET", gone))
        with pytest.raises(http.client.RemoteDisconnected):
            ask(server, "GET", "/api/session")
        assert capsys.readouterr().err == ""

    def test_a_page_that_went_away_mid_answer_is_not_reported(self, server, capsys) -> None:
        try:
            raise ConnectionResetError("the tab was closed")
        except ConnectionResetError:
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
    """ddd gui serving a copy of examples/demo, and where the copy is."""
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
        assert answered(server, "GET", "/api/state")["revision"] == 2

    def test_the_state_lists_the_components_loaded_and_clean(self, demo) -> None:
        server, _ = demo
        body = answered(server, "GET", "/api/state")
        components = [f for f in body["files"] if f["kind"] == "component"]
        assert {f["name"] for f in components} == self.COMPONENTS
        assert all(f["loaded"] and f["findings"]["error"] == 0 for f in components)
        assert not [f for f in body["findings"] if f["severity"] == "error"]
        waited = answered(server, "GET", f"/api/state?after={body['revision']}")
        assert waited["revision"] == body["revision"]

    def test_a_component_is_read_with_its_fingerprint(self, demo) -> None:
        server, root = demo
        controller = root / "components" / "controller.ddd.json"
        body = answered(server, "GET", f"/api/file?path={quote(controller.as_posix())}")
        assert body["data"]["component"]["name"] == "Controller"
        assert (body["fingerprint"], body["error"]) == (fingerprint(controller.read_bytes()), None)

    def test_the_dictionary_is_the_demos(self, demo) -> None:
        server, _ = demo
        body = answered(server, "GET", "/api/dictionary")
        assert (body["revision"], body["dictionary"]["name"]) == (1, "DemoDevice")

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
            ]
        }
        body = answered(server, "POST", "/api/edit", edit)
        after = controller.read_bytes()
        assert after == before.replace(b'"unit": "%"', b'"unit": "rpm"', 1)
        assert body == {
            "revision": 2,
            "files": [{"path": controller.as_posix(), "fingerprint": fingerprint(after)}],
        }
        state = answered(server, "GET", "/api/state")
        disagreeing = {
            Path(f["file"]).name for f in state["findings"] if f["check"] == "definition-mismatch"
        }
        assert disagreeing == {"controller.ddd.json", "sensor_hub.ddd.json"}


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
        why = [f for f in body["findings"] if f["file"] == (root / "b.ddd.json").as_posix()]
        assert [f["check"] for f in why] == ["json-syntax"]

    def test_the_file_is_answered_as_the_reason_it_does_not_parse(self, broken) -> None:
        server, root = broken
        target = root / "b.ddd.json"
        body = answered(server, "GET", f"/api/file?path={quote(target.as_posix())}")
        assert (body["data"], body["fingerprint"]) == (None, fingerprint(target.read_bytes()))
        assert body["error"].startswith(f"{target} is not json: ")


class TestRunning:
    def test_an_installation_without_compiled_pages_is_a_usage_error(
        self, tmp_path, capsys
    ) -> None:
        assert run(None, [], 0, open_browser=False, static=tmp_path) == EXIT_USAGE
        assert "npm run build" in capsys.readouterr().err

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
        assert f"cannot serve on port {port}" in capsys.readouterr().err

    @pytest.mark.parametrize("open_browser", [True, False])
    def test_it_prints_its_address_serves_and_exits_cleanly_when_interrupted(
        self, project_file, pages, monkeypatch, capsys, open_browser
    ) -> None:
        opened: list[str] = []
        stopped: list[bool] = []
        monkeypatch.setattr(module.webbrowser, "open", opened.append)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: stopped.append(True))

        def interrupted(self, poll_interval=0.5):
            raise KeyboardInterrupt

        monkeypatch.setattr(GuiServer, "serve_forever", interrupted)
        assert run(project_file, [], 0, open_browser=open_browser, static=pages) == EXIT_OK
        (line,) = capsys.readouterr().out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")
        assert "/open?token=" in line
        assert opened == ([line.rsplit(" ", 1)[1]] if open_browser else [])
        assert stopped == [True]

    def test_a_server_shut_down_from_elsewhere_also_ends_cleanly(self, pages, monkeypatch) -> None:
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert run(None, [], 0, open_browser=False, static=pages) == EXIT_OK


def test_the_windows_server_does_not_share_a_port() -> None:
    assert GuiServer.allow_reuse_address is (sys.platform != "win32")
