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
from typing import Any, Final, Literal

from pydantic import TypeAdapter

from ddd.diagnostics import Diagnostic
from ddd.lsp.navigation import Index, Site, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.models.constants import ConstantValue
from ddd.variables import declarations_of

CONSTANT: Final = "constant"
"""The ``kind`` a constant's row carries. The tab holds three kinds once sections and rasters land;
the column is what tells a reader how to read the rest of the row."""


@dataclass(frozen=True, slots=True)
class Judgement:
    """What a key's json text is judged by, and the clause naming what it should have been.

    Kept apart from a bare :class:`~pydantic.TypeAdapter`: ``_judged`` in :mod:`ddd.shared_plans`
    builds one refusal sentence for every key of every vocabulary, and ``tail`` is the one part an
    adapter alone cannot supply back - a constant's value and its description share the sentence's
    shape and differ only in this clause.
    """

    adapter: TypeAdapter[Any]
    tail: str


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
    alone.

    The first entry is what a file needs at its top level to be recognised as one of the
    vocabulary's own (:func:`~ddd.shared_plans.project_of`) and what a newly created file wraps
    its first entry in (:func:`~ddd.shared_plans._created`), so it must be a bare top-level key -
    ``"constants"``, not ``"component.constants"``. A later entry nests under a container of its
    own instead, the way ``component.constants`` does. :meth:`__post_init__` enforces the first
    half of that; nothing enforces the second, because only one vocabulary has a second entry to
    check."""

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

    uses: Callable[[Index, str, dict[Path, Document]], tuple[Use, ...]]
    """Every shape naming one entry, resolved rather than merely located: :attr:`used` only says
    where the index recorded a naming shape, and this reads what each site there actually says. A
    constant's own shapes are a dimension entry, an axis size, a structure member's dimension; a
    section's and a raster's are different shapes entirely - so unlike :attr:`entries`, :attr:`used`
    and :attr:`states`, each a one-line lambda, this is bound to a named function per vocabulary."""

    required: frozenset[str]
    """Of ``keys``, the ones the model gives no default, so a reader may not take them away: a
    constant's ``value``, a section's ``access`` and ``alignment``. A file missing one does not
    load, which is the outcome the interface refuses rather than writes."""

    filename: str
    """The file ``add`` writes beside the project description where the project includes none, named
    for what it holds so that whoever opens the checkout can tell."""

    judge: Mapping[str, Judgement]
    """Per key, what its json text is judged by and the clause a refusal names it with. The
    interface never restates a rule: a constant's value is judged by ``ConstantValue``, a section's
    alignment by its own field's power-of-two rule."""

    name_judge: Callable[[Index, str], str | None]
    """What decides whether a name may be used: the index and the wanted name in, the sentence
    refusing it or ``None`` out. Not a model of the string, because the answer depends on what the
    project already holds. A constant's is ``rename_problem``, whose c identifier rule and
    ``occupied`` check fit a constant and neither of the others: a section's name is a linker string
    and a raster's an a2l short name, and neither joins the namespace ``occupied`` guards."""

    def __post_init__(self) -> None:
        """Three checks tying ``keys``, ``required``, ``judge`` and ``containers`` together, so a
        descriptor that drops a key from one of these tables fails at construction rather than the
        first time a reader reaches the one that fell out of step.

        Unreachable through :data:`CONSTANTS` today - which is exactly why it matters. The next
        vocabulary is hand-written, and the one after it a third time: ``dataclasses.replace(
        CONSTANTS, keys=("value", "description", "comment"))`` gives a descriptor whose ``judge``
        does not cover ``comment``, and :func:`~ddd.shared_plans._judged`'s ``vocabulary.judge[
        key]`` has no guard of its own - so setting ``comment`` would raise ``KeyError`` where a
        reader should meet a refusal, and nothing before this would have said so.
        """
        unjudged = [key for key in self.keys if key not in self.judge]
        if unjudged:
            msg = f"{self.kind}: {unjudged} in keys but judge has no entry for them"
            raise ValueError(msg)
        ungiven = sorted(self.required - set(self.keys))
        if ungiven:
            msg = f"{self.kind}: {ungiven} in required but not in keys"
            raise ValueError(msg)
        if "." in self.containers[0]:
            msg = f"{self.kind}: containers[0] '{self.containers[0]}' is not a bare top-level key"
            raise ValueError(msg)


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
        for name in vocabulary.entries(built)
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
    """Every shape the index recorded naming ``name``, in the order it recorded them: whatever
    :attr:`Vocabulary.uses` ``vocabulary`` binds - a constant's own shapes for :data:`CONSTANTS`,
    a different reading entirely for a vocabulary shaped differently."""
    return vocabulary.uses(built, name, cache)


def _constant_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Use, ...]:
    """:data:`CONSTANTS`'s :attr:`~Vocabulary.uses`: a dimension entry, an axis size, or a
    structure member's dimension, in the order the index recorded them.

    A declaration comes with the component declaring it, as :func:`ddd.variables.declarations_of`
    reads it, and one its file no longer declares where the index recorded it is left out, as that
    function leaves it out: the file changed since the analysis, and the next revision lists it
    where it went.

    Bound to :data:`CONSTANTS` rather than generalised: a section is named only at a definition's
    ``section`` key and a raster at a definition's or a component's own ``raster`` - neither a
    dimension entry, an axis size, nor a structure member - so each vocabulary reads its own uses
    through its own function instead of sharing this one.
    """
    found: list[Use] = []
    for site in built.constant_uses.get(name, ()):
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


_VALUE: Final[TypeAdapter[ConstantValue]] = TypeAdapter(ConstantValue)
"""The format's own judge of what a constant's value may hold, so that the interface and the
loader cannot come to different answers. Strict on both arms, which is what keeps ``2`` a whole
constant and ``2.0`` a fractional one."""

_DESCRIPTION: Final[TypeAdapter[str]] = TypeAdapter(str)
"""The format's own judge of what a description may hold: any string, and nothing else -
``ConstantDeclaration.description`` is a plain ``str``, so this need only refuse what a string can
never be: a number, a bool, ``null``, an array, an object."""


def _constant_name_judge(built: Index, to: str) -> str | None:
    """:data:`CONSTANTS`'s :attr:`~Vocabulary.name_judge`: ``rename_problem``, called exactly as
    ``rename_constant`` and ``add_constant`` always called it, so a constant's rename and its
    declaration refuse a name in the same words they always have. Its c identifier rule and
    ``occupied`` check fit a constant and neither of the other two: a section's name is a linker
    string and a raster's an a2l short name."""
    return rename_problem(built, to, "constant")


CONSTANTS: Final = Vocabulary(
    kind=CONSTANT,
    containers=("constants", "component.constants"),
    name_key="name",
    keys=("value", "description"),
    strings=frozenset({"description"}),
    entries=lambda built: built.constants,
    used=lambda built: built.constant_uses,
    states=lambda texts: texts["value"],
    uses=_constant_uses,
    required=frozenset({"value"}),
    filename="constants.ddd.json",
    judge={
        "value": Judgement(
            _VALUE,
            "a whole number a 64 bit target holds, of either sign, or a finite fractional one",
        ),
        "description": Judgement(_DESCRIPTION, "a json string"),
    },
    name_judge=_constant_name_judge,
)

HELD: Final = (CONSTANTS,)
"""Every vocabulary the Shared files tab holds. :func:`shared_rows` walks this; Task 4 adds a
word."""


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
