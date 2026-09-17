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

import json
from dataclasses import dataclass, field
from typing import Any, Final

INVALID: Final = "invalid"
"""A pointer names nothing, an operation does not fit what it names, or a value is not json."""

UNREADABLE: Final = "unreadable"
"""The file is not valid json, so no pointer names a place in it."""

UNVERIFIED: Final = "unverified"
"""The edited text did not read back as the intended document."""

_WHITESPACE: Final = " \t\r\n"
_STRUCTURE: Final = "{}[]:,"
_OPENING: Final = ("{", "[")


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
