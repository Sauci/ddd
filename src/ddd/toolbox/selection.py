"""Which variables of an image the command line asks for (section 3.1 of the design)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Final

from ddd.diagnostics import DiagnosticBag, where
from ddd.elf import DECLARED_ONLY, Image, Variable, described_apart, size_of, without_address
from ddd.toolbox.findings import place, report

_GLOB: Final = frozenset("*?[")

_UNDESCRIBED: Final = (
    "defined where the debug information does not describe it, in assembly or in a unit built "
    "without -g"
)


@dataclass(frozen=True, slots=True)
class Wanted:
    """One ``SYMBOL`` argument: a name or a glob, and the unit it is narrowed to, if any."""

    text: str
    unit: str | None
    pattern: str
    glob: bool


def wanted(text: str) -> Wanted:
    """Read one ``[UNIT:]PATTERN`` argument; a malformed one is a usage error.

    The argument is split at its last colon, which neither a C identifier nor a glob holds, so
    a unit spelled with a drive letter keeps it.
    """
    unit, colon, pattern = text.rpartition(":")
    if not pattern:
        msg = f"'{text}' names no variable: give a name or a pattern after the unit"
        raise ValueError(msg)
    if colon and not unit:
        msg = f"'{text}' names no unit before its colon"
        raise ValueError(msg)
    return Wanted(text, unit or None, pattern, not _GLOB.isdisjoint(pattern))


def select(image: Image, arguments: Sequence[Wanted], bag: DiagnosticBag) -> list[Variable]:
    """The variables the arguments name, in their order, each once; a glob's in name order.

    An argument naming nothing, a name several units define and a variable without storage
    are findings rather than usage errors, so that one run reports every one of them, and
    each name is reported once however many arguments reach it. A name at one address is one
    variable, however many units describe it: ``-fcommon`` makes a tentative definition in
    several units one variable, which the DWARF of each unit describes.
    """
    # Every unit's variable of each name, gathered once: a disagreement is judged over all of
    # them, and a scan of the image for each name a glob matched cost the square of the names.
    named: dict[str, list[Variable]] = {}
    for variable in image.variables:
        named.setdefault(variable.name, []).append(variable)
    chosen: list[tuple[Variable, str]] = []
    taken: set[tuple[str, int]] = set()
    judged: set[str] = set()
    disagreed: set[tuple[str, int]] = set()
    for argument in arguments:
        matched: dict[str, list[Variable]] = {}
        for variable in image.variables:
            if _in_unit(variable, argument.unit) and _matches(variable, argument):
                matched.setdefault(variable.name, []).append(variable)
        if not matched:
            report(bag, "elf-symbol-missing", _missing(argument, image), where(image.path))
            continue
        for name in sorted(matched):
            ordered = sorted(matched[name], key=lambda variable: variable.unit)
            apart = described_apart(named[name], image)
            # Only the addresses this argument reaches: another is its own variable's.
            apart = {
                address: there
                for address, there in apart.items()
                if address in {variable.address for variable in ordered}
            }
            for address, there in apart.items():
                if (name, address) not in disagreed:
                    disagreed.add((name, address))
                    _report_disagreement(name, address, there, image, bag)
            group = _distinct(ordered)
            (variable, *others) = group
            if not others and variable.address is not None:
                # A disagreeing address is reported above and chosen by no argument; it is left
                # out of what is chosen only, so that it still counts toward an ambiguity.
                if variable.address not in apart and (name, variable.address) not in taken:
                    taken.add((name, variable.address))
                    chosen.append((variable, argument.text))
                continue
            if name in judged:
                continue
            judged.add(name)
            if others and any(member.address is not None for member in group):
                _report_ambiguous(name, group, image, bag)
                continue
            report(
                bag,
                "elf-no-storage",
                _without_storage(name, group, image),
                place(image, variable.declared_at),
            )
    return _once_each(chosen, image, bag)


def _without_storage(name: str, group: Sequence[Variable], image: Image) -> str:
    """The sentence for a name none of whose variables has an address. Where several units
    describe it, as a header's ``static const`` each unit folded, no unit's prefix would take
    it, so the sentence names the units and the reasons instead of asking for a prefix."""
    (variable, *others) = group
    if not others:
        if variable.missing == DECLARED_ONLY and name in image.symbols:
            return (
                f"'{name}' has no address in the image: its debug information only declares "
                f"it, and the symbol table holds it, {_UNDESCRIBED}"
            )
        return without_address(name, variable.missing)
    units = ", ".join(f"'{member.unit}'" for member in group)
    reasons = "; ".join(dict.fromkeys(member.missing for member in group))
    return (
        f"'{name}' has no address in the image, in any of its {len(group)} units, {units}: "
        f"{reasons}"
    )


def _once_each(
    chosen: Sequence[tuple[Variable, str]], image: Image, bag: DiagnosticBag
) -> list[Variable]:
    """The chosen variables with every name two of them share refused, in the reader's terms:
    DDD names an object once, and a check of its own would say so in the words of a component
    the tool made up, where here the reader is told which arguments reached which variables."""
    by_name: dict[str, list[tuple[Variable, str]]] = {}
    for variable, text in chosen:
        by_name.setdefault(variable.name, []).append((variable, text))
    twice = {name for name, found in by_name.items() if len(found) > 1}
    for name in sorted(twice):
        found = by_name[name]
        spelt = [f"as '{text}' (in '{variable.unit}')" for variable, text in found]
        times = "twice" if len(found) == 2 else f"{len(found)} times"
        report(
            bag,
            "elf-symbol-ambiguous",
            f"'{name}' is asked for {times}, {_listed(spelt)}: DDD names an object once, so two "
            f"variables of one name cannot both be described",
            place(image, found[-1][0].declared_at),
            [
                (f"asked for as '{text}'", place(image, variable.declared_at))
                for variable, text in found
            ],
        )
    return [variable for variable, _ in chosen if variable.name not in twice]


def _listed(parts: Sequence[str]) -> str:
    """``parts`` as prose: joined by commas, the last by ``and``."""
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _report_disagreement(
    name: str, address: int, there: Sequence[Variable], image: Image, bag: DiagnosticBag
) -> None:
    sized = [(variable, size) for variable in there if (size := size_of(variable.type)) is not None]
    by_size: dict[int, list[str]] = {}
    for variable, size in sized:
        by_size.setdefault(size, []).append(f"'{variable.unit}'")
    described = _listed([f"as {size} bytes by {_listed(units)}" for size, units in by_size.items()])
    message = f"'{name}' at {address:#x} is described {described}"
    symbol = image.object_sizes.get((name, address))
    if symbol:
        message += f", and the symbol table holds it as {symbol} bytes"
    message += ": one name at one address is one variable, so no one description of it is right"
    report(
        bag,
        "elf-type-conflict",
        message,
        place(image, sized[0][0].declared_at),
        [
            (f"described as {size} bytes here", place(image, variable.declared_at))
            for variable, size in sized
        ],
    )


def _distinct(group: Sequence[Variable]) -> list[Variable]:
    """One variable per address: the first unit's, where several units describe one. A
    variable without storage is one of its own."""
    seen: set[int] = set()
    distinct: list[Variable] = []
    for variable in group:
        if variable.address is not None:
            if variable.address in seen:
                continue
            seen.add(variable.address)
        distinct.append(variable)
    return distinct


def _in_unit(variable: Variable, unit: str | None) -> bool:
    """Whether ``variable`` is of ``unit``, whole or by its trailing components, the separators
    of both spelled as forward slashes - a Windows build records its units with backslashes,
    and the argument repeats them, as the ambiguity's own hint does."""
    if unit is None:
        return True
    spelled = variable.unit.replace("\\", "/")
    asked = unit.replace("\\", "/")
    return spelled == asked or spelled.endswith(f"/{asked}")


def _matches(variable: Variable, argument: Wanted) -> bool:
    if argument.glob:
        return fnmatchcase(variable.name, argument.pattern)
    return variable.name == argument.pattern


def _missing(argument: Wanted, image: Image) -> str:
    within = ""
    if argument.unit is not None:
        within = f" in unit '{argument.unit}'"
    if argument.glob:
        return f"no variable of the image's debug information matches '{argument.pattern}'{within}"
    message = f"the image's debug information holds no variable named '{argument.pattern}'{within}"
    # The hint is true only where no unit's DWARF holds the name: asked for in the wrong unit,
    # a variable is missing there, and its own unit has debug information.
    described = any(variable.name == argument.pattern for variable in image.variables)
    if argument.pattern in image.symbols and not described:
        message += (
            "; the symbol table holds it, so the unit defining it was built without debug "
            "information (-g)"
        )
    return message


def _report_ambiguous(
    name: str, group: Sequence[Variable], image: Image, bag: DiagnosticBag
) -> None:
    units = ", ".join(f"'{variable.unit}'" for variable in group)
    # A unit without storage would earn elf-no-storage, so the offered prefix is one that has some.
    offered = next(variable for variable in group if variable.address is not None)
    report(
        bag,
        "elf-symbol-ambiguous",
        f"'{name}' names a variable in {len(group)} units, {units}: prefix it with one, "
        f"as '{offered.unit}:{name}'",
        place(image, group[0].declared_at),
        [
            (f"defined in '{variable.unit}'", place(image, variable.declared_at))
            for variable in group
        ],
    )
