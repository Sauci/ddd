"""Turning dictionary values into c source fragments: literals, comments, guards."""

from __future__ import annotations

import re

from ddd.backends.c.types import C_TYPE, LITERAL_SUFFIX
from ddd.ir import ResolvedInstance, ResolvedObject
from ddd.models import (
    Datatype,
    InitValue,
    PointCounts,
    broadcast,
    flatten,
    format_shape,
    stored_counts,
)

_MAX_VALUES_PER_LINE = 8
_INDENT = "    "
_INT64_MIN = -(2**63)


def c_literal(value: bool | int | float, datatype: Datatype) -> str:
    """Render one raw value as a c literal of ``datatype``."""
    if datatype is Datatype.BOOLEAN:
        # "1"/"0" rather than "true"/"false": the words need <stdbool.h> before C23, a
        # project on AUTOSAR's Platform_Types has TRUE/FALSE instead, and the initialiser
        # is the one c fragment the tool writes that no template can respell - it sits
        # inside the braces of a nested initialiser. The numerals mean the same thing in
        # every one of these worlds and need no header in any of them.
        return "1" if value else "0"
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


def c_constant_literal(value: int | float) -> str:
    """Render a declared constant as the c literal its value means.

    A constant carries no datatype - it is a named number, and what a shape or an expression
    does with it is the project's business - so the literal is spelled for the narrowest type
    that holds the value: an ``int`` where one holds it, and ``long long`` or ``unsigned long
    long`` past that, which is what :func:`c_literal` already spells for an ``init``. Written
    out bare instead, the two ends of the 64 bit range are not the numbers they read as:
    ``18446744073709551615`` has no signed type to be and c takes it as unsigned with a
    diagnostic, and ``-9223372036854775808`` is a unary minus applied to that same literal.
    A number with a fraction is a ``double`` literal, which is what it looks like already.
    """
    if isinstance(value, float):
        return c_literal(value, Datatype.FLOAT64)
    if Datatype.SINT32.raw_min <= value <= Datatype.SINT32.raw_max:
        return c_literal(value, Datatype.SINT32)
    if value <= Datatype.SINT64.raw_max:
        return c_literal(value, Datatype.SINT64)
    return c_literal(value, Datatype.UINT64)


def c_string_literal(text: str) -> str:
    """Render a string init as a c string literal.

    Only ``"`` and ``\\`` need escaping in printable ASCII, and ``?`` gets it too: two of
    them before any of the nine characters that close a trigraph form a trigraph under a
    pedantic pre-C23 dialect, and ``\\?`` is the escape c provides for exactly that. The
    analysis has refused anything outside 0x20 to 0x7E, so no other escape is ever needed,
    and it has left room for the terminator, which c writes along with the zeros that fill
    the rest of the array.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("?", "\\?")
    return f'"{escaped}"'


def _flat_braces(parts: tuple[str, ...], indent: int = 0) -> str:
    """Lay a flat list of already-rendered parts out as a c initialiser: one line up to
    ``_MAX_VALUES_PER_LINE`` values, then wrapped - the layout a flat run of values gets
    whether it came from a one-dimensional init or from a table's counts and values together.
    """
    if len(parts) <= _MAX_VALUES_PER_LINE:
        return "{ " + ", ".join(parts) + " }"
    pad = _INDENT * (indent + 1)
    closing_pad = _INDENT * indent
    lines = [
        pad + ", ".join(parts[start : start + _MAX_VALUES_PER_LINE])
        for start in range(0, len(parts), _MAX_VALUES_PER_LINE)
    ]
    return "{\n" + ",\n".join(lines) + "\n" + closing_pad + "}"


def c_initializer(value: InitValue, datatype: Datatype, indent: int = 0) -> str:
    """Render a (possibly nested) init value as a c initialiser."""
    if isinstance(value, str):
        return c_string_literal(value)
    if not isinstance(value, tuple):
        return c_literal(value, datatype)

    pad = _INDENT * (indent + 1)
    closing_pad = _INDENT * indent
    parts = [c_initializer(element, datatype, indent + 1) for element in value]

    if any(isinstance(element, tuple) for element in value):
        # One sub array per line keeps the shape of the data readable.
        body = ",\n".join(f"{pad}{part}" for part in parts)
        return "{\n" + body + "\n" + closing_pad + "}"

    return _flat_braces(tuple(parts), indent)


def c_type(entry: ResolvedObject) -> str:
    return C_TYPE[entry.datatype]


def _counted(entry: ResolvedObject | ResolvedInstance) -> bool:
    """Whether the object stores its point counts ahead of its data.

    A structured variable never does: it is no table, and it carries no such field."""
    return isinstance(entry, ResolvedObject) and entry.point_counts is PointCounts.LEADING


def storage_suffix(entry: ResolvedObject | ResolvedInstance) -> str:
    """The array suffix the object is declared with: its shape, or the flat storage of a table
    that keeps its counts in front of its values.

    Flat because the counts and the values are one run of one type in memory - which is what
    the routine reading them is handed - and a ``[y][x]`` array has no room in front of it.
    Each dimension is parenthesised because it may be a constant's name, and a constant is a
    macro whose expansion nobody here controls.
    """
    spelled = entry.spelled_shape
    if not _counted(entry):
        return format_shape(spelled)
    product = " * ".join(f"({dimension})" for dimension in spelled)
    return f"[{len(spelled)} + {product}]"


def initializer_of(entry: ResolvedObject) -> str | None:
    """The initialiser of an object, or ``None`` for implicit zero initialisation.

    A table keeping its counts in front always has one, since the counts cannot be left to the
    startup code: the counts, each by the constant's name when its axis is sized by one, then
    the values in the row order the nested form would have used - or nothing more, when no
    ``init`` was given, which leaves the rest zero exactly as an absent initialiser would.
    """
    if _counted(entry):
        counts = [
            count if isinstance(count, str) else c_literal(count, entry.datatype)
            for count in stored_counts(entry.kind, entry.spelled_shape)
        ]
        values = [] if entry.init is None else flatten(broadcast(entry.init, entry.shape))
        flat = (*counts, *(c_literal(value, entry.datatype) for value in values))
        return _flat_braces(flat)
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
    """Make text safe to put inside a ``/* ... */`` comment.

    Both markers are defused, because both of them end a build. ``*/`` closes the comment the
    template opened and spills the rest of the description into the code; ``/*`` stays inside
    it and is a diagnostic instead - ``-Wcomment``, which ``-Wall`` turns on, reports ``"/*"
    within comment``, and the warning set this repository verifies the generated code with
    (``docker/compile.sh``) carries ``-Werror``. One description reaches the definition file,
    the shared header, the types header and the component's own header, so one of them stops
    the compilation of all four.

    The opener is replaced first, and the order is what makes the pair safe rather than a
    matter of taste: ``/*/`` is both markers sharing one ``*``, and defusing either of them
    alone re-forms the other out of what is left. Taking the opener first leaves no ``/``
    immediately before a ``*``, so the second pass can form no new opener, and it inserts a
    space before the ``/`` it writes, so it can form no new closer either.
    """
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed.replace("/*", "/ *").replace("*/", "* /")


def guard_name(*parts: str) -> str:
    """Build an include guard such as ``DDD_SENSOR_HUB_H``."""
    joined = "_".join(part for part in parts if part)
    upper = re.sub(r"[^0-9A-Za-z]+", "_", joined).upper()
    upper = re.sub(r"__+", "_", upper).strip("_")
    if upper and upper[0].isdigit():
        upper = "N" + upper
    return f"{upper}_H"
