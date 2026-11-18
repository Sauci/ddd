"""A size the a2l's ``uint`` cannot hold: ``MATRIX_DIM``, ``NUMBER`` and ``MaxAxisPoints``.

ASAP2 1.6.1 types the three as ``uint``, two bytes. A size past 65,535 is ``a2l-unrepresentable``,
a warning: the file is still written, with the number whole, and ``--strict`` stops on it. It is
said once per cause, at the declaration that states the size.
"""

from __future__ import annotations

import re
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


def size_fields(tree: Path, files: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    """What the run reports, and the size fields each record of the a2l it writes holds.

    The finding names a field; the record is where the field is, so the two are read off one
    run: a string is a ``NUMBER`` in a characteristic and a ``MATRIX_DIM`` in a measurement.
    """
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, messages(bag)
    rendered = render_files(dictionary, tree / "gen")
    text = next(file.content for file in rendered if file.path.name == "P.a2l")
    records = {
        found.group(2): re.findall(r"^\s*(MATRIX_DIM|NUMBER) ", found.group(3), re.MULTILINE)
        for found in re.finditer(
            r"/begin (MEASUREMENT|CHARACTERISTIC) (\S+)(.*?)/end \1", text, re.DOTALL
        )
    }
    return messages(bag), records


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

    def strings(self, kind: str) -> dict[str, Any]:
        return {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "S", typename="Text_t", dimensions=[OVER], kind=kind)
            ),
            "t.ddd.json": types(TEXT_TYPE),
        }

    def test_a_string_measurement_names_the_matrix_dim_its_record_writes(self, tree: Path) -> None:
        """A string measurement stays the byte array it is, so its size is a ``MATRIX_DIM``."""
        rendered, records = size_fields(tree, self.strings("measurement"))
        assert records["S"] == ["MATRIX_DIM"]
        assert "but the MATRIX_DIM of ASAP2 1.6.1 is a uint of two bytes" in rendered
        assert "NUMBER" not in rendered

    def test_a_string_value_block_names_the_number_its_record_writes(self, tree: Path) -> None:
        rendered, records = size_fields(tree, self.strings("value_block"))
        assert records["S"] == ["NUMBER"]
        assert "but the NUMBER of ASAP2 1.6.1 is a uint of two bytes" in rendered
        assert "MATRIX_DIM" not in rendered

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

    def test_a_string_member_names_both_fields_its_records_write(self, tree: Path) -> None:
        """A member is named once at its type, and its record is the instance's kind's: the
        ``MATRIX_DIM`` of a measurement and the ``NUMBER`` of a characteristic, so both."""
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A",
                declare("local", "X", typename="S_t"),
                declare("local", "Y", typename="S_t", kind="parameter"),
            ),
            "t.ddd.json": types(
                TEXT_TYPE,
                struct_type("S_t", value_member("v", typename="Text_t", dimensions=[OVER])),
            ),
        }
        rendered, records = size_fields(tree, files)
        assert (records["X.v"], records["Y.v"]) == (["MATRIX_DIM"], ["NUMBER"])
        assert rendered.count("a2l-unrepresentable") == 1
        assert (
            "member 'v' of structure 'S_t' has a dimension of 65536 elements, but the "
            "MATRIX_DIM of a measurement or the NUMBER of a characteristic of ASAP2 1.6.1 is a "
            "uint of two bytes and carries at most 65535; the size is written whole"
        ) in rendered

    def test_a_member_that_is_no_string_names_the_matrix_dim_whatever_holds_it(
        self, tree: Path
    ) -> None:
        files = self.structure_files(instances=None)
        files["a.ddd.json"] = component(
            "A",
            declare("local", "X", typename="S_t"),
            declare("local", "Y", typename="S_t", kind="parameter"),
        )
        rendered, records = size_fields(tree, files)
        assert (records["X.v"], records["Y.v"]) == (["MATRIX_DIM"], ["MATRIX_DIM"])
        assert "but the MATRIX_DIM of ASAP2 1.6.1 is a uint of two bytes" in rendered
        assert "NUMBER" not in rendered

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


class TestAMemberWithTooManyDimensions:
    """``MATRIX_DIM`` carries three dimensions. A member's dimensions are its type's, so a
    member with four is named once, at the type file, however many variables reach it."""

    def files(
        self, *, variables: int = 2, instances: int | None = 1000, **member: Any
    ) -> dict[str, Any]:
        dimensions = {} if instances is None else {"dimensions": [instances]}
        names = "ABCD"[:variables]
        return {
            "project.ddd.json": project("P", "w.ddd.json", "t.ddd.json"),
            "w.ddd.json": component(
                "W", *(declare("local", name, typename="Slot_t", **dimensions) for name in names)
            ),
            "t.ddd.json": types(
                struct_type(
                    "Slot_t",
                    value_member("tensor", "uint8", dimensions=[2, 2, 2, 2], **member),
                    value_member("raw"),
                )
            ),
        }

    def test_a_member_is_named_once_at_the_type_whatever_reaches_it(self, tree: Path) -> None:
        bag = run_analysis(tree, self.files())[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        rendered = messages(bag)
        assert "t.ddd.json#types[0].members[0].dimensions" in rendered
        assert "member 'tensor' of structure 'Slot_t' has 4 dimensions" in rendered
        assert "MATRIX_DIM" in rendered
        assert "w.ddd.json" not in rendered

    def test_one_instance_names_it_once_too(self, tree: Path) -> None:
        bag = run_analysis(tree, self.files(variables=1, instances=None))[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        assert "t.ddd.json#types[0].members[0].dimensions" in messages(bag)

    def test_a_member_kept_out_of_the_a2l_says_nothing(self, tree: Path) -> None:
        bag = run_analysis(tree, self.files(a2l={"export": False}))[1]
        assert checks(bag) == []

    def test_a_member_past_both_limits_is_named_in_one_walk_each_cause_once(
        self, tree: Path
    ) -> None:
        files = self.files()
        files["t.ddd.json"] = types(
            struct_type("Slot_t", value_member("tensor", dimensions=[OVER, 2, 2, 2]))
        )
        bag = run_analysis(tree, files)[1]
        assert checks(bag) == ["a2l-unrepresentable"] * 2
        rendered = messages(bag)
        assert rendered.count("has 4 dimensions") == 1
        assert rendered.count("has a dimension of 65536 elements") == 1
        assert "w.ddd.json" not in rendered

    def test_a_declarations_own_dimensions_are_named_at_the_declaration(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "w.ddd.json"),
            "w.ddd.json": component("W", declare("local", "V", dimensions=[2, 2, 2, 2])),
        }
        bag = run_analysis(tree, files)[1]
        assert checks(bag) == ["a2l-unrepresentable"]
        assert "w.ddd.json#component.interface[0].definition" in messages(bag)
        assert "'V' has 4 dimensions" in messages(bag)
