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

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal, cast

from ddd.ir import DataDictionary
from ddd.lsp.navigation import Index
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
    """``not-found``: the project declares no object of that name. ``invalid``: the change
    cannot be made - an element outside the shape, a value the datatype cannot hold, an object
    whose init is text."""

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
    file: str | None
    """The producing declaration's path, posix-separated; ``None`` where nothing produces it,
    which is a grid that can be read and not changed."""


def grid_of(dictionary: DataDictionary, built: Index, name: str) -> Grid:
    """One object's grid, read from the resolved dictionary and the index.

    No document is read: every value here is already resolved, and where the change goes is
    the index's answer.
    """
    resolved = dictionary.by_name.get(name)
    if resolved is None:
        raise ValueRefusalError("not-found", f"the project declares no '{name}'")
    shape = tuple(resolved.shape)
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
        file=sites[0].path.as_posix() if sites else None,
    )


def _breakpoints(init: InitValue | None) -> tuple[float, ...]:
    """An axis's own raw values, laid out flat: what its breakpoints are.

    An axis's ``init`` is, in practice, always the array of its points - but the type it
    shares with every other object also allows a scalar, text or none of them, none of
    which describes a breakpoint. Only the array arm does, and an axis is always one
    dimensional, so every element of it is a scalar rather than a further nested list -
    which the cast tells mypy, ``InitElement`` allowing nesting only a curve or a map states.
    """
    return tuple(cast(Iterable[float], init)) if isinstance(init, tuple) else ()


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
        # assumes; InitElement's deeper nesting is for a shape this module does not draw.
        if len(shape) == 1:
            return "array", (tuple(cast(Iterable[float], init)),)
        return "array", tuple(tuple(cast(Iterable[float], row)) for row in init)
    return "scalar", _filled(cast(float, init), shape)


def _filled(scalar: float, shape: tuple[int, ...]) -> tuple[tuple[float, ...], ...]:
    if len(shape) == 1:
        return (tuple([scalar] * shape[0]),)
    return tuple(tuple([scalar] * shape[1]) for _ in range(shape[0]))
