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

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.ir import DataDictionary, ResolvedObject
from ddd.loading import load_dictionary, load_workspace
from ddd.models import ComponentFile, ObjectKind, PointCounts, ProjectFile, stored_counts


def axis(name: str = "AX", size: int | str = 4, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return declare("local", name, datatype, kind="axis", size=size, **extra)


def curve(name: str = "C", over: str = "AX", datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
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
        write_tree(tree, {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")})
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
    def test_x_comes_first(self, kind: ObjectKind, shape: tuple[Any, ...], counts: tuple[Any, ...]) -> None:
        """A map is declared ``[y][x]`` and stores x then y: an 8 by 11 map begins ``8, 11``."""
        assert stored_counts(kind, shape) == counts


def files(*declarations: dict[str, Any], default: str | None = None, **extra: Any) -> dict[str, Any]:
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
    def test_a_component_overrides_the_default(self, tree: Path, default: str, override: str) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default=default, point_counts=override))
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "M").point_counts is PointCounts(override)

    def test_it_reaches_no_other_kind(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            files(declare("local", "X"), declare("local", "K", kind="parameter", init=1), default="leading"),
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
