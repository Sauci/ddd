"""From the C model of :mod:`ddd.elf` to DDD's spelling of it (section 4 of the design).

Kinds, datatypes, conversions, dimensions and the ``struct`` entries of ``types``: what an
image states exactly, it states. What DDD itself decides about the result - its caps, an
enumerator wider than an ``int``, the spelling of a name - is not restated here: the result is
handed to DDD's own loader and analysis (:mod:`ddd.toolbox.checked`), which says so itself.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Final

from ddd.diagnostics import DiagnosticBag, Location
from ddd.elf import (
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    Array,
    Base,
    CType,
    Declared,
    Enum,
    Image,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    size_of,
)
from ddd.toolbox.findings import place, report

_FAMILIES: Final = {
    DW_ATE_BOOLEAN: "boolean",
    DW_ATE_FLOAT: "float",
    DW_ATE_SIGNED: "signed",
    DW_ATE_SIGNED_CHAR: "signed",
    DW_ATE_UNSIGNED: "unsigned",
    DW_ATE_UNSIGNED_CHAR: "unsigned",
}
_DATATYPES: Final = {
    ("boolean", 1): "boolean",
    ("unsigned", 1): "uint8",
    ("unsigned", 2): "uint16",
    ("unsigned", 4): "uint32",
    ("unsigned", 8): "uint64",
    ("signed", 1): "sint8",
    ("signed", 2): "sint16",
    ("signed", 4): "sint32",
    ("signed", 8): "sint64",
    ("float", 4): "float32",
    ("float", 8): "float64",
}
_ENCODED_AS: Final = {
    DW_ATE_BOOLEAN: "a boolean",
    DW_ATE_COMPLEX_FLOAT: "a complex number",
    DW_ATE_FLOAT: "a floating point number",
    DW_ATE_SIGNED: "a signed integer",
    DW_ATE_SIGNED_CHAR: "a signed character",
    DW_ATE_UNSIGNED: "an unsigned integer",
    DW_ATE_UNSIGNED_CHAR: "an unsigned character",
}


@dataclass(frozen=True, slots=True)
class Shape:
    """A C type seen as DDD sees one: its core, the dimensions around it, its qualifiers, and
    the typedef closest to the core that names it."""

    core: Base | Enum | Struct | Unsupported
    dimensions: tuple[int, ...] = ()
    const: bool = False
    volatile: bool = False
    name: str | None = None


def shape_of(ctype: CType) -> Shape:
    """Walk ``ctype`` down to its core, collecting what DDD states about the way.

    A qualifier counts wherever it sits: on the variable's type, under a typedef, or on an
    array's element, where producers put it for an array. The name is the typedef closest to
    the core, so that a second alias still names one structure; a typedef naming an array
    names the array, and is dropped when the walk passes into its element.
    """
    dimensions: list[int] = []
    const = False
    volatile = False
    name: str | None = None
    node = ctype
    while True:
        if isinstance(node, Qualified):
            const = const or node.const
            volatile = volatile or node.volatile
            node = node.inner
        elif isinstance(node, Typedef):
            name = node.name
            node = node.inner
        elif isinstance(node, Array):
            dimensions.extend(node.dimensions)
            name = None
            node = node.element
        else:
            return Shape(node, tuple(dimensions), const, volatile, name)


def datatype_of(core: Base | Enum) -> str | None:
    """The DDD datatype of a base type or an enum, or None where no datatype holds it."""
    if isinstance(core, Enum):
        sign = "signed" if core.signed else "unsigned"
        return _DATATYPES.get((sign, core.size))
    family = _FAMILIES.get(core.encoding)
    if family is None:
        return None
    return _DATATYPES.get((family, core.size))


def described(core: Base | Enum) -> str:
    """A base type or an enum in words, as a refusal says what it is."""
    if isinstance(core, Enum):
        return f"an enum of {_bytes(core.size)}"
    what = _ENCODED_AS.get(core.encoding, f"a value of DWARF encoding {core.encoding:#x}")
    return f"'{core.name}', {what} of {_bytes(core.size)}"


def _bytes(size: int) -> str:
    if size == 1:
        return "1 byte"
    return f"{size} bytes"


@dataclass(frozen=True, slots=True)
class Typed:
    """What DDD states of one variable's type, before its storage is read."""

    kind: str
    datatype: str | None
    """None for a structured object, which names its ``typename`` instead."""

    typename: str | None
    dimensions: tuple[int, ...]
    conversion: dict[str, Any] | None
    volatile: bool
    reaches: frozenset[str]
    """The structures and enums the variable names, directly or through members."""

    element_size: int
    """The bytes of one element, for reading the initial value."""


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why a type cannot be described: the path to the part DDD cannot state, and what it is."""

    path: str
    what: str
    declared_at: Declared | None = None


type _Described = tuple[str, frozenset[str]] | Refusal


class Mapper:
    """Maps variables one after the other, keeping one ``types`` entry per structure name.

    Structures and enums are registered by name as they are described, every distinct
    description of one name kept, so that :meth:`conflicts` can name each name the image
    defines more than one way once every variable has been mapped.
    """

    def __init__(self, image: Image, bag: DiagnosticBag) -> None:
        self._image = image
        self._bag = bag
        self._named: dict[str, list[tuple[dict[str, Any], Declared | None]]] = {}
        self._structures: list[str] = []
        self._synthesized: dict[Struct | Enum, str] = {}
        self._described: dict[tuple[Struct, str], _Described] = {}
        self._reported: set[tuple[str, str]] = set()

    def typed(self, variable: Variable) -> Typed | None:
        """What DDD states of ``variable``'s type; None, reported, where it cannot be stated."""
        shape = shape_of(variable.type)
        location = place(self._image, variable.declared_at)
        core = shape.core
        if isinstance(core, Unsupported):
            self._refuse(variable, Refusal(variable.name, core.what), location)
            return None
        if isinstance(core, Struct):
            return self._structured(variable, shape, core, location)
        scalar = self._scalar(core, variable.name, shape.name, f"{variable.name}_t", None)
        if isinstance(scalar, Refusal):
            self._refuse(variable, scalar, location)
            return None
        datatype, conversion, reaches = scalar
        return Typed(
            kind=_kind(shape),
            datatype=datatype,
            typename=None,
            dimensions=shape.dimensions,
            conversion=conversion,
            volatile=shape.volatile,
            reaches=reaches,
            element_size=core.size,
        )

    def conflicts(self) -> dict[str, list[Declared | None]]:
        """Every name the image defines more than one way, with where each way is declared."""
        return {
            name: [declared_at for _, declared_at in known]
            for name, known in self._named.items()
            if len(known) > 1
        }

    def types(self, names: Collection[str]) -> list[dict[str, Any]]:
        """The ``struct`` entries among ``names``, each after the structures it names."""
        return [self._named[name][0][0] for name in self._structures if name in names]

    def _structured(
        self, variable: Variable, shape: Shape, core: Struct, location: Location
    ) -> Typed | None:
        if shape.const and shape.dimensions:
            report(
                self._bag,
                "elf-type-unsupported",
                f"'{variable.name}' is a const array of structures, which DDD cannot state: a "
                f"parameter has no dimensions, and a value block holds no structure",
                location,
            )
            return None
        described_ = self._struct(core, shape.name, f"{variable.name}_t")
        if isinstance(described_, Refusal):
            self._refuse(variable, described_, location)
            return None
        name, reaches = described_
        return Typed(
            kind="parameter" if shape.const else "measurement",
            datatype=None,
            typename=name,
            dimensions=shape.dimensions,
            conversion=None,
            volatile=shape.volatile,
            reaches=reaches,
            element_size=core.size,
        )

    def _refuse(self, variable: Variable, refusal: Refusal, location: Location) -> None:
        if refusal.path == variable.name:
            message = f"'{variable.name}' is {refusal.what}, which DDD cannot state"
        else:
            message = (
                f"'{variable.name}' cannot be described: '{refusal.path}' is {refusal.what}, "
                f"which DDD cannot state"
            )
        notes: list[tuple[str, Location | None]] = []
        if refusal.declared_at is not None:
            notes.append(
                (f"'{refusal.path}' is declared here", place(self._image, refusal.declared_at))
            )
        report(self._bag, "elf-type-unsupported", message, location, notes)

    def _scalar(
        self,
        core: Base | Enum,
        path: str,
        alias: str | None,
        synthesized: str,
        declared_at: Declared | None,
    ) -> tuple[str, dict[str, Any], frozenset[str]] | Refusal:
        datatype = datatype_of(core)
        if datatype is None:
            return Refusal(path, described(core), declared_at)
        if isinstance(core, Base):
            return datatype, {"kind": "identity"}, frozenset()
        name = alias or core.tag or self._synthesize(core, synthesized)
        conversion = {"kind": "enum", "name": name, "enumerators": dict(core.enumerators)}
        self._register(name, conversion, core.declared_at)
        return datatype, conversion, frozenset({name})

    def _struct(self, struct: Struct, alias: str | None, synthesized: str) -> _Described:
        name = alias or struct.tag or self._synthesize(struct, synthesized)
        key = (struct, name)
        known = self._described.get(key)
        if known is None:
            known = self._describe_struct(struct, name)
            self._described[key] = known
        return known

    def _describe_struct(self, struct: Struct, name: str) -> _Described:
        members: list[dict[str, Any]] = []
        reaches: set[str] = {name}
        for member in struct.members:
            entry = self._member(name, member)
            if isinstance(entry, Refusal):
                return entry
            described_member, reached = entry
            members.append(described_member)
            reaches.update(reached)
        self._register(
            name, {"type": "struct", "name": name, "members": members}, struct.declared_at
        )
        if name not in self._structures:
            self._structures.append(name)
        self._layout(name, struct)
        return name, frozenset(reaches)

    def _member(
        self, structure: str, member: Member
    ) -> tuple[dict[str, Any], frozenset[str]] | Refusal:
        if member.name is None:
            return Refusal(f"{structure}.<anonymous>", "an anonymous member", member.declared_at)
        path = f"{structure}.{member.name}"
        shape = shape_of(member.type)
        if shape.const or shape.volatile:
            self._qualifier_dropped(path, shape, member.declared_at)
        core = shape.core
        synthesized = f"{structure}_{member.name}_t"
        if isinstance(core, Unsupported):
            return Refusal(path, core.what, member.declared_at)
        if member.bit_size is not None:
            return self._bits(path, member, core, shape.name, synthesized)
        entry: dict[str, Any] = {"name": member.name, "member": "value"}
        if isinstance(core, Struct):
            nested = self._struct(core, shape.name, synthesized)
            if isinstance(nested, Refusal):
                return nested
            entry["typename"], reaches = nested
            if shape.dimensions:
                entry["dimensions"] = list(shape.dimensions)
            return entry, reaches
        scalar = self._scalar(core, path, shape.name, synthesized, member.declared_at)
        if isinstance(scalar, Refusal):
            return scalar
        entry["datatype"], entry["conversion"], reaches = scalar
        if shape.dimensions:
            entry["dimensions"] = list(shape.dimensions)
        return entry, reaches

    def _bits(
        self,
        path: str,
        member: Member,
        core: Base | Enum | Struct,
        alias: str | None,
        synthesized: str,
    ) -> tuple[dict[str, Any], frozenset[str]] | Refusal:
        if isinstance(core, Struct):
            return Refusal(path, "a bitfield of a structure", member.declared_at)
        entry: dict[str, Any] = {"name": member.name, "member": "bits"}
        if isinstance(core, Base) and core.encoding == DW_ATE_BOOLEAN:
            self._once(
                "elf-boolean-bitfield",
                path,
                f"'{path}' is a _Bool bitfield, described as a uint8 one of the same width: "
                f"DDD refuses a boolean bitfield",
                member.declared_at,
            )
            entry["datatype"] = "uint8"
            entry["conversion"] = {"kind": "identity"}
            entry["bits"] = member.bit_size
            return entry, frozenset()
        scalar = self._scalar(core, path, alias, synthesized, member.declared_at)
        if isinstance(scalar, Refusal):
            return scalar
        entry["datatype"], entry["conversion"], reaches = scalar
        entry["bits"] = member.bit_size
        return entry, reaches

    def _qualifier_dropped(self, path: str, shape: Shape, declared_at: Declared | None) -> None:
        stated = [word for word, on in (("const", shape.const), ("volatile", shape.volatile)) if on]
        self._once(
            "elf-qualifier-dropped",
            path,
            f"'{path}' is {' '.join(stated)} in C, which DDD cannot state of a member: DDD "
            f"qualifies whole objects",
            declared_at,
        )

    def _layout(self, name: str, struct: Struct) -> None:
        if struct.alignment is not None:
            self._once(
                "elf-alignment",
                name,
                f"'{name}' is aligned to {struct.alignment} bytes in C, which DDD cannot state: "
                f"the structure DDD generates is aligned as its members are",
                struct.declared_at,
            )
        end: int | None = 0
        for member in struct.members:
            label = f"{name}.{member.name}"
            if member.alignment is not None:
                self._once(
                    "elf-alignment",
                    label,
                    f"'{label}' is aligned to {member.alignment} bytes in C, which DDD cannot "
                    f"state",
                    member.declared_at,
                )
            gap = _gap(end, member)
            if gap:
                self._once(
                    "elf-bitfield-gap",
                    label,
                    f"'{label}' starts at bit {member.bit_offset} although it fits at bit {end}: "
                    f"an unnamed or zero width bitfield leaves such a gap, which DDD cannot "
                    f"state, so the structure DDD generates starts it at bit {end}",
                    member.declared_at,
                )
            end = _end(member)

    def _synthesize(self, key: Struct | Enum, name: str) -> str:
        known = self._synthesized.get(key)
        if known is not None:
            return known
        self._synthesized[key] = name
        what = "structure" if isinstance(key, Struct) else "enum"
        self._once(
            "elf-name-synthesized",
            name,
            f"an anonymous {what} is named '{name}', after the first thing that reaches it; "
            f"rename it if the source has a better name",
            key.declared_at,
        )
        return name

    def _register(
        self, name: str, description: dict[str, Any], declared_at: Declared | None
    ) -> None:
        known = self._named.setdefault(name, [])
        text = json.dumps(description)
        if all(json.dumps(other) != text for other, _ in known):
            known.append((description, declared_at))

    def _once(self, check: str, key: str, message: str, declared_at: Declared | None) -> None:
        if (check, key) in self._reported:
            return
        self._reported.add((check, key))
        report(self._bag, check, message, place(self._image, declared_at))


def _kind(shape: Shape) -> str:
    if not shape.const:
        return "measurement"
    if shape.dimensions:
        return "value_block"
    return "parameter"


def _gap(end: int | None, member: Member) -> int:
    """The bits before a bitfield that it would have fit into, or 0.

    That is the trace an unnamed or zero width bitfield leaves. "Would have fit" is the rule
    the System V ABIs and the AAPCS share: a bitfield starts at the next free bit unless it
    would then cross a boundary of its declared type's size. A gap that rule explains is
    padding the structure DDD generates reproduces, and is none of this function's business.
    """
    start = member.bit_offset
    if end is None or start is None or member.bit_size is None or start <= end:
        return 0
    size = size_of(member.type)
    # A bitfield's type is an integer or an enum here: any other was refused before the
    # layout of its structure was looked at.
    assert size is not None
    width = 8 * size
    if end // width != (end + member.bit_size - 1) // width:
        return 0
    return start - end


def _end(member: Member) -> int | None:
    if member.bit_offset is None:
        return None
    if member.bit_size is not None:
        return member.bit_offset + member.bit_size
    size = size_of(member.type)
    # Every member's type is described by the time the layout is looked at.
    assert size is not None
    return member.bit_offset + 8 * size
