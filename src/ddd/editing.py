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
  like the member before it and ended like the line it follows. It goes after the last member -
  an id after the ``name`` it identifies, as ``ddd id`` has always written it (:data:`_FOLLOWS`).
* **Every edit is verified.** The operations are applied to the parsed document as well, and
  the edited text has to read back as exactly that document, or nothing is written.

:mod:`ddd.lsp.ranges` is imported inside the functions that scan a text rather than at the top:
importing it runs ``ddd.lsp``, which brings up the whole language server, and
:mod:`ddd.identity` - which the language server imports - takes its layout helpers from here.
"""

from __future__ import annotations

import codecs
import contextlib
import copy
import errno
import json
import os
import re
import secrets
import stat
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Final, NamedTuple

from ddd.file_names import STAGING_TOKEN_BYTES, staged_name, uncreatable
from ddd.loading import NESTED_TOO_DEEPLY, fingerprint, parse_json_text
from ddd.pointers import parent_pointer, segments

if TYPE_CHECKING:
    from ddd.lsp.ranges import Document

INVALID: Final = "invalid"
"""A pointer names nothing, an operation does not fit what it names, or a value is not json."""

UNREADABLE: Final = "unreadable"
"""The file is not valid json, so no pointer names a place in it."""

UNVERIFIED: Final = "unverified"
"""The edited text did not read back as the intended document."""

STALE: Final = "stale"
"""A file's fingerprint is not the one on disk: it changed since the edit was computed, or while
the edit was being written.

Answered only where nothing is left half made - ``ddd gui`` tells a person that nothing was
written, or put back, for it: a refusal that could not put every file it had written back is
:data:`UNWRITABLE` instead, whose sentence names the files it could not."""

UNWRITABLE: Final = "unwritable"
"""A file could not be written - it is read-only, which is refused before any file of the edit is
staged (:func:`_refuse_read_only`), or the disk refused it, and the ones already written were put
back where they could be - or could not be put back after the edit was refused as stale."""

REPLACE_TRIES: Final = 50 if os.name == "nt" else 1
"""How many times a file is renamed into place, or taken away, before a refusal stands.

Windows refuses both while another handle holds the file open, and ``ddd gui`` reads a
project's files on a thread of its own while an edit writes one: on CI's windows runners the
benchmark's own edits were refused ``[WinError 5] Access is denied`` renaming the staged file
into place, during an analysis reading that file, where a read lets go within milliseconds.
On posix neither waits on a reader, and a refusal is final at once."""

REPLACE_PAUSE: Final = 0.02
"""Seconds between two tries: fifty wait a second at most."""

STAGE_TRIES: Final = 16
"""How many names are drawn for a stage while each one drawn is taken - by a stage another writer
holds, or a killed process left - before the write is refused. Two draws alike are a matter of
chance, four random bytes each; sixteen taken in a row are the file system's doing, and would
have been drawn for for ever."""

SYNC_WORKERS: Final = 64
"""How many stages of one edit, or of one undo, are synced at once. A sync waits for the disk and
not for the processor, and a disk takes many at once: on a file system that journals, one sync
after the other cost milliseconds a file - seconds for an edit of hundreds of files, under the
session's lock - where syncs that overlap share the commits of the journal."""

_UNSYNCABLE: Final = frozenset({errno.EINVAL, errno.ENOTSUP})
"""What a file system that has no sync to offer answers one with - a network share, a virtual
file system: the write is made without it. Every other error is the disk's, and refuses it."""

_WRITE_PERMISSIONS: Final = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
"""Every permission to write a file. A file holding none of them is read-only to everyone, as a
file with windows' read-only flag is: python reports its mode as ``0444``."""

_WHITESPACE: Final = " \t\r\n"
_STRUCTURE: Final = "{}[]:,"
_OPENING: Final = ("{", "[")

_BREAK: Final = re.compile(r"[\r\n]")
"""A line break of any spelling: a character either of them is made of."""

_INK: Final = re.compile(r"\S")
"""A character that is not whitespace, as ``str.strip`` reads whitespace."""

DEFAULT_INDENT_UNIT: Final = "  "
"""The indentation unit of a file that nests nothing on a line of its own."""

_FOLLOWS: Final = {"id": "name"}
"""The member a new member is written after, by its key, where its object states that member: an
id goes right after the ``name`` it identifies, where ``ddd id`` has always written it and the
examples spell it. Any other member goes after the last (:func:`member_addition`).

Decided here, where a member's place is decided, rather than by each writer that gives an object
an id: ``ddd id`` and the fix ``ddd gui`` offers for ``missing-id`` set the same key, and a place
left to each of them showed in a file's diff which of the two had stamped it."""

_INDEXED: Final = re.compile(r"(.*)\[(\d+)\]")

_INDEX_DIGITS: Final = len(str(sys.maxsize))
"""The most digits an array index can need: no list holds more than ``sys.maxsize`` elements -
nineteen digits on a 64-bit python."""

_LONG_INDEX: Final = re.compile(rf"\[\d{{{_INDEX_DIGITS + 1},}}\]")
"""An index of more digits than any array needs, which names nothing - and which ``int()``
refuses with a plain ``ValueError`` past 4,300 digits."""


class EditError(ValueError):
    """An edit that cannot be made, carrying the code ``ddd gui`` answers it with."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_raw(raw: object) -> Any:
    """The value a json text stands for, refusing anything but exactly one json value.

    Read by the loader's own rule: ``NaN`` and ``Infinity`` are refused although python's parser
    accepts them, and so is an object spelling a key twice - the file the value is written into
    would be one ``ddd check`` refuses to read.
    """
    if not isinstance(raw, str):
        raise EditError(INVALID, "a value is given as json text")
    try:
        return parse_json_text(raw)
    except ValueError as error:
        raise not_one_value(raw, error) from None


def not_one_value(raw: str, why: object) -> EditError:
    """The refusal of ``raw`` as a value, saying ``why``: the words of every refusal
    :func:`parse_raw` makes, and of the ones ``ddd gui`` makes of a value in a query before
    parsing it (:func:`ddd.gui.queries.json_text`)."""
    return EditError(INVALID, f"{raw!r} is not one json value: {why}")


def newline_at(text: str, offset: int) -> str:
    """How the line ``offset`` sits on ends, so a line added after it ends the same way.

    All three spellings, found by whichever of ``\\r`` and ``\\n`` comes first. Looking for
    ``\\n`` alone answered "line feed" for a file written with bare carriage returns, which has
    none at all. Where no line break follows ``offset`` - the last member of a file whose last
    line has none - the last one before it is copied, the file's own ending; ``\\n`` is for a
    text with no line break at all.

    The carriage return is looked for no further than the line feed: in a file of line feeds
    alone the search for one went on to the end of the text, for every id ``ddd id`` gave it.
    """
    feed = text.find("\n", offset)
    carriage = text.find("\r", offset, len(text) if feed < 0 else feed)
    if carriage >= 0:
        return "\r\n" if carriage + 1 == feed else "\r"
    if feed >= 0:
        return "\n"
    feed = text.rfind("\n", 0, offset)
    carriage = text.rfind("\r", 0, offset)
    if carriage >= 0 and carriage + 1 == feed:
        return "\r\n"
    return "\r" if carriage > feed else "\n"


def indent_of_line_at(text: str, offset: int) -> str:
    """The leading whitespace of the line ``offset`` sits on, so a new line lines up with it.

    Whatever the file is indented with: a file written with tabs gets a tab, one written with
    four spaces gets four. A line is what a line feed, a carriage return or both end.
    """
    return _indentation(text, _line_start(text, offset))


def _line_start(text: str, offset: int) -> int:
    """Where the line ``offset`` sits on starts: just past the last line break before it, of
    whichever spelling - a ``\\r\\n`` ends in the ``\\n``, the later of the two. The carriage
    return is looked for no further back than the line feed, so that a file of line feeds alone
    is not searched to its start for each line asked about."""
    feed = text.rfind("\n", 0, offset)
    return max(feed, text.rfind("\r", feed + 1, offset)) + 1


def _indentation(text: str, start: int) -> str:
    """The whitespace ``text`` holds from ``start`` on, as ``str.lstrip`` strips it, read forward
    to the first character that is not whitespace. It was read by stripping it off the rest of
    the text, which copied all of that: for every id ``ddd id`` gave a file, and for every entry
    of a file written on one line looked at for its indentation unit (:func:`indent_unit`)."""
    ink = _INK.search(text, start)
    return text[start : len(text) if ink is None else ink.start()]


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

    A value nested deeper than the layout goes is refused as one too deep to read, the way the
    loader refuses a document deeper than python's parser goes (:func:`parse_raw`). The parser
    reads thousands of levels, where reading the tokens here spends a frame of python's stack a
    level and writing them out two: a value three thousand levels deep, sent to ``ddd gui`` as
    an edit's value, ended the request in a ``RecursionError``.
    """
    parse_raw(raw)
    try:
        node, _ = _parsed(_tokens(raw), 0)
        return _rendered(node, one_line=one_line, indent=indent, unit=unit, newline=newline)
    except RecursionError:
        raise not_one_value(raw, NESTED_TOO_DEEPLY) from None


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

    ``set`` writes ``raw`` at ``pointer``, adding the member when its object lacks it - after the
    last member, or an ``id`` after the ``name`` it identifies (:data:`_FOLLOWS`); ``remove``
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
    return _unit_below(document, "", _Lines(document.text)) or DEFAULT_INDENT_UNIT


def replacement(document: Document, pointer: str, raw: str) -> TextEdit:
    """The edit writing ``raw`` in place of the value at ``pointer``."""
    span = document.value_span_of(pointer) if _holds(document, pointer) else None
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
    """The edit adding ``key: raw`` to the object at ``pointer``, after its last member - or,
    for an ``id``, after the ``name`` the object states (:data:`_FOLLOWS`).

    ``verbatim`` writes ``raw`` exactly as given - a value copied out of another file the way
    its author wrote it - where otherwise it is laid out to fit.
    """
    members = document.value_at(pointer)
    if not isinstance(members, dict):
        raise EditError(INVALID, f"{_named(pointer)} is not an object")
    if key in members:
        raise EditError(INVALID, f"{_child(pointer, key)} is already written")
    prefix = f"{json.dumps(key, ensure_ascii=False)}: "
    after = _follows(key, members)
    return _added(document, pointer, prefix, raw, None, verbatim=verbatim, after=after)


def _follows(key: str, members: Mapping[str, Any]) -> str | None:
    """The member of ``members`` a new member ``key`` is written after, or ``None`` for after the
    last: the one :data:`_FOLLOWS` names for it, where the object states that."""
    after = _FOLLOWS.get(key)
    return after if after in members else None


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
    span = document.span_of(pointer) if pointer and _holds(document, pointer) else None
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
    """The text with every operation made in order, verified against the parsed document.

    Verified after every operation rather than once at the end, wherever one operation can
    depend on what another left. The next operation is checked against the text the last one
    left and made on the document that one was meant to leave, so the two have to be one document
    before it starts: when they were not, an operation that passed its checks on the text reached
    into the document for a value it did not hold.

    A batch none of whose operations can depend on another (:func:`_independent`) is made from
    the one reading instead, and the text it leaves is read once and compared as the text one
    operation leaves is. A unit is renamed by a set at every declaration stating it, hundreds of
    places in one component file of a large project, and ``ddd id`` gives every declaration of a
    file an id, thousands of members added to one file; the file was read again after each of
    them. One reading compares the whole document every operation was meant to leave, so an
    operation whose edit wrote what it was not meant to fails it as the reading after that
    operation would have. A batch made at once that is refused, or does not read back as the
    document it was meant to leave, is made again one operation at a time, which answers what it
    always has: the same text, or the same refusal.
    """
    unreadable = "the file is not json DDD reads, so no pointer names a place in it"
    document = _read(text, UNREADABLE, unreadable)
    if _independent(document, operations):
        made = _made_at_once(document, operations)
        if made is not None:
            return made
    return _made_in_turn(document, operations)


def _independent(document: Document, operations: Sequence[Operation]) -> bool:
    """Whether every operation can be tried on the text as it was read, none depending on what
    another one writes: each a ``set`` at a pointer spelled the way the scan spells one, which is
    no other operation's pointer and nests within none of them, to a value given as text that
    opens neither an object nor an array - a literal, or text that is no json at all and is
    refused when it is made. Each sets a value the document holds, or adds a member to an object
    that holds members already and is given no other one, under a pointer the scan recorded
    nothing at (:func:`_gaining`); and a batch that adds a member sets no literal in place of an
    object or an array.

    Anything else may depend on what another operation leaves. An ``insert`` or a ``remove``
    writes or takes a comma beside its neighbours, and in an array moves the elements after it to
    other indices; a ``move`` is both; and a set within a value another set replaces, and the same
    pointer set twice, answer otherwise in another order. An object or an array set in place of a
    value is laid out to fit the lines around it, in the indentation unit read off the first
    entry the file writes on a line of its own, which may be inside a value another set replaces.
    A literal is written as it is spelled, whatever lines are around it.

    A member added is laid out to fit the lines around it as well: on the line of an object
    written on one line, or on a line of its own indented like the line the member before it ends
    on, and ended like it. A literal set in place of another leaves every line as it was, and so
    does a member added to another object, which joins a line or splits one into two indented
    alike. A literal set in place of an object or an array can take lines away: replacing a value
    an object writes over several lines can put the object on one line, which a member added to
    it then joins. Two members added to one object are laid out one after the other, the second
    after the first; and the member added to an object holding none, in a container written over
    lines, goes on a line of its own indented by the file's unit, which is read off the first
    entry on a line of its own - a member added before it can be that entry.
    """
    pointers = {operation.pointer for operation in operations}
    if len(pointers) < len(operations):
        return False
    gaining: set[str] = set()
    replaces_a_container = False
    for operation in operations:
        if operation.op != "set" or not isinstance(operation.raw, str):
            return False
        if _structured(operation.raw) or not _spelled(operation.pointer):
            return False
        if _holds(document, operation.pointer):
            replaced = document.value_at(operation.pointer)
            replaces_a_container = replaces_a_container or isinstance(replaced, dict | list)
        else:
            gains = _gaining(document, operation.pointer)
            if gains is None or gains in gaining:
                return False
            gaining.add(gains)
        within = operation.pointer
        while within:
            within = parent_pointer(within)
            if within in pointers:
                return False
    return not (gaining and replaces_a_container)


def _gaining(document: Document, pointer: str) -> str | None:
    """The object a set at ``pointer`` adds a member to, where the pointer names a member that an
    object holding members already has not got, and no text the scan recorded; ``None`` for any
    other place the document holds nothing at - an element past the end of an array, a member of
    what is not an object, or of an object holding none.

    The scan records a member whose key holds a dot under the pointer the grammar reads it as,
    which may be the one a member added takes: ``{"b.c": 1, "b": {...}}`` records ``b.c``, and
    once ``b`` is given a ``c`` the pointer names that one, for every operation made after it -
    one at a time, and not at once."""
    if _indexed(pointer) is not None or document.span_of(pointer) is not None:
        return None
    parent = parent_pointer(pointer)
    members = document.value_at(parent)
    return parent if isinstance(members, dict) and members else None


def _made_at_once(document: Document, operations: Sequence[Operation]) -> str | None:
    """The operations made on the text as it was read, and the text they leave read once - or
    ``None`` when one of them is refused, or that text does not read back as the document every
    operation was meant to leave, for :func:`_made_in_turn` to answer as it answers any batch.

    Only for a batch :func:`_independent` lets through, each of whose edits is a literal as
    spelled, over where the value it replaces sits, or a member added to an object the way
    :func:`member_addition` adds one to the text as it was read - which no other edit of the batch
    changes where the member reads it. :func:`replacement` measures the lines around the value
    first, which a literal never reads, copying the text from the value's line to its end for
    every operation.
    """
    expected = copy.deepcopy(document.data)
    edits: list[TextEdit] = []
    try:
        for operation in operations:
            raw = _raw_of(operation)
            if _holds(document, operation.pointer):
                start, end = _span(document.value_span_of(operation.pointer))
                # A literal is the one token it is spelled as, so the layout given is never read.
                literal = lay_out(
                    raw, one_line=True, indent="", unit=DEFAULT_INDENT_UNIT, newline="\n"
                )
                edits.append(TextEdit(start, end, literal))
            else:
                edits.append(_set_edit(document, operation.pointer, raw))
            expected = _set_value(expected, operation.pointer, parse_raw(raw))
        made = _read(
            _all_applied(document.text, edits), UNVERIFIED, "an edit left the file unreadable"
        )
    except EditError:
        return None
    if _canonical(made.data) != _canonical(expected):
        return None
    return made.text


def _made_in_turn(document: Document, operations: Sequence[Operation]) -> str:
    """The operations made one after another, starting from the document as it was read, each
    verified before the next (:func:`edit_text`)."""
    text = document.text
    expected = copy.deepcopy(document.data)
    for operation in operations:
        text, expected = _made(document, operation, expected)
        document = _read(text, UNVERIFIED, "an edit left the file unreadable")
        if _canonical(document.data) != _canonical(expected):
            raise EditError(
                UNVERIFIED, "the edited file does not read back as the intended document"
            )
    return text


def _all_applied(text: str, edits: Sequence[TextEdit]) -> str:
    """The text with every edit made, each where the text as it stands puts it, none overlapping
    another: made from the last back, so that making one moves none of those before it, and
    joined once rather than copying the whole text for each."""
    pieces: list[str] = []
    end = len(text)
    for edit in sorted(edits, key=lambda edit: edit.start, reverse=True):
        pieces += (text[edit.end : end], edit.text)
        end = edit.start
    pieces.append(text[:end])
    return "".join(reversed(pieces))


def _read(text: str, code: str, refusal: str) -> Document:
    """The text scanned for where its values sit, or refused with ``code`` when DDD does not read
    it as json.

    Read by the loader's rule before it is scanned. The scan parses with python's own reader,
    which takes ``NaN`` and a key spelled twice, so a file ``ddd check`` refuses was edited as
    though it could be read, and an edit spelling a key twice read back as the document it was
    meant to be - the last spelling winning - and was written.
    """
    from ddd.lsp.ranges import Document

    try:
        parse_json_text(text)
    except ValueError as error:
        raise EditError(code, f"{refusal}: {error}") from None
    document = Document(text)
    if document.data is None:
        # Read by the parser and too deep for the scan, which spends more stack per level.
        raise EditError(code, f"{refusal}: the json is nested too deeply to read")
    return document


def _made(document: Document, operation: Operation, expected: Any) -> tuple[str, Any]:
    """One operation made on the text, and on the parsed document it has to read back as."""
    if not _spelled(operation.pointer):
        raise EditError(INVALID, f"{operation.pointer!r} is not a pointer")
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
    if _holds(document, pointer):
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
    after: str | None = None,
) -> TextEdit:
    """The edit putting ``prefix`` and ``raw`` into a container: before entry ``index``, or after
    the last entry - or, for an object's member that follows another (``after``), right after
    that one.

    The lines around the place are measured only where the layout reads them. An entry joining
    a container written on one line is laid out on that line, whatever the lines say, and only a
    value that opens an object or an array is laid out in the file's indentation unit, over lines
    of its own (:func:`_structured`). Measured for every entry, they cost ``ddd id`` a search of
    the rest of the file for each id it gave, and a file written on one line a look at every entry
    it holds for the unit, for each member added to it."""
    text = document.text
    start, end = _span(document.value_span_of(container))
    entries = _entries(document, container)
    if not entries:
        # Rewritten whole, holding its one entry, in the layout of the container around it.
        if _around_on_one_line(document, container):
            value = _value_on_one_line(raw, verbatim)
            inner = f" {prefix}{value} " if text[start] == "{" else f"{prefix}{value}"
            return TextEdit(start, end, f"{text[start]}{inner}{text[end - 1]}")
        base = indent_of_line_at(text, start)
        newline = newline_at(text, start)
        unit = indent_unit(document)
        deeper = base + unit
        value = _value(raw, verbatim, one_line=False, indent=deeper, unit=unit, newline=newline)
        whole = f"{text[start]}{newline}{deeper}{prefix}{value}{newline}{base}{text[end - 1]}"
        return TextEdit(start, end, whole)
    if index is None or index == len(entries):
        preceding = entries[-1] if after is None else _child(container, after)
        at = _span(document.span_of(preceding))[1]
    else:
        at = _span(document.span_of(entries[index]))[0]
    if _on_one_line(document, container):
        value = _value_on_one_line(raw, verbatim)
        separator = ", "
    else:
        indent = indent_of_line_at(text, at)
        newline = newline_at(text, at)
        unit = indent_unit(document) if _structured(raw) else DEFAULT_INDENT_UNIT
        value = _value(raw, verbatim, one_line=False, indent=indent, unit=unit, newline=newline)
        separator = f",{newline}{indent}"
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


def _value_on_one_line(raw: str, verbatim: bool) -> str:
    """``raw`` as an entry joining a line writes it: laid out on one line, which reads nothing of
    the lines around it - neither their indentation, nor how they end, nor the file's unit."""
    return _value(raw, verbatim, one_line=True, indent="", unit=DEFAULT_INDENT_UNIT, newline="\n")


def _structured(raw: str) -> bool:
    """Whether a value given as json text opens an object or an array: the only kind
    :func:`lay_out` can write over lines, a literal being the one token it is spelled as."""
    return raw.lstrip(_WHITESPACE)[:1] in _OPENING


def _entries(document: Document, pointer: str) -> list[str]:
    """The pointers of a container's entries, in the order the text writes them."""
    value = document.value_at(pointer)
    if isinstance(value, dict):
        for key in value:
            if not segments(key):
                raise EditError(
                    INVALID,
                    f"{_named(pointer)} has the key {json.dumps(key)}, which spells no pointer, "
                    "so no member of it can be told from another by one",
                )
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
    return _BREAK.search(document.text, start, end) is None


def _around_on_one_line(document: Document, pointer: str) -> bool:
    """Whether the container holding ``pointer`` is written on one line; the top of the file is
    measured as itself."""
    return _on_one_line(document, parent_pointer(pointer) if pointer else "")


def _unit_below(document: Document, pointer: str, lines: _Lines) -> str | None:
    """The unit :func:`indent_unit` reads off the first entry under ``pointer`` written on a line
    of its own - a line break between its container's opening and it - and indented deeper than
    the line its container opens on; ``None`` for a value holding no such entry. The entries are
    taken in the order the text writes them, each before the ones it holds, which is the order
    ``lines`` is asked about them in."""
    opening = _span(document.value_span_of(pointer))[0]
    outer = lines.indent_at(opening)
    for entry in _entries(document, pointer):
        start = _span(document.span_of(entry))[0]
        if lines.start_at(start) > opening:
            inner = lines.indent_at(start)
            if len(inner) > len(outer) and inner.startswith(outer):
                return inner[len(outer) :]
        found = _unit_below(document, entry, lines)
        if found is not None:
            return found
    return None


class _Lines:
    """Where the lines of a text start, and how each is indented, for offsets asked in the order
    the text writes them (:func:`_unit_below`): the text between two offsets is searched once for
    a line break, and a line's indentation read once, however many entries sit there.

    Each entry used to be asked for the line it sits on by searching back from it to the line's
    start, and for that line's indentation by copying the rest of the text: in a file written on
    one line, where no entry has a line of its own and every one is asked, the square of its size.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self._reached = 0
        self._start = 0
        """Where the line holding ``_reached`` starts."""
        self._indented = (-1, "")
        """The start of the line last asked for its indentation, and that indentation."""

    def start_at(self, offset: int) -> int:
        """Where the line ``offset`` sits on starts: just past the line break before it - a line
        feed, a carriage return or both - or at the start of the text.

        An offset before the last one asked starts the search again from the start of the text.
        Only a key holding a dot asks one: the scan records such a member under the pointer of
        the member nested in its neighbour that the pointer spells, and the walk goes from the one
        to the other and back (``tests/test_editing.py``)."""
        if offset < self._reached:
            self._reached = self._start = 0
        # A line feed or a carriage return, the later: a `\r\n` ends in the line feed.
        end = max(
            self._text.rfind("\n", self._reached, offset),
            self._text.rfind("\r", self._reached, offset),
        )
        if end >= 0:
            self._start = end + 1
        self._reached = offset
        return self._start

    def indent_at(self, offset: int) -> str:
        """The leading whitespace of the line ``offset`` sits on (:func:`indent_of_line_at`)."""
        start = self.start_at(offset)
        if self._indented[0] != start:
            self._indented = (start, _indentation(self._text, start))
        return self._indented[1]


def _holds(document: Document, pointer: str) -> bool:
    """Whether the parsed document has a value where ``pointer`` points.

    Asked of the parsed document, not of the scan. The scan records a member under its key as
    written, so a key holding a dot or a bracket - ``{"a.b": 1}`` - is recorded under a pointer
    the grammar reads as more steps than it is: the text has something under that spelling, and
    the document has nothing at the place it names, not even a parent to put it in.
    """
    parts = segments(pointer)
    if not parts:
        return True
    parent = document.value_at(parent_pointer(pointer))
    last = parts[-1]
    if isinstance(last, int):
        return isinstance(parent, list) and last < len(parent)
    return isinstance(parent, dict) and last in parent


def _spelled(pointer: str) -> bool:
    """Whether ``pointer`` is written the one way the scan writes a pointer to what it names.

    The grammar reads more spellings than that - ``a..b``, ``a[01]``, ``a]`` - and a pointer
    spelled one of those ways names nothing the scan recorded, while the helpers here take every
    pointer they are handed for one it did. Nor does a pointer whose index has more digits than
    any array can need (:data:`_INDEX_DIGITS`), and it is refused before the grammar reads the
    index: ``int()`` refuses one of more than 4,300 digits with a ``ValueError``, which
    ``ddd gui`` answered ``500``. Every caller asks this first - the check of whether a batch can
    be made at once as much as each operation's own.
    """
    if _LONG_INDEX.search(pointer):
        return False
    written = "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in segments(pointer)
    )
    return written.removeprefix(".") == pointer


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
    """The parsed document with ``value`` set at ``pointer``: replaced where it is, and added
    where it is not - in the place the text writes a member (:func:`member_addition`), because
    what an edit is verified against is a document as the text reads back, its members in the
    order it spells them."""
    if not pointer:
        return value
    container, last = _container(document, pointer)
    after = (
        _follows(last, container) if isinstance(container, dict) and last not in container else None
    )
    if after is None:
        container[last] = value
        return document
    members = list(container.items())
    container.clear()
    for key, held in members:
        container[key] = held
        if key == after:
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


@dataclass(frozen=True, slots=True)
class FileChange:
    """The operations for one file, and the fingerprint of the bytes they were computed for."""

    path: Path
    fingerprint: str | None
    """``None`` for a change that creates its file, which must not exist yet: one ``set`` of the
    whole document, at the pointer ``""``."""

    operations: tuple[Operation, ...]
    like: Path | None = None
    """The file a created file takes its mode from, and its owner and group where this process
    may give it them; a file that exists keeps its own, whatever this says."""


@dataclass(frozen=True, slots=True)
class Written:
    """One file an edit wrote: what it held before, and what it left.

    What an undo is made of. The previous bytes rather than the inverse operations: the file
    goes back to exactly what its author wrote, whatever the edit did to the layout around the
    value it changed, and a file the edit created is one that simply had no bytes at all.
    """

    path: Path

    before: bytes | None
    """The bytes the file held before the edit; ``None`` for a file the edit created."""

    fingerprint: str
    """The fingerprint of the bytes the edit left, which says whether it may still be put back:
    a file that has changed since is somebody else's now."""


@dataclass(frozen=True, slots=True)
class _Step:
    """One file of a write made all at once, an edit's or an undo's: the bytes to give it, the
    bytes it has to hold still for that, and the file whose access its stage takes."""

    path: Path

    data: bytes | None
    """What the file is given; ``None`` takes it away, which has no stage."""

    expected: bytes | None
    """What the file has to hold still, looked at once more right before it is given ``data`` or
    taken away: ``None`` for a file that is not there. What a rollback gives it back."""

    like: Path | None
    """The file whose access the stage takes: none, for the access any new file gets."""


class _Words(NamedTuple):
    """What the refusal of a write made all at once says - an edit's, or an undo's."""

    refused: str
    """Of a file the disk refused, in which ``{path}`` and ``{error}`` stand for it."""

    lost: str
    """Leads the files that could not be put back after it."""

    kept: str
    """Says that the files already written were put back."""


_WRITTEN: Final = _Words(
    "{path} could not be written ({error})",
    "these could not be put back: ",
    "the files already written were put back",
)
_PUT_BACK: Final = _Words(
    "{path} could not be put back",
    "these could not be written forward again: ",
    "the files already put back were written forward again",
)


def apply_changes(changes: Sequence[FileChange]) -> tuple[Written, ...]:
    """Make every change or none of them, and hand back what each file held before it and holds
    now.

    Every file is checked against its fingerprint and edited in memory before anything is
    written, and every file this process may not write - one kept read-only - is refused
    (:func:`_refuse_read_only`), so that a refusal of either kind leaves every file as it was
    and nothing staged. Every file is then staged beside it, under a name of its own, and the
    stages synced to the disk together, before any is renamed; each is then renamed onto its
    file, one after the other (:func:`_write_all`) - but only after that file is read once more,
    right before the rename, and found to hold still the bytes the edit was made from: a file
    saved since is somebody else's, which the rename would overwrite, and is refused as stale.
    When one fails or is refused, the files already written are written back from the bytes read
    before the edit - each one that still holds what the edit wrote - and a file the edit
    created is taken away again; a stage that cannot be made or synced refuses the edit before
    any file is renamed. A refusal as stale says that every one went back: where one could not,
    whatever refused the edit, the refusal is ``unwritable`` and names the files that could not.

    What an edit is made all at once against is a refusal, not a stop. A process killed while it
    writes - a closed terminal, a ``kill`` - has no refusal to put the files back with: it can
    leave the files it had renamed as the edit made them, the others as they were, and the
    stages it was writing beside their files; nothing records any of it. A power cut leaves each
    file as it was or as the edit made it, and not empty, on a journaling file system that has a
    sync to offer: the bytes of every stage are synced before it is renamed.
    """
    planned: list[tuple[FileChange, bytes | None, bytes]] = []
    for pending in changes:
        if any(done.path == pending.path for done, _, _ in planned):
            raise EditError(INVALID, f"{pending.path} is named twice in one edit")
        original, new = edited(pending)
        if original is not None:
            _refuse_read_only(pending.path, "written")
        planned.append((pending, original, new))
    _write_all(
        [
            _Step(pending.path, new, original, _access_of(pending, original))
            for pending, original, new in planned
        ],
        _WRITTEN,
    )
    return tuple(
        Written(pending.path, original, fingerprint(new)) for pending, original, new in planned
    )


def _write_all(steps: Sequence[_Step], words: _Words) -> None:
    """Write every file of an edit, or of an undo: stage them all, sync the stages together, and
    give each file its bytes - or take it away - one after the other. A file that cannot be
    written refuses the write (:func:`_refused`), and every stage that is not renamed is taken
    away.

    The stages are made one after the other, by this thread, which is what knows each of them; a
    file that is to be taken away has none. They are synced on up to :data:`SYNC_WORKERS`
    threads, a sync waiting for the disk. Each file is then renamed over, or taken away, in its
    turn - given the access of its file, and looking at that file once more right before
    (:func:`_replace`). The first that fails, in the order of the files, is the one the refusal
    names."""
    stages: dict[int, Path] = {}
    try:
        for index, step in enumerate(steps):
            if step.data is not None:
                try:
                    stages[index] = _stage(step.path, step.data, step.like)
                except OSError as error:
                    raise _refused(step.path, error, [], words) from None
        with ThreadPoolExecutor(SYNC_WORKERS) as pool:
            owners = list(stages)
            synced = 0
            try:
                for _ in pool.map(_sync, stages.values()):
                    synced += 1
            except OSError as error:
                raise _refused(steps[owners[synced]].path, error, [], words) from None
        done: list[tuple[Path, bytes | None, bytes | None]] = []
        for index, step in enumerate(steps):
            try:
                if step.data is None:
                    _put_back(step.path, None, step.expected)
                else:
                    _replace(step.path, stages[index], step.like, step.expected)
            except (OSError, EditError) as error:
                raise _refused(step.path, error, done, words) from None
            stages.pop(index, None)
            done.append((step.path, step.expected, step.data))
    finally:
        for stage in stages.values():
            _discard(stage)


def _refused(
    path: Path,
    error: OSError | EditError,
    done: Sequence[tuple[Path, bytes | None, bytes | None]],
    words: _Words,
) -> EditError:
    """The refusal of a write whose file ``path`` could not be written, for ``error``, after the
    files ``done`` already are put back (:func:`_not_put_back`): ``unwritable`` where one could
    not be, and then the sentence names it; else the code of the refusal that stopped the write,
    ``unwritable`` for an error of the disk."""
    lost = _not_put_back(done)
    outcome = words.lost + ", ".join(str(file) for file in lost) if lost else words.kept
    code = UNWRITABLE
    reason = words.refused.format(path=path, error=error)
    if isinstance(error, EditError):
        reason = str(error)
        if not lost:
            code = error.code
    return EditError(code, f"{reason}; {outcome}")


def _access_of(pending: FileChange, original: bytes | None) -> Path | None:
    """The file whose access the stage of a write takes: a file that exists keeps its own, and
    one the edit creates takes the access of the file it is like - or, like none, the access any
    new file gets."""
    return pending.path if original is not None else pending.like


def unchanged(entry: Written) -> bytes:
    """The file's bytes as the edit left them, refusing one that has changed since.

    What says whether an edit may still be put back: :func:`restore` checks every file with it
    before writing anything, and ``ddd gui`` reads the lines of its preview from what it
    answers.
    """
    try:
        current = entry.path.read_bytes()
    except OSError:
        raise EditError(STALE, f"{entry.path} can no longer be read") from None
    if fingerprint(current) != entry.fingerprint:
        raise EditError(STALE, f"{entry.path} changed on disk since it was written")
    return current


def restore(written: Sequence[Written]) -> None:
    """Put every file of an edit back where it was, or none of them.

    Every file is checked against the fingerprint the edit left it at, and for the permission to
    write it (:func:`_refuse_read_only`), before anything is written, so a refusal leaves every
    file as it stands. The previous versions are then written as an edit's files are: every file
    staged and every stage synced before any is renamed, each file looked at once more right
    before it is renamed over - or taken away, for a file the edit created
    (:func:`_write_all`) - and refused as stale if it was saved since that first check. When one
    cannot be written, or is refused, the files already put back are written forward to what
    the edit had left them, each one that still holds what was put back. A refusal as stale
    says that every one went forward again: where one could not, the refusal is ``unwritable``
    and names the files that could not.
    """
    ahead = [(entry, unchanged(entry)) for entry in written]
    for entry, _ in ahead:
        _refuse_read_only(entry.path, "put back")
    _write_all(
        [_Step(entry.path, entry.before, current, entry.path) for entry, current in ahead],
        _PUT_BACK,
    )


def edited(pending: FileChange) -> tuple[bytes | None, bytes]:
    """A file's bytes as they are, and as the change leaves them, made in memory and refused as
    :func:`apply_changes` refuses them; ``None`` for the bytes of a file the change creates.

    Public for a caller that has to know what an edit would write before it is made: ``ddd gui``
    lets an edit create a file only when its change of the project description includes that
    file, and asks this - rather than a reading of its own - what the description would say.
    """
    if pending.fingerprint is None:
        return None, _created(pending)
    try:
        original = pending.path.read_bytes()
    except OSError:
        raise EditError(STALE, f"{pending.path} can no longer be read") from None
    if fingerprint(original) != pending.fingerprint:
        raise EditError(STALE, f"{pending.path} changed on disk since it was read")
    mark = codecs.BOM_UTF8 if original.startswith(codecs.BOM_UTF8) else b""
    try:
        text = original[len(mark) :].decode("utf-8")
    except UnicodeDecodeError:
        raise EditError(UNREADABLE, f"{pending.path} is not utf-8") from None
    try:
        changed = edit_text(text, pending.operations)
    except EditError as refusal:
        raise EditError(refusal.code, f"{pending.path}: {refusal}") from None
    return original, mark + changed.encode("utf-8")


def _created(pending: FileChange) -> bytes:
    """The bytes of a file a change creates: its one ``set`` of the whole document, as given.

    As given, because there is no file yet whose layout an edit could follow - whoever plans the
    change lays the document out - and still read by the loader's rule first, so that no file
    ``ddd check`` would refuse to read is ever written. A name no file can be created under is
    refused next (:func:`uncreatable`), before the engine asks the file system anything about it.
    A file already there is somebody's, and the change was computed without it: refused as
    stale, whatever it holds.
    """
    only = pending.operations[0] if len(pending.operations) == 1 else None
    if only is None or (only.op, only.pointer) != ("set", "") or only.raw is None:
        raise EditError(
            INVALID, f"{pending.path} is created whole, by one set at the top of the file"
        )
    _read(only.raw, INVALID, f"{pending.path} would be created holding what DDD does not read")
    refused = uncreatable(pending.path.name)
    if refused is not None:
        raise EditError(INVALID, f"{pending.path} cannot be created: {refused}")
    if pending.path.exists():
        raise EditError(STALE, f"{pending.path} exists already")
    return only.raw.encode("utf-8")


def _refuse_read_only(path: Path, outcome: str) -> None:
    """Refuse a file this process may not write, before any file of the edit is staged. Two
    kinds are refused: a file kept read-only - nobody has the permission to write it, which
    stops even a process that may write anything, as root may - and one the system says this
    process may not write, as it does for a file of another user's or on a read-only mount.
    ``outcome`` is what was not done: ``written`` or ``put back``.

    Asked on every system. Windows refused the rename of a stage over a read-only file, after
    its second of tries, and left the stage behind; where a rename asks the permission of the
    folder and not of the file, a read-only checkout was written through, and kept read-only. A
    file that has gone since :func:`edited` read it is refused as stale, as there."""
    try:
        mode = path.stat().st_mode
    except OSError:
        raise EditError(STALE, f"{path} can no longer be read") from None
    if not mode & _WRITE_PERMISSIONS or not os.access(path, os.W_OK):
        raise EditError(UNWRITABLE, f"{path} is read-only, so nothing was {outcome}")


def _stage(path: Path, data: bytes, like: Path | None) -> Path:
    """Write ``data`` into a file staged beside ``path`` under a name of its own
    (:func:`_new_stage`), which takes the access of ``like`` once it is renamed
    (:func:`_replace`); answer it, closed. A stage whose write fails is taken away before the
    failure is raised."""
    staging, handle = _new_stage(path, like)
    try:
        with handle:
            handle.write(data)
    except OSError:
        _discard(staging)
        raise
    return staging


def _sync(staging: Path) -> None:
    """Sync the bytes of a stage to the disk, so that the rename that is to put them in place
    cannot reach the disk ahead of them: a power cut then leaves an empty file where there was a
    file. A write the disk reports failed only now - a full disk, a failing one - is refused
    like any other.

    The stage is opened again, having been closed when it was written - the stages of an edit
    are not all open at once - and tried again while the system refuses it access, as the rename
    is (:func:`_patiently`): Windows refuses to open for writing a file another handle holds, a
    scanner's with the file just closed, and lets go within milliseconds. A file system that
    has no sync to offer (:data:`_UNSYNCABLE`) is let by."""

    def synced() -> None:
        descriptor = os.open(staging, os.O_WRONLY | getattr(os, "O_BINARY", 0))
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in _UNSYNCABLE:
                raise
        finally:
            os.close(descriptor)

    _patiently(synced)


def _replace(path: Path, staging: Path, like: Path | None, expected: bytes | None) -> None:
    """Rename a stage over ``path``, once it has been given the access of ``like``.

    The file is read once more right before the rename (:func:`_unless_changed`): it has to
    hold ``expected`` still, the bytes the stage was made from - or not be there, for ``None``.
    The check made when the change was computed does not see a save that lands afterwards,
    while this and the other writes of the edit are made, and the rename would overwrite it. It
    is made once the stage is written and synced rather than before, so that the time the write
    itself takes is not left outside it. The stage is the caller's to take away if this fails."""
    if like is not None:
        _keep_access(like, staging)
    _patiently(_unless_changed(path, expected, lambda: staging.replace(path)))


def _stage_and_replace(path: Path, data: bytes, like: Path | None, expected: bytes | None) -> None:
    """Write ``data`` to ``path`` through a file staged beside it, synced, and renamed into
    place, one file at a time: the put-back of the files an edit had renamed, or the write
    forward of those an undo had put back (:func:`_put_back`) - when a write is refused, which is
    rare, so that its files are not staged together as a write's own are (:func:`_write_all`).
    A write that fails, or is refused, takes its own stage away (:func:`_discard`), and no
    other."""
    staging = _stage(path, data, like)
    try:
        _sync(staging)
        _replace(path, staging, like, expected)
    except (OSError, EditError):
        _discard(staging)
        raise


def _discard(staging: Path) -> None:
    """Take a stage away, made writable first: it took the access of a read-only file, and
    Windows refuses to delete a read-only file, so that each write refused beside one left its
    stage behind. A stage that is gone already, or that cannot be taken away, is left as it is:
    the refusal that brought the write here is the one to say."""
    with contextlib.suppress(OSError):
        staging.chmod(stat.S_IREAD | stat.S_IWRITE)
    with contextlib.suppress(OSError):
        staging.unlink()


def _unless_changed(
    path: Path, expected: bytes | None, act: Callable[[], object]
) -> Callable[[], None]:
    """``act``, a write onto ``path`` - the rename of a stage over it, or taking it away - made to
    look at the file once more first, every time it is tried.

    :func:`_patiently` tries it again where Windows refuses it access, a second after the first
    try at the most, and a save that lands between two tries is one the next would overwrite, or
    delete, unless the file is looked at again before that one too. Refused as stale where the
    file does not hold ``expected`` any more, ``None`` standing for no file at all: one somebody
    saved, took away or created since the bytes were read. A file that cannot be read is no more
    the bytes that were read than one that holds others."""

    def checked() -> None:
        if expected is None:
            holds = not path.exists()
        else:
            try:
                holds = path.read_bytes() == expected
            except OSError:
                holds = False
        if not holds:
            raise EditError(STALE, f"{path} changed on disk while it was being written")
        act()

    return checked


def _new_stage(path: Path, like: Path | None) -> tuple[Path, BinaryIO]:
    """A file created beside ``path`` and open for writing, under a name no other write holds:
    ``path``'s name, a dot, :data:`~ddd.file_names.STAGING_TOKEN_BYTES` random bytes in
    hexadecimal and the staging suffix (:func:`~ddd.file_names.staged_name`).

    The engine used to stage every write under one name, the file's and the suffix, so that two
    writers applying a change to one file at one instant wrote their bytes into the same stage,
    or took it away from under each other's rename - and on Windows the file was gone. The file
    is created only where nothing is: a stage another writer holds, or a killed process left, is
    never written over, its name is drawn again - :data:`STAGE_TRIES` times, and then the write
    is refused, ``FileExistsError`` - and what the failure of a write takes away is the stage it
    created itself.

    A stage that is to take the access of ``like`` (:func:`_keep_access`) is created for its
    owner alone, ``0600``, as :func:`tempfile.mkstemp` would create it: it holds a file's new
    bytes, which that file's own mode may keep from every other user, and they are not to be
    readable for as long as it takes to narrow it. A stage with no ``like`` is created as any
    new file is, with the access the umask leaves it - which is why :func:`tempfile.mkstemp` is
    not used: a file created like no file gets the access any new file gets
    (:func:`apply_changes`).
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    mode = 0o666 if like is None else 0o600
    for _ in range(STAGE_TRIES):
        staging = path.with_name(staged_name(path.name, secrets.token_hex(STAGING_TOKEN_BYTES)))
        try:
            descriptor = os.open(staging, flags, mode)
        except FileExistsError:
            continue
        return staging, os.fdopen(descriptor, "wb")
    raise FileExistsError(errno.EEXIST, "every name drawn for its stage is taken", str(path))


def _patiently(act: Callable[[], object]) -> None:
    """``act``, tried again while the system refuses it access, :data:`REPLACE_TRIES` times in
    all, :data:`REPLACE_PAUSE` apart; the last refusal is raised."""
    tries = REPLACE_TRIES
    while True:
        try:
            act()
            return
        except PermissionError:
            tries -= 1
            if tries == 0:
                raise
        time.sleep(REPLACE_PAUSE)


def _keep_access(original: Path, staged: Path) -> None:
    """Give the staged file the original's permissions, and its owner where this process may.

    A file written afresh takes this process's umask and user rather than the file's own. An
    edit made as root in a container, over a checkout mounted from the host, left the developer
    a file they could no longer save; one made to a file somebody kept read-only made it
    writable. Giving a file away is root's alone on a posix system and no notion at all on
    windows, so a refusal - or a system without ``chown`` - leaves the owner the write gave it.
    """
    status = original.stat()
    staged.chmod(stat.S_IMODE(status.st_mode))
    chown = getattr(os, "chown", None)
    if chown is not None:
        with contextlib.suppress(OSError):
            chown(staged, status.st_uid, status.st_gid)


def _put_back(path: Path, data: bytes | None, expected: bytes | None) -> None:
    """Give a file the bytes it held at some earlier point - written back, or the file taken
    away when it held none - provided it still holds ``expected``, the bytes it was left with,
    or ``None`` where it was left not there.

    Both directions of a rollback: the bytes a file held before an edit, and, for one an undo
    has already taken away when something else refuses, the bytes that edit had left. A file
    that is not there any more takes the access a new file gets, there being none of its own
    left to copy.

    Written back or taken away like any other write, which looks at the file once more right
    before (:func:`_unless_changed`): one saved since is somebody else's, and putting back
    what it held before would lose the save. Raises :class:`OSError` for a file that cannot be
    written, and the refusal :func:`_unless_changed` makes for one that was saved.
    """
    if data is None:
        _patiently(_unless_changed(path, expected, path.unlink))
    else:
        _stage_and_replace(path, data, path if path.exists() else None, expected)


def _not_put_back(steps: Sequence[tuple[Path, bytes | None, bytes | None]]) -> list[Path]:
    """Put back each of ``steps`` - a file, the bytes to give it, and the bytes it has to hold
    still for that (:func:`_put_back`) - and answer the files that could not be: written to and
    refused, or saved since. A file that cannot be put back never keeps the ones after it from
    being."""
    lost: list[Path] = []
    for path, data, expected in steps:
        try:
            _put_back(path, data, expected)
        except (OSError, EditError):
            lost.append(path)
    return lost
