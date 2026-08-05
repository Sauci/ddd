"""Contract for the unit vocabulary file.

A ``units`` file declares the units a project spells, so that one quantity cannot drift into
two spellings.  ``unit`` is free text everywhere it is written - DDD cannot know that ``Nm``
and ``newton_meter`` mean the same thing - and without a vocabulary the drift is invisible:
each object agrees with itself, and the calibration tool ends up showing two units for one
quantity.

Declaring the vocabulary is opt-in.  A project without a units file keeps its units free;
one with a units file has every stated unit checked against it (``unknown-unit``), with the
nearest declared spelling suggested.  The empty unit - a dimensionless value - is always
allowed, because it is the absence of an answer rather than a spelling of one.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from ddd.models.common import FileRoot


class UnitDeclaration(BaseModel):
    """One unit of the vocabulary, with what it stands for."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    unit: Annotated[str, StringConstraints(min_length=1)]
    """The spelling, exactly as every description file writes it: ``Nm``, ``rpm``, ``degC``.

    Case counts - ``mV`` and ``MV`` are different units - and the empty string is not an
    entry, because a dimensionless value states no unit at all.
    """

    description: str = ""
    """What the unit stands for, e.g. ``torque, newton metre``.

    This is where the vocabulary of a project is written down once, instead of being implied
    by every object that happens to use it.
    """


def _string_shorthand(value: Any) -> Any:
    """Allow a bare string where an entry object is expected.

    ``"units": ["Nm", "rpm"]`` is the whole file for a project that only wants the
    spellings pinned; the object form is there for whoever wants the meaning written down.
    """
    if isinstance(value, str):
        return {"unit": value}
    return value


Unit = Annotated[UnitDeclaration, BeforeValidator(_string_shorthand)]


class UnitsFile(FileRoot):
    """Root object of a ``*.ddd.json`` unit vocabulary description.

    ``units`` is the top level key that makes this a units file rather than a project, a
    component or a types file; DDD decides what a file is from that key alone.  The file is
    listed in the ``includes`` of a project like any other description.
    """

    model_config = ConfigDict(title="DDD unit vocabulary")

    units: Annotated[tuple[Unit, ...], Field(min_length=1)]
    """The units this project spells, in any order; an empty vocabulary is no file at all."""
