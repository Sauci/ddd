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
    are findings rather than usage errors, so that one run reports every one of them.
    """
    chosen: list[Variable] = []
    taken: set[tuple[str, str]] = set()
    judged: set[str] = set()
    for argument in arguments:
        matched = [
            variable
            for variable in image.variables
            if _in_unit(variable, argument.unit) and _matches(variable, argument)
        ]
        if not matched:
            report(bag, "elf-symbol-missing", _missing(argument, image), where(image.path))
            continue
        for name in sorted({variable.name for variable in matched}):
            group = sorted(
                (variable for variable in matched if variable.name == name),
                key=lambda variable: variable.unit,
            )
            if len(group) > 1:
                if name not in judged:
                    judged.add(name)
                    _report_ambiguous(name, group, image, bag)
                continue
            (variable,) = group
            if variable.address is None:
                if name not in judged:
                    judged.add(name)
                    report(
                        bag,
                        "elf-no-storage",
                        f"'{name}' has no address in the image: {variable.missing}",
                        place(image, variable.declared_at),
                    )
                continue
            key = (variable.name, variable.unit)
            if key not in taken:
                taken.add(key)
                chosen.append(variable)
    return chosen


def _in_unit(variable: Variable, unit: str | None) -> bool:
    if unit is None:
        return True
    spelled = variable.unit.replace("\\", "/")
    return spelled == unit or spelled.endswith(f"/{unit}")


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
    if argument.pattern in image.symbols:
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
