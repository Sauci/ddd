"""What changing a type takes, planned but never written."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.type_plans import TypeRefusalError, rename_type, set_key

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
        with pytest.raises(TypeRefusalError) as refused:
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
        with pytest.raises(TypeRefusalError) as refused:
            set_key(built, name, key, None, cache)
        assert refused.value.code == "invalid"
        assert key in str(refused.value)

    def test_a_name_no_type_holds_is_not_found(self, built, cache) -> None:
        with pytest.raises(TypeRefusalError) as refused:
            set_key(built, "Nothing_t", "unit", '"K"', cache)
        assert refused.value.code == "not-found"


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
        with pytest.raises(TypeRefusalError) as refused:
            rename_type(built, "Temperature_t", to, cache)
        assert refused.value.code == "invalid"
        assert says in str(refused.value)

    def test_a_name_no_type_holds_is_not_found(self, built, cache) -> None:
        with pytest.raises(TypeRefusalError) as refused:
            rename_type(built, "Nothing_t", "Reading_t", cache)
        assert refused.value.code == "not-found"
