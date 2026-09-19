"""What each change of a unit takes, file by file, and what refuses it.

The plans are the one rule behind the language server's Rename Symbol on a unit and its two
quick fixes, and behind the Units tab of ``ddd gui``, so each case here is a sentence about what
either of them may write. A plan is checked by what it does rather than by how it spells it: its
operations are made by the edit engine on the files as they stand, and the json they leave is
what is asserted.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    checks,
    component,
    declare,
    project,
    run_analysis,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.editing import edit_text
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.lsp.units import (
    ADOPTED,
    UnitPlan,
    UnitProject,
    UnitRefusalError,
    add_unit,
    adopt_units,
    describe_unit,
    remove_unit,
    rename_unit,
    unit_project,
)


def opened(
    tmp_path: Path, files: dict[str, Any], unread: Sequence[str] = ()
) -> tuple[Index, UnitProject]:
    """A project including the files given, in that order: its index as the language server
    builds it, and the project its plans are made in, with the files named in ``unread`` taken
    for files that did not load."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    described = unit_project(tmp_path / "p.ddd.json", [tmp_path / name for name in unread], {})
    return index(workspace), described


def drifted(vocabulary: list[Any] | None = None) -> dict[str, Any]:
    """A project whose speed drifted into two spellings - ``RPM`` on a declaration, a scalar type
    and a structure member, ``rpm`` on another variable - with ``%`` stated by a structure member
    alone, and, given one, a vocabulary."""
    files: dict[str, Any] = {
        "a.ddd.json": component(
            "A",
            declare("output", "Speed", "uint16", unit="RPM", limits={"min": 0, "max": 8000}),
            declare("output", "Torque", unit="Nm"),
        ),
        "b.ddd.json": component(
            "B",
            declare("input", "Speed", "uint16", unit="RPM"),
            declare("output", "Idle", unit="rpm"),
        ),
        "types.ddd.json": types(
            scalar_type("Speed_t", unit="RPM"),
            struct_type(
                "Sample_t", value_member("rate", unit="RPM"), value_member("level", unit="%")
            ),
        ),
    }
    return files if vocabulary is None else {"units.ddd.json": {"units": vocabulary}, **files}


def written(plan: UnitPlan) -> dict[Path, str]:
    """Every file the plan writes, as the text it leaves: a created file as the text it carries,
    any other as the edit engine leaves it after making its operations in order."""
    found: dict[Path, str] = {}
    for edit in plan.edits:
        if edit.creates:
            (made,) = edit.operations
            assert (made.op, made.pointer) == ("set", "")
            assert made.raw is not None
            found[edit.path] = made.raw
        else:
            found[edit.path] = edit_text(edit.path.read_text(encoding="utf-8"), edit.operations)
    return found


def after(plan: UnitPlan) -> dict[str, Any]:
    """Every file the plan writes, by name, as the json it leaves."""
    return {path.name: json.loads(text) for path, text in written(plan).items()}


def refusal(plan: Callable[[], UnitPlan]) -> tuple[str, str]:
    """The code and the message a plan is refused with."""
    with pytest.raises(UnitRefusalError) as refused:
        plan()
    return refused.value.code, refused.value.message


class TestTheProject:
    def test_its_units_files_are_those_it_includes_in_the_order_it_lists_them(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "late.ddd.json", "a.ddd.json", "early.ddd.json"),
                "late.ddd.json": {"units": ["rpm"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "early.ddd.json": {"units": ["Nm"]},
            },
        )
        found = unit_project(tmp_path / "p.ddd.json", (), {})
        assert found.project == (tmp_path / "p.ddd.json").resolve()
        assert found.units_files == (
            (tmp_path / "late.ddd.json").resolve(),
            (tmp_path / "early.ddd.json").resolve(),
        )

    def test_a_pattern_is_expanded_as_the_loader_expands_it_and_a_file_counts_once(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units/b.ddd.json", "units/*.ddd.json"),
                "units/b.ddd.json": {"units": ["rpm"]},
                "units/a.ddd.json": {"units": ["Nm"]},
                "units/c.ddd.json": component("C", declare("output", "Speed", unit="rpm")),
                "units/broken.ddd.json": '{"units": [',
            },
        )
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == (
            (tmp_path / "units" / "b.ddd.json").resolve(),
            (tmp_path / "units" / "a.ddd.json").resolve(),
        )

    def test_an_entry_the_loader_cannot_expand_names_no_units_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(self: Path, pattern: str) -> object:
            raise NotImplementedError("Non-relative patterns are unsupported")

        write_tree(
            tmp_path,
            {
                "p.ddd.json": {
                    "project": {"name": "P", "includes": [7, "*.ddd.json", "u.ddd.json"]}
                },
                "u.ddd.json": {"units": ["rpm"]},
            },
        )
        monkeypatch.setattr(Path, "glob", refuse)
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == (
            (tmp_path / "u.ddd.json").resolve(),
        )

    def test_a_description_including_nothing_has_no_units_file(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P"}}})
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == ()

    def test_the_files_that_did_not_load_are_sorted_and_named_once(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        b, a = tmp_path / "b.ddd.json", tmp_path / "a.ddd.json"
        assert unit_project(tmp_path / "p.ddd.json", [b, a, b], {}).unread == (
            a.resolve(),
            b.resolve(),
        )


class TestRename:
    def test_every_place_the_unit_is_stated_takes_the_new_spelling_and_nothing_else_changes(
        self, tmp_path: Path
    ) -> None:
        files = drifted()
        idx, where = opened(tmp_path, files)
        plan = rename_unit(idx, where, "RPM", "1/min", {})
        files["a.ddd.json"]["component"]["interface"][0]["definition"]["unit"] = "1/min"
        files["b.ddd.json"]["component"]["interface"][0]["definition"]["unit"] = "1/min"
        files["types.ddd.json"]["types"][0]["unit"] = "1/min"
        files["types.ddd.json"]["types"][1]["members"][0]["unit"] = "1/min"
        assert [edit.path.name for edit in plan.edits] == [
            "a.ddd.json",
            "b.ddd.json",
            "types.ddd.json",
        ]
        assert after(plan) == {
            name: files[name] for name in ("a.ddd.json", "b.ddd.json", "types.ddd.json")
        }

    def test_a_spelling_only_the_vocabulary_lists_is_renamed_there(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "kPa"]))
        assert after(rename_unit(idx, where, "kPa", "hPa", {})) == {
            "units.ddd.json": {"units": ["rpm", "hPa"]}
        }

    def test_an_entry_is_renamed_in_the_form_it_takes_and_keeps_its_description(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        plain = after(rename_unit(idx, where, "rpm", "1/min", {}))
        described = after(rename_unit(idx, where, "Nm", "N.m", {}))
        assert plain["units.ddd.json"] == {
            "units": ["1/min", {"unit": "Nm", "description": "torque"}]
        }
        assert described["units.ddd.json"] == {
            "units": ["rpm", {"unit": "N.m", "description": "torque"}]
        }

    def test_renaming_onto_a_listed_spelling_merges_and_takes_the_old_entry_out(
        self, tmp_path: Path
    ) -> None:
        vocabulary = [
            {"unit": "rpm", "description": "revolutions per minute"},
            {"unit": "RPM", "description": "the same, shouted"},
            "Nm",
        ]
        idx, where = opened(tmp_path, drifted(vocabulary))
        found = after(rename_unit(idx, where, "RPM", "rpm", {}))
        assert found["units.ddd.json"] == {
            "units": [{"unit": "rpm", "description": "revolutions per minute"}, "Nm"]
        }
        assert found["types.ddd.json"]["types"][1]["members"][0]["unit"] == "rpm"

    def test_a_unit_listed_twice_has_both_entries_renamed(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["RPM", "Nm", {"unit": "RPM", "description": ""}]))
        assert after(rename_unit(idx, where, "RPM", "1/min", {}))["units.ddd.json"] == {
            "units": ["1/min", "Nm", {"unit": "1/min", "description": ""}]
        }

    def test_a_spelling_outside_ascii_is_written_as_it_is_spelled(self, tmp_path: Path) -> None:
        idx, where = opened(
            tmp_path, {"t.ddd.json": component("T", declare("output", "T", unit="C"))}
        )
        (text,) = written(rename_unit(idx, where, "C", "°C", {})).values()
        assert '"unit": "°C"' in text

    def test_a_merge_takes_every_entry_of_a_unit_listed_twice_out_in_every_file(
        self, tmp_path: Path
    ) -> None:
        files = {"more.ddd.json": {"units": ["RPM", "kPa"]}, **drifted(["RPM", "rpm", "Nm", "RPM"])}
        idx, where = opened(tmp_path, files)
        found = after(rename_unit(idx, where, "RPM", "rpm", {}))
        assert found["units.ddd.json"] == {"units": ["rpm", "Nm"]}
        assert found["more.ddd.json"] == {"units": ["kPa"]}

    def test_a_merge_that_would_leave_a_units_file_listing_nothing_is_invalid(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, {"shouted.ddd.json": {"units": ["RPM"]}, **drifted(["rpm"])})
        code, message = refusal(lambda: rename_unit(idx, where, "RPM", "rpm", {}))
        assert code == "invalid"
        assert "shouted.ddd.json" in message

    @pytest.mark.parametrize("new", ["", " rpm", "rpm\t", "RPM"])
    def test_a_new_name_that_is_empty_has_spaces_around_it_or_is_the_old_one_is_invalid(
        self, tmp_path: Path, new: str
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        assert refusal(lambda: rename_unit(idx, where, "RPM", new, {}))[0] == "invalid"

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: rename_unit(idx, where, "Hz", "1/s", {}))[0] == "not-found"

    def test_while_any_file_of_the_project_does_not_load_a_rename_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        files = {**drifted(), "broken.ddd.json": '{"component": '}
        idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
        code, message = refusal(lambda: rename_unit(idx, where, "RPM", "rpm", {}))
        assert code == "unreadable"
        assert "broken.ddd.json" in message


class TestAdd:
    def test_a_unit_is_appended_as_a_spelling_where_every_entry_is_one(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "Nm"]))
        assert after(add_unit(idx, where, "RPM", {})) == {
            "units.ddd.json": {"units": ["rpm", "Nm", "RPM"]}
        }

    def test_a_unit_is_appended_as_an_object_where_an_entry_is_one(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        assert after(add_unit(idx, where, "RPM", {})) == {
            "units.ddd.json": {
                "units": [
                    "rpm",
                    {"unit": "Nm", "description": "torque"},
                    {"unit": "RPM", "description": ""},
                ]
            }
        }

    def test_a_unit_goes_into_the_first_units_file_the_includes_list(self, tmp_path: Path) -> None:
        files = {"first.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])}
        idx, where = opened(tmp_path, files)
        assert after(add_unit(idx, where, "Hz", {})) == {"first.ddd.json": {"units": ["kPa", "Hz"]}}

    @pytest.mark.parametrize("unit", ["", "RPM "])
    def test_a_spelling_no_unit_is_written_with_is_invalid(self, tmp_path: Path, unit: str) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: add_unit(idx, where, unit, {}))[0] == "invalid"

    def test_a_project_without_a_units_file_has_nowhere_to_add_one(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted())
        assert refusal(lambda: add_unit(idx, where, "RPM", {})) == (
            "invalid",
            "p.ddd.json includes no units file to add 'RPM' to",
        )

    def test_a_unit_the_vocabulary_lists_already_is_invalid(self, tmp_path: Path) -> None:
        files = {"first.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])}
        idx, where = opened(tmp_path, files)
        code, message = refusal(lambda: add_unit(idx, where, "rpm", {}))
        assert code == "invalid"
        assert "units.ddd.json" in message

    def test_while_the_units_file_does_not_load_an_addition_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: add_unit(idx, where, "RPM", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message


class TestDescribe:
    def test_an_entry_that_is_a_spelling_alone_becomes_an_object_holding_the_description(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        assert after(describe_unit(idx, where, "rpm", "revolutions per minute", {})) == {
            "units.ddd.json": {
                "units": [
                    {"unit": "rpm", "description": "revolutions per minute"},
                    {"unit": "Nm", "description": "torque"},
                ]
            }
        }

    def test_an_object_has_its_description_set_or_added(self, tmp_path: Path) -> None:
        vocabulary = [{"unit": "rpm"}, {"unit": "Nm", "description": "torque"}]
        idx, where = opened(tmp_path, drifted(vocabulary))
        added = after(describe_unit(idx, where, "rpm", "speed", {}))
        replaced = after(describe_unit(idx, where, "Nm", "torque, newton metre", {}))
        assert added["units.ddd.json"]["units"][0] == {"unit": "rpm", "description": "speed"}
        assert replaced["units.ddd.json"]["units"][1] == {
            "unit": "Nm",
            "description": "torque, newton metre",
        }

    def test_a_unit_listed_twice_has_both_entries_described(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "rpm", "description": "old"}]))
        assert after(describe_unit(idx, where, "rpm", "speed", {})) == {
            "units.ddd.json": {
                "units": [
                    {"unit": "rpm", "description": "speed"},
                    {"unit": "rpm", "description": "speed"},
                ]
            }
        }

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: describe_unit(idx, where, "Hz", "frequency", {}))[0] == "not-found"

    def test_a_unit_stated_outside_the_vocabulary_has_no_description_to_set(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: describe_unit(idx, where, "RPM", "shouted", {}))[0] == "invalid"

    def test_while_the_units_file_listing_it_does_not_load_a_description_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: describe_unit(idx, where, "rpm", "speed", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message

    def test_a_unit_no_loaded_entry_lists_is_unreadable_while_a_units_file_does_not_load(
        self, tmp_path: Path
    ) -> None:
        """The file that did not load may be the one listing it: saying it is not in the
        vocabulary would be a guess."""
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        assert refusal(lambda: describe_unit(idx, where, "RPM", "shouted", {}))[0] == "unreadable"


class TestRemove:
    def test_a_unit_nothing_states_is_taken_out_in_either_form(self, tmp_path: Path) -> None:
        vocabulary = ["rpm", "kPa", {"unit": "degC", "description": "temperature"}, "Nm"]
        idx, where = opened(tmp_path, drifted(vocabulary))
        assert after(remove_unit(idx, where, "kPa", {})) == {
            "units.ddd.json": {
                "units": ["rpm", {"unit": "degC", "description": "temperature"}, "Nm"]
            }
        }
        assert after(remove_unit(idx, where, "degC", {})) == {
            "units.ddd.json": {"units": ["rpm", "kPa", "Nm"]}
        }

    def test_a_unit_listed_twice_has_every_entry_taken_out(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["kPa", "rpm", {"unit": "kPa", "description": ""}]))
        assert after(remove_unit(idx, where, "kPa", {})) == {"units.ddd.json": {"units": ["rpm"]}}

    def test_a_unit_something_still_states_is_invalid(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "Nm"]))
        assert refusal(lambda: remove_unit(idx, where, "rpm", {})) == (
            "invalid",
            "'rpm' is still stated in 1 place; only a unit nothing states is taken out of the "
            "vocabulary",
        )
        assert refusal(lambda: remove_unit(idx, where, "RPM", {}))[1].startswith(
            "'RPM' is still stated in 4 places"
        )

    def test_a_unit_no_entry_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: remove_unit(idx, where, "Hz", {}))[0] == "not-found"

    def test_the_last_unit_a_units_file_lists_is_not_taken_out(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, {"more.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])})
        assert refusal(lambda: remove_unit(idx, where, "kPa", {})) == (
            "invalid",
            "'kPa' is all more.ddd.json lists, and a units file lists at least one unit",
        )

    def test_while_the_units_file_listing_it_does_not_load_a_removal_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "kPa"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: remove_unit(idx, where, "kPa", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message


class TestAdopt:
    def test_every_unit_in_use_is_listed_alphabetically_and_the_file_included(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        plan = adopt_units(idx, where, {})
        listing = {
            "units": [
                {"unit": "%", "description": ""},
                {"unit": "Nm", "description": ""},
                {"unit": "RPM", "description": ""},
                {"unit": "rpm", "description": ""},
            ]
        }
        assert [(edit.path, edit.creates) for edit in plan.edits] == [
            ((tmp_path / "p.ddd.json").resolve(), False),
            ((tmp_path / ADOPTED).resolve(), True),
        ]
        assert plan.edits[1].operations[0].raw == (
            "{\n"
            '  "units": [\n'
            '    { "unit": "%", "description": "" },\n'
            '    { "unit": "Nm", "description": "" },\n'
            '    { "unit": "RPM", "description": "" },\n'
            '    { "unit": "rpm", "description": "" }\n'
            "  ]\n"
            "}\n"
        )
        assert after(plan) == {
            "p.ddd.json": project(
                "P", "a.ddd.json", "b.ddd.json", "types.ddd.json", "units.ddd.json"
            ),
            "units.ddd.json": listing,
        }

    def test_after_adopting_nothing_is_reported_that_was_not_reported_before(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        _, before = run_analysis(tmp_path, {}, root="p.ddd.json")
        for path, text in written(adopt_units(idx, where, {})).items():
            path.write_text(text, encoding="utf-8")
        _, adopted = run_analysis(tmp_path, {}, root="p.ddd.json")
        assert checks(adopted) == checks(before)

    def test_a_project_with_a_units_file_has_a_vocabulary_already(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: adopt_units(idx, where, {})) == (
            "invalid",
            "this project has a vocabulary already: units.ddd.json",
        )

    def test_a_units_file_a_sub_project_includes_is_a_vocabulary_already(
        self, tmp_path: Path
    ) -> None:
        files = {"sub.ddd.json": project("Sub", "rates.ddd.json"), **drifted()}
        write_tree(tmp_path, {"rates.ddd.json": {"units": ["Hz"]}})
        idx, where = opened(tmp_path, files)
        assert refusal(lambda: adopt_units(idx, where, {}))[1].endswith("rates.ddd.json")

    def test_a_project_stating_no_unit_has_nothing_to_adopt(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, {"a.ddd.json": component("A", declare("output", "Flag"))})
        assert refusal(lambda: adopt_units(idx, where, {}))[0] == "invalid"

    @pytest.mark.parametrize("existing", [{"notes": "not a units file"}, {"units": ["rpm"]}])
    def test_a_file_where_the_vocabulary_would_go_is_never_written_over(
        self, tmp_path: Path, existing: dict[str, Any]
    ) -> None:
        files = drifted()
        write_tree(tmp_path, {ADOPTED: existing})
        idx, where = opened(tmp_path, files)
        code, message = refusal(lambda: adopt_units(idx, where, {}))
        assert code == "invalid"
        assert ADOPTED in message

    def test_while_any_file_of_the_project_does_not_load_adopting_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        files = {**drifted(), "broken.ddd.json": '{"component": '}
        idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
        code, message = refusal(lambda: adopt_units(idx, where, {}))
        assert code == "unreadable"
        assert "broken.ddd.json" in message


@pytest.mark.parametrize(
    "plan",
    [
        lambda idx, where: add_unit(idx, where, "Hz", {}),
        lambda idx, where: describe_unit(idx, where, "rpm", "speed", {}),
        lambda idx, where: remove_unit(idx, where, "kPa", {}),
    ],
)
def test_a_component_that_does_not_load_stops_no_change_to_the_vocabulary(
    tmp_path: Path, plan: Callable[[Index, UnitProject], UnitPlan]
) -> None:
    """Only the units file matters to these: a component that did not load may state units, and
    no entry of the vocabulary changes with what it states."""
    files = {**drifted(["rpm", "kPa"]), "broken.ddd.json": '{"component": '}
    idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
    assert list(after(plan(idx, where))) == ["units.ddd.json"]


@pytest.mark.parametrize(
    "plan",
    [
        lambda idx, where, cache: rename_unit(idx, where, "RPM", "rpm", cache),
        lambda idx, where, cache: add_unit(idx, where, "Hz", cache),
        lambda idx, where, cache: describe_unit(idx, where, "rpm", "speed", cache),
        lambda idx, where, cache: remove_unit(idx, where, "kPa", cache),
        lambda idx, where, cache: adopt_units(idx, where, cache),
    ],
)
def test_a_refused_plan_has_read_no_file(
    tmp_path: Path, plan: Callable[[Index, UnitProject, dict[Path, Document]], UnitPlan]
) -> None:
    """Every refusal is made from the index and the project alone, before a file is read."""
    idx, where = opened(tmp_path, drifted(["rpm", "kPa"]), unread=["units.ddd.json"])
    cache: dict[Path, Document] = {}
    with pytest.raises(UnitRefusalError):
        plan(idx, where, cache)
    assert cache == {}
