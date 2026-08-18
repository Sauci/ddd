"""Tests for the type description file.

An entry of a types file is a tagged union on ``type``: a structure, which says where bytes
are, or a scalar type, which says what they mean. Every rule here exists to stop a type being
generated that the description does not describe, so each one is tested from both sides: the
shape it accepts and the shape it refuses.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ddd.models import (
    MEMBER_OBJECT_KINDS,
    Datatype,
    IdentityConversion,
    Limits,
    Member,
    MemberKind,
    ObjectKind,
    ScalarType,
    StructType,
    TypesFile,
    bitfield_range,
)


def value(name: str = "Speed", **extra: Any) -> dict[str, Any]:
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": "uint16", "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "value", **storage, **extra}


def bits(name: str = "Ready", **extra: Any) -> dict[str, Any]:
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": "uint16", "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "bits", **storage, "bits": 1, **extra}


def structure(*members: dict[str, Any], name: str = "Engine_t", **extra: Any) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members) or [value()], **extra}


def scalar(name: str = "Speed_t", **extra: Any) -> dict[str, Any]:
    meaning: dict[str, Any] = {} if "conversion" in extra else {"conversion": {"kind": "identity"}}
    return {"type": "scalar", "name": name, "datatype": "uint16", **meaning, **extra}


class TestMemberShape:
    """Which shapes a member has at all, and what a member is therefore not allowed to say."""

    def test_a_member_is_a_value_or_a_bitfield(self) -> None:
        """The two layouts c has room for; a member describes layout and nothing else."""
        assert [kind.value for kind in MemberKind] == ["value", "bits"]

    def test_a_shape_is_stated_rather_than_inferred(self) -> None:
        """A file that forgets a key is told which shape it failed to describe."""
        payload = value()
        del payload["member"]
        with pytest.raises(ValidationError, match="Field required"):
            Member.model_validate(payload)

    def test_a_structure_is_no_longer_a_shape_of_its_own(self) -> None:
        """Nesting is a ``value`` naming the structure: one key names a type, everywhere."""
        with pytest.raises(ValidationError, match="Input should be 'value' or 'bits'"):
            Member.model_validate({"name": "Inner", "member": "struct", "typename": "Sample_t"})

    def test_a_member_states_no_storage_class(self) -> None:
        """``const`` qualifies a whole c object, so the declaration decides, not half a struct."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Member.model_validate(value(kind="measurement"))

    @pytest.mark.parametrize(
        ("key", "stated"),
        [
            ("unit", "rpm"),
            ("conversion", {"factor": 0.5}),
            ("limits", {"min": 0, "max": 10}),
            ("a2l", {"export": False}),
        ],
    )
    def test_a_member_says_what_its_bytes_mean_as_well_as_where_they_are(
        self, key: str, stated: Any
    ) -> None:
        """Because after flattening a member *is* an a2l object, and needs what one needs.

        Requiring a named scalar type for every member that has a unit would put the friction
        in the wrong place: one timestamp should not cost a ``Milliseconds_t``.
        """
        member = Member.model_validate(value(**{key: stated}))
        assert getattr(member, key) is not None

    @pytest.mark.parametrize(
        ("key", "stated"),
        [("init", 0), ("volatile", True), ("kind", "measurement")],
    )
    def test_a_member_carries_nothing_that_belongs_to_a_variable(
        self, key: str, stated: Any
    ) -> None:
        """Two variables of one structure may start differently and only one be volatile.

        ``kind`` goes with them for the same reason a member states no storage class: ``const``
        qualifies a whole c object, so it cannot be decided a member at a time.
        """
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Member.model_validate(value(**{key: stated}))

    @pytest.mark.parametrize("key", ["unit", "conversion", "limits"])
    def test_a_member_naming_a_type_may_not_restate_what_it_fixes(self, key: str) -> None:
        """The same rule as on a declaration, so one question has one answer in both places."""
        stated = {"unit": "rpm", "conversion": {"factor": 0.5}, "limits": {"min": 0, "max": 1}}
        with pytest.raises(ValidationError, match="already fixes what this value means"):
            Member.model_validate(value(typename="Speed_t", **{key: stated[key]}))

    def test_the_limits_of_a_bitfield_come_from_its_width(self) -> None:
        """Not from the storage carrying it, which is the whole point of stating a width.

        A two bit field offered to a calibration tool as ``0 .. 65535`` lets somebody enter a
        value the field cannot hold, and the software then reads back something else.
        """
        member = Member.model_validate(
            {"name": "mode", "member": "bits", "datatype": "uint16", "bits": 2, "conversion": {}}
        )
        assert member.physical_limits().as_tuple() == (0, 3)

    def test_the_limits_of_a_member_follow_its_conversion(self) -> None:
        member = Member.model_validate(
            value(datatype="uint16", conversion={"factor": 0.1, "offset": -40})
        )
        assert member.physical_limits().as_tuple() == (-40.0, 6513.5)

    def test_stated_limits_win_over_the_derivation(self) -> None:
        """State them to say the software handles less than the storage could."""
        member = Member.model_validate(value(limits={"min": 0, "max": 100}))
        assert member.physical_limits().as_tuple() == (0, 100)

    def test_only_a_measurement_or_a_parameter_may_instantiate_a_structure(self) -> None:
        """A curve, a map or an axis refers to other objects, which a structure cannot do."""
        assert MEMBER_OBJECT_KINDS == (ObjectKind.MEASUREMENT, ObjectKind.PARAMETER)


class TestValueMember:
    def test_a_scalar(self) -> None:
        member = Member.model_validate(value())
        assert member.member is MemberKind.VALUE
        assert member.dimensions == ()
        assert member.bits is None

    def test_an_array(self) -> None:
        assert Member.model_validate(value(dimensions=[2, 3])).dimensions == (2, 3)

    def test_a_nested_structure_is_a_value_whose_typename_names_it(self) -> None:
        """Nesting needs no shape of its own: naming a structure is what nests it."""
        member = Member.model_validate(value("latest", typename="Sample_t"))
        assert member.member is MemberKind.VALUE
        assert member.datatype is None
        assert member.typename == "Sample_t"

    def test_the_conversion_is_required_beside_a_datatype(self) -> None:
        """The same rule as on a definition: the identity is an answer, not a default."""
        payload = value()
        del payload["conversion"]
        with pytest.raises(ValidationError, match="comes with a 'conversion'"):
            Member.model_validate(payload)

    def test_storage_is_named_exactly_once(self) -> None:
        """Neither key is a silence to interpret, and both at once is a contradiction."""
        payload = value()
        del payload["datatype"]
        with pytest.raises(ValidationError, match="storage is named exactly once"):
            Member.model_validate(payload)
        with pytest.raises(ValidationError, match="storage is named exactly once"):
            Member.model_validate(value(typename="Sample_t", datatype="uint16"))

    @pytest.mark.parametrize("datatype", ["boolean", "float64"])
    def test_an_enum_conversion_needs_an_integer_datatype(self, datatype: str) -> None:
        """The same rule as on a definition; boolean does not count as an integer."""
        with pytest.raises(
            ValidationError, match=f"requires an integer datatype, got '{datatype}'"
        ):
            Member.model_validate(
                value(
                    datatype=datatype,
                    conversion={"kind": "enum", "name": "E_t", "enumerators": {"A": 0}},
                )
            )

    def test_it_has_no_bits(self) -> None:
        """A width quietly ignored would generate a full width member and move every offset."""
        with pytest.raises(ValidationError, match="a 'value' member has no 'bits'"):
            Member.model_validate(value(bits=3))

    def test_a_dimension_of_zero_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            Member.model_validate(value(dimensions=[0]))


class TestBitsMember:
    def test_a_bitfield(self) -> None:
        member = Member.model_validate(bits(bits=2))
        assert member.member is MemberKind.BITS
        assert member.bits == 2
        assert member.dimensions == ()

    def test_a_width_is_required(self) -> None:
        """A forgotten width would turn a one bit flag into a full width member."""
        payload = bits()
        del payload["bits"]
        with pytest.raises(ValidationError, match="a 'bits' member needs a 'bits'"):
            Member.model_validate(payload)

    def test_it_has_no_dimensions(self) -> None:
        """An array of bitfields is not something c can express."""
        with pytest.raises(ValidationError, match="a 'bits' member has no 'dimensions'"):
            Member.model_validate(bits(dimensions=[4]))

    def test_it_fills_its_storage_exactly(self) -> None:
        assert Member.model_validate(bits(bits=16)).bits == 16

    def test_it_cannot_be_wider_than_its_storage(self) -> None:
        """A field wider than the type carrying it does not compile."""
        with pytest.raises(ValidationError, match="17 bits does not fit in 'uint16'"):
            Member.model_validate(bits(bits=17))

    @pytest.mark.parametrize("datatype", ["float32", "float64", "boolean"])
    def test_it_needs_an_integer(self, datatype: str) -> None:
        """C allows a bitfield in nothing else."""
        with pytest.raises(ValidationError, match="a bitfield needs an integer datatype"):
            Member.model_validate(bits(datatype=datatype))

    def test_it_cannot_name_a_declared_type(self) -> None:
        """A bitfield has no room for a structure, and a scalar type would carry limits the
        width contradicts."""
        with pytest.raises(ValidationError, match="got the declared type 'Flags_t'"):
            Member.model_validate(bits(typename="Flags_t", bits=2))

    def test_a_width_of_zero_is_refused(self) -> None:
        """A zero width field is a c alignment device, not a variable anybody addresses."""
        with pytest.raises(ValidationError):
            Member.model_validate(bits(bits=0))


class TestDatatypeReference:
    """``datatype`` is one of the eleven, ``typename`` a declared name - never mixed."""

    @pytest.mark.parametrize("name", ["boolean", "uint8", "sint16", "uint64", "float32"])
    def test_a_base_name_is_the_datatype(self, name: str) -> None:
        assert Member.model_validate(value(datatype=name)).datatype is Datatype(name)

    def test_a_declared_name_stays_a_name(self) -> None:
        """Nothing here can resolve it: the type it names may be declared in another file."""
        member = Member.model_validate(value(typename="Sample_t"))
        assert member.datatype is None
        assert member.typename == "Sample_t"

    def test_an_empty_name_is_neither(self) -> None:
        with pytest.raises(ValidationError):
            Member.model_validate(value(datatype=""))


class TestStructType:
    def test_a_structure(self) -> None:
        parsed = StructType.model_validate(structure(value("Speed"), bits("Ready")))
        assert parsed.type == "struct"
        assert [member.name for member in parsed.members] == ["Speed", "Ready"]

    def test_the_type_key_is_required(self) -> None:
        """Every entry of a types file says which kind of entry it is."""
        payload = structure()
        del payload["type"]
        with pytest.raises(ValidationError, match="Field required"):
            StructType.model_validate(payload)

    def test_a_structure_needs_a_member(self) -> None:
        with pytest.raises(ValidationError, match="at least 1 item"):
            StructType.model_validate({"type": "struct", "name": "Engine_t", "members": []})

    def test_two_members_cannot_share_a_name(self) -> None:
        with pytest.raises(ValidationError, match="declares member 'Speed' twice"):
            StructType.model_validate(structure(value("Speed"), value("Speed")))

    def test_an_unknown_key_is_refused(self) -> None:
        """Offsets and sizes are read back out of the build, never stated here."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            StructType.model_validate(structure(size=14))


class TestScalarType:
    def test_a_name_for_what_a_number_means(self) -> None:
        parsed = ScalarType.model_validate(
            scalar(unit="rpm", conversion={"factor": 0.25}, limits={"min": 0, "max": 8000})
        )
        assert parsed.type == "scalar"
        assert parsed.datatype is Datatype.UINT16
        assert parsed.unit == "rpm"
        assert parsed.conversion.to_physical(4) == 1.0
        assert parsed.limits == Limits(min=0, max=8000)

    def test_what_it_leaves_out_stays_open(self) -> None:
        """Limits are derived from datatype and conversion where the type does not state them."""
        parsed = ScalarType.model_validate(scalar())
        assert isinstance(parsed.conversion, IdentityConversion)
        assert parsed.unit == ""
        assert parsed.limits is None

    def test_the_type_key_is_required(self) -> None:
        payload = scalar()
        del payload["type"]
        with pytest.raises(ValidationError, match="Field required"):
            ScalarType.model_validate(payload)

    def test_it_needs_a_base_datatype(self) -> None:
        """A type defined in terms of a second one would chain, and could form a cycle."""
        with pytest.raises(ValidationError, match="Input should be 'boolean', 'uint8'"):
            ScalarType.model_validate(scalar(datatype="Other_t"))

    def test_an_enum_conversion_needs_an_integer_datatype(self) -> None:
        """The rule of a definition holds here, where the meaning is fixed for everybody."""
        with pytest.raises(ValidationError, match="requires an integer datatype, got 'float32'"):
            ScalarType.model_validate(
                scalar(
                    datatype="float32",
                    conversion={"kind": "enum", "name": "E_t", "enumerators": {"A": 0}},
                )
            )

    @pytest.mark.parametrize(
        ("key", "stated"),
        [
            ("kind", "measurement"),
            ("dimensions", [4]),
            ("init", 0),
            ("volatile", True),
            ("a2l", {"export": False}),
        ],
    )
    def test_it_fixes_nothing_that_belongs_to_one_variable(self, key: str, stated: Any) -> None:
        """Two measurements of one type may differ in whether an interrupt writes one of them."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ScalarType.model_validate(scalar(**{key: stated}))


class TestTypesFile:
    def test_a_file_of_structures_and_scalars(self) -> None:
        """A type is declared once and shared, so both kinds live in the same file."""
        parsed = TypesFile.model_validate({"types": [structure(name="A_t"), scalar(name="B_t")]})
        assert [type(entry) for entry in parsed.types] == [StructType, ScalarType]
        assert [entry.name for entry in parsed.types] == ["A_t", "B_t"]

    def test_an_entry_states_which_kind_it_is(self) -> None:
        """A file that omits the key is told so, rather than silently becoming the other kind."""
        payload = structure()
        del payload["type"]
        with pytest.raises(ValidationError, match="Unable to extract tag using discriminator"):
            TypesFile.model_validate({"types": [payload]})

    def test_an_unknown_kind_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="does not match any of the expected tags"):
            TypesFile.model_validate({"types": [{"type": "enum", "name": "State_t"}]})

    def test_a_file_needs_a_type(self) -> None:
        with pytest.raises(ValidationError, match="at least 1 item"):
            TypesFile.model_validate({"types": []})

    def test_two_types_cannot_share_a_name(self) -> None:
        """Across both kinds: a name is what the whole project agrees on."""
        with pytest.raises(ValidationError, match="'Speed_t' is already declared"):
            TypesFile.model_validate({"types": [structure(name="Speed_t"), scalar(name="Speed_t")]})

    def test_the_schema_key_is_allowed(self) -> None:
        """Same editor binding as every other description file."""
        parsed = TypesFile.model_validate(
            {"$schema": "../schemas/ddd_types.schema.json", "types": [structure()]}
        )
        assert parsed.schema_reference == "../schemas/ddd_types.schema.json"

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TypesFile.model_validate({"types": [structure()], "typos": []})


class TestBitfieldRange:
    """The raw values a bitfield holds, which is what its limits are derived from."""

    def test_an_unsigned_field_runs_from_zero(self) -> None:
        """A two bit mode offered as 0 .. 65535 lets a tool write a value the field loses."""
        assert bitfield_range(Datatype.UINT16, 2) == (0, 3)

    def test_a_signed_field_spends_a_bit_on_the_sign(self) -> None:
        """Four bits of a ``sint8`` is -8 .. 7, not 0 .. 15: c gives the field a sign bit."""
        assert bitfield_range(Datatype.SINT8, 4) == (-8, 7)

    def test_one_signed_bit_holds_only_minus_one_and_zero(self) -> None:
        """The single bit is the sign bit, which is what makes a signed flag a bad idea."""
        assert bitfield_range(Datatype.SINT16, 1) == (-1, 0)

    @pytest.mark.parametrize(
        ("datatype", "width", "expected"),
        [
            (Datatype.UINT8, 8, (0, 255)),
            (Datatype.SINT8, 8, (-128, 127)),
            (Datatype.UINT64, 64, (0, 18446744073709551615)),
            (Datatype.SINT64, 64, (-9223372036854775808, 9223372036854775807)),
        ],
    )
    def test_a_field_as_wide_as_its_storage_is_the_whole_range(
        self, datatype: Datatype, width: int, expected: tuple[int, int]
    ) -> None:
        """Both ends clamp to the storage, so the widest field states what the type states."""
        assert bitfield_range(datatype, width) == expected
