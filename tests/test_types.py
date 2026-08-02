"""Tests for the structured datatype description file.

Every rule here exists to stop a structure being generated that the description does not
describe, so each one is tested from both sides: the shape it accepts and the shape it refuses.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ddd.models import Member, MemberKind, StructType, TypesFile


def value(name: str = "Speed", **extra: Any) -> dict[str, Any]:
    return {"name": name, "member": "value", "kind": "measurement", "datatype": "uint16", **extra}


def bits(name: str = "Ready", **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "member": "bits",
        "kind": "measurement",
        "datatype": "uint16",
        "bits": 1,
        **extra,
    }


def structure(*members: dict[str, Any], name: str = "Engine_t") -> dict[str, Any]:
    return {"name": name, "members": list(members) or [value()]}


class TestValueMember:
    def test_a_scalar(self) -> None:
        member = Member.model_validate(value())
        assert member.member is MemberKind.VALUE
        assert member.dimensions == ()

    def test_an_array(self) -> None:
        member = Member.model_validate(value(dimensions=[2, 3]))
        assert member.dimensions == (2, 3)

    def test_a_datatype_is_required(self) -> None:
        payload = value()
        del payload["datatype"]
        with pytest.raises(ValidationError, match="a 'value' member needs a 'datatype'"):
            Member.model_validate(payload)

    def test_a_kind_is_required(self) -> None:
        payload = value()
        del payload["kind"]
        with pytest.raises(ValidationError, match="a 'value' member needs a 'kind'"):
            Member.model_validate(payload)

    def test_it_has_no_bits(self) -> None:
        with pytest.raises(ValidationError, match="a 'value' member has no 'bits'"):
            Member.model_validate(value(bits=3))

    def test_it_has_no_nested_type(self) -> None:
        with pytest.raises(ValidationError, match="a 'value' member has no 'type'"):
            Member.model_validate(value(type="Other_t"))

    @pytest.mark.parametrize("kind", ["curve", "map", "axis", "value_block"])
    def test_only_a_measurement_or_a_parameter(self, kind: str) -> None:
        """The others refer to other objects, which a member has no way to do."""
        with pytest.raises(ValidationError, match="cannot be a"):
            Member.model_validate(value(kind=kind))

    def test_a_parameter_member_is_accepted(self) -> None:
        assert Member.model_validate(value(kind="parameter")).kind is not None


class TestBitsMember:
    def test_a_bitfield(self) -> None:
        member = Member.model_validate(bits(bits=2))
        assert member.member is MemberKind.BITS
        assert member.bits == 2

    def test_a_width_is_required(self) -> None:
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
        with pytest.raises(ValidationError, match="17 bits does not fit in 'uint16'"):
            Member.model_validate(bits(bits=17))

    @pytest.mark.parametrize("datatype", ["float32", "float64", "boolean"])
    def test_it_needs_an_integer(self, datatype: str) -> None:
        with pytest.raises(ValidationError, match="a bitfield needs an integer datatype"):
            Member.model_validate(bits(datatype=datatype))

    def test_a_width_of_zero_is_refused(self) -> None:
        """A zero width field is a c alignment device, not a variable anybody addresses."""
        with pytest.raises(ValidationError):
            Member.model_validate(bits(bits=0))


class TestStructMember:
    def test_a_nested_structure(self) -> None:
        member = Member.model_validate({"name": "Inner", "member": "struct", "type": "Other_t"})
        assert member.type == "Other_t"

    def test_a_type_is_required(self) -> None:
        with pytest.raises(ValidationError, match="a 'struct' member needs a 'type'"):
            Member.model_validate({"name": "Inner", "member": "struct"})

    def test_it_has_no_datatype(self) -> None:
        with pytest.raises(ValidationError, match="a 'struct' member has no 'datatype'"):
            Member.model_validate(
                {"name": "Inner", "member": "struct", "type": "Other_t", "datatype": "uint8"}
            )

    def test_it_has_no_kind(self) -> None:
        """A nested structure is measured or calibrated member by member, not as a whole."""
        with pytest.raises(ValidationError, match="a 'struct' member has no 'kind'"):
            Member.model_validate(
                {"name": "Inner", "member": "struct", "type": "Other_t", "kind": "measurement"}
            )

    def test_it_has_no_dimensions(self) -> None:
        """An array of structures is a later stage; refused rather than half generated."""
        with pytest.raises(ValidationError, match="a 'struct' member has no 'dimensions'"):
            Member.model_validate(
                {"name": "Inner", "member": "struct", "type": "Other_t", "dimensions": [2]}
            )

    def test_an_empty_type_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            Member.model_validate({"name": "Inner", "member": "struct", "type": ""})


class TestStructType:
    def test_a_structure(self) -> None:
        parsed = StructType.model_validate(structure(value("Speed"), bits("Ready")))
        assert [member.name for member in parsed.members] == ["Speed", "Ready"]

    def test_a_structure_needs_a_member(self) -> None:
        with pytest.raises(ValidationError):
            StructType.model_validate({"name": "Engine_t", "members": []})

    def test_two_members_cannot_share_a_name(self) -> None:
        with pytest.raises(ValidationError, match="declares member 'Speed' twice"):
            StructType.model_validate(structure(value("Speed"), value("Speed")))

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            StructType.model_validate({"name": "Engine_t", "members": [value()], "size": 14})


class TestTypesFile:
    def test_a_file_of_structures(self) -> None:
        parsed = TypesFile.model_validate({"types": [structure(name="A_t"), structure(name="B_t")]})
        assert [entry.name for entry in parsed.types] == ["A_t", "B_t"]

    def test_a_file_needs_a_structure(self) -> None:
        with pytest.raises(ValidationError):
            TypesFile.model_validate({"types": []})

    def test_two_structures_cannot_share_a_name(self) -> None:
        with pytest.raises(ValidationError, match="'A_t' is declared twice"):
            TypesFile.model_validate({"types": [structure(name="A_t"), structure(name="A_t")]})

    def test_the_schema_key_is_allowed(self) -> None:
        """Same editor binding as every other description file."""
        parsed = TypesFile.model_validate(
            {"$schema": "../schemas/ddd_types.schema.json", "types": [structure()]}
        )
        assert parsed.schema_reference is not None

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            TypesFile.model_validate({"types": [structure()], "typos": []})
