"""Contract for the constant vocabulary file.

A ``constants`` file declares named integer constants, so that a size lives in one place and
is shared by name.  An array dimension is commonly a named constant of the project, stated
once and used by every loop that walks the array; a bare number in a description restates
that constant and drifts from it silently.  With the vocabulary declared, a shape - an entry
of ``dimensions``, or the ``size`` of an axis - names the constant where it would state the
number, and the generated code carries the name rather than a copy of its value.

The value is a literal only: an expression would put a parser and an evaluation order into a
description format, and a constant cannot name another constant, for the reason a scalar
type cannot be declared in terms of a second one - what cannot be written cannot cycle.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ddd.models.common import FileRoot, Identifier


class ConstantDeclaration(BaseModel):
    """One named integer constant, declared once and named wherever a shape needs it."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """The name a shape writes where it would state a number: ``PRESSURE_CELLS``.

    An identifier, because the name reaches the generated code as an identifier of its own;
    the templates receive every declared constant to emit.
    """

    value: Annotated[int, Field(strict=True, ge=1)]
    """The value, an integer of at least 1, written as a number.

    A literal only: an expression would put a parser and an evaluation order into a
    description format, and a constant cannot name another constant, so what cannot be
    written cannot cycle.  At least 1 because the value is an array dimension, and an array
    of no elements is no array.
    """

    description: str = ""
    """What the constant counts, e.g. ``cells of the pressure manifold``.

    This is where the meaning of a size is written down once, instead of being implied by
    every object that happens to be dimensioned by it.
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
