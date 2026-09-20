"""Where a project states each unit, and which entries of its vocabulary list it.

The navigation index's record of units is what renaming a unit reaches and what the Units tab of
``ddd gui`` counts, so each case here is a place a rename would otherwise leave holding the old
spelling, or a count the tab and the picker would otherwise disagree about.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, Site, UnitSite, index
from ddd.variables import units_in_use

UNIT = "component.interface[0].definition.unit"


def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project including every file given, as the language server builds it."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def at(tmp_path: Path, file: str, pointer: str) -> Site:
    """A site as the index records it, in the file the loader resolved."""
    return Site((tmp_path / file).resolve(), pointer)


class TestWhereAUnitIsStated:
    def test_every_declaration_stating_a_unit_is_recorded_as_its_variable(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert idx.units == {
            "rpm": [
                UnitSite(at(tmp_path, "a.ddd.json", UNIT), "variable", "Speed"),
                UnitSite(at(tmp_path, "b.ddd.json", UNIT), "variable", "Speed"),
            ]
        }

    @pytest.mark.parametrize(
        ("kind", "extra"),
        [
            ("measurement", {}),
            ("parameter", {}),
            ("value_block", {"dimensions": [4]}),
            ("axis", {"size": 4}),
            ("curve", {"axis": "Axis"}),
            ("map", {"x_axis": "Axis", "y_axis": "Axis"}),
        ],
    )
    def test_a_data_object_of_every_kind_states_its_unit(
        self, tmp_path: Path, kind: str, extra: dict[str, Any]
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Table", kind=kind, unit="Nm", **extra),
                    declare("output", "Axis", kind="axis", size=4, unit="rpm"),
                )
            },
        )
        assert idx.units["Nm"] == [UnitSite(at(tmp_path, "a.ddd.json", UNIT), "variable", "Table")]

    def test_a_scalar_type_states_its_unit_under_its_own_name(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"types.ddd.json": types(scalar_type("Speed_t", unit="rpm"))})
        assert idx.units == {
            "rpm": [UnitSite(at(tmp_path, "types.ddd.json", "types[0].unit"), "type", "Speed_t")]
        }

    def test_a_structure_member_states_its_unit_as_type_dot_member(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    struct_type("Sample_t", value_member("level"), value_member("rate", unit="Hz"))
                )
            },
        )
        assert idx.units == {
            "Hz": [
                UnitSite(
                    at(tmp_path, "types.ddd.json", "types[0].members[1].unit"),
                    "member",
                    "Sample_t.rate",
                )
            ]
        }

    def test_the_types_a_component_declares_inline_state_their_units_there(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Supply", typename="Volts_t"),
                    types=[
                        scalar_type("Volts_t", unit="V"),
                        struct_type("Frame_t", value_member("current", unit="A")),
                    ],
                )
            },
        )
        assert idx.units == {
            "A": [
                UnitSite(
                    at(tmp_path, "a.ddd.json", "component.types[1].members[0].unit"),
                    "member",
                    "Frame_t.current",
                )
            ],
            "V": [
                UnitSite(at(tmp_path, "a.ddd.json", "component.types[0].unit"), "type", "Volts_t")
            ],
        }

    def test_a_declaration_repeated_in_one_component_is_recorded_each_time(
        self, tmp_path: Path
    ) -> None:
        """``unknown-unit`` reads a repeat once; a rename has to rewrite both."""
        speed = declare("output", "Speed", unit="rpm")
        idx = built(tmp_path, **{"a.ddd.json": component("A", speed, speed)})
        assert [stated.site.pointer for stated in idx.units["rpm"]] == [
            UNIT,
            "component.interface[1].definition.unit",
        ]

    def test_the_empty_unit_is_no_unit_and_is_not_recorded(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    scalar_type("Ratio_t", unit=""),
                    struct_type("Pair_t", value_member("left", unit="")),
                ),
                "a.ddd.json": component(
                    "A", declare("output", "Plain", unit=""), declare("output", "Bare")
                ),
            },
        )
        assert idx.units == {}


class TestTheVocabulary:
    def test_both_forms_of_entry_are_recorded_at_the_entry(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{"units.ddd.json": {"units": ["rpm", {"unit": "Nm", "description": "torque"}]}},
        )
        assert idx.vocabulary == {
            "rpm": [at(tmp_path, "units.ddd.json", "units[0]")],
            "Nm": [at(tmp_path, "units.ddd.json", "units[1]")],
        }

    def test_a_unit_listed_twice_is_recorded_at_every_entry(self, tmp_path: Path) -> None:
        """The loader keeps the first of the two and reports the second as ``duplicate-unit``;
        a rename has to reach both, or the second still lists the spelling it renamed."""
        idx = built(
            tmp_path,
            **{
                "units.ddd.json": {"units": ["rpm", "Nm", {"unit": "rpm", "description": ""}]},
                "more.ddd.json": {"units": ["Nm"]},
            },
        )
        assert idx.vocabulary == {
            "rpm": [
                at(tmp_path, "units.ddd.json", "units[0]"),
                at(tmp_path, "units.ddd.json", "units[2]"),
            ],
            "Nm": [
                at(tmp_path, "units.ddd.json", "units[1]"),
                at(tmp_path, "more.ddd.json", "units[0]"),
            ],
        }

    def test_a_project_without_a_units_file_has_no_vocabulary(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "S", unit="rpm"))})
        assert idx.vocabulary == {}

    def test_a_listed_unit_nothing_states_is_in_the_vocabulary_alone(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"units.ddd.json": {"units": ["kPa"]}})
        assert (idx.units, list(idx.vocabulary)) == ({}, ["kPa"])


class TestTheUnitsInUse:
    def test_a_unit_only_types_and_members_state_is_used_by_no_variable(
        self, tmp_path: Path
    ) -> None:
        """The picker's count is of variables, as part 1 has it; a type's unit reaches no
        variable's count, not even that of a variable naming the type."""
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    scalar_type("Speed_t", unit="rpm"),
                    struct_type("Sample_t", value_member("rate", unit="Hz")),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", typename="Speed_t"),
                    declare("output", "Torque", unit="Nm"),
                ),
            },
        )
        assert units_in_use(idx) == (("Nm", 1),)

    def test_a_variable_two_components_declare_counts_once_under_each_spelling(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("output", "Idle", unit="RPM")),
            },
        )
        assert units_in_use(idx) == (("RPM", 1), ("rpm", 1))
