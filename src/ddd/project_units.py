"""A project's units as the Units tab of ``ddd gui`` shows them, and what changing one takes.

Transport-neutral, like :mod:`ddd.variables`: nothing here knows about http or the session. Where
a unit is stated and which vocabulary entries list it is the navigation index's own record
(:attr:`ddd.lsp.navigation.Index.units` and :attr:`~ddd.lsp.navigation.Index.vocabulary`), and
every change is planned by :mod:`ddd.lsp.units`, beside the language server's rename, so that the
page and an editor cannot disagree about what renaming a unit reaches. What this adds is what a
page needs around the two: the table's rows, one unit's places with the component and the role
of each variable stating it, the findings that are the unit's own, and the edit a plan comes to
with the lines it changes, computed without writing anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.diagnostics import Diagnostic
from ddd.lsp.navigation import Index, Site, UnitSite
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import UnitPlan
from ddd.variables import Planned, declarations_of, hunks, planned

UNIT_CHECKS: Final = frozenset({"unknown-unit", "duplicate-unit"})
"""The findings that are a unit's own: stated outside the vocabulary, or listed in it twice."""


@dataclass(frozen=True, slots=True)
class UnitRow:
    """One unit as the Units tab lists it."""

    unit: str
    description: str | None
    """What the vocabulary says it means, or ``None`` outside it or for a spelling alone."""

    files: tuple[Path, ...]
    """The units files listing it, each once, in the index's order; empty outside the
    vocabulary."""

    variables: int
    types: int
    members: int
    findings: int
    """How many of its own findings - ``unknown-unit`` and ``duplicate-unit`` - are filed."""


@dataclass(frozen=True, slots=True)
class Place:
    """One place a unit is stated, as its panel lists it."""

    stated: UnitSite
    component: str | None
    """The component declaring the variable; ``None`` for a type or a member."""

    role: str | None
    """``produces``, ``reads`` or ``local`` for a variable; ``None`` for a type or a member."""


def unit_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[UnitRow, ...]:
    """Every unit the project states or its vocabulary lists, by spelling, with how many
    variables, types and structure members state it and how many of its own findings are filed.

    Counted from the index's record as it stands, the way the picker counts the units in use:
    a variable several components declare counts once, and so does a type or a member.
    """
    own = [(file, finding) for file, finding in findings if finding.check in UNIT_CHECKS]
    return tuple(
        UnitRow(
            unit=unit,
            description=description_of(built, unit, cache),
            files=tuple(dict.fromkeys(entry.path for entry in built.vocabulary.get(unit, ()))),
            variables=_stating(built, unit, "variable"),
            types=_stating(built, unit, "type"),
            members=_stating(built, unit, "member"),
            findings=sum(1 for file, finding in own if located_on_unit(built, unit, file, finding)),
        )
        for unit in sorted(built.units.keys() | built.vocabulary.keys())
    )


def description_of(built: Index, unit: str, cache: dict[Path, Document]) -> str | None:
    """What the vocabulary says ``unit`` means: the description of the first entry listing it,
    read from its file; ``None`` outside the vocabulary and for an entry that is a spelling
    alone."""
    first = next(iter(built.vocabulary.get(unit, ())), None)
    if first is None:
        return None
    described = read(first.path, cache).value_at(f"{first.pointer}.description")
    return described if isinstance(described, str) else None


def places_of(built: Index, unit: str, cache: dict[Path, Document]) -> tuple[Place, ...]:
    """Every place the index recorded stating ``unit``, in the order it recorded them.

    A variable comes with its component and its role as :func:`ddd.variables.declarations_of`
    reads them, and a variable its file no longer declares where the index recorded it is left
    out, as that function leaves it out: the file changed since the analysis, and the next
    revision lists it where it went.
    """
    found: list[Place] = []
    for stated in built.units.get(unit, ()):
        if stated.kind != "variable":
            found.append(Place(stated, None, None))
            continue
        definition = Site(stated.site.path, stated.site.pointer.removesuffix(".unit"))
        declared = next(
            (d for d in declarations_of(built, stated.name, cache) if d.site == definition), None
        )
        if declared is not None:
            found.append(Place(stated, declared.component, declared.role))
    return tuple(found)


def located_on_unit(built: Index, unit: str, file: Path, finding: Diagnostic) -> bool:
    """Whether a finding shown on ``file`` is one of ``unit``'s own: an ``unknown-unit`` or a
    ``duplicate-unit`` filed on a place stating it or on an entry listing it."""
    location = finding.location
    if location is None or finding.check not in UNIT_CHECKS:
        return False
    shown = file.resolve()
    return any(
        site.pointer == location.pointer and site.path.resolve() == shown
        for site in (
            *(stated.site for stated in built.units.get(unit, ())),
            *built.vocabulary.get(unit, ()),
        )
    )


def adoptable(built: Index | None, has_vocabulary: bool) -> int | None:
    """How many units adopting a vocabulary would list - every unit in use - or ``None`` when
    the project has a units file already, and so nothing to adopt."""
    if has_vocabulary:
        return None
    return 0 if built is None else len(built.units)


def previewed(plan: UnitPlan, fingerprints: Mapping[Path, str]) -> tuple[Planned, ...]:
    """The edit a plan comes to, file by file in the plan's order, and the lines it changes in
    each - made by the edit engine in memory and never written.

    A file the plan changes carries the fingerprint the analysis read it at, from
    ``fingerprints`` (keyed by resolved path), exactly as :func:`ddd.variables.preview` has it.
    A file the plan creates has none - ``POST /api/edit`` creates a file for a change without
    one - and its one hunk is the whole file, at line 1.
    """
    return tuple(
        Planned(edit.path, None, edit.operations, hunks("", edit.operations[0].raw or ""))
        if edit.creates
        else planned(edit.path, edit.operations, fingerprints)
        for edit in plan.edits
    )


def _stating(built: Index, unit: str, kind: str) -> int:
    """How many variables, types or members - by name, each once - state ``unit``."""
    return len({stated.name for stated in built.units.get(unit, ()) if stated.kind == kind})
