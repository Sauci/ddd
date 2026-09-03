"""Tests for the pydantic contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis
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
    storage: dict[str, object] = (
        {} if "typename" in kwargs else {"datatype": "uint8", "conversion": {"kind": "identity"}}
    )
    return Measurement.model_validate(
        {"name": "X", "kind": "measurement", "volatile": False, **storage, **kwargs}
    )


class TestDatatype:
    """The core knows the storage properties; the spelling belongs to the backends."""

    @pytest.mark.parametrize(
        ("datatype", "size"),
        [
            (Datatype.BOOLEAN, 1),
            (Datatype.UINT8, 1),
            (Datatype.SINT16, 2),
            (Datatype.UINT32, 4),
            (Datatype.SINT64, 8),
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
        assert Datatype.SINT16.raw_min == -32768
        assert Datatype.BOOLEAN.is_integer is False
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
    def test_the_conversion_is_required_beside_a_datatype(self) -> None:
        """The identity is derivable, which is exactly why it is asked for: raw equalling
        physical is an engineering claim, and a forgotten scaling displays raw counts."""
        import pytest
        from pydantic import ValidationError

        payload = {"name": "X", "datatype": "uint8", "kind": "measurement", "volatile": False}
        with pytest.raises(ValidationError, match="comes with a 'conversion'"):
            Measurement.model_validate(payload)

    def test_an_empty_object_is_the_identity(self) -> None:
        assert isinstance(definition(conversion={}).conversion, IdentityConversion)

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
                    "kind": "measurement",
                    "name": "X",
                    "datatype": "float32",
                    "volatile": False,
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
            {
                "kind": "measurement",
                "name": "X",
                "datatype": "sint16",
                "volatile": False,
                "conversion": {"factor": 0.1},
            }
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

    def test_the_shape_of_an_init_is_not_a_contract_rule(self) -> None:
        """A wrong shape is ``init-invalid`` in the analysis, not a schema error here.

        Only part of the answer is written in the file - a curve takes its shape from an
        axis another declaration owns - so the analysis checks every kind in one place; see
        ``test_analysis.py``.
        """
        assert definition(dimensions=[2], init=[1, 2, 3]).init == (1, 2, 3)
        assert definition(init=[1, 2]).init == (1, 2)

    def test_zero_dimension_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            definition(dimensions=[0])


class TestContractStrictness:
    def test_unknown_keys_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            definition(typo=1)

    def test_component_requires_a_name(self) -> None:
        with pytest.raises(ValidationError):
            ComponentFile.model_validate({"component": {"interface": []}})

    def test_definitions_are_hashable(self) -> None:
        assert len({definition(), definition()}) == 1

    def test_blank_condition_becomes_none(self) -> None:
        model = ComponentFile.model_validate(
            {
                "component": {
                    "name": "C",
                    "interface": [
                        {
                            "scope": "output",
                            "condition": "   ",
                            "definition": {
                                "kind": "measurement",
                                "name": "X",
                                "datatype": "uint8",
                                "conversion": {},
                                "volatile": False,
                            },
                        }
                    ],
                }
            }
        )
        assert model.component.interface[0].condition is None

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


class TestObjectIdentity:
    def test_an_id_of_the_right_shape_is_accepted(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
            },
        )
        assert dictionary is not None, messages(bag)

    @pytest.mark.parametrize(
        "value",
        ["k7m2q9xr4t8", "k7m2q9xr4t8ww", "K7M2Q9XR4T8W", "k7m2q9xr4t8i", "k7m2-q9xr4t8", ""],
    )
    def test_an_id_of_the_wrong_shape_is_refused(self, tree: Path, value: str) -> None:
        """Too short, too long, upper case, an excluded letter, punctuation, empty."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", id=value)),
            },
        )
        assert "schema" in checks(bag), messages(bag)

    def test_a_consumer_may_not_state_an_identity(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", id="k7m2q9xr4t8w")),
                "b.ddd.json": component("B", declare("input", "X", id="p3rt5vwx9z2q")),
            },
        )
        assert checks(bag) == ["consumer-identity"], messages(bag)
        assert "'B', which reads it" in messages(bag)
