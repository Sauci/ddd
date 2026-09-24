"""One object's values, and what changing one of them takes.

Transport-neutral, like :mod:`ddd.type_plans` and :mod:`ddd.declaration_plans` beside it.
Nothing here writes a file: a change answers a plan of edit-engine operations, and
``POST /api/edit`` is what writes it.

Nothing here resolves a shape either. ``revision.dictionary`` already answers, per object, the
fully numeric shape - which for a curve or a map comes from the axes and is only known once the
whole project resolves - together with the producer's merged ``init``, the conversion with its
defaults filled in and the physical limits. Re-deriving any of that would give the project two
answers to what shape an object is, and the second would be wrong first for a dimension spelled
as the name of a constant.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from ddd.editing import Operation
from ddd.ir import DataDictionary
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.common import Datatype
from ddd.models.conversion import Conversion
from ddd.models.objects import InitValue

AXIS_REFERENCES: Final = ("axis", "x_axis", "y_axis")
"""The references that name an axis, in the order a grid lays them out.

Measured, not assumed: an axis's own ``references`` names its ``input`` measurement, which is a
reference and is not an axis - ``AxisA`` of examples/demo answers ``{"input": "ValueE"}``. A
grid laid against every reference would draw that measurement as the axis's own breakpoints.
"""


class ValueRefusalError(Exception):
    """A grid that cannot be shown or changed, and the code both clients refuse it with."""

    code: Literal["invalid", "not-found"]
    """``not-found``: the project declares no object of that name. ``invalid``: the grid cannot
    be drawn - a shape of more dimensions than rows of cells - or the change cannot be made: an
    element outside the shape, a value the datatype cannot hold, an object whose init is text,
    or no one declaration to write into."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class Axis:
    """One axis a grid is laid against."""

    position: str
    """Which of :data:`AXIS_REFERENCES` names it."""

    name: str
    unit: str
    breakpoints: tuple[float, ...]
    """Raw, as the axis's own producer writes them; the page reads them through
    :attr:`conversion`, which is the axis's and not the object's."""

    conversion: Conversion


@dataclass(frozen=True, slots=True)
class Grid:
    """One object's values, and everything needed to read them."""

    name: str
    kind: str
    datatype: str
    unit: str
    conversion: Conversion
    minimum: float
    """The resolved physical limits. Shown, never enforced: nothing in the analysis weighs an
    init against them, and refusing here would leave cells a person wrote by hand that this
    cannot edit."""

    maximum: float
    shape: tuple[int, ...]
    rows: tuple[tuple[float, ...], ...]
    """Always rows: a one dimensional object is one row, so one shape serves both."""

    stated: Literal["array", "scalar", "text", "none"]
    """What the producer writes: the values themselves, one value standing for every element,
    text - which is no grid - or nothing, which the startup code zeroes."""

    axes: tuple[Axis, ...]
    owner: str | None
    """The component the analysis reads the values from, and ``None`` where nothing produces
    this object at all - which is what tells a read-only grid nothing produces from one that
    more than one declaration does, where an owner is named and :attr:`file` is still ``None``."""

    file: str | None
    """The producing declaration's path, resolved and posix-separated; ``None`` where there is
    not exactly one producing declaration, which is a grid that can be read and not changed."""

    pointer: str | None
    """The producing declaration's own pointer - ``component.interface[N]`` - paired with
    :attr:`file` and ``None`` for the same reason. A finding about this object's ``init`` is
    filed at this pointer with ``.definition.init`` appended, which is how
    :mod:`ddd.gui.api` tells one object's own finding from another's in the same file."""


def grid_of(dictionary: DataDictionary, built: Index, name: str) -> Grid:
    """One object's grid, read from the resolved dictionary and the index.

    No document is read: every value here is already resolved, and where the change goes is
    the index's answer.
    """
    resolved = dictionary.by_name.get(name)
    if resolved is None:
        raise ValueRefusalError("not-found", f"the project declares no '{name}'")
    shape = tuple(resolved.shape)
    if len(shape) > 2:
        # `dimensions: [2, 3, 4]` is ordinary DDD - the loader takes it and no check reports
        # it - and a grid is rows of cells and nothing deeper, which :attr:`Grid.rows`,
        # :func:`_laid_out` and :func:`_element` all assume. Refused where the page can draw
        # the sentence, rather than drawn a dimension short.
        raise ValueRefusalError(
            "invalid", f"'{name}' has {len(shape)} dimensions, and a grid draws at most two"
        )
    stated, rows = _laid_out(resolved.init, shape)
    axes = tuple(
        Axis(
            position=position,
            name=named,
            unit=dictionary.by_name[named].unit or "",
            breakpoints=_breakpoints(dictionary.by_name[named].init),
            conversion=dictionary.by_name[named].conversion,
        )
        for position in AXIS_REFERENCES
        if (named := resolved.references.get(position)) is not None and named in dictionary.by_name
    )
    sites = built.producers.get(name) or []
    # Exactly one, and a statement rather than a ternary: coverage.py registers no branch at
    # all for a conditional expression, which is exactly how `file`'s own `else None` arm went
    # untested here before - an `if`/`else` leaves both arms visible to the 100 % gate.
    #
    # Measured: the analysis's own producer - which `rows` and `owner` come from - and
    # `Index.producers[0]` need not be the same declaration when two of them produce one name,
    # so a file answered here could be a file whose numbers were never on screen. Nothing
    # produces it, or more than one thing does, comes to the same grid: read it, do not write
    # it. The values and the owner stay, because they are how a reader finds the second one.
    if len(sites) == 1:
        # Resolved, the spelling `ddd.variables` compares by and `_variable` publishes.
        file: str | None = sites[0].path.resolve().as_posix()
        # `Site.pointer` for a producer is always `…interface[N].definition` - `index()` builds
        # every one of them with "definition" as the literal suffix - but a finding's own
        # pointer is the declaration's, with `.definition.init` (or another key) appended to
        # it; stripped here so the two spellings share one convention rather than two.
        pointer: str | None = sites[0].pointer.removesuffix(".definition")
    else:
        file = None
        pointer = None
    return Grid(
        name=name,
        kind=str(resolved.kind),
        datatype=str(resolved.datatype),
        unit=resolved.unit or "",
        conversion=resolved.conversion,
        minimum=resolved.limits.min,
        maximum=resolved.limits.max,
        shape=shape,
        rows=rows,
        stated=stated,
        axes=axes,
        owner=resolved.owner,
        file=file,
        pointer=pointer,
    )


def _breakpoints(init: InitValue | None) -> tuple[float, ...]:
    """An axis's own raw values, laid out flat: what its breakpoints are.

    An axis's ``init`` is, in practice, always the array of its points - but the type it
    shares with every other object also allows a scalar, text or none of them, none of
    which describes a breakpoint. Only the array arm does, and an axis is always one
    dimensional, so every element of it is a scalar rather than a further nested list -
    which the cast tells mypy, ``InitElement`` allowing nesting only a curve or a map states.

    ``list | tuple``, as :func:`_laid_out` reads the very same value: one guard answering an
    array's breakpoints and the other answering none for it would be two answers to what an
    array is, and this is the side that fails open - an empty header over a grid of no cells.
    """
    return tuple(cast(Iterable[float], init)) if isinstance(init, list | tuple) else ()


def _laid_out(
    init: InitValue | None, shape: tuple[int, ...]
) -> tuple[Literal["array", "scalar", "text", "none"], tuple[tuple[float, ...], ...]]:
    """What the producer states, and the rows it comes to.

    A shapeless object - a plain measurement or parameter, most of a project - has no cell
    for a value to sit in: ``stated`` still says whether the producer wrote one or nothing,
    but ``rows`` is always empty for it, never reaching :func:`_filled`, which assumes at
    least one dimension to index.
    """
    if isinstance(init, str):
        return "text", ()
    if not shape:
        return ("none" if init is None else "scalar"), ()
    if init is None:
        return "none", _filled(0, shape)
    if isinstance(init, list | tuple):
        # A grid is never more than one row of one more level - what Grid.rows itself
        # assumes; InitElement's deeper nesting is for a shape `grid_of` has already refused
        # before anything reaches here.
        if len(shape) == 1:
            return "array", (tuple(cast(Iterable[float], init)),)
        return "array", tuple(tuple(cast(Iterable[float], row)) for row in init)
    return "scalar", _filled(cast(float, init), shape)


def _filled(scalar: float, shape: tuple[int, ...]) -> tuple[tuple[float, ...], ...]:
    if len(shape) == 1:
        return (tuple([scalar] * shape[0]),)
    return tuple(tuple([scalar] * shape[1]) for _ in range(shape[0]))


@dataclass(frozen=True, slots=True)
class ValuePlan:
    """Everything one change of a value takes: one edit, on the producer's file."""

    edits: tuple[PlannedEdit, ...]


def set_cell(
    dictionary: DataDictionary,
    built: Index,
    name: str,
    at: str,
    raw: float,
    cache: dict[Path, Document],
) -> ValuePlan:
    """What setting one element takes.

    One ``set`` at the element's own pointer - ``…definition.init[2]`` for a curve,
    ``…init[1][3]`` for a map - so that changing one cell of a sixteen by sixteen map changes
    one line rather than reprinting two hundred and fifty six numbers. Where the array is not
    written yet, because the producer states one value for every element or states none at
    all, the whole ``init`` is written instead and the preview shows the object gaining it.

    A shapeless object - a plain measurement or a parameter, most of a project - has no cell
    for a value to sit in, the same as :func:`grid_of` finds when it lays one out; refused
    here before ``at`` is checked against the empty shape, rather than left to crash on one.
    """
    grid = grid_of(dictionary, built, name)
    if not grid.shape:
        raise ValueRefusalError("invalid", f"'{name}' has no cell for a value to sit in")
    if grid.stated == "text":
        raise ValueRefusalError("invalid", f"'{name}' is initialised with text, not with a grid")
    sites = built.producers.get(name) or []
    if not sites:
        raise ValueRefusalError("invalid", f"nothing produces '{name}', so it has no values to set")
    if len(sites) > 1:
        # The two causes of a read-only grid say different things, because only one of them is
        # true at a time: here two declarations do produce it, and the refusal is that neither
        # of them is *the* file - the analysis reads one of them for the values and the index
        # need not name the same one first.
        raise ValueRefusalError(
            "invalid",
            f"'{name}' is produced in more than one place, so there is no one file to set it in",
        )
    found = _element(at, grid.shape)
    _acceptable(raw, Datatype(grid.datatype), name)
    site = sites[0]
    written = read(site.path, cache).value_at(f"{site.pointer}.init")
    if isinstance(written, list):
        operation = Operation("set", f"{site.pointer}.init{at}", json.dumps(raw))
    else:
        rows = [list(row) for row in grid.rows]
        whole: list[float] | list[list[float]]
        if len(grid.shape) == 1:
            # A one dimensional object is one row, so its only index is the column.
            row, column = 0, found[0]
            whole = rows[0]
        else:
            row, column = found
            whole = rows
        rows[row][column] = raw
        operation = Operation("set", f"{site.pointer}.init", json.dumps(whole))
    return ValuePlan((PlannedEdit(site.path, (operation,)),))


def _element_label(row: int, column: int, shape: tuple[int, ...]) -> str:
    """``element 3``, ``element 2, 4`` - one-based, the spelling the undo strip already uses.

    One-based because the reader is looking at a breakpoint and not at an index, and the same
    words ``valueLabel`` puts in "Undo element 3 of CurveA".
    """
    if len(shape) == 1:
        return f"element {column + 1}"
    return f"element {row + 1}, {column + 1}"


def set_values(
    dictionary: DataDictionary,
    built: Index,
    name: str,
    rows: Sequence[Sequence[float]],
) -> ValuePlan:
    """What replacing every value of an object takes: one ``set`` of the whole ``init``.

    The whole table at once, rather than a cell at a time, is what makes a pasted calibration one
    edit and one entry in the undo stack. The shape is checked here as well as on the page,
    because the page is not the only thing that can call this.

    No document cache is taken, unlike :func:`set_cell`: that one reads whether the file already
    holds an array, to decide between setting one element and setting the whole ``init``, and
    this one always writes the whole ``init`` - so there is nothing for it to read.
    """
    grid = grid_of(dictionary, built, name)
    if grid.stated == "text":
        raise ValueRefusalError("invalid", f"'{name}' is initialised with text, not with a grid")
    if not grid.shape:
        raise ValueRefusalError("invalid", f"'{name}' has no cell for a value to sit in")
    sites = built.producers.get(name) or []
    if len(sites) != 1:
        raise ValueRefusalError("invalid", _no_single_producer(name, sites))
    wanted = (1, grid.shape[0]) if len(grid.shape) == 1 else (grid.shape[0], grid.shape[1])
    given = (len(rows), len(rows[0]) if rows else 0)
    # Ragged first, and in a sentence of its own: measured against `wanted` alone, a block of
    # four rows of six with a short row in the middle reads "takes 4 rows of 6, and this is 4
    # rows of 6" - the same shape printed twice, since `given`'s width is the first row's. What
    # is wrong with such a block is not its shape but that it has none.
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueRefusalError(
            "invalid",
            f"'{name}' takes {_table(wanted)} values, and this block's rows are not all the "
            "same length",
        )
    if given != wanted:
        raise ValueRefusalError(
            "invalid",
            f"'{name}' takes {_table(wanted)} values, and this is {_table(given)}",
        )
    datatype = Datatype(grid.datatype)
    offenders = []
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            try:
                _acceptable(value, datatype, name)
            except ValueRefusalError as refused:
                offenders.append((_element_label(r, c, grid.shape), refused.message))
    if offenders:
        raise ValueRefusalError("invalid", _all_of_them(offenders, name))
    site = sites[0]
    whole: list[float] | list[list[float]] = (
        list(rows[0]) if len(grid.shape) == 1 else [list(row) for row in rows]
    )
    operation = Operation("set", f"{site.pointer}.init", json.dumps(whole))
    return ValuePlan((PlannedEdit(site.path, (operation,)),))


def _table(shape: tuple[int, int]) -> str:
    """``1 row of 6``, ``4 rows of 6`` - how a block is counted, in both languages.

    The word "values" is left to whichever sentence wants it, so that this reads in the refusal
    and in the page's hint alike; `table` in ``objectValues.ts`` spells it the same way.
    """
    rows, columns = shape
    return f"{rows} row{'' if rows == 1 else 's'} of {columns}"


def _no_single_producer(name: str, sites: Sequence[object]) -> str:
    """Why a read-only grid cannot take a table, in the words part 8 refuses a cell with.

    Both sentences are ``set_cell``'s own, word for word, and the page's ``readOnlyNote``
    spells the same two: one condition said in three places wants one wording, and the
    multi-producer one here was the only one of the three saying it differently.
    """
    if not sites:
        return f"nothing produces '{name}', so it has no values to set"
    return f"'{name}' is produced in more than one place, so there is no one file to set it in"


def _all_of_them(offenders: Sequence[tuple[str, str]], name: str) -> str:
    """Every element that failed, up to five, with its own reason, then how many more.

    ``_acceptable``'s own message is quoted whole rather than reshaped into this sentence:
    reshaping only ever matched one phrasing, "... does not fit into ...", and broke - or for
    ``rounds_to_zero``, inverted - every other refusal ``_acceptable`` raises.

    Quoted once per offender, not once for the block: a table can be wrong in several ways at
    once - a physical column pasted into a grid left in raw gives both out-of-range counts and
    fractional ones - and one reason lent to every element named is false of most of them.
    Repeating the same sentence for elements that do fail the same way is the price of that,
    and the cheaper of the two mistakes: a reader sent to a cell to fix something that cell
    does not have is sent twice.

    Semicolons separate the clauses because a two-dimensional label carries a comma of its own
    ("element 1, 2"), and the one conjunction in the sentence is the last clause's "and N
    more", so the two never compete to be read as the same list's.
    """
    if len(offenders) == 1:
        label, message = offenders[0]
        return f"{label} of '{name}' is refused: {message}"
    clauses = [f"{label} because {message}" for label, message in offenders[:5]]
    if len(offenders) > 5:
        clauses.append(f"and {len(offenders) - 5} more")
    return f"{len(offenders)} elements of '{name}' are refused: {'; '.join(clauses)}"


def _element(at: str, shape: tuple[int, ...]) -> tuple[int, ...]:
    """The indices ``at`` names - ``[2]``, or ``[1][3]`` - checked against the shape."""
    parts = [piece for piece in at.replace("]", "").split("[") if piece != ""]
    if len(parts) != len(shape) or not all(piece.isdecimal() for piece in parts):
        raise ValueRefusalError("invalid", f"'{at}' is not an element of this object")
    found = tuple(int(piece) for piece in parts)
    if any(index >= size for index, size in zip(found, shape, strict=True)):
        raise ValueRefusalError("invalid", f"'{at}' is past the end of this object")
    return found


def _acceptable(raw: float, datatype: Datatype, name: str) -> None:
    """What an init value is refused for, in the words the check refuses it with.

    Read from :class:`~ddd.models.common.Datatype`'s own properties, which is where
    ``ddd.analysis``'s own init check reads them: the rule a value is written by and the rule
    it is read back by cannot then drift apart. The object's limits are deliberately not
    weighed - nothing in the analysis weighs an init against them, and a grid stricter than
    ``ddd check`` would leave cells a person wrote by hand that it could not edit.
    """
    if datatype is Datatype.BOOLEAN:
        if not isinstance(raw, bool) and raw not in (0, 1):
            raise ValueRefusalError("invalid", f"{raw!r} is not a valid bool")
        return
    if datatype.is_integer and isinstance(raw, float):
        raise ValueRefusalError(
            "invalid",
            f"{raw!r} is written as a fractional number, but '{name}' has the integer "
            f"datatype {datatype.value}",
        )
    info = datatype.info
    if not info.raw_min <= raw <= info.raw_max:
        raise ValueRefusalError(
            "invalid",
            f"{raw} does not fit into {datatype.value} ({info.raw_min} .. {info.raw_max})",
        )
    if datatype.rounds_to_zero(raw):
        raise ValueRefusalError("invalid", f"{raw} rounds to zero in {datatype.value}")
