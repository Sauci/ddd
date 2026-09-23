"""The JSON API of ddd gui, answered without a network: request in, reply out."""

from __future__ import annotations

import json
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Final

import pytest

from conftest import (
    EXAMPLES,
    component,
    declare,
    project,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd import __version__
from ddd.diagnostics import CHECKS
from ddd.editing import UNREADABLE, UNVERIFIED, UNWRITABLE, EditError, fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Session
from ddd.variable_keys import KEY_ORDER

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

# The project HALF_SAVED becomes once `b.ddd.json` is saved whole: opened this way first, then
# broken exactly as HALF_SAVED is broken already (or removed outright) once the panel has read
# it once, to reproduce the race the CI diagnosis found deterministically - no browser, no
# timing, just a write landing between two requests of the same revision.
RACE = {
    "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "b.ddd.json": component("B", declare("input", "Torque", unit="Nm")),
}

# One unit stated three ways: by a variable, by a scalar type and by a structure member.
STATED_THREE_WAYS = {
    "p.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
    "types.ddd.json": types(
        scalar_type("Speed_t", unit="rpm"),
        struct_type("Sample_t", value_member("speed", unit="rpm")),
    ),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}

# A vocabulary listing one unit twice, which the loader reports as `duplicate-unit`.
LISTED_TWICE = {
    "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
    "units.ddd.json": {"units": ["rpm", "rpm"]},
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}


def opened(tmp_path: Path, files: dict[str, object]) -> Api:
    write_tree(tmp_path, files)
    session = Session(tmp_path)
    session.open(tmp_path / "p.ddd.json")
    return Api(session, tmp_path / "p.ddd.json", wait_seconds=0.05)


def opened_example(tmp_path: Path, example: str, description: str) -> Api:
    """``ddd gui`` over a copy of one of the shipped examples, so the test may edit it."""
    shutil.copytree(EXAMPLES / example, tmp_path / example)
    session = Session(tmp_path / example)
    session.open(tmp_path / example / description)
    return Api(session, tmp_path / example / description, wait_seconds=0.05)


def unloaded(tmp_path: Path) -> Api:
    """A project the analysis could not read at all, so its revision has no index."""
    api = opened(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 3}}})
    assert api.session.revision is not None
    assert api.session.revision.index is None
    return api


def posix(root: Path, name: str) -> str:
    return (root / name).resolve().as_posix()


def picked(body: dict[str, Any]) -> dict[str, Any]:
    """What part 1's picker reads of ``GET /api/units``: the Units tab's rows and adoption left
    out, which the tests of the tab assert on their own."""
    return {key: body[key] for key in ("revision", "vocabulary", "used")}


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


def unit_edit(
    api: Api, root: Path, unit: str, name: str = "b.ddd.json", label: str = "the unit of Speed"
) -> dict:
    target = root / name
    return {
        "changes": [
            {
                "file": target.as_posix(),
                "fingerprint": fingerprint(target.read_bytes()),
                "operations": [{"op": "set", "pointer": UNIT, "raw": json.dumps(unit)}],
            }
        ],
        "label": label,
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
        assert _finding(filed, None, {})["notes"] == [{"message": "n", "file": None, "pointer": ""}]
        assert _finding(filed, None, {})["pointer"] == ""
        # A file the analysis did not list has no kind to route by, so the finding leads nowhere.
        assert _finding(filed, None, {})["route"] is None

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

    def test_every_finding_says_where_it_leads(self, api: Api) -> None:
        # The root fixture's two components declare Speed, and `a.ddd.json` states no id: every
        # finding this project reports is about that declaration, and each says so.
        findings = get(api, "/api/state").body["findings"]
        assert findings
        assert all(
            finding["route"] == {"kind": "variable", "name": "Speed"} for finding in findings
        )

    def test_a_finding_on_a_file_that_did_not_load_leads_nowhere(self, tmp_path: Path) -> None:
        state = get(opened(tmp_path, HALF_SAVED), "/api/state").body
        half = next(
            finding for finding in state["findings"] if finding["file"].endswith("b.ddd.json")
        )
        assert half["route"] is None

    def test_an_unknown_unit_leads_to_its_unit(self, tmp_path: Path) -> None:
        api = opened_example(tmp_path, "vocabulary", "project.ddd.json")
        drifted = tmp_path / "vocabulary" / "pump.ddd.json"
        drifted.write_text(
            drifted.read_text(encoding="utf-8").replace('"unit": "kPa"', '"unit": "KPA"', 1),
            encoding="utf-8",
            newline="",
        )
        # Session has no `refresh`; `poll()` is what re-analyses the open project on demand when
        # a file of it changed on disk (its own docstring, and the pattern the rest of this file
        # uses), which is the same thing under a different name.
        assert api.session.poll() is True
        unknown = next(
            finding
            for finding in get(api, "/api/state").body["findings"]
            if finding["check"] == "unknown-unit"
        )
        assert unknown["route"] == {"kind": "unit", "name": "KPA"}


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
            ],
            "label": "the unit of ValueA",
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
            ],
            "label": "the unit of Speed",
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
        def unwritable(changes, label):
            raise EditError(UNWRITABLE, "disk full")

        monkeypatch.setattr(api.session, "edit", unwritable)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (500, "unwritable")

    def test_an_edit_that_does_not_read_back_is_a_refusal_the_page_can_act_on(
        self, api: Api, root: Path, monkeypatch
    ) -> None:
        def unverified(changes, label):
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
            {"changes": [], "label": "x"},
            {"changes": [7], "label": "x"},
            {
                "changes": [
                    {
                        "file": 1,
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": "1"}],
                    }
                ],
                "label": "x",
            },
            {"changes": [{"file": "a", "fingerprint": "x", "operations": []}], "label": "x"},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [7]}], "label": "x"},
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "rename", "pointer": "a"}],
                    }
                ],
                "label": "x",
            },
            {
                "changes": [
                    {"file": "a", "fingerprint": "x", "operations": [{"op": "set", "pointer": 1}]}
                ],
                "label": "x",
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": 1}],
                    }
                ],
                "label": "x",
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "move", "pointer": "a[0]", "to": "1"}],
                    }
                ],
                "label": "x",
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "move", "pointer": "a[0]", "to": True}],
                    }
                ],
                "label": "x",
            },
            {
                "changes": [
                    {
                        "file": "a",
                        "fingerprint": "x",
                        "operations": [{"op": "set", "pointer": "a", "raw": "1", "unknown": True}],
                    }
                ],
                "label": "x",
            },
        ],
    )
    def test_a_malformed_edit_is_a_bad_request(self, api: Api, body: object) -> None:
        reply = post(api, "/api/edit", body)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_an_edit_without_a_label_is_refused(self, api: Api, root: Path) -> None:
        controller = root / "a.ddd.json"
        reply = post(
            api,
            "/api/edit",
            {
                "changes": [
                    {
                        "file": controller.as_posix(),
                        "fingerprint": fingerprint(controller.read_bytes()),
                        "operations": [{"op": "set", "pointer": UNIT, "raw": '"Hz"'}],
                    }
                ]
            },
        )
        assert reply.status == 400
        assert reply.body["error"] == "bad-request"

    @pytest.mark.parametrize("label", ["", "x" * 121])
    def test_a_label_is_a_sentence_of_at_most_a_hundred_and_twenty_characters(
        self, api: Api, root: Path, label: str
    ) -> None:
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz", label=label))
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
            ],
            "label": "the vocabulary adopted",
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
            ],
            "label": "the vocabulary adopted",
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
            ],
            "label": "the includes reordered",
        }
        assert post(api, "/api/edit", edit).status == 200
        includes = json.loads(target.read_text(encoding="utf-8"))["project"]["includes"]
        assert includes == ["b.ddd.json", "a.ddd.json"]


class TestUndoing:
    def test_the_state_says_what_there_is_to_undo(self, api: Api, root: Path) -> None:
        assert get(api, "/api/state").body["undoable"] is None
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        assert get(api, "/api/state").body["undoable"] == {"at": 1, "label": "the unit of Speed"}

    def test_nothing_to_undo_is_not_found(self, api: Api) -> None:
        reply = get(api, "/api/undo")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_the_preview_carries_the_lines_each_file_would_get_back(
        self, api: Api, root: Path
    ) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        body = get(api, "/api/undo").body
        assert (body["at"], body["label"]) == (1, "the unit of Speed")
        assert body["revision"] == get(api, "/api/state").body["revision"]
        change = body["changes"][0]
        assert Path(change["file"]).name == "b.ddd.json"
        assert change["gone"] is False
        assert any('"Hz"' in line for hunk in change["hunks"] for line in hunk["before"])
        assert any('"rpm"' in line for hunk in change["hunks"] for line in hunk["after"])

    def test_a_file_changed_since_the_edit_refuses_the_preview(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        b = root / "b.ddd.json"
        b.write_text('{"component": {"name": "B", "interface": []}}', encoding="utf-8")
        reply = get(api, "/api/undo")
        assert (reply.status, reply.body["error"]) == (409, "stale")
        assert reply.body["message"] == "b.ddd.json changed on disk since it was written"

    def test_a_preview_that_could_not_be_built_is_a_server_error(
        self, api: Api, root: Path, monkeypatch
    ) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200

        def unwritable(entry):
            raise EditError(UNWRITABLE, "disk full")

        monkeypatch.setattr("ddd.gui.api.unchanged", unwritable)
        reply = get(api, "/api/undo")
        assert (reply.status, reply.body["error"]) == (500, "unwritable")

    def test_an_undo_puts_the_files_back_and_answers_the_new_revision(
        self, api: Api, root: Path
    ) -> None:
        b = root / "b.ddd.json"
        before = b.read_bytes()
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        reply = post(api, "/api/undo", {"at": 1})
        assert reply.status == 200
        assert reply.body == {"revision": 3}
        assert b.read_bytes() == before
        assert get(api, "/api/state").body["undoable"] is None

    def test_an_undo_of_anything_but_the_top_is_refused(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        reply = post(api, "/api/undo", {"at": 9})
        assert (reply.status, reply.body["error"]) == (409, "stale")
        assert get(api, "/api/state").body["undoable"] == {"at": 1, "label": "the unit of Speed"}

    def test_an_undo_that_could_not_be_written_is_a_server_error(
        self, api: Api, monkeypatch
    ) -> None:
        def unwritable(at):
            raise EditError(UNWRITABLE, "disk full")

        monkeypatch.setattr(api.session, "undo", unwritable)
        reply = post(api, "/api/undo", {"at": 1})
        assert (reply.status, reply.body["error"]) == (500, "unwritable")

    def test_an_undo_takes_a_number(self, api: Api) -> None:
        reply = post(api, "/api/undo", {})
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_undoing_needs_an_open_project(self, root: Path) -> None:
        bare = Api(Session(root))
        assert get(bare, "/api/undo").status == 409
        assert post(bare, "/api/undo", {"at": 1}).status == 409

    def test_both_methods_of_one_path_are_served(self, api: Api) -> None:
        reply = api.handle("DELETE", "/api/undo", {}, None)
        assert (reply.status, reply.body["error"]) == (405, "method-not-allowed")
        assert reply.body["message"] == "/api/undo takes GET or POST"


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

    def test_a_panel_finding_carries_its_route(self, api: Api) -> None:
        findings = get(api, "/api/variable", name="Speed").body["findings"]
        # `a.ddd.json` states no id for Speed, so the panel has a finding to carry a route at
        # all: asserted, or the `all` below would pass over an empty list saying nothing.
        assert findings
        assert all(
            finding["route"] == {"kind": "variable", "name": "Speed"} for finding in findings
        )

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

    def test_a_name_only_a_file_that_changed_since_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        # The race itself: a file saved half-edited between the analysis and this request is
        # still recorded loaded, with the fingerprint it had before the save. Answered "not
        # declared", the page would close the panel for good instead of waiting out the second
        # or so until the next analysis catches up.
        api = opened(tmp_path, RACE)
        assert get(api, "/api/variable", name="Torque").status == 200
        write_tree(tmp_path, {"b.ddd.json": HALF_SAVED["b.ddd.json"]})
        reply = get(api, "/api/variable", name="Torque")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "'Torque' is not declared in any file that has not changed since, "
            "and b.ddd.json changed since it was read"
        )

    def test_a_name_only_a_file_deleted_since_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        # Gone missing since counts as changed: the fingerprint recorded at the analysis cannot
        # be read back at all, which is answered the same as a file whose bytes moved on.
        api = opened(tmp_path, RACE)
        assert get(api, "/api/variable", name="Torque").status == 200
        (tmp_path / "b.ddd.json").unlink()
        reply = get(api, "/api/variable", name="Torque")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "'Torque' is not declared in any file that has not changed since, "
            "and b.ddd.json changed since it was read"
        )

    def test_a_project_the_analysis_could_not_read_cannot_say_what_it_declares(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/variable", name="Speed")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_variable_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/variable", name="Speed")
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_every_shared_key_is_answered_with_what_it_offers(self, api: Api) -> None:
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]
        }
        assert list(offered) == list(KEY_ORDER)
        # Both declarations of the root fixture are measurements stating rpm.
        assert offered["unit"]["values"] == [
            {"raw": '"rpm"', "components": ["A", "B"], "producer": True}
        ]
        assert offered["volatile"]["carried"] == [
            {"allowed": True, "required": True},
            {"allowed": True, "required": True},
        ]
        assert offered["size"]["carried"] == [
            {"allowed": False, "required": False},
            {"allowed": False, "required": False},
        ]

    def test_the_keys_that_disagree_say_so(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "%")).status == 200
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]
        }
        assert offered["unit"]["disagrees"] is True
        assert offered["datatype"]["disagrees"] is False
        assert offered["limits"]["disagrees"] is False

    def test_a_key_says_which_field_chooses_it_and_what_that_field_lists(self, api: Api) -> None:
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]
        }
        assert (offered["datatype"]["editor"], offered["datatype"]["choices"][:2]) == (
            "datatype",
            ["boolean", "uint8"],
        )
        assert (offered["conversion"]["editor"], offered["conversion"]["choices"]) == ("none", [])
        assert (offered["unit"]["editor"], offered["limits"]["editor"]) == ("unit", "limits")

    def test_a_value_a_type_fixes_is_in_play_and_its_storage_is_not_removable(
        self, tmp_path: Path
    ) -> None:
        offered = {
            offer["key"]: offer
            for offer in get(opened(tmp_path, TYPED), "/api/variable", name="Speed").body["keys"]
        }
        # `a.ddd.json` names Speed_t, which fixes rpm; `b.ddd.json` states % itself.
        assert offered["unit"]["values"] == [
            {"raw": '"rpm"', "components": ["A"], "producer": True},
            {"raw": '"%"', "components": ["B"], "producer": False},
        ]
        assert offered["typename"]["carried"] == [
            {"allowed": True, "required": True},
            {"allowed": True, "required": False},
        ]
        assert offered["typename"]["choices"] == ["Speed_t"]

    def test_a_key_naming_an_object_lists_the_projects_objects_of_that_kind(
        self, tmp_path: Path
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="MapA").body["keys"]
        }
        # The demo's map is declared once, local to Controller, over the two axes it declares.
        assert offered["x_axis"]["values"] == [
            {"raw": '"AxisA"', "components": ["Controller"], "producer": False}
        ]
        assert offered["x_axis"]["choices"] == ["AxisA", "AxisB"]
        assert offered["y_axis"]["choices"] == ["AxisA", "AxisB"]
        # A map has no `axis` of its own, and the axes are not measurements.
        assert offered["axis"]["carried"] == [{"allowed": False, "required": False}]
        assert "ValueA" in offered["input"]["choices"]
        assert "AxisA" not in offered["input"]["choices"]

    def test_one_value_two_files_spell_differently_is_one_value_in_play(
        self, tmp_path: Path
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="ValueA").body["keys"]
        }
        # SensorHub writes ValueA's conversion over four lines and Controller writes it on one:
        # one conversion, in the producer's spelling, and a row the panel does not mark.
        assert [
            (value["components"], value["producer"]) for value in offered["conversion"]["values"]
        ] == [(["Controller", "SensorHub"], True)]
        assert json.loads(offered["conversion"]["values"][0]["raw"])["kind"] == "linear"
        assert "\n" in offered["conversion"]["values"][0]["raw"]


class TestUnits:
    def test_without_a_vocabulary_the_units_in_use_are_answered(self, api: Api) -> None:
        assert picked(get(api, "/api/units").body) == {
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
            ],
            "label": "the unit of Speed",
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

    @pytest.mark.parametrize(
        ("name", "key", "raw", "written"),
        [
            ("ValueA", "unit", '"Hz"', "Hz"),
            ("ValueA", "limits", '{"min": 0, "max": 50}', {"min": 0, "max": 50}),
            (
                "ValueA",
                "conversion",
                '{"kind": "linear", "factor": 0.25}',
                {"kind": "linear", "factor": 0.25},
            ),
            ("ValueA", "volatile", "true", True),
            ("CurveA", "axis", '"AxisB"', "AxisB"),
        ],
    )
    def test_a_key_of_any_shape_previews_without_writing_and_applies_what_it_said(
        self, tmp_path: Path, name: str, key: str, raw: str, written: Any
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        root = tmp_path / "demo"
        before = contents(root)
        preview = get(api, "/api/settle", name=name, key=key, raw=raw)
        assert preview.status == 200
        assert contents(root) == before, "a preview writes nothing"
        edit = {
            "changes": [
                {field: change[field] for field in ("file", "fingerprint", "operations")}
                for change in preview.body["changes"]
            ],
            "label": f"the {key} of {name}",
        }
        assert post(api, "/api/edit", edit).status == 200
        for declaration in get(api, "/api/variable", name=name).body["declarations"]:
            assert json.loads(declaration["stated"][key]) == written

    def test_a_key_a_declarations_kind_cannot_hold_is_refused_whole(self, tmp_path: Path) -> None:
        # Two kinds under one name: the measurement may hold dimensions and the parameter may
        # not, so the change reaches some declarations and not others - which `ddd gui` refuses
        # rather than applying by halves (see `ddd.lsp.edits.settle`).
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", dimensions=[4])),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        before = contents(tmp_path)
        reply = get(api, "/api/settle", name="Speed", key="dimensions", raw="[8]")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert "b.ddd.json" in reply.body["message"]
        assert contents(tmp_path) == before

    def test_a_container_value_spelled_differently_but_meaning_the_producers_is_settled(
        self, tmp_path: Path
    ) -> None:
        # A and B mean the same range of limits - one spelled with ints, the other with floats.
        # `stated == raw` (ddd.lsp.edits.settle's own check) compares text, so before ddd gui
        # narrowed a settlement by what a value means rather than only how it is spelled, this
        # found something to change here; now the producer's own value (A's, the int spelling)
        # is already what B means, so there is nothing to settle.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", limits={"min": 0.0, "max": 100.0})
                ),
            },
        )
        raw = next(
            key["values"][0]["raw"]
            for key in get(api, "/api/variable", name="Speed").body["keys"]
            if key["key"] == "limits"
        )
        assert json.loads(raw) == {"min": 0, "max": 100}
        assert get(api, "/api/settle", name="Speed", key="limits", raw=raw).body["changes"] == []


class TestFix:
    def test_a_missing_id_is_previewed_and_applied(self, tmp_path: Path) -> None:
        # A second producing declaration without an id, so that stamping the first proves the
        # fix is scoped to the pointer it was asked about rather than to every unstamped
        # declaration the file holds.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("output", "Torque", unit="Nm"),
                ),
            },
        )
        root = tmp_path
        before = contents(root)
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert reply.status == 200
        assert [fix["title"] for fix in reply.body["fixes"]] == ["Give 'Speed' an id"]
        assert contents(root) == before, "a preview writes nothing"

        (change,) = reply.body["fixes"][0]["changes"]
        assert change["hunks"], "the reader is shown the line it would add"
        edit = {
            "changes": [{f: change[f] for f in ("file", "fingerprint", "operations")}],
            "label": "Give 'Speed' an id",
        }
        assert post(api, "/api/edit", edit).status == 200
        stamped = json.loads((root / "a.ddd.json").read_text(encoding="utf-8"))
        assert len(stamped["component"]["interface"][0]["definition"]["id"]) == 12
        # Named by the pointer alone: the declaration `/api/fix` was not asked about is left as
        # it was, which a fixture with only one unstamped declaration could not have shown.
        assert "id" not in stamped["component"]["interface"][1]["definition"]

    def test_a_fix_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, api: Api, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `fixes_for` and `planned` each read the file from disk, moments apart, inside the one
        # request: an external rewrite or delete in that window is refused by `planned`, the way
        # `_settle`/`_unit_plan` are, rather than crashing into a generic 500.
        def refuse(*_: object) -> None:
            raise EditError(UNREADABLE, "a.ddd.json can no longer be read as utf-8")

        monkeypatch.setattr("ddd.gui.api.planned", refuse)
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == "a.ddd.json can no longer be read as utf-8"

    def test_a_finding_with_no_fix_answers_none(self, api: Api, root: Path) -> None:
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="definition-mismatch",
        )
        assert (reply.status, reply.body["fixes"]) == (200, [])

    @pytest.mark.parametrize(
        "query",
        [{}, {"file": "a.ddd.json"}, {"file": "a.ddd.json", "pointer": "x"}],
    )
    def test_a_malformed_request_is_bad(self, api: Api, query: dict[str, str]) -> None:
        assert get(api, "/api/fix", **query).status == 400

    def test_a_file_of_no_project_is_not_found(self, api: Api, tmp_path: Path) -> None:
        reply = get(
            api,
            "/api/fix",
            file=(tmp_path / "elsewhere.ddd.json").resolve().as_posix(),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_fixing_needs_an_open_project(self, root: Path) -> None:
        reply = get(
            Api(Session(root)),
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (409, "no-project")


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


def applied(api: Api, preview: dict[str, Any], label: str = "the change previewed") -> Reply:
    """A preview's edit posted exactly as the page posts it: each change without its hunks."""
    changes = [
        {key: change[key] for key in ("file", "fingerprint", "operations")}
        for change in preview["changes"]
    ]
    return post(api, "/api/edit", {"changes": changes, "label": label})


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


def findings_of(state: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """What a state reports, each finding by its file, check, place and sentence."""
    return {(f["file"], f["check"], f["pointer"], f["message"]) for f in state["findings"]}


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

    def test_settling_a_conversion_onto_the_producers_own_layout_reaches_nothing_to_change(
        self, demo: tuple[Api, Path]
    ) -> None:
        # SensorHub (ValueA's producer) pretty-prints its conversion over three lines; Controller
        # keeps it compact. Drifting Controller's factor gives the settlement something real to
        # change; applying it writes the value in Controller's own layout, not SensorHub's - so a
        # second preview that compared text, as `ddd.lsp.edits.settle` alone does, would find
        # something to change again forever. It must not: this is the case reported against Task
        # 7 (see task-7-report.md), reproduced here.
        api, root = demo
        controller = root / self.CONTROLLER
        before = controller.read_text("utf-8")
        pattern = r'("name": "ValueA"[\s\S]*?"factor": )[0-9.]+'
        drifted = re.sub(pattern, r"\g<1>0.25", before, count=1)
        assert drifted != before
        controller.write_text(drifted, encoding="utf-8")
        assert api.session.poll() is True

        raw = next(
            key["values"][0]["raw"]
            for key in get(api, "/api/variable", name="ValueA").body["keys"]
            if key["key"] == "conversion"
        )
        preview = get(api, "/api/settle", name="ValueA", key="conversion", raw=raw).body
        assert [change["file"] for change in preview["changes"]] == [posix(root, self.CONTROLLER)]
        assert applied(api, preview).status == 200
        declarations = get(api, "/api/variable", name="ValueA").body["declarations"]
        controller_conversion = next(d for d in declarations if d["component"] == "Controller")[
            "stated"
        ]["conversion"]
        assert json.loads(controller_conversion) == {"kind": "linear", "factor": 0.5}

        again = get(api, "/api/settle", name="ValueA", key="conversion", raw=raw).body
        assert again["changes"] == []

    def test_without_a_vocabulary_the_units_in_use_are_answered_most_used_first(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, _ = demo
        assert picked(get(api, "/api/units").body) == {
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

    def test_the_units_tab_lists_every_unit_in_use_and_how_many_adopting_would_list(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, _ = demo
        body = get(api, "/api/units").body
        assert body["adoptable"] == 5
        assert [
            (u["unit"], u["variables"], u["types"], u["members"], u["findings"])
            for u in body["units"]
        ] == [
            ("%", 5, 0, 0, 0),
            ("Hz", 3, 0, 0, 0),
            ("V", 2, 0, 0, 0),
            ("degC", 2, 0, 0, 0),
            ("ms", 1, 0, 0, 0),
        ]
        assert all((u["description"], u["files"]) == (None, []) for u in body["units"])

    def test_adopting_writes_the_units_file_includes_it_and_reports_nothing_more(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        reported = findings_of(get(api, "/api/state").body)
        preview = get(api, "/api/unit-plan", action="adopt").body
        assert contents(root) == before
        described, created = preview["changes"]
        assert (described["file"], created["file"]) == (
            posix(root, "demo.ddd.json"),
            posix(root, "units.ddd.json"),
        )
        assert described["fingerprint"] == fingerprint(before["demo.ddd.json"])
        assert created["fingerprint"] is None
        assert applied(api, preview).status == 200
        text = (root / "units.ddd.json").read_text(encoding="utf-8")
        assert created["hunks"] == [{"line": 1, "before": [], "after": text.splitlines()}]
        listed = json.loads(text)["units"]
        assert sorted(entry["unit"] for entry in listed) == ["%", "Hz", "V", "degC", "ms"]
        assert all(entry["description"] == "" for entry in listed)
        last = b'"subsystems/logging/logging.ddd.json"'
        assert contents(root) == {
            **before,
            "demo.ddd.json": before["demo.ddd.json"].replace(
                last, last + b',\n      "units.ddd.json"'
            ),
            "units.ddd.json": text.encode("utf-8"),
        }
        assert findings_of(get(api, "/api/state").body) <= reported
        units = get(api, "/api/units").body
        assert units["adoptable"] is None
        assert {u["unit"]: u["files"] for u in units["units"]}["Hz"] == [
            posix(root, "units.ddd.json")
        ]

    def test_undoing_an_adoption_takes_the_file_away_and_puts_the_description_back(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="adopt").body
        assert applied(api, preview, "the vocabulary adopted").status == 200
        undo = get(api, "/api/undo").body
        assert undo["label"] == "the vocabulary adopted"
        changes = {Path(c["file"]).name: c for c in undo["changes"]}
        assert changes["units.ddd.json"]["gone"] is True
        assert changes["units.ddd.json"]["hunks"][0]["after"] == []
        assert changes["demo.ddd.json"]["gone"] is False
        assert post(api, "/api/undo", {"at": undo["at"]}).status == 200
        # Every file of the project is exactly as it was, the new one gone with the line that
        # included it.
        assert contents(root) == before

    def test_undoing_a_settlement_puts_a_re_laid_out_container_back_exactly(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        preview = get(
            api, "/api/settle", name="ValueA", key="limits", raw='{"min": 0, "max": 10}'
        ).body
        assert applied(api, preview, "the limits of ValueA").status == 200
        assert contents(root) != before
        assert post(api, "/api/undo", {"at": 1}).status == 200
        assert contents(root) == before


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
        assert picked(get(api, "/api/units").body) == {
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

    def test_the_units_tab_lists_the_vocabulary_beside_what_states_each_unit(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        body = get(api, "/api/units").body
        listing = [posix(root, "units.ddd.json")]
        assert body["adoptable"] is None
        assert body["units"] == [
            {
                "unit": "Nm",
                "description": "torque, newton metre",
                "files": listing,
                "variables": 0,
                "types": 1,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "degC",
                "description": "temperature",
                "files": listing,
                "variables": 0,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "kPa",
                "description": "pressure",
                "files": listing,
                "variables": 2,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "rpm",
                "description": "rotational speed, revolutions per minute",
                "files": listing,
                "variables": 1,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
        ]

    def test_a_unit_a_type_states_is_answered_with_its_entry_and_the_type(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        assert get(api, "/api/unit", name="Nm").body == {
            "revision": 1,
            "unit": "Nm",
            "description": "torque, newton metre",
            "entries": [{"file": posix(root, "units.ddd.json"), "pointer": "units[1]"}],
            "sites": [
                {
                    "path": posix(root, self.PUMP),
                    "pointer": "component.types[0].unit",
                    "kind": "type",
                    "name": "Torque_t",
                    "component": None,
                    "role": None,
                }
            ],
            "findings": [],
        }

    def test_a_spelling_drifted_from_outside_merges_into_the_vocabularys_own(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        original = contents(root)
        (root / self.PUMP).write_bytes(with_unit(original[self.PUMP], "PumpSpeed", "RPM"))
        assert api.session.poll() is True
        drifted = {u["unit"]: u for u in get(api, "/api/units").body["units"]}["RPM"]
        assert (drifted["description"], drifted["files"], drifted["findings"]) == (None, [], 1)
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="rename", unit="RPM", to="rpm").body
        assert contents(root) == before
        assert [(c["file"], c["operations"]) for c in preview["changes"]] == [
            (
                posix(root, self.PUMP),
                [
                    {
                        "op": "set",
                        "pointer": "component.interface[0].definition.unit",
                        "raw": '"rpm"',
                    }
                ],
            )
        ]
        assert applied(api, preview).status == 200
        assert contents(root) == original
        units = {u["unit"]: u for u in get(api, "/api/units").body["units"]}
        assert "RPM" not in units
        assert (units["rpm"]["variables"], units["rpm"]["findings"]) == (1, 0)

    def test_a_description_is_written_into_its_entry_and_nowhere_else(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        preview = get(
            api, "/api/unit-plan", action="describe", unit="kPa", description="pressure, kilopascal"
        ).body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                b'"pressure"', b'"pressure, kilopascal"'
            ),
        }
        assert get(api, "/api/unit", name="kPa").body["description"] == "pressure, kilopascal"

    def test_a_unit_outside_the_vocabulary_is_added_in_the_form_its_entries_take(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        original = contents(root)
        (root / self.PUMP).write_bytes(with_unit(original[self.PUMP], "ManifoldPressure", "bar"))
        assert api.session.poll() is True
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="add", unit="bar").body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        last = b'{ "unit": "kPa", "description": "pressure" }'
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                last, last + b',\n    { "unit": "bar", "description": "" }'
            ),
        }
        assert "unknown-unit" not in {f["check"] for f in get(api, "/api/state").body["findings"]}

    def test_a_unit_nothing_states_is_removed_from_the_vocabulary(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="remove", unit="degC").body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                b'    { "unit": "degC", "description": "temperature" },\n', b""
            ),
        }
        assert get(api, "/api/unit", name="degC").status == 404

    def test_a_unit_something_still_states_is_not_removed(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        reply = get(api, "/api/unit-plan", action="remove", unit="rpm")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert contents(root) == before


class TestUnitsTab:
    """The rows ``GET /api/units`` adds for the Units tab, and what adopting would list."""

    def test_each_unit_in_use_is_a_row_and_adopting_would_list_it(self, api: Api) -> None:
        body = get(api, "/api/units").body
        assert body["units"] == [
            {
                "unit": "rpm",
                "description": None,
                "files": [],
                "variables": 1,
                "types": 0,
                "members": 0,
                "findings": 0,
            }
        ]
        assert body["adoptable"] == 1

    def test_a_unit_is_counted_by_the_variables_types_and_members_stating_it(
        self, tmp_path: Path
    ) -> None:
        (row,) = get(opened(tmp_path, STATED_THREE_WAYS), "/api/units").body["units"]
        assert (row["unit"], row["variables"], row["types"], row["members"]) == ("rpm", 1, 1, 1)

    def test_a_unit_listed_twice_counts_its_findings_on_both_entries_and_its_file_once(
        self, tmp_path: Path
    ) -> None:
        body = get(opened(tmp_path, LISTED_TWICE), "/api/units").body
        assert body["adoptable"] is None
        (row,) = body["units"]
        assert (row["files"], row["findings"]) == ([posix(tmp_path, "units.ddd.json")], 2)

    def test_a_project_the_analysis_could_not_read_has_no_rows_and_nothing_to_adopt(
        self, tmp_path: Path
    ) -> None:
        body = get(unloaded(tmp_path), "/api/units").body
        assert (body["units"], body["adoptable"]) == ([], 0)


class TestUnit:
    def test_every_place_stating_a_unit_is_answered_with_its_variable(
        self, api: Api, root: Path
    ) -> None:
        reply = get(api, "/api/unit", name="rpm")
        assert reply.status == 200
        assert reply.body == {
            "revision": 1,
            "unit": "rpm",
            "description": None,
            "entries": [],
            "sites": [
                {
                    "path": posix(root, name),
                    "pointer": UNIT,
                    "kind": "variable",
                    "name": "Speed",
                    "component": component_name,
                    "role": role,
                }
                for name, component_name, role in (
                    ("a.ddd.json", "A", "produces"),
                    ("b.ddd.json", "B", "reads"),
                )
            ],
            "findings": [],
        }

    def test_a_type_and_a_structure_member_are_places_of_their_unit(self, tmp_path: Path) -> None:
        sites = get(opened(tmp_path, STATED_THREE_WAYS), "/api/unit", name="rpm").body["sites"]
        assert sorted(
            (s["kind"], s["name"], s["pointer"], s["component"], s["role"]) for s in sites
        ) == [
            ("member", "Sample_t.speed", "types[1].members[0].unit", None, None),
            ("type", "Speed_t", "types[0].unit", None, None),
            ("variable", "Speed", UNIT, "A", "produces"),
        ]

    def test_a_variable_its_file_no_longer_declares_there_is_left_out(
        self, api: Api, root: Path
    ) -> None:
        write_tree(root, {"b.ddd.json": component("B", declare("input", "Torque", unit="rpm"))})
        sites = get(api, "/api/unit", name="rpm").body["sites"]
        assert [(s["component"], s["name"]) for s in sites] == [("A", "Speed")]

    def test_a_unit_listed_twice_has_its_findings_on_both_entries(self, tmp_path: Path) -> None:
        body = get(opened(tmp_path, LISTED_TWICE), "/api/unit", name="rpm").body
        units = posix(tmp_path, "units.ddd.json")
        assert body["entries"] == [
            {"file": units, "pointer": "units[0]"},
            {"file": units, "pointer": "units[1]"},
        ]
        assert sorted((f["file"], f["check"], f["pointer"]) for f in body["findings"]) == [
            (units, "duplicate-unit", "units[0]"),
            (units, "duplicate-unit", "units[1]"),
        ]

    def test_a_unit_is_asked_for_by_name(self, api: Api) -> None:
        reply = get(api, "/api/unit")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_unit_nothing_states_or_lists_is_not_found(self, api: Api) -> None:
        reply = get(api, "/api/unit", name="RPM")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_unit_only_a_file_that_did_not_load_states_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        reply = get(opened(tmp_path, HALF_SAVED), "/api/unit", name="Nm")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "b.ddd.json did not load" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_cannot_say_what_it_states(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/unit", name="rpm")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_unit_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/unit", name="rpm")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestUnitPlan:
    def test_a_rename_is_previewed_as_the_edit_and_the_lines_it_changes(
        self, api: Api, root: Path
    ) -> None:
        before = contents(root)
        reply = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz")
        assert reply.status == 200
        assert contents(root) == before
        assert reply.body["revision"] == 1
        assert [change["file"] for change in reply.body["changes"]] == [
            posix(root, "a.ddd.json"),
            posix(root, "b.ddd.json"),
        ]
        for change in reply.body["changes"]:
            name = Path(change["file"]).name
            lines = before[name].decode("utf-8").splitlines()
            line = next(n for n, text in enumerate(lines, 1) if '"unit": "rpm"' in text)
            assert change["fingerprint"] == fingerprint(before[name])
            assert change["operations"] == [{"op": "set", "pointer": UNIT, "raw": '"Hz"'}]
            assert change["hunks"] == [
                {
                    "line": line,
                    "before": [lines[line - 1]],
                    "after": [lines[line - 1].replace('"rpm"', '"Hz"')],
                }
            ]

    def test_posting_a_rename_changes_the_unit_everywhere_it_is_stated(
        self, api: Api, root: Path
    ) -> None:
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz").body
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            **{
                name: before[name].replace(b'"unit": "rpm"', b'"unit": "Hz"')
                for name in ("a.ddd.json", "b.ddd.json")
            },
        }
        assert get(api, "/api/unit", name="rpm").status == 404

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"action": "merge", "unit": "rpm"},
            {"action": "rename", "unit": "rpm"},
            {"action": "rename", "to": "Hz"},
            {"action": "describe", "unit": "rpm"},
            {"action": "remove", "unit": ""},
        ],
    )
    def test_a_missing_or_unknown_parameter_is_a_bad_request(
        self, api: Api, query: dict[str, str]
    ) -> None:
        reply = get(api, "/api/unit-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    @pytest.mark.parametrize(
        "query",
        [
            {"action": "rename", "unit": "rpm", "to": "rpm"},
            {"action": "rename", "unit": "rpm", "to": ""},
            {"action": "add", "unit": "rpm"},
        ],
    )
    def test_a_plan_its_rules_refuse_is_invalid_and_writes_nothing(
        self, api: Api, root: Path, query: dict[str, str]
    ) -> None:
        before = contents(root)
        reply = get(api, "/api/unit-plan", **query)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert contents(root) == before

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, api: Api) -> None:
        reply = get(api, "/api/unit-plan", action="rename", unit="Nm", to="rpm")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_rename_while_a_file_does_not_load_is_unreadable_and_names_it(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, HALF_SAVED), "/api/unit-plan", action="rename", unit="rpm", to="Hz"
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "b.ddd.json" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_plans_nothing(self, tmp_path: Path) -> None:
        reply = get(unloaded(tmp_path), "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"].startswith("p.ddd.json did not load")

    def test_a_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz")
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_planning_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestTheTypesTab:
    """The three endpoints over a copy of examples/structures, and what applying a plan writes."""

    @pytest.fixture
    def structures(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "structures", "project.ddd.json")

    def test_every_type_is_a_row_with_its_kind_and_uses(self, structures) -> None:
        api, _ = structures
        body = get(api, "/api/types").body
        rows = {row["name"]: row for row in body["types"]}
        assert [row["name"] for row in body["types"]] == sorted(rows)
        assert (rows["Temperature_t"]["kind"], rows["Temperature_t"]["uses"]) == ("scalar", 3)
        assert rows["DriverStatus_t"]["kind"] == "external"
        assert rows["Sample_t"]["kind"] == "struct"

    def test_a_scalar_answers_what_it_fixes_as_offers(self, structures) -> None:
        api, _ = structures
        body = get(api, "/api/type", name="Temperature_t").body
        assert (body["kind"], body["header"]) == ("scalar", None)
        assert body["description"].startswith("A temperature as every component")
        offers = {offer["key"]: offer for offer in body["keys"]}
        assert list(offers) == ["datatype", "unit", "conversion", "limits"]
        assert offers["unit"]["values"][0]["raw"] == '"degC"'
        assert offers["unit"]["editor"] == "unit"
        assert offers["datatype"]["carried"][0]["required"] is True
        assert offers["limits"]["carried"][0]["required"] is False
        assert body["members"] == []

    def test_a_structure_answers_its_members_and_no_offers(self, structures) -> None:
        api, _ = structures
        body = get(api, "/api/type", name="Sensor_t").body
        assert body["keys"] == []
        assert [member["name"] for member in body["members"]] == [
            "latest",
            "status",
            "driver",
            "history",
        ]
        assert body["members"][3]["dimensions"] == ["8"]
        assert body["members"][0]["typename"] == "Sample_t"

    def test_an_external_answers_its_header(self, structures) -> None:
        api, _ = structures
        body = get(api, "/api/type", name="DriverStatus_t").body
        assert (body["kind"], body["header"]) == ("external", "driver_status.h")
        assert body["keys"] == []

    def test_the_uses_carry_the_component_and_the_role(self, structures) -> None:
        api, _ = structures
        body = get(api, "/api/type", name="Sensor_t").body
        assert [
            (use["kind"], use["name"], use["component"], use["role"]) for use in body["uses"]
        ] == [
            ("variable", "Inlet", "Sensing", "produces"),
            ("variable", "Inlet", "Monitoring", "reads"),
        ]

    def test_a_type_is_asked_for_by_name(self, structures) -> None:
        api, _ = structures
        reply = get(api, "/api/type")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_type_the_project_does_not_declare_is_not_found(self, structures) -> None:
        api, _ = structures
        reply = get(api, "/api/type", name="Nothing_t")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_setting_a_unit_is_previewed_then_written(self, structures) -> None:
        api, root = structures
        before = contents(root)
        preview = get(
            api, "/api/type-plan", action="set", name="Temperature_t", key="unit", raw='"K"'
        ).body
        assert contents(root) == before
        assert [Path(change["file"]).name for change in preview["changes"]] == ["types.ddd.json"]
        assert applied(api, preview, "the unit of Temperature_t").status == 200
        assert '"unit": "K"' in (root / "types.ddd.json").read_text(encoding="utf-8")

    def test_renaming_rewrites_the_type_and_every_name_reaching_it(self, structures) -> None:
        api, root = structures
        preview = get(api, "/api/type-plan", action="rename", name="Sensor_t", to="Probe_t").body
        assert [Path(change["file"]).name for change in preview["changes"]] == [
            "monitoring.ddd.json",
            "sensing.ddd.json",
            "types.ddd.json",
        ]
        assert applied(api, preview, "the rename of 'Sensor_t' to 'Probe_t'").status == 200
        for name in ("monitoring.ddd.json", "sensing.ddd.json", "types.ddd.json"):
            text = (root / name).read_text(encoding="utf-8")
            assert "Sensor_t" not in text
        assert get(api, "/api/type", name="Probe_t").status == 200

    @pytest.mark.parametrize(
        ("to", "says"),
        [("Sample_t", "shares c's namespace"), ("uint16", "spells a base datatype")],
    )
    def test_a_rename_that_may_not_be_made_is_refused_in_the_editor_s_words(
        self, structures, to, says
    ) -> None:
        api, _ = structures
        reply = get(api, "/api/type-plan", action="rename", name="Temperature_t", to=to)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert says in reply.body["message"]

    def test_a_plan_takes_the_parameters_its_action_names(self, structures) -> None:
        api, _ = structures
        assert get(api, "/api/type-plan", action="set", name="Temperature_t").status == 400
        assert get(api, "/api/type-plan", action="dance", name="Temperature_t").status == 400
        assert get(api, "/api/type-plan", name="Temperature_t", to="X_t").status == 400

    def test_a_finding_inside_a_type_carries_its_route(self, structures) -> None:
        api, root = structures
        # A unit no vocabulary lists is not reported here. Naming the external DriverStatus_t
        # directly - rather than through a structure member - is a type-kind, and the refusal's
        # own note ("declared here") points at the type's entry, so the mirrored copy of the
        # finding is filed there and routes to it. Drift the file rather than inventing a
        # finding: replacing the typename with "Sample_t" (a structure, as the brief for this
        # test first suggested) instead produces a definition-mismatch between the two
        # components declaring 'Inlet', filed on their two declarations - neither of which is
        # inside a type's own entry - so it never routes to "type"; DriverStatus_t is the
        # substitution that actually lands a finding there.
        broken = (root / "sensing.ddd.json").read_text(encoding="utf-8")
        (root / "sensing.ddd.json").write_text(
            broken.replace('"typename": "Sensor_t"', '"typename": "DriverStatus_t"', 1),
            encoding="utf-8",
        )
        api.session.poll()
        routes = {
            finding["check"]: finding["route"]
            for finding in get(api, "/api/state").body["findings"]
            if finding["route"] is not None and finding["route"]["kind"] == "type"
        }
        assert routes == {"type-kind": {"kind": "type", "name": "DriverStatus_t"}}

    def test_the_types_of_a_project_that_declares_none_are_empty(self, api: Api) -> None:
        # The `api` fixture's project has no types file at all.
        assert get(api, "/api/types").body["types"] == []

    def test_a_project_the_analysis_could_not_read_has_no_types(self, tmp_path: Path) -> None:
        body = get(unloaded(tmp_path), "/api/types").body
        assert body["types"] == []

    def test_a_project_the_analysis_could_not_read_cannot_answer_a_type(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/type", name="Temperature_t")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_project_the_analysis_could_not_read_plans_no_type_change(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            unloaded(tmp_path), "/api/type-plan", action="rename", name="Temperature_t", to="X_t"
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"].startswith("p.ddd.json did not load")

    def test_a_type_the_project_neither_declares_cannot_be_changed(self, structures) -> None:
        api, _ = structures
        reply = get(api, "/api/type-plan", action="rename", name="Nothing_t", to="X_t")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_type_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, structures, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        api, _ = structures

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/type-plan", action="rename", name="Sensor_t", to="Probe_t")
        assert (reply.status, reply.body["error"]) == (409, "unverified")


class TestWhatAComponentMayAdd:
    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def controller(self, root: Path) -> str:
        return (root / "components" / "controller.ddd.json").as_posix()

    def test_the_names_it_may_read_come_with_their_producer_and_scopes(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        names = {entry["name"]: entry for entry in body["names"]}
        # Measured against examples/demo: Controller declares 14 of the project's 23 names.
        assert sorted(names) == [
            "BlockA",
            "CurveB",
            "Diagnosis",
            "FlagA",
            "ValueC",
            "ValueD",
            "ValueI",
            "ValueJ",
            "ValueK",
        ]
        assert (names["ValueC"]["producer"], names["ValueC"]["kind"]) == (
            "SensorHub",
            "measurement",
        )
        # Every one of them is produced by something, so reading is all any of them may be.
        assert names["ValueC"]["scopes"] == ["input"]

    def test_the_kinds_carry_the_form_each_one_asks_for(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        forms = {entry["kind"]: entry for entry in body["kinds"]}
        assert list(forms) == ["measurement", "parameter", "value_block", "curve", "map", "axis"]
        required = {
            key["key"] for key in forms["value_block"]["keys"] if key["carried"][0]["required"]
        }
        assert required == {"volatile", "dimensions"}
        editors = {key["key"]: key["editor"] for key in forms["axis"]["keys"]}
        assert (editors["size"], editors["unit"], editors["input"]) == ("size", "unit", "name")

    def test_a_name_the_project_has_never_seen_may_take_any_scope(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        assert body["scopes"] == ["output", "input", "local"]

    def test_the_project_s_constants_come_with_it_for_a_value_block_s_dimensions(
        self, tmp_path
    ) -> None:
        # Review finding: the panel used to read these off the `dimensions` offer, which
        # `variable_keys` answers with `editor: "none"` and no choices - the variable's panel
        # shares that answer, so the field could never offer what spec 2 says a dimension may
        # name. examples/vocabulary is the example that declares any: one in the project's own
        # constants file and one inside the component, both of which a size may name.
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/declarable", file=(root / "pump.ddd.json").as_posix()).body
        assert body["constants"] == ["PRESSURE_CELLS", "TREND_SAMPLES"]
        dimensions = next(
            key
            for form in body["kinds"]
            if form["kind"] == "value_block"
            for key in form["keys"]
            if key["key"] == "dimensions"
        )
        assert (dimensions["editor"], dimensions["choices"]) == ("none", [])

    def test_a_project_declaring_no_constants_offers_none(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        assert body["constants"] == []

    def test_without_a_file_it_says_so(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/declarable")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "declarable takes ?file="

    def test_a_file_outside_the_project_is_not_found(self, demo, tmp_path) -> None:
        api, _ = demo
        reply = get(api, "/api/declarable", file=(tmp_path / "x.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_of_the_project_that_is_not_a_component_is_refused(self, demo) -> None:
        api, root = demo
        reply = get(api, "/api/declarable", file=(root / "demo.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "demo.ddd.json is not a component of the open project"

    def test_a_project_that_did_not_load_has_nothing_to_add_to(self, tmp_path) -> None:
        # Measured: `unloaded` leaves one file in the revision, p.ddd.json, kind "project", with
        # `index is None` - so it passes `_source` and is refused for the missing index before
        # the component check ever runs, the same answer `/api/declaration-plan` gives for the
        # same project.
        api = unloaded(tmp_path)
        reply = get(api, "/api/declarable", file=(tmp_path / "p.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "the open project did not load, so no interface of it can be changed"
        )


class TestPlanningAChangeOfAnInterface:
    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def controller(self, root: Path) -> str:
        return (root / "components" / "controller.ddd.json").as_posix()

    def test_reading_a_variable_is_previewed_then_written(self, demo) -> None:
        api, root = demo
        before = contents(root)
        preview = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="ValueC",
            scope="input",
        ).body
        assert contents(root) == before  # a plan writes nothing
        assert [Path(change["file"]).name for change in preview["changes"]] == [
            "controller.ddd.json"
        ]
        assert applied(api, preview, "reading ValueC").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "ValueC"' in written

    def test_declaring_a_new_object_takes_the_definition_as_json(self, demo) -> None:
        api, root = demo
        # `datatype` needs a `conversion` beside it - declaration_plans.declare_object now
        # validates the composed definition against the models, which is exactly the rule
        # tests/test_declaration_plans.py::TestDeclaringSomethingNew::
        # test_a_stated_datatype_with_no_conversion_is_refused_rather_than_planned pins for
        # this same definition minus the conversion.
        definition = json.dumps(
            {
                "name": "Pressure",
                "kind": "measurement",
                "datatype": "uint16",
                "conversion": {"kind": "identity"},
                "volatile": False,
            }
        )
        preview = get(
            api,
            "/api/declaration-plan",
            action="declare",
            file=self.controller(root),
            scope="output",
            definition=definition,
        ).body
        assert len(preview["changes"]) == 1
        assert applied(api, preview, "declaring Pressure").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "Pressure"' in written and '"id"' in written

    def test_removing_a_declaration_previews_its_going(self, demo) -> None:
        api, root = demo
        preview = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=self.controller(root),
            name="ValueA",
        ).body
        # `Hunk` carries whole lines under `before`/`after` (tests/test_gui_api.py already
        # reads it this way at TestEdit's "Hz" -> "rpm" assertions), not a per-line kind/text
        # breakdown - a removal's deleted lines are `before` with no `after` to match.
        removed = [
            line
            for change in preview["changes"]
            for hunk in change["hunks"]
            for line in hunk["before"]
        ]
        assert any('"name": "ValueA"' in text for text in removed)
        assert applied(api, preview, "removing ValueA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "ValueA"' not in written

    def test_an_action_that_is_not_one_of_the_three_says_which_are(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/declaration-plan", action="invent")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == (
            "declaration-plan takes ?action= one of read, declare, remove"
        )

    def test_an_action_missing_a_parameter_says_which_it_takes(self, demo) -> None:
        api, root = demo
        reply = get(api, "/api/declaration-plan", action="read", file=self.controller(root))
        assert reply.status == 400
        assert reply.body["message"] == "read takes ?file= and ?name= and ?scope="

    @pytest.mark.parametrize("definition", ["{not json", "[1, 2]"])
    def test_a_definition_that_is_not_a_json_object_is_refused(self, demo, definition) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="declare",
            file=self.controller(root),
            scope="output",
            definition=definition,
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "the definition is not json"

    def test_a_refusal_carries_the_module_s_own_code_and_sentence(self, demo) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="ValueA",
            scope="input",
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "this component already declares 'ValueA'"

    def test_a_name_the_project_has_not_is_not_found(self, demo) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="Nope",
            scope="input",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_outside_the_project_is_not_found(self, demo, tmp_path) -> None:
        api, _ = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=(tmp_path / "x.ddd.json").as_posix(),
            name="ValueA",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_project_that_did_not_load_has_nothing_to_plan_against(self, tmp_path) -> None:
        # The answer /api/type-plan already gives: measured, `unloaded`'s revision has
        # `index is None` and one file, p.ddd.json, which `_source` accepts - so the guard that
        # answers here is the missing index, not the missing file.
        api = unloaded(tmp_path)
        reply = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=(tmp_path / "p.ddd.json").as_posix(),
            name="ValueA",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, demo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The same pattern as TestTheTypesTab's equivalent, over /api/declaration-plan's own
        # call to `previewed`: a stale fingerprint or any other engine refusal reaches the page
        # exactly as /api/unit-plan and /api/type-plan already answer it.
        api, root = demo

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="ValueC",
            scope="input",
        )
        assert (reply.status, reply.body["error"]) == (409, "unverified")


class TestTheValuesGrid:
    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def test_a_curve_answers_its_row_and_its_axis(self, demo) -> None:
        api, _ = demo
        body = get(api, "/api/values", name="CurveA").body
        assert (body["kind"], body["datatype"], body["unit"]) == ("curve", "uint16", "ms")
        assert body["shape"] == [6]
        assert body["rows"] == [[1200, 900, 800, 750, 700, 650]]
        assert body["stated"] == "array"
        assert [(a["position"], a["name"], a["unit"]) for a in body["axes"]] == [
            ("axis", "AxisA", "Hz")
        ]
        assert body["axes"][0]["breakpoints"] == [0, 3200, 6400, 12800, 19200, 32000]
        assert body["owner"] == "Controller"
        assert body["file"].endswith("controller.ddd.json")

    def test_a_map_answers_four_rows_of_six(self, demo) -> None:
        api, _ = demo
        body = get(api, "/api/values", name="MapA").body
        assert body["shape"] == [4, 6]
        assert body["rows"][1] == [18, 22, 26, 28, 30, 28]
        assert [a["position"] for a in body["axes"]] == ["x_axis", "y_axis"]

    def test_an_object_with_no_shape_answers_an_empty_grid(self, demo) -> None:
        # The name is what the brief called this before Task 1's own fix (see task-1's report):
        # a shapeless object was once refused, and now answers the empty grid below instead -
        # grid_of's one refusal is "not-found" alone, so there is nothing left to refuse here.
        api, _ = demo
        reply = get(api, "/api/values", name="ValueA")
        assert reply.status == 200
        assert reply.body["shape"] == []

    def test_without_a_name_it_says_so(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/values")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "values takes ?name="

    def test_a_name_the_project_has_not_is_not_found(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/values", name="Nope")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_project_that_did_not_load_has_no_dictionary(self, tmp_path) -> None:
        reply = get(unloaded(tmp_path), "/api/values", name="Anything")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_the_findings_on_its_init_are_carried_and_others_are_not(self, tmp_path: Path) -> None:
        # examples/demo (the `demo` fixture above) has no finding at all - measured by
        # TestGraph.test_the_demo_lists_its_modules_and_the_flows_between_them, every module's
        # count is zero - so this exercises the filter with its own small project instead.
        # `Bad`'s only bad value (9999, over uint8) files `init-invalid` at exactly
        # `…definition.init`, the pointer test_finding_routes.py's own "Measured" note pins;
        # the same declaration, unread and unidentified, also files `unused-output` (at the
        # bare declaration) and `missing-id` (at `…definition.name`) - neither pointer ends
        # `.definition.init`, so neither is carried here.
        #
        # `Second` is declared beside it, in the same file, with its own bad value: a pointer
        # ending `.definition.init` is not enough to tell the two objects' findings apart, both
        # answer at `…interface[N].definition.init` for their own N - fix round 1's own defect,
        # reproduced here so it stays fixed. `Bad`'s own request must not carry `Second`'s
        # finding, and `Second`'s must not carry `Bad`'s.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Bad",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[2],
                        init=[1, 9999],
                    ),
                    declare(
                        "output",
                        "Second",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[2],
                        init=[2, 8888],
                    ),
                ),
            },
        )
        first = get(api, "/api/values", name="Bad").body["findings"]
        assert [(f["check"], f["pointer"]) for f in first] == [
            ("init-invalid", "component.interface[0].definition.init")
        ]
        second = get(api, "/api/values", name="Second").body["findings"]
        assert [(f["check"], f["pointer"]) for f in second] == [
            ("init-invalid", "component.interface[1].definition.init")
        ]

    def test_setting_a_cell_is_previewed_then_written(self, demo) -> None:
        api, root = demo
        before = contents(root)
        preview = get(api, "/api/value-plan", name="CurveA", at="[2]", raw="750").body
        assert contents(root) == before
        assert [Path(c["file"]).name for c in preview["changes"]] == ["controller.ddd.json"]
        assert applied(api, preview, "element 3 of CurveA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"init": [1200, 900, 750, 750, 700, 650]' in written

    def test_a_map_cell_names_its_row_and_column(self, demo) -> None:
        api, root = demo
        preview = get(api, "/api/value-plan", name="MapA", at="[1][3]", raw="99").body
        assert applied(api, preview, "element 2, 4 of MapA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert "[18, 22, 26, 99, 30, 28]" in written

    def test_a_plan_missing_a_parameter_says_which_it_takes(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/value-plan", name="CurveA")
        assert reply.status == 400
        assert reply.body["message"] == "value-plan takes ?name= and ?at= and ?raw="

    def test_a_raw_that_is_not_a_number_is_refused(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/value-plan", name="CurveA", at="[2]", raw="lots")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'lots' is not a number"

    def test_a_raw_that_is_valid_json_but_not_a_number_is_refused(self, demo) -> None:
        # `json.loads("true")` parses fine and answers a bool - which is an `int` in python, so
        # `isinstance(value, int | float)` alone would let it through as 1. `raw` is always a
        # count (spec 2026-09-23-gui-values-design.md section 4.3), and `true` is not one.
        api, _ = demo
        reply = get(api, "/api/value-plan", name="CurveA", at="[2]", raw="true")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'true' is not a number"

    def test_a_refusal_carries_the_module_s_own_sentence(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/value-plan", name="CurveA", at="[2]", raw="70000")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "70000 does not fit into uint16 (0 .. 65535)"

    def test_a_name_the_project_has_not_is_not_found_for_a_plan(self, demo) -> None:
        # set_cell raises "not-found" through grid_of, for a name the project has not - unlike
        # _values, this handler keeps both of set_cell's refusal codes, and this is the only
        # test reaching the 404 one; without it the status choice's "not-found" arm is untested.
        api, _ = demo
        reply = get(api, "/api/value-plan", name="Nope", at="[0]", raw="1")
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert reply.body["message"] == "the project declares no 'Nope'"

    def test_a_project_that_did_not_load_has_nothing_to_plan_a_value_of(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/value-plan", name="Anything", at="[0]", raw="1")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_plan_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, demo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The same pattern as TestPlanningAChangeOfAnInterface's equivalent, over
        # /api/value-plan's own call to `previewed`.
        api, _ = demo

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/value-plan", name="CurveA", at="[2]", raw="750")
        assert (reply.status, reply.body["error"]) == (409, "unverified")
