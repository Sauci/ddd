"""What a linked image holds of the symbols it places, held to what the description says.

The image an a2l takes its addresses from is the one place the run sees the C the project was
built from, which is written by templates the project owns and edited by hand. The generator
cannot promise that C is what the description says; the image can show it. Each placed variable
is compared on four things - the size of one element, its encoding, the qualifiers the generated
C gives its kind, and its shape - and the type each member's path ends at on the first, the
second and the last: a qualifier belongs to the whole variable, which carries it.

A type is compared by what it resolves to: a ``UWORD`` declared as ``uint16_t`` agrees with a
``uint16``, and a ``uint32_t`` behind a ``uint16`` does not. Reading the image's debug
information (:mod:`ddd.elf`) and placing the symbols (:mod:`ddd.addresses`) are theirs; this
module only judges what they hand back, and is imported where an image is read, as they are.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import prod

from ddd.addresses import Held, Placed
from ddd.elf import (
    DW_ATE_BOOLEAN,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    Array,
    Base,
    CType,
    Enum,
    Image,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    size_of,
)
from ddd.ir import DataDictionary, ResolvedInstance, ResolvedLeaf, ResolvedObject
from ddd.models import Datatype, PointCounts, format_shape

_SIGNED = frozenset({DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR})
_UNSIGNED = frozenset({DW_ATE_UNSIGNED, DW_ATE_UNSIGNED_CHAR})

_UNTYPED = "void"
"""What the reader says of a variable whose debug information gives no type (``-g1``): nothing
to compare, and the description is not at fault."""


@dataclass(frozen=True, slots=True)
class Mismatch:
    """One placed variable the image holds otherwise than its description says."""

    message: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Seen:
    """A type of the image, taken apart: what is left of it with the qualifiers, the typedefs
    and the dimensions of its arrays peeled off."""

    core: CType
    dimensions: tuple[int, ...]
    const: bool
    volatile: bool
    spelled: str
    """The type as the source named it: the outermost typedef, else the base type."""


def _seen(ctype: CType) -> _Seen:
    const = volatile = False
    dimensions: list[int] = []
    spelled: str | None = None
    while True:
        if isinstance(ctype, Qualified):
            const |= ctype.const
            volatile |= ctype.volatile
            ctype = ctype.inner
        elif isinstance(ctype, Typedef):
            spelled = spelled or ctype.name
            ctype = ctype.inner
        elif isinstance(ctype, Array):
            dimensions.extend(ctype.dimensions)
            ctype = ctype.element
        else:
            break
    return _Seen(ctype, tuple(dimensions), const, volatile, spelled or _named(ctype))


def _named(core: CType) -> str:
    if isinstance(core, Base):
        return core.name
    if isinstance(core, Enum):
        return f"enum {core.tag}" if core.tag else "an enumeration"
    if isinstance(core, Struct):
        return f"struct {core.tag}" if core.tag else "a structure"
    assert isinstance(core, Unsupported)
    return core.what


def _kind(core: CType) -> str | None:
    """How the image encodes ``core``, in the words the description's datatypes are held to;
    None for what is no number."""
    if isinstance(core, Base):
        if core.encoding == DW_ATE_BOOLEAN:
            return "a boolean"
        if core.encoding == DW_ATE_FLOAT:
            return "a floating point number"
        if core.encoding in _SIGNED:
            return "a signed integer"
        if core.encoding in _UNSIGNED:
            return "an unsigned integer"
        return f"a base type of DWARF encoding {core.encoding:#x}"
    if isinstance(core, Enum):
        return "a signed integer" if core.signed else "an unsigned integer"
    return None


def _declared_kind(datatype: Datatype) -> str:
    if datatype is Datatype.BOOLEAN:
        return "a boolean"
    if datatype.is_float:
        return "a floating point number"
    return "a signed integer" if datatype.info.is_signed else "an unsigned integer"


def _qualifiers(const: bool, volatile: bool) -> str:
    return (
        " ".join(word for word, present in (("const", const), ("volatile", volatile)) if present)
        or "none"
    )


def _shape(dimensions: tuple[int, ...]) -> str:
    return format_shape(dimensions) or "a scalar"


def _differences(
    held: CType,
    *,
    datatype: Datatype | None,
    shape: tuple[int, ...],
    qualifiers: tuple[bool, bool] | None,
) -> list[str]:
    """What ``held`` says differently from the description: ``datatype``, which is None for a
    structure, whose members are compared where they are placed, its ``shape``, and its
    ``qualifiers`` (const and volatile) where the comparison is of the whole variable."""
    seen = _seen(held)
    core = seen.core
    found: list[str] = []
    if isinstance(core, Unsupported) and core.what == _UNTYPED:
        return found
    if datatype is not None:
        if _kind(core) is None:
            found.append(_says("type", datatype.value, f"{seen.spelled}, which is not a number"))
        else:
            found.extend(_numeric(core, datatype, seen.spelled))
    if seen.dimensions != shape:
        found.append(_says("shape", _shape(shape), _shape(seen.dimensions)))
    if qualifiers is not None and qualifiers != (seen.const, seen.volatile):
        found.append(
            _says("qualifiers", _qualifiers(*qualifiers), _qualifiers(seen.const, seen.volatile))
        )
    return found


def _numeric(core: CType, datatype: Datatype, spelled: str) -> list[str]:
    assert isinstance(core, Base | Enum)
    found: list[str] = []
    if core.size != datatype.size:
        found.append(
            _says(
                "size",
                f"{_bytes(datatype.size)} ({datatype.value})",
                f"{_bytes(core.size)} ({spelled})",
            )
        )
    kind = _kind(core)
    wanted = _declared_kind(datatype)
    # A boolean of one byte is as often an unsigned one - AUTOSAR's boolean is - and C's own is
    # a base type of its own: the description's boolean is either.
    one_byte_flag = datatype is Datatype.BOOLEAN and kind == "an unsigned integer"
    if kind != wanted and not one_byte_flag:
        enumeration = " enumeration" if isinstance(core, Enum) else ""
        found.append(_says("encoding", wanted, f"{kind}{enumeration}"))
    return found


def _bytes(count: int) -> str:
    return f"{count} byte" if count == 1 else f"{count} bytes"


_QUALIFIERS = "as its qualifiers"


def _says(what: str, stated: str, holds: str) -> str:
    return f"as its {what}, the description states {stated} and the image holds {holds}"


def _flat(entry: ResolvedObject) -> tuple[int, ...]:
    """The shape the generated C gives ``entry``: its own, or the single run of a table that
    stores its point counts ahead of its values."""
    if entry.point_counts is PointCounts.LEADING:
        return (len(entry.shape) + prod(entry.shape),)
    return tuple(entry.shape)


def disagreements(dictionary: DataDictionary, placed: Placed, image: Image) -> list[Mismatch]:
    """Every placed variable the image holds otherwise than the description states, and every
    variable the image describes in two ways, in the order of the variables' names.

    A variable the units of the image disagree on is reported as that and compared with
    nothing: its size is two numbers, and the description cannot be held to the first unit's
    just because it came first. Its members, which the same units describe, wait with it.
    """
    objects = dictionary.by_name
    instances = {entry.name: entry for entry in dictionary.instances}
    leaves = {entry.name: entry for entry in dictionary.leaves}
    by_variable: dict[str, list[tuple[str, Held]]] = {}
    for symbol, held in placed.held.items():
        by_variable.setdefault(held.variable.name, []).append((symbol, held))
    found: list[Mismatch] = []
    for name in sorted(by_variable):
        symbols = sorted(by_variable[name])
        variable = symbols[0][1].variable
        if symbols[0][1].apart:
            found.append(_apart(symbols[0][1], image))
            continue
        problems: list[tuple[str, list[str]]] = []
        if name in objects:
            entry = objects[name]
            problems.append(
                (
                    name,
                    _differences(
                        variable.type,
                        datatype=entry.datatype,
                        shape=_flat(entry),
                        qualifiers=(entry.is_calibration, entry.volatile),
                    ),
                )
            )
        else:
            instance = instances[name]
            problems.append(
                (
                    name,
                    _differences(
                        variable.type,
                        datatype=None,
                        shape=tuple(instance.shape),
                        qualifiers=(instance.is_calibration, instance.volatile),
                    ),
                )
            )
            problems.extend(_members(symbols, leaves))
        found.extend(_reported(variable, problems))
        found.extend(_declarations(name, symbols[0][1], objects.get(name) or instances[name]))
    return found


def _declarations(
    name: str, held: Held, entry: ResolvedObject | ResolvedInstance
) -> list[Mismatch]:
    """The units whose declaration of ``name`` states other qualifiers than its kind carries.

    A consumer's ``extern`` that leaves out ``volatile`` lets its compiler read the variable once
    where the description says something else writes it, and one that leaves out ``const`` lets
    it write a calibration. What a declaration may add is ``const``, which ``--const-inputs``
    gives the inputs of a component on purpose; every other difference is judged as the
    definition's is.
    """
    stated = (entry.is_calibration, entry.volatile)
    found: list[Mismatch] = []
    for declaration in held.declarations:
        seen = _seen(declaration.type)
        if isinstance(seen.core, Unsupported) and seen.core.what == _UNTYPED:
            continue
        if seen.volatile == stated[1] and (seen.const or not stated[0]):
            continue
        holds = _qualifiers(seen.const, seen.volatile)
        found.append(
            Mismatch(
                f"'{name}' is declared in '{declaration.unit}' otherwise than its description "
                f"states: as its qualifiers, the description states {_qualifiers(*stated)} and "
                f"the declaration holds {holds}",
                (
                    "a unit that reads the variable through such a declaration is compiled "
                    "without the qualifiers the description gives it",
                    *_declared(declaration),
                ),
            )
        )
    return found


def _members(
    symbols: Iterable[tuple[str, Held]], leaves: dict[str, ResolvedLeaf]
) -> list[tuple[str, list[str]]]:
    return [
        (
            symbol,
            _differences(
                held.ctype,
                datatype=leaves[symbol].datatype,
                shape=tuple(leaves[symbol].shape),
                qualifiers=None,
            ),
        )
        for symbol, held in symbols
    ]


def _reported(variable: Variable, problems: list[tuple[str, list[str]]]) -> list[Mismatch]:
    return [
        Mismatch(
            f"'{symbol}' is not held by the image as its description states: {'; '.join(found)}",
            _notes(variable, qualifiers_only=all(text.startswith(_QUALIFIERS) for text in found)),
        )
        for symbol, found in problems
        if found
    ]


def _notes(variable: Variable, *, qualifiers_only: bool) -> tuple[str, ...]:
    """What follows from the difference: the a2l is written from the description, so a size, an
    encoding or a shape the image does not hold is read wrongly by whoever reads the a2l; a
    qualifier is no part of the a2l, and what changes is the code compiled from the C."""
    if qualifiers_only:
        consequence = (
            "the a2l carries no qualifier, so what differs is the code compiled from this "
            "definition, which treats the variable as the image holds it"
        )
    else:
        consequence = (
            "the a2l is written from the description, so a calibration tool reads this variable "
            "as the image does not hold it"
        )
    return (consequence, *_declared(variable))


def _declared(variable: Variable) -> tuple[str, ...]:
    declared = variable.declared_at
    if declared is None:
        return ()
    return (f"the image's debug information declares it at {declared.path}:{declared.line}",)


def _apart(held: Held, image: Image) -> Mismatch:
    variable = held.variable
    by_size: dict[int, list[str]] = {}
    for there in held.apart:
        size = size_of(there.type)
        if size is not None:
            by_size.setdefault(size, []).append(f"'{there.unit}'")
    assert variable.address is not None
    symbol = image.object_sizes.get((variable.name, variable.address))
    if symbol:
        by_size.setdefault(symbol, []).append("the symbol table")
    described = " and as ".join(f"{_bytes(size)} by {_listed(by)}" for size, by in by_size.items())
    return Mismatch(
        f"'{variable.name}' at {variable.address:#x} is described by the image as {described}: "
        "one name at one address is one variable, so the description is held to none of them",
        _declared(variable),
    )


def _listed(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
