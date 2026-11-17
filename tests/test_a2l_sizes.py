"""A size the a2l's ``uint`` cannot hold: ``MATRIX_DIM``, ``NUMBER`` and ``MaxAxisPoints``.

ASAP2 1.6.1 types the three as ``uint``, two bytes. A size past 65,535 is ``a2l-unrepresentable``,
a warning: the file is still written, with the number whole, and ``--strict`` stops on it. It is
said once per cause, at the declaration that states the size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import (
    TEXT_TYPE,
    checks,
    component,
    declare,
    messages,
    project,
    run_analysis,
    struct_type,
    types,
    value_member,
)

OVER = 65536
"""One more than a two byte ``uint`` holds."""


def one(tree: Path, *declarations: dict[str, Any]) -> Any:
    files = {
        "project.ddd.json": project("P", "a.ddd.json"),
        "a.ddd.json": component("A", *declarations),
    }
    return run_analysis(tree, files)[1]


class TestAnArray:
    def test_65535_elements_are_clean(self, tree: Path) -> None:
        assert checks(one(tree, declare("local", "V", dimensions=[65535]))) == []

    def test_65536_elements_are_named_with_the_number_whole(self, tree: Path) -> None:
        bag = one(tree, declare("local", "V", dimensions=[OVER]))
        assert checks(bag) == ["a2l-unrepresentable"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition" in rendered
        assert "'V' has a dimension of 65536 elements" in rendered
        assert "MATRIX_DIM" in rendered
        assert "65535" in rendered

    def test_one_finding_for_one_object_whatever_its_dimensions(self, tree: Path) -> None:
        bag = one(tree, declare("local", "V", dimensions=[OVER, 2]))
        assert checks(bag) == ["a2l-unrepresentable"]

    def test_an_object_kept_out_of_the_a2l_says_nothing(self, tree: Path) -> None:
        bag = one(tree, declare("local", "V", dimensions=[OVER], a2l={"export": False}))
        assert checks(bag) == []

    def test_a_string_of_65536_characters_names_its_number(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "S", typename="Text_t", dimensions=[OVER])
            ),
            "t.ddd.json": types(TEXT_TYPE),
        }
        bag = run_analysis(tree, files)[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        assert "NUMBER" in messages(bag)

    def test_a_member_of_a_structure_is_named_at_its_own_path(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", value_member("v", dimensions=[OVER]))),
        }
        bag = run_analysis(tree, files)[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        assert "'X.v' has a dimension of 65536 elements" in messages(bag)

    def test_a_member_at_the_limit_is_clean(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", value_member("v", dimensions=[65535]))),
        }
        assert checks(run_analysis(tree, files)[1]) == []


class TestAnAxisAndWhatIsOverIt:
    def axes(self, size: int, *more: dict[str, Any]) -> list[dict[str, Any]]:
        return [declare("local", "Ax", kind="axis", size=size), *more]

    def test_an_axis_of_65535_points_is_clean(self, tree: Path) -> None:
        assert checks(one(tree, *self.axes(65535))) == []

    def test_an_axis_of_65536_points_is_named_as_maxaxispoints(self, tree: Path) -> None:
        bag = one(tree, *self.axes(OVER))
        assert checks(bag) == ["a2l-unrepresentable"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition" in rendered
        assert "'Ax' has a dimension of 65536 elements" in rendered
        assert "MaxAxisPoints" in rendered

    def test_a_curve_over_it_is_not_named_again(self, tree: Path) -> None:
        bag = one(tree, *self.axes(OVER, declare("local", "C", kind="curve", axis="Ax")))
        assert checks(bag) == ["a2l-unrepresentable"]

    def test_a_map_over_it_is_not_named_again(self, tree: Path) -> None:
        bag = one(
            tree,
            *self.axes(
                OVER,
                declare("local", "Ay", kind="axis", size=2),
                declare("local", "M", kind="map", x_axis="Ax", y_axis="Ay"),
            ),
        )
        assert checks(bag) == ["a2l-unrepresentable"]

    def test_a_curve_over_an_axis_at_the_limit_is_clean(self, tree: Path) -> None:
        bag = one(tree, *self.axes(65535, declare("local", "C", kind="curve", axis="Ax")))
        assert checks(bag) == []
