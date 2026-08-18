"""Contract for the type description file.

A ``types`` file declares the types a project names: structures, and scalars that fix what a
number means.  It is the home of the shared ones, because a type with no single owner has no
component to live inside: the point of declaring ``Engine_t`` once is that two components can
agree on it without either owning it.  A component may instead declare the types it publishes
in its own description, with entries of exactly this form; either home puts the name in the
same project wide namespace.

**Two keys name the storage, everywhere.**  ``datatype`` is one of the base datatypes and
nothing else; ``typename`` is the name of a type declared here.  Exactly one of the two is
stated, on a structure member and on a component declaration alike, so that the published
schema keeps ``datatype`` at eleven values and a reader tells base from declared at the use
site.

What a structure member may be is deliberately narrow, and the boundary is layout:

* a **value** member is a base ``datatype`` or a declared ``typename``, optionally an array,
* a **bits** member is a base integer datatype and a width in bits, which is a c bitfield.

A member states no storage class.  Whether an object is measured or calibrated qualifies the
whole c object - ``const`` cannot apply to half a structure - so it is the *declaration* that
decides, and a structure mixing the two is not something this file can express rather than
something DDD has to report.

A member says what its number means as well as where its bytes are, because after a structure
is flattened into the a2l each member *is* an object: it needs a unit and limits like any other.
It may say so directly, or name a scalar type that fixes it, and never both - which is the same
rule a declaration follows, one level up.  Which of the two to reach for is a question of
whether the answer is shared: a unit written on a member says it for that member, and a
``Temperature_t`` says it once for everything in the project that names it.

What a member does *not* carry is what belongs to a variable rather than to a type: ``init``,
because two variables of one structure may start at different values, and ``volatile``, because
a qualifier applies to a whole c object and not to a member of one.

The bit positions of a bitfield are not stated, and cannot be: c leaves the allocation order
within a storage unit implementation defined, so the position of ``Ready : 1`` is a property of
the compiler rather than of this file.  The same holds for the offset of every member.  DDD
reads both back out of the build and never predicts them - see the address map, which is keyed
on access paths for exactly this reason.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from ddd.models.common import Datatype, FileRoot, Identifier, Number, TypeName
from ddd.models.conversion import Conversion, physical_range
from ddd.models.objects import (
    A2lObjectOptions,
    Dimension,
    Limits,
    ObjectKind,
    check_conversion_stated,
    check_storage_named_once,
    refuse_enum_on_non_integer,
    refuse_restating,
)

BITS_PER_BYTE = 8


class MemberKind(StrEnum):
    """What shape a structure member has.

    Stated rather than inferred from which keys are present: a file that omits a key by mistake
    should be told which member shape it failed to describe, not silently become another one.
    A forgotten ``bits`` would otherwise turn a one bit flag into a full width member and move
    every offset after it.
    """

    VALUE = "value"
    """A datatype, scalar or array; the datatype may be a declared type."""

    BITS = "bits"
    """An integer datatype and a width in bits: a c bitfield."""


#: Which object kinds may instantiate a structure. A structured variable is a plain value or a
#: calibratable one; a curve, a map or an axis refers to other objects, which a structure
#: cannot do.
MEMBER_OBJECT_KINDS = (ObjectKind.MEASUREMENT, ObjectKind.PARAMETER)


class Member(BaseModel):
    """One member of a structure, in the order the structure declares it.

    Order is significant: it is the order the c struct is generated in, and therefore the order
    the compiler lays out.  Reordering members of a released structure moves every address after
    the change, which is why a comparison against a baseline reports it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """Name of the member, unique within its structure."""

    member: MemberKind
    """Which shape this member has, and with it which other keys the member may carry.

    * ``value`` needs ``datatype`` or ``typename`` and may add ``dimensions``,
    * ``bits`` needs ``datatype`` and ``bits``.

    A key belonging to the other shape is refused rather than ignored: ``bits`` together with
    ``dimensions`` has no single meaning - c has no array of bitfields - and quietly dropping
    one of the two would put a structure in the generated c that this file does not describe.
    """

    description: str = ""
    """Free text describing the member, offered to the c templates."""

    datatype: Datatype | None = None
    """Storage of this member, one of the eleven base datatypes.

    Exactly one of ``datatype`` and ``typename`` is stated, here exactly as on a declaration.
    """

    typename: TypeName | None = None
    """Name of a declared type, stated instead of ``datatype``.

    A ``value`` member may name a structure, which nests it, or a scalar type, which fixes what
    its number means.  A ``bits`` member states a base integer ``datatype``: a bitfield has no
    room for a structure, and a scalar type would carry limits the width contradicts.
    """

    dimensions: tuple[Dimension, ...] = ()
    """Array dimensions of a ``value`` member, in c declaration order; empty for a scalar.

    ``[4, 2]`` is declared as ``[4][2]``, the last dimension running fastest in memory.
    Each dimension is an integer of at least 1, or the name of a constant the project
    declares, exactly as on a declaration.
    """

    bits: PositiveInt | None = None
    """Width of a ``bits`` member, in bits; required on one, refused on the other.

    It has to fit the datatype carrying it - at most 16 in a ``uint16`` - and that datatype
    has to be an integer, since c allows a bitfield in nothing else.
    """

    unit: str = ""
    """Physical unit of this member, e.g. ``"degC"``.

    Written here, or fixed by a scalar type this member names, and never both.  Which of the
    two to reach for is a question of whether the answer is shared: a unit written here says it
    for this member of this structure, and a ``Temperature_t`` says it for everything that
    names it, across every component of the project.
    """

    conversion: Conversion | None = None
    """How this member's raw value maps to a physical one: identity, linear or an enumeration.

    Required on a member whose storage is a base ``datatype``, exactly as on a definition;
    a member naming a scalar ``typename`` states none, the type fixing it.
    """

    limits: Limits | None = None
    """Physical limits of this member; derived from its storage and conversion if omitted.

    For a ``bits`` member the derivation uses the *width*, not the datatype carrying it: a two
    bit field offered to a calibration tool as ``0 .. 65535`` invites somebody to enter a value
    the field cannot hold and the software then reads back something else.
    """

    a2l: A2lObjectOptions = A2lObjectOptions()
    """What this member asks of the a2l file once the structure is flattened into it.

    Per member rather than per structure, because that is the granularity the a2l ends up with:
    each member becomes an object of its own, so keeping one of them out of the file, or giving
    one of them a display format, is a decision about that member alone.
    """

    def physical_limits(self) -> Limits:
        """Stated limits, or the range this member's storage and conversion imply."""
        if self.limits is not None:
            return self.limits
        assert self.datatype is not None
        assert self.conversion is not None
        raw = (
            bitfield_range(self.datatype, self.bits)
            if self.bits is not None
            else (self.datatype.raw_min, self.datatype.raw_max)
        )
        low, high = physical_range(self.conversion, *raw)
        return Limits(min=low, max=high)

    @model_validator(mode="after")
    def _storage_is_named_exactly_once(self) -> Member:
        check_storage_named_once(self.datatype, self.typename)
        return self

    @model_validator(mode="after")
    def _base_storage_states_its_conversion(self) -> Member:
        check_conversion_stated(self.datatype, self.conversion)
        return self

    @model_validator(mode="after")
    def _enum_requires_integer(self) -> Member:
        refuse_enum_on_non_integer(self.datatype, self.conversion)
        return self

    @model_validator(mode="after")
    def _a_named_type_is_not_restated(self) -> Member:
        if self.typename is not None:
            refuse_restating(self.typename, self.model_fields_set)
        return self

    @model_validator(mode="after")
    def _shape_and_keys_agree(self) -> Member:
        """Each member shape allows exactly the keys it needs.

        Refusing the others matters more here than it looks: ``bits`` on a member that also has
        ``dimensions`` has no single meaning - an array of bitfields is not a thing c can express
        - and quietly ignoring one of the two would put a structure in the generated c that the
        description does not describe.
        """
        if self.member is MemberKind.BITS:
            if self.dimensions:
                msg = "a 'bits' member has no 'dimensions'"
                raise ValueError(msg)
            if self.bits is None:
                msg = "a 'bits' member needs a 'bits'"
                raise ValueError(msg)
        elif self.bits is not None:
            msg = "a 'value' member has no 'bits'"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _a_bitfield_fits_its_storage(self) -> Member:
        """A width no wider than the datatype, and a base integer to put it in.

        A field wider than its storage does not compile, and one in a float, a boolean or a
        declared type is not a bitfield at all - c allows a bitfield only in an integer type.
        """
        if self.bits is None:
            return self
        if self.typename is not None:
            msg = (
                f"a bitfield needs a base integer datatype, got the declared type "
                f"'{self.typename}'; only an integer can carry one in c"
            )
            raise ValueError(msg)
        assert self.datatype is not None
        if not self.datatype.is_integer:
            msg = (
                f"a bitfield needs an integer datatype, got '{self.datatype.value}'; only an "
                f"integer can carry one in c"
            )
            raise ValueError(msg)
        capacity = self.datatype.size * BITS_PER_BYTE
        if self.bits > capacity:
            msg = (
                f"a bitfield of {self.bits} bits does not fit in '{self.datatype.value}', which "
                f"holds {capacity}"
            )
            raise ValueError(msg)
        return self


class StructType(BaseModel):
    """One structured datatype: a name and the members it lays out, in order."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    type: Literal["struct"]
    """Says this entry describes a structure; stated on every entry of a types file."""

    name: TypeName
    """Name of the structure; every type of a project needs a distinct one.

    Refused if it reads as a base datatype, which would be a type nothing could ever refer to:
    where a name is written, a base datatype wins the union.
    """

    description: str = ""
    """Free text describing the structure, offered to the c templates."""

    members: tuple[Member, ...] = Field(min_length=1)
    """The members, in the order they are laid out."""

    @model_validator(mode="after")
    def _member_names_are_distinct(self) -> StructType:
        seen: set[str] = set()
        for member in self.members:
            if member.name in seen:
                msg = f"structure '{self.name}' declares member '{member.name}' twice"
                raise ValueError(msg)
            seen.add(member.name)
        return self


class ScalarType(BaseModel):
    """A name for what a number means, so components agree by naming rather than by copying.

    Three components consuming an engine speed each used to write out the datatype, the unit,
    the scaling and the limits, leaving DDD to notice when one of them was wrong.  If all three
    say ``Speed_t`` instead, there is nothing left to disagree about - which is checking turned
    into construction.

    It fixes exactly the four things that make two declarations interchangeable, and nothing
    else.  ``kind``, ``dimensions``, ``init``, ``volatile`` and ``a2l`` stay on the variable:
    they are properties of one object rather than of the type, and two measurements of the same
    type may well differ in whether an interrupt writes one of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    type: Literal["scalar"]
    """Says this entry names a scalar rather than describing a structure."""

    name: TypeName
    """Name of the type; every type of a project needs a distinct one.

    Refused if it reads as a base datatype, for the reason a structure's name is.
    """

    description: str = ""
    """Free text describing what the type is, offered to the c templates."""

    datatype: Datatype
    """Storage of the value: one of the base datatypes.

    A base datatype rather than another declared type, so that a scalar type cannot be defined
    in terms of a second one.  A chain of names would have to be resolved, could form a cycle,
    and buys nothing a reader of the one entry could not already see.
    """

    unit: str = ""
    """Physical unit of the value, e.g. ``"rpm"``."""

    conversion: Conversion
    """How a raw value maps to a physical one: identity, linear scaling or an enumeration.

    Required: fixing what a value means is the one job a scalar type has, and the identity
    is part of the answer rather than a silence to interpret.
    """

    limits: Limits | None = None
    """Physical limits, in the unit above; derived from datatype and conversion if omitted."""

    @model_validator(mode="after")
    def _enum_requires_integer(self) -> ScalarType:
        refuse_enum_on_non_integer(self.datatype, self.conversion)
        return self


AnyType = Annotated[StructType | ScalarType, Field(discriminator="type")]
"""Any entry of a types file, told apart by its required ``type``.

Discriminated on a stated key rather than inferred from which other keys are present, for the
reason the member shapes already give: a file that omits a key by mistake should be told which
shape it failed to describe, not silently become another one.
"""


def check_distinct_type_names(entries: tuple[StructType | ScalarType, ...]) -> None:
    """Two entries of one list must not share a name.

    One rule for the two places a list of type entries can be written - a types file, and the
    ``types`` a component declares inline - so the second spelling of a name is refused where
    it is written, in either home. The same name declared by two *lists* is not this rule's
    business: that is ``duplicate-type``, reported with a note at the first declaration.
    """
    seen: set[str] = set()
    for entry in entries:
        if entry.name in seen:
            msg = f"type '{entry.name}' is already declared in this file"
            raise ValueError(msg)
        seen.add(entry.name)


class TypesFile(FileRoot):
    """Root object of a ``*.ddd.json`` type description.

    ``types`` is the top level key that makes this a types file rather than a project or a
    component file; DDD decides what a file is from that key alone, so exactly one of them
    appears here.
    """

    model_config = ConfigDict(title="DDD type description")

    types: tuple[AnyType, ...] = Field(min_length=1)
    """The types this file declares."""

    @model_validator(mode="after")
    def _type_names_are_distinct(self) -> TypesFile:
        check_distinct_type_names(self.types)
        return self


def bitfield_range(datatype: Datatype, bits: int) -> tuple[Number, Number]:
    """The raw values a bitfield of that width holds, for deriving its limits.

    A two bit ``mode`` offered to a calibration tool as ``0 .. 65535`` is worse than no limits
    at all: the tool lets somebody enter a value the field cannot store, and the software reads
    back something else. The width is the only thing that says otherwise, and the description
    states it.

    A signed field spends one bit on the sign, so ``sint8 : 4`` runs ``-8 .. 7``. No clamp
    against the storage is needed: a member may not be wider than the datatype carrying it, and
    at exactly that width the two answers are the same one.
    """
    if datatype.info.is_signed:
        top = (1 << (bits - 1)) - 1
        return (-top - 1, top)
    return (0, (1 << bits) - 1)
