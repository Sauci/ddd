"""How the datatypes of the dictionary are spelled in c.

This table used to sit on :class:`~ddd.models.common.Datatype` itself, next to the a2l one.
It belongs here: the core has no reason to know that a ``uint16`` is written ``uint16_t``,
and a project targeting a toolchain with different type names only has to change this file.
"""

from __future__ import annotations

from typing import Final

from ddd.models import Datatype

C_TYPE: Final[dict[Datatype, str]] = {
    Datatype.BOOLEAN: "bool",
    Datatype.UINT8: "uint8_t",
    Datatype.INT8: "int8_t",
    Datatype.UINT16: "uint16_t",
    Datatype.INT16: "int16_t",
    Datatype.UINT32: "uint32_t",
    Datatype.INT32: "int32_t",
    Datatype.UINT64: "uint64_t",
    Datatype.INT64: "int64_t",
    Datatype.FLOAT32: "float",
    Datatype.FLOAT64: "double",
}

# Uppercase suffixes, as the coding standards of the industry ask for.
LITERAL_SUFFIX: Final[dict[Datatype, str]] = {
    Datatype.BOOLEAN: "",
    Datatype.UINT8: "U",
    Datatype.INT8: "",
    Datatype.UINT16: "U",
    Datatype.INT16: "",
    Datatype.UINT32: "U",
    Datatype.INT32: "",
    Datatype.UINT64: "ULL",
    Datatype.INT64: "LL",
    Datatype.FLOAT32: "F",
    Datatype.FLOAT64: "",
}


def needs_stdint(datatypes: set[Datatype]) -> bool:
    return any(datatype.is_integer for datatype in datatypes)


def needs_stdbool(datatypes: set[Datatype]) -> bool:
    return Datatype.BOOLEAN in datatypes
