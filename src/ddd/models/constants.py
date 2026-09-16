"""Contract for the constant vocabulary file.

A ``constants`` file declares named numbers, so that a number the project depends on lives
in one place and is shared by name.  Every declared constant reaches the outputs - the c
templates are handed the vocabulary to emit, the a2l writes one ``SYSTEM_CONSTANT`` each -
so a gain, an offset or a base address belongs here as much as a count does.

A size is the case the vocabulary was built for.  An array dimension is commonly a named
constant of the project, stated once and used by every loop that walks the array; a bare
number in a description restates that constant and drifts from it silently.  With the
vocabulary declared, a shape - an entry of ``dimensions``, or the ``size`` of an axis -
names the constant where it would state the number, and the generated code carries the name
rather than a copy of its value.  Only that use constrains the value, and it constrains it
where the shape is written: a constant a shape names has to be a whole number of at least 1,
the same rule a literal dimension obeys, and a constant nothing dimensions is any number.

The value is a literal only: an expression would put a parser and an evaluation order into a
description format, and a constant cannot name another constant, for the reason a scalar
type cannot be declared in terms of a second one - what cannot be written cannot cycle.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from ddd.models.common import FileRoot, Identifier


def _refuse_whole_number(value: Any) -> Any:
    """Keep a whole number out of the fractional arm of :data:`ConstantValue`.

    Pydantic widens an ``int`` into a strict ``float``, so without this the whole numbers the
    first arm refuses - the ones past what 64 bits hold - would land in the second instead
    and come back rounded.  The file would then mean a number nobody wrote, which is the one
    outcome a description format cannot have.
    """
    if isinstance(value, int):
        raise ValueError("a whole number is not a fractional value")
    return value


ConstantValue = (
    Annotated[int, Field(strict=True, ge=-(2**63), le=2**64 - 1)]
    | Annotated[
        float, BeforeValidator(_refuse_whole_number), Field(strict=True, allow_inf_nan=False)
    ]
)
"""A number written as a literal: a whole number a 64 bit target can hold, of either sign,
or a finite fractional one.

Strict on both arms, and neither silently becomes the other, so the spelling decides which
it is: a description that says ``2.0`` means a fractional constant, and one that says ``2``
means a whole one.  The bound on the whole arm spans signed and unsigned 64 bit alike,
because either is a literal generated code can hold and nothing DDD emits counts further.
"""


class ConstantDeclaration(BaseModel):
    """One named number, declared once and named wherever the project needs it."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """The name a shape writes where it would state a number: ``PRESSURE_CELLS``.

    An identifier, because the name reaches the generated code as an identifier of its own;
    the templates receive every declared constant to emit.
    """

    value: ConstantValue
    """The value, a number: a whole number of either sign, or one written with a point.

    A literal only: an expression would put a parser and an evaluation order into a
    description format, and a constant cannot name another constant, so what cannot be
    written cannot cycle.  How it is written settles what it is - ``2`` is a whole number,
    and anything carrying a point or an exponent is fractional, so ``2.0`` and ``1e3`` both
    are - because that is what the author is picking: the type, not the format.  The
    outputs carry the number in its shortest spelling that reads back as the same number, a
    whole number without a point and any other with a point or an exponent, so ``2.50``
    reaches the generated code as ``2.5`` and ``1e3`` as ``1000.0``.
    A whole number is bounded by what a 64 bit target can express, signed or unsigned, and
    a fractional one must be finite: ``inf`` and ``nan`` name nothing a description can
    state, and would reach a template as those words.

    Nothing here requires the value to be a size.  A constant that a shape names has to be
    a whole number of at least 1, the same rule a dimension written as a literal obeys, but
    that is checked where the shape names it - the declaration is not the place, because a
    constant may be declared to be emitted and never dimension anything.
    """

    description: str = ""
    """What the constant stands for, e.g. ``cells of the pressure manifold``.

    This is where the meaning of a number is written down once, instead of being implied by
    every object that happens to use it.
    """


class ConstantsFile(FileRoot):
    """Root object of a ``*.ddd.json`` constant vocabulary description.

    ``constants`` is the top level key that makes this a constants file rather than a
    project, a component or a types file; DDD decides what a file is from that key alone.
    The file is listed in the ``includes`` of a project like any other description.
    """

    model_config = ConfigDict(title="DDD constant vocabulary")

    constants: Annotated[tuple[ConstantDeclaration, ...], Field(min_length=1)]
    """The constants this project names, in any order; an empty vocabulary is no file at
    all."""
