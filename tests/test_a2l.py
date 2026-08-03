"""Tests for the generated a2l file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, project, render_files, run_analysis
from ddd.backends import ByteOrder, load_address_map
from ddd.backends.a2l.model import a2l_string


def a2l(tree: Path, *declarations: dict[str, Any], **options: Any) -> str:
    files = {
        "project.ddd.json": project("Device", "a.ddd.json"),
        "a.ddd.json": component("A", *declarations, description="a component"),
    }
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [d.render() for d in bag]
    rendered = render_files(dictionary, tree / "gen", **options)
    content = next(file.content for file in rendered if file.path.name == "Device.a2l")
    return content


class TestStructure:
    def test_skeleton(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X"))
        assert "ASAP2_VERSION 1 61" in content
        assert "/begin PROJECT Device" in content
        assert "/begin MODULE Device" in content
        assert content.rstrip().endswith("/end PROJECT")
        assert content.count("/begin") == content.count("/end")

    def test_byte_order(self, tree: Path) -> None:
        assert "BYTE_ORDER MSB_LAST" in a2l(tree, declare("local", "X"))
        assert "BYTE_ORDER MSB_FIRST" in a2l(tree, declare("local", "X"), byte_order=ByteOrder.BIG)

    def test_component_group(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X"))
        assert '/begin GROUP A "a component"' in content
        assert "ROOT" in content
        assert "/begin REF_MEASUREMENT\n        X\n      /end REF_MEASUREMENT" in content


class TestMeasurements:
    def test_plain_measurement(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X", "uint16", description="a signal"))
        assert '/begin MEASUREMENT X "a signal"' in content
        assert "UWORD NO_COMPU_METHOD 0 0 0 65535" in content
        assert "ECU_ADDRESS 0x00000000" in content
        assert 'SYMBOL_LINK "X" 0' in content

    def test_matrix_dim_lists_the_fastest_index_first(self, tree: Path) -> None:
        """``uint16_t X[2][3]`` is three columns per row, and a2l names that dimension first.

        Emitting the c order would describe the transposed object, and a calibration tool
        computing ``x + y * xDim`` would then read and write the wrong element.
        """
        content = a2l(tree, declare("local", "X", dimensions=[2, 3]))
        assert "MATRIX_DIM 3 2 1" in content

    def test_matrix_dim_pads_a_one_dimensional_array(self, tree: Path) -> None:
        """ASAP2 1.6.1 always spells out three dimensions; the unused ones are 1."""
        content = a2l(tree, declare("local", "X", dimensions=[4]))
        assert "MATRIX_DIM 4 1 1" in content

    def test_export_can_be_disabled(self, tree: Path) -> None:
        content = a2l(
            tree, declare("local", "Visible"), declare("local", "Hidden", a2l={"export": False})
        )
        assert "MEASUREMENT Visible" in content
        assert "Hidden" not in content

    def test_an_unstated_export_still_reaches_the_a2l(self, tree: Path) -> None:
        """A dictionary that says nothing about exporting is not asking to be left out.

        ``export`` is a tri-state so that several components can be asked whether an object
        belongs in the file. Reading the unstated third state as "no" would empty the a2l of
        every dictionary written before the key existed, and of every one a third party hands
        over without an a2l block at all.
        """
        content = a2l(tree, declare("local", "X", a2l={"format": "%8.2"}))
        assert "MEASUREMENT X" in content

    def test_format_and_display_identifier(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare("local", "X", a2l={"format": "%8.2", "display_identifier": "Xdisp"}),
        )
        assert 'FORMAT "%8.2"' in content
        assert "DISPLAY_IDENTIFIER Xdisp" in content

    def test_condition_is_documented(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X", condition="defined(F)"))
        assert "/* only present in the build when: defined(F) */" in content

    def test_address_map(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X"), addresses={"X": 0x20000100})
        assert "ECU_ADDRESS 0x20000100" in content

    def test_limits_are_physical(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X", "sint16", conversion={"factor": 0.1}))
        assert "SWORD CM_LIN_NONE 0 0 -3276.8 3276.7" in content


class TestCompuMethods:
    def test_rat_func_coefficients(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare("local", "X", "sint16", unit="degC", conversion={"factor": 0.5, "offset": -40}),
        )
        assert '/begin COMPU_METHOD CM_LIN_DEGC "phys = raw * 0.5 + -40"' in content
        assert 'RAT_FUNC "%8.3" "degC"' in content
        # raw = (phys - offset) / factor  ->  COEFFS 0 1 -offset 0 0 factor
        assert "COEFFS 0 1 40 0 0 0.5" in content

    def test_identity_with_unit(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X", "float32", unit="V"))
        assert "CM_IDENT_V" in content
        assert 'IDENTICAL "%8.3" "V"' in content

    def test_identity_without_unit_uses_no_compu_method(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X"))
        assert "NO_COMPU_METHOD" in content
        assert "COMPU_METHOD CM_" not in content

    def test_identical_conversions_are_shared(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare("local", "X", "uint16", unit="Hz", conversion={"factor": 0.25}),
            declare("local", "Y", "uint16", unit="Hz", conversion={"factor": 0.25}),
        )
        assert content.count("/begin COMPU_METHOD") == 1
        assert content.count("CM_LIN_HZ") == 3  # definition plus two references

    def test_different_units_get_different_methods(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare("local", "X", "uint16", unit="Hz", conversion={"factor": 0.25}),
            declare("local", "Y", "uint16", unit="m/s", conversion={"factor": 0.25}),
        )
        assert "CM_LIN_HZ" in content
        assert "CM_LIN_M_PER_S" in content

    def test_unit_symbols_are_transliterated(self, tree: Path) -> None:
        content = a2l(tree, declare("local", "X", "uint8", unit="%", conversion={"factor": 0.5}))
        assert "CM_LIN_PCT" in content
        assert '"%"' in content

    def test_enum_becomes_a_verbal_table(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare(
                "local",
                "X",
                conversion={"kind": "enum", "name": "Mode_t", "enumerators": {"OFF": 0, "ON": 1}},
            ),
        )
        assert '/begin COMPU_VTAB VTAB_Mode_t "values of Mode_t" TAB_VERB 2' in content
        assert '      0 "OFF"\n      1 "ON"' in content
        assert "COMPU_TAB_REF VTAB_Mode_t" in content
        assert "UBYTE CM_Mode_t 0 0 0 1" in content


class TestHelpers:
    def test_string_escaping(self) -> None:
        assert a2l_string('a "b" \\ c\nd') == 'a \\"b\\" \\\\ c d'

    def test_address_map_accepts_hex_and_decimal(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text('{"A": "0x1000", "B": 32, "C": "40"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x1000, "B": 32, "C": 40}

    @pytest.mark.parametrize("value", ['"ff"', "true", "null", "[1]"])
    def test_address_map_rejects_anything_else(self, tree: Path, value: str) -> None:
        path = tree / "addresses.json"
        path.write_text(f'{{"A": {value}}}', encoding="utf-8")
        with pytest.raises(ValueError, match="is not a number"):
            load_address_map(path)

    def test_address_map_must_be_an_object(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ValueError, match="expected a json object"):
            load_address_map(path)
