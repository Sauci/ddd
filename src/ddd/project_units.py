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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ddd.diagnostics import Diagnostic
from ddd.finding_routes import UNIT_CHECKS
from ddd.findings_by_file import FindingsByFile, Pair
from ddd.lsp.navigation import Index, Site, UnitSite
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit, UnitProject, UnitRefusalError, adoption
from ddd.variables import Planned, declarations_of, hunks, planned, role_of


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
    built: Index, findings: FindingsByFile, cache: dict[Path, Document]
) -> tuple[UnitRow, ...]:
    """Every unit the project states or its vocabulary lists, by spelling, with how many
    variables, types and structure members state it and how many of its own findings are filed.

    Counted from the index's record as it stands, the way the picker counts the units in use:
    a variable several components declare counts once, and so does a type or a member. The
    findings are walked once, whole, for the ``unknown-unit`` and ``duplicate-unit`` among them,
    rather than asked file by file: the two checks are what is kept, and one unit may be stated
    in every file of a project.
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


def places_of(
    built: Index, unit: str, cache: dict[Path, Document], changed: Callable[[Path], bool]
) -> tuple[Place, ...]:
    """Every place the index recorded stating ``unit``, in the order it recorded them.

    A variable comes with its component and its role. On a file ``changed`` answers still reads
    as the analysis read it, both are what the analysis loaded there, the index's
    :attr:`~ddd.lsp.navigation.Index.components` and :attr:`~ddd.lsp.navigation.Index.scopes`,
    and the file is not parsed: read as :func:`ddd.variables.declarations_of` reads them, the
    12,500 places of ``A`` in a generated project of 100,000 declarations in 3,333 components,
    clean, took 2,822 ms, and 91 ms this way (Linux development PC, one run each). On a file
    changed since, the variable is read as that function reads it, and one its file no longer
    declares where the index recorded it is left out, as that function leaves it out: the next
    revision lists it where it went. ``changed`` is asked once of each file holding a variable
    stating the unit.
    """
    found: list[Place] = []
    since: dict[Path, bool] = {}
    for stated in built.units.get(unit, ()):
        if stated.kind != "variable":
            found.append(Place(stated, None, None))
            continue
        path = stated.site.path
        definition = Site(path, stated.site.pointer.removesuffix(".unit"))
        if path not in since:
            since[path] = changed(path)
        if not since[path]:
            found.append(Place(stated, built.components[path], role_of(built.scopes[definition])))
            continue
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
        for site in _sites(built, unit)
    )


def unit_findings(built: Index, unit: str, findings: FindingsByFile) -> list[Pair]:
    """Every finding that is ``unit``'s own, in the order given: what :func:`located_on_unit`
    keeps of every finding, asked only of the findings on the files its places and its entries
    are in, which are the only ones it can keep. Each file is named once, however many places it
    holds: a unit is stated three times over in a file as readily as once."""
    files = dict.fromkeys(site.path for site in _sites(built, unit))
    return [
        (file, found)
        for file, found in findings.on_any(files)
        if located_on_unit(built, unit, file, found)
    ]


def _sites(built: Index, unit: str) -> tuple[Site, ...]:
    """Everywhere a finding of ``unit``'s own can be filed: each place stating it, then each entry
    of the vocabulary listing it. What :func:`located_on_unit` compares a finding against, and so
    the files :func:`unit_findings` asks the findings of - one list, so that the files asked and
    the places compared cannot come to name different places."""
    return (
        *(stated.site for stated in built.units.get(unit, ())),
        *built.vocabulary.get(unit, ()),
    )


def adoptable(built: Index | None, project: UnitProject) -> int | None:
    """How many units adopting a vocabulary would list - every unit in use, none where the
    project states none - or ``None`` where adopting is refused.

    Answered by :func:`ddd.lsp.units.adoption`, the guards :func:`ddd.lsp.units.adopt_units`
    plans by, so the page offers adopting exactly where the plan comes to one: every refusal but
    "nothing to adopt" answers ``None``, and that one answers ``0``, for which the banner says
    there is nothing to adopt and draws no Adopt. A project the analysis could not read has no
    index, and so no plan either.
    """
    if built is None:
        return None
    try:
        planned = adoption(built, project)
    except UnitRefusalError:
        return None
    if planned is None:
        return 0
    return len(planned.units)


def previewed(
    edits: Sequence[PlannedEdit], fingerprints: Mapping[Path, str]
) -> tuple[Planned, ...]:
    """The edit a plan comes to, file by file in the plan's order, and the lines it changes in
    each - made by the edit engine in memory and never written.

    Takes a plan's edits rather than the plan itself, so that a :class:`~ddd.type_plans.TypePlan`
    and a :class:`~ddd.lsp.units.UnitPlan` - two different dataclasses sharing one shape - are
    both previewed by the one function, instead of each tab writing its own copy of it.

    A file the plan changes carries the fingerprint the analysis read it at, from
    ``fingerprints`` (keyed by resolved path), exactly as :func:`ddd.variables.preview` has it.
    A file the plan creates has none - ``POST /api/edit`` creates a file for a change without
    one - and its one hunk is the whole file, at line 1.
    """
    return tuple(
        Planned(edit.path, None, edit.operations, hunks("", edit.operations[0].raw or ""))
        if edit.creates
        else planned(edit.path, edit.operations, fingerprints)
        for edit in edits
    )


def _stating(built: Index, unit: str, kind: str) -> int:
    """How many variables, types or members - by name, each once - state ``unit``."""
    return len({stated.name for stated in built.units.get(unit, ()) if stated.kind == kind})
