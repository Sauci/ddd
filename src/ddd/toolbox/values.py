"""Initial values out of an image's bytes, spelled as DDD states them (section 4.6)."""

from __future__ import annotations

import math
import struct
from typing import Any, Final

_FORMATS: Final = {
    "boolean": "B",
    "uint8": "B",
    "sint8": "b",
    "uint16": "H",
    "sint16": "h",
    "uint32": "I",
    "sint32": "i",
    "uint64": "Q",
    "sint64": "q",
    "float32": "f",
    "float64": "d",
}
_FLOAT32_DIGITS: Final = 9
"""Significant digits that read every float32 back to its own bits."""


class UnstatableValueError(ValueError):
    """An initial value DDD has no spelling for; the message says what the value is."""


def initial_value(raw: bytes, datatype: str, dimensions: tuple[int, ...], byte_order: str) -> Any:
    """``raw`` read as ``datatype`` in ``byte_order``: a scalar, or nested lists in C order.

    An array whose elements are all the same bytes is that one value, the fill DDD gives a
    scalar stated on an array-shaped object. Bytes rather than values are compared, so that
    ``-0.0`` and ``0.0`` stay apart.
    """
    code = ("<" if byte_order == "little" else ">") + _FORMATS[datatype]
    size = struct.calcsize(code)
    chunks = [raw[start : start + size] for start in range(0, len(raw), size)]
    if all(chunk == chunks[0] for chunk in chunks):
        return _decoded(chunks[0], code, datatype)
    return _nested([_decoded(chunk, code, datatype) for chunk in chunks], dimensions)


def shortest_float32(value: float) -> float:
    """The shortest decimal that reads back to the float32 ``value``: 0.1 for ``0.1f``, rather
    than the 0.10000000149011612 the same bits spell as a double."""
    for digits in range(1, _FLOAT32_DIGITS):
        candidate = float(f"{value:.{digits}g}")
        if _reads_back(candidate, value):
            return candidate
    return float(f"{value:.{_FLOAT32_DIGITS}g}")


def _reads_back(candidate: float, value: float) -> bool:
    try:
        (again,) = struct.unpack("<f", struct.pack("<f", candidate))
    except OverflowError:
        # Rounded up past the largest float32, as 3.403e38 is for its largest value.
        return False
    return bool(again == value)


def _decoded(chunk: bytes, code: str, datatype: str) -> Any:
    (value,) = struct.unpack(code, chunk)
    if datatype == "boolean":
        if value not in (0, 1):
            msg = f"a boolean byte of {value}, which is neither 0 nor 1"
            raise UnstatableValueError(msg)
        return value == 1
    if datatype in ("float32", "float64"):
        if math.isnan(value):
            msg = "NaN"
            raise UnstatableValueError(msg)
        if math.isinf(value):
            msg = "an infinity"
            raise UnstatableValueError(msg)
        if datatype == "float32":
            return shortest_float32(value)
    return value


def _nested(values: list[Any], dimensions: tuple[int, ...]) -> list[Any]:
    if len(dimensions) <= 1:
        return values
    step = len(values) // dimensions[0]
    return [
        _nested(values[index * step : (index + 1) * step], dimensions[1:])
        for index in range(dimensions[0])
    ]
