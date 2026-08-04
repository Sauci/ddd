"""Primitive building blocks shared by all DDD contracts.

This module is deliberately free of any output format: a datatype knows how many bytes it
occupies and which values it can hold, not what a c compiler or a calibration tool calls it.
Those mappings belong to the backend that needs them (:mod:`ddd.backends.c.types`,
:mod:`ddd.backends.a2l.types`), and the names c reserves live in :mod:`ddd.models.reserved`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


class FileRoot(BaseModel):
    """Base of the hand-written file roots: project, component, naming and types.

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
    SINT8 = "sint8"
    UINT16 = "uint16"
    SINT16 = "sint16"
    UINT32 = "uint32"
    SINT32 = "sint32"
    UINT64 = "uint64"
    SINT64 = "sint64"
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

    @property
    def schema_description(self) -> str:
        """One line of hover documentation for the published json schema.

        Derived from the table below rather than written out under each member, because what
        an author needs to know about ``uint16`` is exactly what the table already states -
        how much storage it costs and which values fit in it. A docstring repeating that
        would be a second copy of eleven ranges, and the copy that goes wrong is the one
        somebody reads.
        """
        info = self.info
        storage = f"{info.size} byte{'' if info.size == 1 else 's'}"
        if self is Datatype.BOOLEAN:
            return f"A truth value, 0 or 1; {storage} of storage."
        if info.is_float:
            precision = "single" if info.size == 4 else "double"
            return (
                f"IEEE 754 {precision} precision floating point; {storage} of storage, "
                f"magnitude up to {format_number(info.raw_max)}."
            )
        sign = "Signed" if info.is_signed else "Unsigned"
        return (
            f"{sign} integer; {storage} of storage, "
            f"{format_number(info.raw_min)} to {format_number(info.raw_max)}."
        )


_DATATYPE_INFO: Final[dict[Datatype, DatatypeInfo]] = {
    Datatype.BOOLEAN: DatatypeInfo(1, False, False, 0, 1),
    Datatype.UINT8: DatatypeInfo(1, False, False, 0, 255),
    Datatype.SINT8: DatatypeInfo(1, False, True, -128, 127),
    Datatype.UINT16: DatatypeInfo(2, False, False, 0, 65535),
    Datatype.SINT16: DatatypeInfo(2, False, True, -32768, 32767),
    Datatype.UINT32: DatatypeInfo(4, False, False, 0, 4294967295),
    Datatype.SINT32: DatatypeInfo(4, False, True, -2147483648, 2147483647),
    Datatype.UINT64: DatatypeInfo(8, False, False, 0, 18446744073709551615),
    Datatype.SINT64: DatatypeInfo(8, False, True, -9223372036854775808, 9223372036854775807),
    Datatype.FLOAT32: DatatypeInfo(4, True, True, -FLOAT32_MAX, FLOAT32_MAX),
    Datatype.FLOAT64: DatatypeInfo(8, True, True, -FLOAT64_MAX, FLOAT64_MAX),
}


_STORAGE_STEM: Final = r"(?:bool(?:ean)?|u?int|sint|float|double|char|short|long|byte|word)"

_DATATYPE_LIKE: Final = re.compile(rf"{_STORAGE_STEM}[0-9_]*", re.IGNORECASE)
"""A word that is nothing but a storage stem followed by digits or underscores."""

TYPE_NAME_PATTERN: Final = rf"^(?!{_STORAGE_STEM}[0-9_]*$)[A-Za-z_][A-Za-z0-9_]*$"
"""The same rule as a regular expression, for the published schema and for editors.

Spelled twice, in two dialects, because the two consumers cannot share one: json schema
patterns are ECMA-262, where a negative lookahead is ordinary, and the validator pydantic
compiles has none. So the rule is enforced in python and *published* as this pattern, which an
editor applies as the file is typed - which is the whole point of having it.
"""


def _not_a_datatype_in_disguise(value: str) -> str:
    """Refuse a type name that reads as an attempt at a base datatype.

    This is what one key naming both would otherwise cost. Since ``datatype`` accepts a declared
    name as well as a base datatype, a mistyped ``uint166`` is a perfectly well formed *name*:
    without this it would pass the contract, reach the editor as valid, and be reported only
    when the project was next checked. Refusing the shape puts the rejection where the typo is.

    ``uint166``, ``int16``, ``float3`` and ``sint_16`` are refused; ``Int16_t``, ``intensity``,
    ``wordCount`` and ``charge`` are not. It also means a project cannot declare a type called
    ``uint16``, which would be a name nothing could ever refer to - written anywhere, the base
    datatype wins the union.
    """
    if _DATATYPE_LIKE.fullmatch(value):
        msg = (
            f"'{value}' reads as a base datatype rather than as the name of a type this project "
            f"declares; a base datatype has to be spelled as one of them exactly"
        )
        raise ValueError(msg)
    return value


TypeName = Annotated[
    str,
    StringConstraints(pattern=C_IDENTIFIER_PATTERN, min_length=1, max_length=IDENTIFIER_MAX_LENGTH),
    AfterValidator(_not_a_datatype_in_disguise),
    Field(json_schema_extra={"pattern": TYPE_NAME_PATTERN}),
]
"""The name of a type the project declares, as written where something refers to it.

The rule lives in python rather than in the constraint so that it survives being taken apart: a
tool that rebuilds one field on its own - the api documentation generator does exactly that -
gets a model it can still build, and the published pattern goes along for the ride.
"""

DatatypeRef = Annotated[Datatype | TypeName, Field(union_mode="left_to_right")]
"""What may be written where storage is named: one of the base datatypes, or a declared type.

One key names a type everywhere - on a structure member and on a declaration alike - rather
than a second key beside ``datatype``. A ``type`` key would have to mean "the name of a
declared type" in those two places and "which shape this entry has" at the top of a type
entry, and one key with one meaning is worth what it costs.

What it costs is stated plainly, because it is the largest thing given up: the published schema
can no longer say ``datatype`` is one of eleven values. It becomes the eleven *or* a string, so
an editor still offers them as completions and still documents each one, but a typo in a base
datatype name stops being refused as it is typed and becomes an ``unknown-type`` finding from
``ddd check`` instead.

Left to right, so that ``"uint16"`` is the datatype rather than a type somebody named after it.
"""


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
