"""Tests for point counts stored ahead of a curve, a map or an axis.

Some firmware stores the number of axis points inside every interpolation object, ahead of
its data, in the object's own type: the routines read the counts to learn the table's shape.
A project states that once, a component may state otherwise for what it defines, and both
backends then agree on where the data starts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.backends.c.model import build_code_model
from ddd.backends.c.options import COptions
from ddd.compare import compare
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.ir import DataDictionary, ResolvedObject
from ddd.loading import load_dictionary, load_workspace
from ddd.models import ComponentFile, ObjectKind, PointCounts, ProjectFile, stored_counts


def axis(
    name: str = "AX", size: int | str = 4, datatype: str = "uint16", **extra: Any
) -> dict[str, Any]:
    return declare("local", name, datatype, kind="axis", size=size, **extra)


def curve(
    name: str = "C", over: str = "AX", datatype: str = "uint16", **extra: Any
) -> dict[str, Any]:
    return declare("local", name, datatype, kind="curve", axis=over, **extra)


def table(
    name: str = "M", x: str = "AX", y: str = "AY", datatype: str = "uint16", **extra: Any
) -> dict[str, Any]:
    return declare("local", name, datatype, kind="map", x_axis=x, y_axis=y, **extra)


class TestTheDescription:
    def test_a_project_states_the_key(self) -> None:
        model = ProjectFile.model_validate(project("P", point_counts="leading"))
        assert model.project.point_counts is PointCounts.LEADING

    def test_a_component_states_the_key(self) -> None:
        model = ComponentFile.model_validate(component("A", point_counts="none"))
        assert model.component.point_counts is PointCounts.NONE

    def test_the_key_is_optional_on_both(self) -> None:
        assert ProjectFile.model_validate(project("P")).project.point_counts is None
        assert ComponentFile.model_validate(component("A")).component.point_counts is None

    def test_an_unknown_value_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ProjectFile.model_validate(project("P", point_counts="trailing"))


class TestTheProjectDefault:
    def test_an_unstated_default_is_none(self, tree: Path) -> None:
        write_tree(
            tree, {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")}
        )
        workspace = load_workspace(tree / "project.ddd.json", DiagnosticBag())
        assert workspace is not None
        assert workspace.point_counts is PointCounts.NONE

    def test_a_sub_project_may_state_the_default(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="leading"),
                "a.ddd.json": component("A"),
            },
        )
        workspace = load_workspace(tree / "project.ddd.json", DiagnosticBag())
        assert workspace is not None
        assert workspace.point_counts is PointCounts.LEADING

    def test_a_second_file_stating_another_value_is_refused(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json", point_counts="leading"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="none"),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert "point_counts is already stated as 'leading'" in messages(bag)

    def test_a_second_file_stating_the_same_value_is_accepted(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json", point_counts="leading"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="leading"),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None, messages(bag)
        assert checks(bag) == []
        assert workspace.point_counts is PointCounts.LEADING


class TestTheStoredCounts:
    @pytest.mark.parametrize(
        ("kind", "shape", "counts"),
        [
            (ObjectKind.AXIS, (8,), (8,)),
            (ObjectKind.CURVE, (8,), (8,)),
            (ObjectKind.MAP, (11, 8), (8, 11)),
            (ObjectKind.MAP, ("NY", "NX"), ("NX", "NY")),
            (ObjectKind.VALUE_BLOCK, (4,), ()),
            (ObjectKind.PARAMETER, (), ()),
        ],
    )
    def test_x_comes_first(
        self, kind: ObjectKind, shape: tuple[Any, ...], counts: tuple[Any, ...]
    ) -> None:
        """A map is declared ``[y][x]`` and stores x then y: an 8 by 11 map begins ``8, 11``."""
        assert stored_counts(kind, shape) == counts


def files(
    *declarations: dict[str, Any], default: str | None = None, **extra: Any
) -> dict[str, Any]:
    stated = {"point_counts": default} if default is not None else {}
    return {
        "project.ddd.json": project("P", "a.ddd.json", **stated),
        "a.ddd.json": component("A", *declarations, **extra),
    }


def resolved(dictionary: DataDictionary, name: str) -> ResolvedObject:
    return next(entry for entry in dictionary.objects if entry.name == name)


TABLES = (axis("AX", 8), axis("AY", 11), curve("C"), table("M"))


class TestTheResolution:
    def test_the_project_default_reaches_every_table(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        for name in ("AX", "AY", "C", "M"):
            assert resolved(dictionary, name).point_counts is PointCounts.LEADING

    def test_nothing_stated_is_none(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES))
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "M").point_counts is PointCounts.NONE

    @pytest.mark.parametrize(("default", "override"), [("leading", "none"), ("none", "leading")])
    def test_a_component_overrides_the_default(
        self, tree: Path, default: str, override: str
    ) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default=default, point_counts=override))
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "M").point_counts is PointCounts(override)

    def test_it_reaches_no_other_kind(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            files(
                declare("local", "X"),
                declare("local", "K", kind="parameter", init=1),
                default="leading",
            ),
        )
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "X").point_counts is PointCounts.NONE
        assert resolved(dictionary, "K").point_counts is PointCounts.NONE

    def test_a_readers_setting_does_not_reach_what_it_reads(self, tree: Path) -> None:
        """It follows the producer. The reader is included first so that an implementation
        reading the first declaration instead of the producing one would get it wrong."""
        tree_files = {
            "project.ddd.json": project("P", "b.ddd.json", "a.ddd.json"),
            "b.ddd.json": component(
                "B", declare("input", "AX", "uint16", kind="axis", size=8), point_counts="leading"
            ),
            "a.ddd.json": component("A", declare("output", "AX", "uint16", kind="axis", size=8)),
        }
        dictionary, bag = run_analysis(tree, tree_files)
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "AX").point_counts is PointCounts.NONE

    def test_a_format_8_dictionary_reads_back_as_none(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        dumped = dictionary.model_dump(mode="json")
        dumped["format"] = 8
        for entry in dumped["objects"]:
            del entry["point_counts"]
        target = tree / "old.json"
        target.write_text(json.dumps(dumped), encoding="utf-8")
        again = load_dictionary(target, DiagnosticBag())
        assert again is not None
        assert {entry.point_counts for entry in again.objects} == {PointCounts.NONE}


class TestTheFindings:
    def test_a_boolean_table_cannot_hold_a_count(self, tree: Path) -> None:
        _, bag = run_analysis(tree, files(axis("AX", 2, "boolean"), default="leading"))
        assert bag.has_errors
        assert checks(bag) == ["point-counts-unrepresentable"]
        assert "'AX' stores its point count 2 as boolean" in messages(bag)

    def test_the_widest_count_a_type_holds_is_accepted(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 255, "uint8"), default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_one_more_is_refused(self, tree: Path) -> None:
        _, bag = run_analysis(tree, files(axis("AX", 256, "uint8"), default="leading"))
        assert bag.has_errors
        assert checks(bag) == ["point-counts-unrepresentable"]

    def test_a_map_is_checked_on_both_counts(self, tree: Path) -> None:
        """The y count is the one that overflows here, which a check of x alone would miss."""
        _, bag = run_analysis(
            tree,
            files(
                axis("AX", 8, "sint8"),
                axis("AY", 200, "sint16"),
                table("M", datatype="sint8"),
                default="leading",
            ),
        )
        assert bag.has_errors
        assert checks(bag) == ["point-counts-unrepresentable"]
        assert "'M' stores its point count 200 as sint8" in messages(bag)

    def test_a_float_always_holds_a_count(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 300, "float32"), default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_an_uncounted_boolean_table_is_not_a_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 2, "boolean")))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_a_table_and_its_axis_disagreeing_is_a_warning(self, tree: Path) -> None:
        """A defines the curve and reads the axis B defines; B states the other convention."""
        tree_files = {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", point_counts="leading"),
            "a.ddd.json": component(
                "A", declare("input", "AX", "uint16", kind="axis", size=8), curve("C")
            ),
            "b.ddd.json": component(
                "B", declare("output", "AX", "uint16", kind="axis", size=8), point_counts="none"
            ),
        }
        dictionary, bag = run_analysis(tree, tree_files)
        assert dictionary is not None, messages(bag)
        assert checks(bag) == ["point-counts-mismatch"]
        assert (
            "'C' stores its point counts 'leading', but its axis 'AX' stores them 'none'"
            in messages(bag)
        )

    def test_agreement_is_not_a_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []


def generated(tree: Path, tree_files: dict[str, Any]) -> dict[str, str]:
    dictionary, bag = run_analysis(tree, tree_files)
    assert dictionary is not None, messages(bag)
    return {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}


class TestTheC:
    def test_a_counted_map_is_a_flat_array_with_its_counts_first(self, tree: Path) -> None:
        source = generated(
            tree,
            files(
                axis("AX", 2),
                axis("AY", 3),
                table("M", init=[[1, 2], [3, 4], [5, 6]]),
                default="leading",
            ),
        )["ddd_globals.c"]
        assert "const uint16_t M[2 + (3) * (2)] = { 2U, 3U, 1U, 2U, 3U, 4U, 5U, 6U };" in source

    def test_a_counted_axis_and_curve_carry_one_count(self, tree: Path) -> None:
        source = generated(
            tree, files(axis("AX", 2, init=[10, 20]), curve("C"), default="leading")
        )["ddd_globals.c"]
        assert "const uint16_t AX[1 + (2)] = { 2U, 10U, 20U };" in source
        assert "const uint16_t C[1 + (2)] = { 2U };" in source

    def test_a_count_spelled_by_a_constant_is_written_by_name(self, tree: Path) -> None:
        tree_files = files(axis("AX", "NX"), axis("AY", "NY"), table("M"), default="leading")
        tree_files["project.ddd.json"]["project"]["includes"].append("k.ddd.json")
        tree_files["k.ddd.json"] = {
            "constants": [{"name": "NX", "value": 8}, {"name": "NY", "value": 11}]
        }
        source = generated(tree, tree_files)["ddd_globals.c"]
        assert "const uint16_t M[2 + (NY) * (NX)] = { NX, NY };" in source

    def test_the_component_header_declares_the_storage(self, tree: Path) -> None:
        header = generated(tree, files(axis("AX", 2), default="leading"))["A.h"]
        assert "uint16_t AX[1 + (2)]" in header

    def test_an_uncounted_project_is_unchanged(self, tree: Path) -> None:
        """A project that never states the key generates what it generated before."""
        stated = generated(
            tree / "a", files(axis("AX", 2), axis("AY", 3), table("M"), default="none")
        )
        unstated = generated(tree / "b", files(axis("AX", 2), axis("AY", 3), table("M")))
        assert stated == unstated
        assert "const uint16_t M[3][2];" in unstated["ddd_globals.c"]

    def test_the_view_offers_the_dimensions_and_the_counts(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree, files(axis("AX", 2), axis("AY", 3), table("M"), default="leading")
        )
        assert dictionary is not None, messages(bag)
        views = {
            view.name: view
            for group in build_code_model(dictionary, COptions(), "test").groups
            for view in group.variables
        }
        assert views["M"].dimensions == (3, 2)
        assert views["M"].point_counts == (2, 3)
        assert views["AX"].point_counts == (2,)

    def test_an_uncounted_view_has_its_dimensions_and_no_counts(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree, files(declare("local", "V", kind="value_block", dimensions=[4]))
        )
        assert dictionary is not None, messages(bag)
        views = {
            view.name: view
            for group in build_code_model(dictionary, COptions(), "test").groups
            for view in group.variables
        }
        assert views["V"].dimensions == (4,)
        assert views["V"].point_counts == ()


def a2l(tree: Path, tree_files: dict[str, Any]) -> str:
    return generated(tree, tree_files)["P.a2l"]


def layout(text: str, name: str) -> list[str]:
    """The lines of one record layout, stripped."""
    start = text.index(f"/begin RECORD_LAYOUT {name}\n")
    end = text.index("/end RECORD_LAYOUT", start)
    return [line.strip() for line in text[start:end].splitlines()[1:] if line.strip()]


class TestTheA2l:
    def test_a_counted_map_has_both_counts_ahead_of_its_values(self, tree: Path) -> None:
        text = a2l(
            tree,
            files(
                axis("AX", 8, "uint32"),
                axis("AY", 11, "uint32"),
                table("M", datatype="uint32"),
                default="leading",
            ),
        )
        assert layout(text, "RL_MAP_COUNTED_ULONG") == [
            "NO_AXIS_PTS_X 1 ULONG",
            "NO_AXIS_PTS_Y 2 ULONG",
            "FNC_VALUES 3 ULONG ROW_DIR DIRECT",
        ]
        assert "MAP 0x00000000 RL_MAP_COUNTED_ULONG" in text

    def test_a_counted_curve_has_one_count(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8), curve("C"), default="leading"))
        assert layout(text, "RL_CURVE_COUNTED_UWORD") == [
            "NO_AXIS_PTS_X 1 UWORD",
            "FNC_VALUES 2 UWORD ROW_DIR DIRECT",
        ]

    def test_a_counted_axis_has_its_count_ahead_of_its_points(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8, "sint16"), default="leading"))
        assert layout(text, "RL_AXIS_COUNTED_SWORD") == [
            "NO_AXIS_PTS_X 1 SWORD",
            "AXIS_PTS_X 2 SWORD INDEX_INCR DIRECT",
        ]

    def test_objects_of_one_kind_and_type_share_a_layout(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8), axis("AY", 11), default="leading"))
        assert text.count("/begin RECORD_LAYOUT RL_AXIS_COUNTED_UWORD") == 1

    def test_a_mixed_project_keeps_the_plain_layouts_for_the_rest(self, tree: Path) -> None:
        tree_files = {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", point_counts="leading"),
            "a.ddd.json": component("A", axis("AX", 8)),
            "b.ddd.json": component("B", axis("BX", 8), point_counts="none"),
        }
        text = a2l(tree, tree_files)
        assert "RL_AXIS_COUNTED_UWORD" in text
        assert layout(text, "RL_AXIS_UWORD") == ["AXIS_PTS_X 1 UWORD INDEX_INCR DIRECT"]

    def test_no_static_record_layout_is_written(self, tree: Path) -> None:
        """A tool removing points compacts the data behind the new count, which is what a
        routine computing ``y * nx + x`` from the stored count expects."""
        text = a2l(tree, files(axis("AX", 8), default="leading"))
        assert "STATIC_RECORD_LAYOUT" not in text


class TestCompare:
    def test_a_changed_convention_is_a_changed_interface(self, tree: Path) -> None:
        old, bag = run_analysis(tree / "old", files(axis("AX", 8)))
        assert old is not None, messages(bag)
        new, bag = run_analysis(tree / "new", files(axis("AX", 8), default="leading"))
        assert new is not None, messages(bag)
        verdict = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, verdict)
        assert checks(verdict) == ["changed-interface"]
        assert "point_counts" in messages(verdict)

    def test_an_unchanged_convention_is_not_a_finding(self, tree: Path) -> None:
        old, _ = run_analysis(tree / "old", files(axis("AX", 8), default="leading"))
        new, _ = run_analysis(tree / "new", files(axis("AX", 8), default="leading"))
        assert old is not None and new is not None
        verdict = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, verdict)
        assert checks(verdict) == []
