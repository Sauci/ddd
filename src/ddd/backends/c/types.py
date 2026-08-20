"""How the datatypes of the dictionary are spelled in c.

This table used to sit on :class:`~ddd.models.common.Datatype` itself, next to the a2l one.
It belongs here: the core has no reason to know that a ``uint16`` is written ``uint16_t``.
The table is only the ISO spelling the *example* templates render as ``c_type``; a project
whose platform header spells the types itself - AUTOSAR's ``Platform_Types.h`` uses the
dictionary's own names - renders the ``datatype`` field of the views instead and never
meets this table at all.
"""

from __future__ import annotations

from typing import Final

from ddd.models import Datatype

C_TYPE: Final[dict[Datatype, str]] = {
    Datatype.BOOLEAN: "bool",
    Datatype.UINT8: "uint8_t",
    Datatype.SINT8: "int8_t",
    Datatype.UINT16: "uint16_t",
    Datatype.SINT16: "int16_t",
    Datatype.UINT32: "uint32_t",
    Datatype.SINT32: "int32_t",
    Datatype.UINT64: "uint64_t",
    Datatype.SINT64: "int64_t",
    Datatype.FLOAT32: "float",
    Datatype.FLOAT64: "double",
}

# Uppercase suffixes, as the coding standards of the industry ask for.
LITERAL_SUFFIX: Final[dict[Datatype, str]] = {
    Datatype.BOOLEAN: "",
    Datatype.UINT8: "U",
    Datatype.SINT8: "",
    Datatype.UINT16: "U",
    Datatype.SINT16: "",
    Datatype.UINT32: "U",
    Datatype.SINT32: "",
    Datatype.UINT64: "ULL",
    Datatype.SINT64: "LL",
    Datatype.FLOAT32: "F",
    Datatype.FLOAT64: "",
}


def needs_stdint(datatypes: set[Datatype]) -> bool:
    return any(datatype.is_integer for datatype in datatypes)


def needs_stdbool(datatypes: set[Datatype]) -> bool:
    return Datatype.BOOLEAN in datatypes
