"""Changing a description file the way a person would: one value, in the file's own layout.

``ddd gui`` writes into the same ``*.ddd.json`` files that people edit by hand and review in
git, so a change it makes has to read like a hand edit - the value that changed and nothing
else. A json round trip would reformat the whole file, so every change here is textual: a span
of the file's text replaced, computed from the positions :class:`ddd.lsp.ranges.Document`
records.

Three rules keep that safe:

* **Values arrive as json text, never as parsed values.** DDD reads ``1.0`` as fractional and
  ``1`` as an integer, and a value that passed through a parser and a serialiser on its way
  here - JavaScript's ``JSON.stringify(1.0)`` is ``1`` - would change meaning without changing
  its number. A structured value is laid out by re-indenting its tokens, so every literal keeps
  its spelling.
* **An edit follows the file.** A member added to an object written on one line stays on that
  line; one added to an object written one member per line gets a line of its own, indented
  like the member before it and ended like the line it follows.
* **Every edit is verified.** The operations are applied to the parsed document as well, and
  the edited text has to read back as exactly that document, or nothing is written.

:mod:`ddd.lsp.ranges` is imported inside the functions that scan a text rather than at the top:
importing it runs ``ddd.lsp``, which brings up the whole language server, and
:mod:`ddd.identity` - which the language server imports - takes its layout helpers from here.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from ddd.pointers import parent_pointer, segments

if TYPE_CHECKING:
    from ddd.lsp.ranges import Document

INVALID: Final = "invalid"
"""A pointer names nothing, an operation does not fit what it names, or a value is not json."""

UNREADABLE: Final = "unreadable"
"""The file is not valid json, so no pointer names a place in it."""

UNVERIFIED: Final = "unverified"
"""The edited text did not read back as the intended document."""

_WHITESPACE: Final = " \t\r\n"
_STRUCTURE: Final = "{}[]:,"
_OPENING: Final = ("{", "[")

DEFAULT_INDENT_UNIT: Final = "  "
"""The indentation unit of a file that nests nothing on a line of its own."""

_INDEXED: Final = re.compile(r"(.*)\[(\d+)\]")


class EditError(ValueError):
    """An edit that cannot be made, carrying the code ``ddd gui`` answers it with."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_raw(raw: object) -> Any:
    """The value a json text stands for, refusing anything but exactly one json value.

    ``NaN`` and ``Infinity`` are refused although python's parser accepts them: they are not
    json, and nothing else that reads a description would take them.
    """
    if not isinstance(raw, str):
        raise EditError(INVALID, "a value is given as json text")
    try:
        return json.loads(raw, parse_constant=_refuse_constant)
    except ValueError as error:
        raise EditError(INVALID, f"{raw!r} is not one json value: {error}") from None


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"{name} is not json")


def newline_at(text: str, offset: int) -> str:
    """How the line ``offset`` sits on ends, so a line added after it ends the same way.

    All three spellings, found by whichever of ``\\r`` and ``\\n`` comes first. Looking for
    ``\\n`` alone answered "line feed" for a file written with bare carriage returns, which has
    none at all. A text with no line break after ``offset`` is given ``\\n``, there being
    nothing to copy.
    """
    carriage = text.find("\r", offset)
    feed = text.find("\n", offset)
    if carriage >= 0 and (feed < 0 or carriage < feed):
        return "\r\n" if carriage + 1 == feed else "\r"
    return "\n"


def indent_of_line_at(text: str, offset: int) -> str:
    """The leading whitespace of the line ``offset`` sits on, so a new line lines up with it.

    Whatever the file is indented with: a file written with tabs gets a tab, one written with
    four spaces gets four. A line is what ``\\n`` ends, the way every position DDD hands out
    counts lines.
    """
    start = text.rfind("\n", 0, offset) + 1
    return text[start : len(text) - len(text[start:].lstrip())]


@dataclass(slots=True)
class _Node:
    """A json value as its tokens spell it: a literal, or a container and its entries."""

    token: str
    entries: list[tuple[str | None, _Node]] = field(default_factory=list)


def lay_out(raw: str, *, one_line: bool, indent: str, unit: str, newline: str) -> str:
    """A json text rewritten into the layout of the place it goes, every literal as spelled.

    A container goes on one line when ``one_line`` asks for it, or when it holds nothing but
    literals - which is how a description writes a conversion, a range or a shape. Otherwise it
    goes one entry per line, each indented by ``unit`` from ``indent`` - the indentation of the
    line the value starts on - and the lines end with ``newline``.
    """
    parse_raw(raw)
    node, _ = _parsed(_tokens(raw), 0)
    return _rendered(node, one_line=one_line, indent=indent, unit=unit, newline=newline)


def _tokens(raw: str) -> list[str]:
    """The tokens of a json text that has already parsed, each spelled as it is written."""
    tokens: list[str] = []
    position = 0
    while position < len(raw):
        character = raw[position]
        if character in _WHITESPACE:
            position += 1
            continue
        if character in _STRUCTURE:
            end = position + 1
        elif character == '"':
            end = position + 1
            while raw[end] != '"':
                end += 2 if raw[end] == "\\" else 1
            end += 1
        else:
            end = position
            while end < len(raw) and raw[end] not in _STRUCTURE and raw[end] not in _WHITESPACE:
                end += 1
        tokens.append(raw[position:end])
        position = end
    return tokens


def _parsed(tokens: list[str], position: int) -> tuple[_Node, int]:
    """The value starting at ``tokens[position]``, and the position just past it."""
    opening = tokens[position]
    node = _Node(opening)
    if opening not in _OPENING:
        return node, position + 1
    position += 1
    if tokens[position] in ("}", "]"):
        return node, position + 1
    while True:
        key = None
        if opening == "{":
            key = tokens[position]
            position += 2  # the key and its ':'
        child, position = _parsed(tokens, position)
        node.entries.append((key, child))
        position += 1  # the ',' or the closing bracket
        if tokens[position - 1] != ",":
            return node, position


def _rendered(node: _Node, *, one_line: bool, indent: str, unit: str, newline: str) -> str:
    if node.token not in _OPENING:
        return node.token
    closing = "}" if node.token == "{" else "]"
    if not node.entries:
        return node.token + closing
    if one_line or all(child.token not in _OPENING for _, child in node.entries):
        inner = ", ".join(
            _entry(key, _rendered(child, one_line=True, indent=indent, unit=unit, newline=newline))
            for key, child in node.entries
        )
        return f"{{ {inner} }}" if node.token == "{" else f"[{inner}]"
    deeper = indent + unit
    inner = f",{newline}{deeper}".join(
        _entry(key, _rendered(child, one_line=False, indent=deeper, unit=unit, newline=newline))
        for key, child in node.entries
    )
    return f"{node.token}{newline}{deeper}{inner}{newline}{indent}{closing}"


def _entry(key: str | None, value: str) -> str:
    return value if key is None else f"{key}: {value}"


@dataclass(frozen=True, slots=True)
class TextEdit:
    """Replace the characters from ``start`` to ``end`` with ``text``."""

    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Operation:
    """One change at one pointer.

    ``set`` writes ``raw`` at ``pointer``, adding the member when its object lacks it; ``remove``
    takes the entry away; ``insert`` puts ``raw`` into an array before the index ``pointer``
    ends in, which may be the array's length; ``move`` moves an array's element to index ``to``.
    """

    op: str
    pointer: str
    raw: str | None = None
    to: int | None = None


def indent_unit(document: Document) -> str:
    """How far this file indents one level.

    The first entry written on a line of its own, less the indentation of the line its
    container opens on; :data:`DEFAULT_INDENT_UNIT` for a file that nests nothing that way.
    """
    return _unit_below(document, "") or DEFAULT_INDENT_UNIT


def replacement(document: Document, pointer: str, raw: str) -> TextEdit:
    """The edit writing ``raw`` in place of the value at ``pointer``."""
    span = document.value_span_of(pointer)
    if span is None:
        raise EditError(INVALID, f"nothing is written at {_named(pointer)}")
    text = document.text
    value = lay_out(
        raw,
        one_line=_around_on_one_line(document, pointer),
        indent=indent_of_line_at(text, span[0]),
        unit=indent_unit(document),
        newline=newline_at(text, span[0]),
    )
    return TextEdit(span[0], span[1], value)


def member_addition(
    document: Document, pointer: str, key: str, raw: str, *, verbatim: bool = False
) -> TextEdit:
    """The edit adding ``key: raw`` to the object at ``pointer``, after its last member.

    ``verbatim`` writes ``raw`` exactly as given - a value copied out of another file the way
    its author wrote it - where otherwise it is laid out to fit.
    """
    members = document.value_at(pointer)
    if not isinstance(members, dict):
        raise EditError(INVALID, f"{_named(pointer)} is not an object")
    if key in members:
        raise EditError(INVALID, f"{_child(pointer, key)} is already written")
    prefix = f"{json.dumps(key, ensure_ascii=False)}: "
    return _added(document, pointer, prefix, raw, None, verbatim=verbatim)


def insertion(document: Document, pointer: str, raw: str, *, verbatim: bool = False) -> TextEdit:
    """The edit inserting ``raw`` into an array, before the index ``pointer`` ends in."""
    found = _indexed(pointer)
    if found is None:
        raise EditError(INVALID, f"{_named(pointer)} does not end in an array index")
    array, index = found
    elements = document.value_at(array)
    if not isinstance(elements, list):
        raise EditError(INVALID, f"{_named(array)} is not an array")
    if index > len(elements):
        raise EditError(INVALID, f"{pointer} is past the end of an array of {len(elements)}")
    return _added(document, array, "", raw, index, verbatim=verbatim)


def removal(document: Document, pointer: str) -> TextEdit:
    """The edit taking the entry at ``pointer`` away, with exactly one comma.

    The comma after it, or - for the last entry - the one before it, so that none is left
    trailing. Taking the only entry leaves the brackets and nothing between them.
    """
    span = document.span_of(pointer) if pointer else None
    if span is None:
        raise EditError(INVALID, f"nothing to remove at {_named(pointer)}")
    container = parent_pointer(pointer)
    entries = _entries(document, container)
    position = entries.index(pointer)
    if len(entries) == 1:
        start, end = _span(document.value_span_of(container))
        return TextEdit(start + 1, end - 1, "")
    if position < len(entries) - 1:
        return TextEdit(span[0], _span(document.span_of(entries[position + 1]))[0], "")
    return TextEdit(_span(document.span_of(entries[position - 1]))[1], span[1], "")


def edit_text(text: str, operations: Sequence[Operation]) -> str:
    """The text with every operation made in order, verified against the parsed document."""
    from ddd.lsp.ranges import Document

    document = Document(text)
    if document.data is None:
        raise EditError(UNREADABLE, "the file is not valid json, so no pointer names a place in it")
    expected = copy.deepcopy(document.data)
    for operation in operations:
        if document.data is None:
            raise EditError(UNVERIFIED, "an edit left the file unreadable")
        text, expected = _made(document, operation, expected)
        document = Document(text)
    if document.data is None or _canonical(document.data) != _canonical(expected):
        raise EditError(UNVERIFIED, "the edited file does not read back as the intended document")
    return text


def _made(document: Document, operation: Operation, expected: Any) -> tuple[str, Any]:
    """One operation made on the text, and on the parsed document it has to read back as."""
    if operation.op == "set":
        raw = _raw_of(operation)
        value = parse_raw(raw)
        edit = _set_edit(document, operation.pointer, raw)
        return _applied(document.text, edit), _set_value(expected, operation.pointer, value)
    if operation.op == "remove":
        edit = removal(document, operation.pointer)
        return _applied(document.text, edit), _removed_value(expected, operation.pointer)
    if operation.op == "insert":
        raw = _raw_of(operation)
        value = parse_raw(raw)
        edit = insertion(document, operation.pointer, raw)
        return _applied(document.text, edit), _inserted_value(expected, operation.pointer, value)
    if operation.op == "move":
        return _moved(document, operation, expected)
    raise EditError(INVALID, f"{operation.op!r} is not an operation: set, remove, insert or move")


def _set_edit(document: Document, pointer: str, raw: str) -> TextEdit:
    if document.value_span_of(pointer) is not None:
        return replacement(document, pointer, raw)
    if _indexed(pointer) is not None:
        raise EditError(INVALID, f"nothing is written at {pointer}")
    parent = parent_pointer(pointer)
    key = pointer[len(parent) + 1 :] if parent else pointer
    return member_addition(document, parent, key, raw)


def _moved(document: Document, operation: Operation, expected: Any) -> tuple[str, Any]:
    from ddd.lsp.ranges import Document

    found = _indexed(operation.pointer)
    to = operation.to
    elements = None if found is None else document.value_at(found[0])
    if (
        found is None
        or not isinstance(elements, list)
        or not isinstance(to, int)
        or isinstance(to, bool)
        or not 0 <= found[1] < len(elements)
        or not 0 <= to < len(elements)
    ):
        raise EditError(INVALID, f"{_named(operation.pointer)} cannot move to {to!r}")
    array, index = found
    if index == to:
        return document.text, expected
    raw = document.raw_at(operation.pointer)
    assert raw is not None  # value_at just found the element, so the scan recorded it
    removed = _applied(document.text, removal(document, operation.pointer))
    shortened = Document(removed)
    moved = _applied(removed, insertion(shortened, f"{array}[{to}]", raw, verbatim=True))
    container, _ = _container(expected, operation.pointer)
    container.insert(to, container.pop(index))
    return moved, expected


def _added(
    document: Document,
    container: str,
    prefix: str,
    raw: str,
    index: int | None,
    *,
    verbatim: bool,
) -> TextEdit:
    """The edit putting ``prefix`` and ``raw`` into a container, before entry ``index`` or last."""
    text = document.text
    unit = indent_unit(document)
    start, end = _span(document.value_span_of(container))
    entries = _entries(document, container)
    if not entries:
        # Rewritten whole, holding its one entry, in the layout of the container around it.
        base = indent_of_line_at(text, start)
        newline = newline_at(text, start)
        if _around_on_one_line(document, container):
            value = _value(raw, verbatim, one_line=True, indent=base, unit=unit, newline=newline)
            inner = f" {prefix}{value} " if text[start] == "{" else f"{prefix}{value}"
            return TextEdit(start, end, f"{text[start]}{inner}{text[end - 1]}")
        deeper = base + unit
        value = _value(raw, verbatim, one_line=False, indent=deeper, unit=unit, newline=newline)
        whole = f"{text[start]}{newline}{deeper}{prefix}{value}{newline}{base}{text[end - 1]}"
        return TextEdit(start, end, whole)
    one_line = _on_one_line(document, container)
    if index is None or index == len(entries):
        at = _span(document.span_of(entries[-1]))[1]
    else:
        at = _span(document.span_of(entries[index]))[0]
    indent = indent_of_line_at(text, at)
    newline = newline_at(text, at)
    value = _value(raw, verbatim, one_line=one_line, indent=indent, unit=unit, newline=newline)
    separator = ", " if one_line else f",{newline}{indent}"
    if index is None or index == len(entries):
        return TextEdit(at, at, f"{separator}{prefix}{value}")
    return TextEdit(at, at, f"{prefix}{value}{separator}")


def _value(
    raw: str, verbatim: bool, *, one_line: bool, indent: str, unit: str, newline: str
) -> str:
    if verbatim:
        parse_raw(raw)
        return raw.strip()
    return lay_out(raw, one_line=one_line, indent=indent, unit=unit, newline=newline)


def _entries(document: Document, pointer: str) -> list[str]:
    """The pointers of a container's entries, in the order the text writes them."""
    value = document.value_at(pointer)
    if isinstance(value, dict):
        entries = [_child(pointer, key) for key in value]
    elif isinstance(value, list):
        entries = [f"{pointer}[{index}]" for index in range(len(value))]
    else:
        return []
    return sorted(entries, key=lambda entry: _span(document.span_of(entry))[0])


def _on_one_line(document: Document, pointer: str) -> bool:
    """Whether a container is written on one line: its last entry ends on the line it opens on.

    Measured to the last entry rather than to the closing bracket, the way the language server's
    quick fixes have always measured it.
    """
    start, end = _span(document.value_span_of(pointer))
    entries = _entries(document, pointer)
    if entries:
        end = _span(document.span_of(entries[-1]))[1]
    return "\n" not in document.text[start:end]


def _around_on_one_line(document: Document, pointer: str) -> bool:
    """Whether the container holding ``pointer`` is written on one line; the top of the file is
    measured as itself."""
    return _on_one_line(document, parent_pointer(pointer) if pointer else "")


def _unit_below(document: Document, pointer: str) -> str | None:
    text = document.text
    opening = _span(document.value_span_of(pointer))[0]
    outer = indent_of_line_at(text, opening)
    for entry in _entries(document, pointer):
        start = _span(document.span_of(entry))[0]
        inner = indent_of_line_at(text, start)
        if "\n" in text[opening:start] and len(inner) > len(outer) and inner.startswith(outer):
            return inner[len(outer) :]
        found = _unit_below(document, entry)
        if found is not None:
            return found
    return None


def _indexed(pointer: str) -> tuple[str, int] | None:
    match = _INDEXED.fullmatch(pointer)
    return None if match is None else (match.group(1), int(match.group(2)))


def _child(pointer: str, key: str) -> str:
    return f"{pointer}.{key}" if pointer else key


def _named(pointer: str) -> str:
    return pointer or "the top of the file"


def _span(span: tuple[int, int] | None) -> tuple[int, int]:
    """A span the scan recorded for a pointer built from what it scanned."""
    assert span is not None
    return span


def _raw_of(operation: Operation) -> str:
    if operation.raw is None:
        raise EditError(INVALID, f"{operation.op} at {_named(operation.pointer)} needs a value")
    return operation.raw


def _applied(text: str, edit: TextEdit) -> str:
    return f"{text[: edit.start]}{edit.text}{text[edit.end :]}"


def _canonical(value: Any) -> str:
    """A parsed document as a string that tells ``1``, ``1.0`` and ``true`` apart, which
    python's ``==`` does not."""
    return json.dumps(value, ensure_ascii=False)


def _container(document: Any, pointer: str) -> tuple[Any, Any]:
    """Where an entry lives in the parsed document: its container, and its key or index."""
    path = segments(pointer)
    container = document
    for segment in path[:-1]:
        container = container[segment]
    return container, path[-1]


def _set_value(document: Any, pointer: str, value: Any) -> Any:
    if not pointer:
        return value
    container, last = _container(document, pointer)
    container[last] = value
    return document


def _removed_value(document: Any, pointer: str) -> Any:
    container, last = _container(document, pointer)
    del container[last]
    return document


def _inserted_value(document: Any, pointer: str, value: Any) -> Any:
    container, last = _container(document, pointer)
    container.insert(last, value)
    return document
