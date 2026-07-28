"""Primitive building blocks shared by all DDD contracts.

This module is deliberately free of any output format: a datatype knows how many bytes it
occupies and which values it can hold, not what a c compiler or a calibration tool calls it.
Those mappings belong to the backend that needs them (:mod:`ddd.backends.c.types`,
:mod:`ddd.backends.a2l.types`).

The one exception is the identifier rule below. Names have to be usable as c identifiers
because generating c is not optional - it is the reason DDD exists (SPEC 1.3) - so this is a
property of the input contract rather than of a backend that may or may not run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final

from pydantic import StringConstraints

C_IDENTIFIER_PATTERN: Final = r"^[A-Za-z_][A-Za-z0-9_]*$"

Identifier = Annotated[
    str,
    StringConstraints(pattern=C_IDENTIFIER_PATTERN, min_length=1, max_length=255),
]
"""A string that is usable as a c identifier."""


# Keywords of C11/C23 plus the identifiers introduced by <stdbool.h>.  A global
# variable named like one of these produces code that does not compile, so DDD
# rejects them early instead of letting the compiler complain about generated code.
C_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "alignas", "alignof", "auto", "bool", "break", "case", "char", "const",
        "constexpr", "continue", "default", "do", "double", "else", "enum", "extern",
        "false", "float", "for", "goto", "if", "inline", "int", "long", "nullptr",
        "register", "restrict", "return", "short", "signed", "sizeof", "static",
        "static_assert", "struct", "switch", "thread_local", "true", "typedef",
        "typeof", "union", "unsigned", "void", "volatile", "while",
        "_Alignas", "_Alignof", "_Atomic", "_BitInt", "_Bool", "_Complex", "_Decimal32",
        "_Decimal64", "_Decimal128", "_Generic", "_Imaginary", "_Noreturn",
        "_Static_assert", "_Thread_local",
    }
)  # fmt: skip

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

    BOOL = "bool"
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
        return not self.info.is_float and self is not Datatype.BOOL

    @property
    def raw_min(self) -> float:
        """Smallest value representable in the raw (implementation) domain."""
        return self.info.raw_min

    @property
    def raw_max(self) -> float:
        """Largest value representable in the raw (implementation) domain."""
        return self.info.raw_max


_DATATYPE_INFO: Final[dict[Datatype, DatatypeInfo]] = {
    Datatype.BOOL: DatatypeInfo(1, False, False, 0, 1),
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


def is_reserved_identifier(name: str) -> bool:
    """Return ``True`` for names a c compiler reserves for itself."""
    if name in C_KEYWORDS:
        return True
    # C11 7.1.3: identifiers starting with an underscore followed by an uppercase
    # letter, or containing a double underscore, are reserved for the implementation.
    if name.startswith("__") or "__" in name:
        return True
    return len(name) >= 2 and name[0] == "_" and name[1].isupper()


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
