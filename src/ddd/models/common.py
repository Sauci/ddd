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

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


class FileRoot(BaseModel):
    """Base of the hand-written file roots: project, component and types.

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

OBJECT_ID_ALPHABET: Final = "abcdefghjkmnpqrstvwxyz0123456789"
"""The characters an object id is drawn from: lowercase base32 without ``i``, ``l``, ``o``
or ``u``.

Those four are excluded so that an id read off a screen, a printout or a review comment can
be typed back without ambiguity. Lowercase alone rather than both cases, because an id that
differs from another only in case is one somebody will eventually mistype into a duplicate.
"""

OBJECT_ID_LENGTH: Final = 12
"""Twelve characters, about sixty bits: a collision inside one project does not happen, and
``duplicate-id`` catches it if it does."""

OBJECT_ID_PATTERN: Final = rf"^[{OBJECT_ID_ALPHABET}]{{{OBJECT_ID_LENGTH}}}$"

ObjectId = Annotated[str, StringConstraints(pattern=OBJECT_ID_PATTERN)]
"""The identity of a data object, which survives every rename of it.

Constrained rather than free text so that a hand-typed value is refused by the schema, where
an editor reports it as it is typed, rather than by a check that only a run of the tool
reaches. ``ddd id --assign`` is what writes one.
"""


def hash_excluding_mappings(model: BaseModel) -> int:
    """The hash of a frozen model, its mapping fields left out.

    A frozen model hashes by default from all its fields, and a ``dict`` cannot be hashed: an
    ``extensions`` block holds whatever a plugin put there, and a resolved object's
    ``references`` is a mapping too. Leaving them out costs nothing a caller would notice: two
    models equal in every field, mappings included, still hash equal, since equality is finer
    than this - the only thing a hash has to promise.
    """
    return hash((type(model), *(v for v in model.__dict__.values() if not isinstance(v, dict))))


SECTION_NAME_PATTERN: Final = r"^[A-Za-z0-9_.$]+$"
"""What a linker section name is spelled with: ``.calib``, ``.fast_ram``, ``.CRT$XCU``.

Tighter than what a linker accepts, because the name is spliced verbatim into the generated
c - ``__attribute__((section(".calib")))`` - where a quote would end the string literal and
whatever follows would become live code in somebody else's build.
"""

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


_BASE_DATATYPE_NAMES: Final = frozenset(member.value for member in Datatype)

TYPE_NAME_PATTERN: Final = (
    rf"^(?!(?:{'|'.join(sorted(_BASE_DATATYPE_NAMES))})$)[A-Za-z_][A-Za-z0-9_]*$"
)
"""The rule for a declared type's name as a regular expression, for the published schema.

Spelled twice, in two dialects, because the two consumers cannot share one: json schema
patterns are ECMA-262, where a negative lookahead is ordinary, and the validator pydantic
compiles has none. So the rule is enforced in python and *published* as this pattern, which an
editor applies as the file is typed - which is the whole point of having it. The pattern
carries the exact spellings; matching without regard to case is what the schema dialect
cannot say, so the loader says it below.
"""


def _not_a_base_datatype(value: str) -> str:
    """Refuse a declared type named after a base datatype, in any case.

    ``typename`` and ``datatype`` are separate keys, so the tool would not be confused - but a
    reader would: a type called ``uint16``, or ``UINT16``, wears the name of storage it is
    not, and every declaration naming it reads like a typo. Anything else is a legal name;
    what a project *should* call its types belongs to the project.
    """
    if value.lower() in _BASE_DATATYPE_NAMES:
        msg = (
            f"'{value}' spells a base datatype; a declared type carries a name of its own, so "
            f"that reading a declaration tells the two apart"
        )
        raise ValueError(msg)
    return value


TypeName = Annotated[
    str,
    StringConstraints(pattern=C_IDENTIFIER_PATTERN, min_length=1, max_length=IDENTIFIER_MAX_LENGTH),
    AfterValidator(_not_a_base_datatype),
    Field(json_schema_extra={"pattern": TYPE_NAME_PATTERN}),
]
"""The name of a type the project declares, as written where something refers to it.

The rule lives in python rather than in the constraint so that it survives being taken apart: a
tool that rebuilds one field on its own - the api documentation generator does exactly that -
gets a model it can still build, and the published pattern goes along for the ride.
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
