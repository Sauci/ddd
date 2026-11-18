"""What a template can read of an object's scale, and what the example templates write of it.

The a2l states each object's unit, conversion and limits; the same three values reach the c
templates through ``ObjectView``, so a project that generates a scale macro, a table or a header
of its own from them cannot disagree with the a2l. The example ``{component}.h`` template writes
a factor macro and an offset macro for a linear conversion, so that a rescale of a shared type
changes the header every reader includes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import (
    MODE_T,
    component,
    declare,
    project,
    render_files,
    run_analysis,
    scalar_type,
    struct_type,
    types,
)
from ddd.backends.c.model import build_code_model
from ddd.backends.c.options import COptions


def analysed(tree: Path, files: dict[str, Any]) -> Any:
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [d.render() for d in bag]
    assert not bag.has_errors, [d.render() for d in bag]
    return dictionary


def two_components(speed: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {
        "project.ddd.json": project("P", "prod.ddd.json", "cons.ddd.json", *more),
        "prod.ddd.json": component("Prod", declare("output", "Speed", **speed)),
        "cons.ddd.json": component("Cons", declare("input", "Speed", **speed)),
    }


def views(tree: Path, files: dict[str, Any]) -> dict[str, Any]:
    model = build_code_model(analysed(tree, files), COptions(), "ddd")
    return {view.name: view for group in model.groups for view in group.variables}


def headers(tree: Path, files: dict[str, Any]) -> dict[str, str]:
    rendered = render_files(analysed(tree, files), tree / "gen", emit_a2l=False)
    return {file.path.name: file.content for file in rendered}


LINEAR = {"datatype": "sint16", "unit": "degC", "conversion": {"factor": 0.1, "offset": -40.0}}


class TestWhatAViewOffers:
    def test_a_linear_object_offers_its_unit_factor_offset_and_limits(self, tree: Path) -> None:
        speed = views(tree, two_components(LINEAR))["Speed"]
        assert speed.unit == "degC"
        assert (speed.conversion.kind, speed.conversion.factor, speed.conversion.offset) == (
            "linear",
            0.1,
            -40.0,
        )
        assert (speed.conversion.factor_literal, speed.conversion.offset_literal) == (
            "0.1",
            "-40.0",
        )
        assert speed.conversion.coefficients == (0.0, 1.0, 40.0, 0.0, 0.0, 0.1)
        assert speed.conversion.coefficient_literals == ("0.0", "1.0", "40.0", "0.0", "0.0", "0.1")
        # Derived from the datatype and the conversion, as the a2l derives them.
        assert (speed.limits.min, speed.limits.max) == (-3316.8, 3236.7)
        assert (speed.limits.min_literal, speed.limits.max_literal) == ("-3316.8", "3236.7")

    def test_the_three_are_the_values_the_a2l_states(self, tree: Path) -> None:
        files = two_components(LINEAR)
        a2l = render_files(analysed(tree, files), tree / "gen")
        text = "".join(file.content for file in a2l if file.path.suffix == ".a2l")
        assert '"degC"' in text
        assert "COEFFS 0 1 40 0 0 0.1" in text
        assert "-3316.8 3236.7" in text

    def test_explicit_limits_are_the_ones_offered(self, tree: Path) -> None:
        files = two_components({**LINEAR, "limits": {"min": -10, "max": 90}})
        limits = views(tree, files)["Speed"].limits
        assert (limits.min, limits.max) == (-10, 90)
        assert (limits.min_literal, limits.max_literal) == ("-10", "90")

    def test_the_identity_has_a_kind_and_nothing_else(self, tree: Path) -> None:
        conversion = views(tree, two_components({"datatype": "uint8"}))["Speed"].conversion
        assert conversion.kind == "identity"
        assert (conversion.factor, conversion.offset, conversion.enumerators) == (None, None, ())
        assert (conversion.factor_literal, conversion.offset_literal) == ("", "")
        assert conversion.coefficients == ()
        assert conversion.coefficient_literals == ()

    def test_an_enum_offers_its_name_and_values(self, tree: Path) -> None:
        files = two_components({"datatype": "uint8", "conversion": MODE_T})
        conversion = views(tree, files)["Speed"].conversion
        assert conversion.kind == "enum"
        assert conversion.name == MODE_T["name"]
        assert [(e.name, e.value) for e in conversion.enumerators] == [
            ("MODE_OFF", 0),
            ("MODE_ON", 1),
        ]

    def test_a_string_is_a_kind(self, tree: Path) -> None:
        text = {
            "datatype": "uint8",
            "kind": "value_block",
            "conversion": {"kind": "string"},
            "dimensions": [8],
        }
        assert views(tree, two_components(text))["Speed"].conversion.kind == "string"

    def test_a_structured_variable_states_none_of_the_three(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "Pair", typename="Pair_s")),
            "t.ddd.json": types(struct_type("Pair_s")),
        }
        pair = views(tree, files)["Pair"]
        assert (pair.unit, pair.conversion, pair.limits) == ("", None, None)


class Counted(tuple):  # type: ignore[type-arg]
    """The enumerators of an enum, counting every one a walk over them reaches.

    What an object's view costs is counted rather than timed, as the model builders' walks
    are: at 5,000 objects naming one enum of 200 values, ``ddd generate c`` took four times as
    long as it did before the views offered an enum's enumerators, every one of them built and
    made safe for a comment once for each object.
    """

    reached: int

    def __new__(cls, items: Any) -> Counted:
        counted: Counted = super().__new__(cls, items)
        counted.reached = 0
        return counted

    def __iter__(self) -> Any:
        for item in super().__iter__():
            self.reached += 1
            yield item


class TestAnEnumIsViewedOnce:
    """Each enum's enumerators are built once, and every object it converts shares them."""

    ENUMERATORS = 10

    def counted(self, tree: Path, objects: int) -> tuple[Any, Counted]:
        """A project of ``objects`` outputs naming one enum, every copy of the enum counting."""
        enum = {
            "kind": "enum",
            "name": "State_e",
            "enumerators": [
                {"name": f"S_{index}", "value": index, "description": f"state {index}"}
                for index in range(self.ENUMERATORS)
            ],
        }
        files = {
            "project.ddd.json": project("P", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", *(declare("output", f"V{n}", typename="State_t") for n in range(objects))
            ),
            "t.ddd.json": types(scalar_type("State_t", "uint8", conversion=enum)),
        }
        dictionary, bag = run_analysis(tree, files, severities=("unused-output=ignore",))
        assert dictionary is not None, [finding.render() for finding in bag]
        (declared,) = dictionary.enums
        enumerators = Counted(declared.enumerators)
        shared = declared.model_copy(update={"enumerators": enumerators})
        counting = dictionary.model_copy(
            update={
                "enums": (shared,),
                "objects": tuple(
                    entry.model_copy(update={"conversion": shared}) for entry in dictionary.objects
                ),
            }
        )
        return counting, enumerators

    def test_the_work_grows_with_the_enum_and_not_with_the_objects_it_converts(
        self, tree: Path
    ) -> None:
        dictionary, enumerators = self.counted(tree, 40)
        build_code_model(dictionary, COptions(), "ddd")
        assert enumerators.reached <= 2 * self.ENUMERATORS, (
            f"40 objects over one enum of {self.ENUMERATORS} values reached "
            f"{enumerators.reached} enumerators, so each object builds the enum's views again"
        )

    def test_every_object_shares_the_views_the_types_header_is_written_from(
        self, tree: Path
    ) -> None:
        dictionary, _ = self.counted(tree, 3)
        model = build_code_model(dictionary, COptions(), "ddd")
        (enum,) = model.enums
        variables = [view for group in model.groups for view in group.variables]
        assert len(variables) == 3
        for view in variables:
            assert view.conversion.enumerators is enum.enumerators

    def test_an_enum_the_dictionary_does_not_list_is_built_once_too(self, tree: Path) -> None:
        """A dictionary another producer wrote may leave an enum out of ``enums``: the objects
        it converts still share one tuple of its views."""
        dictionary, enumerators = self.counted(tree, 40)
        model = build_code_model(dictionary.model_copy(update={"enums": ()}), COptions(), "ddd")
        assert model.enums == ()
        assert enumerators.reached == self.ENUMERATORS
        variables = [view for group in model.groups for view in group.variables]
        assert [e.name for e in variables[0].conversion.enumerators][:2] == ["S_0", "S_1"]
        assert len({id(view.conversion.enumerators) for view in variables}) == 1

    def test_the_better_documented_copy_reaches_the_view_as_it_reaches_the_types_header(
        self, tree: Path
    ) -> None:
        """Two components spelling one enum, one of them without descriptions: the types header
        writes the documented copy, and an object's view, which a template writes a table of
        labels from, says the same."""
        bare = {
            "kind": "enum",
            "name": "Mode_t",
            "enumerators": [{"name": "MODE_OFF", "value": 0}, {"name": "MODE_ON", "value": 1}],
        }
        told = {
            "kind": "enum",
            "name": "Mode_t",
            "enumerators": [
                {"name": "MODE_OFF", "value": 0, "description": "off"},
                {"name": "MODE_ON", "value": 1, "description": "on"},
            ],
        }
        files = {
            "project.ddd.json": project("P", "prod.ddd.json", "cons.ddd.json"),
            "prod.ddd.json": component("Prod", declare("output", "Speed", conversion=bare)),
            "cons.ddd.json": component("Cons", declare("input", "Speed", conversion=told)),
        }
        model = build_code_model(analysed(tree, files), COptions(), "ddd")
        (enum,) = model.enums
        assert [e.description for e in enum.enumerators] == ["off", "on"]
        speed = views(tree, files)["Speed"]
        assert [e.description for e in speed.conversion.enumerators] == ["off", "on"]


class TestWhatTheExampleHeaderWrites:
    def test_a_linear_input_and_output_each_carry_a_factor_and_an_offset(self, tree: Path) -> None:
        written = headers(tree, two_components(LINEAR))
        for header in ("Prod.h", "Cons.h"):
            assert "#define Speed__FACTOR (0.1)\n#define Speed__OFFSET (-40.0)\n" in written[header]

    def test_the_macros_follow_the_declaration_inside_its_condition(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("output", "Speed", condition="USE_SPEED", **LINEAR)
            ),
        }
        assert (
            "extern int16_t Speed;\n#define Speed__FACTOR (0.1)\n#define Speed__OFFSET (-40.0)\n"
            "#endif /* USE_SPEED */\n"
        ) in headers(tree, files)["A.h"]

    def test_a_local_carries_none(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "Speed", **LINEAR)),
        }
        assert "__FACTOR" not in headers(tree, files)["A.h"]

    def test_no_other_kind_of_conversion_writes_one(self, tree: Path) -> None:
        for speed in ({"datatype": "uint8"}, {"datatype": "uint8", "conversion": MODE_T}):
            assert "__FACTOR" not in headers(tree, two_components(speed))["Cons.h"]

    def test_the_names_are_ones_a_project_cannot_hold(self, tree: Path) -> None:
        from ddd.models import is_reserved_identifier

        # A double underscore is refused in every name a project writes, so the macros cannot
        # take the place of a name the generated c holds.
        assert is_reserved_identifier("Speed__FACTOR")
        assert is_reserved_identifier("Speed__OFFSET")


class TestARescaleOfASharedType:
    @staticmethod
    def files(factor: float) -> dict[str, Any]:
        # The failure the concept page tells: producer and reader name one type, and its factor
        # changes from 0.1 to 0.01. Neither description shows it.
        named = {"typename": "Temp_t"}
        return {
            "project.ddd.json": project("P", "prod.ddd.json", "cons.ddd.json", "t.ddd.json"),
            "prod.ddd.json": component("Prod", declare("output", "Temp", **named)),
            "cons.ddd.json": component("Cons", declare("input", "Temp", **named)),
            "t.ddd.json": types(
                scalar_type("Temp_t", "sint16", unit="degC", conversion={"factor": factor})
            ),
        }

    def test_the_readers_header_differs_where_it_used_to_be_byte_identical(
        self, tmp_path: Path
    ) -> None:
        before = headers(tmp_path / "before", self.files(0.1))
        after = headers(tmp_path / "after", self.files(0.01))
        assert "#define Temp__FACTOR (0.1)\n" in before["Cons.h"]
        assert "#define Temp__FACTOR (0.01)\n" in after["Cons.h"]
        for name in ("Cons.h", "Prod.h"):
            assert before[name] != after[name]
        # What was already true: the rest of the c does not show it.
        for name in ("ddd_globals.c", "ddd_globals.h", "ddd_types.h"):
            assert before[name] == after[name]
