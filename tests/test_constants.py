"""Tests for the constant vocabulary: the file, the checks, and the spelling it carries.

A shape names a constant where it would state a number, so a size lives in one place. The
name is a spelling of the size - declarations compare as written, the generated c declares
the array by the name, the a2l records the constant - and the number is what everything
downstream computes with.
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
from ddd.diagnostics import DiagnosticBag
from ddd.ir import (
    DICTIONARY_FORMAT,
    DataDictionary,
    ResolvedInstance,
    ResolvedLeaf,
    ResolvedObject,
)
from ddd.loading import load_dictionary, load_workspace
from ddd.models import Axis, ConstantsFile, Measurement


def constants(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"constants": list(entries)}


def struct_type(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    """A types file declaring one structure - the scaffold the tests here keep needing."""
    return {"types": [{"type": "struct", "name": name, "members": list(members)}]}


def value_member(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return {"name": name, "member": "value", "datatype": datatype, "conversion": {}, **extra}


def constant(name: str, value: int, description: str = "") -> dict[str, Any]:
    declared = {"name": name, "value": value}
    if description:
        declared["description"] = description
    return declared


class TestTheFile:
    def test_a_constant_carries_its_properties(self) -> None:
        model = ConstantsFile.model_validate(
            constants(constant("PRESSURE_CELLS", 8, "cells of the manifold"))
        )
        declared = model.constants[0]
        assert declared.name == "PRESSURE_CELLS"
        assert declared.value == 8
        assert declared.description == "cells of the manifold"

    def test_a_value_below_one_is_refused(self) -> None:
        """The value is an array dimension, and an array of no elements is no array."""
        with pytest.raises(ValidationError):
            ConstantsFile.model_validate(constants(constant("N", 0)))

    def test_a_quoted_value_is_refused(self) -> None:
        """A value is written as a number; ``"8"`` is neither a number nor a name."""
        with pytest.raises(ValidationError):
            ConstantsFile.model_validate({"constants": [{"name": "N", "value": "8"}]})

    def test_an_empty_vocabulary_is_refused(self) -> None:
        """Declaring nothing is done by not writing the file, not by an empty list."""
        with pytest.raises(ValidationError):
            ConstantsFile.model_validate(constants())

    def test_a_constants_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        write_tree(tree, {"constants.ddd.json": constants(constant("N", 4))})
        bag = DiagnosticBag()
        assert load_workspace(tree / "constants.ddd.json", bag) is None
        assert checks(bag) == ["file-kind"]
        assert "list it in the 'includes'" in messages(bag)

    def test_a_malformed_constants_file_is_reported_against_its_keys(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json"),
                "constants.ddd.json": {"constants": [{"name": "N"}]},
            },
        )
        assert checks(bag) == ["schema"]
        assert "constants[0]" in messages(bag)

    def test_two_files_cannot_declare_the_same_constant(self, tree: Path) -> None:
        """A size that depends on which file loads first is what the vocabulary prevents."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": constants(constant("N", 8)),
                "two.ddd.json": constants(constant("N", 12)),
            },
        )
        assert checks(bag) == ["duplicate-constant"]
        rendered = messages(bag)
        assert "constant 'N' is already declared" in rendered
        assert "one.ddd.json#constants[0]: first declared here" in rendered


class TestTheSpelling:
    """A dimension is an integer or the name of a declared constant, never a third thing."""

    def test_a_dimension_may_name_a_constant(self) -> None:
        model = Measurement.model_validate(
            {
                "name": "X",
                "kind": "measurement",
                "datatype": "uint8",
                "conversion": {},
                "volatile": False,
                "dimensions": ["PRESSURE_CELLS", 4],
            }
        )
        assert model.dimensions == ("PRESSURE_CELLS", 4)
        assert model.declared_shape == ("PRESSURE_CELLS", 4)

    def test_an_axis_size_may_name_a_constant(self) -> None:
        model = Axis.model_validate(
            {
                "name": "Ax",
                "kind": "axis",
                "datatype": "uint8",
                "conversion": {},
                "volatile": False,
                "size": "AXIS_POINTS",
            }
        )
        assert model.size == "AXIS_POINTS"
        assert model.declared_shape == ("AXIS_POINTS",)

    @pytest.mark.parametrize("dimension", ["8", 0, 4.0, ""])
    def test_what_is_neither_a_number_nor_a_name_is_refused(self, dimension: Any) -> None:
        """``"8"`` is a quoted number, not a constant name; reading it as 8 would make the
        file say something its author did not write."""
        with pytest.raises(ValidationError):
            Measurement.model_validate(
                {
                    "name": "X",
                    "kind": "measurement",
                    "datatype": "uint8",
                    "conversion": {},
                    "volatile": False,
                    "dimensions": [dimension],
                }
            )


class TestTheCheck:
    def files(self, *declarations: dict[str, Any], **extra: Any) -> dict[str, Any]:
        vocabulary = extra.pop("vocabulary", [constant("PRESSURE_CELLS", 8)])
        assert not extra
        return {
            "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
            "constants.ddd.json": constants(*vocabulary),
            "a.ddd.json": component("A", *declarations),
        }

    def test_a_declared_name_resolves(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree, self.files(declare("local", "X", dimensions=["PRESSURE_CELLS", 2]))
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["X"].shape == (8, 2)
        assert dictionary.by_name["X"].dimensions == ("PRESSURE_CELLS", 2)

    def test_an_undeclared_name_is_reported_where_it_is_written(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, self.files(declare("local", "X", dimensions=[2, "PRESURE_CELLS"]))
        )
        assert checks(bag) == ["unknown-constant"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition.dimensions[1]" in rendered
        assert "'X' is dimensioned by 'PRESURE_CELLS'" in rendered
        assert "did you mean 'PRESSURE_CELLS'" in rendered

    def test_an_undeclared_axis_size_is_reported_at_the_size(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            self.files(declare("local", "Ax", kind="axis", size="NOWHERE_NEAR", datatype="uint16")),
        )
        assert checks(bag) == ["unknown-constant"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition.size" in rendered
        assert "did you mean" not in rendered  # nothing close enough to suggest

    def test_a_constant_is_a_reference_even_without_a_constants_file(self, tree: Path) -> None:
        """Like a section: a name without a value is a dimension nothing can resolve."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", dimensions=["N"])),
            },
        )
        assert checks(bag) == ["unknown-constant"]

    def test_the_declaration_is_dropped_from_resolution(self, tree: Path) -> None:
        """The poisoning pattern of an unknown type: the axis is dropped, and the curve over
        it is dropped along with it, quietly - saying that nobody declares the axis would be
        false, and the finding at the unknown constant is the one to act on."""
        dictionary, bag = run_analysis(
            tree,
            self.files(
                declare("local", "Ax", kind="axis", size="MISSING", datatype="uint16"),
                declare("local", "C", kind="curve", axis="Ax", datatype="uint16"),
            ),
        )
        assert checks(bag) == ["unknown-constant"]
        assert dictionary is not None
        assert dictionary.objects == ()

    def test_the_drop_carries_through_a_chain_of_references(self, tree: Path) -> None:
        """An axis indexed by a dropped measurement is dropped, and the curve over that
        axis with it: any link kept would leave a dangling name in the a2l, and the one
        finding at the root already names the cause."""
        dictionary, bag = run_analysis(
            tree,
            self.files(
                declare("local", "Meas", dimensions=["MISSING"]),
                declare("local", "Ax", kind="axis", size=4, datatype="uint16", input="Meas"),
                declare("local", "C", kind="curve", axis="Ax", datatype="uint16"),
            ),
        )
        assert checks(bag) == ["unknown-constant"]
        assert dictionary is not None
        assert dictionary.objects == ()

    def test_the_dropped_declarations_leave_the_component_interface(self, tree: Path) -> None:
        """The dictionary's interfaces name only what its objects carry, so a generator
        walking a component's declarations never meets a name that resolves to nothing."""
        dictionary, _ = run_analysis(
            tree,
            self.files(
                declare("local", "Ax", kind="axis", size="MISSING", datatype="uint16"),
                declare("local", "C", kind="curve", axis="Ax", datatype="uint16"),
                declare("local", "Kept", dimensions=["PRESSURE_CELLS"]),
            ),
        )
        assert dictionary is not None
        (component_a,) = dictionary.components
        assert [entry.name for entry in component_a.declarations] == ["Kept"]

    def test_a_member_dimension_is_checked_and_poisons_the_type(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "constants.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "constants.ddd.json": constants(constant("PRESSURE_CELLS", 8)),
                "types.ddd.json": struct_type(
                    "S_t", value_member("raw", dimensions=["PRESURE_CELLS"])
                ),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert checks(bag) == ["unknown-constant"]
        rendered = messages(bag)
        assert "types.ddd.json#types[0].members[0].dimensions[0]" in rendered
        assert "member 'raw' of structure 'S_t'" in rendered

    def test_the_check_is_relaxable(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            self.files(declare("local", "X", dimensions=["MISSING"])),
            severities=["unknown-constant=warning"],
        )
        assert checks(bag) == ["unknown-constant"]
        assert not bag.has_errors

    def test_silencing_the_finding_says_what_the_silence_costs(self, tree: Path) -> None:
        """Relaxing the check does not put the variable back; it only hides why it went.

        The declaration is still dropped - a dimension without a value is an array of no
        known length, whatever severity the finding is given - so with nothing said, ``ddd
        list`` prints a table one row short and exits zero, and ``ddd dump`` archives a
        dictionary a variable is missing from. That is the one way this tool can be wrong
        without anybody being told, so the consequence is reported even when its cause is not.
        """
        dictionary, bag = run_analysis(
            tree,
            self.files(declare("local", "X", dimensions=["MISSING"])),
            severities=["unknown-constant=ignore"],
        )
        assert checks(bag) == ["incomplete-project"]
        assert "'X' is not in the data dictionary" in messages(bag)
        assert dictionary is not None and dictionary.objects == ()

    def test_a_reported_finding_needs_no_second_one(self, tree: Path) -> None:
        """The error already says the variable could not resolve; saying it twice is noise."""
        _, bag = run_analysis(tree, self.files(declare("local", "X", dimensions=["MISSING"])))
        assert checks(bag) == ["unknown-constant"]

    def test_an_ignored_unknown_constant_keeps_the_shape_free_findings(self, tree: Path) -> None:
        """Silencing the shape finding must not silence what the shape never decided: the
        declaration stays out of the dictionary, but an init outside the datatype is wrong
        whatever the shape turns out to be."""
        dictionary, bag = run_analysis(
            tree,
            self.files(declare("local", "X", dimensions=["MISSING"], init=999)),
            severities=["unknown-constant=ignore"],
        )
        assert checks(bag) == ["incomplete-project", "init-invalid"]
        assert "does not fit into uint8" in messages(bag)
        assert dictionary is not None
        assert dictionary.objects == ()

    def test_a_declaration_of_a_poisoned_type_keeps_its_name_checks(self, tree: Path) -> None:
        """The poisoned type makes the declaration unresolvable, but the checks that need
        neither its storage nor its shape still run - here, a consumer claiming the initial
        value of a variable it only reads."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "constants.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "constants.ddd.json": constants(constant("PRESSURE_CELLS", 8)),
                "types.ddd.json": struct_type("S_t", value_member("raw", dimensions=["MISSING"])),
                "a.ddd.json": component("A", declare("input", "X", typename="S_t", init=1)),
            },
            severities=["unknown-constant=ignore"],
        )
        assert checks(bag) == ["consumer-storage"]
        assert "the initial value is decided by the component that produces" in messages(bag)


class TestSpellingIsInterface:
    """A name and its value are different spellings of one size, like conversions."""

    def files(self, mine: Any, theirs: Any) -> dict[str, Any]:
        return {
            "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json", "b.ddd.json"),
            "constants.ddd.json": constants(constant("N", 8)),
            "a.ddd.json": component("A", declare("output", "X", dimensions=mine)),
            "b.ddd.json": component("B", declare("input", "X", dimensions=theirs)),
        }

    def test_the_name_and_its_value_disagree(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files(["N"], [8]))
        assert checks(bag) == ["definition-mismatch"]
        assert "shape: [8] != [N]" in messages(bag)

    def test_the_same_spelling_agrees(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files(["N"], ["N"]))
        assert checks(bag) == []

    def test_axis_sizes_compare_as_written_too(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json", "b.ddd.json"),
                "constants.ddd.json": constants(constant("N", 8)),
                "a.ddd.json": component(
                    "A", declare("output", "Ax", kind="axis", size="N", datatype="uint16")
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Ax", kind="axis", size=8, datatype="uint16")
                ),
            },
        )
        assert checks(bag) == ["definition-mismatch"]
        assert "shape: [8] != [N]" in messages(bag)


class TestResolution:
    def test_a_curve_and_a_map_inherit_the_spelling_of_their_axes(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("N_X", 3), constant("N_Y", 2)),
                "a.ddd.json": component(
                    "A",
                    declare("local", "AxX", kind="axis", size="N_X", datatype="uint16"),
                    declare("local", "AxY", kind="axis", size="N_Y", datatype="uint16"),
                    declare("local", "C", kind="curve", axis="AxX", datatype="uint16"),
                    declare(
                        "local", "M", kind="map", x_axis="AxX", y_axis="AxY", datatype="uint16"
                    ),
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["C"].shape == (3,)
        assert dictionary.by_name["C"].dimensions == ("N_X",)
        assert dictionary.by_name["M"].shape == (2, 3)
        assert dictionary.by_name["M"].dimensions == ("N_Y", "N_X")

    def test_an_init_is_counted_against_the_value(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
            "constants.ddd.json": constants(constant("N", 3)),
            "a.ddd.json": component(
                "A", declare("local", "X", dimensions=["N"], init=[1, 2, 3, 4])
            ),
        }
        _, bag = run_analysis(tree, files)
        assert checks(bag) == ["init-invalid"]
        assert "init has 4 elements, expected 3" in messages(bag)

    def test_an_init_of_the_right_length_passes(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("N", 3)),
                "a.ddd.json": component(
                    "A", declare("local", "X", dimensions=["N"], init=[1, 2, 3])
                ),
            },
        )
        assert checks(bag) == []

    def test_a_structured_array_expands_over_the_value(self, tree: Path) -> None:
        """The instance carries both spellings, and its leaves sit at numeric paths."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "constants.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "constants.ddd.json": constants(constant("CELLS", 2), constant("TAPS", 4)),
                "types.ddd.json": struct_type("Cell_t", value_member("raw", dimensions=["TAPS"])),
                "a.ddd.json": component(
                    "A", declare("local", "Inlet", typename="Cell_t", dimensions=["CELLS"])
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        (instance,) = dictionary.instances
        assert instance.shape == (2,)
        assert instance.dimensions == ("CELLS",)
        assert [leaf.path for leaf in dictionary.leaves] == [
            "Inlet[0].raw",
            "Inlet[1].raw",
        ]
        leaf = dictionary.leaves[0]
        assert leaf.shape == (4,)
        assert leaf.dimensions == ("TAPS",)
        (declared_type,) = dictionary.types
        assert declared_type.members[0].dimensions == ("TAPS",)

    def test_the_a2l_dimension_count_uses_the_values(self, tree: Path) -> None:
        """Four dimensions are four however they are spelled."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("N", 2)),
                "a.ddd.json": component(
                    "A", declare("local", "X", dimensions=["N", "N", "N", "N"])
                ),
            },
        )
        assert checks(bag) == ["a2l-unrepresentable"]


class TestNameChecks:
    def test_a_reserved_constant_name_is_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json"),
                "constants.ddd.json": constants(constant("__CELLS", 8)),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        assert "constants.ddd.json#constants[0].name" in messages(bag)

    def test_a_constant_cannot_share_a_name_with_a_variable(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("Speed", 8)),
                "a.ddd.json": component("A", declare("local", "Speed")),
            },
        )
        assert checks(bag) == ["name-collision"]
        rendered = messages(bag)
        assert "declared as a variable and is also a declared constant" in rendered
        assert "constant declared here" in rendered

    def test_a_constant_cannot_share_a_name_with_an_enum_or_enumerator(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("Mode_t", 8), constant("MODE_OFF", 2)),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "X",
                        conversion={"name": "Mode_t", "enumerators": {"MODE_OFF": 0}},
                    ),
                ),
            },
        )
        assert checks(bag) == ["name-collision", "name-collision"]
        rendered = messages(bag)
        assert "'MODE_OFF' is a declared constant and also an enumerator of enum" in rendered
        assert "'Mode_t' is a declared constant and also the name of an enum" in rendered

    def test_a_constant_cannot_share_a_name_with_a_declared_type(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "constants.ddd.json", "types.ddd.json"),
                "constants.ddd.json": constants(constant("Temp_t", 8)),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Temp_t",
                            "datatype": "uint16",
                            "conversion": {},
                        }
                    ]
                },
            },
        )
        assert checks(bag) == ["name-collision"]
        assert "'Temp_t' is a declared constant and also the name of a type" in messages(bag)


def _vocabulary_project(*declarations: dict[str, Any]) -> dict[str, Any]:
    return {
        "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
        "constants.ddd.json": constants(
            constant("PRESSURE_CELLS", 8, "cells of the manifold"), constant("TAPS", 2)
        ),
        "a.ddd.json": component("A", *declarations),
    }


class TestGeneratedC:
    def test_an_array_is_declared_by_the_constant_name(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"], init=7)),
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        # The definition and the declaration both spell the name; the initialiser is laid
        # out over the resolved value, eight elements of it.
        assert (
            "uint8_t Cells[PRESSURE_CELLS] = { 7U, 7U, 7U, 7U, 7U, 7U, 7U, 7U };"
            in (files["ddd_globals.c"])
        )
        assert "extern uint8_t Cells[PRESSURE_CELLS];" in files["A.h"]

    def test_the_example_templates_emit_the_constants(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"])),
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        header = files["ddd_types.h"]
        assert "#define PRESSURE_CELLS 8 /**< cells of the manifold */" in header
        assert "#define TAPS 2\n" in header  # no description, no comment

    def test_without_constants_no_block_is_emitted(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "named constants" not in files["ddd_types.h"]

    def test_a_structured_array_and_its_members_spell_their_constants(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "constants.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "constants.ddd.json": constants(constant("CELLS", 2), constant("TAPS", 4)),
                "types.ddd.json": struct_type("Cell_t", value_member("raw", dimensions=["TAPS"])),
                "a.ddd.json": component(
                    "A", declare("local", "Inlet", typename="Cell_t", dimensions=["CELLS"])
                ),
            },
        )
        assert dictionary is not None, [d.render() for d in bag]
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "uint16_t raw[TAPS];" in files["ddd_types.h"]
        assert "Cell_t Inlet[CELLS];" in files["ddd_globals.c"]


class TestA2l:
    def test_one_system_constant_per_declared_constant_in_name_order(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"], unit="")),
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        a2l = files["P.a2l"]
        block = a2l[a2l.index("/begin MOD_PAR") : a2l.index("/end MOD_PAR")]
        assert '"named constants of P"' in block
        assert block.index('SYSTEM_CONSTANT "PRESSURE_CELLS" "8"') < block.index(
            'SYSTEM_CONSTANT "TAPS" "2"'
        )
        # The MOD_PAR follows the MOD_COMMON, and every record keeps resolved numbers.
        assert a2l.index("/end MOD_COMMON") < a2l.index("/begin MOD_PAR")
        assert "MATRIX_DIM 8 1 1" in a2l

    def test_without_constants_no_mod_par_is_written(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "MOD_PAR" not in files["P.a2l"]


class TestTheDictionary:
    def test_the_dump_carries_the_constants_and_the_format(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"])),
        )
        assert dictionary is not None
        assert dictionary.format == DICTIONARY_FORMAT == 6
        assert [(c.name, c.value, c.description) for c in dictionary.constants] == [
            ("PRESSURE_CELLS", 8, "cells of the manifold"),
            ("TAPS", 2, ""),
        ]

    def test_the_dictionary_round_trips(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"])),
        )
        assert dictionary is not None
        target = tree / "dump.json"
        target.write_text(dictionary.model_dump_json(indent=2), encoding="utf-8")
        again = load_dictionary(target, DiagnosticBag())
        assert again == dictionary

    def test_an_older_dictionary_spells_its_dimensions_as_numbers(self) -> None:
        """A format 3 dump carries no ``dimensions``; the numbers are the spelling."""
        entry = ResolvedObject.model_validate(
            {
                "name": "X",
                "kind": "measurement",
                "datatype": "uint8",
                "conversion": {"kind": "identity"},
                "limits": {"min": 0, "max": 255},
                "shape": [8],
            }
        )
        assert entry.spelled_shape == (8,)
        assert entry.written_shape == ((8, 8),)

    def test_a_spelled_dictionary_reads_back_with_both_halves(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"])),
        )
        assert dictionary is not None
        entry = dictionary.by_name["Cells"]
        assert entry.spelled_shape == ("PRESSURE_CELLS",)
        assert entry.written_shape == (("PRESSURE_CELLS", 8),)

    @pytest.mark.parametrize("model", [ResolvedObject, ResolvedInstance, ResolvedLeaf])
    def test_a_spelling_that_contradicts_the_shape_is_refused(self, model: Any) -> None:
        parts: dict[str, Any] = {
            "name": "X",
            "kind": "measurement",
            "shape": [8],
            "dimensions": ["A", "B"],
        }
        if model is ResolvedObject:
            parts |= {
                "datatype": "uint8",
                "conversion": {"kind": "identity"},
                "limits": {"min": 0, "max": 255},
            }
        elif model is ResolvedInstance:
            parts |= {"type": "S_t"}
        else:
            parts = {
                "path": "X.raw",
                "instance": "X",
                "kind": "measurement",
                "datatype": "uint8",
                "conversion": {"kind": "identity"},
                "limits": {"min": 0, "max": 255},
                "shape": [8],
                "dimensions": ["A", "B"],
            }
        with pytest.raises(ValidationError, match="must agree"):
            model.model_validate(parts)


class TestComparingDeliveries:
    def deliveries(
        self, tree: Path, before: Any, after: Any, value: int = 8
    ) -> tuple[DataDictionary, DataDictionary]:
        baseline, _ = run_analysis(
            tree / "old",
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("N", 8)),
                "a.ddd.json": component("A", declare("local", "X", dimensions=before)),
            },
        )
        candidate, _ = run_analysis(
            tree / "new",
            {
                "project.ddd.json": project("P", "constants.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(constant("N", value)),
                "a.ddd.json": component("A", declare("local", "X", dimensions=after)),
            },
        )
        assert baseline is not None and candidate is not None
        return baseline, candidate

    def test_a_respelled_dimension_is_a_changed_interface(self, tree: Path) -> None:
        """The spelling is what the generated code carries, so it is interface even while
        the number stands."""
        from ddd.compare import compare

        baseline, candidate = self.deliveries(tree, [8], ["N"])
        bag = DiagnosticBag()
        compare(baseline, candidate, bag)
        assert checks(bag) == ["changed-interface"]
        assert "shape: [N] != [8]" in messages(bag)

    def test_a_revalued_constant_is_a_changed_interface(self, tree: Path) -> None:
        from ddd.compare import compare

        baseline, candidate = self.deliveries(tree, ["N"], ["N"], value=12)
        bag = DiagnosticBag()
        compare(baseline, candidate, bag)
        assert "changed-interface" in checks(bag)

    def test_the_same_spelling_and_value_compare_clean(self, tree: Path) -> None:
        from ddd.compare import compare

        baseline, candidate = self.deliveries(tree, ["N"], ["N"])
        bag = DiagnosticBag()
        compare(baseline, candidate, bag)
        assert checks(bag) == []

    def archived(self, dictionary: DataDictionary) -> DataDictionary:
        """The dictionary as a format 3 dump carried it: no spellings, no constants."""
        stripped = json.loads(dictionary.model_dump_json())
        stripped["format"] = 3
        for entry in stripped["objects"]:
            del entry["dimensions"]
        del stripped["constants"]
        return DataDictionary.model_validate(stripped)

    def test_an_older_baseline_compares_its_dimensions_by_value(self, tree: Path) -> None:
        """A format 3 baseline recorded no spellings, so only the values can disagree:
        adopting a constant for a dimension whose size stands is a clean migration, not a
        changed interface."""
        from ddd.compare import compare

        baseline, candidate = self.deliveries(tree, [8], ["N"])
        bag = DiagnosticBag()
        compare(self.archived(baseline), candidate, bag)
        assert checks(bag) == []

    def test_a_value_change_against_an_older_baseline_still_reports(self, tree: Path) -> None:
        """The deference is about the spelling only; a dimension of another size is a
        changed interface whichever format the baseline was dumped in."""
        from ddd.compare import compare

        baseline, candidate = self.deliveries(tree, [8], ["N"], value=12)
        bag = DiagnosticBag()
        compare(self.archived(baseline), candidate, bag)
        assert checks(bag) == ["changed-interface"]
        assert "shape: [N] != [8]" in messages(bag)


class TestTheListTable:
    def test_the_shape_column_shows_the_spelling(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import main

        write_tree(
            tree,
            _vocabulary_project(declare("local", "Cells", dimensions=["PRESSURE_CELLS"])),
        )
        assert main(["list", str(tree / "project.ddd.json")]) == 0
        out = capsys.readouterr().out
        assert "[PRESSURE_CELLS]" in out

    def test_the_schema_command_offers_the_constants_kind(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import main

        assert main(["schema", "constants"]) == 0
        schema = json.loads(capsys.readouterr().out)
        assert "constants" in schema["properties"]


class TestTheEditor:
    """Navigation, hover and rename around the constants, plus the standalone leniency."""

    def workspace(self, tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "constants.ddd.json", "types.ddd.json", "a.ddd.json"),
                "constants.ddd.json": constants(
                    constant("PRESSURE_CELLS", 8, "cells of the manifold")
                ),
                "types.ddd.json": struct_type(
                    "S_t",
                    value_member("raw", dimensions=["PRESSURE_CELLS"]),
                    value_member("plain", "uint8", dimensions=[2]),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Cells", dimensions=["PRESSURE_CELLS", 2]),
                    declare("local", "Ax", kind="axis", size="PRESSURE_CELLS", datatype="uint16"),
                ),
            },
        )
        return tmp_path / "p.ddd.json"

    def index_of(self, root: Path) -> Any:
        from ddd.lsp.navigation import index

        return index(load_workspace(root, DiagnosticBag()))

    def test_a_dimension_jumps_to_the_constant_that_states_it(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "a.ddd.json"
        (site,) = definition(
            built, read(path, {}), path, "component.interface[0].definition.dimensions[0]"
        )
        assert site.path == tmp_path / "constants.ddd.json"
        assert site.pointer == "constants[0]"

    def test_an_axis_size_and_a_member_dimension_jump_too(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "a.ddd.json"
        (site,) = definition(built, read(path, {}), path, "component.interface[1].definition.size")
        assert site.pointer == "constants[0]"
        types = tmp_path / "types.ddd.json"
        (site,) = definition(built, read(types, {}), types, "types[0].members[0].dimensions[0]")
        assert site.pointer == "constants[0]"

    def test_inside_the_constants_file_the_name_answers_for_itself(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "constants.ddd.json"
        (site,) = definition(built, read(path, {}), path, "constants[0].name")
        assert site.pointer == "constants[0]"

    def test_a_name_nobody_declares_jumps_nowhere(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition
        from ddd.lsp.ranges import read

        root = self.workspace(tmp_path)
        path = tmp_path / "a.ddd.json"
        rewritten = json.loads(path.read_text(encoding="utf-8"))
        rewritten["component"]["interface"][0]["definition"]["dimensions"][0] = "MISSING"
        path.write_text(json.dumps(rewritten, indent=2), encoding="utf-8")
        built = self.index_of(root)
        found = definition(
            built, read(path, {}), path, "component.interface[0].definition.dimensions[0]"
        )
        assert found == []

    def test_an_integer_dimension_still_jumps_to_the_declaration(self, tmp_path: Path) -> None:
        """A number names no constant, so the wide rule answers: the object's producer."""
        from ddd.lsp.navigation import definition
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "a.ddd.json"
        (site,) = definition(
            built, read(path, {}), path, "component.interface[0].definition.dimensions[1]"
        )
        assert site.pointer == "component.interface[0].definition"

    def test_references_list_the_declaration_and_every_use(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import references
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "constants.ddd.json"
        found = references(built, read(path, {}), "constants[0].name")
        assert {(site.path.name, site.pointer) for site in found} == {
            ("constants.ddd.json", "constants[0]"),
            ("a.ddd.json", "component.interface[0].definition.dimensions[0]"),
            ("a.ddd.json", "component.interface[1].definition.size"),
            ("types.ddd.json", "types[0].members[0].dimensions[0]"),
        }

    def test_a_reference_from_an_undeclared_spelling_answers_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import references
        from ddd.lsp.ranges import read

        built = self.index_of(self.workspace(tmp_path))
        path = tmp_path / "a.ddd.json"
        rewritten = json.loads(path.read_text(encoding="utf-8"))
        rewritten["component"]["interface"][0]["definition"]["dimensions"][0] = "MISSING"
        path.write_text(json.dumps(rewritten, indent=2), encoding="utf-8")
        assert (
            references(
                built,
                read(path, {}),
                "component.interface[0].definition.dimensions[0]",
            )
            == []
        )

    def test_renaming_an_object_to_a_constant_name_is_refused(self, tmp_path: Path) -> None:
        """A rename that lands on a constant merges two identifiers in the generated c."""
        from ddd.lsp.navigation import rename_problem

        built = self.index_of(self.workspace(tmp_path))
        refused = rename_problem(built, "PRESSURE_CELLS")
        assert refused is not None
        assert "declared constant 'PRESSURE_CELLS'" in refused

    def hovered(self, tmp_path: Path, path: Path, pointer: str) -> Any:
        import io

        from ddd.lsp.ranges import Document
        from ddd.lsp.server import Server
        from test_lsp import build_record, framed, sent

        build_record(tmp_path, tmp_path / "p.ddd.json")
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        writer = io.BytesIO()
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }
        Server(framed(request), writer, root=tmp_path).run()
        (answer,) = sent(writer)
        return answer["result"]

    def test_hover_on_a_use_site_shows_the_constant(self, tmp_path: Path) -> None:
        self.workspace(tmp_path)
        result = self.hovered(
            tmp_path,
            tmp_path / "a.ddd.json",
            "component.interface[0].definition.dimensions[0]",
        )
        value = result["contents"]["value"]
        assert "**PRESSURE_CELLS** = 8" in value
        assert "cells of the manifold" in value

    def test_hover_in_the_constants_file_shows_the_entry(self, tmp_path: Path) -> None:
        self.workspace(tmp_path)
        result = self.hovered(tmp_path, tmp_path / "constants.ddd.json", "constants[0].name")
        assert "**PRESSURE_CELLS** = 8" in result["contents"]["value"]

    def test_hover_on_a_description_of_a_constant_says_nothing(self, tmp_path: Path) -> None:
        """Free text names no constant, and a constants file declares no data object."""
        self.workspace(tmp_path)
        assert (
            self.hovered(tmp_path, tmp_path / "constants.ddd.json", "constants[0].description")
            is None
        )

    def test_a_constants_file_alone_resolves_to_no_hover(self, tmp_path: Path) -> None:
        """No build and no project claim the file, so there is nothing to resolve against."""
        import io

        from ddd.lsp.ranges import Document
        from ddd.lsp.server import Server
        from test_lsp import framed, sent

        write_tree(tmp_path, {"constants.ddd.json": constants(constant("PRESSURE_CELLS", 8))})
        path = tmp_path / "constants.ddd.json"
        position = Document(path.read_text(encoding="utf-8")).range_of("constants[0].name")["start"]
        writer = io.BytesIO()
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }
        Server(framed(request), writer, root=tmp_path).run()
        (answer,) = sent(writer)
        assert answer["result"] is None

    def test_a_constant_without_a_description_hovers_without_one(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe_constant

        dictionary, _ = run_analysis(
            tmp_path,
            {
                "project.ddd.json": project("P", "constants.ddd.json"),
                "constants.ddd.json": constants(constant("N", 4)),
            },
        )
        assert dictionary is not None
        assert describe_constant(dictionary, "N") == "**N** = 4 — declared constant"
        assert describe_constant(dictionary, "MISSING") is None

    def test_a_lonely_file_holds_the_unknown_constant_back(self, tmp_path: Path) -> None:
        """The seventh of the checks that need every component of a project."""
        from ddd.lsp import diagnostics as service

        write_tree(
            tmp_path,
            {
                "lonely.ddd.json": component(
                    "Lonely", declare("local", "X", dimensions=["ELSEWHERE"])
                )
            },
        )
        reports = service.collect([], [tmp_path / "lonely.ddd.json"])
        # 'X' is a producing declaration with no 'id', and that finding needs no other
        # component to be right either, so it is the one thing standalone mode still says.
        assert {entry["code"] for findings in reports.values() for entry in findings} == {
            "missing-id"
        }

    def test_a_lonely_file_still_reports_what_no_constant_is_needed_for(
        self, tmp_path: Path
    ) -> None:
        """The held back unknown-constant drops the declaration, not the whole file's
        checks: an init outside the datatype needs no other component to be wrong."""
        from ddd.lsp import diagnostics as service

        write_tree(
            tmp_path,
            {
                "lonely.ddd.json": component(
                    "Lonely", declare("local", "X", dimensions=["ELSEWHERE"], init=999)
                )
            },
        )
        reports = service.collect([], [tmp_path / "lonely.ddd.json"])
        assert {entry["code"] for findings in reports.values() for entry in findings} == {
            "init-invalid",
            "missing-id",
        }

    def test_exactly_nine_checks_need_every_component(self) -> None:
        """``incomplete-project`` is one of them, and has to be.

        It reports that a declaration is missing from the dictionary, which is true of a file
        read on its own for the same reason the other eight are wrong about one: the constant,
        the raster or the type is declared, in a file only the project lists. In a run that was
        shown the whole project it is the finding that stops a relaxed check from quietly
        shrinking the dictionary.
        """
        from ddd.diagnostics import CHECKS

        assert {name for name, check in CHECKS.items() if check.needs_every_component} == {
            "unknown-type",
            "unknown-unit",
            "unknown-section",
            "unknown-constant",
            "unknown-raster",
            "missing-producer",
            "unknown-reference",
            "unused-output",
            "incomplete-project",
        }
