"""A project's types as the Types tab shows them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import (
    component,
    declare,
    project,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.project_types import (
    fixed_by,
    kind_of,
    located_in_type,
    members_of,
    row_of,
    type_rows,
    uses_of,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _finding(check: str, pointer: str) -> Diagnostic:
    return Diagnostic(check, Severity.ERROR, "message", Location(Path(), pointer))


@pytest.fixture
def built() -> Index:
    return index(load_workspace(EXAMPLES / "structures" / "project.ddd.json", DiagnosticBag()))


@pytest.fixture
def demo() -> Index:
    return index(load_workspace(EXAMPLES / "demo" / "demo.ddd.json", DiagnosticBag()))


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


class TestRows:
    def test_every_type_is_a_row_with_its_kind_and_description(self, built, cache) -> None:
        rows = {row.name: row for row in type_rows(built, (), cache)}
        assert [row.name for row in type_rows(built, (), cache)] == sorted(rows)
        assert (rows["Temperature_t"].kind, rows["Temperature_t"].uses) == ("scalar", 3)
        assert rows["Temperature_t"].description.startswith("A temperature as every component")
        assert rows["DriverStatus_t"].kind == "external"
        assert rows["Sample_t"].kind == "struct"

    def test_the_uses_are_counted_as_the_index_recorded_them(self, built, cache) -> None:
        # Measured against examples/structures as it stands: every type there is named at least
        # once, and Sensor_t twice - by the component that produces Inlet and the one that reads
        # it. A test asserting a type nothing names belongs to a project built for it, below.
        rows = {row.name: row.uses for row in type_rows(built, (), cache)}
        assert rows == {
            "DriverStatus_t": 1,
            "Sample_t": 1,
            "SensorCal_t": 1,
            "Sensor_t": 2,
            "Status_t": 1,
            "Temperature_t": 3,
        }

    def test_a_findings_count_is_the_type_s_own(self, built, cache, tmp_path) -> None:
        # A unit no vocabulary lists, stated by the scalar type: one finding, inside its entry.
        findings = [
            (site.path, _finding("unknown-unit", site.pointer + ".unit"))
            for name, site in built.types.items()
            if name == "Temperature_t"
        ]
        rows = {row.name: row for row in type_rows(built, findings, cache)}
        assert rows["Temperature_t"].findings == 1
        assert rows["Sample_t"].findings == 0

    def test_row_of_answers_the_one_row_type_rows_would(self, built, cache) -> None:
        # `_type` pulls a single row through `row_of` rather than `type_rows`' whole table; the
        # two must still agree; a type the finding is inside and one it is not, so both of
        # `located_in_type`'s outcomes are exercised on this path too.
        findings = [
            (site.path, _finding("unknown-unit", site.pointer + ".unit"))
            for name, site in built.types.items()
            if name == "Temperature_t"
        ]
        rows = {row.name: row for row in type_rows(built, findings, cache)}
        assert row_of(built, "Temperature_t", findings, cache) == rows["Temperature_t"]
        assert row_of(built, "Sample_t", findings, cache) == rows["Sample_t"]

    def test_a_finding_elsewhere_or_on_no_type_locates_nothing(self, built) -> None:
        # `type_rows` only ever asks about a finding already paired with the type's own file,
        # so a mismatch is exercised directly here rather than through it.
        temperature = built.types["Temperature_t"]
        elsewhere = EXAMPLES / "structures" / "sensing.ddd.json"
        finding = _finding("unknown-unit", f"{temperature.pointer}.unit")
        assert not located_in_type(built, "Temperature_t", elsewhere, finding)
        assert not located_in_type(built, "Nothing_t", temperature.path, finding)

    def test_a_finding_with_no_location_locates_nothing(self, built) -> None:
        # A check about the project rather than a place in a file files no location at all - a
        # real input, unlike the mismatches above, and one this suite otherwise never hands
        # `located_in_type`, so its `location is None` arm goes untested by everything else here.
        temperature = built.types["Temperature_t"]
        finding = Diagnostic("missing-producer", Severity.ERROR, "message")
        assert not located_in_type(built, "Temperature_t", temperature.path, finding)


class TestUses:
    def test_a_declaration_naming_a_type_comes_with_its_component_and_role(self, built, cache):
        # Both declarations of one variable name Sensor_t, so the panel lists two uses of the
        # same name: keyed by name alone, one would swallow the other.
        assert [
            (use.kind, use.name, use.component, use.role)
            for use in uses_of(built, "Sensor_t", cache)
        ] == [
            ("variable", "Inlet", "Sensing", "produces"),
            ("variable", "Inlet", "Monitoring", "reads"),
        ]

    def test_a_member_nesting_a_type_is_named_by_its_structure_and_member(self, built, cache):
        assert [
            (use.kind, use.name, use.component, use.role)
            for use in uses_of(built, "Temperature_t", cache)
        ] == [
            ("member", "Sample_t.value", None, None),
            ("member", "SensorCal_t.warnLimit", None, None),
            ("member", "Sensor_t.history", None, None),
        ]

    def test_a_member_of_a_component_s_own_type_is_named_too(self, demo, cache) -> None:
        # A component may declare its own types inline, at `component.types[i]` rather than a
        # types file's `types[i]`; examples/demo's SensorHub nests DriverState_t inside the
        # struct it declares alongside its interface, so the member-use address has that prefix.
        # Measured, not guessed: the actual site is
        # `component.types[1].members[0].typename` in sensor_hub.ddd.json.
        uses = uses_of(demo, "DriverState_t", cache)
        assert [(use.kind, use.name, use.component, use.role) for use in uses] == [
            ("member", "SensorDiagnosis_t.driver", None, None)
        ]
        # The row's own count is read straight from the index and must agree with what this
        # lists, or the panel shows one place and lists none.
        rows = {row.name: row for row in type_rows(demo, (), cache)}
        assert rows["DriverState_t"].uses == len(uses)

    def test_a_name_no_type_holds_has_no_uses_and_states_nothing(self, built, cache) -> None:
        assert uses_of(built, "Nothing_t", cache) == ()
        assert fixed_by(built, "Nothing_t", cache) == {}
        assert members_of(built, "Nothing_t", cache) == ()
        assert kind_of(built, "Nothing_t", cache) == ""

    def test_a_type_s_kind_is_what_its_own_entry_says(self, built, cache) -> None:
        assert kind_of(built, "Temperature_t", cache) == "scalar"
        assert kind_of(built, "DriverStatus_t", cache) == "external"
        assert kind_of(built, "Sensor_t", cache) == "struct"

    def test_a_type_nothing_names_counts_no_uses(self, tmp_path, cache) -> None:
        # Its own project, because every type of examples/structures is named by something.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar_type("Spare_t", unit="rpm")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        assert [(row.name, row.uses) for row in type_rows(built, (), cache)] == [("Spare_t", 0)]

    def test_a_member_whose_own_name_has_drifted_is_not_a_use(self, tmp_path, cache) -> None:
        # A member whose `name` a later edit dropped and a structure whose `name` a later edit
        # dropped are two different drifts; this is the member's own, so it writes its json by
        # hand rather than asking a builder to omit a key it always fills in.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar_type("Leaf_t"),
                    struct_type("Holder_t", value_member("field", typename="Leaf_t")),
                ),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(
            tmp_path,
            {
                "types.ddd.json": types(
                    scalar_type("Leaf_t"),
                    {
                        "type": "struct",
                        "name": "Holder_t",
                        "members": [{"member": "value", "typename": "Leaf_t"}],
                    },
                )
            },
        )
        assert uses_of(built, "Leaf_t", cache) == ()

    def test_a_structure_whose_own_name_has_drifted_is_not_a_use(self, tmp_path, cache) -> None:
        # The structure's own drift, as distinct from the member's above.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar_type("Leaf_t"),
                    struct_type("Holder_t", value_member("field", typename="Leaf_t")),
                ),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(
            tmp_path,
            {
                "types.ddd.json": types(
                    scalar_type("Leaf_t"),
                    {"type": "struct", "members": [value_member("field", typename="Leaf_t")]},
                )
            },
        )
        assert uses_of(built, "Leaf_t", cache) == ()

    def test_a_declaration_whose_own_name_has_drifted_is_not_a_use(self, tmp_path, cache) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json", "c.ddd.json"),
                "types.ddd.json": types(scalar_type("Leaf_t")),
                "c.ddd.json": component("C", declare("output", "Var", typename="Leaf_t")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(
            tmp_path,
            {
                "c.ddd.json": {
                    "component": {
                        "name": "C",
                        "interface": [{"scope": "output", "definition": {"typename": "Leaf_t"}}],
                    }
                }
            },
        )
        assert uses_of(built, "Leaf_t", cache) == ()

    def test_a_declaration_renamed_since_is_not_a_use(self, tmp_path, cache) -> None:
        # The name at the recorded site now belongs to nobody the index ever declared, rather
        # than to nobody at all: a different drift than the declaration losing its name above.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json", "c.ddd.json"),
                "types.ddd.json": types(scalar_type("Leaf_t")),
                "c.ddd.json": component("C", declare("output", "Var", typename="Leaf_t")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(
            tmp_path,
            {"c.ddd.json": component("C", declare("output", "Renamed", typename="Leaf_t"))},
        )
        assert uses_of(built, "Leaf_t", cache) == ()


class TestWhatATypeStates:
    def test_a_scalar_states_its_datatype_unit_conversion_and_limits(self, built, cache) -> None:
        stated = fixed_by(built, "Temperature_t", cache)
        assert stated["datatype"] == '"uint16"'
        assert stated["unit"] == '"degC"'
        assert json.loads(stated["conversion"]) == {"factor": 0.1, "offset": -40}
        assert json.loads(stated["limits"]) == {"min": -40, "max": 150}

    def test_an_external_states_its_header_and_no_datatype(self, built, cache) -> None:
        stated = fixed_by(built, "DriverStatus_t", cache)
        assert stated["header"] == '"driver_status.h"'
        assert "datatype" not in stated

    def test_a_structure_states_only_its_description(self, built, cache) -> None:
        assert set(fixed_by(built, "Sample_t", cache)) == {"description"}

    def test_a_structure_s_members_are_listed_in_the_file_s_order(self, built, cache) -> None:
        members = members_of(built, "Sensor_t", cache)
        assert [member["name"] for member in members] == ["latest", "status", "driver", "history"]
        assert members[0]["typename"] == "Sample_t"
        assert members[3]["dimensions"] == ("8",)
        assert members_of(built, "Temperature_t", cache) == ()
