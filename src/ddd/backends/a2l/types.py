"""How the datatypes of the dictionary are spelled in ASAM MCD-2 MC.

The counterpart of :mod:`ddd.backends.c.types`: the core does not know these names either.
"""

from __future__ import annotations

from typing import Final

from ddd.models import Datatype

A2L_TYPE: Final[dict[Datatype, str]] = {
    Datatype.BOOLEAN: "UBYTE",
    Datatype.UINT8: "UBYTE",
    Datatype.SINT8: "SBYTE",
    Datatype.UINT16: "UWORD",
    Datatype.SINT16: "SWORD",
    Datatype.UINT32: "ULONG",
    Datatype.SINT32: "SLONG",
    Datatype.UINT64: "A_UINT64",
    Datatype.SINT64: "A_INT64",
    Datatype.FLOAT32: "FLOAT32_IEEE",
    Datatype.FLOAT64: "FLOAT64_IEEE",
}
