"""Tests for the calibration data objects: parameter, value block, curve, map and axis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from conftest import checks, component, declare, messages, project, render_files, run_analysis
from ddd.models import AnyDataObject, Axis, Curve, Map, ObjectKind, Parameter, ValueBlock

DEFINITION = TypeAdapter(AnyDataObject)


def axis(name: str = "Ax", size: int = 3, **extra: Any) -> dict[str, Any]:
    return declare("local", name, "uint16", kind="axis", size=size, **extra)


def generate(tree: Path, *declarations: dict[str, Any], **options: Any) -> dict[str, str]:
    files = {
        "project.ddd.json": project("Device", "a.ddd.json"),
        "a.ddd.json": component("A", *declarations, description="a component"),
    }
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [d.render() for d in bag]
    assert not bag.has_errors, [d.render() for d in bag]
    rendered = render_files(dictionary, tree / "gen", **options)
    return {file.path.name: file.content for file in rendered}


class TestContract:
    def test_kind_defaults_to_measurement(self) -> None:
        definition = DEFINITION.validate_python({"name": "X", "datatype": "uint8"})
        assert definition.kind is ObjectKind.MEASUREMENT
        assert not definition.is_calibration

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ({"kind": "parameter"}, Parameter),
            ({"kind": "value_block", "dimensions": [2]}, ValueBlock),
            ({"kind": "axis", "size": 3}, Axis),
            ({"kind": "curve", "axis": "Ax"}, Curve),
            ({"kind": "map", "x_axis": "Ax", "y_axis": "Ay"}, Map),
        ],
    )
    def test_kinds(self, payload: dict[str, Any], expected: type) -> None:
        definition = DEFINITION.validate_python({"name": "X", "datatype": "uint8", **payload})
        assert isinstance(definition, expected)
        assert definition.is_calibration

    def test_a_parameter_has_no_dimensions(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DEFINITION.validate_python(
                {"kind": "parameter", "name": "X", "datatype": "uint8", "dimensions": [2]}
            )

    def test_a_value_block_needs_dimensions(self) -> None:
        with pytest.raises(ValidationError):
            DEFINITION.validate_python({"kind": "value_block", "name": "X", "datatype": "uint8"})

    def test_an_axis_needs_a_size(self) -> None:
        with pytest.raises(ValidationError):
            DEFINITION.validate_python({"kind": "axis", "name": "X", "datatype": "uint8"})

    def test_a_curve_needs_an_axis(self) -> None:
        with pytest.raises(ValidationError):
            DEFINITION.validate_python({"kind": "curve", "name": "X", "datatype": "uint8"})

    def test_calibration_objects_are_never_volatile(self) -> None:
        definition = DEFINITION.validate_python(
            {"kind": "parameter", "name": "X", "datatype": "uint8"}
        )
        assert definition.volatile is False
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DEFINITION.validate_python(
                {"kind": "parameter", "name": "X", "datatype": "uint8", "volatile": True}
            )

    def test_the_shape_of_a_curve_is_unknown_to_the_contract(self) -> None:
        curve = DEFINITION.validate_python(
            {"kind": "curve", "name": "X", "datatype": "uint8", "axis": "Ax"}
        )
        assert curve.declared_shape is None
        assert curve.references == {"axis": "Ax"}


class TestResolution:
    def test_a_curve_takes_its_shape_from_the_axis(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    axis("Ax", 5),
                    declare("local", "C", "uint8", kind="curve", axis="Ax"),
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["C"].shape == (5,)

    def test_a_map_is_stored_row_wise(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    axis("Ax", 6),
                    axis("Ay", 4),
                    declare("local", "M", "uint8", kind="map", x_axis="Ax", y_axis="Ay"),
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        # [y][x]: the x index runs fastest, which the a2l calls ROW_DIR
        assert dictionary.by_name["M"].shape == (4, 6)

    def test_an_axis_may_live_in_another_component(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Ax", "uint16", kind="axis", size=3)
                ),
                "b.ddd.json": component(
                    "B",
                    declare("input", "Ax", "uint16", kind="axis", size=3),
                    declare("local", "C", "uint8", kind="curve", axis="Ax"),
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["C"].shape == (3,)

    def test_unknown_axis(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "C", "uint8", kind="curve", axis="Ax")
                ),
            },
        )
        assert checks(bag) == ["unknown-reference"]
        assert "refers to 'Ax' as its axis" in messages(bag)

    def test_reference_with_the_wrong_kind(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "NotAnAxis", "uint8"),
                    declare("local", "C", "uint8", kind="curve", axis="NotAnAxis"),
                ),
            },
        )
        assert checks(bag) == ["reference-kind"]
        assert "must be of kind 'axis', but 'NotAnAxis' is of kind 'measurement'" in messages(bag)

    def test_unknown_input_quantity_of_an_axis(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", axis("Ax", 3, input="Nope")),
            },
        )
        assert checks(bag) == ["unknown-reference"]

    def test_init_shape_of_a_curve_is_checked_against_the_axis(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    axis("Ax", 3),
                    declare("local", "C", "uint8", kind="curve", axis="Ax", init=[1, 2]),
                ),
            },
        )
        assert checks(bag) == ["init-invalid"]
        assert "has the shape [3] given by its axes: init has 2 elements" in messages(bag)

    def test_components_must_agree_on_the_kind(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", "uint8", kind="parameter")),
                "b.ddd.json": component("B", declare("input", "X", "uint8")),
            },
        )
        assert "definition-mismatch" in checks(bag)
        assert "kind: measurement != parameter" in messages(bag)

    def test_components_must_agree_on_the_axis(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    axis("Ax", 3),
                    declare("output", "C", "uint8", kind="curve", axis="Ax"),
                ),
                "b.ddd.json": component(
                    "B",
                    axis("Other", 3),
                    declare("input", "C", "uint8", kind="curve", axis="Other"),
                ),
            },
        )
        assert "definition-mismatch" in checks(bag)
        assert "references: axis=Other != axis=Ax" in messages(bag)


class TestCodeGeneration:
    def test_calibration_data_is_const(self, tree: Path) -> None:
        files = generate(
            tree,
            declare("local", "P", "uint16", kind="parameter", init=7),
            declare("local", "M", "uint16"),
        )
        source = files["ddd_globals.c"]
        assert "const uint16_t P = 7U;" in source
        assert "uint16_t M;" in source
        assert "const uint16_t M;" not in source

    def test_sections_separate_ram_from_calibration_data(self, tree: Path) -> None:
        files = generate(
            tree,
            declare("local", "M", "uint16"),
            declare("local", "P", "uint16", kind="parameter"),
        )
        source = files["ddd_globals.c"]
        assert "/* measurements */" in source
        assert source.index("/* measurements */") < source.index("/* calibration data */")

    def test_curve_and_map_arrays(self, tree: Path) -> None:
        files = generate(
            tree,
            axis("Ax", 3),
            axis("Ay", 2),
            declare("local", "C", "uint8", kind="curve", axis="Ax", init=[1, 2, 3]),
            declare(
                "local",
                "M",
                "uint8",
                kind="map",
                x_axis="Ax",
                y_axis="Ay",
                init=[[1, 2, 3], [4, 5, 6]],
            ),
        )
        source = files["ddd_globals.c"]
        assert "const uint8_t C[3] = { 1U, 2U, 3U };" in source
        assert "const uint8_t M[2][3] = {\n    { 1U, 2U, 3U },\n    { 4U, 5U, 6U }\n};" in source
        assert "const uint16_t Ax[3]" in source

    def test_scalar_init_is_broadcast_over_the_axis(self, tree: Path) -> None:
        files = generate(
            tree, axis("Ax", 4), declare("local", "C", "uint8", kind="curve", axis="Ax", init=9)
        )
        assert "const uint8_t C[4] = { 9U, 9U, 9U, 9U };" in files["ddd_globals.c"]

    def test_comment_names_the_axes(self, tree: Path) -> None:
        files = generate(
            tree,
            axis("Ax", 3),
            declare("local", "C", "uint8", kind="curve", axis="Ax", description="feed forward"),
        )
        assert "/** feed forward (calibration curve over Ax) */" in files["ddd_globals.c"]

    def test_const_inputs_does_not_duplicate_const(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "P", "uint8", kind="parameter")),
                "b.ddd.json": component("B", declare("input", "P", "uint8", kind="parameter")),
            },
        )
        assert dictionary is not None
        assert not bag.has_errors
        files = {
            file.path.name: file.content
            for file in render_files(dictionary, tree / "gen", const_inputs=True)
        }
        assert "extern const uint8_t P;" in files["B.h"]
        assert "const const" not in files["B.h"]


class TestA2l:
    def a2l(self, tree: Path, *declarations: dict[str, Any]) -> str:
        return generate(tree, *declarations)["Device.a2l"]

    def test_parameter_becomes_a_value_characteristic(self, tree: Path) -> None:
        content = self.a2l(tree, declare("local", "P", "uint16", kind="parameter"))
        layout = "/begin RECORD_LAYOUT RL_VALUES_UWORD\n      FNC_VALUES 1 UWORD ROW_DIR DIRECT"
        assert layout in content
        assert "VALUE 0x00000000 RL_VALUES_UWORD 0 NO_COMPU_METHOD 0 65535" in content
        assert 'SYMBOL_LINK "P" 0' in content

    def test_value_block_carries_a_matrix_dim(self, tree: Path) -> None:
        content = self.a2l(
            tree, declare("local", "V", "uint8", kind="value_block", dimensions=[2, 3])
        )
        assert "VAL_BLK 0x00000000 RL_VALUES_UBYTE" in content
        # The c declaration is [2][3]; a2l lists the fastest running index first.
        assert "MATRIX_DIM 3 2 1" in content

    def test_axis_becomes_axis_pts(self, tree: Path) -> None:
        content = self.a2l(tree, declare("local", "Speed", "uint16"), axis("Ax", 5, input="Speed"))
        assert "AXIS_PTS_X 1 UWORD INDEX_INCR DIRECT" in content
        assert "0x00000000 Speed RL_AXIS_UWORD 0 NO_COMPU_METHOD 5 0 65535" in content

    def test_axis_without_input_quantity(self, tree: Path) -> None:
        content = self.a2l(tree, axis("Ax", 5))
        assert "0x00000000 NO_INPUT_QUANTITY RL_AXIS_UWORD 0 NO_COMPU_METHOD 5 0 65535" in content

    def test_curve_refers_to_its_axis(self, tree: Path) -> None:
        content = self.a2l(
            tree, axis("Ax", 5), declare("local", "C", "uint8", kind="curve", axis="Ax")
        )
        assert "CURVE 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255" in content
        assert (
            "/begin AXIS_DESCR\n        COM_AXIS NO_INPUT_QUANTITY NO_COMPU_METHOD 5 0 65535\n"
            "        AXIS_PTS_REF Ax\n      /end AXIS_DESCR" in content
        )

    def test_map_has_the_x_axis_first(self, tree: Path) -> None:
        content = self.a2l(
            tree,
            axis("Ax", 6),
            axis("Ay", 4),
            declare("local", "M", "uint8", kind="map", x_axis="Ax", y_axis="Ay"),
        )
        assert content.index("AXIS_PTS_REF Ax") < content.index("AXIS_PTS_REF Ay")
        assert content.count("/begin AXIS_DESCR") == 2

    def test_group_references_both_kinds(self, tree: Path) -> None:
        content = self.a2l(
            tree,
            declare("local", "M", "uint16"),
            declare("local", "P", "uint16", kind="parameter"),
        )
        assert "/begin REF_MEASUREMENT\n        M\n      /end REF_MEASUREMENT" in content
        assert "/begin REF_CHARACTERISTIC\n        P\n      /end REF_CHARACTERISTIC" in content

    def test_an_axis_needed_by_a_curve_is_always_exported(self, tree: Path) -> None:
        content = self.a2l(
            tree,
            declare("local", "Ax", "uint16", kind="axis", size=3, a2l={"export": False}),
            declare("local", "C", "uint8", kind="curve", axis="Ax"),
        )
        assert "/begin AXIS_PTS Ax" in content
        assert "AXIS_PTS_REF Ax" in content

    def test_record_layouts_are_shared(self, tree: Path) -> None:
        content = self.a2l(
            tree,
            declare("local", "P", "uint16", kind="parameter"),
            declare("local", "Q", "uint16", kind="parameter"),
        )
        assert content.count("/begin RECORD_LAYOUT") == 1

    def test_balanced_blocks(self, tree: Path) -> None:
        content = self.a2l(
            tree,
            declare("local", "Speed", "uint16"),
            axis("Ax", 6, input="Speed"),
            axis("Ay", 4),
            declare("local", "M", "uint8", kind="map", x_axis="Ax", y_axis="Ay"),
            declare("local", "C", "uint8", kind="curve", axis="Ax"),
            declare("local", "P", "uint16", kind="parameter"),
            declare("local", "V", "uint8", kind="value_block", dimensions=[4]),
        )
        assert content.count("/begin") == content.count("/end")
