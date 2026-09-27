"""A project's constants as the Shared files tab shows them.

Transport-neutral, like :mod:`ddd.project_types` and :mod:`ddd.project_units`: nothing here knows
about http or the session. Where a constant is declared and which shapes name it is the navigation
index's own record (:attr:`ddd.lsp.navigation.Index.constants` and
:attr:`~ddd.lsp.navigation.Index.constant_uses`), and what an entry *says* is read from the
document at that entry, the way a type's keys are.

Nothing is parsed into the models: a value travels as the json text it is written as, so ``2.0``
reaches the page - and comes back to an edit - as the three characters its author typed. The format
treats ``2`` and ``2.0`` as different constants, so a panel that read the value and wrote it back
would retype one nobody asked it to.

Every function answers empty for a name the index does not hold. The api looks a name up before it
asks, so that arm is only reachable from a test - which is where it is covered.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.diagnostics import Diagnostic
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.variables import declarations_of

CONSTANT: Final = "constant"
"""The ``kind`` a constant's row carries. The tab holds three kinds once sections and rasters land;
the column is what tells a reader how to read the rest of the row."""

_DECLARATION_SHAPE: Final = re.compile(
    r"^(component\.interface\[\d+\]\.definition)\.(?:dimensions\[\d+\]|size)$"
)
"""A declaration's own shape - an entry of its ``dimensions``, or the ``size`` of its axis - and
the definition it belongs to, whose ``name`` names the variable."""

_MEMBER_SHAPE: Final = re.compile(
    r"^((?:component\.)?types\[\d+\])\.(members\[\d+\])\.dimensions\[\d+\]$"
)
"""A structure member's dimension, and the two halves of its address: the structure and the member.

The ``component.`` prefix is optional because a component may declare its own types inline,
alongside its interface, at ``component.types[i]`` rather than a types file's ``types[i]`` -
exactly as :data:`ddd.project_types._MEMBER_TYPENAME` allows, and for the same reason:
:mod:`ddd.loading` registers both homes under one name.
"""


@dataclass(frozen=True, slots=True)
class SharedRow:
    """One row of the Shared files tab."""

    kind: str
    """``constant``. Sections and rasters bring their own words here."""

    name: str

    value: str
    """What the entry states, as the json text its file spells: ``16``, ``2.0``."""

    uses: int
    """How many shapes name it."""

    findings: int
    """How many findings are filed inside its entry or at a shape naming it."""


@dataclass(frozen=True, slots=True)
class ConstantUse:
    """One shape that names a constant."""

    site: Site

    kind: Literal["variable", "member"]
    """``variable`` for a declaration's ``dimensions`` entry or its axis ``size``, ``member`` for
    a structure member's ``dimensions`` entry."""

    name: str
    """The variable's name, or ``Sample_t.history`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member, whose structure may be
    declared in a types file no component owns, and which ``name`` locates instead."""


def located_on_constant(built: Index, name: str, file: Path, found: Diagnostic) -> bool:
    """Whether this finding belongs to that constant: filed inside its entry, or at a shape naming
    it.

    Wider than :func:`ddd.project_types.located_in_type`, which asks only about a type's own entry,
    and deliberately. ``dimension-value`` is filed at the shape, never at the entry, and is about
    nothing but the constant's value; a table counting only the entry's own findings would show
    nothing for the one finding a reader of this tab has come to act on.

    Answered for a name no file declares too, which is what ``unknown-constant`` is: the question
    is whether the finding concerns that name, and the shape naming it is where it is filed.
    """
    location = found.location
    if location is None:
        return False
    resolved = file.resolve()
    entry = built.constants.get(name)
    places = [] if entry is None else [entry]
    places.extend(built.constant_uses.get(name, ()))
    return any(
        place.path.resolve() == resolved
        and (
            location.pointer == place.pointer
            or location.pointer.startswith((f"{place.pointer}.", f"{place.pointer}["))
        )
        for place in places
    )


def shared_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[SharedRow, ...]:
    """Every entry the tab lists, by name: the project's constants today, from both homes.

    ``findings`` is read into a list once rather than walked per row: the api hands this a
    generator, and a second walk of a spent one would count nothing for every row but the first.
    """
    filed = list(findings)
    return tuple(constant_row(built, name, filed, cache) for name in sorted(built.constants))


def constant_row(
    built: Index,
    name: str,
    findings: Iterable[tuple[Path, Diagnostic]],
    cache: dict[Path, Document],
) -> SharedRow:
    """One constant's own row: what :func:`shared_rows` would answer for ``name`` alone, without
    building every other row alongside it - what ``GET /api/constant`` needs one of."""
    filed = list(findings)
    return SharedRow(
        kind=CONSTANT,
        name=name,
        value=constant_text(built, name, "value", cache),
        uses=len(built.constant_uses.get(name, ())),
        findings=sum(1 for file, found in filed if located_on_constant(built, name, file, found)),
    )


def constant_text(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """The json text ``key`` is written as in that constant's entry, or empty where the entry has
    it not: ``16``, ``2.0``, ``"slots of a trend buffer"``.

    The text and not the value, so that an edit built from what the page was shown writes back what
    was written.
    """
    entry = built.constants.get(name)
    if entry is None:
        return ""
    return read(entry.path, cache).raw_at(f"{entry.pointer}.{key}") or ""


def constant_string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """The string ``key`` holds in that constant's entry, or empty where it holds none.

    Beside :func:`constant_text` rather than folded into it: a description is shown as prose and a
    value as the text it is written as, and reading a description through ``raw_at`` would put its
    quotes on the screen.
    """
    entry = built.constants.get(name)
    if entry is None:
        return ""
    value = read(entry.path, cache).value_at(f"{entry.pointer}.{key}")
    return value if isinstance(value, str) else ""


def constant_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[ConstantUse, ...]:
    """Every shape the index recorded naming ``name``, in the order it recorded them.

    A declaration comes with the component declaring it, as :func:`ddd.variables.declarations_of`
    reads it, and one its file no longer declares where the index recorded it is left out, as that
    function leaves it out: the file changed since the analysis, and the next revision lists it
    where it went.
    """
    found: list[ConstantUse] = []
    for site in built.constant_uses.get(name, ()):
        document = read(site.path, cache)
        member = _MEMBER_SHAPE.match(site.pointer)
        if member is not None:
            structure = document.value_at(f"{member.group(1)}.name")
            named = document.value_at(f"{member.group(1)}.{member.group(2)}.name")
            if isinstance(structure, str) and isinstance(named, str):
                found.append(ConstantUse(site, "member", f"{structure}.{named}", None))
            continue
        shape = _DECLARATION_SHAPE.match(site.pointer)
        # `_DECLARATION_SHAPE` and `_MEMBER_SHAPE` between them cover exactly what
        # `_DIMENSION_KEY` matches, which is the pointer shape navigation.index() writes here,
        # and tests/test_project_shared.py pins the two patterns to that authority. A pointer
        # neither matches would mean this module and `_DIMENSION_KEY` have drifted apart, not
        # that the file holds anything unexpected - and undercounting a constant's uses
        # silently is worse than failing loudly the moment the two fall out of step.
        assert shape is not None
        definition = shape.group(1)
        variable = document.value_at(f"{definition}.name")
        if not isinstance(variable, str):
            continue
        declared = next(
            (
                entry
                for entry in declarations_of(built, variable, cache)
                if entry.site == Site(site.path, definition)
            ),
            None,
        )
        if declared is not None:
            found.append(ConstantUse(site, "variable", variable, declared.component))
    return tuple(found)
