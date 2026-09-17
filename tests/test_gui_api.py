"""The JSON API of ddd gui, answered without a network: request in, reply out."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd import __version__
from ddd.diagnostics import CHECKS
from ddd.editing import UNVERIFIED, UNWRITABLE, EditError, fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Session

UNIT = "component.interface[0].definition.unit"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            "other/q.ddd.json": project("Q"),
        },
    )
    return tmp_path


@pytest.fixture
def api(root: Path) -> Api:
    session = Session(root)
    session.open(root / "p.ddd.json")
    return Api(session, root / "p.ddd.json", wait_seconds=0.05)


def get(api: Api, path: str, /, **query: str) -> Reply:
    # positional-only: a call passing path=... as part of ?path=... (the /api/file query) would
    # otherwise collide with this path, the url being requested.
    return api.handle("GET", path, {key: [value] for key, value in query.items()}, None)


def post(api: Api, path: str, body: object) -> Reply:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return api.handle("POST", path, {}, raw)


def unit_edit(api: Api, root: Path, unit: str, name: str = "b.ddd.json") -> dict:
    target = root / name
    return {
        "changes": [
            {
                "file": target.as_posix(),
                "fingerprint": fingerprint(target.read_bytes()),
                "operations": [{"op": "set", "pointer": UNIT, "raw": json.dumps(unit)}],
            }
        ]
    }


class TestRoutes:
    def test_an_unknown_path_is_not_found(self, api: Api) -> None:
        assert get(api, "/api/nothing") == Reply(
            404, {"error": "not-found", "message": "/api/nothing is not part of the api"}
        )

    def test_a_known_path_with_the_wrong_method_is_refused(self, api: Api) -> None:
        reply = api.handle("POST", "/api/state", {}, b"{}")
        assert (reply.status, reply.body["error"]) == (405, "method-not-allowed")


class TestSession:
    def test_the_open_project_and_the_version_are_described(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/session")
        assert reply.status == 200
        assert reply.body == {
            "version": __version__,
            "preview": True,
            "root": root.resolve().as_posix(),
            "project": {"path": (root / "p.ddd.json").resolve().as_posix(), "name": "P"},
            "builds": [],
        }

    def test_without_a_project_the_session_says_so(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/session")
        assert (reply.body["project"], reply.body["builds"]) == (None, [])

    def test_the_records_a_project_is_analysed_under_are_listed(self, root: Path) -> None:
        from conftest import build_record

        build_record(root, root / "p.ddd.json", severity=["unused-output=error"])
        session = Session(root)
        session.open(root / "p.ddd.json")
        assert get(Api(session), "/api/session").body["builds"] == [
            {"image": "firmware.elf", "strict": False, "severity": ["unused-output=error"]}
        ]


class TestProjects:
    def test_the_projects_found_are_listed(self, api: Api, root: Path) -> None:
        body = get(api, "/api/projects").body
        # sorted by path: other/q.ddd.json comes before p.ddd.json
        assert [(p["name"], p["images"]) for p in body["projects"]] == [("Q", []), ("P", [])]
        assert body["refused"] == []

    def test_a_refused_record_is_listed_with_its_reason(self, root: Path) -> None:
        from conftest import build_record

        record = build_record(root, root / "p.ddd.json", severity=["no-such-check=error"])
        body = get(Api(Session(root)), "/api/projects").body
        assert [entry["record"] for entry in body["refused"]] == [record.resolve().as_posix()]

    def test_a_record_from_a_newer_ddd_is_listed_with_both_formats(self, root: Path) -> None:
        """Spec 6.10: the start page lists it with the reason, as the language server logs it."""
        from conftest import build_record
        from ddd.build_info import BUILD_INFO_FORMAT

        newer = BUILD_INFO_FORMAT + 1
        record = build_record(root, root / "p.ddd.json", format=newer, colour="blue")
        body = get(Api(Session(root)), "/api/projects").body
        assert body["refused"] == [
            {
                "record": record.resolve().as_posix(),
                "reason": f"written in format {newer} by a newer DDD, and this one understands "
                f"up to format {BUILD_INFO_FORMAT}",
            }
        ]

    def test_a_project_found_can_be_opened(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/open", {"path": (root / "other" / "q.ddd.json").as_posix()})
        assert (reply.status, reply.body["project"]["name"]) == (200, "Q")

    def test_the_project_named_on_the_command_line_can_be_opened_from_anywhere(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        elsewhere = tmp_path_factory.mktemp("elsewhere")
        write_tree(elsewhere, {"p.ddd.json": project("Far")})
        start = tmp_path_factory.mktemp("start")
        api = Api(Session(start), elsewhere / "p.ddd.json")
        reply = post(api, "/api/open", {"path": (elsewhere / "p.ddd.json").as_posix()})
        assert reply.body["project"]["name"] == "Far"

    def test_a_path_that_is_not_a_project_found_is_not_opened(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/open", {"path": (root / "a.ddd.json").as_posix()})
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_record_naming_something_that_is_not_a_project_cannot_be_opened(
        self, root: Path
    ) -> None:
        from conftest import build_record

        build_record(root, root / "a.ddd.json")
        reply = post(Api(Session(root)), "/api/open", {"path": (root / "a.ddd.json").as_posix()})
        assert (reply.status, reply.body["error"]) == (409, "not-a-project")

    @pytest.mark.parametrize("body", [b"not json", b"[]", {"path": 7}, {}])
    def test_an_open_request_without_a_path_is_bad(self, api: Api, body: object) -> None:
        reply = post(api, "/api/open", body)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")


class TestState:
    def test_the_state_lists_every_file_and_finding(self, api: Api, root: Path) -> None:
        body = get(api, "/api/state").body
        assert body["revision"] == 1
        assert body["project"] == (root / "p.ddd.json").resolve().as_posix()
        files = {Path(f["path"]).name: f for f in body["files"]}
        assert files["a.ddd.json"]["kind"] == "component"
        assert files["a.ddd.json"]["name"] == "A"
        assert files["a.ddd.json"]["loaded"] is True
        assert files["a.ddd.json"]["findings"] == {"error": 0, "warning": 0, "info": 1}
        assert {f["check"] for f in body["findings"]} == {"missing-id"}

    def test_a_disagreement_carries_its_pointer_and_its_note(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        findings = [
            f
            for f in get(api, "/api/state").body["findings"]
            if f["check"] == "definition-mismatch"
        ]
        assert {Path(f["file"]).name for f in findings} == {"a.ddd.json", "b.ddd.json"}
        assert all(f["pointer"] == "component.interface[0].definition" for f in findings)
        noted = [f for f in findings if f["notes"]]
        assert noted and noted[0]["notes"][0]["pointer"] == "component.interface[0].definition"

    def test_a_note_without_a_place_is_carried_without_one(self, api: Api) -> None:
        from ddd.diagnostics import Diagnostic, Severity
        from ddd.gui.api import _finding
        from ddd.gui.session import Filed

        filed = Filed(
            Path("a.ddd.json"), Diagnostic("schema", Severity.ERROR, "m", None, (("n", None),))
        )
        assert _finding(filed)["notes"] == [{"message": "n", "file": None, "pointer": ""}]
        assert _finding(filed)["pointer"] == ""

    def test_asking_for_a_newer_revision_waits_for_one(self, api: Api, root: Path) -> None:
        threading.Timer(0.01, api.session.open, args=(root / "p.ddd.json",)).start()
        api.wait_seconds = 5
        assert get(api, "/api/state", after="1").body["revision"] == 2

    def test_asking_for_a_newer_revision_answers_with_the_current_one_after_waiting(
        self, api: Api
    ) -> None:
        assert get(api, "/api/state", after="1").body["revision"] == 1

    @pytest.mark.parametrize("after", ["", "-1", "one", "٣"])
    def test_an_after_that_is_not_a_number_does_not_wait(self, api: Api, after: str) -> None:
        api.wait_seconds = 30
        assert get(api, "/api/state", after=after).body["revision"] == 1

    def test_the_state_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root), wait_seconds=0.01), "/api/state", after="0")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestFiles:
    def test_a_description_file_is_read(self, api: Api, root: Path) -> None:
        body = get(api, "/api/file", path=(root / "a.ddd.json").as_posix()).body
        assert body["data"]["component"]["name"] == "A"
        assert body["fingerprint"] == fingerprint((root / "a.ddd.json").read_bytes())
        assert body["error"] is None

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            ('{"component": {"name": "B", "limit": NaN}}', "'NaN' is not valid json"),
            ('{"component": {"name": "B", "name": "C"}}', "key 'name' appears twice"),
        ],
    )
    def test_a_file_the_loader_does_not_read_as_json_is_answered_as_its_reason(
        self, root: Path, content: str, reason: str
    ) -> None:
        """Parsed by python's own reader, the first was answered with a ``NaN`` that the page's
        parser turned into nothing at all, and the page went blank."""
        (root / "b.ddd.json").write_text(content, encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        body = get(Api(session), "/api/file", path=(root / "b.ddd.json").as_posix()).body
        assert body["data"] is None
        assert reason in body["error"]
        json.dumps(body, allow_nan=False)

    def test_a_file_outside_the_project_is_not_found(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/file", path=(root / "other" / "q.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_request_needs_a_path(self, api: Api) -> None:
        assert get(api, "/api/file").status == 400

    def test_a_file_request_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/file", path=(root / "a.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestDictionaryAndChecks:
    def test_the_dictionary_of_the_current_revision_is_served(self, api: Api) -> None:
        body = get(api, "/api/dictionary").body
        assert body["revision"] == 1
        assert body["dictionary"]["name"] == "P"

    def test_a_project_that_does_not_resolve_has_no_dictionary(self, root: Path) -> None:
        (root / "b.ddd.json").write_text("{", encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        assert get(Api(session), "/api/dictionary").body["dictionary"] is None

    def test_the_dictionary_needs_an_open_project(self, root: Path) -> None:
        assert get(Api(Session(root)), "/api/dictionary").status == 409

    def test_the_built_in_checks_are_listed_without_a_project(self, root: Path) -> None:
        checks = get(Api(Session(root)), "/api/checks").body["checks"]
        assert [c["check"] for c in checks] == list(CHECKS)
        assert set(checks[0]) == {
            "check",
            "default_severity",
            "description",
            "overridable",
            "needs_every_component",
            "comparison",
        }

    def test_the_checks_of_the_open_projects_plugins_follow(self, api: Api, monkeypatch) -> None:
        from dataclasses import replace

        from ddd.diagnostics import CheckInfo, Severity

        revision = api.session.revision
        assert revision is not None
        extra = CheckInfo("demo/tagged", Severity.WARNING, "a demonstration check")
        monkeypatch.setattr(api.session, "_revision", replace(revision, checks=(extra,)))
        assert get(api, "/api/checks").body["checks"][-1]["check"] == "demo/tagged"


class TestEdit:
    def test_an_edit_is_written_and_the_new_revision_answered(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert reply.status == 200
        assert reply.body["revision"] == 2
        target = (root / "b.ddd.json").resolve()
        assert reply.body["files"] == [
            {"path": target.as_posix(), "fingerprint": fingerprint(target.read_bytes())}
        ]
        assert '"unit": "Hz"' in target.read_text(encoding="utf-8")

    def test_a_stale_edit_is_a_refusal_the_page_can_act_on(self, api: Api, root: Path) -> None:
        edit = unit_edit(api, root, "Hz")
        (root / "b.ddd.json").write_text("{}", encoding="utf-8")
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "stale")

    def test_an_edit_that_could_not_be_written_is_a_server_error(
        self, api: Api, root: Path, monkeypatch
    ) -> None:
        def unwritable(changes):
            raise EditError(UNWRITABLE, "disk full")

        monkeypatch.setattr(api.session, "edit", unwritable)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (500, "unwritable")

    def test_an_edit_that_does_not_read_back_is_a_refusal_the_page_can_act_on(
        self, api: Api, root: Path, monkeypatch
    ) -> None:
        def unverified(changes):
            raise EditError(
                UNVERIFIED, "the edited file does not read back as the intended document"
            )

        monkeypatch.setattr(api.session, "edit", unverified)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_an_edit_outside_the_project_is_not_found(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz", name="other/q.ddd.json"))
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_an_edit_needs_an_open_project(self, root: Path) -> None:
        reply = post(Api(Session(root)), "/api/edit", unit_edit(None, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    @pytest.mark.parametrize(
        "body",
        [
            b"not json",
            {},
            {"changes": []},
            {"changes": [7]},
            {
                "changes": [
                    {
                        "file": 1,
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": "1"}],
                    }
                ]
            },
            {"changes": [{"file": "a", "fingerprint": "x", "operations": []}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [7]}]},
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "rename", "pointer": "a"}],
                    }
                ]
            },
            {
                "changes": [
                    {"file": "a", "fingerprint": "x", "operations": [{"op": "set", "pointer": 1}]}
                ]
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": 1}],
                    }
                ]
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "move", "pointer": "a[0]", "to": "1"}],
                    }
                ]
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "move", "pointer": "a[0]", "to": True}],
                    }
                ]
            },
        ],
    )
    def test_a_malformed_edit_is_a_bad_request(self, api: Api, body: object) -> None:
        reply = post(api, "/api/edit", body)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_pointer_that_names_nothing_is_an_invalid_edit(self, api: Api, root: Path) -> None:
        edit = unit_edit(api, root, "Hz")
        edit["changes"][0]["operations"][0]["pointer"] = "component.interface[5].definition.unit"
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "invalid")

    @pytest.mark.parametrize(
        "content",
        [
            "{",
            '{"component": {"name": "B", "limit": NaN}}',
            '{"component": {"name": "B", "name": "C"}}',
        ],
    )
    def test_an_edit_of_a_file_that_is_not_json_is_unreadable(
        self, root: Path, content: str
    ) -> None:
        (root / "b.ddd.json").write_text(content, encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        api = Api(session)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_move_carries_its_target_index(self, api: Api, root: Path) -> None:
        target = root / "p.ddd.json"
        edit = {
            "changes": [
                {
                    "file": target.as_posix(),
                    "fingerprint": fingerprint(target.read_bytes()),
                    "operations": [{"op": "move", "pointer": "project.includes[0]", "to": 1}],
                }
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        includes = json.loads(target.read_text(encoding="utf-8"))["project"]["includes"]
        assert includes == ["b.ddd.json", "a.ddd.json"]
