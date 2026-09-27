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
from collections.abc import Callable, Iterable, Mapping
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


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """What one of the tab's vocabularies is, in the facts that differ between them.

    Three vocabularies share one table, one panel and one set of verbs, and they differ in a short,
    enumerable list: where their entries live, what their name key is called, which keys a reader
    may change and what judges each. Everything else - how a row is counted, how a use is found,
    how a rename reaches every naming site, how a file is created - is written once and takes one
    of these.

    Part 13 wrote all of it concretely for constants and recorded the ruling that this part would
    refactor rather than extend, so that the shape would be drawn from more than one real case. This
    record is that shape, drawn from three.
    """

    kind: str
    """The word a row carries in its own column: ``constant``, ``section``, ``raster``."""

    containers: tuple[str, ...]
    """The pointers its entries live at, first the vocabulary file's own. Only constants have a
    second: a component may declare them inline, where sections and rasters live in their own files
    alone."""

    name_key: str
    """What the entry calls its name: ``name`` for a constant, ``section``, ``raster``."""

    keys: tuple[str, ...]
    """Every key a reader may change, ``description`` among them, in the order the panel draws
    them."""

    strings: frozenset[str]
    """Of those keys, the ones whose json value is a string - so the panel shows them without their
    quotes and the row's cell reads as prose rather than as source."""

    entries: Callable[[Index], dict[str, Site]]
    """Where this vocabulary's own entries are recorded in the index."""

    used: Callable[[Index], dict[str, list[Site]]]
    """Where the places naming one are recorded."""

    states: Callable[[Mapping[str, str]], str]
    """The row's ``States`` cell, from the display texts of its keys. A constant states its value; a
    section its access and its alignment; a raster its event and its cycle. `Value` was the column's
    header while constants were alone in the tab and fits nothing else."""


CONSTANTS: Final = Vocabulary(
    kind=CONSTANT,
    containers=("constants", "component.constants"),
    name_key="name",
    keys=("value", "description"),
    strings=frozenset({"description"}),
    entries=lambda built: built.constants,
    used=lambda built: built.constant_uses,
    states=lambda texts: texts["value"],
)

HELD: Final = (CONSTANTS,)
"""Every vocabulary the Shared files tab holds. :func:`shared_rows` walks this; Task 4 adds a
word."""

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

    states: str
    """What the entry states, built by its vocabulary's own :attr:`Vocabulary.states` rule from the
    display text of its keys - a constant's value as the json text its file spells: ``16``,
    ``2.0``."""

    uses: int
    """How many shapes name it."""

    findings: int
    """How many findings are filed inside its entry or at a shape naming it."""

    @property
    def value(self) -> str:
        """``states``, under the name every row carried before this task renamed it.

        Two tests in `TestTheRows` (`tests/test_project_shared.py`) read this field by that name,
        and this task's proof is that suite passing without an edit to it. Renaming the field
        outright would need those two lines to change, which is exactly what the task says to stop
        and report instead of doing - so the field is ``states`` everywhere new, and this is the
        one place the old name still answers. For one task only, like the bindings below.
        """
        return self.states


@dataclass(frozen=True, slots=True)
class Use:
    """One shape that names an entry of a vocabulary."""

    site: Site

    kind: Literal["variable", "member"]
    """``variable`` for a declaration's ``dimensions`` entry or its axis ``size``, ``member`` for
    a structure member's ``dimensions`` entry."""

    name: str
    """The variable's name, or ``Sample_t.history`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member, whose structure may be
    declared in a types file no component owns, and which ``name`` locates instead."""


def located_on(
    vocabulary: Vocabulary, built: Index, name: str, file: Path, found: Diagnostic
) -> bool:
    """Whether this finding belongs to that entry of ``vocabulary``: filed inside its own record, or
    at a shape naming it.

    Wider than :func:`ddd.project_types.located_in_type`, which asks only about a type's own entry,
    and deliberately. A constant's ``dimension-value`` is filed at the shape, never at the entry,
    and is about nothing but its value; a table counting only the entry's own findings would show
    nothing for the one finding a reader of this tab has come to act on.

    Answered for a name no file declares too, which is what ``unknown-constant`` is: the question
    is whether the finding concerns that name, and the shape naming it is where it is filed.
    """
    location = found.location
    if location is None:
        return False
    resolved = file.resolve()
    entry = vocabulary.entries(built).get(name)
    places = [] if entry is None else [entry]
    places.extend(vocabulary.used(built).get(name, ()))
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
    """Every entry the tab lists, sorted by kind then name: every vocabulary in :data:`HELD`, from
    every home each declares its entries at.

    ``findings`` is read into a list once rather than walked per row: the api hands this a
    generator, and a second walk of a spent one would count nothing for every row but the first.
    """
    filed = list(findings)
    rows = [
        row_of(vocabulary, built, name, filed, cache)
        for vocabulary in HELD
        for name in sorted(vocabulary.entries(built))
    ]
    return tuple(sorted(rows, key=lambda row: (row.kind, row.name)))


def row_of(
    vocabulary: Vocabulary,
    built: Index,
    name: str,
    findings: Iterable[tuple[Path, Diagnostic]],
    cache: dict[Path, Document],
) -> SharedRow:
    """One entry's own row: what :func:`shared_rows` would answer for ``name`` of ``vocabulary``
    alone, without building every other row alongside it - what ``GET /api/constant`` needs one
    of."""
    filed = list(findings)
    return SharedRow(
        kind=vocabulary.kind,
        name=name,
        states=vocabulary.states(shown(vocabulary, built, name, cache)),
        uses=len(vocabulary.used(built).get(name, ())),
        findings=sum(
            1 for file, found in filed if located_on(vocabulary, built, name, file, found)
        ),
    )


def shown(
    vocabulary: Vocabulary, built: Index, name: str, cache: dict[Path, Document]
) -> dict[str, str]:
    """Each editable key's display text: a string key without its quotes, any other as the json text
    its file spells.

    Written as a loop rather than a comprehension with a conditional expression, which coverage.py
    counts no branch in - the arm no vocabulary of the day exercised would pass the gate unseen.
    """
    display: dict[str, str] = {}
    for key in vocabulary.keys:
        if key in vocabulary.strings:
            display[key] = string_of(vocabulary, built, name, key, cache)
        else:
            display[key] = text_of(vocabulary, built, name, key, cache)
    return display


def text_of(
    vocabulary: Vocabulary, built: Index, name: str, key: str, cache: dict[Path, Document]
) -> str:
    """The json text ``key`` is written as in that entry, or empty where the entry has it not:
    ``16``, ``2.0``, ``"slots of a trend buffer"``.

    The text and not the value, so that an edit built from what the page was shown writes back what
    was written.
    """
    entry = vocabulary.entries(built).get(name)
    if entry is None:
        return ""
    return read(entry.path, cache).raw_at(f"{entry.pointer}.{key}") or ""


def string_of(
    vocabulary: Vocabulary, built: Index, name: str, key: str, cache: dict[Path, Document]
) -> str:
    """The string ``key`` holds in that entry, or empty where it holds none.

    Beside :func:`text_of` rather than folded into it: a description is shown as prose and a value
    as the text it is written as, and reading a description through ``raw_at`` would put its quotes
    on the screen.
    """
    entry = vocabulary.entries(built).get(name)
    if entry is None:
        return ""
    value = read(entry.path, cache).value_at(f"{entry.pointer}.{key}")
    return value if isinstance(value, str) else ""


def uses_of(
    vocabulary: Vocabulary, built: Index, name: str, cache: dict[Path, Document]
) -> tuple[Use, ...]:
    """Every shape the index recorded naming ``name``, in the order it recorded them.

    A declaration comes with the component declaring it, as :func:`ddd.variables.declarations_of`
    reads it, and one its file no longer declares where the index recorded it is left out, as that
    function leaves it out: the file changed since the analysis, and the next revision lists it
    where it went.

    Written for a constant's own use shapes - a dimension entry, an axis size, a structure member's
    dimension - which is all any vocabulary in :data:`HELD` has today; a vocabulary whose uses are
    shaped differently is Task 4's to read.
    """
    found: list[Use] = []
    for site in vocabulary.used(built).get(name, ()):
        document = read(site.path, cache)
        member = _MEMBER_SHAPE.match(site.pointer)
        if member is not None:
            structure = document.value_at(f"{member.group(1)}.name")
            named = document.value_at(f"{member.group(1)}.{member.group(2)}.name")
            if isinstance(structure, str) and isinstance(named, str):
                found.append(Use(site, "member", f"{structure}.{named}", None))
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
            found.append(Use(site, "variable", variable, declared.component))
    return tuple(found)


# Bindings, for one task only. `tests/test_project_shared.py` passing untouched across the
# generalisation is the evidence that it moved no behaviour - the same evidence part 13's first task
# took from `tests/test_unit_plans.py`. Task 5 moves the api to the generic readers and deletes
# these; nothing else may call them.
def constant_row(
    built: Index,
    name: str,
    findings: Iterable[tuple[Path, Diagnostic]],
    cache: dict[Path, Document],
) -> SharedRow:
    return row_of(CONSTANTS, built, name, findings, cache)


def constant_text(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    return text_of(CONSTANTS, built, name, key, cache)


def constant_string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    return string_of(CONSTANTS, built, name, key, cache)


def constant_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Use, ...]:
    return uses_of(CONSTANTS, built, name, cache)


def located_on_constant(built: Index, name: str, file: Path, found: Diagnostic) -> bool:
    return located_on(CONSTANTS, built, name, file, found)
