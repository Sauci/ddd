"""What changing a type takes, planned but never written."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document, read
from ddd.plans import Plan, PlanRefusalError
from ddd.type_plans import rename_type, set_key

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def built() -> Index:
    return index(load_workspace(EXAMPLES / "structures" / "project.ddd.json", DiagnosticBag()))


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


class TestSettingAKey:
    def test_a_scalar_s_unit_is_one_set_at_its_own_pointer(self, built, cache) -> None:
        plan = set_key(built, "Temperature_t", "unit", '"K"', cache)
        (edit,) = plan.edits
        assert edit.path.name == "types.ddd.json"
        assert [(o.op, o.pointer, o.raw) for o in edit.operations] == [
            ("set", "types[0].unit", '"K"')
        ]

    def test_a_key_left_out_is_removed(self, built, cache) -> None:
        plan = set_key(built, "Temperature_t", "limits", None, cache)
        (edit,) = plan.edits
        assert [(o.op, o.pointer) for o in edit.operations] == [("remove", "types[0].limits")]

    def test_a_key_the_entry_does_not_carry_is_an_empty_plan(self, tmp_path, cache) -> None:
        # examples/structures offers no fixture for this: its one scalar, Temperature_t, has
        # every optional key - description, unit, limits - already filled in, so a key genuinely
        # missing from an entry needs a project built for it, measured rather than assumed.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar_type("Spare_t")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        assert set_key(built, "Spare_t", "limits", None, cache) == Plan(())

    @pytest.mark.parametrize(
        ("name", "key"),
        [
            ("Sample_t", "datatype"),  # a structure has none
            ("Sample_t", "unit"),
            ("DriverStatus_t", "datatype"),  # nor has an external
            ("Temperature_t", "header"),  # nor has a scalar a header
            ("Temperature_t", "members"),  # nor is anything else settable
        ],
    )
    def test_a_key_the_kind_does_not_have_is_refused(self, built, cache, name, key) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, name, key, '"x"', cache)
        assert refused.value.code == "invalid"

    @pytest.mark.parametrize(
        ("name", "key"),
        [
            ("Temperature_t", "datatype"),
            ("Temperature_t", "conversion"),
            ("DriverStatus_t", "header"),
        ],
    )
    def test_a_required_key_may_not_be_left_out(self, built, cache, name, key) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, name, key, None, cache)
        assert refused.value.code == "invalid"
        assert key in str(refused.value)

    def test_a_name_no_type_holds_is_not_found(self, built, cache) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, "Nothing_t", "unit", '"K"', cache)
        assert refused.value.code == "not-found"

    @pytest.mark.parametrize(
        ("key", "raw", "says"),
        [
            (
                "datatype",
                '"uint7"',
                "Input should be 'boolean', 'uint8', 'sint8', 'uint16', 'sint16', 'uint32', "
                "'sint32', 'uint64', 'sint64', 'float32' or 'float64'",
            ),
            ("limits", '{"min": 10, "max": 1}', "min (10) is greater than max (1)"),
            ("conversion", '{"kind": "linear", "factor": 0}', "factor must not be zero"),
        ],
        ids=["a-datatype-that-is-none", "an-empty-range", "a-conversion-of-factor-0"],
    )
    def test_a_value_the_entry_would_not_load_with_is_refused_in_the_models_words(
        self, built, cache, key, raw, says
    ) -> None:
        """3:I1. Planned and applied, each of these left a types file the loader refuses, and every
        type it declares went with it: the entry as the plan would leave it is asked of the models
        (``type_problem``), as a variable's settlement asks them of a definition."""
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, "Temperature_t", key, raw, cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            f"the type 'Temperature_t' in types.ddd.json would not load with that {key}: {says}",
        )

    def test_a_conversion_whose_derived_limits_are_not_finite_is_refused(
        self, tmp_path, cache
    ) -> None:
        """What the analysis files as ``schema`` of a scalar type alone, the models having taken
        it: a double scaled by two runs past the largest float."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar_type("Wide_t", "float64")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, "Wide_t", "conversion", '{"kind": "linear", "factor": 2}', cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "the type 'Wide_t' in types.ddd.json would not load with that conversion: the limits "
            "derived from 'float64' and this conversion are not finite",
        )
        assert set_key(built, "Wide_t", "conversion", '{"factor": 0.5}', cache).edits

    def test_a_key_taken_out_is_asked_of_the_entry_without_it(self, tmp_path, cache) -> None:
        """The entry as the change leaves it: a range its file has come to hold since the analysis,
        with the maximum below the minimum, is taken out - which mends the entry - rather than
        refused for the very range the change removes."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar_type("Spare_t", limits={"min": 0, "max": 5})),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        emptied = types(scalar_type("Spare_t", limits={"min": 5, "max": 0}))
        write_tree(tmp_path, {"types.ddd.json": emptied})
        (edit,) = set_key(built, "Spare_t", "limits", None, cache).edits
        assert [(o.op, o.pointer) for o in edit.operations] == [("remove", "types[0].limits")]

    def test_a_value_the_loader_would_not_read_as_json_is_refused_in_its_words(
        self, built, cache
    ) -> None:
        """Json the loader refuses - a key written twice - is said as the loader says it, as a
        variable's settlement says it (``loading_problem``), and never raised."""
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, "Temperature_t", "limits", '{"min": 0, "min": 1, "max": 5}', cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "the type 'Temperature_t' in types.ddd.json would not load with that limits: key "
            "'min' appears twice in one object; json would silently keep the last spelling, so "
            "decide which one stays",
        )

    def test_a_type_its_file_no_longer_holds_where_the_index_found_it_is_stale(
        self, tmp_path, cache
    ) -> None:
        """A type put in at the top of the file after the index was built: where the index
        recorded ``B_t``, the file holds ``A_t``, whose key the plan would set - and whose kind
        would decide which keys may be set at all."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar_type("A_t", unit="rpm"), scalar_type("B_t", unit="Nm")
                ),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        moved = types(
            scalar_type("X_t", unit="V"),
            scalar_type("A_t", unit="rpm"),
            scalar_type("B_t", unit="Nm"),
        )
        write_tree(tmp_path, {"types.ddd.json": moved})
        with pytest.raises(PlanRefusalError) as refused:
            set_key(built, "B_t", "unit", '"K"', cache)
        assert (refused.value.code, refused.value.message) == (
            "stale",
            "types.ddd.json changed since the project was analysed, so 'B_t' cannot be changed "
            "until the project is analysed again",
        )


class TestATypeTheAnalysisRefusesAlready:
    """A scalar type whose derived limits run past the largest float - a ``float64`` doubled -
    loads, and the analysis refuses it, at its conversion. Every key set on it was refused all the
    same, its sentence blaming whichever key the reader chose; and the Types tab asks a plan of a
    row's own value the moment the row is selected. A change is refused where it brings the entry
    a refusal it did not carry: one leaving the entry's own as it was is planned, and so is one
    mending it."""

    TYPE_IN_FILE = "types[0]"

    @pytest.fixture
    def wide(self, tmp_path: Path) -> Index:
        doubled = {"kind": "linear", "factor": 2}
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar_type("Wide_t", "float64", unit="rpm", conversion=doubled)
                ),
            },
        )
        return index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))

    @pytest.mark.parametrize(
        ("key", "raw"),
        [
            ("unit", '"Nm"'),
            ("description", '"doubled"'),
            ("limits", '{"min": 0, "max": 1}'),
            ("conversion", '{"kind": "linear", "factor": 0.5}'),
        ],
        ids=["its-unit", "its-description", "its-limits", "a-conversion-mending-it"],
    )
    def test_a_change_that_brings_no_refusal_of_its_own_is_planned(
        self, wide, cache, key, raw
    ) -> None:
        (edit,) = set_key(wide, "Wide_t", key, raw, cache).edits
        assert [(o.op, o.pointer, o.raw) for o in edit.operations] == [
            ("set", f"{self.TYPE_IN_FILE}.{key}", raw)
        ]

    @pytest.mark.parametrize("key", ["unit", "conversion"])
    def test_a_row_s_own_value_merely_asked_is_planned(self, wide, cache, tmp_path, key) -> None:
        """What the Types tab asks the moment a row is selected, the conversion's among them:
        the value the file holds, which leaves the entry's refusal as it was."""
        own = read(tmp_path / "types.ddd.json", {}).raw_at(f"{self.TYPE_IN_FILE}.{key}")
        assert own is not None
        assert set_key(wide, "Wide_t", key, own, cache).edits

    def test_a_datatype_bringing_a_refusal_of_its_own_is_refused_naming_it(
        self, wide, cache
    ) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            set_key(wide, "Wide_t", "datatype", '"uint7"', cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "the type 'Wide_t' in types.ddd.json would not load with that datatype: Input should "
            "be 'boolean', 'uint8', 'sint8', 'uint16', 'sint16', 'uint32', 'sint32', 'uint64', "
            "'sint64', 'float32' or 'float64'",
        )


class TestRenaming:
    def test_the_type_and_every_name_reaching_it_are_rewritten(self, built, cache) -> None:
        plan = rename_type(built, "Temperature_t", "Reading_t", cache)
        (edit,) = plan.edits
        assert edit.path.name == "types.ddd.json"
        # Its own name first, then every member nesting it, as the index recorded them.
        assert [(o.op, o.pointer, o.raw) for o in edit.operations] == [
            ("set", "types[0].name", '"Reading_t"'),
            ("set", "types[2].members[0].typename", '"Reading_t"'),
            ("set", "types[5].members[0].typename", '"Reading_t"'),
            ("set", "types[4].members[3].typename", '"Reading_t"'),
        ]

    def test_a_rename_reaching_three_files_is_one_edit_per_file_sorted_by_path(self, built, cache):
        plan = rename_type(built, "Sensor_t", "Probe_t", cache)
        assert [edit.path.name for edit in plan.edits] == [
            "monitoring.ddd.json",
            "sensing.ddd.json",
            "types.ddd.json",
        ]
        assert [o.pointer for edit in plan.edits for o in edit.operations] == [
            "component.interface[0].definition.typename",
            "component.interface[1].definition.typename",
            "types[4].name",
        ]

    @pytest.mark.parametrize(
        ("to", "says"),
        [
            ("Sample_t", "shares c's namespace"),
            ("uint16", "spells a base datatype"),
            ("Inlet", "already declared by this project"),
            ("9bad", "not a usable c identifier"),
            ("int", "reserved by c"),
            ("T" * 129, "not a usable c identifier"),
        ],
    )
    def test_a_name_that_may_not_be_used_is_refused_in_the_editor_s_own_words(
        self, built, cache, to, says
    ) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            rename_type(built, "Temperature_t", to, cache)
        assert refused.value.code == "invalid"
        assert says in str(refused.value)

    def test_a_name_no_type_holds_is_not_found(self, built, cache) -> None:
        with pytest.raises(PlanRefusalError) as refused:
            rename_type(built, "Nothing_t", "Reading_t", cache)
        assert refused.value.code == "not-found"

    @pytest.mark.parametrize("to", ["DriverState_t", "Sample_t"], ids=["free", "taken"])
    def test_an_external_type_is_refused_in_the_editor_s_own_words(self, built, cache, to) -> None:
        """10:M9. The header beside an external type defines its name, which no plan of the
        descriptions reaches: the page renamed it through the editor's ``rename_sites`` and left
        the header defining the old name. Refused in the sentence the editor's ``F2`` refuses it
        with (``tests/test_lsp.py``), so the two clients cannot disagree about it - and whatever
        it would be renamed onto, since no new name would do."""
        with pytest.raises(PlanRefusalError) as refused:
            rename_type(built, "DriverStatus_t", to, cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "'DriverStatus_t' is an external type whose name driver_status.h defines, so a rename "
            "here would leave that header defining the old one",
        )

    def test_a_type_its_file_no_longer_holds_where_the_index_found_it_is_stale(
        self, tmp_path, cache
    ) -> None:
        """A type put in at the top of the file after the index was built: renamed at the place
        the index recorded, the type now sitting there would take the new name instead."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar_type("A_t"), scalar_type("B_t")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        moved = types(scalar_type("X_t"), scalar_type("A_t"), scalar_type("B_t"))
        write_tree(tmp_path, {"types.ddd.json": moved})
        with pytest.raises(PlanRefusalError) as refused:
            rename_type(built, "B_t", "C_t", cache)
        assert (refused.value.code, refused.value.message) == (
            "stale",
            "types.ddd.json changed since the project was analysed, so renaming 'B_t' cannot be "
            "planned until the project is analysed again",
        )

    def test_a_declaration_naming_the_type_moved_since_is_stale_as_well(
        self, tmp_path, cache
    ) -> None:
        """The type's own entry where it was, and a component naming it given a declaration
        above: every place the rename writes is asked, the declaration's ``typename`` too."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar_type("A_t")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="A_t")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        moved = component(
            "A", declare("output", "Other"), declare("output", "Speed", typename="A_t")
        )
        write_tree(tmp_path, {"a.ddd.json": moved})
        with pytest.raises(PlanRefusalError) as refused:
            rename_type(built, "A_t", "C_t", cache)
        assert (refused.value.code, refused.value.message) == (
            "stale",
            "a.ddd.json changed since the project was analysed, so renaming 'A_t' cannot be "
            "planned until the project is analysed again",
        )
