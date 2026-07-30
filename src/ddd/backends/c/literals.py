"""Turning dictionary values into c source fragments: literals, comments, guards."""

from __future__ import annotations

import re

from ddd.backends.c.types import C_TYPE, LITERAL_SUFFIX
from ddd.ir import ResolvedObject
from ddd.models import Datatype, InitValue, Shape, broadcast

_MAX_VALUES_PER_LINE = 8
_INDENT = "    "
_INT64_MIN = -(2**63)


def c_literal(value: bool | int | float, datatype: Datatype) -> str:
    """Render one raw value as a c literal of ``datatype``."""
    if datatype is Datatype.BOOLEAN:
        return "true" if value else "false"
    if datatype.is_float:
        # repr of a float always carries a '.' or an exponent, so the literal is never
        # mistaken for an integer one.
        return repr(float(value)) + LITERAL_SUFFIX[datatype]
    number = int(value)
    suffix = LITERAL_SUFFIX[datatype]
    if number == _INT64_MIN:
        # There is no negative literal in c: '-9223372036854775808' is the negation of a
        # literal too large for any signed type, which is a constraint violation rather than
        # the value it looks like. Every <stdint.h> spells INT64_MIN this way for the same
        # reason, and the extra parentheses keep it safe in any surrounding expression.
        return f"(-9223372036854775807{suffix} - 1)"
    return f"{number}{suffix}"


def c_initializer(value: InitValue, datatype: Datatype, indent: int = 0) -> str:
    """Render a (possibly nested) init value as a c initialiser."""
    if not isinstance(value, tuple):
        return c_literal(value, datatype)

    pad = _INDENT * (indent + 1)
    closing_pad = _INDENT * indent
    parts = [c_initializer(element, datatype, indent + 1) for element in value]

    if any(isinstance(element, tuple) for element in value):
        # One sub array per line keeps the shape of the data readable.
        body = ",\n".join(f"{pad}{part}" for part in parts)
        return "{\n" + body + "\n" + closing_pad + "}"

    if len(parts) <= _MAX_VALUES_PER_LINE:
        return "{ " + ", ".join(parts) + " }"
    lines = [
        pad + ", ".join(parts[start : start + _MAX_VALUES_PER_LINE])
        for start in range(0, len(parts), _MAX_VALUES_PER_LINE)
    ]
    return "{\n" + ",\n".join(lines) + "\n" + closing_pad + "}"


def declarator_suffix(shape: Shape) -> str:
    """``"[4][2]"`` for a 4x2 array, ``""`` for a scalar."""
    return "".join(f"[{dimension}]" for dimension in shape)


def c_type(entry: ResolvedObject) -> str:
    return C_TYPE[entry.datatype]


def initializer_of(entry: ResolvedObject) -> str | None:
    """The initialiser of an object, or ``None`` for implicit zero initialisation."""
    if entry.init is None:
        return None
    return c_initializer(broadcast(entry.init, entry.shape), entry.datatype)


def doc_comment(entry: ResolvedObject) -> str | None:
    """One line describing the object, or ``None`` when there is nothing to say.

    The text only, without any comment marker: whether it ends up in a plain comment, a
    documented one, or nowhere at all is for the template to decide.
    """
    parts: list[str] = []
    if entry.description:
        parts.append(sanitize_comment(entry.description))
    if entry.unit:
        parts.append(f"[{sanitize_comment(entry.unit)}]")
    detail = _kind_detail(entry)
    if detail:
        parts.append(detail)
    return " ".join(parts) if parts else None


def _kind_detail(entry: ResolvedObject) -> str:
    """Short note about what a calibration object is, added to its comment."""
    references = entry.references
    shape = entry.shape
    match entry.kind.value:
        case "parameter":
            return "(calibration parameter)"
        case "value_block":
            return "(calibration value block)"
        case "axis":
            return f"(calibration axis, {shape[0] if shape else 0} points)"
        case "curve":
            return f"(calibration curve over {references.get('axis', '?')})"
        case "map":
            return (
                f"(calibration map over {references.get('x_axis', '?')}"
                f" and {references.get('y_axis', '?')})"
            )
        case _:
            return ""


def sanitize_comment(text: str) -> str:
    """Make text safe to put inside a ``/* ... */`` comment."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed.replace("*/", "* /")


def guard_name(*parts: str) -> str:
    """Build an include guard such as ``DDD_SENSOR_HUB_H``."""
    joined = "_".join(part for part in parts if part)
    upper = re.sub(r"[^0-9A-Za-z]+", "_", joined).upper()
    upper = re.sub(r"__+", "_", upper).strip("_")
    if upper and upper[0].isdigit():
        upper = "N" + upper
    return f"{upper}_H"
