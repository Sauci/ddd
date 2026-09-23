"""Tests for point counts stored ahead of a curve, a map or an axis.

Some firmware stores the number of axis points inside every interpolation object, ahead of
its data, in the object's own type: the routines read the counts to learn the table's shape.
A project states that once, a component may state otherwise for what it defines, and both
backends then agree on where the data starts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
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
