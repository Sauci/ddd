"""Which variables of an image the command line asks for (section 3.1 of the design)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Final

from ddd.diagnostics import DiagnosticBag, where
from ddd.elf import Image, Variable
from ddd.toolbox.findings import place, report

_GLOB: Final = frozenset("*?[")


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
    chosen: list[Variable] = []
    taken: set[tuple[str, int]] = set()
    judged: set[str] = set()
    for argument in arguments:
        matched: dict[str, list[Variable]] = {}
        for variable in image.variables:
            if _in_unit(variable, argument.unit) and _matches(variable, argument):
                matched.setdefault(variable.name, []).append(variable)
        if not matched:
            report(bag, "elf-symbol-missing", _missing(argument, image), where(image.path))
            continue
        for name in sorted(matched):
            group = _distinct(sorted(matched[name], key=lambda variable: variable.unit))
            (variable, *others) = group
            if not others and variable.address is not None:
                if (name, variable.address) not in taken:
                    taken.add((name, variable.address))
                    chosen.append(variable)
                continue
            if name in judged:
                continue
            judged.add(name)
            if others:
                _report_ambiguous(name, group, image, bag)
                continue
            report(
                bag,
                "elf-no-storage",
                f"'{name}' has no address in the image: {variable.missing}",
                place(image, variable.declared_at),
            )
    return chosen


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
    report(
        bag,
        "elf-symbol-ambiguous",
        f"'{name}' names a variable in {len(group)} units, {units}: prefix it with one, "
        f"as '{group[0].unit}:{name}'",
        place(image, group[0].declared_at),
        [
            (f"defined in '{variable.unit}'", place(image, variable.declared_at))
            for variable in group
        ],
    )
