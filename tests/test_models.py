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

    def test_a_string_conversion_is_spelled_with_its_kind(self) -> None:
        """A string has no key of its own to be inferred from, so ``{}`` stays the identity."""
        from ddd.models import StringConversion

        parsed = definition(conversion={"kind": "string"}, dimensions=[8])
        assert isinstance(parsed.conversion, StringConversion)
        assert isinstance(parsed.conversion, ConversionRule)
        assert parsed.conversion.describe() == "string"
        assert isinstance(definition(conversion={}).conversion, IdentityConversion)

    def test_a_string_conversion_takes_no_other_key(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            definition(conversion={"kind": "string", "factor": 2}, dimensions=[8])

    def test_a_string_is_the_identity_on_one_byte(self) -> None:
        """Compared as written, ranged as its datatype, and one byte reads as nothing."""
        from ddd.models import StringConversion, conversion_identity, physical_range, raw_reading

        conversion = StringConversion(kind="string")
        assert conversion.to_physical(86) == 86
        assert conversion.to_raw(86) == 86
        assert conversion_identity(conversion) == {"kind": "string"}
        assert physical_range(conversion, 0, 255) == (0, 255)
        assert raw_reading(conversion, 86) is None


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

    def test_a_producing_declaration_without_an_identity_is_reported(self, tree: Path) -> None:
        """`missing-id` is silenced by default across the suite (see conftest.run_analysis),
        so this opts back in - otherwise the test would pass whether or not the check fires."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
            severities=["missing-id=info"],
        )
        assert "missing-id" in checks(bag), messages(bag)

    def test_a_reading_declaration_without_an_identity_is_not_reported(self, tree: Path) -> None:
        """The key is the producer's to state, so its absence is only the producer's silence."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", id="k7m2q9xr4t8w")),
                "b.ddd.json": component("B", declare("input", "X")),
            },
            severities=["missing-id=info"],
        )
        assert "missing-id" not in checks(bag), messages(bag)

    def test_two_objects_may_not_share_an_identity(self, tree: Path) -> None:
        """The likeliest real mistake: a declaration copied to make a new object."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
                "b.ddd.json": component("B", declare("local", "Y", id="k7m2q9xr4t8w")),
            },
        )
        assert "duplicate-id" in checks(bag), messages(bag)
        assert "'Y'" in messages(bag) and "'X'" in messages(bag)

    def test_three_objects_sharing_an_identity_all_point_at_the_first(self, tree: Path) -> None:
        """N=3 does not blow up pairwise: one finding per extra claimant, not one per pair."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
                "b.ddd.json": component("B", declare("local", "Y", id="k7m2q9xr4t8w")),
                "c.ddd.json": component("C", declare("local", "Z", id="k7m2q9xr4t8w")),
            },
        )
        findings = [diagnostic for diagnostic in bag if diagnostic.check == "duplicate-id"]
        assert len(findings) == 2, messages(bag)
        finding_for_y, finding_for_z = findings
        assert "'Y'" in finding_for_y.message and "'X'" in finding_for_y.message, messages(bag)
        assert "'Z'" in finding_for_z.message and "'X'" in finding_for_z.message, messages(bag)
        # The note is what an editor follows to the other declaration - pointing at the
        # first object's own declaration, not back at the second one reporting it.
        note_text, note_location = finding_for_y.notes[0]
        assert note_text == "first carries the id here"
        assert note_location is not None
        assert note_location.path.name == "a.ddd.json"


class TestQuotedNumbers:
    """The published schema says integer; a quoted number is refused where it is written."""

    def test_an_enumerator_value_must_be_a_number(self) -> None:
        from ddd.models import EnumConversion

        with pytest.raises(ValidationError):
            EnumConversion.model_validate(
                {"kind": "enum", "name": "S", "enumerators": [{"name": "OFF", "value": "0"}]}
            )

    def test_a_raster_event_must_be_a_number(self) -> None:
        from ddd.models import RastersFile

        with pytest.raises(ValidationError):
            RastersFile.model_validate({"rasters": [{"raster": "R", "event": "5"}]})

    def test_a_section_alignment_must_be_a_number(self) -> None:
        from ddd.models import SectionsFile

        with pytest.raises(ValidationError):
            SectionsFile.model_validate(
                {"sections": [{"section": ".x", "access": "read-write", "alignment": "4"}]}
            )


class TestSixtyFourBitBound:
    """No datatype DDD offers holds more than 64 bits, so neither does any integer field.

    Before this bound, an integer beyond it reached an arithmetic comparison somewhere
    downstream instead of being refused where it was written: ``_below``/``_above`` on a
    stated ``limits``, or ``float(...)`` in ``physical_range`` on an enum's values, raised
    ``OverflowError``; a ``constants`` value, a bare ``dimensions`` entry or a section
    ``alignment`` that big was silently accepted instead, with no finding at all.
    """

    HUGE = 10**400  # 401 digits: far beyond even a float, let alone a 64 bit datatype

    def test_a_huge_limit_on_a_definition_is_a_schema_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", limits={"min": 0, "max": self.HUGE})
                ),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.limits.max" in messages(bag), messages(bag)

    def test_a_limit_one_past_64_bits_is_a_schema_finding(self, tree: Path) -> None:
        """``2**64``, not ``HUGE``: the narrowest value the silent-widening band starts at.

        Between ``2**64 - 1`` (the bound) and roughly ``1.8e308`` (the largest a float64 can
        hold), a value failed only the int arm's own ``le`` and was still small enough to
        survive the union's ``Real`` arm - so it was quietly accepted as a ``float`` instead
        of refused. ``HUGE`` is far past that band and does not exercise it.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", limits={"min": 0, "max": 2**64})
                ),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.limits.max" in messages(bag), messages(bag)
        assert "does not fit 64 bits" in messages(bag), messages(bag)

    def test_a_limit_one_below_64_bits_is_a_schema_finding(self, tree: Path) -> None:
        """The bottom edge, mirrored: one less than ``-(2**63)`` is refused the same way."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", limits={"min": -(2**63) - 1, "max": 0})
                ),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.limits.min" in messages(bag), messages(bag)
        assert "does not fit 64 bits" in messages(bag), messages(bag)

    def test_a_huge_limit_on_a_structure_member_is_a_schema_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "types.ddd.json"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [
                                {
                                    "name": "m",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {"kind": "identity"},
                                    "limits": {"min": 0, "max": self.HUGE},
                                }
                            ],
                        }
                    ]
                },
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "types[0].members[0].limits.max" in messages(bag), messages(bag)

    def test_a_huge_enumerator_value_on_a_definition_is_a_schema_finding(self, tree: Path) -> None:
        enum = {
            "kind": "enum",
            "name": "E",
            "enumerators": [{"name": "OFF", "value": 0}, {"name": "BIG", "value": self.HUGE}],
        }
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", conversion=enum)),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.conversion.enumerators[1].value" in messages(bag), messages(bag)

    def test_a_huge_enumerator_value_on_a_member_is_a_schema_finding(self, tree: Path) -> None:
        enum = {
            "kind": "enum",
            "name": "E",
            "enumerators": [{"name": "OFF", "value": 0}, {"name": "BIG", "value": self.HUGE}],
        }
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "types.ddd.json"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [
                                {
                                    "name": "m",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": enum,
                                }
                            ],
                        }
                    ]
                },
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "types[0].members[0].conversion.enumerators[1].value" in messages(bag), messages(bag)

    def test_a_huge_enumerator_value_on_a_scalar_type_is_a_schema_finding(self, tree: Path) -> None:
        enum = {
            "kind": "enum",
            "name": "E",
            "enumerators": [{"name": "OFF", "value": 0}, {"name": "BIG", "value": self.HUGE}],
        }
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "types.ddd.json"),
                "types.ddd.json": {
                    "types": [
                        {"type": "scalar", "name": "E_t", "datatype": "uint8", "conversion": enum}
                    ]
                },
                "a.ddd.json": component("A", declare("local", "X", typename="E_t")),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "types[0].conversion.enumerators[1].value" in messages(bag), messages(bag)

    def test_a_huge_constant_is_a_schema_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "constants.ddd.json"),
                "constants.ddd.json": {"constants": [{"name": "N", "value": self.HUGE}]},
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "constants[0].value" in messages(bag), messages(bag)

    def test_a_huge_dimension_is_a_schema_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", dimensions=[self.HUGE])),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.dimensions[0]" in messages(bag), messages(bag)

    def test_a_huge_init_value_is_a_schema_finding(self, tree: Path) -> None:
        """``init`` is bounded too, listed as one of the fields the plan calls out by name.

        Unlike the fields above, ``init`` shares its union with ``Real``: before the integer
        arm was moved ahead of ``bool`` (see ``InitValue``), the reported error was "Input
        should be a valid boolean", which is technically a ``schema`` finding but a
        confusing one for a value the author plainly wrote as a whole number.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", init=self.HUGE)),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.init" in messages(bag), messages(bag)
        assert "valid boolean" not in messages(bag), messages(bag)
        assert "does not fit 64 bits" in messages(bag), messages(bag)

    def test_an_init_one_past_64_bits_is_a_schema_finding(self, tree: Path) -> None:
        """The same silent-widening band as the limit above, for ``init``.

        ``init`` is a raw value, not a physical one, so the consequence of missing this band
        is worse than for ``limits``: before this check ran ahead of the union, ``2**64``
        here would have been quietly reinterpreted as a ``float`` and reached
        ``_check_init``'s "is written as a fractional number" branch - misleading, since the
        author wrote a plain integer.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", init=2**64)),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "definition.init" in messages(bag), messages(bag)
        assert "does not fit 64 bits" in messages(bag), messages(bag)

    def test_a_huge_section_alignment_is_a_schema_finding(self, tree: Path) -> None:
        """A power of two, so the pre-existing "not a power of two" check cannot catch it.

        ``2**500`` is a legal power of two and used to sail through with no finding at all -
        no crash, but no complaint either, which is worse: a project could ship a linker
        section aligned to something no real target could satisfy.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "sections.ddd.json"),
                "sections.ddd.json": {
                    "sections": [{"section": ".x", "access": "read-write", "alignment": 2**500}]
                },
                "a.ddd.json": component("A", declare("local", "X", section=".x")),
            },
        )
        assert dictionary is None
        assert checks(bag) == ["schema"]
        assert "sections[0].alignment" in messages(bag), messages(bag)

    # -- the bound is exactly 64 bits: the datatype still decides within it ----------------

    def test_uint64_max_is_still_accepted_as_an_init_where_uint64_allows(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "uint64", init=2**64 - 1)),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    def test_uint64_max_is_still_init_invalid_on_a_smaller_datatype(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "uint8", init=2**64 - 1)),
            },
        )
        assert checks(bag) == ["init-invalid"]

    def test_sint64_min_is_still_accepted_as_an_init_where_sint64_allows(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "sint64", init=-(2**63))),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    def test_limits_at_the_full_uint64_range_are_still_accepted(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", "uint64", limits={"min": 0, "max": 2**64 - 1})
                ),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    def test_limits_at_the_full_sint64_range_are_still_accepted(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", "sint64", limits={"min": -(2**63), "max": 2**63 - 1}),
                ),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    def test_a_float_init_written_with_an_exponent_is_still_accepted(self, tree: Path) -> None:
        """Not every large ``init`` is a whole number in disguise.

        ``1.8e19`` is a ``float`` from the moment the json parser reads it - it has no
        integer form to begin with - so the new check, which only ever looks at Python
        ``int``, has nothing to say about it: it is a ``Real`` on its own terms.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "float64", init=1.8e19)),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    def test_a_bool_init_on_a_boolean_definition_is_still_accepted(self, tree: Path) -> None:
        """``bool`` is a python subclass of ``int``, so the new check has to exclude it by hand.

        Without that exclusion, ``isinstance(value, int)`` alone would be true for ``True``
        and ``False`` too, and every boolean ``init`` would be refused as out of range.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "boolean", init=True)),
            },
        )
        assert dictionary is not None
        assert checks(bag) == []

    # -- direct against the contract, no project tree needed ------------------------------

    def test_a_dimension_beyond_64_bits_is_rejected_directly(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal"):
            definition(dimensions=[self.HUGE])

    def test_a_constant_beyond_64_bits_is_rejected_directly(self) -> None:
        from ddd.models import ConstantsFile

        with pytest.raises(ValidationError, match="less than or equal"):
            ConstantsFile.model_validate({"constants": [{"name": "N", "value": self.HUGE}]})
