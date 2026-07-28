"""Tests for the pydantic contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ddd.models import (
    ComponentFile,
    ConversionRule,
    Datatype,
    EnumConversion,
    IdentityConversion,
    LinearConversion,
    Measurement,
    ProjectFile,
    broadcast,
    format_shape,
    is_reserved_identifier,
)


def definition(**kwargs: object) -> Measurement:
    return Measurement.model_validate({"name": "X", "datatype": "uint8", **kwargs})


class TestDatatype:
    """The core knows the storage properties; the spelling belongs to the backends."""

    @pytest.mark.parametrize(
        ("datatype", "size"),
        [
            (Datatype.BOOL, 1),
            (Datatype.UINT8, 1),
            (Datatype.INT16, 2),
            (Datatype.UINT32, 4),
            (Datatype.INT64, 8),
            (Datatype.FLOAT32, 4),
            (Datatype.FLOAT64, 8),
        ],
    )
    def test_size(self, datatype: Datatype, size: int) -> None:
        assert datatype.size == size

    def test_the_core_does_not_know_any_output_format(self) -> None:
        assert not hasattr(Datatype.UINT16, "c_type")
        assert not hasattr(Datatype.UINT16, "a2l_type")

    def test_ranges(self) -> None:
        assert Datatype.UINT8.raw_min == 0
        assert Datatype.UINT8.raw_max == 255
        assert Datatype.INT16.raw_min == -32768
        assert Datatype.BOOL.is_integer is False
        assert Datatype.FLOAT32.is_float is True


class TestIdentifiers:
    @pytest.mark.parametrize("name", ["int", "volatile", "_Bool", "__hidden", "a__b", "_Foo"])
    def test_reserved(self, name: str) -> None:
        assert is_reserved_identifier(name)

    @pytest.mark.parametrize("name", ["ValueE", "_speed", "x1", "a_b"])
    def test_allowed(self, name: str) -> None:
        assert not is_reserved_identifier(name)

    @pytest.mark.parametrize("name", ["1abc", "with space", "", "a-b"])
    def test_rejected_by_the_contract(self, name: str) -> None:
        with pytest.raises(ValidationError):
            definition(name=name)


class TestConversions:
    def test_default_is_identity(self) -> None:
        assert isinstance(definition().conversion, IdentityConversion)

    def test_kind_is_inferred_for_linear(self) -> None:
        conversion = definition(conversion={"factor": 0.5}).conversion
        assert isinstance(conversion, LinearConversion)
        assert conversion.factor == 0.5
        assert conversion.offset == 0.0

    def test_kind_is_inferred_for_enum(self) -> None:
        variable = definition(conversion={"name": "E", "enumerators": {"A": 0, "B": 1}})
        conversion = variable.conversion
        assert isinstance(conversion, EnumConversion)
        assert conversion.values == (0, 1)
        assert [e.name for e in conversion.enumerators] == ["A", "B"]

    def test_factor_zero_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="factor must not be zero"):
            definition(conversion={"kind": "linear", "factor": 0})

    def test_duplicate_enumerator_name_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate enumerator"):
            definition(
                conversion={
                    "kind": "enum",
                    "name": "E",
                    "enumerators": [{"name": "A", "value": 0}, {"name": "A", "value": 1}],
                }
            )

    def test_enum_needs_an_integer_datatype(self) -> None:
        with pytest.raises(ValidationError, match="requires an integer datatype"):
            Measurement.model_validate(
                {
                    "name": "X",
                    "datatype": "float32",
                    "conversion": {"kind": "enum", "name": "E", "enumerators": {"A": 0}},
                }
            )

    def test_physical_conversion(self) -> None:
        conversion = LinearConversion(factor=0.25, offset=-40.0)
        assert conversion.to_physical(4) == -39.0
        assert conversion.to_raw(-39.0) == 4


class TestLimits:
    def test_derived_from_datatype_and_conversion(self) -> None:
        limits = Measurement.model_validate(
            {"name": "X", "datatype": "int16", "conversion": {"factor": 0.1}}
        ).physical_limits()
        assert limits.min == pytest.approx(-3276.8)
        assert limits.max == pytest.approx(3276.7)

    def test_negative_factor_swaps_the_limits(self) -> None:
        limits = definition(conversion={"factor": -1.0}).physical_limits()
        assert (limits.min, limits.max) == (-255.0, 0.0)

    def test_explicit_limits_win(self) -> None:
        assert definition(limits={"min": 0, "max": 10}).physical_limits().as_tuple() == (0.0, 10.0)

    def test_inverted_limits_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="greater than max"):
            definition(limits={"min": 10, "max": 0})


class TestArraysAndInit:
    def test_dimensions_and_size(self) -> None:
        variable = definition(datatype="uint16", dimensions=[3, 4])
        assert variable.declared_shape == (3, 4)
        assert format_shape(variable.declared_shape) == "[3][4]"

    def test_scalar_init_is_broadcast(self) -> None:
        variable = definition(dimensions=[2, 2], init=7)
        assert broadcast(variable.init, variable.declared_shape) == ((7, 7), (7, 7))

    def test_nested_init_is_kept(self) -> None:
        variable = definition(dimensions=[2], init=[1, 2])
        assert broadcast(variable.init, variable.declared_shape) == (1, 2)

    def test_wrong_length_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="init has 3 elements, expected 2"):
            definition(dimensions=[2], init=[1, 2, 3])

    def test_list_for_a_scalar_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="but the object is a scalar"):
            definition(init=[1, 2])

    def test_zero_dimension_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            definition(dimensions=[0])


class TestContractStrictness:
    def test_unknown_keys_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            definition(typo=1)

    def test_component_requires_a_name(self) -> None:
        with pytest.raises(ValidationError):
            ComponentFile.model_validate({"component": {"declarations": []}})

    def test_definitions_are_hashable(self) -> None:
        assert len({definition(), definition()}) == 1

    def test_blank_condition_becomes_none(self) -> None:
        model = ComponentFile.model_validate(
            {
                "component": {
                    "name": "C",
                    "declarations": [
                        {
                            "scope": "output",
                            "condition": "   ",
                            "definition": {"name": "X", "datatype": "uint8"},
                        }
                    ],
                }
            }
        )
        assert model.component.declarations[0].condition is None

    def test_json_schema_is_generated(self) -> None:
        for model in (ProjectFile, ComponentFile):
            schema = model.model_json_schema()
            assert schema["type"] == "object"
            assert schema["additionalProperties"] is False


class TestConversionInterface:
    @pytest.mark.parametrize(
        "conversion",
        [
            IdentityConversion(),
            LinearConversion(factor=0.5, offset=-40.0),
            EnumConversion(name="E", enumerators={"A": 0}),
        ],
    )
    def test_every_variant_answers_the_same_three_questions(
        self, conversion: ConversionRule
    ) -> None:
        assert isinstance(conversion, ConversionRule)
        assert conversion.to_raw(conversion.to_physical(4)) == pytest.approx(4)
        assert conversion.describe()
