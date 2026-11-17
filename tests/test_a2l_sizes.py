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
    render_files,
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

    def test_the_record_is_still_written_with_its_number(self, tree: Path) -> None:
        """The finding says the size is written whole; the file must hold it."""
        files = {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "V", dimensions=[OVER])),
        }
        dictionary, _ = run_analysis(tree, files)
        assert dictionary is not None
        rendered = render_files(dictionary, tree / "gen")
        text = next(file.content for file in rendered if file.path.name == "P.a2l")
        assert "MATRIX_DIM 65536 1 1" in text

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

    def structure_files(self, *, instances: int | None, size: int = OVER) -> dict[str, Any]:
        dimensions = {} if instances is None else {"dimensions": [instances]}
        return {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t", **dimensions)),
            "t.ddd.json": types(struct_type("S_t", value_member("v", dimensions=[size]))),
        }

    def test_a_member_is_named_once_at_the_type_that_states_its_size(self, tree: Path) -> None:
        """A member's size is its type's, so the cause is the type file's."""
        bag = run_analysis(tree, self.structure_files(instances=None))[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        rendered = messages(bag)
        assert "t.ddd.json#types[0].members[0].dimensions" in rendered
        assert "member 'v' of structure 'S_t' has a dimension of 65536 elements" in rendered
        assert "MATRIX_DIM" in rendered

    def test_an_array_of_structures_names_its_member_once(self, tree: Path) -> None:
        """Three elements are three records of the member, and one cause."""
        bag = run_analysis(tree, self.structure_files(instances=3))[1]
        assert checks(bag) == ["a2l-unrepresentable"]

    def test_two_instances_of_one_type_name_its_member_once(self, tree: Path) -> None:
        files = self.structure_files(instances=None)
        files["a.ddd.json"] = component(
            "A", declare("local", "X", typename="S_t"), declare("local", "Y", typename="S_t")
        )
        assert checks(run_analysis(tree, files)[1]) == ["a2l-unrepresentable"]

    def test_a_string_member_is_named_by_its_number_field(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                TEXT_TYPE,
                struct_type("S_t", value_member("v", typename="Text_t", dimensions=[OVER])),
            ),
        }
        bag = run_analysis(tree, files)[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        assert "the NUMBER of ASAP2" in messages(bag)

    def test_a_member_is_still_written_with_its_number(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, self.structure_files(instances=None))
        assert dictionary is not None
        rendered = render_files(dictionary, tree / "gen")
        text = next(file.content for file in rendered if file.path.name == "P.a2l")
        assert "MATRIX_DIM 65536 1 1" in text

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
