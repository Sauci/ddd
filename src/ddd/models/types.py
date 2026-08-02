"""Contract for the structured datatype description file.

A ``types`` file declares composite datatypes - structures - that component descriptions then
refer to.  It is a file of its own rather than a section of a component, because a structure is
usually shared: the point of declaring ``Engine_t`` once is that two components can agree on it
without either owning it.

What a member may be is deliberately narrow, and the boundary is layout:

* a **value** member is a datatype, optionally an array,
* a **bits** member is a datatype and a width in bits, which is a c bitfield,
* a **struct** member is another declared structure.

Nothing here describes conversions, limits or a2l options.  Those belong to the objects a
structure is *instantiated* as, and adding them to a member would mean two places to state the
same thing.  A member says where the bytes are; a declaration says what they mean.

The bit positions of a bitfield are not stated, and cannot be: c leaves the allocation order
within a storage unit implementation defined, so the position of ``Ready : 1`` is a property of
the compiler rather than of this file.  DDD reads the real positions back out of the build and
never predicts them - see the layout probe.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from ddd.models.common import Datatype, FileRoot, Identifier
from ddd.models.objects import ObjectKind

BITS_PER_BYTE = 8


class MemberKind(StrEnum):
    """What shape a structure member has.

    Stated rather than inferred from which keys are present: a file that omits a key by mistake
    should be told which member shape it failed to describe, not silently become another one.
    """

    VALUE = "value"
    """A datatype, scalar or array."""

    BITS = "bits"
    """A datatype and a width in bits: a c bitfield."""

    STRUCT = "struct"
    """Another declared structure, nested in this one."""


#: Which object kinds a member may be. A structure member is a plain value or a calibratable
#: one; a curve, a map or an axis refers to other objects, which a member cannot do.
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

    * ``value`` needs ``kind`` and ``datatype``, and may add ``dimensions``,
    * ``bits`` needs ``kind``, ``datatype`` and ``bits``,
    * ``struct`` needs ``type`` and takes nothing else.

    A key belonging to another shape is refused rather than ignored: ``bits`` together with
    ``dimensions`` has no single meaning - c has no array of bitfields - and quietly dropping
    one of the two would put a structure in the generated c that this file does not describe.
    """

    description: str = ""
    """Free text describing the member, offered to the c templates."""

    kind: ObjectKind | None = None
    """Whether the member is measured or calibrated; required unless it is a nested structure.

    Only ``measurement`` and ``parameter`` are allowed here. A curve, a map, a value block or
    an axis refers to other objects by name, which a member of a structure cannot do.
    """

    datatype: Datatype | None = None
    """Storage of a ``value`` or ``bits`` member; required on both."""

    dimensions: tuple[PositiveInt, ...] = ()
    """Array dimensions of a ``value`` member, in c declaration order; empty for a scalar.

    ``[4, 2]`` is declared as ``[4][2]``, the last dimension running fastest in memory.
    """

    bits: PositiveInt | None = None
    """Width of a ``bits`` member, in bits; required on one, refused on the others.

    It has to fit the datatype carrying it - at most 16 in a ``uint16`` - and that datatype
    has to be an integer, since c allows a bitfield in nothing else.
    """

    type: str | None = Field(default=None, min_length=1, max_length=128)
    """Name of the structure a ``struct`` member nests; declared anywhere in the project.

    The name is not pattern checked here on purpose. A structure that does not exist, or whose
    name is not a usable identifier, is reported against the structure that refers to it and
    with a location, which says more than a pattern violation on a key seen out of context.
    """

    @model_validator(mode="after")
    def _shape_and_keys_agree(self) -> Member:
        """Each member shape allows exactly the keys it needs.

        Refusing the others matters more here than it looks: ``bits`` on a member that also has
        ``dimensions`` has no single meaning - an array of bitfields is not a thing c can express
        - and quietly ignoring one of the two would put a structure in the generated c that the
        description does not describe.
        """
        allowed: dict[MemberKind, tuple[str, ...]] = {
            MemberKind.VALUE: ("kind", "datatype", "dimensions"),
            MemberKind.BITS: ("kind", "datatype", "bits"),
            MemberKind.STRUCT: ("type",),
        }
        required: dict[MemberKind, tuple[str, ...]] = {
            MemberKind.VALUE: ("kind", "datatype"),
            MemberKind.BITS: ("kind", "datatype", "bits"),
            MemberKind.STRUCT: ("type",),
        }
        for field in ("kind", "datatype", "bits", "type"):
            if getattr(self, field) is not None and field not in allowed[self.member]:
                msg = f"a '{self.member.value}' member has no '{field}'"
                raise ValueError(msg)
        if self.dimensions and "dimensions" not in allowed[self.member]:
            msg = f"a '{self.member.value}' member has no 'dimensions'"
            raise ValueError(msg)
        for field in required[self.member]:
            if getattr(self, field) is None:
                msg = f"a '{self.member.value}' member needs a '{field}'"
                raise ValueError(msg)
        if self.kind is not None and self.kind not in MEMBER_OBJECT_KINDS:
            offered = ", ".join(kind.value for kind in MEMBER_OBJECT_KINDS)
            msg = (
                f"a structure member cannot be a '{self.kind.value}': it would have to refer to "
                f"other objects. Use one of: {offered}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _a_bitfield_fits_its_storage(self) -> Member:
        """A width no wider than the datatype, and an integer to put it in.

        A field wider than its storage does not compile, and one in a float or a boolean is not
        a bitfield at all - c allows a bitfield only in an integer type.
        """
        if self.bits is None or self.datatype is None:
            return self
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
    """One structured datatype."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """Name of the structure; every structure of a project needs a distinct one."""

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


class TypesFile(FileRoot):
    """Root object of a ``*.ddd.json`` structured datatype description.

    ``types`` is the top level key that makes this a types file rather than a project, a
    component or a naming file; DDD decides what a file is from that key alone, so exactly one
    of the four appears here.
    """

    model_config = ConfigDict(title="DDD structured datatype description")

    types: tuple[StructType, ...] = Field(min_length=1)
    """The structures this file declares."""

    @model_validator(mode="after")
    def _type_names_are_distinct(self) -> TypesFile:
        seen: set[str] = set()
        for structure in self.types:
            if structure.name in seen:
                msg = f"structure '{structure.name}' is declared twice in this file"
                raise ValueError(msg)
            seen.add(structure.name)
        return self
