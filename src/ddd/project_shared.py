"""A project's constants, its memory sections and its measurement rasters as the Shared files tab
shows them.

Transport-neutral, like :mod:`ddd.project_types` and :mod:`ddd.project_units`: nothing here knows
about http or the session. Where an entry is declared and which shapes name it is the navigation
index's own record, one pair of dictionaries per vocabulary
(:attr:`ddd.lsp.navigation.Index.constants` and :attr:`~ddd.lsp.navigation.Index.constant_uses`,
:attr:`~ddd.lsp.navigation.Index.sections` and :attr:`~ddd.lsp.navigation.Index.section_uses`,
:attr:`~ddd.lsp.navigation.Index.rasters` and :attr:`~ddd.lsp.navigation.Index.raster_uses`),
and what an entry *says* is read from the document at that entry, the way a type's keys are.

Nothing is parsed into the models: a value travels as the json text it is written as, so ``2.0``
reaches the page - and comes back to an edit - as the three characters its author typed. The format
treats ``2`` and ``2.0`` as different constants, so a panel that read the value and wrote it back
would retype one nobody asked it to.

Every function answers empty for a name the index does not hold. The api looks a name up before it
asks, so that arm is only reachable from a test - which is where it is covered.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Final, Literal

from pydantic import BeforeValidator, TypeAdapter

from ddd.diagnostics import Diagnostic
from ddd.finding_routes import ABOUT_THE_DECLARATION
from ddd.lsp.navigation import Index, Site, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.models.constants import ConstantValue
from ddd.models.rasters import RasterDeclaration
from ddd.models.sections import SectionAccess, SectionDeclaration
from ddd.variables import component_of, declarations_of

CONSTANT: Final = "constant"
"""The ``kind`` a constant's row carries. The tab holds three kinds; the column is what tells a
reader how to read the rest of the row."""

SECTION: Final = "section"
"""The ``kind`` a section's row carries, and the word :func:`~ddd.lsp.navigation.rename_problem`
knows a section's name rule by - one string, so that the row a reader clicks and the judge that
refuses their new name cannot be about two different things."""

RASTER: Final = "raster"
"""The ``kind`` a raster's row carries, and the word
:func:`~ddd.lsp.navigation.rename_problem` knows a raster's name rule by - one string, for the
reason :data:`SECTION` is one."""


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
    constant's ``value``, a section's ``access`` and ``alignment``, a raster's ``event``. A file
    missing one does not load, which is the outcome the interface refuses rather than writes.

    A raster's ``cycle`` is deliberately not one of them, and is the first key of any vocabulary a
    reader may take away: :class:`~ddd.models.rasters.RasterDeclaration` gives it the default
    ``None`` and says why - an event that is not cyclic is a real kind of raster rather than an
    omission."""

    filename: str
    """The file ``add`` writes beside the project description where the project includes none, named
    for what it holds so that whoever opens the checkout can tell."""

    judge: Mapping[str, Judgement]
    """Per key, what its json text is judged by and the clause a refusal names it with. The
    interface never restates a rule: a constant's value is judged by ``ConstantValue``, a section's
    alignment by its own field's power-of-two rule."""

    taken: Mapping[str, Callable[[Index, str | None, str, dict[Path, Document]], str | None]]
    """Per key whose value is the project's alone, what refuses a value another entry claims.

    The index, the entry whose key is being set - ``None`` where there is no entry yet, as an
    ``add`` has none - the wanted value, and the document cache; the sentence refusing it, or
    ``None``.

    A map rather than the single ``name_judge`` it replaces, because a raster has **two** such
    keys: its name and its ``event``. :func:`~ddd.shared_plans._judged` takes no :class:`Index`,
    so a key's own judge can ask whether a value is legal and never whether it is taken.

    Never empty, and never without :attr:`name_key`: every vocabulary has a name, and that name is
    the project's alone in every one of them. ``rename_entry`` and ``add_entry`` both index
    ``taken[name_key]`` with no guard of their own, so a map lacking it - the empty one, or one
    holding only a second key, as a rasters descriptor written ``{"event": ...}`` would - imports
    clean and raises ``KeyError`` at the first rename. :meth:`__post_init__` refuses it instead. A
    vocabulary with nothing but its name carries a map of one, not a map of none.

    The entry is given because an event needs it: a panel asks for a plan on every keystroke, so a
    reader re-typing the event their raster already claims must not be told it is taken by
    themselves. A name judge ignores it, which preserves what part 14 settled - a rename of a name
    to itself is refused, and says nothing about a reader's real mistake either way.

    The cache is given because :attr:`Index.rasters` maps a name to a :class:`Site` and **not** to
    its event: asking which raster claims one means reading each entry's own text, as
    :func:`text_of` does and takes a cache for. A name judge ignores this too - a name is in the
    index - so both name judges carry two arguments they do not read. That is the price of one map
    over two fields, and it is paid once.

    A constant's judge is ``rename_problem``, whose c identifier rule and ``occupied`` check fit a
    constant and neither of the others: a section's name is a linker string and a raster's an a2l
    short name, and neither joins the namespace ``occupied`` guards.
    """

    def __post_init__(self) -> None:
        """Six checks tying ``keys``, ``required``, ``judge``, ``name_key``, ``taken`` and
        ``containers`` together, so a
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
        if self.name_key in self.keys:
            msg = (
                f"{self.kind}: name_key '{self.name_key}' is also in keys, so the api would offer "
                "the name through set, which renames the entry and nothing that spells it"
            )
            raise ValueError(msg)
        if "." in self.containers[0]:
            msg = f"{self.kind}: containers[0] '{self.containers[0]}' is not a bare top-level key"
            raise ValueError(msg)
        for key in sorted(self.taken):
            if key == self.name_key:
                continue
            if key in self.keys:
                continue
            msg = f"{self.kind}: taken names '{key}', which is neither the name key nor settable"
            raise ValueError(msg)
        if self.name_key not in self.taken:
            # The check above's other direction, and the one a map can fail while every key in it
            # is legal: `{"event": ...}` alone is a plausible hand-written rasters map and holds
            # nothing the check above can complain about. `rename_entry` and `add_entry` index
            # `taken[name_key]` with no guard of their own, so that descriptor imports clean and
            # raises `KeyError` at the first rename - the outcome this method exists to turn into
            # a refusal, here for the same reason it does for `judge`.
            msg = (
                f"{self.kind}: taken has no judge for the name key '{self.name_key}', which "
                "rename and add both ask it for unconditionally"
            )
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
    """``constant``, ``section`` or ``raster``."""

    name: str

    states: str
    """What the entry states, built by its vocabulary's own :attr:`Vocabulary.states` rule from the
    display text of its keys - a constant's value as the json text its file spells (``16``,
    ``2.0``), a section's access and alignment in one cell (``read-only, align 4``), a raster's
    event and cycle in one too (``event 1, 10ms``)."""

    uses: int
    """How many shapes name it."""

    findings: int
    """How many findings are filed inside its entry or at a shape naming it."""


@dataclass(frozen=True, slots=True)
class Use:
    """One shape that names an entry of a vocabulary."""

    site: Site

    kind: Literal["variable", "member", "component"]
    """Whose use this is: a variable's declaration, a structure member's, or a **component's own**
    - the last being a raster named at ``component.raster`` as the default for everything that
    component produces, which sits inside no definition. A constant is never named that way and a
    section is named only by a definition, so this third word arrives with rasters."""

    name: str
    """The variable's name, ``Sample_t.history`` for a structure member, or - for a component's
    own default raster, which names no variable - the component's own name again."""

    component: str | None
    """The component declaring the variable, or naming a raster as its own default; ``None`` for
    a member, whose structure may be declared in a types file no component owns, and which
    ``name`` locates instead."""


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


    Where a finding sits does not by itself say whose it is, and
    :data:`~ddd.finding_routes.ABOUT_THE_DECLARATION` is the one place that difference is written
    down. This asks it for the same reason :func:`ddd.finding_routes.route_of` does, and asking it
    in only one of the two is what the branch's final review caught: ``consumer-storage`` is filed
    at a definition's ``section`` key, so it matched every pointer test here, and a section whose
    name a consumer had wrongly stated showed ``1`` in the tab's Findings column and listed a
    finding in its panel that routed away from it. That column is what a reader scans for what
    needs attention; a count they can do nothing about is worse than no count.
    """
    if found.check in ABOUT_THE_DECLARATION:
        return False
    if found.location is None:
        return False
    entry = vocabulary.entries(built).get(name)
    places: list[Site] = []
    if entry is not None:
        places.append(entry)
    places.extend(vocabulary.used(built).get(name, ()))
    wanted = file.resolve()
    return any(_at(place, wanted, found.location.pointer) for place in places)


def _at(place: Site, path: Path, pointer: str) -> bool:
    """Whether ``pointer`` in ``path`` is that place, or somewhere inside it."""
    if place.path.resolve() != path:
        return False
    if pointer == place.pointer:
        return True
    return pointer.startswith((f"{place.pointer}.", f"{place.pointer}["))


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


_PLACEMENT_SHAPE: Final = re.compile(r"^(component\.interface\[\d+\]\.definition)\.section$")
"""The one shape that names a section - a definition's own ``section`` key - and the definition it
belongs to, whose ``name`` names the variable placed there.

One where a constant has three, and no second home: a section is a project wide vocabulary with no
place inside a component the way a constant has ``component.constants``, which
:data:`ddd.lsp.navigation._SECTION_KEY` is the authority for and
``test_the_placement_pattern_matches_what_the_index_calls_a_placement`` pins this pattern to.
"""


def _section_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Use, ...]:
    """:data:`SECTIONS`'s :attr:`~Vocabulary.uses`: every definition placing its data in the
    section, in the order the index recorded them.

    The use is the *variable's*, not the section's own: a section is named by a definition, so
    what a reader wants beside the row is which variable sits there and in which component -
    which is why :attr:`Use.kind` needs no widening for this vocabulary. Only a raster breaks
    that, a component naming one directly for everything it produces.

    Drift is handled as :func:`_constant_uses` handles it, and for the same reason: the index
    recorded where the analysis read the definition, the file may have changed since, and a panel
    naming a variable that is no longer there is worse than one row short. A definition with no
    ``name`` left at that pointer names nothing, and one whose name belongs to no declaration the
    index holds has moved - the next revision lists it where it went.
    """
    found: list[Use] = []
    for site in built.section_uses.get(name, ()):
        document = read(site.path, cache)
        shape = _PLACEMENT_SHAPE.match(site.pointer)
        # As in `_constant_uses`: `_SECTION_KEY` is the shape navigation.index() writes here, and
        # the test named above pins this pattern to it. A pointer this fails to match would mean
        # the two have drifted apart, and undercounting a section's uses silently is worse than
        # failing loudly the moment they do.
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


_RASTER_DEFAULT_SHAPE: Final = re.compile(r"^component\.raster$")
"""A component's own default raster - the one use written outside any definition at all, and the
first of the two shapes a raster may be named at."""

_RASTER_DEFINITION_SHAPE: Final = re.compile(r"^(component\.interface\[\d+\]\.definition)\.raster$")
"""A definition's own raster, and the definition it belongs to, whose ``name`` names the variable
sampled on it - the second of the two shapes, read exactly as ``_PLACEMENT_SHAPE`` reads a
section's one."""


def _raster_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Use, ...]:
    """Every component naming this raster as its own default, and every definition naming it
    directly, in the order the index recorded them: per component, its own default ahead of its
    own definitions', as :func:`ddd.lsp.navigation.index` writes it - two components interleave
    rather than group by kind, one's default and definitions together before the next one's. This
    is what a raster's own :attr:`Vocabulary.uses` will read through, once a rasters part binds
    one.

    The one vocabulary :attr:`Use.kind` was widened for: a component's own default is a use
    inside no definition at all, so unlike :func:`_section_uses` this cannot say every use is the
    variable's. ``component.raster`` reads as the ``"component"`` kind, its own name doing double
    duty as both :attr:`Use.name` and :attr:`Use.component` - there being no variable between the
    component and the raster to name instead. Read through :func:`~ddd.variables.component_of`
    rather than a bare ``value_at``: a component that has dropped its own ``name`` since the
    analysis is still named, by its file, exactly as every other reader of a component's name
    already falls back to.

    A definition's own raster is read exactly as :func:`_section_uses` reads a placement, drift
    handled the same way and for the same reason: the index recorded where the analysis read the
    definition, the file may have changed since, and a panel naming a variable that is no longer
    there is worse than one row short.
    """
    found: list[Use] = []
    for site in built.raster_uses.get(name, ()):
        document = read(site.path, cache)
        if _RASTER_DEFAULT_SHAPE.match(site.pointer):
            component = component_of(document, site.path)
            found.append(Use(site, "component", component, component))
            continue
        shape = _RASTER_DEFINITION_SHAPE.match(site.pointer)
        # As in `_constant_uses` and `_section_uses`: `_RASTER_KEY` is the shape
        # navigation.index() writes here, and
        # `test_the_two_raster_patterns_match_what_the_index_calls_a_raster_key` pins these two
        # patterns to it. A pointer neither matches would mean this module and `_RASTER_KEY` have
        # drifted apart, not that the file holds anything unexpected.
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
``ConstantDeclaration.description`` and ``SectionDeclaration.description`` are both a plain
``str``, so this need only refuse what a string can never be: a number, a bool, ``null``, an
array, an object. One adapter for both, because the two fields are the same field twice; a
vocabulary whose description were constrained would bring its own."""


def _constant_name_judge(
    built: Index, _entry: str | None, to: str, _cache: dict[Path, Document]
) -> str | None:
    """:data:`CONSTANTS`'s :attr:`~Vocabulary.taken` entry for its name: ``rename_problem``, called
    exactly as ``rename_entry`` and ``add_entry`` call it for a constant, so a constant's rename and
    its declaration refuse a name in the same words they always have. Its c identifier rule and
    ``occupied`` check fit a constant and neither of the other two: a section's name is a linker
    string and a raster's an a2l short name.

    The entry and the cache go unread, for the reason :attr:`~Vocabulary.taken` gives."""
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
    taken={"name": _constant_name_judge},
)

_ACCESS: Final[TypeAdapter[SectionAccess]] = TypeAdapter(SectionAccess)
"""The format's own judge of what a section's ``access`` may say: the two members of
:class:`~ddd.models.sections.SectionAccess` and nothing else. Whatever the panel's chooser offers,
the value reaches the plan through the api as text, so a third word is refused here."""


def _aligned(value: Any) -> dict[str, Any]:
    """One whole section entry built around the alignment being judged, for :data:`_ALIGNMENT`.

    The power-of-two rule is a ``@model_validator(mode="after")`` on
    :class:`~ddd.models.sections.SectionDeclaration`, not a constraint on the field, so no adapter
    over the field's annotation alone can reach it - and this interface never restates a rule, which
    is the one thing :attr:`Vocabulary.judge` promises. Validating the whole entry is what asks the
    model itself, and it answers in the loader's own words: ``alignment 3 is not a power of two``.

    The other two keys cannot affect the answer. They are the only ones the model has besides
    ``description``, which defaults, and ``extra="forbid"`` means there are no others; both are
    fixed here and both are valid - ``.ddd`` matches ``SECTION_NAME_PATTERN`` and ``read-write`` is
    a member of the enum - so neither can contribute a refusal of its own. Nor can either change
    what the alignment is judged by: the model's single cross-field rule reads ``alignment`` and
    nothing else. ``test_an_alignment_the_model_takes_is_planned`` is what pins that, since a
    placeholder the model refused would refuse every alignment and leave the refusal cases passing.

    A dict rather than a keyword call so that the model's own validation reports which key was
    refused, and taken as ``Any`` rather than ``int`` for the reason :data:`_ALIGNMENT` gives.
    """
    return {"section": ".ddd", "access": SectionAccess.READ_WRITE, "alignment": value}


_ALIGNMENT: Final[TypeAdapter[SectionDeclaration]] = TypeAdapter(
    Annotated[SectionDeclaration, BeforeValidator(_aligned)]
)
"""The format's own judge of what a section's ``alignment`` may hold: the model's own field, asked
through the model, so the interface and the loader cannot come to different answers.

A ``BeforeValidator`` wrapping the value into an entry rather than
``Annotated[int, AfterValidator(...)]`` over the same rule, because an adapter whose type is ``int``
**coerces**: ``4.0`` would arrive at the validator as ``4`` and be accepted, where the field's own
``strict=True`` refuses it and the loader refuses the file. Strictness belongs to the field, so the
field has to be the thing doing the validating."""


def _section_name_judge(
    built: Index, _entry: str | None, to: str, _cache: dict[Path, Document]
) -> str | None:
    """:data:`SECTIONS`'s :attr:`~Vocabulary.taken` entry for its name: ``rename_problem``'s own
    section arm, asked exactly as :func:`_constant_name_judge` asks for a constant's, so that the
    tab and the editor's F2 refuse a section's name in the same words. The rule lives there rather
    than here because :mod:`ddd.lsp.navigation` cannot import this module - :class:`Index` is its
    own - and writing it twice is the defect one entry point exists to avoid.

    The entry and the cache go unread, for the reason :attr:`~Vocabulary.taken` gives."""
    return rename_problem(built, to, SECTION)


SECTIONS: Final = Vocabulary(
    kind=SECTION,
    containers=("sections",),
    name_key="section",
    keys=("access", "alignment", "description"),
    strings=frozenset({"access", "description"}),
    entries=lambda built: built.sections,
    used=lambda built: built.section_uses,
    states=lambda texts: f"{texts['access']}, align {texts['alignment']}",
    uses=_section_uses,
    required=frozenset({"access", "alignment"}),
    filename="sections.ddd.json",
    judge={
        "access": Judgement(_ACCESS, "read-write or read-only, as the running software sees it"),
        "alignment": Judgement(
            _ALIGNMENT,
            "a power of two, written as a whole number a 64 bit address could satisfy",
        ),
        "description": Judgement(_DESCRIPTION, "a json string"),
    },
    taken={"section": _section_name_judge},
)


def _evented(value: Any) -> dict[str, Any]:
    """One whole raster entry built around the event being judged, for :data:`_EVENT`.

    Built as :func:`_aligned` is, and for the same reason in a different place: the strictness
    lives on the field rather than on its annotation. ``RasterDeclaration.event`` is
    ``Field(strict=True, ge=0, le=EVENT_MAX)``, so ``TypeAdapter(int)`` over the annotation alone
    would **coerce** - ``1e3`` is the float ``1000.0``, which the published schema accepts, the
    loader refuses, and a bare adapter would wave through as ``1000``. Strictness belongs to the
    field, so the field has to be the thing doing the validating.

    The other keys cannot affect the answer. ``raster`` is fixed to ``ddd``, which
    :data:`~ddd.models.common.RASTER_NAME_PATTERN` admits and
    :data:`~ddd.models.common.RASTER_NAME_LENGTH` leaves room for, so it can contribute no refusal
    of its own; ``cycle`` and ``description`` are left out and take the model's own defaults, and
    ``extra="forbid"`` means there are no others. Leaving ``cycle`` out is what keeps this about
    the event alone: :class:`~ddd.models.rasters.RasterDeclaration`'s single cross-field rule,
    ``_cycle_is_a_period_xcp_carries``, returns at its first line for a ``cycle`` of ``None``, so
    it can never surface a cycle's refusal here. ``test_an_event_the_model_takes_is_planned`` is
    what pins all of that, since a placeholder the model refused would refuse every event and
    leave the refusal cases passing.

    A dict rather than a keyword call so that the model's own validation reports which key was
    refused, and taken as ``Any`` rather than ``int`` for the reason :data:`_ALIGNMENT` gives.
    """
    return {"raster": "ddd", "event": value}


_EVENT: Final[TypeAdapter[RasterDeclaration]] = TypeAdapter(
    Annotated[RasterDeclaration, BeforeValidator(_evented)]
)
"""The format's own judge of what a raster's ``event`` may hold: the model's own field, asked
through the model, so the interface and the loader cannot come to different answers. A
``BeforeValidator`` wrapping the value into an entry rather than an adapter over the field's
annotation, for the reason :func:`_evented` gives."""


def _cycled(value: Any) -> dict[str, Any]:
    """One whole raster entry built around the cycle being judged, for :data:`_CYCLE`.

    The period rule is a ``@model_validator(mode="after")`` on
    :class:`~ddd.models.rasters.RasterDeclaration`, not a constraint on the field, exactly as a
    section's power-of-two rule is - so ``TypeAdapter(str | None)`` over the annotation alone would
    take ``"1234ms"`` and ``"potato"``, neither of which is a period the loader accepts. Written,
    the file stops loading and every tab empties, which is the failure
    :func:`ddd.shared_plans.set_entry`'s own docstring says it exists to prevent.

    The other two keys cannot affect the answer. ``raster`` is fixed to ``ddd`` as above, and
    ``event`` to ``0``, which ``ge=0`` admits and ``strict=True`` takes for a python ``int``, so
    neither can contribute a refusal of its own; ``description`` is left out and defaults, and
    ``extra="forbid"`` means there are no others. Nor can either change what the cycle is judged
    by: the model's single cross-field rule reads ``cycle`` and nothing else.
    ``test_a_cycle_the_model_takes_is_planned`` is what pins that, and it asks for ``null`` too -
    ``cycle`` is ``str | None``, and an event that is not cyclic is a real kind of raster rather
    than an omission.
    """
    return {"raster": "ddd", "event": 0, "cycle": value}


_CYCLE: Final[TypeAdapter[RasterDeclaration]] = TypeAdapter(
    Annotated[RasterDeclaration, BeforeValidator(_cycled)]
)
"""The format's own judge of what a raster's ``cycle`` may hold: the model's own field and the
model's own period rule, for the reason :func:`_cycled` gives."""


def _raster_states(texts: Mapping[str, str]) -> str:
    """``event 3, 10ms``, or ``event 3`` where the raster states no cycle.

    The first row cell composed from a key that may not be there, and the reason this is a named
    function where the other two vocabularies' are lambdas. Written as statements: a conditional
    expression registers no branch with coverage.py, and the arm for a raster with no cycle would
    then be one no gate could tell had run.

    Both keys are indexed rather than read with ``.get``: :func:`shown` fills every key of
    :attr:`Vocabulary.keys` for every entry, so ``texts["cycle"]`` is always there - ``""`` where
    the entry states none, and ``""`` too where it states an explicit ``null``, since ``cycle`` is
    one of :attr:`Vocabulary.strings` and :func:`string_of` answers ``""`` for a value that is not
    a string. A default would be one no call could reach.
    """
    cycle = texts["cycle"]
    if not cycle:
        return f"event {texts['event']}"
    return f"event {texts['event']}, {cycle}"


def _raster_name_judge(
    built: Index, _entry: str | None, to: str, _cache: dict[Path, Document]
) -> str | None:
    """:data:`RASTERS`'s :attr:`~Vocabulary.taken` entry for its name: ``rename_problem``'s own
    raster arm, asked exactly as :func:`_constant_name_judge` and :func:`_section_name_judge` ask
    for theirs, so that the tab and the editor's F2 refuse a name in the same words. The rule lives
    there rather than here for the reason :func:`_section_name_judge` gives.

    The entry and the cache go unread, for the reason :attr:`~Vocabulary.taken` gives."""
    return rename_problem(built, to, RASTER)


def _event_taken(
    built: Index, entry: str | None, wanted: str, cache: dict[Path, Document]
) -> str | None:
    """Why this event may not be claimed, or nothing if it may.

    The second judge of :data:`RASTERS`'s :attr:`~Vocabulary.taken`, and the reason that field is a
    map where part 13 had a single name judge: a raster has two keys whose value is the project's
    alone. What the model will take is a different question from what another raster has already
    got, and only the second needs an :class:`Index` to answer.

    ``entry`` is the raster whose event is being set, and is exempt from itself: the panel asks for
    a plan on every keystroke, so a reader who has typed nothing new must not be refused. An
    ``add`` passes ``None``, there being no entry yet for one to be exempt from.

    Which rasters there are is asked of the index, for the reason
    :func:`ddd.shared_plans.remove_entry` gives about what is in use: reading text to answer a
    question about meaning is the mistake part 11 filed against ``variable_keys._storage_of``.
    What each of them *claims* cannot be asked of it - :attr:`ddd.lsp.navigation.Index.rasters`
    maps a name to a :class:`Site` and not to its event - so the event is read from the entry's
    own text through :func:`text_of`, which is why :attr:`Vocabulary.taken` hands a judge the
    cache.

    ``wanted`` is parsed with no guard of its own. ``ddd.shared_plans._untaken`` asks this only
    after ``_judged`` has taken the same text through :data:`_EVENT`, so it is already json the
    model accepted; a guard here would be a line no test could reach, and text the model would
    refuse must leave through the model's refusal rather than this one - two refusals for one
    keystroke is one too many, and the model's is the one that says what a legal event looks like.

    What another raster states is guarded, because that one is reachable: the index recorded where
    the analysis read a declaration and the file may have dropped its ``event`` since, the drift
    :func:`_raster_uses` and :func:`ddd.lsp.navigation.rename_edits` both handle. Unguarded,
    ``json.loads("")`` would raise out of a plan the panel asked for; a declaration that states no
    event claims none, and the next revision says what it claims instead.
    """
    event = json.loads(wanted)
    for other in built.rasters:
        if other == entry:
            continue
        claimed = text_of(RASTERS, built, other, "event", cache)
        if not claimed:
            continue
        if json.loads(claimed) == event:
            return f"event {event} is already claimed by raster '{other}'"
    return None


RASTERS: Final = Vocabulary(
    kind=RASTER,
    containers=("rasters",),
    name_key="raster",
    keys=("event", "cycle", "description"),
    strings=frozenset({"cycle", "description"}),
    entries=lambda built: built.rasters,
    used=lambda built: built.raster_uses,
    states=_raster_states,
    uses=_raster_uses,
    required=frozenset({"event"}),
    filename="rasters.ddd.json",
    judge={
        "event": Judgement(_EVENT, "a whole number the target offers as a channel"),
        "cycle": Judgement(_CYCLE, "a json string, or nothing"),
        "description": Judgement(_DESCRIPTION, "a json string"),
    },
    taken={"raster": _raster_name_judge, "event": _event_taken},
)

HELD: Final = (CONSTANTS, SECTIONS, RASTERS)
"""Every vocabulary the Shared files tab holds, and the order :func:`shared_rows` walks them in -
which the sort by kind then name makes invisible to a reader. The third of them added a word here
and nothing else, which is what the descriptor was for."""
