"""The JSON API of ddd gui, answered without a network: request in, reply out."""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Final

import pytest

from conftest import (
    EXAMPLES,
    build_record,
    component,
    declare,
    directory_link,
    project,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd import __version__
from ddd.cli import EXIT_OK, main
from ddd.diagnostics import CHECKS, Location
from ddd.editing import UNREADABLE, UNVERIFIED, UNWRITABLE, EditError, fingerprint
from ddd.file_plans import CREATABLE
from ddd.gui.api import (
    RASTER_PLANS,
    SECTION_PLANS,
    Api,
    Reply,
    _declared,
    _finding,
    _json_texts,
    _required_keys,
)
from ddd.gui.session import Filed, Revision, Session
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document
from ddd.object_values import grid_of
from ddd.project_shared import CONSTANTS, RASTERS, SECTIONS, Vocabulary
from ddd.project_shared import located_on as located_on_entry
from ddd.project_types import located_in_type
from ddd.project_units import located_on_unit
from ddd.variable_keys import KEY_ORDER
from ddd.variables import declarations_of, located_on

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

# A units file declaring nothing - what taking out the last unit nothing states leaves - in a
# project stating two units. A units file opts its project in whatever it declares, so both are
# `unknown-unit`, and adopting fills this file rather than writing a second one.
EMPTY_UNITS_FILE = {
    "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
    "units.ddd.json": {"units": []},
    "a.ddd.json": component(
        "A", declare("local", "Speed", unit="rpm"), declare("local", "Torque", unit="Nm")
    ),
}

# A units file that fails to load - the empty spelling is refused - in a project stating two units:
# the analysis indexes none of its entries, and adopting is refused while it does not load.
BROKEN_UNITS_FILE = {
    "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
    "units.ddd.json": {"units": ["rpm", ""]},
    "a.ddd.json": component(
        "A", declare("local", "Speed", unit="rpm"), declare("local", "Torque", unit="Nm")
    ),
}

# A sub-project's units file declaring nothing, which is the very units.ddd.json adopting would
# write beside the root description: the root lists no units file of its own, so adopting would
# create one there, and the file is there already.
SUB_PROJECTS_UNITS_FILE = {
    "p.ddd.json": project("P", "sub.ddd.json", "a.ddd.json"),
    "sub.ddd.json": project("Sub", "units.ddd.json"),
    "units.ddd.json": {"units": []},
    "a.ddd.json": component("A", declare("local", "Speed", unit="rpm")),
}

# A constant declared with no `description` at all - `set_entry`'s "nothing to remove" arm
# needs an entry the key is already absent from, which no shipped example happens to have.
NO_DESCRIPTION = {
    "p.ddd.json": project("P", "c.ddd.json"),
    "c.ddd.json": {"constants": [{"name": "BARE", "value": 1}]},
}

# A constants file whose one entry fails the format - missing `value` - so the project as a
# whole still opens (unlike a component, which loads nothing when invalid) but this one file
# does not: measured with a scratch probe, `built` is not `None` and `c.ddd.json` is in both
# `revision.files` (not loaded) and `project_of(CONSTANTS, ...).files` (still recognised as
# a constants file, since that only asks whether its top level holds a `constants` key).
UNREADABLE_CONSTANTS = {
    "p.ddd.json": project("P", "c.ddd.json"),
    "c.ddd.json": {"constants": [{"name": "BAD"}]},
}

# A stray constants.ddd.json beside the project description, naming nothing the project
# includes: `add` must refuse to create over it rather than overwrite a file it does not own.
STRAY_CONSTANTS_FILE = {
    "p.ddd.json": project("P", "a.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "constants.ddd.json": "not a file `add` wrote",
}

# One constant and nothing else in the file's own list, so removing it leaves `"constants": []` -
# refused while that was a schema error, and now a file that loads and declares nothing. Two
# clicks from this tab's own add flow, since nothing names it and Remove is offered.
SOLE_CONSTANT_IN_A_FILE = {
    "p.ddd.json": project("P", "c.ddd.json"),
    "c.ddd.json": {"constants": [{"name": "SOLE", "value": 4, "description": "the only one"}]},
}

# The same case in the other home, where the list may still not be empty: `Component.constants`
# keeps its `min_length=1`, and a component that stops loading takes every variable it declares
# out of the project with it - so its last constant goes with the `constants` key instead.
SOLE_CONSTANT_IN_A_COMPONENT = {
    "p.ddd.json": project("P", "a.ddd.json"),
    "a.ddd.json": component(
        "A", declare("output", "Speed", unit="rpm"), constants=[{"name": "SOLE", "value": 4}]
    ),
}

# A project whose only constants file is truncated the way an editor leaves one being typed
# into. It parses as nothing, so its kind cannot be told - and `add` must not read that as "this
# project has no constants file" and write a second one beside the description.
HALF_WRITTEN_CONSTANTS = {
    "p.ddd.json": project("P", "sizes.ddd.json", "a.ddd.json"),
    "sizes.ddd.json": '{"constants": [{"name": "',
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}

# Two constants, neither used, so that removing one leaves the other: the last one going is the
# case SOLE_CONSTANT_IN_A_FILE is for.
UNUSED_CONSTANT = {
    "p.ddd.json": project("P", "c.ddd.json"),
    "c.ddd.json": {
        "constants": [
            {"name": "SPARE", "value": 3, "description": "not used yet"},
            {"name": "KEPT", "value": 1, "description": "stays after SPARE goes"},
        ]
    },
}

# The sections the shipped example cannot supply: both of its own are placed in, so neither may
# be removed, and a project that has no sections file at all is the one `add` creates into.
#
# Two sections, one of them named by nothing, so that removing it leaves the other: the last one
# going is the case SOLE_SECTION_IN_A_FILE is for.
UNUSED_SECTION = {
    "p.ddd.json": project("P", "s.ddd.json", "a.ddd.json"),
    "s.ddd.json": {
        "sections": [
            {"section": ".spare", "access": "read-write", "alignment": 4},
            {"section": ".ram", "access": "read-write", "alignment": 4},
        ]
    },
    "a.ddd.json": component("A", declare("output", "Gain", section=".ram")),
}

# One section and nothing else in the list, so removing it leaves `"sections": []` - refused while
# that was a schema error, exactly as `"constants": []` was, and a file that loads now. Two clicks
# from this tab: declare a section into a project that has none, then remove it.
SOLE_SECTION_IN_A_FILE = {
    "p.ddd.json": project("P", "s.ddd.json"),
    "s.ddd.json": {"sections": [{"section": ".sole", "access": "read-write", "alignment": 4}]},
}

# A sections file whose one entry fails the format - no `access` - so the project as a whole
# still opens and this one file does not: measured, `built` is not `None` and `s.ddd.json` is in
# both `revision.files` (not loaded) and `project_of(SECTIONS, ...).files` (still recognised as a
# sections file, since that only asks whether its top level holds a `sections` key).
UNREADABLE_SECTIONS = {
    "p.ddd.json": project("P", "s.ddd.json"),
    "s.ddd.json": {"sections": [{"section": ".bad", "alignment": 4}]},
}

# A project whose only sections file is truncated the way an editor leaves one being typed into.
# Named `places.ddd.json` so that its kind cannot be guessed from its name either.
HALF_WRITTEN_SECTIONS = {
    "p.ddd.json": project("P", "places.ddd.json", "a.ddd.json"),
    "places.ddd.json": '{"sections": [{"section": "',
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}

# A stray sections.ddd.json beside the project description, naming nothing the project includes.
STRAY_SECTIONS_FILE = {
    "p.ddd.json": project("P", "a.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "sections.ddd.json": "not a file `add` wrote",
}

# A vocabulary whose `keys` are deliberately out of alphabetical order, for the two tests that ask
# which table `_required_keys` reads the order off. Every real vocabulary happens to draw its keys
# alphabetically - a section's `access`, `alignment`, `description` - so over `SECTIONS` alone the
# panel's order and `sorted(SECTIONS.required)` are the same list, and neither test could say which
# of the two it was seeing. Here they disagree on every position.
#
# Six keys rather than a section's three for a second reason, now retired but worth the sentence:
# while the order came off a frozenset it also changed with the interpreter's hash seed, and a set
# of two strings falls into sorted order under about half of them.
#
# Nothing about this descriptor describes a real vocabulary; `judge` covers every key only because
# `Vocabulary.__post_init__` refuses a descriptor whose tables disagree.
WIDE_KEYS: Final = ("f", "d", "b", "e", "a", "c")
WIDE: Final = dataclasses.replace(
    SECTIONS,
    keys=(*WIDE_KEYS, "description"),
    required=frozenset(WIDE_KEYS),
    judge=dict.fromkeys((*WIDE_KEYS, "description"), SECTIONS.judge["description"]),
)

# A consumer restating the producer's `section`, which is `consumer-storage`: a key only the
# component producing a variable may state, filed at the same `definition.section` pointer the
# section's own three checks are filed at. `.ram` is read-write so no `section-access` fires
# beside it, leaving one finding in the project that names a section and is not about it.
CONSUMER_PLACES = {
    "p.ddd.json": project("P", "s.ddd.json", "a.ddd.json", "b.ddd.json"),
    "s.ddd.json": {"sections": [{"section": ".ram", "access": "read-write", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "Gain", section=".ram")),
    "b.ddd.json": component("B", declare("input", "Gain", section=".ram")),
}

# A definition placed in a section no file declares, which is what `unknown-section` reports and
# the one route a reader follows to an add form rather than to a panel.
PLACED_NOWHERE = {
    "p.ddd.json": project("P", "s.ddd.json", "a.ddd.json"),
    "s.ddd.json": {"sections": [{"section": ".calib", "access": "read-only", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "Gain", section=".nvm")),
}

# The two shapes that name a raster, on one raster: a component's own default and a definition's
# own key. The shipped example has both shapes but not on one entry - its pump defaults to `10ms`
# and measures `PumpSpeed` in `1ms` - so a panel listing both in one answer needs this tree.
MEASURED_TWICE = {
    "p.ddd.json": project("P", "r.ddd.json", "a.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}

# A raster stating no `cycle` at all, which the model permits and gives no default for: every
# raster examples/vocabulary declares states one, so the key the panel reads as prose is never
# empty there.
NO_CYCLE = {
    "p.ddd.json": project("P", "r.ddd.json", "a.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "20ms", "event": 2}]},
    "a.ddd.json": component("A", declare("output", "X", raster="20ms")),
}

# One name declared twice, which the loader reports as `duplicate-raster` - filed at the second
# entry and again at the first, which is the copy the first entry's panel lists.
DECLARED_TWICE = {
    "p.ddd.json": project("P", "r.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1}, {"raster": "10ms", "event": 2}]},
}

# A definition measured in a raster no file declares, which is what `unknown-raster` reports and
# the one route a reader follows to an add form rather than to a panel.
MEASURED_NOWHERE = {
    "p.ddd.json": project("P", "r.ddd.json", "a.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="50ms")),
}

# A consumer restating the producer's `raster`, which is `consumer-raster`: a key only the
# component producing a variable may state, filed at the same `definition.raster` pointer
# `unknown-raster` is filed at. The raster's copy of CONSUMER_PLACES above.
CONSUMER_MEASURES = {
    "p.ddd.json": project("P", "r.ddd.json", "a.ddd.json", "b.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="10ms")),
    "b.ddd.json": component("B", declare("input", "X", raster="10ms")),
}

# A calibration object stating a raster, which is `raster-kind`: the third check filed at
# `definition.raster` and the second of the two that are about the declaration, not the raster.
CALIBRATION_MEASURED = {
    "p.ddd.json": project("P", "r.ddd.json", "a.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component(
        "A", declare("output", "Gain", kind="parameter", init=1, raster="10ms")
    ),
}

# A rasters file whose one entry fails the format - no `event` - so the project as a whole still
# opens and this one file does not: measured, `built` is not `None` and `r.ddd.json` is in both
# `revision.files` (not loaded) and `project_of(RASTERS, ...).files`, the sections fixture's own
# case at the third vocabulary.
UNREADABLE_RASTERS = {
    "p.ddd.json": project("P", "r.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "50ms"}]},
}

# One raster and nothing else in the list, so removing it leaves `"rasters": []` - refused while
# that was a schema error, exactly as `"sections": []` was, and a file that loads now.
SOLE_RASTER_IN_A_FILE = {
    "p.ddd.json": project("P", "r.ddd.json"),
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1}]},
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
        # Posix-separated, as every path the api hands the page is: this reason is drawn in the
        # same banner as the rest, and on windows it read with backslashes.
        assert (root / "other" / "q.ddd.json").as_posix() in reply.body["message"]

    def test_a_file_request_needs_a_path(self, api: Api) -> None:
        assert get(api, "/api/file").status == 400

    def test_a_file_request_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/file", path=(root / "a.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestWhatTheSessionServes:
    """``ddd gui`` serves the directory it was started in, and the project it was pointed at
    where that lies elsewhere. What the open project *includes* is wider than that and is the
    project's own business - a directory up is where a shared vocabulary lives - but an edit
    may add such an entry, so belonging to the project is a reach the page can widen for
    itself. These two directories it cannot.
    """

    @pytest.fixture
    def reaching_out(self, tmp_path: Path) -> tuple[Api, Path]:
        """A project under the root, its ``includes`` edited to name a file above the root -
        the escape, step one - and that file, which declares the same variable in another unit.
        """
        write_tree(
            tmp_path,
            {
                "outside.ddd.json": component("S", declare("output", "Speed", unit="rpm")),
                "inside/p.ddd.json": project("P", "a.ddd.json"),
                "inside/a.ddd.json": component("A", declare("input", "Speed", unit="km/h")),
            },
        )
        inside = tmp_path / "inside"
        session = Session(inside)
        session.open(inside / "p.ddd.json")
        api = Api(session, inside / "p.ddd.json", wait_seconds=0.05)
        described = inside / "p.ddd.json"
        added = post(
            api,
            "/api/edit",
            {
                "changes": [
                    {
                        "file": described.as_posix(),
                        "fingerprint": fingerprint(described.read_bytes()),
                        "operations": [
                            {
                                "op": "insert",
                                "pointer": "project.includes[1]",
                                "raw": '"../outside.ddd.json"',
                            }
                        ],
                    }
                ],
                "label": "one more include",
            },
        )
        assert added.status == 200
        outside = (tmp_path / "outside.ddd.json").resolve()
        revision = api.session.revision
        assert revision is not None
        # Step one worked: the file above the root is a file of the open project now. Asserted
        # here so no test below can pass by the edit having been refused instead.
        assert outside in {file.path for file in revision.files}
        return api, outside

    def test_a_file_outside_them_is_not_read(self, reaching_out: tuple[Api, Path]) -> None:
        api, outside = reaching_out
        reply = get(api, "/api/file", path=outside.as_posix())
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert outside.as_posix() in reply.body["message"]
        assert api.session.root.as_posix() in reply.body["message"]

    def test_an_edit_of_a_file_outside_them_is_refused(
        self, reaching_out: tuple[Api, Path]
    ) -> None:
        """Refused though the fingerprint is right: read from disk here, since the one route
        that would hand it over no longer does."""
        api, outside = reaching_out
        reply = post(
            api,
            "/api/edit",
            {
                "changes": [
                    {
                        "file": outside.as_posix(),
                        "fingerprint": fingerprint(outside.read_bytes()),
                        "operations": [{"op": "set", "pointer": UNIT, "raw": '"km/h"'}],
                    }
                ],
                "label": "the unit of Speed",
            },
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert outside.read_bytes() == json.dumps(
            component("S", declare("output", "Speed", unit="rpm")), indent=2
        ).encode("utf-8")

    def test_a_settlement_reaching_a_file_outside_them_is_refused(
        self, reaching_out: tuple[Api, Path]
    ) -> None:
        """A preview carries the very lines it would change, so offering this one would show a
        file the page may not read - and the edit it offers would then be refused anyway."""
        api, outside = reaching_out
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"km/h"')
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert outside.as_posix() in reply.body["message"]

    def test_a_settlement_reaching_only_served_files_is_offered(
        self, reaching_out: tuple[Api, Path]
    ) -> None:
        """The other way round on the same project: the value settled on is the one the file
        above the root already spells, so nothing there has to change and the preview stands."""
        api, _ = reaching_out
        reply = get(api, "/api/settle", name="Speed", key="unit", raw='"rpm"')
        assert reply.status == 200
        assert [Path(change["file"]).name for change in reply.body["changes"]] == ["a.ddd.json"]

    def test_a_project_named_from_outside_the_root_is_served_with_its_own_directory(
        self, tmp_path: Path
    ) -> None:
        """``ddd gui ../elsewhere/p.ddd.json`` serves the directory it was started in - where
        the picker looks - and the project the operator named, whose own directory that operator
        named just as plainly. Confined to the root alone, that invocation would answer a banner
        in place of every component's table.
        """
        write_tree(
            tmp_path,
            {
                "work/.keep": "",
                "elsewhere/p.ddd.json": project("P", "a.ddd.json"),
                "elsewhere/a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        described = tmp_path / "elsewhere" / "p.ddd.json"
        session = Session(tmp_path / "work")
        session.open(described)
        api = Api(session, described, wait_seconds=0.05)
        reply = get(api, "/api/file", path=(tmp_path / "elsewhere" / "a.ddd.json").as_posix())
        assert reply.status == 200
        assert reply.body["data"]["component"]["name"] == "A"


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

    def test_a_mismatch_is_previewed(self, tmp_path: Path) -> None:
        # Not applied here too, unlike the missing-id test above: applying is `POST /api/edit`
        # spelling the same operations regardless of which finding asked for them, and that
        # round trip is already shown there. What only this check can show is that the preview
        # really reaches the edit engine for a fix with several files behind one title.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        root = tmp_path
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "b.ddd.json"),
            pointer="component.interface[0].definition",
            check="definition-mismatch",
        )
        assert reply.status == 200
        assert reply.body["revision"] == 1
        assert [fix["title"] for fix in reply.body["fixes"]] == ["Use the unit declared in a"]
        (change,) = reply.body["fixes"][0]["changes"]
        assert change["file"] == posix(root, "b.ddd.json")
        assert change["hunks"], "the reader is shown the line it would change"

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

    def test_a_project_that_did_not_load_offers_no_fix(self, tmp_path: Path) -> None:
        # No index, no declarations: a revision whose project did not load has nothing to
        # reconcile, and this answers no fixes rather than an error - the one file such a
        # revision has is the project description itself.
        reply = get(
            unloaded(tmp_path),
            "/api/fix",
            file=posix(tmp_path, "p.ddd.json"),
            pointer="component.interface[0].definition",
            check="definition-mismatch",
        )
        assert (reply.status, reply.body["fixes"]) == (200, [])

    def test_fixing_needs_an_open_project(self, root: Path) -> None:
        reply = get(
            Api(Session(root)),
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (409, "no-project")


def dumped(source: Path, target: Path) -> None:
    """``target`` as ``ddd dump`` would write it for the project description at ``source``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    assert main(["dump", str(source), "-o", str(target)]) == EXIT_OK


class TestCompare:
    def test_a_project_compared_against_a_dump_of_itself_matches(
        self, api: Api, root: Path
    ) -> None:
        dump = root / "baseline.json"
        dumped(root / "p.ddd.json", dump)
        reply = get(api, "/api/compare", baseline=dump.as_posix())
        assert reply.status == 200
        assert reply.body["revision"] == 1
        assert reply.body["verdict"] is True
        assert reply.body["findings"] == []
        assert reply.body["baseline_findings"] == []
        assert reply.body["renames"] == []

    def test_a_drifted_datatype_fails_the_verdict_with_a_changed_interface_finding(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path
        write_tree(
            root,
            {
                "old/p.ddd.json": project("P", "a.ddd.json"),
                "old/a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        dumped(root / "old" / "p.ddd.json", dump)
        api = opened(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        reply = get(api, "/api/compare", baseline=dump.as_posix())
        assert reply.status == 200
        assert reply.body["verdict"] is False
        changed = [f for f in reply.body["findings"] if f["check"] == "changed-interface"]
        assert len(changed) == 1
        assert changed[0]["file"] == posix(root, "p.ddd.json")
        # `compare()` takes one location for the whole call, the way `ddd compare`'s own text
        # report does, so every finding of a comparison is filed at the candidate's own project
        # file - never at the component that happens to declare the object. `route_of` only
        # opens a component file at a declaration's own pointer, so - like every finding
        # `/api/state` already answers this way for a file that did not load or names no place -
        # there is nothing here for the page to open either.
        assert changed[0]["route"] is None

    def test_comparing_a_project_against_itself_with_its_own_conflict_never_routes_into_it(
        self, tmp_path: Path
    ) -> None:
        """The regression this route actually had: comparing a project against itself is the
        first thing a reader tries, and a baseline only has to sit under the session root - it
        is not required to be a file other than the candidate's own. Here the open project has
        a `multiple-producers` conflict of its own, so reading it a second time as its own
        baseline forwards that same conflict, once per producer, at files that really are
        `revision.files`' own. Neither answers a route: it used to, because the api asked
        "is this file one of the open project's" and answered honestly for a message that
        says "in the baseline: ..."; now a baseline finding is carried in its own field of the
        reply, `baseline_findings`, never in `findings` - marked by which one it is in, not by
        where its path happens to resolve to, and a page reading the wire is told the same way
        a test reading this reply's body now is."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
            },
        )
        reply = get(api, "/api/compare", baseline=posix(tmp_path, "p.ddd.json"))
        assert reply.status == 200
        # Never here: `multiple-producers` is not one of `compare`'s own comparison checks, and
        # nothing the baseline's analysis forwards is ever mixed into this field.
        assert not any(f["check"] == "multiple-producers" for f in reply.body["findings"])
        forwarded = [
            f for f in reply.body["baseline_findings"] if f["check"] == "multiple-producers"
        ]
        assert len(forwarded) == 2
        assert all(f["message"].startswith("in the baseline: ") for f in forwarded)
        assert all(f["route"] is None for f in forwarded)
        # Each really is a file of the open project - the coincidence a path check alone
        # cannot tell apart from a baseline kept somewhere else entirely.
        assert {Path(f["file"]).name for f in forwarded} == {"a.ddd.json", "b.ddd.json"}

    def test_a_missing_baseline_is_bad(self, api: Api) -> None:
        reply = get(api, "/api/compare")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_baseline_outside_the_root_is_refused(self, api: Api, tmp_path: Path) -> None:
        outside = tmp_path / "elsewhere.json"
        outside.write_text("{}")
        reply = get(api, "/api/compare", baseline=outside.as_posix())
        assert reply.status == 400
        assert "outside" in reply.body["message"]

    def test_an_unreadable_baseline_is_refused(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/compare", baseline=posix(root, "missing.json"))
        assert reply.status == 400
        assert "unreadable" in reply.body["message"]

    def test_a_baseline_path_with_a_nul_byte_is_refused(self, api: Api) -> None:
        """Reader input over the wire: ``parse_qs`` decodes ``%00`` into a real NUL. Before this
        was caught, that reached ``Path.resolve`` unguarded and left the terminal holding a
        traceback and the reader a 500 telling them to go and read it - and ``ddd gui --host``
        widens the bind beyond loopback."""
        baseline = "base\x00line.json"
        reply = get(api, "/api/compare", baseline=baseline)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        # Which of the four refusals answers this is platform-dependent, though a refusal
        # always does: `Path.resolve` raises `ValueError` on an embedded NUL on POSIX, straight
        # into the *unreadable* rule (`_resolved_baseline`'s `except (OSError, ValueError)`);
        # on Windows it resolves the path against the current drive instead - a real path that
        # merely lands outside the session root, straight into the confinement rule
        # (`is_relative_to`). Both name the path the reader typed in their message, which is
        # the one thing asserted here rather than pinning either reason by name.
        assert baseline in reply.body["message"]

    def test_a_baseline_whose_resolve_raises_a_value_error_is_refused(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forced rather than left to the platform, the way ``test_hardening.py``'s own
        ``test_a_path_refused_by_resolve_itself`` forces the same thing for the same reason: the
        NUL byte above only raises ``ValueError`` out of ``resolve()`` on POSIX, so the real test
        alone leaves this except clause unexercised on Windows - and the 100% coverage gate is
        read once per platform, not once for whichever machine happened to run the suite."""

        def refuse(self: Path, *args: object, **kwargs: object) -> Path:
            msg = "embedded null character in path"
            raise ValueError(msg)

        monkeypatch.setattr(Path, "resolve", refuse)
        reply = get(api, "/api/compare", baseline="whatever.json")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert "whatever.json' is unreadable" in reply.body["message"]

    def test_a_baseline_whose_resolve_raises_an_os_error_is_refused(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other exception the same clause catches, which nothing above ever reaches on
        either platform: ``Path.resolve()`` can still raise ``OSError`` outright even unstrict -
        a symlink loop is the one case it does not swallow. Forced for its own sake and not only
        the gate's: one ``except`` clause covering two exceptions is a choice that could quietly
        drop either from its tuple, and only a test naming each one separately would notice."""

        def refuse(self: Path, *args: object, **kwargs: object) -> Path:
            msg = "Too many levels of symbolic links"
            raise OSError(40, msg)

        monkeypatch.setattr(Path, "resolve", refuse)
        reply = get(api, "/api/compare", baseline="whatever.json")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert "whatever.json' is unreadable" in reply.body["message"]

    def test_a_baseline_that_is_not_json_is_refused(self, api: Api, root: Path) -> None:
        (root / "bad.json").write_text("{not json at all")
        reply = get(api, "/api/compare", baseline=posix(root, "bad.json"))
        assert reply.status == 400
        assert "not valid json" in reply.body["message"]

    def test_a_baseline_that_is_neither_a_dictionary_nor_a_description_is_refused(
        self, api: Api, root: Path
    ) -> None:
        # The fourth reason, the one nobody thinks of: a perfectly valid json file that is
        # simply something else.
        (root / "odd.json").write_text(json.dumps({"something": "else"}))
        reply = get(api, "/api/compare", baseline=posix(root, "odd.json"))
        assert reply.status == 400
        assert "neither a dictionary nor a description" in reply.body["message"]

    def test_a_project_that_did_not_load_cannot_be_compared(self, tmp_path: Path) -> None:
        reply = get(unloaded(tmp_path), "/api/compare", baseline=posix(tmp_path, "p.ddd.json"))
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_comparing_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/compare")
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

    def test_a_project_the_analysis_could_not_read_has_no_rows_and_is_offered_no_adoption(
        self, tmp_path: Path
    ) -> None:
        """No index, so no plan: the offer answers as the plan does, and not with 0, which the
        banner reads as "it states no unit" - of a project nobody could read."""
        api = unloaded(tmp_path)
        body = get(api, "/api/units").body
        assert (body["units"], body["adoptable"]) == ([], None)
        reply = get(api, "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_units_file_that_did_not_load_is_offered_no_adoption_the_plan_would_refuse(
        self, tmp_path: Path
    ) -> None:
        """The offer and the plan ask the same guards. Asked only whether a units file lists a
        unit the index holds, the offer would read a file that did not load as one listing
        nothing, and the banner would offer adopting two units the plan then refuses - a warning
        with no Adopt under it, for as long as the file being edited does not load."""
        api = opened(tmp_path, BROKEN_UNITS_FILE)
        assert get(api, "/api/units").body["adoptable"] is None
        reply = get(api, "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "units.ddd.json did not load, so adopting could not list every unit in use"
        )

    def test_a_sub_projects_units_file_where_adopting_would_write_is_offered_no_adoption(
        self, tmp_path: Path
    ) -> None:
        """The same property in the rarer shape: the root description lists no units file, so
        adopting would write units.ddd.json beside it - where a sub-project's own already is."""
        api = opened(tmp_path, SUB_PROJECTS_UNITS_FILE)
        assert get(api, "/api/units").body["adoptable"] is None
        reply = get(api, "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == (
            "adopting writes units.ddd.json beside p.ddd.json, and a file of that name is there "
            "already"
        )

    def test_a_units_file_declaring_nothing_reports_every_unit_and_offers_adopting_them(
        self, tmp_path: Path
    ) -> None:
        """The file opts the project in, so each stated unit is a row carrying its finding, and
        adoption is offered - the count the server gives is the page's whole answer to whether."""
        body = get(opened(tmp_path, EMPTY_UNITS_FILE), "/api/units").body
        assert body["vocabulary"] == []
        assert [(u["unit"], u["files"], u["findings"]) for u in body["units"]] == [
            ("Nm", [], 1),
            ("rpm", [], 1),
        ]
        assert body["adoptable"] == 2

    def test_adopting_fills_a_units_file_declaring_nothing(self, tmp_path: Path) -> None:
        """One file changed and none created: the project description keeps its ``includes``."""
        api = opened(tmp_path, EMPTY_UNITS_FILE)
        before = contents(tmp_path)
        preview = get(api, "/api/unit-plan", action="adopt").body
        assert [(Path(c["file"]).name, c["fingerprint"] is None) for c in preview["changes"]] == [
            ("units.ddd.json", False)
        ]
        assert applied(api, preview, "the vocabulary adopted").status == 200
        assert contents(tmp_path)["p.ddd.json"] == before["p.ddd.json"]
        listed = json.loads((tmp_path / "units.ddd.json").read_text(encoding="utf-8"))["units"]
        assert [entry["unit"] for entry in listed] == ["Nm", "rpm"]
        body = get(api, "/api/units").body
        assert body["adoptable"] is None
        assert [(u["unit"], u["findings"]) for u in body["units"]] == [("Nm", 0), ("rpm", 0)]


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


class TestShared:
    """``GET /api/shared``: the Shared files tab's one table, over examples/vocabulary - the one
    example declaring a constant in a constants file (`TREND_SAMPLES`) and one inline in a
    component (`PRESSURE_CELLS`), both named by a dimension, two memory sections its pump places
    data in, and three measurement rasters it samples on, checking clean."""

    def test_the_table_lists_every_entry_of_every_kind_with_what_it_states(
        self, tmp_path: Path
    ) -> None:
        """All three vocabularies in one table, sorted by kind then name: the endpoint answers
        whatever `ddd.project_shared.HELD` holds, so a section row and then a raster row each
        arrived here without this route learning that either exists. A constant states the json
        text of its value; a section its access and its alignment; a raster its event and its
        cycle - which is why the column is headed `States` and not `Value`. The three rasters sort
        by name as strings, which puts `100ms` in front of `1ms`."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/shared").body
        assert body["revision"] == 1
        assert [(e["kind"], e["name"], e["states"]) for e in body["entries"]] == [
            ("constant", "PRESSURE_CELLS", "8"),
            ("constant", "TREND_SAMPLES", "16"),
            ("raster", "100ms", "event 2, 100ms"),
            ("raster", "10ms", "event 1, 10ms"),
            ("raster", "1ms", "event 0, 1ms"),
            ("section", ".calib", "read-only, align 4"),
            ("section", ".fast_ram", "read-write, align 4"),
        ]

    def test_each_row_counts_its_uses_and_its_findings(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        rows = {e["name"]: e for e in get(api, "/api/shared").body["entries"]}
        assert (rows["PRESSURE_CELLS"]["uses"], rows["PRESSURE_CELLS"]["findings"]) == (1, 0)
        assert (rows["TREND_SAMPLES"]["uses"], rows["TREND_SAMPLES"]["findings"]) == (1, 0)

    def test_a_finding_on_a_shape_naming_a_constant_counts_on_its_row(self, tmp_path: Path) -> None:
        """Review finding: every fixture elsewhere in this class checks clean, so a row's own
        `findings` count was never asked to be anything but 0 - a mutation that hard-codes it to
        0 passed the whole file. `dimension-value` is filed at the shape naming the constant, not
        at its own entry (`located_on` counts both), so breaking `TREND_SAMPLES`'s value
        files exactly one finding, on the one row, without disturbing `PRESSURE_CELLS`'s."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        text = (root / "constants.ddd.json").read_text(encoding="utf-8")
        (root / "constants.ddd.json").write_text(
            text.replace('"value": 16', '"value": 0'), encoding="utf-8"
        )
        api.session.poll()
        rows = {e["name"]: e for e in get(api, "/api/shared").body["entries"]}
        assert rows["TREND_SAMPLES"]["findings"] == 1
        assert rows["PRESSURE_CELLS"]["findings"] == 0

    def test_a_project_declaring_none_of_them_has_an_empty_table(self, api: Api) -> None:
        # The `api` fixture's project includes neither a constants file nor a sections one.
        assert get(api, "/api/shared").body["entries"] == []

    def test_a_project_the_analysis_could_not_read_has_an_empty_table(self, tmp_path: Path) -> None:
        assert get(unloaded(tmp_path), "/api/shared").body["entries"] == []

    def test_shared_needs_an_open_project(self, root: Path) -> None:
        assert get(Api(Session(root)), "/api/shared").status == 409


class TestConstant:
    """``GET /api/constant`` and ``GET /api/constant-plan``, over examples/vocabulary and a
    handful of small trees it cannot exercise on its own: an absent key, a constants file that
    did not load, a stray one beside the project description, and a constant nothing uses."""

    def test_the_panel_names_its_entry_its_uses_and_its_description(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/constant", name="PRESSURE_CELLS").body
        assert body["revision"] == 1
        assert body["value"] == "8"
        assert body["description"] == "cells of the pressure manifold"
        assert body["file"] == posix(root, "pump.ddd.json")
        assert body["pointer"] == "component.constants[0]"
        assert [(u["kind"], u["name"], u["component"]) for u in body["uses"]] == [
            ("variable", "ManifoldPressure", "Pump")
        ]
        assert body["findings"] == []

    def test_a_constant_declared_in_a_constants_file_answers_the_same_shape(
        self, tmp_path: Path
    ) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/constant", name="TREND_SAMPLES").body
        assert body["value"] == "16"
        assert body["description"].startswith("sample slots of a pressure trend buffer")
        assert body["file"] == posix(root, "constants.ddd.json")
        assert body["pointer"] == "constants[0]"
        assert [(u["kind"], u["name"], u["component"]) for u in body["uses"]] == [
            ("variable", "PressureTrend", "Pump")
        ]

    def test_a_dimension_value_finding_routes_back_to_the_constant_and_nowhere_else(
        self, tmp_path: Path
    ) -> None:
        """Pins the fix that belongs beside this route: ``FindingRoute.kind`` had no
        ``"constant"`` member until this part, so building this very finding for the panel
        raised a ``pydantic.ValidationError`` before a test ever reached the assertion below -
        every other test of this class happens to ask about a constant with no finding on it,
        which is why only this one catches it. Also checks the finding does not bleed into a
        different constant's own count."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        text = (root / "constants.ddd.json").read_text(encoding="utf-8")
        (root / "constants.ddd.json").write_text(
            text.replace('"value": 16', '"value": 0'), encoding="utf-8"
        )
        api.session.poll()
        trend = get(api, "/api/constant", name="TREND_SAMPLES").body
        findings = {f["check"]: f for f in trend["findings"]}
        assert findings["dimension-value"]["route"] == {
            "kind": "constant",
            "name": "TREND_SAMPLES",
        }
        pressure = get(api, "/api/constant", name="PRESSURE_CELLS").body
        assert pressure["findings"] == []

    def test_a_constant_is_asked_for_by_name(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_constant_the_project_does_not_declare_is_not_found(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant", name="NOTHING")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_name_only_a_file_that_did_not_load_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        files = {
            "p.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": json.dumps(
                component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    constants=[{"name": "GHOST", "value": 1}],
                ),
                indent=2,
            )[:60],
        }
        reply = get(opened(tmp_path, files), "/api/constant", name="GHOST")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "a.ddd.json did not load" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_cannot_answer_a_constant(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/constant", name="TREND_SAMPLES")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_constant_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/constant", name="TREND_SAMPLES")
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_setting_a_value_is_previewed_then_written(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        preview = get(
            api, "/api/constant-plan", action="set", name="PRESSURE_CELLS", key="value", raw="9"
        ).body
        assert contents(root) == before
        assert [Path(c["file"]).name for c in preview["changes"]] == ["pump.ddd.json"]
        assert applied(api, preview, "the value of PRESSURE_CELLS").status == 200
        assert '"value": 9' in (root / "pump.ddd.json").read_text(encoding="utf-8")

    def test_renaming_rewrites_the_entry_and_every_shape_naming_it(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(
            api, "/api/constant-plan", action="rename", name="TREND_SAMPLES", to="SAMPLE_COUNT"
        ).body
        assert [Path(c["file"]).name for c in preview["changes"]] == [
            "constants.ddd.json",
            "pump.ddd.json",
        ]
        label = "the rename of 'TREND_SAMPLES' to 'SAMPLE_COUNT'"
        assert applied(api, preview, label).status == 200
        for name in ("constants.ddd.json", "pump.ddd.json"):
            assert "TREND_SAMPLES" not in (root / name).read_text(encoding="utf-8")
        assert get(api, "/api/constant", name="SAMPLE_COUNT").status == 200
        assert get(api, "/api/constant", name="TREND_SAMPLES").status == 404

    @pytest.mark.parametrize(
        ("to", "says"),
        [("PRESSURE_CELLS", "is the name of the declared constant"), ("if", "is reserved")],
    )
    def test_a_rename_that_may_not_be_made_is_refused_in_the_editor_s_words(
        self, tmp_path: Path, to: str, says: str
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant-plan", action="rename", name="TREND_SAMPLES", to=to)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert says in reply.body["message"]

    def test_removing_an_unused_constant_takes_its_entry_out(self, tmp_path: Path) -> None:
        api = opened(tmp_path, UNUSED_CONSTANT)
        preview = get(api, "/api/constant-plan", action="remove", name="SPARE").body
        assert applied(api, preview, "SPARE removed").status == 200
        assert get(api, "/api/constant", name="SPARE").status == 404

    def test_removing_the_only_constant_a_file_declares_leaves_it_declaring_nothing(
        self, tmp_path: Path
    ) -> None:
        """This request used to be refused, `{"constants": []}` being a schema error. The file's
        own list may be empty now: the removal is applied, and what is left loads, reported as
        `empty-vocabulary` at the list - so the project stays open rather than emptying the page.
        """
        api = opened(tmp_path, SOLE_CONSTANT_IN_A_FILE)
        preview = get(api, "/api/constant-plan", action="remove", name="SOLE").body
        assert applied(api, preview, "SOLE removed").status == 200
        written = json.loads((tmp_path / "c.ddd.json").read_text(encoding="utf-8"))
        assert written == {"constants": []}
        state = get(api, "/api/state").body
        assert [(f["check"], f["severity"], f["pointer"]) for f in state["findings"]] == [
            ("empty-vocabulary", "info", "constants")
        ]
        assert get(api, "/api/constant", name="SOLE").status == 404

    def test_removing_the_only_constant_a_component_declares_inline_takes_the_key_with_it(
        self, tmp_path: Path
    ) -> None:
        """The other home, whose list may still not be empty: a component publishing no constant
        leaves the key out, so the key goes with its last entry. `"constants": []` written there
        would stop the component loading, and `Speed` - every variable it declares - would leave
        the project along with the constant the reader meant to remove."""
        api = opened(tmp_path, SOLE_CONSTANT_IN_A_COMPONENT)
        preview = get(api, "/api/constant-plan", action="remove", name="SOLE").body
        assert [change["operations"] for change in preview["changes"]] == [
            [{"op": "remove", "pointer": "component.constants", "raw": None}]
        ]
        assert applied(api, preview, "SOLE removed").status == 200
        written = json.loads((tmp_path / "a.ddd.json").read_text(encoding="utf-8"))
        assert "constants" not in written["component"]
        assert "schema" not in {f["check"] for f in get(api, "/api/state").body["findings"]}
        assert get(api, "/api/variable", name="Speed").status == 200
        assert get(api, "/api/constant", name="SOLE").status == 404

    def test_removing_a_constant_a_shape_names_is_refused(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        reply = get(api, "/api/constant-plan", action="remove", name="TREND_SAMPLES")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert "pump.ddd.json" in reply.body["message"]
        assert contents(root) == before

    def test_adding_to_an_existing_constants_file_is_previewed_then_written(
        self, tmp_path: Path
    ) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(api, "/api/constant-plan", action="add", name="SPARE_CELLS", raw="4").body
        assert [Path(c["file"]).name for c in preview["changes"]] == ["constants.ddd.json"]
        assert applied(api, preview, "SPARE_CELLS declared").status == 200
        text = (root / "constants.ddd.json").read_text(encoding="utf-8")
        assert '"name": "SPARE_CELLS"' in text
        assert get(api, "/api/constant", name="SPARE_CELLS").status == 200

    def test_adding_when_the_project_has_no_constants_file_creates_one(
        self, api: Api, root: Path
    ) -> None:
        before = contents(root)
        preview = get(api, "/api/constant-plan", action="add", name="NEW_CONST", raw="5").body
        assert contents(root) == before
        # Sorted by path, as `SharedPlan` promises: "constants.ddd.json" sorts before
        # "p.ddd.json" beside it, unlike the units precedent this test is modelled on, where the
        # project file happens to sort first - so the two are told apart here by which one has a
        # fingerprint rather than by position.
        created, described = preview["changes"]
        assert (Path(described["file"]).name, Path(created["file"]).name) == (
            "p.ddd.json",
            "constants.ddd.json",
        )
        assert described["fingerprint"] == fingerprint(before["p.ddd.json"])
        assert created["fingerprint"] is None
        assert applied(api, preview, "NEW_CONST declared").status == 200
        text = (root / "constants.ddd.json").read_text(encoding="utf-8")
        assert created["hunks"] == [{"line": 1, "before": [], "after": text.splitlines()}]
        # The whole entry, not just its name: `add` gives `description` an empty string of its
        # own although the form asks for none, and nothing else in this suite says so - the hunk
        # above is checked against the file it wrote, so it agrees with whatever was written.
        assert json.loads(text)["constants"] == [
            {"name": "NEW_CONST", "value": 5, "description": ""}
        ]
        assert '"constants.ddd.json"' in (root / "p.ddd.json").read_text(encoding="utf-8")

    def test_an_add_of_a_name_already_declared_is_refused_in_the_editor_s_words(
        self, tmp_path: Path
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant-plan", action="add", name="PRESSURE_CELLS", raw="1")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert "is the name of the declared constant" in reply.body["message"]

    def test_an_add_while_the_constants_file_did_not_load_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, UNREADABLE_CONSTANTS),
            "/api/constant-plan",
            action="add",
            name="NEW",
            raw="1",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "c.ddd.json" in reply.body["message"]

    def test_an_add_while_a_file_nobody_could_read_is_included_creates_nothing(
        self, tmp_path: Path
    ) -> None:
        """Measured before it was guarded: with `sizes.ddd.json` truncated mid-save, the index is
        still built - so the 409 the route gives an unreadable project never fires - and this
        request answered 200 with a two-edit plan creating a second `constants.ddd.json` and
        adding it to `project.includes`. What the truncated file declares is unknown, so the name
        declared here can collide with one in it the moment it is saved."""
        api = opened(tmp_path, HALF_WRITTEN_CONSTANTS)
        before = contents(tmp_path)
        reply = get(api, "/api/constant-plan", action="add", name="NEW_ONE", raw="8")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "sizes.ddd.json did not parse" in reply.body["message"]
        assert contents(tmp_path) == before

    def test_an_add_that_would_overwrite_a_stray_file_is_refused(self, tmp_path: Path) -> None:
        reply = get(
            opened(tmp_path, STRAY_CONSTANTS_FILE),
            "/api/constant-plan",
            action="add",
            name="NEW",
            raw="1",
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert "constants.ddd.json" in reply.body["message"]

    def test_a_constant_no_file_declares_cannot_be_changed(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant-plan", action="set", name="NOPE", key="value", raw="1")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_setting_an_absent_key_to_nothing_is_an_empty_plan_not_a_refusal(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, NO_DESCRIPTION),
            "/api/constant-plan",
            action="set",
            name="BARE",
            key="description",
        )
        assert reply.status == 200
        assert reply.body["changes"] == []

    def test_a_malformed_raw_is_bad_before_any_refusal_about_the_project(
        self, tmp_path: Path
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(
            api,
            "/api/constant-plan",
            action="set",
            name="TREND_SAMPLES",
            key="value",
            raw="not json",
        )
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"action": "dance", "name": "TREND_SAMPLES"},
            {"action": "set", "name": "TREND_SAMPLES"},
            {"action": "set", "name": "", "key": "value", "raw": "1"},
            {"action": "rename", "name": "TREND_SAMPLES"},
            {"action": "add", "name": "NEW"},
            {"action": "add", "name": "NEW", "raw": ""},
            {"action": "remove"},
        ],
    )
    def test_a_missing_or_unknown_parameter_is_a_bad_request(
        self, tmp_path: Path, query: dict[str, str]
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/constant-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_project_the_analysis_could_not_read_plans_no_constant_change(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/constant-plan", action="remove", name="X")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"].startswith("p.ddd.json did not load")

    def test_a_constant_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(
            api, "/api/constant-plan", action="set", name="TREND_SAMPLES", key="value", raw="20"
        )
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_constant_plan_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/constant-plan", action="remove", name="X")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestSection:
    """``GET /api/section`` and ``GET /api/section-plan``, over examples/vocabulary and the small
    trees it cannot supply: both of its sections are placed in, so neither may be removed, and it
    has a sections file, so nothing there reaches ``add``'s creating arm.

    The constants pair's sibling, request for request, which is the point: the two routes run the
    same five verbs over a different :class:`~ddd.project_shared.Vocabulary`, so a case one of
    them answers and the other does not would be a case the descriptor failed to describe.
    """

    def test_the_panel_names_its_entry_its_keys_and_the_variable_it_holds(
        self, tmp_path: Path
    ) -> None:
        """`access` and `description` arrive as prose and `alignment` as the json text its file
        spells, which is what `SECTIONS.strings` decides: read the other way round, `access` would
        carry its quotes onto the chooser and `alignment` would come back empty, the value at that
        key being no string."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/section", name=".calib").body
        assert body["revision"] == 1
        assert body["name"] == ".calib"
        assert body["access"] == "read-only"
        assert body["alignment"] == "4"
        assert body["description"].startswith("calibration flash")
        assert body["file"] == posix(root, "sections.ddd.json")
        assert body["pointer"] == "sections[1]"
        assert [(u["kind"], u["name"], u["component"], u["pointer"]) for u in body["uses"]] == [
            ("variable", "TorqueLimit", "Pump", "component.interface[3].definition.section")
        ]
        assert body["findings"] == []

    def test_a_section_two_definitions_place_data_in_lists_both(self, tmp_path: Path) -> None:
        """The count is the one a reader of the tab came for - which variables sit there - so a
        panel listing whichever the index happened to record first would be worse than none.
        `.calib` above holds one; `.fast_ram` is the example's other section and holds two."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/section", name=".fast_ram").body
        assert body["access"] == "read-write"
        assert [u["name"] for u in body["uses"]] == ["PumpSpeed", "ManifoldPressure"]

    def test_a_finding_at_a_definition_placing_data_there_is_the_section_s_own(
        self, tmp_path: Path
    ) -> None:
        """Both arms of the panel's own filter in one revision: `section-access` is filed at the
        definition's `section` key - a use site, never the entry - so making `.fast_ram` read-only
        files one finding per measurement it holds, on that panel, and leaves `.calib`'s empty.

        Each leads back to the section it is shown on, which is `PLACEMENT_KEY` reaching through
        the api: both findings name `.fast_ram`, the `access` they complain about is the one this
        panel edits, and the two variables they are also about are in the `uses` list beside them.
        The same request answered `{"kind": "variable", ...}` before the route became pointer
        shaped, which is the split spec 4.6 does not draw."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        text = (root / "sections.ddd.json").read_text(encoding="utf-8")
        (root / "sections.ddd.json").write_text(
            text.replace(
                '"section": ".fast_ram", "access": "read-write"',
                '"section": ".fast_ram", "access": "read-only"',
            ),
            encoding="utf-8",
        )
        api.session.poll()
        fast = get(api, "/api/section", name=".fast_ram").body
        assert [(f["check"], f["route"]) for f in fast["findings"]] == [
            ("section-access", {"kind": "section", "name": ".fast_ram"}),
            ("section-access", {"kind": "section", "name": ".fast_ram"}),
        ]
        assert [f["message"].split("'")[1] for f in fast["findings"]] == [
            "PumpSpeed",
            "ManifoldPressure",
        ]
        assert [u["name"] for u in fast["uses"]] == ["PumpSpeed", "ManifoldPressure"]
        assert get(api, "/api/section", name=".calib").body["findings"] == []

    def test_a_duplicate_section_finding_routes_back_to_the_section(self, tmp_path: Path) -> None:
        """The fix that belongs beside the route: `FindingRoute.kind` had no `"section"` member
        until this part, and `_finding` builds that model for every finding of every request - so
        this panel raised a `pydantic.ValidationError` before a test could reach the assertion,
        exactly as part 13's `constant` nearly shipped. Every other test of this class asks about a
        section carrying no section-routed finding, which is why only this one catches it."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "s.ddd.json"),
                "s.ddd.json": {
                    "sections": [
                        {"section": ".calib", "access": "read-only", "alignment": 4},
                        {"section": ".calib", "access": "read-write", "alignment": 8},
                    ]
                },
            },
        )
        body = get(api, "/api/section", name=".calib").body
        assert [(f["check"], f["route"]) for f in body["findings"]] == [
            ("duplicate-section", {"kind": "section", "name": ".calib"})
        ]

    def test_a_consumers_stray_section_key_is_neither_counted_nor_listed_on_the_section(
        self, tmp_path: Path
    ) -> None:
        """Both halves of the same rule, end to end, which the branch's final review found the
        route obeying and the reader's two screens not.

        `consumer-storage` is filed at `component.interface[i].definition.section`, so it matched
        every pointer test `located_on` makes: measured before the fix, this project's `.ram` row
        read `findings: 1` and its panel listed a finding whose route left the panel, with nothing
        in it a reader could act on. The Findings column is what a reader scans for what needs
        attention, so a count they cannot act on is worse than no count.

        The finding is not lost, only re-attributed, which the third assertion holds: the project
        still reports it, at the declaration that states the key, where the fix is. And the `uses`
        count stays at two - the consumer's key really does name the section, which is exactly what
        `consumer-storage` complains about."""
        api = opened(tmp_path, CONSUMER_PLACES)
        row = {e["name"]: e for e in get(api, "/api/shared").body["entries"]}[".ram"]
        assert (row["uses"], row["findings"]) == (2, 0)
        assert get(api, "/api/section", name=".ram").body["findings"] == []
        assert {f["check"]: f["route"] for f in get(api, "/api/state").body["findings"]}[
            "consumer-storage"
        ] == {"kind": "variable", "name": "Gain"}

    def test_an_unknown_section_leads_to_the_name_the_definition_names(
        self, tmp_path: Path
    ) -> None:
        """The route the page turns into a pre-filled add form: the name is in no index, so the
        panel would answer 404 and the route carries it anyway."""
        state = get(opened(tmp_path, PLACED_NOWHERE), "/api/state").body
        routes = {f["check"]: f["route"] for f in state["findings"]}
        assert routes["unknown-section"] == {"kind": "section", "name": ".nvm"}

    def test_a_section_is_asked_for_by_name(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "section takes ?name="

    def test_a_section_the_project_does_not_declare_is_not_found(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section", name=".nvm")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_name_only_a_sections_file_that_did_not_load_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        reply = get(opened(tmp_path, UNREADABLE_SECTIONS), "/api/section", name=".bad")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "s.ddd.json did not load" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_cannot_answer_a_section(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/section", name=".calib")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_section_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/section", name=".calib")
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_setting_an_alignment_is_previewed_then_written(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        preview = get(
            api, "/api/section-plan", action="set", name=".calib", key="alignment", raw="8"
        ).body
        assert contents(root) == before
        assert [Path(c["file"]).name for c in preview["changes"]] == ["sections.ddd.json"]
        assert applied(api, preview, "the alignment of .calib").status == 200
        assert '"alignment": 8' in (root / "sections.ddd.json").read_text(encoding="utf-8")
        assert get(api, "/api/section", name=".calib").body["alignment"] == "8"

    def test_renaming_rewrites_the_entry_and_every_definition_placing_data_there(
        self, tmp_path: Path
    ) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(api, "/api/section-plan", action="rename", name=".calib", to=".eeprom").body
        assert [Path(c["file"]).name for c in preview["changes"]] == [
            "pump.ddd.json",
            "sections.ddd.json",
        ]
        assert applied(api, preview, "the rename of '.calib' to '.eeprom'").status == 200
        for name in ("sections.ddd.json", "pump.ddd.json"):
            assert ".calib" not in (root / name).read_text(encoding="utf-8")
        assert get(api, "/api/section", name=".eeprom").status == 200
        assert get(api, "/api/section", name=".calib").status == 404

    def test_declaring_one_takes_a_json_text_per_key_the_model_gives_no_default(
        self, tmp_path: Path
    ) -> None:
        """Where a constant's `add` takes a lone `?raw=`: a section the file states no `access` or
        no `alignment` for is one that does not load, so both are the request's to supply and
        `description`, which defaults, is not."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(
            api,
            "/api/section-plan",
            action="add",
            name=".nvm",
            access='"read-write"',
            alignment="8",
        ).body
        assert [Path(c["file"]).name for c in preview["changes"]] == ["sections.ddd.json"]
        assert applied(api, preview, ".nvm declared").status == 200
        declared = json.loads((root / "sections.ddd.json").read_text(encoding="utf-8"))
        assert declared["sections"][-1] == {
            "section": ".nvm",
            "access": "read-write",
            "alignment": 8,
            "description": "",
        }
        assert get(api, "/api/section", name=".nvm").status == 200

    def test_adding_when_the_project_has_no_sections_file_creates_one(
        self, api: Api, root: Path
    ) -> None:
        """`SECTIONS.filename` and `SECTIONS.containers[0]` both, in the bytes of a file nothing
        else in this suite ever sees written: the name beside the description and the key its one
        entry is wrapped in."""
        before = contents(root)
        preview = get(
            api,
            "/api/section-plan",
            action="add",
            name=".nvm",
            access='"read-write"',
            alignment="4",
        ).body
        assert contents(root) == before
        described, created = preview["changes"]
        assert (Path(described["file"]).name, Path(created["file"]).name) == (
            "p.ddd.json",
            "sections.ddd.json",
        )
        assert (described["fingerprint"], created["fingerprint"]) == (
            fingerprint(before["p.ddd.json"]),
            None,
        )
        assert applied(api, preview, ".nvm declared").status == 200
        assert created["hunks"] == [
            {
                "line": 1,
                "before": [],
                "after": [
                    "{",
                    '  "sections": [',
                    '    { "section": ".nvm", "access": "read-write", "alignment": 4, '
                    '"description": "" }',
                    "  ]",
                    "}",
                ],
            }
        ]
        assert '"sections.ddd.json"' in (root / "p.ddd.json").read_text(encoding="utf-8")

    def test_removing_a_section_nothing_places_data_in_takes_its_entry_out(
        self, tmp_path: Path
    ) -> None:
        api = opened(tmp_path, UNUSED_SECTION)
        preview = get(api, "/api/section-plan", action="remove", name=".spare").body
        assert applied(api, preview, ".spare removed").status == 200
        assert get(api, "/api/section", name=".spare").status == 404
        assert get(api, "/api/section", name=".ram").status == 200

    @pytest.mark.parametrize(
        ("query", "says"),
        [
            (
                {"action": "rename", "name": ".calib", "to": "my section"},
                "'my section' is not a usable linker section name",
            ),
            (
                {"action": "rename", "name": ".calib", "to": ".fast_ram"},
                "'.fast_ram' is already a section this project declares",
            ),
            (
                {"action": "add", "name": ".fast_ram", "access": '"read-write"', "alignment": "4"},
                "'.fast_ram' is already a section this project declares",
            ),
            (
                {"action": "set", "name": ".calib", "key": "alignment", "raw": "3"},
                "3 is not an alignment a section may state, so '.calib' cannot take it in "
                "sections.ddd.json: a power of two",
            ),
            (
                {"action": "add", "name": ".nvm", "access": '"read-write"', "alignment": "3"},
                "3 is not an alignment a section may state, so '.nvm' cannot take it in "
                "sections.ddd.json: a power of two",
            ),
            (
                {"action": "set", "name": ".calib", "key": "access", "raw": '"read-sideways"'},
                "\"read-sideways\" is not an access a section may state, so '.calib' cannot take "
                "it in sections.ddd.json: read-write or read-only",
            ),
            (
                {"action": "set", "name": ".calib", "key": "access"},
                "a section states an access, so '.calib' cannot be left without one in "
                "sections.ddd.json",
            ),
            (
                {"action": "set", "name": ".calib", "key": "unit", "raw": '"rpm"'},
                "a section has no 'unit' to set in sections.ddd.json: it states access, "
                "alignment and description",
            ),
            (
                {"action": "remove", "name": ".calib"},
                "'.calib' is named by 1 shape, the first in pump.ddd.json",
            ),
        ],
    )
    def test_a_change_the_project_refuses_says_why_in_the_format_s_own_words(
        self, tmp_path: Path, query: dict[str, str], says: str
    ) -> None:
        """Spec 4.6's refusals, each asserted by its sentence and not only by its code. Measured
        against this checkout: a substring long enough that a rewording fails here, which is what
        the rest of this branch's refusal tests do not do - every one of them checks a file name
        or a clause and would pass a sentence rewritten around it.

        Nothing is written either: a refusal that had already touched a file would be the one
        outcome none of these codes can describe."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        reply = get(api, "/api/section-plan", **query)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert says in reply.body["message"]
        assert contents(root) == before

    def test_removing_the_only_section_a_file_declares_leaves_it_declaring_nothing(
        self, tmp_path: Path
    ) -> None:
        """The constants case at the second vocabulary: refused while `sections` was
        `min_length=1`, applied now, and the file left behind loads."""
        api = opened(tmp_path, SOLE_SECTION_IN_A_FILE)
        preview = get(api, "/api/section-plan", action="remove", name=".sole").body
        assert applied(api, preview, ".sole removed").status == 200
        written = json.loads((tmp_path / "s.ddd.json").read_text(encoding="utf-8"))
        assert written == {"sections": []}
        state = get(api, "/api/state").body
        assert [(f["check"], f["severity"], f["pointer"]) for f in state["findings"]] == [
            ("empty-vocabulary", "info", "sections")
        ]
        assert get(api, "/api/section", name=".sole").status == 404

    def test_a_section_no_file_declares_cannot_be_changed(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section-plan", action="set", name=".nope", key="alignment", raw="8")
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert reply.body["message"] == (
            "no file of this project declares a section called '.nope'"
        )

    def test_an_add_while_the_sections_file_did_not_load_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, UNREADABLE_SECTIONS),
            "/api/section-plan",
            action="add",
            name=".new",
            access='"read-write"',
            alignment="4",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert (
            "s.ddd.json did not load, so what it declares is unknown and '.new' cannot be added "
            "to it" in reply.body["message"]
        )

    def test_an_add_while_a_file_nobody_could_read_is_included_creates_nothing(
        self, tmp_path: Path
    ) -> None:
        """What `places.ddd.json` holds is unknown, so whether this project already keeps its
        sections there is unknown too - and a second `sections.ddd.json` written beside the
        description could collide with a name in it the moment the first one parses again."""
        api = opened(tmp_path, HALF_WRITTEN_SECTIONS)
        before = contents(tmp_path)
        reply = get(
            api,
            "/api/section-plan",
            action="add",
            name=".nvm",
            access='"read-write"',
            alignment="4",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "places.ddd.json did not parse" in reply.body["message"]
        assert "keeps its sections there is unknown" in reply.body["message"]
        assert contents(tmp_path) == before

    def test_an_add_that_would_overwrite_a_stray_file_is_refused(self, tmp_path: Path) -> None:
        reply = get(
            opened(tmp_path, STRAY_SECTIONS_FILE),
            "/api/section-plan",
            action="add",
            name=".nvm",
            access='"read-write"',
            alignment="4",
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert (
            "declaring '.nvm' writes sections.ddd.json beside p.ddd.json, and a file of that name "
            "is there already" in reply.body["message"]
        )

    @pytest.mark.parametrize(
        ("query", "whose"),
        [
            ({"action": "set", "name": ".calib", "key": "alignment", "raw": "not json"}, "raw"),
            (
                {"action": "add", "name": ".nvm", "access": "read-write", "alignment": "4"},
                "access",
            ),
            (
                {"action": "add", "name": ".nvm", "access": '"read-write"', "alignment": "4 8"},
                "alignment",
            ),
        ],
    )
    def test_a_value_that_is_not_json_is_bad_before_any_refusal_about_the_project(
        self, tmp_path: Path, query: dict[str, str], whose: str
    ) -> None:
        """`?access=read-write` is the mistake this guard is really for. Left to the model, it
        would meet *"read-write is not an access a section may state ... : read-write or
        read-only"* - a sentence naming the value it refuses among the ones it allows, because
        what is wrong with it is the missing quotes and not the word."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert f"{query[whose]!r} is not one json value" in reply.body["message"]

    def test_two_values_that_are_not_json_are_refused_in_a_fixed_order(
        self, tmp_path: Path
    ) -> None:
        """One bad value has only one sentence to answer with; two have a choice, and the choice is
        the panel's field order. `_json_texts` walks `SECTIONS.keys` filtered to the required ones,
        and the caller stops at the first text that is not json - so the refusal is about `access`,
        the first field the form draws, and not about whichever key a container happened to yield
        first."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(
            api,
            "/api/section-plan",
            action="add",
            name=".nvm",
            access="read-write",
            alignment="4 8",
        )
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"].startswith("'read-write' is not one json value")

    def test_two_values_the_model_refuses_name_the_same_one_every_run(self, tmp_path: Path) -> None:
        """The same choice one layer down, and the one the written file cannot show: `_entry_text`
        composes the entry in `SECTIONS.keys` order, so the bytes an `add` writes do not depend on
        how `raws` was built - but `add_entry` and `_created` both judge `raws.items()` in insertion
        order and stop at the first key the model refuses. `_declared` builds it in the panel's
        order, so a request with a bad `access` and a bad `alignment` meets the access refusal."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(
            api,
            "/api/section-plan",
            action="add",
            name=".nvm",
            access='"read-sideways"',
            alignment="3",
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"].startswith(
            '"read-sideways" is not an access a section may state'
        )

    def test_the_json_texts_of_a_request_come_in_the_order_the_panel_draws_them(self) -> None:
        """The two tests above pin the sentence a reader meets; this pins *which table decides* it.

        Both are asked of `SECTIONS`, whose keys are drawn in alphabetical order by coincidence, so
        over it alone the panel's order and `sorted(SECTIONS.required)` are the same list and
        neither test above can tell them apart. `WIDE` draws `f, d, b, e, a, c`, where the two
        disagree on every position: this assertion holds only if the order is read off
        `Vocabulary.keys`, and fails against a sort.

        Reading it off `keys` is what makes the answer a claim rather than an accident. A sort is
        deterministic too, but it puts `access` before `alignment` because of the alphabet; the
        panel's order puts it first because that is the field the reader is looking at. The helpers
        take a `Vocabulary` precisely so this is askable without an endpoint."""
        given = {key: f'"{key}"' for key in WIDE_KEYS}
        assert _json_texts(WIDE, given, None) == [given[key] for key in WIDE_KEYS]

    def test_a_declared_entry_is_built_in_the_panels_own_order(self) -> None:
        """The other walk, pinned the same way, plus one promise of its own: `description` comes
        after the required keys and not among them. It is the key `add` supplies itself, so no
        refusal can be about it."""
        given = {key: f'"{key}"' for key in WIDE_KEYS}
        assert list(_declared(WIDE, given)) == [*WIDE_KEYS, "description"]

    def test_a_key_the_panel_draws_but_the_model_defaults_is_not_a_request_parameter(self) -> None:
        """The arm of `_required_keys`'s filter that skips a key: `description` is drawn by both
        real vocabularies and required by neither, so it is never asked of a request. Asserted
        because a comprehension filter registers no branch with coverage.py - the loop there is
        written as statements for that reason, and this is the test that would notice if the skip
        stopped happening."""
        given = {key: f'"{key}"' for key in (*WIDE_KEYS, "description")}
        assert "description" not in _json_texts(WIDE, given, None)
        assert _json_texts(SECTIONS, {"description": '"prose"'}, None) == []

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"action": "dance", "name": ".calib"},
            {"action": "set", "name": ".calib"},
            {"action": "set", "name": "", "key": "alignment", "raw": "4"},
            {"action": "rename", "name": ".calib"},
            {"action": "add", "name": ".nvm", "access": '"read-write"'},
            {"action": "add", "name": ".nvm", "alignment": "4"},
            {"action": "remove"},
        ],
    )
    def test_a_missing_or_unknown_parameter_is_a_bad_request(
        self, tmp_path: Path, query: dict[str, str]
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_the_actions_a_section_plan_offers_are_named_in_its_refusal(
        self, tmp_path: Path
    ) -> None:
        """The noun comes off the descriptor, so a route wired to the wrong vocabulary would say
        `constant-plan` here - which no status code would show."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/section-plan", action="dance")
        assert reply.body["message"] == (
            "section-plan takes ?action= one of set, rename, add, remove"
        )

    def test_an_add_names_a_parameter_for_each_key_the_section_model_requires(self) -> None:
        """The one thing neither the endpoint's tests nor the coverage gate can see going wrong:
        `SECTION_PLANS["add"]` and `SECTIONS.required` are two tables of the same fact, and
        `_declared` reads the request by the second. A key added to the model's required set
        without a parameter here would raise `KeyError` inside the route - a 500 where a reader
        should meet a form.

        Asserted against `_required_keys` rather than against `sorted(...)`, so the two statements
        are the relation and the literal rather than the relation twice: the parameters after
        `?name=` are the required keys in the order the panel draws them, which is also the order a
        refusal names them in."""
        assert SECTION_PLANS["add"] == ("name", *_required_keys(SECTIONS))
        assert SECTION_PLANS["add"] == ("name", "access", "alignment")

    def test_a_project_the_analysis_could_not_read_plans_no_section_change(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/section-plan", action="remove", name=".calib")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "p.ddd.json did not load, so no section of the project can be changed"
        )

    def test_a_section_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/section-plan", action="set", name=".calib", key="alignment", raw="8")
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_section_plan_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/section-plan", action="remove", name=".calib")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestRaster:
    """``GET /api/raster`` and ``GET /api/raster-plan``, over examples/vocabulary and the small
    trees it cannot supply.

    The third of the pair, request for request, which is the point: the same five verbs over a
    third :class:`~ddd.project_shared.Vocabulary`, so a case two of them answer and the third does
    not would be a case the descriptor failed to describe.

    The example is richer here than it is for a section: its ``100ms`` is named by nothing, so
    ``remove``'s happy path needs no tree of its own, and its ``10ms`` and ``1ms`` are named by a
    component's own default and by a definition respectively - the two kinds of use, one apiece.

    Every refusal below was rendered from the current source with a throwaway script and is
    asserted whole, with ``==``: a tail reworded in :data:`~ddd.project_shared.RASTERS` fails here
    rather than passing a substring check. Task 4's own fix round rewrote two of these tails, so a
    sentence copied out of the plan would have pinned wording that no longer exists.
    """

    def test_the_panel_names_its_entry_its_keys_and_the_component_measuring_in_it(
        self, tmp_path: Path
    ) -> None:
        """`event` arrives as the json text its file spells and `cycle` and `description` as the
        strings they hold, which is what `RASTERS.strings` decides: read the other way round,
        `cycle` would carry its quotes onto the panel and `event` would come back empty, the value
        at that key being no string.

        The use is the component's own, `Pump` naming `10ms` as the default for everything it
        produces - a use inside no definition at all, and the one `SectionUse.kind` could not
        describe."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/raster", name="10ms").body
        assert body["revision"] == 1
        assert body["name"] == "10ms"
        assert body["event"] == "1"
        assert body["cycle"] == "10ms"
        assert body["description"] == "control task"
        assert body["file"] == posix(root, "rasters.ddd.json")
        assert body["pointer"] == "rasters[1]"
        assert [(u["kind"], u["name"], u["component"], u["pointer"]) for u in body["uses"]] == [
            ("component", "Pump", "Pump", "component.raster")
        ]
        assert body["findings"] == []

    def test_a_definition_measured_in_a_raster_is_a_use_of_the_variable(
        self, tmp_path: Path
    ) -> None:
        """The other kind, and the one a section's panel also lists: `PumpSpeed` states `1ms`
        itself rather than taking its component's default, so the reader is shown which variable is
        sampled there and in which component."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/raster", name="1ms").body
        assert body["event"] == "0"
        assert [(u["kind"], u["name"], u["component"], u["pointer"]) for u in body["uses"]] == [
            ("variable", "PumpSpeed", "Pump", "component.interface[0].definition.raster")
        ]

    def test_a_raster_named_both_ways_lists_both_uses_in_the_index_s_own_order(
        self, tmp_path: Path
    ) -> None:
        """No raster of the example is named both ways, so the order the two kinds come in is
        askable only here: per component, its own default ahead of its own definitions', which is
        the order `ddd.lsp.navigation.index` records them in."""
        body = get(opened(tmp_path, MEASURED_TWICE), "/api/raster", name="10ms").body
        assert [(u["kind"], u["name"], u["pointer"]) for u in body["uses"]] == [
            ("component", "A", "component.raster"),
            ("variable", "X", "component.interface[0].definition.raster"),
        ]

    def test_a_raster_stating_no_cycle_answers_an_empty_one(self, tmp_path: Path) -> None:
        """`cycle` is `str | None` in the model and every shipped raster states one, so the empty
        answer needs a tree of its own. An event that is not cyclic is a real kind of raster rather
        than an omission, which is why the panel draws the field empty instead of the endpoint
        refusing to answer."""
        body = get(opened(tmp_path, NO_CYCLE), "/api/raster", name="20ms").body
        assert (body["event"], body["cycle"], body["description"]) == ("2", "", "")

    def test_a_duplicate_raster_finding_routes_back_to_the_raster(self, tmp_path: Path) -> None:
        """The fix that belongs beside the route: `FindingRoute.kind` had no `"raster"` member
        until this part, and `_finding` builds that model for every finding of every request - so
        this panel raised a `pydantic.ValidationError` before a test could reach the assertion,
        exactly as part 13's `constant` and part 14's `section` each nearly shipped. Every other
        test of this class asks about a raster carrying no raster-routed finding, which is why only
        this one catches it.

        The copy the panel lists is the one filed at the *first* entry - `duplicate-raster` is
        filed at the repeat and again at the entry it repeats - since the index registers the first
        and `located_on` asks about that one's pointer."""
        body = get(opened(tmp_path, DECLARED_TWICE), "/api/raster", name="10ms").body
        assert body["pointer"] == "rasters[0]"
        assert [(f["check"], f["route"]) for f in body["findings"]] == [
            ("duplicate-raster", {"kind": "raster", "name": "10ms"})
        ]

    def test_an_unknown_raster_leads_to_the_name_the_definition_names(self, tmp_path: Path) -> None:
        """The route the page turns into a pre-filled add form: the name is in no index, so the
        panel would answer 404 and the route carries it anyway."""
        state = get(opened(tmp_path, MEASURED_NOWHERE), "/api/state").body
        routes = {f["check"]: f["route"] for f in state["findings"]}
        assert routes["unknown-raster"] == {"kind": "raster", "name": "50ms"}

    def test_a_consumers_stray_raster_key_is_neither_counted_nor_listed_on_the_raster(
        self, tmp_path: Path
    ) -> None:
        """The raster's copy of the same rule end to end, and a defect measured on the revision
        before this one rather than a case inherited from the sections pair: `consumer-raster` is
        filed at `component.interface[i].definition.raster`, which is a shape naming the raster, so
        `10ms`'s row already read `findings: 1` for a finding whose route leaves the panel - and
        the panel this part adds would have listed it.

        The finding is not lost, only attributed: the project still reports it, at the declaration
        that states the key, where the fix is. The `uses` count stays at two - the consumer's key
        really does name the raster, which is exactly what `consumer-raster` complains about."""
        api = opened(tmp_path, CONSUMER_MEASURES)
        row = {e["name"]: e for e in get(api, "/api/shared").body["entries"]}["10ms"]
        assert (row["uses"], row["findings"]) == (2, 0)
        assert get(api, "/api/raster", name="10ms").body["findings"] == []
        assert {f["check"]: f["route"] for f in get(api, "/api/state").body["findings"]}[
            "consumer-raster"
        ] == {"kind": "variable", "name": "X"}

    def test_a_raster_on_a_calibration_object_is_not_counted_on_the_raster_either(
        self, tmp_path: Path
    ) -> None:
        """The second of the two checks at that pointer that are not the raster's. `raster-kind`
        says a calibration object states a raster and no daq list carries one: the entry is
        innocent, and both ways to settle it are edits to the declaration."""
        api = opened(tmp_path, CALIBRATION_MEASURED)
        row = {e["name"]: e for e in get(api, "/api/shared").body["entries"]}["10ms"]
        assert (row["uses"], row["findings"]) == (1, 0)
        assert get(api, "/api/raster", name="10ms").body["findings"] == []
        assert {f["check"]: f["route"] for f in get(api, "/api/state").body["findings"]}[
            "raster-kind"
        ] == {"kind": "variable", "name": "Gain"}

    @pytest.mark.parametrize("query", [{}, {"name": ""}])
    def test_a_raster_is_asked_for_by_name(self, tmp_path: Path, query: dict[str, str]) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "raster takes ?name="

    def test_a_raster_the_project_does_not_declare_is_not_found(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster", name="50ms")
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert reply.body["message"] == "'50ms' is not declared in the open project"

    def test_a_name_only_a_rasters_file_that_did_not_load_declares_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        reply = get(opened(tmp_path, UNREADABLE_RASTERS), "/api/raster", name="50ms")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "'50ms' is not declared in any file that loaded, and r.ddd.json did not load"
        )

    def test_a_project_the_analysis_could_not_read_cannot_answer_a_raster(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/raster", name="10ms")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_raster_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/raster", name="10ms")
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_setting_a_cycle_is_previewed_then_written(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        preview = get(
            api, "/api/raster-plan", action="set", name="10ms", key="cycle", raw='"20ms"'
        ).body
        assert contents(root) == before
        assert [Path(c["file"]).name for c in preview["changes"]] == ["rasters.ddd.json"]
        assert applied(api, preview, "the cycle of 10ms").status == 200
        assert '"cycle": "20ms"' in (root / "rasters.ddd.json").read_text(encoding="utf-8")
        assert get(api, "/api/raster", name="10ms").body["cycle"] == "20ms"

    def test_renaming_rewrites_the_entry_and_every_shape_naming_it(self, tmp_path: Path) -> None:
        """Both shapes in one rename, which is what `rename_sites` reaches for a raster: the
        entry's own name in the rasters file, and the pump's default in the component.

        Asserted key by key rather than by `'10ms' not in the file`, which is how the sections pair
        asserts its own rename and which cannot be asked here: a raster is the one vocabulary whose
        name and one of its values are spelled alike - `10ms` names the entry *and* states its
        cycle - so the entry that has been correctly renamed still holds the string. That the cycle
        is left alone is worth its own line: a rename reaching it would silently change how often
        the signal is sampled."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(api, "/api/raster-plan", action="rename", name="10ms", to="20ms").body
        assert [Path(c["file"]).name for c in preview["changes"]] == [
            "pump.ddd.json",
            "rasters.ddd.json",
        ]
        assert applied(api, preview, "the rename of '10ms' to '20ms'").status == 200
        declared = json.loads((root / "rasters.ddd.json").read_text(encoding="utf-8"))
        assert declared["rasters"][1] == {
            "raster": "20ms",
            "event": 1,
            "cycle": "10ms",
            "description": "control task",
        }
        pump = json.loads((root / "pump.ddd.json").read_text(encoding="utf-8"))
        assert pump["component"]["raster"] == "20ms"
        assert get(api, "/api/raster", name="20ms").status == 200
        assert get(api, "/api/raster", name="10ms").status == 404

    def test_declaring_one_takes_a_json_text_per_key_the_model_gives_no_default(
        self, tmp_path: Path
    ) -> None:
        """`event` alone, where a section's `add` takes two: a raster the file states no `event`
        for is one that does not load, and `cycle` - which a raster may honestly state none of -
        is not the request's to supply. The entry written states no `cycle` at all rather than an
        explicit `null`, which is `_entry_text` skipping a key `raws` leaves out."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(api, "/api/raster-plan", action="add", name="50ms", event="3").body
        assert [Path(c["file"]).name for c in preview["changes"]] == ["rasters.ddd.json"]
        assert applied(api, preview, "50ms declared").status == 200
        declared = json.loads((root / "rasters.ddd.json").read_text(encoding="utf-8"))
        assert declared["rasters"][-1] == {"raster": "50ms", "event": 3, "description": ""}
        assert get(api, "/api/raster", name="50ms").status == 200

    def test_adding_when_the_project_has_no_rasters_file_creates_one(
        self, api: Api, root: Path
    ) -> None:
        """`RASTERS.filename` and `RASTERS.containers[0]` both, in the bytes of a file nothing else
        in this suite ever sees written: the name beside the description and the key its one entry
        is wrapped in."""
        before = contents(root)
        preview = get(api, "/api/raster-plan", action="add", name="10ms", event="1").body
        assert contents(root) == before
        described, created = preview["changes"]
        assert (Path(described["file"]).name, Path(created["file"]).name) == (
            "p.ddd.json",
            "rasters.ddd.json",
        )
        assert (described["fingerprint"], created["fingerprint"]) == (
            fingerprint(before["p.ddd.json"]),
            None,
        )
        assert applied(api, preview, "10ms declared").status == 200
        assert created["hunks"] == [
            {
                "line": 1,
                "before": [],
                "after": [
                    "{",
                    '  "rasters": [',
                    '    { "raster": "10ms", "event": 1, "description": "" }',
                    "  ]",
                    "}",
                ],
            }
        ]
        assert '"rasters.ddd.json"' in (root / "p.ddd.json").read_text(encoding="utf-8")

    def test_removing_a_raster_nothing_names_takes_its_entry_out(self, tmp_path: Path) -> None:
        """`100ms` is the example's own unused entry, so this needs no tree of its own where the
        sections pair needed UNUSED_SECTION: both of that example's sections are placed in."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        preview = get(api, "/api/raster-plan", action="remove", name="100ms").body
        assert applied(api, preview, "100ms removed").status == 200
        assert get(api, "/api/raster", name="100ms").status == 404
        assert get(api, "/api/raster", name="10ms").status == 200

    @pytest.mark.parametrize(
        ("query", "says"),
        [
            (
                {"action": "rename", "name": "10ms", "to": "not a raster name!"},
                "'not a raster name!' is not a usable raster name",
            ),
            (
                {"action": "rename", "name": "10ms", "to": "100ms"},
                "'100ms' is already a raster this project declares",
            ),
            (
                {"action": "add", "name": "100ms", "event": "9"},
                "'100ms' is already a raster this project declares",
            ),
            (
                {"action": "set", "name": "10ms", "key": "event", "raw": "4.0"},
                "4.0 is not an event a raster may state, so '10ms' cannot take it in "
                "rasters.ddd.json: a channel number xcp addresses - 0 to 65535 - written "
                "without a decimal point",
            ),
            (
                {"action": "add", "name": "50ms", "event": "1e3"},
                "1e3 is not an event a raster may state, so '50ms' cannot take it in "
                "rasters.ddd.json: a channel number xcp addresses - 0 to 65535 - written "
                "without a decimal point",
            ),
            (
                {"action": "set", "name": "10ms", "key": "cycle", "raw": '"potato"'},
                "\"potato\" is not a cycle a raster may state, so '10ms' cannot take it in "
                "rasters.ddd.json: a count of 1 to 255 times a decade from 1ns to 1s, written "
                "as one string - '1500us', '10ms'. A raster that is not cyclic states no cycle "
                "at all: the key is left out of its entry, which no value set here can do",
            ),
            (
                {"action": "set", "name": "10ms", "key": "cycle", "raw": '""'},
                "\"\" is not a cycle a raster may state, so '10ms' cannot take it in "
                "rasters.ddd.json: a count of 1 to 255 times a decade from 1ns to 1s, written "
                "as one string - '1500us', '10ms'. A raster that is not cyclic states no cycle "
                "at all: the key is left out of its entry, which no value set here can do",
            ),
            (
                {"action": "set", "name": "10ms", "key": "event", "raw": "0"},
                "event 0 is already claimed by raster '1ms'",
            ),
            (
                {"action": "add", "name": "50ms", "event": "1"},
                "event 1 is already claimed by raster '10ms'",
            ),
            (
                {"action": "set", "name": "10ms", "key": "event"},
                "a raster states an event, so '10ms' cannot be left without one in "
                "rasters.ddd.json",
            ),
            (
                {"action": "set", "name": "10ms", "key": "unit", "raw": '"rpm"'},
                "a raster has no 'unit' to set in rasters.ddd.json: it states cycle, "
                "description and event",
            ),
            (
                {"action": "remove", "name": "10ms"},
                "'10ms' is named by 1 shape, the first in pump.ddd.json; nothing may name it "
                "before it goes",
            ),
        ],
    )
    def test_a_change_the_project_refuses_says_why_in_the_format_s_own_words(
        self, tmp_path: Path, query: dict[str, str], says: str
    ) -> None:
        """Every refusal a raster has, each asserted whole rather than by a substring: a tail
        reworded in `RASTERS.judge` or a clause dropped from `shared_plans` fails here.

        The two rows a substring would have let through are the interesting ones. `cycle`'s tail
        was `"a json string, or nothing"` in the plan this branch was written from, which is the
        annotation and not the rule - and `"potato"` *is* a json string, so the one sentence a
        reader with a mistyped period ever sees would have refuted itself. `event`'s named neither
        half of what its field refuses. Both were corrected after Task 4's review, and every
        sentence here was rendered from the current source rather than copied from the plan or
        from the sections pair beside it.

        The `cycle` pair is why there are two rows for one tail. That correction left the tail's
        own `or nothing` standing, and the field a reader clears sends `""` - so the sentence met
        on the likelier keystroke still ended by naming the state that had just been refused.
        `""` is what the panel sends for an emptied Cycle field (`rasterRaw`), and `"potato"` what
        it sends for a mistyped period; both are here because the defect was found at one of them
        and fixed only there. The key is taken out for a `raw` of `None` alone, which this field
        has no way to send - the open item the tail now points at instead of promising.

        The two `already claimed` rows are the raster's own refusal, which neither of the other
        vocabularies has: a value, not a name, that is the project's alone. Both verbs that write
        one are asked, since asking in only one would refuse a collision on edit and write it on
        create.

        Nothing is written either: a refusal that had already touched a file would be the one
        outcome none of these codes can describe."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        before = contents(root)
        reply = get(api, "/api/raster-plan", **query)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == says
        assert contents(root) == before

    def test_removing_the_only_raster_a_file_declares_leaves_it_declaring_nothing(
        self, tmp_path: Path
    ) -> None:
        """The constants case at the third vocabulary: refused while `rasters` was
        `min_length=1`, applied now, and the file left behind loads."""
        api = opened(tmp_path, SOLE_RASTER_IN_A_FILE)
        preview = get(api, "/api/raster-plan", action="remove", name="10ms").body
        assert applied(api, preview, "10ms removed").status == 200
        written = json.loads((tmp_path / "r.ddd.json").read_text(encoding="utf-8"))
        assert written == {"rasters": []}
        state = get(api, "/api/state").body
        assert [(f["check"], f["severity"], f["pointer"]) for f in state["findings"]] == [
            ("empty-vocabulary", "info", "rasters")
        ]
        assert get(api, "/api/raster", name="10ms").status == 404

    def test_a_raster_no_file_declares_cannot_be_changed(self, tmp_path: Path) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster-plan", action="set", name="50ms", key="cycle", raw='"50ms"')
        assert (reply.status, reply.body["error"]) == (404, "not-found")
        assert reply.body["message"] == ("no file of this project declares a raster called '50ms'")

    def test_an_add_while_the_rasters_file_did_not_load_is_unreadable(self, tmp_path: Path) -> None:
        reply = get(
            opened(tmp_path, UNREADABLE_RASTERS),
            "/api/raster-plan",
            action="add",
            name="60ms",
            event="4",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "r.ddd.json did not load, so what it declares is unknown and '60ms' cannot be "
            "added to it"
        )

    @pytest.mark.parametrize(
        ("query", "whose"),
        [
            ({"action": "set", "name": "10ms", "key": "cycle", "raw": "not json"}, "raw"),
            ({"action": "add", "name": "50ms", "event": "3 4"}, "event"),
        ],
    )
    def test_a_value_that_is_not_json_is_bad_before_any_refusal_about_the_project(
        self, tmp_path: Path, query: dict[str, str], whose: str
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        # `startswith` and not `in`, matching the section pair's own
        # `test_two_values_that_are_not_json_are_refused_in_a_fixed_order`: what follows the
        # clause is python's json decoder's own text (`: Expecting value: line 1 column 1`),
        # which this suite has no business pinning - but `in` would leave the prefix free too,
        # and the prefix is the sentence `parse_raw` writes.
        assert reply.body["message"].startswith(f"{query[whose]!r} is not one json value")

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"action": "dance", "name": "10ms"},
            {"action": "set", "name": "10ms"},
            {"action": "set", "name": "", "key": "cycle", "raw": '"20ms"'},
            {"action": "rename", "name": "10ms"},
            {"action": "add", "name": "50ms"},
            {"action": "remove"},
        ],
    )
    def test_a_missing_or_unknown_parameter_is_a_bad_request(
        self, tmp_path: Path, query: dict[str, str]
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_the_actions_a_raster_plan_offers_are_named_in_its_refusal(
        self, tmp_path: Path
    ) -> None:
        """The noun comes off the descriptor, so a route wired to the wrong vocabulary would say
        `section-plan` here - which no status code would show."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        reply = get(api, "/api/raster-plan", action="dance")
        assert reply.body["message"] == "raster-plan takes ?action= one of set, rename, add, remove"

    def test_an_add_names_a_parameter_for_each_key_the_raster_model_requires(self) -> None:
        """The same relation `SECTION_PLANS` is asserted by, at the vocabulary whose required set
        has one member rather than two: a key added to the model's required set without a
        parameter here would raise `KeyError` inside the route - a 500 where a reader should meet
        a form."""
        assert RASTER_PLANS["add"] == ("name", *_required_keys(RASTERS))
        assert RASTER_PLANS["add"] == ("name", "event")

    def test_a_project_the_analysis_could_not_read_plans_no_raster_change(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/raster-plan", action="remove", name="10ms")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"] == (
            "p.ddd.json did not load, so no raster of the project can be changed"
        )

    def test_a_raster_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/raster-plan", action="set", name="10ms", key="cycle", raw='"20ms"')
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_raster_plan_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/raster-plan", action="remove", name="10ms")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


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

    def test_a_shape_of_more_than_two_dimensions_is_refused_rather_than_drawn(
        self, tmp_path: Path
    ) -> None:
        # The other status this endpoint answers, and the reason it weighs the code at all:
        # `dimensions: [2, 3, 4]` used to reach `ValuesReply` as a three level nest and come
        # back 500 out of the server's blanket handler. A refusal, with the sentence the page
        # renders, and 409 rather than 404 - the project does declare this object.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output", "Cube", kind="value_block", datatype="uint8", dimensions=[2, 3, 4]
                    ),
                ),
            },
        )
        reply = get(api, "/api/values", name="Cube")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'Cube' has 3 dimensions, and a grid draws at most two"
        plan = get(api, "/api/value-plan", name="Cube", at="[1][2][3]", raw="7")
        assert (plan.status, plan.body["error"]) == (409, "invalid")
        plans = get(api, "/api/values-plan", name="Cube", raw="7")
        assert (plans.status, plans.body["error"]) == (409, "invalid")

    def test_a_name_two_declarations_produce_is_read_only(self, tmp_path: Path) -> None:
        # The values come from the analysis's own producer and the file used to come from
        # `Index.producers[0]`, which is a different choice: with the project listing b first,
        # the reply showed A's numbers over b's file and an edit would have replaced a value
        # that was never on screen. No one file to write into, so the grid opens read-only -
        # the numbers and the owner still shown, since they are how the reader finds the
        # second producer.
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "b.ddd.json", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Twin",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[3],
                        init=[1, 2, 3],
                    ),
                ),
                "b.ddd.json": component(
                    "B",
                    declare(
                        "output",
                        "Twin",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[3],
                        init=[7, 8, 9],
                    ),
                ),
            },
        )
        body = get(api, "/api/values", name="Twin").body
        assert (body["rows"], body["owner"], body["file"]) == ([[1, 2, 3]], "A", None)
        before = contents(tmp_path)
        plan = get(api, "/api/value-plan", name="Twin", at="[0]", raw="5")
        assert (plan.status, plan.body["error"]) == (409, "invalid")
        assert plan.body["message"] == (
            "'Twin' is produced in more than one place, so there is no one file to set it in"
        )
        plans = get(api, "/api/values-plan", name="Twin", raw="1,2,3")
        assert (plans.status, plans.body["error"]) == (409, "invalid")
        # The same sentence as the cell's above, not a second spelling of the same condition:
        # a reader who pastes and a reader who types are told the one thing that is true.
        assert plans.body["message"] == plan.body["message"]
        assert contents(tmp_path) == before

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

    def test_a_pasted_curve_is_previewed_then_written(self, demo) -> None:
        api, root = demo
        before = contents(root)
        preview = get(api, "/api/values-plan", name="CurveA", raw="1300,950,850,800,750,700").body
        assert contents(root) == before
        assert [Path(c["file"]).name for c in preview["changes"]] == ["controller.ddd.json"]
        assert applied(api, preview, "the values of CurveA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"init": [1300, 950, 850, 800, 750, 700]' in written

    def test_a_pasted_map_is_folded_by_the_shape_the_server_knows(self, demo) -> None:
        # Every row, not the first and the last alone: a fold that got those two right and
        # scrambled the two between them would have passed, which is the one thing this test -
        # the only one whose subject is `_folded` itself - is here to catch.
        api, root = demo
        counts = ",".join(str(n) for n in range(1, 25))
        preview = get(api, "/api/values-plan", name="MapA", raw=counts).body
        assert applied(api, preview, "the values of MapA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        # Read back as one value rather than as four substrings: `in` says a row is somewhere in
        # the file and nothing about where, so four of them pass just as happily on a fold that
        # swapped the middle two - which is exactly what this test says it is here to catch.
        interface = json.loads(written)["component"]["interface"]
        init = next(e["definition"]["init"] for e in interface if e["definition"]["name"] == "MapA")
        assert init == [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
        ]

    def test_a_list_of_the_wrong_length_says_what_it_wanted(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/values-plan", name="CurveA", raw="1,2,3")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == ("'CurveA' takes 1 row of 6 values, and this is 1 row of 3")

    def test_a_two_dimensional_name_given_the_wrong_count_is_laid_out_as_one_row(
        self, demo
    ) -> None:
        # `_folded`'s wrong-length arm for a two-dimensional name: every other wrong-count test
        # here names a one- or three-dimensional object, which takes the `len(shape) != 2` half
        # of the same `or` and leaves the length half unexercised for a shape that has one.
        # One row of 23 is what the reader is told they pasted, which is what they did.
        api, _ = demo
        counts = ",".join(str(n) for n in range(1, 24))
        reply = get(api, "/api/values-plan", name="MapA", raw=counts)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'MapA' takes 4 rows of 6 values, and this is 1 row of 23"

    def test_a_name_the_project_has_not_is_not_found_for_a_values_plan(self, demo) -> None:
        # Named distinctly from TestTheValuesGrid's own /api/values test above (and
        # /api/value-plan's own "_for_a_plan" test below): two methods of the same name in one
        # class would shadow one another, silently dropping the first from the suite.
        api, _ = demo
        reply = get(api, "/api/values-plan", name="Nope", raw="1")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_without_its_parameters_it_says_which_it_takes(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/values-plan", name="CurveA")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "values-plan takes ?name= and ?raw="

    def test_a_count_that_is_not_a_number_is_refused(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/values-plan", name="CurveA", raw="1200,900,lots,750,700,650")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'lots' is not a number"

    def test_a_project_that_did_not_load_has_nothing_to_plan_values_of(self, tmp_path) -> None:
        # Named distinctly from TestTheValuesGrid's own /api/values test above, for the same
        # reason as the "not-found" rename just above it.
        reply = get(unloaded(tmp_path), "/api/values-plan", name="Anything", raw="1")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_values_plan_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, demo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The same pattern as test_a_plan_the_engine_refuses_is_a_refusal_the_page_can_act_on
        # above, over /api/values-plan's own call to `previewed` - its own line in this
        # handler, and the coverage gate cannot tell it was exercised by the other endpoint's
        # test alone.
        api, _ = demo

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/values-plan", name="CurveA", raw="1300,950,850,800,750,700")
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_a_text_init_cannot_be_pasted_into_at_the_endpoint(self, demo) -> None:
        # set_values's own text refusal, plumbed through: neither /api/values nor
        # /api/value-plan has a test of this at the http layer either, so this is new ground
        # rather than a sibling to extend.
        api, _ = demo
        reply = get(api, "/api/values-plan", name="SoftwareLabel", raw="1")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'SoftwareLabel' is initialised with text, not with a grid"

    def test_a_shapeless_object_cannot_be_pasted_into_at_the_endpoint(self, demo) -> None:
        # set_values's own shapeless refusal, plumbed through - the other refusal kind with no
        # existing http-layer test to extend.
        api, _ = demo
        reply = get(api, "/api/values-plan", name="ValueA", raw="1")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "'ValueA' has no cell for a value to sit in"


# The four shapes an entry of the root's includes takes, in one list: a literal naming a file, a
# pattern matching two, a plain path naming no file and a pattern matching none. The last two carry
# the findings filed at the entry itself - `file-not-found` and `include-empty` - and the first
# names a file with a finding of its own, `empty-vocabulary`, which is the file's and not its row's.
ENTRIES_OF_EVERY_SHAPE = {
    "p.ddd.json": project(
        "P", "units.ddd.json", "sensors/*.ddd.json", "missing.ddd.json", "nothing/*.ddd.json"
    ),
    "units.ddd.json": {"units": []},
    "sensors/b.ddd.json": component("B"),
    "sensors/a.ddd.json": component("A"),
}

# A root that loads, its first entry an empty vocabulary and its second a pattern matching no file:
# both findings the Files tab gives a row to, on files the analysis loaded, so both have a route.
FINDINGS_ABOUT_FILES = {
    "p.ddd.json": project("P", "units.ddd.json", "nothing/*.ddd.json"),
    "units.ddd.json": {"units": []},
}


class TestTheFilesTab:
    """``GET /api/files``: the root's includes, one row per entry, as the loader reads them."""

    def test_each_entry_is_listed_in_order_with_what_it_brings(self, tmp_path: Path) -> None:
        api = opened(tmp_path, ENTRIES_OF_EVERY_SHAPE)
        reply = get(api, "/api/files")
        assert reply == Reply(
            200,
            {
                "revision": 1,
                "project": posix(tmp_path, "p.ddd.json"),
                "entries": [
                    {
                        "index": 0,
                        "entry": "units.ddd.json",
                        "names": True,
                        "key": posix(tmp_path, "units.ddd.json"),
                        "files": [posix(tmp_path, "units.ddd.json")],
                        "findings": 0,
                    },
                    {
                        "index": 1,
                        "entry": "sensors/*.ddd.json",
                        "names": False,
                        "key": posix(tmp_path, "sensors/*.ddd.json"),
                        "files": [
                            posix(tmp_path, "sensors/a.ddd.json"),
                            posix(tmp_path, "sensors/b.ddd.json"),
                        ],
                        "findings": 0,
                    },
                    {
                        "index": 2,
                        "entry": "missing.ddd.json",
                        "names": False,
                        "key": posix(tmp_path, "missing.ddd.json"),
                        "files": [],
                        "findings": 1,
                    },
                    {
                        "index": 3,
                        "entry": "nothing/*.ddd.json",
                        "names": False,
                        "key": posix(tmp_path, "nothing/*.ddd.json"),
                        "files": [],
                        "findings": 1,
                    },
                ],
                "creatable": ["component", "types", "units", "constants", "sections", "rasters"],
            },
        )

    def test_a_row_counts_the_findings_at_its_entry_and_its_file_keeps_its_own(
        self, tmp_path: Path
    ) -> None:
        """Which finding each count is: the two rows naming nothing carry the two findings filed
        at their own entries, and the vocabulary's `empty-vocabulary` is counted on its file in
        `State.files`, never again on the row naming it."""
        api = opened(tmp_path, ENTRIES_OF_EVERY_SHAPE)
        at_entries = {
            (finding["check"], finding["pointer"])
            for finding in get(api, "/api/state").body["findings"]
            if finding["file"] == posix(tmp_path, "p.ddd.json")
        }
        assert at_entries == {
            ("file-not-found", "project.includes[2]"),
            ("include-empty", "project.includes[3]"),
        }
        files = {file["path"]: file for file in get(api, "/api/state").body["files"]}
        assert files[posix(tmp_path, "units.ddd.json")]["findings"] == {
            "error": 0,
            "warning": 0,
            "info": 1,
        }
        counts = [entry["findings"] for entry in get(api, "/api/files").body["entries"]]
        assert counts == [0, 0, 1, 1]

    def test_a_finding_at_an_entry_of_a_sub_project_is_not_the_root_s(self, tmp_path: Path) -> None:
        """The sub-project's own first entry matches nothing, and the finding sits at its
        `project.includes[0]` - the same pointer as the root's first entry, on another file."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/project.ddd.json", "a.ddd.json"),
                "sub/project.ddd.json": project("Sub", "nothing/*.ddd.json"),
                "a.ddd.json": component("A"),
            },
        )
        filed = [
            (finding["file"], finding["check"], finding["pointer"])
            for finding in get(api, "/api/state").body["findings"]
        ]
        assert filed == [
            (posix(tmp_path, "sub/project.ddd.json"), "include-empty", "project.includes[0]")
        ]
        counts = [entry["findings"] for entry in get(api, "/api/files").body["entries"]]
        assert counts == [0, 0]

    def test_a_finding_at_an_entry_is_counted_whatever_its_severity(self, tmp_path: Path) -> None:
        """A build may lower `include-empty` to a warning; the row carries it all the same, as a
        file's three counts together carry every finding filed on it."""
        from conftest import build_record

        write_tree(tmp_path, FINDINGS_ABOUT_FILES)
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["include-empty=warning"])
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        api = Api(session, tmp_path / "p.ddd.json", wait_seconds=0.05)
        at_entries = [
            (finding["check"], finding["severity"], finding["pointer"])
            for finding in get(api, "/api/state").body["findings"]
            if finding["file"] == posix(tmp_path, "p.ddd.json")
        ]
        assert at_entries == [("include-empty", "warning", "project.includes[1]")]
        counts = [entry["findings"] for entry in get(api, "/api/files").body["entries"]]
        assert counts == [0, 1]

    def test_a_root_failing_its_schema_lists_files_the_analysis_never_read(
        self, tmp_path: Path
    ) -> None:
        """A schema error in the root stops its read before its includes, so no file they bring
        is among `State.files`, while the entries, read off the description, still name them."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "lib/*.ddd.json", colour="red"),
                "a.ddd.json": component("A"),
                "lib/l.ddd.json": component("L"),
            },
        )
        read = {file["path"] for file in get(api, "/api/state").body["files"]}
        assert read == {posix(tmp_path, "p.ddd.json")}
        listed = [
            file for entry in get(api, "/api/files").body["entries"] for file in entry["files"]
        ]
        assert listed == [posix(tmp_path, "a.ddd.json"), posix(tmp_path, "lib/l.ddd.json")]

    def test_what_can_be_created_is_the_plans_own_list(self, tmp_path: Path) -> None:
        """Sent rather than restated on the page, where a second copy could drift from the server's
        with nothing to catch it."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        body = get(api, "/api/files").body
        assert body["creatable"] == list(CREATABLE)
        assert [
            (entry["entry"], entry["names"], entry["findings"]) for entry in body["entries"]
        ] == [
            ("units.ddd.json", True, 0),
            ("sections.ddd.json", True, 0),
            ("constants.ddd.json", True, 0),
            ("rasters.ddd.json", True, 0),
            ("pump.ddd.json", True, 0),
        ]

    def test_a_finding_about_an_entry_or_a_file_leads_to_its_row(self, tmp_path: Path) -> None:
        """What `route_of` names is what a row is keyed by, read through both endpoints the page
        joins: the pattern's `include-empty` to the pattern's row, the vocabulary's
        `empty-vocabulary` to its own."""
        api = opened(tmp_path, FINDINGS_ABOUT_FILES)
        routes = {
            finding["check"]: finding["route"]
            for finding in get(api, "/api/state").body["findings"]
        }
        keys = [entry["key"] for entry in get(api, "/api/files").body["entries"]]
        assert routes == {
            "include-empty": {"kind": "file", "name": keys[1]},
            "empty-vocabulary": {"kind": "file", "name": keys[0]},
        }

    def test_a_missing_file_s_finding_leads_nowhere(self, tmp_path: Path) -> None:
        """`file-not-found` is a load check, so the description carrying it did not load and its
        findings lead nowhere - the `include-empty` beside it among them. Its row is reached by
        the tab, not by a link."""
        api = opened(tmp_path, ENTRIES_OF_EVERY_SHAPE)
        routes = {
            finding["check"]: finding["route"]
            for finding in get(api, "/api/state").body["findings"]
            if finding["file"] == posix(tmp_path, "p.ddd.json")
        }
        assert routes == {"file-not-found": None, "include-empty": None}

    def test_the_files_need_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/files")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


def files_plan(api: Api, action: str, **query: str) -> Reply:
    """``GET /api/files-plan`` as the page asks it."""
    return get(api, "/api/files-plan", action=action, **query)


def refused(reply: Reply) -> tuple[int, str, str]:
    """A refusal as the page receives it: its status, its code and its whole sentence."""
    return reply.status, reply.body["error"], reply.body["message"]


def written(preview: dict[str, Any], file: Path) -> str:
    """What a preview's change of ``file`` writes: the text of the one ``set`` creating it."""
    change = next(change for change in preview["changes"] if change["file"] == file.as_posix())
    [operation] = change["operations"]
    return operation["raw"]


def errors_in(api: Api) -> list[tuple[str, str, str]]:
    """Every error the open project reports now, by file name, check and message."""
    return [
        (Path(finding["file"]).name, finding["check"], finding["message"])
        for finding in get(api, "/api/state").body["findings"]
        if finding["severity"] == "error"
    ]


def vocabulary_below(tmp_path: Path) -> Api:
    """``examples/vocabulary`` included as a sub-project by a root with no units file of its own,
    ``Device``: its only units file, and its only component, ``Pump``, are the sub-project's."""
    shutil.copytree(EXAMPLES / "vocabulary", tmp_path / "vocabulary")
    return opened(tmp_path, {"p.ddd.json": project("Device", "vocabulary/project.ddd.json")})


# A root with a literal entry and a pattern, and beside them files a reader might add: one bringing
# an error - it reads what nothing writes - one bringing none, and three the loader recognises no
# kind in: json that is no description, a half-saved file, and a plugin's python.
ADDABLE = {
    "p.ddd.json": project("P", "a.ddd.json", "lib/*.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "lib/l.ddd.json": component("L", declare("input", "Speed", unit="rpm")),
    "b.ddd.json": component("B", declare("input", "Torque", unit="Nm")),
    "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
    "notes.json": {"title": "not a description"},
    "half.ddd.json": '{"component": {"name": "H',
    "tool.py": "print('a plugin')\n",
}

# A component reading what the one file writing it would write, that file - in a directory of
# its own - saved half-edited: the project is not analysed, and removing the broken file would
# leave `missing-producer` if judged.
READER_OF_A_BROKEN_WRITER = {
    "p.ddd.json": project("P", "a.ddd.json", "lib/b.ddd.json"),
    "a.ddd.json": component("A", declare("input", "Speed", unit="rpm")),
    "lib/b.ddd.json": json.dumps(component("B", declare("output", "Speed")), indent=2)[:60],
}

# A reader of three variables, each written by a component that a pattern in a directory of its
# own brings in: one in `lib`, two in `sensors`.
WRITERS_IN_DIRECTORIES = {
    "p.ddd.json": project("P", "a.ddd.json", "lib/*.ddd.json", "sensors/*.ddd.json"),
    "a.ddd.json": component(
        "A",
        declare("input", "Speed", unit="rpm"),
        declare("input", "Torque", unit="Nm"),
        declare("input", "Flow", unit="l/min"),
    ),
    "lib/speed.ddd.json": component("S", declare("output", "Speed", unit="rpm")),
    "sensors/torque.ddd.json": component("T", declare("output", "Torque", unit="Nm")),
    "sensors/flow.ddd.json": component("F", declare("output", "Flow", unit="l/min")),
}

# A root whose pattern will match a file created once the revision is analysed, beside a file
# nothing uses and one it could add.
PATTERN_OVER_A_DIRECTORY = {
    "p.ddd.json": project("P", "a.ddd.json", "lib/*.ddd.json", "spare.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "lib/l.ddd.json": component("L", declare("input", "Speed", unit="rpm")),
    "spare.ddd.json": component("Spare"),
    "c.ddd.json": component("C"),
}

NEW_READER = component("N", declare("input", "Torque", unit="Nm"))
"""A component saved into a matched directory after the analysis, reading what nothing writes:
judged against a revision that never read it, its error read as the change's."""

APPEARED = (
    "new.ddd.json appeared since the project was analysed, so the change cannot be judged until "
    "the project is analysed again"
)

NO_KIND = (
    "is no kind of file a project includes: it cannot be read as json, or its top level holds "
    "none of project, component, types, units, sections, constants and rasters"
)

UNJUDGED_ADDING = (
    "not every analysis of this project ran to its end, so what adding c.ddd.json brings cannot "
    "be judged"
)
"""What an add to READER_OF_A_BROKEN_WRITER is answered with: nothing brought, and why."""

UNJUDGED_REMOVING = (
    "not every analysis of this project ran to its end, so what removing lib/b.ddd.json leaves "
    "cannot be judged"
)
"""What removing READER_OF_A_BROKEN_WRITER's broken writer is answered with: allowed, and why
unjudged - the file named as the includes spell it, from the description's directory."""


class TestAFilesPlanRequest:
    """What ``GET /api/files-plan`` takes, before any plan is asked for."""

    @pytest.mark.parametrize("action", ["", "rename"])
    def test_an_action_it_does_not_take_is_a_bad_request(self, api: Api, action: str) -> None:
        assert refused(files_plan(api, action)) == (
            400,
            "bad-request",
            "files-plan takes ?action= one of create, add, remove",
        )

    @pytest.mark.parametrize(
        ("action", "query", "says"),
        [
            pytest.param(
                "create", {"name": "sizes"}, "create takes ?kind= and ?name=", id="no kind"
            ),
            pytest.param(
                "create",
                {"kind": "types", "name": ""},
                "create takes ?kind= and ?name=",
                id="no name",
            ),
            pytest.param("add", {}, "add takes ?path=", id="add, no path"),
            pytest.param("add", {"path": ""}, "add takes ?path=", id="add, an empty path"),
            pytest.param("remove", {}, "remove takes ?path=", id="remove, no path"),
        ],
    )
    def test_a_parameter_missing_or_empty_is_a_bad_request(
        self, api: Api, action: str, query: dict[str, str], says: str
    ) -> None:
        assert refused(files_plan(api, action, **query)) == (400, "bad-request", says)

    @pytest.mark.parametrize("path", ["a.ddd.json", "../p/a.ddd.json"])
    def test_a_key_to_remove_that_is_not_absolute_is_a_bad_request(
        self, api: Api, path: str
    ) -> None:
        """A row's key is absolute. Read against the server's own working directory, a relative
        one named another file, and the refusal said no entry names a file one names."""
        assert refused(files_plan(api, "remove", path=path)) == (
            400,
            "bad-request",
            f"remove takes ?path= as a row's key, which is absolute, and '{path}' is not",
        )

    def test_a_plan_needs_an_open_project(self, root: Path) -> None:
        reply = files_plan(Api(Session(root)), "remove", path=posix(root, "a.ddd.json"))
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    def test_a_files_plan_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same pattern as every other plan endpoint's, over this handler's own call to
        `previewed`."""
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")

        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = files_plan(api, "create", kind="types", name="more")
        assert (reply.status, reply.body["error"]) == (409, "unverified")


class TestCreatingAFile:
    """``create``: a new file beside the description, appended to its includes in one edit."""

    def test_a_vocabulary_file_is_previewed_declaring_nothing(self, tmp_path: Path) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        described = root / "project.ddd.json"
        reply = files_plan(api, "create", kind="constants", name="limits")
        assert reply == Reply(
            200,
            {
                "revision": 1,
                "changes": [
                    {
                        "file": posix(root, "limits.ddd.json"),
                        "fingerprint": None,
                        "operations": [
                            {"op": "set", "pointer": "", "raw": '{\n  "constants": []\n}\n'}
                        ],
                        "hunks": [
                            {
                                "line": 1,
                                "before": [],
                                "after": ["{", '  "constants": []', "}"],
                            }
                        ],
                    },
                    {
                        "file": posix(root, "project.ddd.json"),
                        "fingerprint": fingerprint(described.read_bytes()),
                        "operations": [
                            {
                                "op": "insert",
                                "pointer": "project.includes[5]",
                                "raw": '"limits.ddd.json"',
                            }
                        ],
                        "hunks": [
                            {
                                "line": 11,
                                "before": ['      "pump.ddd.json"'],
                                "after": ['      "pump.ddd.json",', '      "limits.ddd.json"'],
                            }
                        ],
                    },
                ],
                "unjudged": None,
                "brings": [],
                "kept_by": None,
            },
        )

    def test_a_first_units_file_lists_every_unit_the_project_states(self, tmp_path: Path) -> None:
        """No units file anywhere in the tree: the file created opts the project in, so it lists
        what the project states rather than making each of them `unknown-unit`."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm"), declare("local", "Load", unit="%")
                ),
            },
        )
        preview = files_plan(api, "create", kind="units", name="units").body
        assert written(preview, (tmp_path / "units.ddd.json").resolve()) == (
            '{\n  "units": [\n    { "unit": "%", "description": "" },\n'
            '    { "unit": "rpm", "description": "" }\n  ]\n}\n'
        )

    def test_a_units_file_of_a_project_a_sub_project_opted_in_is_created_empty(
        self, tmp_path: Path
    ) -> None:
        """Whether a units file is the first is asked of every file of the tree, not of the
        root's own includes: listing the sub-project's four units again in a root file would fail
        the project with a `duplicate-unit` for each. Applied, and the project read again."""
        api = vocabulary_below(tmp_path)
        before = errors_in(api)
        preview = files_plan(api, "create", kind="units", name="units").body
        assert written(preview, (tmp_path / "units.ddd.json").resolve()) == '{\n  "units": []\n}\n'
        assert applied(api, preview).status == 200
        assert (tmp_path / "units.ddd.json").read_text(encoding="utf-8") == (
            '{\n  "units": []\n}\n'
        )
        assert errors_in(api) == before == []

    def test_a_component_is_refused_the_name_of_a_sub_project_s_but_for_its_case(
        self, tmp_path: Path
    ) -> None:
        """Every component of the tree takes its name, a sub-project's among them."""
        api = vocabulary_below(tmp_path)
        assert refused(
            files_plan(api, "create", kind="component", name="pump", component="pump")
        ) == (
            409,
            "invalid",
            "this project has a component called 'Pump' already, and 'pump' differs from it only "
            "in upper and lower case, so the two would ask for the same generated header",
        )

    def test_a_component_that_did_not_load_still_takes_its_name(self, tmp_path: Path) -> None:
        """Its name read off the file, since it clashes the moment the file is fixed; and a
        component naming itself nothing takes no name at all, so that a name no component has is
        compared, case folded, with the names there are and nothing else."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "broken.ddd.json", "nameless.ddd.json"),
                "broken.ddd.json": {"component": {"name": "Broken", "interface": 3}},
                "nameless.ddd.json": {"component": {"interface": []}},
            },
        )
        assert refused(
            files_plan(api, "create", kind="component", name="other", component="Broken")
        ) == (409, "invalid", "this project has a component called 'Broken' already")
        reply = files_plan(api, "create", kind="component", name="fresh", component="Fresh")
        assert reply.status == 200

    def test_the_project_s_own_name_is_no_component_s(self, tmp_path: Path) -> None:
        """A description's name is no component's: only a component takes one from a new
        component. Measured, a component named as its project passes `ddd check`."""
        api = vocabulary_below(tmp_path)
        reply = files_plan(api, "create", kind="component", name="device", component="Device")
        assert reply.status == 200

    @pytest.mark.parametrize(
        ("query", "says"),
        [
            pytest.param(
                {"kind": "project", "name": "sub"},
                "no file of kind 'project' can be created here; the kinds that can are component, "
                "types, units, constants, sections and rasters",
                id="a kind",
            ),
            pytest.param(
                {"kind": "types", "name": "a.b"},
                "'a.b' cannot name a new file: a name is one or more of the letters a to z and A "
                "to Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it",
                id="a name",
            ),
            pytest.param(
                {"kind": "types", "name": "units"},
                "units.ddd.json is there already, beside project.ddd.json",
                id="a file there already",
            ),
            pytest.param(
                {"kind": "component", "name": "motor"},
                "a new component needs a name, besides its file's",
                id="no component's name",
            ),
            pytest.param(
                {"kind": "component", "name": "motor", "component": ""},
                "a new component needs a name, besides its file's",
                id="an empty component's name",
            ),
            pytest.param(
                {"kind": "component", "name": "motor", "component": "2Motor"},
                "'2Motor' cannot name a component, not being a usable c identifier",
                id="no c identifier",
            ),
            pytest.param(
                {"kind": "component", "name": "motor", "component": "int"},
                "'int' cannot name a component, being reserved by c or by a header DDD generates",
                id="a reserved name",
            ),
            pytest.param(
                {"kind": "component", "name": "motor", "component": "Pump"},
                "this project has a component called 'Pump' already",
                id="a component's name taken",
            ),
        ],
    )
    def test_a_refused_creation_says_why(
        self, tmp_path: Path, query: dict[str, str], says: str
    ) -> None:
        api, _ = copied(tmp_path, "vocabulary", "project.ddd.json")
        assert refused(files_plan(api, "create", **query)) == (409, "invalid", says)

    def test_a_first_units_file_is_refused_while_a_file_did_not_load(self, tmp_path: Path) -> None:
        api = opened(tmp_path, HALF_SAVED)
        assert refused(files_plan(api, "create", kind="units", name="units")) == (
            409,
            "unreadable",
            "b.ddd.json did not load, so a first units file could not list every unit in use",
        )

    def test_a_file_created_where_a_pattern_matches_its_name_is_applied_and_read(
        self, tmp_path: Path
    ) -> None:
        """The new file is appended by its own name although the pattern reaches it: an edit may
        create a file only where an entry names it. Applied through the edit a page posts, and
        the project read again: listed twice, read once, and passing."""
        api = opened(
            tmp_path,
            {"p.ddd.json": project("P", "*.ddd.json"), "a.ddd.json": component("A")},
        )
        preview = files_plan(api, "create", kind="component", name="extra", component="Extra")
        assert preview.status == 200
        assert applied(api, preview.body).status == 200
        described = json.loads((tmp_path / "p.ddd.json").read_text(encoding="utf-8"))
        assert described["project"]["includes"] == ["*.ddd.json", "extra.ddd.json"]
        assert json.loads((tmp_path / "extra.ddd.json").read_text(encoding="utf-8")) == {
            "component": {"name": "Extra", "interface": []}
        }
        assert errors_in(api) == []
        assert posix(tmp_path, "extra.ddd.json") in {
            file["path"] for file in get(api, "/api/state").body["files"]
        }


class TestAddingAFile:
    """``add``: an existing file appended to the includes as written, and the errors it is
    counted to bring - previewed, never refused by the analysis."""

    def test_an_added_owner_turning_a_readers_disagreement_leaves_it_unlisted(
        self, tmp_path: Path
    ) -> None:
        """The cost of counting per place, an add's as a removal's: `W2` writes `X` as `uint32`
        in `Nm` and `R` reads it as `uint32` in `rpm`, a `definition-mismatch` with `W2` over its
        unit, on `R`. Added, `W1` writes it as `uint16` in `rpm` and owns it, its name sorting
        first, and `R`'s disagreement becomes one with `W1` over its datatype at the same place:
        counted as the one `R` has, it is not listed, while the writers' conflict and `W2`'s
        disagreement with `W1` are. Applied, the project reports it. The answer asserted is the
        one given."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "w2.ddd.json", "r.ddd.json"),
                "w1.ddd.json": component("W1", declare("output", "X", "uint16", unit="rpm")),
                "w2.ddd.json": component("W2", declare("output", "X", "uint32", unit="Nm")),
                "r.ddd.json": component("R", declare("input", "X", "uint32", unit="rpm")),
            },
        )
        reply = files_plan(api, "add", path="w1.ddd.json")
        assert reply.body["unjudged"] is None
        assert [
            (Path(brought["file"]).name, brought["check"], brought["message"])
            for brought in reply.body["brings"]
        ] == [
            (
                "w1.ddd.json",
                "multiple-producers",
                "'X' is written by component 'W1' and by component 'W2'; exactly one writer is "
                "allowed",
            ),
            (
                "w2.ddd.json",
                "definition-mismatch",
                "'X' is declared differently by component 'W2' than by 'W1' (datatype: uint32 != "
                "uint16, unit: 'Nm' != 'rpm')",
            ),
        ]
        assert applied(api, reply.body).status == 200
        assert (
            "r.ddd.json",
            "definition-mismatch",
            "'X' is declared differently by component 'R' than by 'W1' (datatype: uint32 != "
            "uint16)",
        ) in errors_in(api)

    def test_an_absolute_path_is_appended_as_typed(self, tmp_path: Path) -> None:
        """A path need not be written from the description's directory: one inside what is
        served may be absolute, and is appended so."""
        api = opened(tmp_path, ADDABLE)
        typed = posix(tmp_path, "c.ddd.json")
        reply = files_plan(api, "add", path=typed)
        assert (reply.status, reply.body["unjudged"], reply.body["brings"]) == (200, None, [])
        assert reply.body["changes"][0]["operations"] == [
            {"op": "insert", "pointer": "project.includes[2]", "raw": json.dumps(typed)}
        ]

    def test_a_file_is_appended_with_the_errors_it_would_bring(self, tmp_path: Path) -> None:
        api = opened(tmp_path, ADDABLE)
        described = tmp_path / "p.ddd.json"
        reply = files_plan(api, "add", path="b.ddd.json")
        assert reply == Reply(
            200,
            {
                "revision": 1,
                "changes": [
                    {
                        "file": posix(tmp_path, "p.ddd.json"),
                        "fingerprint": fingerprint(described.read_bytes()),
                        "operations": [
                            {
                                "op": "insert",
                                "pointer": "project.includes[2]",
                                "raw": '"b.ddd.json"',
                            }
                        ],
                        "hunks": [
                            {
                                "line": 6,
                                "before": ['      "lib/*.ddd.json"'],
                                "after": ['      "lib/*.ddd.json",', '      "b.ddd.json"'],
                            }
                        ],
                    }
                ],
                "unjudged": None,
                "brings": [
                    {
                        "file": posix(tmp_path, "b.ddd.json"),
                        "check": "missing-producer",
                        "message": "'Torque' is read by component 'B' but no component declares "
                        "it as output",
                    }
                ],
                "kept_by": None,
            },
        )

    def test_a_file_bringing_nothing_brings_nothing(self, tmp_path: Path) -> None:
        body = files_plan(opened(tmp_path, ADDABLE), "add", path="c.ddd.json").body
        assert (body["unjudged"], body["brings"], body["kept_by"]) == (None, [], None)

    @pytest.mark.parametrize(
        ("path", "status", "code", "says"),
        [
            pytest.param(
                "missing.ddd.json",
                404,
                "not-found",
                "missing.ddd.json names no file; a file not there yet is created, not added",
                id="no file",
            ),
            pytest.param(
                "p.ddd.json",
                409,
                "invalid",
                "p.ddd.json is this project's own description, which it cannot include",
                id="the description",
            ),
            pytest.param(
                "./a.ddd.json",
                409,
                "invalid",
                "./a.ddd.json is part of this project already, as the entry 'a.ddd.json'",
                id="an entry's file",
            ),
            pytest.param(
                "lib/l.ddd.json",
                409,
                "invalid",
                "lib/l.ddd.json is part of this project already: the pattern 'lib/*.ddd.json' "
                "brings it in",
                id="a pattern's file",
            ),
            pytest.param("notes.json", 409, "invalid", f"notes.json {NO_KIND}", id="no kind"),
            pytest.param(
                "half.ddd.json", 409, "invalid", f"half.ddd.json {NO_KIND}", id="half saved"
            ),
            pytest.param(
                "tool.py",
                409,
                "invalid",
                "tool.py is a python file, which a project names among its plugins rather than "
                "its includes",
                id="a plugin",
            ),
        ],
    )
    def test_a_refused_addition_says_why(
        self, tmp_path: Path, path: str, status: int, code: str, says: str
    ) -> None:
        assert refused(files_plan(opened(tmp_path, ADDABLE), "add", path=path)) == (
            status,
            code,
            says,
        )

    @pytest.fixture
    def served_below(self, tmp_path: Path) -> Api:
        """``ddd gui`` started in ``inside``, a description file lying one directory up."""
        write_tree(
            tmp_path,
            {
                "outside.ddd.json": component("S", declare("output", "Speed", unit="rpm")),
                "inside/p.ddd.json": project("P", "a.ddd.json"),
                "inside/a.ddd.json": component("A", declare("input", "Speed", unit="rpm")),
            },
        )
        session = Session(tmp_path / "inside")
        session.open(tmp_path / "inside" / "p.ddd.json")
        return Api(session, tmp_path / "inside" / "p.ddd.json", wait_seconds=0.05)

    @pytest.mark.parametrize("path", ["../outside.ddd.json", "../missing.ddd.json"])
    def test_a_file_outside_what_the_session_serves_is_refused_first(
        self, served_below: Api, tmp_path: Path, path: str
    ) -> None:
        """Decided by the rule every read and every edit is, so that adding and reading never
        disagree; asked before anything else, a file there or not."""
        assert refused(files_plan(served_below, "add", path=path)) == (
            409,
            "invalid",
            f"{path} lies outside what ddd gui serves, {(tmp_path / 'inside').resolve().as_posix()}"
            "; start it in a directory holding this file to add it here",
        )

    def test_a_file_the_project_has_is_refused_as_such_before_its_kind(
        self, tmp_path: Path
    ) -> None:
        api = opened(
            tmp_path,
            {"p.ddd.json": project("P", "lib/*.ddd.json"), "lib/half.ddd.json": '{"component": '},
        )
        assert refused(files_plan(api, "add", path="lib/half.ddd.json")) == (
            409,
            "invalid",
            "lib/half.ddd.json is part of this project already: the pattern 'lib/*.ddd.json' "
            "brings it in",
        )

    def test_an_addition_to_a_project_not_analysed_brings_nothing_unjudged(
        self, tmp_path: Path
    ) -> None:
        api = opened(tmp_path, {**READER_OF_A_BROKEN_WRITER, "c.ddd.json": component("C")})
        body = files_plan(api, "add", path="c.ddd.json").body
        assert (body["unjudged"], body["brings"], body["kept_by"]) == (UNJUDGED_ADDING, [], None)

    def test_an_addition_is_refused_where_a_file_changed_since_the_analysis(
        self, tmp_path: Path
    ) -> None:
        """What the file brings is judged against the revision's findings, which a file saved
        since no longer says."""
        api = opened(tmp_path, ADDABLE)
        (tmp_path / "lib" / "l.ddd.json").write_text(
            json.dumps(component("L", declare("input", "Speed", unit="km/h"))), encoding="utf-8"
        )
        assert refused(files_plan(api, "add", path="c.ddd.json")) == (
            409,
            "stale",
            "l.ddd.json changed since the project was analysed, so the change cannot be judged "
            "until the project is analysed again",
        )

    def test_an_addition_is_refused_where_a_file_appeared_since_the_analysis(
        self, tmp_path: Path
    ) -> None:
        """What the added file brings was listed with the new file's error beside it, which no
        revision had shown."""
        api = opened(tmp_path, PATTERN_OVER_A_DIRECTORY)
        write_tree(tmp_path, {"lib/new.ddd.json": NEW_READER})
        assert refused(files_plan(api, "add", path="c.ddd.json")) == (409, "stale", APPEARED)

    def test_an_addition_the_disk_refuses_is_refused_so_though_a_file_changed_since(
        self, tmp_path: Path
    ) -> None:
        """What the disk answers holds whenever it is asked; only the judgement is the revision's
        to spoil."""
        api = opened(tmp_path, ADDABLE)
        (tmp_path / "a.ddd.json").write_bytes((tmp_path / "a.ddd.json").read_bytes() + b"\n")
        assert refused(files_plan(api, "add", path="missing.ddd.json")) == (
            404,
            "not-found",
            "missing.ddd.json names no file; a file not there yet is created, not added",
        )

    def test_an_unjudged_addition_is_not_refused_for_a_file_saved_since(
        self, tmp_path: Path
    ) -> None:
        """Nothing is judged, so nothing is stale: a project not analysed is answered unjudged,
        with no refusal, whatever was saved since."""
        api = opened(tmp_path, {**READER_OF_A_BROKEN_WRITER, "c.ddd.json": component("C")})
        (tmp_path / "a.ddd.json").write_bytes((tmp_path / "a.ddd.json").read_bytes() + b"\n")
        body = files_plan(api, "add", path="c.ddd.json").body
        assert (body["unjudged"], body["brings"]) == (UNJUDGED_ADDING, [])


class TestRemovingAFile:
    """``remove``: every entry keyed by the path taken out, refused where the project without it
    would have an error more than it has now at its place."""

    def test_the_units_file_is_removed_and_the_project_read_again_checking_no_unit(
        self, tmp_path: Path
    ) -> None:
        """`pump.ddd.json` states units `units.ddd.json` declares, but a units file is what opts
        a project into checking its units: with none left no unit is checked, and nothing
        fails."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        described = root / "project.ddd.json"
        reply = files_plan(api, "remove", path=posix(root, "units.ddd.json"))
        assert reply == Reply(
            200,
            {
                "revision": 1,
                "changes": [
                    {
                        "file": posix(root, "project.ddd.json"),
                        "fingerprint": fingerprint(described.read_bytes()),
                        "operations": [
                            {"op": "remove", "pointer": "project.includes[0]", "raw": None}
                        ],
                        "hunks": [{"line": 7, "before": ['      "units.ddd.json",'], "after": []}],
                    }
                ],
                "unjudged": None,
                "brings": [],
                "kept_by": None,
            },
        )
        assert applied(api, reply.body).status == 200
        assert json.loads(described.read_text(encoding="utf-8"))["project"]["includes"] == [
            "sections.ddd.json",
            "constants.ddd.json",
            "rasters.ddd.json",
            "pump.ddd.json",
        ]
        assert errors_in(api) == []

    def test_a_file_whose_declaration_is_used_is_refused_naming_the_error_it_would_leave(
        self, tmp_path: Path
    ) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        assert refused(files_plan(api, "remove", path=posix(root, "constants.ddd.json"))) == (
            409,
            "invalid",
            "removing constants.ddd.json would leave one error more than the project has now at "
            "its place, in pump.ddd.json: 'PressureTrend' is dimensioned by 'TREND_SAMPLES', "
            "which is not a constant any file of this project declares",
        )

    def test_a_file_leaving_several_errors_is_refused_naming_the_first_and_how_many(
        self, tmp_path: Path
    ) -> None:
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        assert refused(files_plan(api, "remove", path=posix(root, "sections.ddd.json"))) == (
            409,
            "invalid",
            "removing sections.ddd.json would leave 3 errors more than the project has now at "
            "their places, the first in pump.ddd.json: 'PumpSpeed' is placed in '.fast_ram', "
            "which is not a section any file of this project declares",
        )

    @pytest.mark.parametrize(
        ("pattern", "says"),
        [
            pytest.param(
                "lib/*.ddd.json",
                "removing lib/*.ddd.json would leave one error more than the project has now at "
                "its place, in a.ddd.json: 'Speed' is read by component 'A' but no component "
                "declares it as output",
                id="one error",
            ),
            pytest.param(
                "sensors/*.ddd.json",
                "removing sensors/*.ddd.json would leave 2 errors more than the project has now "
                "at their places, the first in a.ddd.json: 'Torque' is read by component 'A' but "
                "no component declares it as output",
                id="several",
            ),
        ],
    )
    def test_a_pattern_in_a_directory_is_named_as_the_includes_spell_it(
        self, tmp_path: Path, pattern: str, says: str
    ) -> None:
        """Named relative to the description's directory, as its entry is written, and not by
        its last part: `lib/*.ddd.json`, never `*.ddd.json`, which another pattern may end in."""
        api = opened(tmp_path, WRITERS_IN_DIRECTORIES)
        assert refused(files_plan(api, "remove", path=posix(tmp_path, pattern))) == (
            409,
            "invalid",
            says,
        )

    def test_a_failing_project_s_count_is_of_errors_more_at_their_places_not_a_total(
        self, tmp_path: Path
    ) -> None:
        """The project fails already, with four errors, and the writer removed reads a variable
        nothing writes. Measured: five errors once it is gone, its own leaving with it, so read as
        a total, "two errors more than it has now" would say six."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "w.ddd.json"),
                "a.ddd.json": component(
                    "A", *(declare("input", name) for name in ("X1", "X2", "X3", "Y1", "Y2"))
                ),
                "w.ddd.json": component(
                    "W", declare("output", "Y1"), declare("output", "Y2"), declare("input", "Z")
                ),
            },
        )
        assert len(errors_in(api)) == 4
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "w.ddd.json"))) == (
            409,
            "invalid",
            "removing w.ddd.json would leave 2 errors more than the project has now at their "
            "places, the first in a.ddd.json: 'Y1' is read by component 'A' but no component "
            "declares it as output",
        )

    def test_a_removal_is_named_by_its_entry_as_the_includes_spell_it(self, tmp_path: Path) -> None:
        """Written through a link to a directory, the pattern is keyed by where the link leads,
        and named as it is written - not by the key, which names a pattern no entry spells."""
        write_tree(tmp_path, {"lib/w.ddd.json": component("W", declare("output", "Speed"))})
        directory_link(tmp_path / "link", tmp_path / "lib")
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "link/*.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Speed")),
            },
        )
        key = get(api, "/api/files").body["entries"][1]["key"]
        assert key == posix(tmp_path, "lib/*.ddd.json")
        assert refused(files_plan(api, "remove", path=key)) == (
            409,
            "invalid",
            "removing link/*.ddd.json would leave one error more than the project has now at its "
            "place, in a.ddd.json: 'Speed' is read by component 'A' but no component declares it "
            "as output",
        )

    def test_a_file_listed_twice_is_named_by_the_first_entry_removed(self, tmp_path: Path) -> None:
        """Every entry naming the file goes, and the one the list has first names the removal."""
        api = opened(
            tmp_path,
            {
                **READER_OF_A_BROKEN_WRITER,
                "p.ddd.json": project("P", "./lib/b.ddd.json", "a.ddd.json", "lib/b.ddd.json"),
            },
        )
        body = files_plan(api, "remove", path=posix(tmp_path, "lib/b.ddd.json")).body
        assert body["unjudged"] == (
            "not every analysis of this project ran to its end, so what removing ./lib/b.ddd.json "
            "leaves cannot be judged"
        )
        assert body["changes"][0]["operations"] == [
            {"op": "remove", "pointer": "project.includes[2]", "raw": None},
            {"op": "remove", "pointer": "project.includes[0]", "raw": None},
        ]

    def test_a_file_a_pattern_pulled_in_is_refused_naming_the_pattern(self, tmp_path: Path) -> None:
        api = opened(
            tmp_path,
            {"p.ddd.json": project("P", "lib/*.ddd.json"), "lib/a.ddd.json": component("A")},
        )
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "lib/a.ddd.json"))) == (
            409,
            "invalid",
            "a.ddd.json has no entry of its own: the pattern 'lib/*.ddd.json' brings it in, and "
            "only the whole pattern can be removed",
        )

    def test_a_path_no_entry_brings_in_is_not_found(self, tmp_path: Path) -> None:
        api = opened(
            tmp_path, {"p.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")}
        )
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "other.ddd.json"))) == (
            404,
            "not-found",
            "no entry of p.ddd.json's includes names other.ddd.json, and none of its patterns "
            "matches it",
        )

    def test_a_key_ending_in_a_link_is_named_as_the_request_sent_it(self, tmp_path: Path) -> None:
        """Never by what it resolves to: `elsewhere`, a link among the files served, leads to
        `outside`, a directory beside them that is not served, and the refusal names only what
        the request wrote."""
        write_tree(
            tmp_path,
            {
                "served/p.ddd.json": project("P", "a.ddd.json"),
                "served/a.ddd.json": component("A"),
                "outside/secret.ddd.json": component("S"),
            },
        )
        directory_link(tmp_path / "served" / "elsewhere", tmp_path / "outside")
        session = Session(tmp_path / "served")
        session.open(tmp_path / "served" / "p.ddd.json")
        api = Api(session, tmp_path / "served" / "p.ddd.json", wait_seconds=0.05)
        sent = (tmp_path / "served" / "elsewhere").as_posix()
        assert refused(files_plan(api, "remove", path=sent)) == (
            404,
            "not-found",
            "no entry of p.ddd.json's includes names elsewhere, and none of its patterns "
            "matches it",
        )

    def test_a_file_a_pattern_keeps_in_the_project_says_which(self, tmp_path: Path) -> None:
        """The literal entry goes, and the pattern left still brings the file in: allowed, and
        the plan says so for the preview to tell the reader."""
        api = opened(
            tmp_path,
            {"p.ddd.json": project("P", "*.ddd.json", "a.ddd.json"), "a.ddd.json": component("A")},
        )
        body = files_plan(api, "remove", path=posix(tmp_path, "a.ddd.json")).body
        assert (body["unjudged"], body["brings"], body["kept_by"]) == (None, [], "*.ddd.json")
        assert body["changes"][0]["operations"] == [
            {"op": "remove", "pointer": "project.includes[1]", "raw": None}
        ]

    def test_an_unjudged_removal_says_which_pattern_keeps_the_file_all_the_same(
        self, tmp_path: Path
    ) -> None:
        """Whether a pattern keeps the file is the loader's rule over the entries left, and needs
        no analysis: a project that is not analysed is told it too."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "*.ddd.json", "a.ddd.json"),
                "a.ddd.json": component("A"),
                "b.ddd.json": '{"component": ',
            },
        )
        body = files_plan(api, "remove", path=posix(tmp_path, "a.ddd.json")).body
        assert (body["unjudged"], body["brings"], body["kept_by"]) == (
            "not every analysis of this project ran to its end, so what removing a.ddd.json "
            "leaves cannot be judged",
            [],
            "*.ddd.json",
        )

    def test_a_row_s_key_spelled_another_way_still_names_its_row(self, tmp_path: Path) -> None:
        """Resolved before it is compared, as every path the page sends is, and as the row's own
        key was made."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        spelled = f"{root.resolve().as_posix()}/sub/../units.ddd.json"
        body = files_plan(api, "remove", path=spelled).body
        assert body["changes"][0]["operations"] == [
            {"op": "remove", "pointer": "project.includes[0]", "raw": None}
        ]

    def test_a_broken_file_of_a_project_not_analysed_is_removed_unjudged(
        self, tmp_path: Path
    ) -> None:
        """Judged, removing the half-saved writer would be refused for the `missing-producer`
        its reader is left with - an error of an analysis that never ran on the project as it is,
        so one the reader cannot see. Not every run analysed: allowed, and said to be unjudged."""
        api = opened(tmp_path, READER_OF_A_BROKEN_WRITER)
        reply = files_plan(api, "remove", path=posix(tmp_path, "lib/b.ddd.json"))
        assert reply.status == 200
        assert (reply.body["unjudged"], reply.body["brings"], reply.body["kept_by"]) == (
            UNJUDGED_REMOVING,
            [],
            None,
        )

    def test_a_missing_file_s_entry_is_removed_unjudged(self, tmp_path: Path) -> None:
        """A plain path naming no file is `file-not-found`, a load check: the project is not
        analysed, and taking the entry out is allowed without a judgement."""
        api = opened(tmp_path, ENTRIES_OF_EVERY_SHAPE)
        body = files_plan(api, "remove", path=posix(tmp_path, "missing.ddd.json")).body
        assert (body["unjudged"], body["brings"], body["kept_by"]) == (
            "not every analysis of this project ran to its end, so what removing missing.ddd.json "
            "leaves cannot be judged",
            [],
            None,
        )
        assert body["changes"][0]["operations"] == [
            {"op": "remove", "pointer": "project.includes[2]", "raw": None}
        ]

    def test_a_removal_is_refused_where_any_file_changed_since_the_analysis(
        self, tmp_path: Path
    ) -> None:
        """Not only the description: a component saved just before the next poll would make an
        error that save brought read as the removal's. Every file saved since is named, in the
        revision's order."""
        api, root = copied(tmp_path, "vocabulary", "project.ddd.json")
        for saved in ("rasters.ddd.json", "pump.ddd.json"):
            (root / saved).write_bytes((root / saved).read_bytes() + b"\n")
        assert refused(files_plan(api, "remove", path=posix(root, "units.ddd.json"))) == (
            409,
            "stale",
            "pump.ddd.json, rasters.ddd.json changed since the project was analysed, so the "
            "change cannot be judged until the project is analysed again",
        )

    def test_a_removal_is_refused_where_a_file_appeared_since_the_analysis(
        self, tmp_path: Path
    ) -> None:
        """Saved where the pattern matches once the revision was analysed, a new component reads
        what nothing writes. Judged, removing a file nothing uses was refused for the new file's
        error, which no revision had shown."""
        api = opened(tmp_path, PATTERN_OVER_A_DIRECTORY)
        write_tree(tmp_path, {"lib/new.ddd.json": NEW_READER})
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "spare.ddd.json"))) == (
            409,
            "stale",
            APPEARED,
        )

    def test_a_file_appearing_under_a_sub_project_s_pattern_is_seen_too(
        self, tmp_path: Path
    ) -> None:
        """Every description of the tree is expanded, a sub-project's as well as the root's."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/project.ddd.json", "spare.ddd.json"),
                "sub/project.ddd.json": project("Sub", "lib/*.ddd.json"),
                "sub/lib/l.ddd.json": component("L"),
                "spare.ddd.json": component("Spare"),
            },
        )
        write_tree(tmp_path, {"sub/lib/new.ddd.json": NEW_READER})
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "spare.ddd.json"))) == (
            409,
            "stale",
            APPEARED,
        )

    def test_a_file_two_entries_reach_is_named_once(self, tmp_path: Path) -> None:
        """Both patterns match what the analysis read, and both reach the new file."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "lib/*.ddd.json", "lib/*w.ddd.json", "spare.ddd.json"),
                "lib/low.ddd.json": component("Low"),
                "spare.ddd.json": component("Spare"),
            },
        )
        write_tree(tmp_path, {"lib/new.ddd.json": NEW_READER})
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "spare.ddd.json"))) == (
            409,
            "stale",
            APPEARED,
        )

    def test_a_file_changed_is_named_before_one_that_appeared(self, tmp_path: Path) -> None:
        api = opened(tmp_path, PATTERN_OVER_A_DIRECTORY)
        write_tree(tmp_path, {"lib/new.ddd.json": NEW_READER})
        (tmp_path / "a.ddd.json").write_bytes((tmp_path / "a.ddd.json").read_bytes() + b"\n")
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "spare.ddd.json"))) == (
            409,
            "stale",
            "a.ddd.json changed since the project was analysed, so the change cannot be judged "
            "until the project is analysed again",
        )

    def test_an_unjudged_plan_is_not_refused_for_a_file_that_appeared(self, tmp_path: Path) -> None:
        """Nothing is judged, so nothing appearing spoils a judgement: a project not analysed is
        answered unjudged, whatever a pattern matches since."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "lib/*.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Speed")),
                "lib/b.ddd.json": READER_OF_A_BROKEN_WRITER["lib/b.ddd.json"],
                "c.ddd.json": component("C"),
            },
        )
        write_tree(tmp_path, {"lib/new.ddd.json": NEW_READER})
        removed = files_plan(api, "remove", path=posix(tmp_path, "a.ddd.json")).body
        assert removed["unjudged"] == (
            "not every analysis of this project ran to its end, so what removing a.ddd.json "
            "leaves cannot be judged"
        )
        added = files_plan(api, "add", path="c.ddd.json").body
        assert added["unjudged"] == UNJUDGED_ADDING

    def test_a_removal_the_disk_refuses_is_refused_so_though_a_file_changed_since(
        self, tmp_path: Path
    ) -> None:
        """What the disk answers holds whenever it is asked; only the judgement is the revision's
        to spoil."""
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "b.ddd.json", "lib/*.ddd.json"),
                "b.ddd.json": component("B"),
                "lib/a.ddd.json": component("A"),
            },
        )
        (tmp_path / "b.ddd.json").write_bytes((tmp_path / "b.ddd.json").read_bytes() + b"\n")
        assert refused(files_plan(api, "remove", path=posix(tmp_path, "lib/a.ddd.json"))) == (
            409,
            "invalid",
            "a.ddd.json has no entry of its own: the pattern 'lib/*.ddd.json' brings it in, and "
            "only the whole pattern can be removed",
        )

    def test_an_unjudged_removal_is_not_refused_for_a_file_saved_since(
        self, tmp_path: Path
    ) -> None:
        """Nothing is judged, so nothing is stale: a project not analysed has its removal answered
        unjudged, with no refusal, whatever was saved since."""
        api = opened(tmp_path, READER_OF_A_BROKEN_WRITER)
        (tmp_path / "a.ddd.json").write_bytes((tmp_path / "a.ddd.json").read_bytes() + b"\n")
        body = files_plan(api, "remove", path=posix(tmp_path, "lib/b.ddd.json")).body
        assert (body["unjudged"], body["brings"]) == (UNJUDGED_REMOVING, [])


LOWERED: Final = tuple(
    f"{check}=warning"
    for check in (
        "duplicate-unit",
        "duplicate-constant",
        "duplicate-type",
        "duplicate-section",
        "duplicate-event",
        "include-empty",
    )
)
"""The load checks the drifted examples below report, lowered by their build record: each is an
error that stops a run at its read, and lowered, the analysis goes on, so that one revision
carries what the read and the analysis say alike."""


def definition_of(document: dict[str, Any], name: str) -> dict[str, Any]:
    """The definition a component's document declares ``name`` by."""
    return next(
        entry["definition"]
        for entry in document["component"]["interface"]
        if entry["definition"]["name"] == name
    )


def changed(root: Path, name: str, change: Callable[[dict[str, Any]], object]) -> None:
    """``root / name`` read as json, ``change`` made to it, and written back."""
    path = root / name
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def unnamed(value: Any) -> Any:
    """``value`` with every ``id`` taken out, however deep: each producing declaration is then a
    ``missing-id``."""
    if isinstance(value, dict):
        return {key: unnamed(entry) for key, entry in value.items() if key != "id"}
    if isinstance(value, list):
        return [unnamed(entry) for entry in value]
    return value


def drift_demo(root: Path) -> None:
    """The sub-project read first, so that the index lists `event_logger.ddd.json`'s
    declarations before the components' while the revision files them last; a vocabulary
    listing `%` twice and leaving `V`, `degC` and `ms` out; `ValueE` read as `V` against its
    producer's `Hz`; a structure member stating `degC`; an `init` no `uint16` holds; and an
    include matching nothing."""
    changed(
        root,
        "demo.ddd.json",
        lambda document: document["project"].update(
            includes=[
                "subsystems/logging/logging.ddd.json",
                "components/*.ddd.json",
                "units.ddd.json",
                "missing/*.ddd.json",
            ]
        ),
    )
    write_tree(root, {"units.ddd.json": {"units": ["%", "%", {"unit": "Hz"}]}})
    changed(
        root,
        "subsystems/logging/event_logger.ddd.json",
        lambda document: definition_of(document, "ValueE").update(unit="V"),
    )
    changed(
        root,
        "components/sensor_hub.ddd.json",
        lambda document: document["component"]["types"][1]["members"][1].update(unit="degC"),
    )
    changed(
        root,
        "components/controller.ddd.json",
        lambda document: definition_of(document, "ParameterA").update(init=999999),
    )


def drift_pump(document: dict[str, Any]) -> None:
    """A unit the vocabulary does not list, a measurement placed in read-only memory, an `init` no
    `uint16` holds on a parameter naming a raster, a constant no shape can be sized by, and
    limits the type's own datatype cannot reach."""
    definition_of(document, "PumpSpeed")["unit"] = "bar"
    definition_of(document, "ManifoldPressure")["section"] = ".calib"
    definition_of(document, "TorqueLimit").update(init=99999999, raster="10ms")
    document["component"]["constants"][0]["value"] = 0
    document["component"]["types"][0]["limits"] = {"min": 0, "max": 99999999}


def drift_vocabulary(root: Path) -> None:
    """Every vocabulary of the example given a finding: `pump.ddd.json` drifted as
    :func:`drift_pump` says, a unit, a constant and a section each declared twice, two rasters
    claiming one event, and an include matching nothing."""
    changed(root, "pump.ddd.json", drift_pump)
    changed(root, "units.ddd.json", lambda document: document["units"].append("rpm"))
    changed(
        root,
        "rasters.ddd.json",
        lambda document: document["rasters"].append({"raster": "5ms", "event": 1}),
    )
    changed(
        root,
        "sections.ddd.json",
        lambda document: document["sections"].append(
            {"section": ".calib", "access": "read-only", "alignment": 4}
        ),
    )
    changed(
        root,
        "constants.ddd.json",
        lambda document: document["constants"].append({"name": "TREND_SAMPLES", "value": 16}),
    )
    changed(
        root,
        "project.ddd.json",
        lambda document: document["project"]["includes"].insert(1, "missing/*.ddd.json"),
    )


def drift_structures(root: Path) -> None:
    """A vocabulary listing `ms` twice and `degC` not at all, `Temperature_t` declared a second
    time by the component producing `Inlet`, `Inlet` read as another type than it is written as -
    `sensing.ddd.json`, which the index lists first, filed after `monitoring.ddd.json` - and an
    include matching nothing."""
    changed(
        root,
        "project.ddd.json",
        lambda document: document["project"].update(
            includes=["units.ddd.json", *document["project"]["includes"], "missing/*.ddd.json"]
        ),
    )
    write_tree(root, {"units.ddd.json": {"units": ["ms", "ms"]}})
    changed(
        root,
        "sensing.ddd.json",
        lambda document: document["component"].update(
            types=[scalar_type("Temperature_t", "uint8", unit="degC")]
        ),
    )
    changed(
        root,
        "monitoring.ddd.json",
        lambda document: definition_of(document, "Inlet").update(typename="Sample_t"),
    )


DRIFTED: Final[dict[str, tuple[str, Callable[[Path], None]]]] = {
    "demo": ("demo.ddd.json", drift_demo),
    "vocabulary": ("project.ddd.json", drift_vocabulary),
    "structures": ("project.ddd.json", drift_structures),
}
"""Each example the answers are checked on, with its description and how it is drifted."""


def through(path: Path, real: Path, link: Path) -> Path:
    """``path``, under ``real``, spelled through ``link`` instead."""
    return link / path.relative_to(real)


def respelled(filed: Filed, real: Path, link: Path) -> Filed:
    """A finding shown on the same file and place, both spelled through ``link``: a second
    spelling of every path, as a plugin filing its findings by a path of its own would give."""
    found = filed.diagnostic
    location = found.location
    if location is not None:
        found = dataclasses.replace(
            found, location=dataclasses.replace(location, path=through(location.path, real, link))
        )
    return Filed(through(filed.file, real, link), found)


def drifted(
    tmp_path: Path, example: str, monkeypatch: pytest.MonkeyPatch, *, spelled_again: bool
) -> Api:
    """``ddd gui``'s api over a copy of one of the examples, every id taken out and the rest
    drifted until the analysis reports findings on every kind of name the panels list - under
    :data:`LOWERED`, so the analysis runs to its end. ``spelled_again``: every finding of the
    revision filed through a link to the directory the copy is in, before any request."""
    description, drift = DRIFTED[example]
    real = tmp_path / "real"
    root = real / example
    shutil.copytree(EXAMPLES / example, root)
    for path in root.rglob("*.ddd.json"):
        document = unnamed(json.loads(path.read_text(encoding="utf-8")))
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    drift(root)
    build_record(root, root / description, severity=list(LOWERED))
    session = Session(root)
    session.open(root / description)
    revision = session.revision
    assert revision is not None
    assert revision.analysed
    if spelled_again:
        link = tmp_path / "link"
        directory_link(link, real)
        findings = tuple(respelled(filed, real.resolve(), link) for filed in revision.findings)
        monkeypatch.setattr(session, "_revision", dataclasses.replace(revision, findings=findings))
    return Api(session, root / description, wait_seconds=0.05)


def analysed(api: Api) -> tuple[Revision, Index]:
    revision = api.session.revision
    assert revision is not None
    assert revision.index is not None
    return revision, revision.index


def as_listed(api: Api, found: Iterable[Filed]) -> list[dict[str, Any]]:
    """Findings as a panel lists them, each with where it leads: what the api answered for the
    findings a predicate kept, before it indexed a revision's findings by file."""
    revision, _ = analysed(api)
    sources = {file.path.resolve(): file for file in revision.files}
    cache: dict[Path, Document] = {}
    return [_finding(filed, sources.get(filed.file.resolve()), cache) for filed in found]


def places_as_read(built: Index, unit: str) -> list[dict[str, Any]]:
    """Every place stating ``unit`` as ``GET /api/unit`` answered it before this part: a
    variable's component and role read by :func:`ddd.variables.declarations_of`, and one its file
    no longer declares left out."""
    cache: dict[Path, Document] = {}
    sites = []
    for stated in built.units.get(unit, ()):
        component_name = role = None
        if stated.kind == "variable":
            definition = Site(stated.site.path, stated.site.pointer.removesuffix(".unit"))
            declared = next(
                (d for d in declarations_of(built, stated.name, cache) if d.site == definition),
                None,
            )
            if declared is None:
                continue
            component_name, role = declared.component, declared.role
        sites.append(
            {
                "path": stated.site.path.resolve().as_posix(),
                "pointer": stated.site.pointer,
                "kind": stated.kind,
                "name": stated.name,
                "component": component_name,
                "role": role,
            }
        )
    return sites


BY_KIND: Final[dict[str, tuple[Vocabulary, str]]] = {
    "constant": (CONSTANTS, "/api/constant"),
    "section": (SECTIONS, "/api/section"),
    "raster": (RASTERS, "/api/raster"),
}
"""Each kind of row of the Shared files tab, with its vocabulary and its panel's route."""


@pytest.mark.parametrize("spelled_again", [False, True], ids=["as-filed", "through-a-link"])
class TestEachAnswerIsEveryFindingAskedAlone:
    """Every name's panel and every tab's count, against what the api computed before it indexed
    a revision's findings: every finding of the revision asked the name's own predicate, in the
    revision's order - which is file by file in path order, and not the order the index lists a
    name's places in. Each example is drifted so that the two orders differ where a name's
    findings lie on several files, and asked once as the analysis filed it and once with every
    finding filed through a link, a second spelling of every path."""

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_the_state_lists_every_finding_with_where_it_leads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, _ = analysed(api)
        listed = get(api, "/api/state").body["findings"]
        assert listed == as_listed(api, revision.findings)
        assert listed

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_every_variable_s_panel_lists_its_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        answered = 0
        for name in sorted(built.declarations):
            declared = declarations_of(built, name, {})
            expected = as_listed(
                api,
                [
                    filed
                    for filed in revision.findings
                    if located_on(declared, filed.file, filed.diagnostic)
                ],
            )
            assert get(api, "/api/variable", name=name).body["findings"] == expected, name
            answered += len(expected)
        assert answered

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_every_unit_s_panel_lists_its_places_and_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        answered = 0
        for unit in sorted(built.units.keys() | built.vocabulary.keys()):
            body = get(api, "/api/unit", name=unit).body
            expected = as_listed(
                api,
                [
                    filed
                    for filed in revision.findings
                    if located_on_unit(built, unit, filed.file, filed.diagnostic)
                ],
            )
            assert body["findings"] == expected, unit
            assert body["sites"] == places_as_read(built, unit), unit
            answered += len(expected)
        assert answered

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_every_type_s_panel_lists_its_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        answered = 0
        for name in sorted(built.types):
            expected = as_listed(
                api,
                [
                    filed
                    for filed in revision.findings
                    if located_in_type(built, name, filed.file, filed.diagnostic)
                ],
            )
            assert get(api, "/api/type", name=name).body["findings"] == expected, name
            answered += len(expected)
        assert answered

    def test_every_constant_section_and_raster_s_panel_lists_its_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelled_again: bool
    ) -> None:
        """The vocabulary example alone declares entries of the three vocabularies."""
        api = drifted(tmp_path, "vocabulary", monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        answered = 0
        for vocabulary, route in BY_KIND.values():
            for name in sorted(vocabulary.entries(built)):
                expected = as_listed(
                    api,
                    [
                        filed
                        for filed in revision.findings
                        if located_on_entry(vocabulary, built, name, filed.file, filed.diagnostic)
                    ],
                )
                assert get(api, route, name=name).body["findings"] == expected, name
                answered += len(expected)
        assert answered

    @pytest.mark.parametrize("example", ["demo", "vocabulary"])
    def test_every_grid_lists_the_findings_about_its_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        """The two examples that state an `init` a grid shows a finding about. A name with no grid
        - one the dictionary holds no object of - is refused before any finding is read."""
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        assert revision.dictionary is not None
        answered = 0
        for name in sorted(built.declarations):
            reply = get(api, "/api/values", name=name)
            if reply.status != 200:
                continue
            grid = grid_of(revision.dictionary, built, name)
            at = f"{grid.pointer}.definition.init"
            expected = as_listed(
                api,
                [
                    filed
                    for filed in revision.findings
                    if grid.pointer is not None
                    and filed.file.resolve().as_posix() == grid.file
                    and filed.diagnostic.location is not None
                    and filed.diagnostic.location.pointer == at
                ],
            )
            assert reply.body["findings"] == expected, name
            answered += len(expected)
        assert answered

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_the_units_and_types_tabs_count_what_each_panel_lists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        units = get(api, "/api/units").body["units"]
        assert [row["unit"] for row in units] == sorted(built.units.keys() | built.vocabulary)
        assert [row["findings"] for row in units] == [
            sum(
                1
                for filed in revision.findings
                if located_on_unit(built, row["unit"], filed.file, filed.diagnostic)
            )
            for row in units
        ]
        types_listed = get(api, "/api/types").body["types"]
        assert [row["name"] for row in types_listed] == sorted(built.types)
        assert [row["findings"] for row in types_listed] == [
            sum(
                1
                for filed in revision.findings
                if located_in_type(built, row["name"], filed.file, filed.diagnostic)
            )
            for row in types_listed
        ]
        assert any(row["findings"] for row in units)
        assert any(row["findings"] for row in types_listed)

    def test_the_shared_files_tab_counts_what_each_panel_lists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelled_again: bool
    ) -> None:
        api = drifted(tmp_path, "vocabulary", monkeypatch, spelled_again=spelled_again)
        revision, built = analysed(api)
        rows = get(api, "/api/shared").body["entries"]
        assert [(row["kind"], row["name"]) for row in rows] == sorted(
            (vocabulary.kind, name)
            for vocabulary, _ in BY_KIND.values()
            for name in vocabulary.entries(built)
        )
        assert [row["findings"] for row in rows] == [
            sum(
                1
                for filed in revision.findings
                if located_on_entry(
                    BY_KIND[row["kind"]][0], built, row["name"], filed.file, filed.diagnostic
                )
            )
            for row in rows
        ]
        assert any(row["findings"] for row in rows)

    @pytest.mark.parametrize("example", list(DRIFTED))
    def test_the_files_tab_counts_the_findings_at_each_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str, spelled_again: bool
    ) -> None:
        """Compared as a whole location, the description's own path and the entry's pointer, as
        the tab always compared them - so an entry's finding filed through the link is no entry's,
        and the tab counts none where the analysis filed one."""
        api = drifted(tmp_path, example, monkeypatch, spelled_again=spelled_again)
        revision, _ = analysed(api)
        entries = get(api, "/api/files").body["entries"]
        counted = [
            sum(
                1
                for filed in revision.findings
                if filed.diagnostic.location
                == Location(revision.project, f"project.includes[{entry['index']}]")
            )
            for entry in entries
        ]
        assert [entry["findings"] for entry in entries] == counted
        assert any(counted) is not spelled_again


# A vocabulary of two units, and one variable read as it is written: an edit of the reader's unit
# to one the vocabulary does not list brings an `unknown-unit`, which the Units tab counts.
LISTED = {
    "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json", "b.ddd.json"),
    "units.ddd.json": {"units": ["rpm", "Hz"]},
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
}

KEPT: Final = ("/api/graph", "/api/units", "/api/types", "/api/shared", "/api/files")
"""The answers made once per revision and kept for as long as it is the newest."""


class TestAnswersKeptForARevision:
    """What the api makes of one revision it makes once: the findings grouped by file, and the
    graph and the tabs' rows, each kept until a new revision - or an edit - is written."""

    @pytest.mark.parametrize("path", KEPT)
    def test_one_revision_answers_with_the_very_reply_it_made_first(
        self, api: Api, path: str
    ) -> None:
        first = get(api, path)
        assert first.status == 200
        assert get(api, path) is first

    def test_a_new_revision_answers_the_graph_anew_showing_the_change(
        self, api: Api, root: Path
    ) -> None:
        before = get(api, "/api/graph")
        assert [flow["disagreements"] for flow in before.body["flows"]] == [[]]
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        after = get(api, "/api/graph")
        assert after is not before
        assert after.body["revision"] == 2
        (flow,) = after.body["flows"]
        assert [d["check"] for d in flow["disagreements"]] == ["definition-mismatch"]

    def test_a_new_revision_counts_its_own_findings_on_the_tabs_rows(self, tmp_path: Path) -> None:
        """The rows count the findings the newest revision groups, never the last one's: the
        unit the edit brings is counted with the finding it brings."""
        api = opened(tmp_path, LISTED)
        before = get(api, "/api/units").body["units"]
        assert [(row["unit"], row["findings"]) for row in before] == [("Hz", 0), ("rpm", 0)]
        assert post(api, "/api/edit", unit_edit(api, tmp_path, "Nm")).status == 200
        after = get(api, "/api/units").body
        assert after["revision"] == 2
        assert [(row["unit"], row["findings"]) for row in after["units"]] == [
            ("Hz", 0),
            ("Nm", 1),
            ("rpm", 0),
        ]

    def test_an_edit_written_before_its_analysis_answers_anew(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An answer reading the files as they stand changes with an edit before the revision
        does, once an edit no longer waits for its analysis: kept by the edits written as well
        as by the revision. Stood for here by the count moving on its own."""
        first = get(api, "/api/units")
        monkeypatch.setattr(api.session, "_edits", api.session.edits + 1)
        again = get(api, "/api/units")
        assert again is not first
        assert again == first

    def test_a_revision_is_derived_once_and_its_successor_s_answers_replace_its_own(
        self, api: Api, root: Path
    ) -> None:
        revision = api.session.revision
        assert revision is not None
        assert api._derive(revision) is api._derive(revision)
        for path in KEPT:
            get(api, path)
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        newer = api.session.revision
        assert newer is not None
        assert api._derive(newer) is not api._derive(revision)
        get(api, "/api/graph")
        assert {key[1] for key in api._memo} == {newer.number}
