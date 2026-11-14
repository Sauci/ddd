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
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from ddd.editing import Operation
from ddd.ir import DataDictionary
from ddd.lsp.navigation import Index, Site, changed_since, drift
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.common import Datatype
from ddd.models.conversion import Conversion
from ddd.models.objects import InitElement, InitValue, check_shape

_ELEMENT: Final = re.compile(r"(?:\[[0-9]+\])+")
"""An element's indices as the pointer writes them: each in brackets, ``[2]`` or ``[1][3]``."""

_INDEX: Final = re.compile(r"\[([0-9]+)\]")

EXACT: Final = 2**53
"""Where a double, the number the page holds, stops holding every whole number.

``2**53 + 1`` reaches the page as ``2**53``, a 64 bit mask loses its low bits, and ``2**64 - 1``,
the most a uint64 holds, arrives as ``2**64``, which none holds. Typed or pasted into an integer
cell, a number past it either side is refused by the page in any spelling, and the page draws no
grid holding one, nor one holding a value at it in a 64 bit integer (:attr:`Grid.unshown`); a
number the page sends at or past it may be another it rounded, which :func:`_acceptable`
refuses a 64 bit integer. Carrying every cell across as exact text instead was weighed and not
taken: from 2^53 on, a 64 bit value is edited in the file."""

WIDE: Final = frozenset({Datatype.UINT64, Datatype.SINT64})
"""The integers whose range runs past :data:`EXACT`: the ones a number the page sends at or past
it may be another the page rounded - narrower ones hold no number that large at all."""

AXIS_REFERENCES: Final = ("axis", "x_axis", "y_axis")
"""The references that name an axis, in the order a grid lays them out.

Measured, not assumed: an axis's own ``references`` names its ``input`` measurement, which is a
reference and is not an axis - ``AxisA`` of examples/demo answers ``{"input": "ValueE"}``. A
grid laid against every reference would draw that measurement as the axis's own breakpoints.
"""


class ValueRefusalError(Exception):
    """A grid that cannot be shown or changed, and the code both clients refuse it with."""

    code: Literal["invalid", "not-found", "stale"]
    """``not-found``: the project declares no object of that name. ``invalid``: the grid cannot
    be drawn - a shape of more dimensions than rows of cells, an init with a list where a number
    belongs or a number where a row belongs - or the change cannot be made: an element outside
    the shape, a value the datatype cannot hold, an object whose init is text, or no one
    declaration to write into. ``stale``: the producing declaration's file no longer holds it
    where the index found it, having changed since the analysis read it."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found", "stale"], message: str) -> None:
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
    minimum_text: str | None
    """:attr:`minimum` in its own digits where the double it reaches the page as would show
    another number (:func:`_limit_text`), and ``None`` where the double shows it as it is."""

    maximum_text: str | None
    """:attr:`maximum` the same way: the default maximum of a uint64, ``18446744073709551615``,
    reaches the page as 2^64 and printed as ``18446744073709552000``, which no uint64 holds."""

    shape: tuple[int, ...]
    rows: tuple[tuple[float, ...], ...]
    """Always rows: a one dimensional object is one row, so one shape serves both. A scalar - a
    number or nothing written for an object of no shape - is one row of one cell, the value its
    own ``init`` states, or the zero the startup code makes of none. Only text, and a list written
    for an object of no shape, leave it empty: neither has a value to show."""

    stated: Literal["array", "scalar", "text", "none"]
    """What the producer writes: the values themselves, one value standing for every element,
    text - which is no grid - or nothing, which the startup code zeroes."""

    axes: tuple[Axis, ...]
    unshown: str | None
    """The object whose numbers this grid cannot draw as they are, or ``None``: this one where its
    rows hold such a number, else the first of :attr:`axes` whose breakpoints hold one. A whole
    number past :data:`EXACT` reaches the page as the double nearest it, and one at it in a 64 bit
    integer is a value its cell cannot be set back to, so drawn, either would be a number nobody
    can keep: the page draws no grid of them and says why. A float in the file is a double
    already and is never one."""

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
    _fits(name, resolved.init, shape)
    for position in AXIS_REFERENCES:
        axis = dictionary.by_name.get(resolved.references.get(position) or "")
        if axis is not None:
            _fits(axis.name, axis.init, tuple(axis.shape))
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
        minimum_text=_limit_text(resolved.limits.min),
        maximum_text=_limit_text(resolved.limits.max),
        shape=shape,
        rows=rows,
        stated=stated,
        axes=axes,
        unshown=_unshown(name, resolved.datatype, rows, axes, dictionary),
        owner=resolved.owner,
        file=file,
        pointer=pointer,
    )


def _unshown(
    name: str,
    datatype: Datatype,
    rows: tuple[tuple[float, ...], ...],
    axes: tuple[Axis, ...],
    dictionary: DataDictionary,
) -> str | None:
    """:attr:`Grid.unshown`: the first of the object and its axes whose numbers the grid draws -
    its rows, their breakpoints - hold one it cannot draw (:func:`_unshowable`), each weighed by
    its own datatype."""
    drawn = [(name, datatype, [value for row in rows for value in row])]
    drawn += [
        (axis.name, dictionary.by_name[axis.name].datatype, list(axis.breakpoints)) for axis in axes
    ]
    for named, stored, values in drawn:
        if any(_unshowable(value, stored) for value in values):
            return named
    return None


def _limit_text(limit: float) -> str | None:
    """A limit in its own digits where the page could not print it from its double, a whole
    number past :data:`EXACT`, else ``None``. A float is a double already, and a whole number up
    to 2^53 prints as itself; past it the double is another number, or prints as one -
    ``2**63`` as ``9223372036854776000``."""
    if isinstance(limit, int) and abs(limit) > EXACT:
        return str(limit)
    return None


def _unshowable(value: float, datatype: Datatype) -> bool:
    """Whether the page cannot draw ``value`` as the number it is and have its cell set back to it:
    a whole number past :data:`EXACT`, which reaches the page as the double nearest it, or one at
    it in a 64 bit integer, which :func:`_acceptable` refuses a value at it. A float is a double
    already, and is never one."""
    if not isinstance(value, int):
        return False
    if datatype in WIDE:
        return abs(value) >= EXACT
    return abs(value) > EXACT


def limits_refusal(raw: str, datatypes: Iterable[object]) -> str | None:
    """The sentence ``limits`` stated as ``raw`` are refused with where they would give a 64 bit
    integer among ``datatypes`` a bound at or past :data:`EXACT` - which the page may have rounded,
    as it may a value :func:`_acceptable` refuses - or ``None``.

    The route refuses what the page sends; a range written in the file holds its bounds exactly,
    and the panel shows them as written. ``raw`` is json text the route's query has read already,
    and ``datatypes`` are the declarations' own, as their files state them: what is no datatype
    is no 64 bit integer either.
    """
    wide = next((d for d in datatypes if isinstance(d, str) and d in WIDE), None)
    limits = json.loads(raw)
    if wide is None or not isinstance(limits, dict):
        return None
    for bound in (limits.get("min"), limits.get("max")):
        if isinstance(bound, int) and abs(bound) >= EXACT:
            side = "-" if bound < 0 else ""
            return (
                f"{bound} is at or past {side}2^53, where the page cannot hold every whole number "
                f"exactly, so no limit of a {wide} is set to it here"
            )
    return None


def _fits(name: str, init: InitValue | None, shape: tuple[int, ...]) -> None:
    """Refuse an init a grid has no place for: a list where a number belongs, or a number where a
    row belongs - in the object's own rows, or in an axis's breakpoints.

    The loader keeps an init whatever its shape, and the analysis finds one that does not fit
    ``init-invalid`` and still resolves the project. Laid out regardless, an element of either
    kind reached :class:`Grid` where the other belongs, and the answer failed to be built: a
    ``500``. Nothing else is judged. A short or a ragged init is drawn as written: the finding
    says what is wrong with it, and setting cells or pasting a table - the plans this grid is
    read for - is how the page repairs it, which a refusal here would close; the variable
    panel's own settle of ``dimensions`` can leave an init short. A whole scalar fills every
    cell, text is no grid at all, and an object of no shape has no cell to lay any of its init
    out in."""
    if not isinstance(init, tuple):
        return
    if not shape:
        return
    problem = _misplaced(init, shape)
    if problem is not None:
        raise ValueRefusalError(
            "invalid", f"'{name}' is initialised with values that do not fit its shape: {problem}"
        )


def _misplaced(
    values: tuple[InitElement, ...], shape: tuple[int, ...], path: str = ""
) -> str | None:
    """The first element of ``values`` a grid of ``shape`` has no place for, or ``None``: in a
    shape of two dimensions a row belongs at each element, and in a row a number. Said in the
    words :func:`~ddd.models.objects.check_shape` - the analysis's own judge - says it of that
    element, which a kind out of place always gives one. How many elements there are is not
    judged, so a short row is still a row."""
    for index, element in enumerate(values):
        at = f"{path}[{index}]"
        if len(shape) > 1:
            if not isinstance(element, tuple):
                return check_shape(element, shape[1:], at)
            problem = _misplaced(element, shape[1:], at)
            if problem is not None:
                return problem
        elif isinstance(element, tuple):
            return check_shape(element, (), at)
    return None


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

    A shapeless object - a plain measurement or parameter, most of a project - is one cell: its
    value, or the zero the startup code makes of none, as one row of one, which never reaches
    :func:`_filled`, which assumes at least one dimension to index. A boolean's ``true`` is the
    count 1 it is stored as. A list written for an object of no shape, which ``init-invalid``
    reports, has no value to show, and no row is drawn for it.
    """
    if isinstance(init, str):
        return "text", ()
    if not shape:
        if init is None:
            return "none", ((0,),)
        if isinstance(init, tuple):
            return "scalar", ()
        return "scalar", ((int(init) if isinstance(init, bool) else init,),)
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
    all, the whole ``init`` is written instead and the preview shows the object gaining it. So
    is one the array of which is too short to hold the cell: the cell past its end is set, the
    elements before it that the array lacks being zeros, as the startup code makes them.

    A shapeless object - a plain measurement or a parameter, most of a project - is a grid of
    one cell, taken at no element (``at`` is empty): one ``set`` at the declaration's own
    ``init``, added where it states none, the preview showing the object gaining it. What has no
    value to show - text, and a list written for an object of no shape - has no cell for a value
    to sit in, refused here before ``at`` is checked against the empty shape.

    Refused while the producing declaration's file no longer holds it where the index found it
    (:func:`_in_place`): the cell set there would be another declaration's.
    """
    grid = grid_of(dictionary, built, name)
    if not grid.shape and not grid.rows:
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
    _in_place(site, name, cache)
    if not grid.shape:
        # The scalar's own pointer: its value is its ``init``, whether it is stated or not.
        operation = Operation("set", f"{site.pointer}.init", json.dumps(raw))
        return ValuePlan((PlannedEdit(site.path, (operation,)),))
    written = read(site.path, cache).value_at(f"{site.pointer}.init")
    if _has_cell(written, found):
        operation = Operation("set", f"{site.pointer}.init{at}", json.dumps(raw))
    else:
        # The array is not written yet, or is shorter than the shape: written whole, a short
        # one filled out with zeros - what the startup code makes of the elements it lacks.
        rows = _filled_out(grid.rows, grid.shape)
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


def set_cells(
    dictionary: DataDictionary,
    built: Index,
    name: str,
    cells: Sequence[tuple[str, float]],
    cache: dict[Path, Document],
) -> ValuePlan:
    """What setting several elements at once takes: the cells typed into the page's grid, each
    given as :func:`set_cell` takes one, its element and its raw count, in the grid's order.

    One edit, a ``set`` at each element's own pointer: what nobody typed stays as the file writes
    it - its spellings, ``3.0`` as ``3.0``, its layout, and a value its datatype cannot hold,
    which the analysis reports and this leaves alone - and a block too long for its table to be
    sent in one request takes its cells all the same. Where the array is not written yet, or is
    too short to hold one of the cells, the whole ``init`` is written instead, as :func:`set_cell`
    writes it for one cell, every cell given set over the values the file states. A cell given
    twice is set to the value given last, as the edit engine makes two sets of one pointer.

    Refused as :func:`set_cell` refuses one cell, and in the same order: no shape, text, no
    producer or more than one; then an element of another number of indices than the shape's,
    which names no element of the object at all (:func:`_indices`); then every cell past the end
    of the shape and every value its datatype cannot hold, each named with its own reason as
    :func:`set_values` names a table's (:func:`_all_of_them`); then a producing declaration no
    longer where the index found it (:func:`_in_place`).
    """
    grid = grid_of(dictionary, built, name)
    if not grid.shape:
        raise ValueRefusalError("invalid", f"'{name}' has no cell for a value to sit in")
    if grid.stated == "text":
        raise ValueRefusalError("invalid", f"'{name}' is initialised with text, not with a grid")
    sites = built.producers.get(name) or []
    if len(sites) != 1:
        raise ValueRefusalError("invalid", _no_single_producer(name, sites))
    found = [(_indices(at, grid.shape), at, raw) for at, raw in cells]
    datatype = Datatype(grid.datatype)
    offenders: list[tuple[str, str]] = []
    for element, at, raw in found:
        row, column = (0, element[0]) if len(grid.shape) == 1 else element
        label = _element_label(row, column, grid.shape)
        if _past(element, grid.shape):
            offenders.append((label, f"'{at}' is past the end of this object"))
            continue
        try:
            _acceptable(raw, datatype, name)
        except ValueRefusalError as refused:
            offenders.append((label, refused.message))
    if offenders:
        raise ValueRefusalError("invalid", _all_of_them(offenders, name))
    site = sites[0]
    _in_place(site, name, cache)
    written = read(site.path, cache).value_at(f"{site.pointer}.init")
    if all(_has_cell(written, element) for element, _, _ in found):
        operations = tuple(
            Operation(
                "set",
                f"{site.pointer}.init" + "".join(f"[{index}]" for index in element),
                json.dumps(raw),
            )
            for element, _, raw in found
        )
        return ValuePlan((PlannedEdit(site.path, operations),))
    rows = _filled_out(grid.rows, grid.shape)
    for element, _, raw in found:
        row, column = (0, element[0]) if len(grid.shape) == 1 else element
        rows[row][column] = raw
    whole: list[float] | list[list[float]] = rows[0] if len(grid.shape) == 1 else rows
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
    cache: dict[Path, Document],
) -> ValuePlan:
    """What replacing every value of an object takes: one ``set`` of the whole ``init``.

    The whole table at once, rather than a cell at a time, is what makes a pasted calibration one
    edit and one entry in the undo stack. The shape is checked here as well as on the page,
    because the page is not the only thing that can call this.

    It always writes the whole ``init``, so where :func:`set_cell` reads whether the file already
    holds an array, this reads one thing alone through ``cache``: whether the producing
    declaration is still where the index found it (:func:`_in_place`), the table pasted over
    another declaration's values otherwise.
    """
    grid = grid_of(dictionary, built, name)
    # Shape before text, the order :func:`set_cell` asks them in: an object that is both - a
    # scalar whose init is a string - would otherwise be told two different things depending on
    # which way a reader reached it.
    if not grid.shape:
        raise ValueRefusalError("invalid", f"'{name}' has no cell for a value to sit in")
    if grid.stated == "text":
        raise ValueRefusalError("invalid", f"'{name}' is initialised with text, not with a grid")
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
    _in_place(site, name, cache)
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


def _has_cell(written: object, found: tuple[int, ...]) -> bool:
    """Whether the ``init`` a producer writes - a list, or whatever else it is - holds the cell at
    ``found`` (its column alone, for one row): the one place an element is set where it stands."""
    if not isinstance(written, list):
        return False
    if len(found) == 1:
        return found[0] < len(written)
    row = written[found[0]] if found[0] < len(written) else None
    return isinstance(row, list) and found[1] < len(row)


def _filled_out(rows: tuple[tuple[float, ...], ...], shape: tuple[int, ...]) -> list[list[float]]:
    """``rows`` as lists, each row and the rows themselves taken to the shape with zeros; one
    longer than the shape is left as it is, for its own finding to say so."""
    filled = [list(row) for row in rows]
    width = shape[-1]
    for row in filled:
        row.extend([0] * (width - len(row)))
    while len(filled) < shape[0] and len(shape) > 1:
        filled.append([0] * width)
    return filled


def _indices(at: str, shape: tuple[int, ...]) -> tuple[int, ...]:
    """The indices ``at`` names - ``[2]``, or ``[1][3]`` - one for each of the shape's dimensions,
    whether or not they fall inside it. Each is in brackets, as the pointer the edit is made at
    writes them: ``1`` is no element, where read as one it planned a key of its own, ``init1``."""
    parts = _INDEX.findall(at) if _ELEMENT.fullmatch(at) else []
    if len(parts) != len(shape):
        raise ValueRefusalError("invalid", f"'{at}' is not an element of this object")
    return tuple(int(piece) for piece in parts)


def _past(found: tuple[int, ...], shape: tuple[int, ...]) -> bool:
    """Whether the element at ``found`` lies past the end of the shape in any dimension."""
    return any(index >= size for index, size in zip(found, shape, strict=True))


def _element(at: str, shape: tuple[int, ...]) -> tuple[int, ...]:
    """The indices ``at`` names (:func:`_indices`), checked against the shape."""
    found = _indices(at, shape)
    if _past(found, shape):
        raise ValueRefusalError("invalid", f"'{at}' is past the end of this object")
    return found


def _in_place(site: Site, name: str, cache: dict[Path, Document]) -> None:
    """Refuse a change of ``name``'s values while the declaration the index recorded producing
    it, at ``site``, no longer names it, its file read as it now stands: a declaration put in
    above it or taken out moves it, and an ``init`` set at the recorded place would be another's.
    The question :func:`ddd.variables.declarations_of` asks of a declaration before it reads one.
    ``stale``: the next analysis reads the file again, and the plan asked then is made where the
    declaration now is."""
    moved = drift((Site(site.path, f"{site.pointer}.name"),), name, cache)
    if moved:
        raise ValueRefusalError(
            "stale", changed_since(moved, f"the values of '{name}' cannot be set")
        )


def _acceptable(raw: float, datatype: Datatype, name: str) -> None:
    """What an init value is refused for, in the words the check refuses it with.

    Read from :class:`~ddd.models.common.Datatype`'s own properties, which is where
    ``ddd.analysis``'s own init check reads them: the rule a value is written by and the rule
    it is read back by cannot then drift apart. The object's limits are deliberately not
    weighed - nothing in the analysis weighs an init against them, and a grid stricter than
    ``ddd check`` would leave cells a person wrote by hand that it could not edit.

    One refusal is stricter than the check, and on purpose: a 64 bit integer is refused a whole
    number at or past :data:`EXACT`, which ``ddd check`` takes. The number the page sends there
    may be another it rounded - ``2**53`` stands for ``2**53 + 1`` too - and nothing here can tell
    which was meant. What it costs is the cells it leaves: a value past 2^53 is set in the
    file, and the grid holding one says it cannot show it. Asked after the range, so that a
    number the datatype cannot hold at all is still refused as not fitting.
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
    if datatype.is_integer and abs(raw) >= EXACT:
        # Only a 64 bit integer reaches this: a narrower one holds no number this large, and
        # is refused it above as not fitting.
        raise ValueRefusalError(
            "invalid",
            f"{raw} is at or past {'-' if raw < 0 else ''}2^53, where the page cannot hold every "
            f"whole number exactly, so no {datatype.value} is set to it here",
        )
    if datatype.rounds_to_zero(raw):
        raise ValueRefusalError("invalid", f"{raw} rounds to zero in {datatype.value}")
