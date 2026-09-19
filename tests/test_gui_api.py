"""The JSON API of ddd gui, answered without a network: request in, reply out."""

from __future__ import annotations

import json
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Final

import pytest

from conftest import EXAMPLES, component, declare, project, scalar_type, types, write_tree
from ddd import __version__
from ddd.diagnostics import CHECKS
from ddd.editing import UNVERIFIED, UNWRITABLE, EditError, fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Session

UNIT = "component.interface[0].definition.unit"

TYPED = {
    "p.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
    "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
    "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
    "b.ddd.json": component("B", declare("input", "Speed", "uint16", unit="%")),
}

# A project whose one file declaring `Torque` was saved half-edited, as an editor saves a file
# being typed into: it no longer parses, so `Torque` is in no index while the file is like this.
HALF_SAVED = {
    "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "b.ddd.json": json.dumps(component("B", declare("input", "Torque", unit="Nm")), indent=2)[:60],
}


def opened(tmp_path: Path, files: dict[str, object]) -> Api:
    write_tree(tmp_path, files)
    session = Session(tmp_path)
    session.open(tmp_path / "p.ddd.json")
    return Api(session, tmp_path / "p.ddd.json", wait_seconds=0.05)


def unloaded(tmp_path: Path) -> Api:
    """A project the analysis could not read at all, so its revision has no index."""
    api = opened(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 3}}})
    assert api.session.revision is not None
    assert api.session.revision.index is None
    return api


def posix(root: Path, name: str) -> str:
    return (root / name).resolve().as_posix()


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

    @pytest.mark.parametrize("body", [b"not json", b"[]", {"path": 7}, {}, {"path": "a", "x": 1}])
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
        assert json.loads(json.dumps(body, allow_nan=False)) == body

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


class TestGraph:
    COMPONENTS: Final = {
        "components/controller.ddd.json": "Controller",
        "components/sensor_hub.ddd.json": "SensorHub",
        "components/user_interface.ddd.json": "UserInterface",
        "subsystems/logging/event_logger.ddd.json": "EventLogger",
    }
    """Every component of examples/demo, by its path relative to the project."""

    FLOWS: Final = {
        ("components/controller.ddd.json", "components/user_interface.ddd.json"),
        ("components/controller.ddd.json", "subsystems/logging/event_logger.ddd.json"),
        ("components/sensor_hub.ddd.json", "components/controller.ddd.json"),
        ("components/sensor_hub.ddd.json", "components/user_interface.ddd.json"),
        ("components/sensor_hub.ddd.json", "subsystems/logging/event_logger.ddd.json"),
        ("components/user_interface.ddd.json", "subsystems/logging/event_logger.ddd.json"),
        ("subsystems/logging/event_logger.ddd.json", "components/user_interface.ddd.json"),
    }
    """Every producing-consuming pair examples/demo's dictionary puts a flow between."""

    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        """``ddd gui``'s api over a copy of examples/demo, and where the copy is."""
        root = tmp_path / "demo"
        shutil.copytree(EXAMPLES / "demo", root)
        session = Session(root)
        session.open(root / "demo.ddd.json")
        return Api(session, root / "demo.ddd.json"), root.resolve()

    def test_the_demo_lists_its_modules_and_the_flows_between_them(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        body = get(api, "/api/graph").body
        assert body["revision"] == 1
        modules = {m["path"]: m for m in body["modules"]}
        assert set(modules) == {(root / suffix).as_posix() for suffix in self.COMPONENTS}
        for suffix, name in self.COMPONENTS.items():
            module = modules[(root / suffix).as_posix()]
            assert (module["name"], module["loaded"]) == (name, True)
            assert module["findings"] == {"error": 0, "warning": 0, "info": 0}
        pairs = {(f["from"], f["to"]) for f in body["flows"]}
        assert pairs == {
            ((root / source).as_posix(), (root / target).as_posix())
            for source, target in self.FLOWS
        }
        assert all(f["severity"] is None and f["disagreements"] == [] for f in body["flows"])

    def test_a_revision_that_resolved_a_dictionary_says_so(self, demo: tuple[Api, Path]) -> None:
        api, _ = demo
        assert get(api, "/api/graph").body["dictionary"] is True

    def test_a_revision_with_no_dictionary_says_so_and_answers_the_modules_alone(
        self, root: Path
    ) -> None:
        """What the page shows its "no dictionary" banner for: it is told, rather than guessing
        it from an answer a project whose modules share nothing gives just as well."""
        (root / "b.ddd.json").write_text('{"component": {}}', encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        body = get(Api(session), "/api/graph").body
        assert body["dictionary"] is False
        assert [module["name"] for module in body["modules"]] == ["A", "b"]
        assert body["flows"] == []

    def test_a_disagreement_with_the_producer_colours_the_flow(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        controller = root / "components" / "controller.ddd.json"
        edit = {
            "changes": [
                {
                    "file": controller.as_posix(),
                    "fingerprint": fingerprint(controller.read_bytes()),
                    "operations": [{"op": "set", "pointer": UNIT, "raw": json.dumps("rpm")}],
                }
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        body = get(api, "/api/graph").body
        sensor_hub = (root / "components" / "sensor_hub.ddd.json").as_posix()
        flow = next(
            f for f in body["flows"] if (f["from"], f["to"]) == (sensor_hub, controller.as_posix())
        )
        assert flow["severity"] == "error"
        assert any(
            (d["check"], d["object"], d["severity"]) == ("definition-mismatch", "ValueA", "error")
            for d in flow["disagreements"]
        )
        assert all(f["severity"] is None for f in body["flows"] if f is not flow)

    def test_the_graph_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/graph")
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_a_component_that_does_not_load_is_a_module_with_no_flow(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": '{"component": {}}',
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        body = get(Api(session), "/api/graph").body
        modules = {m["path"]: m for m in body["modules"]}
        broken = (tmp_path / "b.ddd.json").resolve().as_posix()
        assert (modules[broken]["loaded"], modules[broken]["name"]) == (False, "b")
        assert body["flows"] == []


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

    def test_an_edit_whose_raw_value_is_a_fractional_number_is_written_as_typed(
        self, api: Api, root: Path
    ) -> None:
        """``1.0`` must not become ``1``: contract.Operation.raw is a str pydantic never parses,
        and the value it carries reaches the file exactly as it was sent, decimal point kept."""
        target = root / "b.ddd.json"
        edit = {
            "changes": [
                {
                    "file": target.as_posix(),
                    "fingerprint": fingerprint(target.read_bytes()),
                    "operations": [{"op": "set", "pointer": UNIT, "raw": "1.0"}],
                }
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        assert '"unit": 1.0' in target.read_text(encoding="utf-8")

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
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": "1", "unknown": True}],
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

    def test_a_change_without_a_fingerprint_creates_the_file_the_edit_includes(
        self, api: Api, root: Path
    ) -> None:
        described = root / "p.ddd.json"
        created = {"op": "set", "pointer": "", "raw": '{"units": ["rpm"]}'}
        included = {"op": "insert", "pointer": "project.includes[2]", "raw": '"units.ddd.json"'}
        edit = {
            "changes": [
                {
                    "file": (root / "units.ddd.json").as_posix(),
                    "fingerprint": None,
                    "operations": [created],
                },
                {
                    "file": described.as_posix(),
                    "fingerprint": fingerprint(described.read_bytes()),
                    "operations": [included],
                },
            ]
        }
        reply = post(api, "/api/edit", edit)
        assert reply.status == 200
        assert (root / "units.ddd.json").read_bytes() == b'{"units": ["rpm"]}'
        assert {f["path"] for f in reply.body["files"]} == {
            posix(root, "units.ddd.json"),
            posix(root, "p.ddd.json"),
        }
        files = {Path(f["path"]).name: f for f in get(api, "/api/state").body["files"]}
        assert (files["units.ddd.json"]["kind"], files["units.ddd.json"]["loaded"]) == (
            "units",
            True,
        )

    def test_a_file_the_edit_does_not_include_is_not_created(self, api: Api, root: Path) -> None:
        edit = {
            "changes": [
                {
                    "file": (root / "units.ddd.json").as_posix(),
                    "fingerprint": None,
                    "operations": [{"op": "set", "pointer": "", "raw": '{"units": ["rpm"]}'}],
                }
            ]
        }
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert not (root / "units.ddd.json").exists()

    def test_a_change_that_leaves_its_fingerprint_out_is_a_bad_request(
        self, api: Api, root: Path
    ) -> None:
        """Left out is not ``null``: a page that forgot the fingerprint is not taken to be
        creating the file."""
        edit = unit_edit(api, root, "Hz")
        del edit["changes"][0]["fingerprint"]
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

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


class TestVariable:
    def test_every_declaration_of_a_variable_is_described(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/variable", name="Speed")
        assert reply.status == 200
        # `a.ddd.json` produces `Speed` and states no `id`, so `missing-id` is filed on it too -
        # the same info finding `TestState.test_the_state_lists_every_file_and_finding` already
        # counts for this fixture; asserted by its check alone, the declarations below are what
        # this test is about.
        assert (reply.body["revision"], reply.body["name"]) == (1, "Speed")
        assert {f["check"] for f in reply.body["findings"]} == {"missing-id"}
        assert [
            (d["path"], d["pointer"], d["component"], d["role"], d["stated"]["unit"], d["type"])
            for d in reply.body["declarations"]
        ] == [
            (
                posix(root, "a.ddd.json"),
                "component.interface[0].definition",
                "A",
                "produces",
                '"rpm"',
                None,
            ),
            (
                posix(root, "b.ddd.json"),
                "component.interface[0].definition",
                "B",
                "reads",
                '"rpm"',
                None,
            ),
        ]

    def test_a_disagreement_is_among_its_findings_on_both_sides(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "%")).status == 200
        findings = get(api, "/api/variable", name="Speed").body["findings"]
        # Filtered to the check this test is about: `a.ddd.json` also carries its standing
        # `missing-id` info finding (see the note above), which is not what "among" means here.
        mismatches = [f for f in findings if f["check"] == "definition-mismatch"]
        assert sorted((f["file"], f["check"]) for f in mismatches) == [
            (posix(root, "a.ddd.json"), "definition-mismatch"),
            (posix(root, "b.ddd.json"), "definition-mismatch"),
        ]

    def test_a_declaration_naming_a_type_says_what_the_type_fixes(self, tmp_path: Path) -> None:
        declarations = get(opened(tmp_path, TYPED), "/api/variable", name="Speed").body[
            "declarations"
        ]
        assert (declarations[0]["type"], declarations[0]["fixed"]["unit"]) == ("Speed_t", '"rpm"')
        assert "unit" not in declarations[0]["stated"]

    def test_a_variable_is_asked_for_by_name(self, api: Api) -> None:
        assert get(api, "/api/variable").status == 400

    def test_a_name_nothing_declares_is_not_found(self, api: Api) -> None:
        assert get(api, "/api/variable", name="Torque").status == 404

    def test_a_name_only_a_file_that_did_not_load_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        # Answered "not declared", the page would close the name's panel for good (spec 5.5),
        # when the next save puts the declaration back: the answer says which file did not load.
        reply = get(opened(tmp_path, HALF_SAVED), "/api/variable", name="Torque")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "'Torque' is not declared in any file that loaded, and b.ddd.json did not load"
        )

    def test_a_project_the_analysis_could_not_read_cannot_say_what_it_declares(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/variable", name="Speed")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_variable_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/variable", name="Speed")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestUnits:
    def test_without_a_vocabulary_the_units_in_use_are_answered(self, api: Api) -> None:
        assert get(api, "/api/units").body == {
            "revision": 1,
            "vocabulary": None,
            "used": [{"unit": "rpm", "variables": 1}],
        }

    def test_a_vocabulary_is_answered_with_its_descriptions(self, tmp_path: Path) -> None:
        files = {
            "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
            "units.ddd.json": {"units": ["rpm", {"unit": "Nm", "description": "torque"}]},
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
        }
        assert get(opened(tmp_path, files), "/api/units").body["vocabulary"] == [
            {"unit": "rpm", "description": None},
            {"unit": "Nm", "description": "torque"},
        ]

    def test_a_project_the_analysis_could_not_read_uses_no_units(self, tmp_path: Path) -> None:
        assert get(unloaded(tmp_path), "/api/units").body["used"] == []

    def test_units_need_an_open_project(self, root: Path) -> None:
        assert get(Api(Session(root)), "/api/units").status == 409


class TestSettle:
    def test_a_preview_is_the_edit_and_the_lines_it_changes(self, api: Api, root: Path) -> None:
        before = {name: (root / name).read_bytes() for name in ("a.ddd.json", "b.ddd.json")}
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"%"')
        assert reply.status == 200
        assert [change["file"] for change in reply.body["changes"]] == [
            posix(root, "a.ddd.json"),
            posix(root, "b.ddd.json"),
        ]
        for change in reply.body["changes"]:
            name = Path(change["file"]).name
            lines = before[name].decode("utf-8").splitlines()
            line = next(n for n, text in enumerate(lines, 1) if '"unit": "rpm"' in text)
            assert change["fingerprint"] == fingerprint(before[name])
            assert change["operations"] == [{"op": "set", "pointer": UNIT, "raw": '"%"'}]
            assert change["hunks"] == [
                {
                    "line": line,
                    "before": [lines[line - 1]],
                    "after": [lines[line - 1].replace('"rpm"', '"%"')],
                }
            ]
        assert {name: (root / name).read_bytes() for name in before} == before

    def test_posting_a_preview_makes_every_declaration_agree(self, api: Api, root: Path) -> None:
        before = {name: (root / name).read_bytes() for name in ("a.ddd.json", "b.ddd.json")}
        preview = get(api, "/api/settle", name="Speed", key="unit", raw='"%"').body
        edit = {
            "changes": [
                {key: change[key] for key in ("file", "fingerprint", "operations")}
                for change in preview["changes"]
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        for name, bytes_before in before.items():
            expected = bytes_before.decode("utf-8").replace('"unit": "rpm"', '"unit": "%"')
            assert (root / name).read_bytes() == expected.encode("utf-8")
        declarations = get(api, "/api/variable", name="Speed").body["declarations"]
        assert {d["stated"]["unit"] for d in declarations} == {'"%"'}

    def test_when_every_declaration_agrees_there_is_nothing_to_change(self, api: Api) -> None:
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"rpm"')
        assert reply.body == {"revision": 1, "changes": []}

    def test_without_a_value_the_key_is_taken_out(self, api: Api) -> None:
        changes = get(api, "/api/settle", name="Speed", key="unit").body["changes"]
        assert [change["operations"] for change in changes] == [
            [{"op": "remove", "pointer": UNIT, "raw": None}],
            [{"op": "remove", "pointer": UNIT, "raw": None}],
        ]

    def test_a_unit_a_type_fixes_to_another_value_is_refused(self, tmp_path: Path) -> None:
        reply = get(opened(tmp_path, TYPED), "/api/settle", name="Speed", key="unit", raw='"%"')
        assert (reply.status, reply.body["error"]) == (409, "fixed-by-type")
        assert "Speed_t" in reply.body["message"]

    def test_a_declaration_moved_since_the_analysis_is_unreadable(
        self, api: Api, root: Path
    ) -> None:
        write_tree(root, {"b.ddd.json": component("B", declare("input", "Torque"))})
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"%"')
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.preview", refuse)
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"%"')
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    @pytest.mark.parametrize(
        "query",
        [
            {"key": "unit", "raw": '"%"'},
            {"name": "Speed", "raw": '"%"'},
            {"name": "Speed", "key": "name", "raw": '"B"'},
            {"name": "Speed", "key": "unit", "raw": "not json"},
        ],
    )
    def test_a_malformed_request_is_bad(self, api: Api, query: dict[str, str]) -> None:
        reply = get(api, "/api/settle", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_name_nothing_declares_is_not_found(self, api: Api) -> None:
        assert get(api, "/api/settle", name="Torque", key="unit", raw='"%"').status == 404

    def test_a_name_only_a_file_that_did_not_load_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, HALF_SAVED), "/api/settle", name="Torque", key="unit", raw="null"
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "b.ddd.json did not load" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_settles_nothing(self, tmp_path: Path) -> None:
        reply = get(unloaded(tmp_path), "/api/settle", name="Speed", key="unit", raw='"%"')
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_settling_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/settle", name="Speed", key="unit", raw='"%"')
        assert reply.status == 409


def copied(tmp_path: Path, example: str, project_file: str) -> tuple[Api, Path]:
    """``ddd gui``'s api over a copy of one of the examples, and where the copy is: the example
    itself is never written to."""
    root = tmp_path / example
    shutil.copytree(EXAMPLES / example, root)
    session = Session(root)
    session.open(root / project_file)
    return Api(session, root / project_file), root


def contents(root: Path) -> dict[str, bytes]:
    """Every file under ``root``, by its path relative to it: what an edit may have changed."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def applied(api: Api, preview: dict[str, Any]) -> Reply:
    """A preview's edit posted exactly as the page posts it: each change without its hunks."""
    changes = [
        {key: change[key] for key in ("file", "fingerprint", "operations")}
        for change in preview["changes"]
    ]
    return post(api, "/api/edit", {"changes": changes})


def with_unit(data: bytes, name: str, unit: str | None) -> bytes:
    """A file's bytes with the unit of the definition named ``name`` replaced by ``unit``, or
    taken out with its line for ``None``, and nothing else touched: the first ``"unit"`` member
    after that name, which in the examples is always followed by another member."""
    text = data.decode("utf-8")
    if unit is None:
        member = re.compile(rf'("name": "{name}"[\s\S]*?)\n *"unit": "[^"]*",')
        changed = member.sub(lambda found: found[1], text, count=1)
    else:
        value = re.compile(rf'("name": "{name}"[\s\S]*?"unit": )"[^"]*"')
        changed = value.sub(lambda found: found[1] + json.dumps(unit), text, count=1)
    assert changed != text
    return changed.encode("utf-8")


class TestTheDemo:
    """The three endpoints over a copy of examples/demo, and what applying a preview writes."""

    CONTROLLER: Final = "components/controller.ddd.json"
    SENSOR_HUB: Final = "components/sensor_hub.ddd.json"

    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def test_a_variable_is_answered_with_each_file_declaring_it(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        reply = get(api, "/api/variable", name="ValueA")
        assert reply.status == 200
        assert [
            (d["path"], d["component"], d["role"], d["stated"]["unit"], d["type"])
            for d in reply.body["declarations"]
        ] == [
            (posix(root, self.CONTROLLER), "Controller", "reads", '"%"', None),
            (posix(root, self.SENSOR_HUB), "SensorHub", "produces", '"%"', None),
        ]
        assert reply.body["findings"] == []

    def test_without_a_vocabulary_the_units_in_use_are_answered_most_used_first(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, _ = demo
        assert get(api, "/api/units").body == {
            "revision": 1,
            "vocabulary": None,
            "used": [
                {"unit": "%", "variables": 5},
                {"unit": "Hz", "variables": 3},
                {"unit": "V", "variables": 2},
                {"unit": "degC", "variables": 2},
                {"unit": "ms", "variables": 1},
            ],
        }

    def test_a_preview_writes_nothing_and_its_edit_changes_exactly_the_units(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        preview = get(api, "/api/settle", name="ValueA", key="unit", raw='"rpm"').body
        assert contents(root) == before
        assert [change["file"] for change in preview["changes"]] == [
            posix(root, self.CONTROLLER),
            posix(root, self.SENSOR_HUB),
        ]
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            self.CONTROLLER: with_unit(before[self.CONTROLLER], "ValueA", "rpm"),
            self.SENSOR_HUB: with_unit(before[self.SENSOR_HUB], "ValueA", "rpm"),
        }

    def test_no_unit_takes_the_unit_out_of_every_declaration_and_nothing_else(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        preview = get(api, "/api/settle", name="ValueA", key="unit").body
        assert contents(root) == before
        assert [change["operations"] for change in preview["changes"]] == [
            [{"op": "remove", "pointer": "component.interface[0].definition.unit", "raw": None}],
            [{"op": "remove", "pointer": "component.interface[0].definition.unit", "raw": None}],
        ]
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            self.CONTROLLER: with_unit(before[self.CONTROLLER], "ValueA", None),
            self.SENSOR_HUB: with_unit(before[self.SENSOR_HUB], "ValueA", None),
        }
        declarations = get(api, "/api/variable", name="ValueA").body["declarations"]
        assert [declaration["stated"].get("unit") for declaration in declarations] == [None, None]


class TestTheVocabulary:
    """The three endpoints over a copy of examples/vocabulary, a project that pins its units."""

    PUMP: Final = "pump.ddd.json"

    @pytest.fixture
    def vocabulary(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "vocabulary", "project.ddd.json")

    def test_the_vocabulary_is_answered_described_beside_the_units_in_use(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, _ = vocabulary
        assert get(api, "/api/units").body == {
            "revision": 1,
            "vocabulary": [
                {"unit": "rpm", "description": "rotational speed, revolutions per minute"},
                {"unit": "Nm", "description": "torque, newton metre"},
                {"unit": "degC", "description": "temperature"},
                {"unit": "kPa", "description": "pressure"},
            ],
            "used": [{"unit": "kPa", "variables": 2}, {"unit": "rpm", "variables": 1}],
        }

    def test_a_local_variable_is_answered_with_its_one_declaration(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        declarations = get(api, "/api/variable", name="PumpSpeed").body["declarations"]
        assert [
            (d["path"], d["component"], d["role"], d["stated"]["unit"]) for d in declarations
        ] == [(posix(root, self.PUMP), "Pump", "local", '"rpm"')]

    def test_a_preview_writes_nothing_and_its_edit_changes_exactly_the_unit(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        preview = get(api, "/api/settle", name="PumpSpeed", key="unit", raw='"kPa"').body
        assert contents(root) == before
        assert [change["file"] for change in preview["changes"]] == [posix(root, self.PUMP)]
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            self.PUMP: with_unit(before[self.PUMP], "PumpSpeed", "kPa"),
        }

    def test_a_unit_the_declared_type_fixes_is_left_to_the_type(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        declaration = get(api, "/api/variable", name="TorqueLimit").body["declarations"][0]
        assert (declaration["type"], declaration["fixed"]["unit"]) == ("Torque_t", '"Nm"')
        assert "unit" not in declaration["stated"]
        agreed = get(api, "/api/settle", name="TorqueLimit", key="unit", raw='"Nm"')
        assert (agreed.status, agreed.body["changes"]) == (200, [])
        refused = get(api, "/api/settle", name="TorqueLimit", key="unit", raw='"rpm"')
        assert (refused.status, refused.body["error"]) == (409, "fixed-by-type")
        assert "Torque_t" in refused.body["message"]
        assert contents(root) == before
