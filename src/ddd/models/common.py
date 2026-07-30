"""Primitive building blocks shared by all DDD contracts.

This module is deliberately free of any output format: a datatype knows how many bytes it
occupies and which values it can hold, not what a c compiler or a calibration tool calls it.
Those mappings belong to the backend that needs them (:mod:`ddd.backends.c.types`,
:mod:`ddd.backends.a2l.types`), and the names c reserves live in :mod:`ddd.models.reserved`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class FileRoot(BaseModel):
    """Base of the three hand-written file roots: project, component and naming.

    The one thing they share is the ``$schema`` key. Editors use it to bind a json file to
    its schema, and that binding is what turns the published contract into completion,
    hover documentation and as-you-type validation - so the key has to be *allowed*, even
    though ``extra="forbid"`` rightly rejects everything else it does not know. DDD itself
    ignores the value: which schema file a team points at, and where they keep it, is their
    editor setup, not project data.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    schema_reference: str | None = Field(default=None, alias="$schema")
    """Editor binding to a schema written by ``ddd schema -o``; not interpreted by DDD."""


C_IDENTIFIER_PATTERN: Final = r"^[A-Za-z_][A-Za-z0-9_]*$"

IDENTIFIER_MAX_LENGTH: Final = 128
"""Longest identifier DDD accepts.

ASAP2 1.6.1 limits an identifier to 128 characters, and a name DDD cannot put into the a2l
is of no use in a project that generates one.  C compilers are more generous, so this is the
tighter of the two rules.
"""

Identifier = Annotated[
    str,
    StringConstraints(pattern=C_IDENTIFIER_PATTERN, min_length=1, max_length=IDENTIFIER_MAX_LENGTH),
]
"""A string that is usable as a c identifier and as an a2l identifier."""

A2L_FORMAT_PATTERN: Final = r"^%\d*\.\d+$"

A2lFormat = Annotated[str, StringConstraints(pattern=A2L_FORMAT_PATTERN)]
"""An a2l ``FORMAT`` string: ``%`` then the total width, a dot, and the decimal places.

Constrained rather than passed through, because the value is written into a quoted a2l
literal: a quote or a backslash in it would unbalance the string and no calibration tool
would parse the file at all - a whole delivery lost to one typo in one description.
"""

Real = Annotated[float, Field(allow_inf_nan=False)]
"""A finite number.

Infinity and NaN are refused wherever a number is read. Neither survives the trip to an
output - there is no c literal and no a2l number for them - and NaN is worse than useless
on the way there, because every comparison against it is false: a NaN limit passes every
range check in silence instead of failing one.
"""

Number = int | Real
"""A finite number that keeps whole values exact.

``int`` first on purpose: the range of a 64 bit datatype does not survive a float, and a
limit rendered as 18446744073709551616 - one more than uint64 can hold - is a value the
calibration tool would refuse.
"""


FLOAT32_MAX: Final = 3.4028234663852886e38
FLOAT64_MAX: Final = 1.7976931348623157e308


@dataclass(frozen=True, slots=True)
class DatatypeInfo:
    """Format independent properties of a base datatype."""

    size: int
    is_float: bool
    is_signed: bool
    raw_min: float
    raw_max: float


class Datatype(StrEnum):
    """The base datatypes DDD can allocate storage for."""

    BOOLEAN = "boolean"
    """A truth value.

    Spelled ``boolean`` rather than ``bool`` because this module names datatypes without
    reference to any output format: ``bool`` is what c calls it, and the c backend is where
    that spelling belongs.
    """

    UINT8 = "uint8"
    INT8 = "int8"
    UINT16 = "uint16"
    INT16 = "int16"
    UINT32 = "uint32"
    INT32 = "int32"
    UINT64 = "uint64"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"

    @property
    def info(self) -> DatatypeInfo:
        return _DATATYPE_INFO[self]

    @property
    def size(self) -> int:
        """Size of one element in bytes."""
        return self.info.size

    @property
    def is_float(self) -> bool:
        return self.info.is_float

    @property
    def is_integer(self) -> bool:
        return not self.info.is_float and self is not Datatype.BOOLEAN

    @property
    def raw_min(self) -> float:
        """Smallest value representable in the raw (implementation) domain."""
        return self.info.raw_min

    @property
    def raw_max(self) -> float:
        """Largest value representable in the raw (implementation) domain."""
        return self.info.raw_max


_DATATYPE_INFO: Final[dict[Datatype, DatatypeInfo]] = {
    Datatype.BOOLEAN: DatatypeInfo(1, False, False, 0, 1),
    Datatype.UINT8: DatatypeInfo(1, False, False, 0, 255),
    Datatype.INT8: DatatypeInfo(1, False, True, -128, 127),
    Datatype.UINT16: DatatypeInfo(2, False, False, 0, 65535),
    Datatype.INT16: DatatypeInfo(2, False, True, -32768, 32767),
    Datatype.UINT32: DatatypeInfo(4, False, False, 0, 4294967295),
    Datatype.INT32: DatatypeInfo(4, False, True, -2147483648, 2147483647),
    Datatype.UINT64: DatatypeInfo(8, False, False, 0, 18446744073709551615),
    Datatype.INT64: DatatypeInfo(8, False, True, -9223372036854775808, 9223372036854775807),
    Datatype.FLOAT32: DatatypeInfo(4, True, True, -FLOAT32_MAX, FLOAT32_MAX),
    Datatype.FLOAT64: DatatypeInfo(8, True, True, -FLOAT64_MAX, FLOAT64_MAX),
}


def format_number(value: float | int) -> str:
    """Render a number in the shortest form that round-trips.

    Used wherever a number reaches a human or a text format, so that ``0.25`` does not
    turn into ``0.25000000000000001``.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if value == 0:  # also normalises -0.0
        return "0"
    if value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return repr(value)
