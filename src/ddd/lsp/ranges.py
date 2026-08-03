"""Where in the text a json pointer points.

DDD locates a finding at ``component.declarations[2].definition.unit`` rather than at a line,
and the reason is written down in the file formats documentation: a line number in a file that
is often generated or reformatted means very little, while the pointer is exactly where the
key sits whatever the formatting. An editor, though, draws on lines and columns, so somebody
has to bridge the two and it is this module.

The bridge is a second pass over the raw text, because the loader deliberately throws the
positions away: it hands the document to pydantic, which reports paths and not offsets. Rather
than thread offsets through the loader for the sake of one consumer, the text is scanned again
here, where the cost is one editor keystroke rather than every ``ddd check`` in every build.

Two behaviours are deliberate:

* **A member's span covers its key as well as its value.** Underlining ``"unit": "Hz"`` says
  which key is wrong; underlining ``"Hz"`` alone leaves the reader to look left.
* **A pointer that does not resolve falls back to its parent**, and so on up to the whole
  document. A finding shown slightly too high up is still a finding somebody can act on,
  where one dropped for lack of a span is a check that silently stopped running.
"""

from __future__ import annotations

import bisect
import json
import re
from pathlib import Path
from typing import Any, Final

_WHITESPACE: Final = " \t\n\r"
_LITERAL_END: Final = ",}] \t\n\r"


class Document:
    """One json document, and everything an editor needs to point into it.

    Built once per file per refresh: the scan and the line index are shared by every finding
    reported against that file, which is the difference between a linear pass and one per
    diagnostic.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self._line_starts = _line_starts(text)
        try:
            self.data: Any = json.loads(text)
        except ValueError:
            # Caught mid edit. There are no spans to offer and no values to read, which every
            # caller reads as "nothing here", rather than as an error of its own.
            self.data = None
            self._spans: dict[str, tuple[int, int]] = {}
            self._texts: dict[str, tuple[int, int]] = {}
            self._values: dict[str, tuple[int, int]] = {}
        else:
            # Scanned without a single defensive branch: a document that has already parsed
            # cannot surprise the scanner.
            scanner = _Scanner(text)
            scanner.value("")
            self._spans = scanner.spans
            self._texts = scanner.texts
            self._values = scanner.values

    def range_of(self, pointer: str) -> dict[str, Any]:
        """The range to underline for a finding located at ``pointer``."""
        span = self._resolve(pointer)
        if span is None:
            # Nothing resolved, which means the text is not json at all - a file caught mid
            # edit. The finding belongs to the file, so it goes at the top of it.
            return _range(_POSITION_ZERO, _POSITION_ZERO)
        start, end = span
        return _range(self._position(start), self._position(end))

    def pointer_at(self, position: dict[str, int]) -> str:
        """Which value the cursor is in, as the pointer DDD would name it.

        The inverse of :meth:`range_of`, and what turns "go to definition here" into a
        question about the document rather than about a column. The innermost span wins: a
        cursor inside ``"axis": "EngSpdAxis"`` is on the axis reference, not on the
        declaration that contains it.
        """
        offset = self._offset(position)
        containing = [
            (end - start, pointer)
            for pointer, (start, end) in self._spans.items()
            if start <= offset < end
        ]
        return min(containing)[1] if containing else ""

    def value_at(self, pointer: str) -> Any:
        """What is written at that pointer, already parsed, or ``None`` if nothing is.

        Indexing works the same way into an object and into an array, so one loop covers
        both. The guard is for pointers that were *built* rather than scanned - asking a
        declaration for its ``definition.name`` when the file is halfway through being
        written, and there is no definition yet.
        """
        value = self.data
        try:
            for segment in segments(pointer):
                value = value[segment]
        except (KeyError, IndexError, TypeError):
            return None
        return value

    def _offset(self, position: dict[str, int]) -> int:
        """Where a protocol position lands in the text, counting as the protocol counts."""
        line = min(position["line"], len(self._line_starts) - 1)
        offset = self._line_starts[line]
        remaining = position["character"]
        while remaining > 0 and offset < len(self.text) and self.text[offset] != "\n":
            remaining -= 1 if ord(self.text[offset]) < 0x10000 else 2
            offset += 1
        return offset

    def text_range_of(self, pointer: str) -> dict[str, Any] | None:
        """The range of a string's *contents*, inside the quotes, or nothing if it is not one.

        What an edit replaces. :meth:`range_of` covers the key as well, which is right for
        underlining a finding and wrong for rewriting a name: it would quote the quotes.
        """
        span = self._texts.get(pointer)
        if span is None:
            return None
        return _range(self._position(span[0]), self._position(span[1]))

    def raw_at(self, pointer: str) -> str | None:
        """The source text of a value, exactly as the author wrote it.

        Copied rather than re-serialised when a value is propagated to another declaration:
        ``{ "kind": "linear", "factor": 0.5 }`` arrives in the other file looking the way its
        author typed it, where ``json.dumps`` would arrive as a different four lines.
        """
        span = self._values.get(pointer)
        return None if span is None else self.text[span[0] : span[1]]

    def value_range_of(self, pointer: str) -> dict[str, Any] | None:
        """The range of a value alone, without the key in front of it."""
        span = self._values.get(pointer)
        if span is None:
            return None
        return _range(self._position(span[0]), self._position(span[1]))

    def _resolve(self, pointer: str) -> tuple[int, int] | None:
        """The span of the pointer, of its nearest documented ancestor, or nothing."""
        current = pointer
        while True:
            found = self._spans.get(current)
            if found is not None:
                return found
            if not current:
                return None
            current = _parent(current)

    def _position(self, offset: int) -> dict[str, int]:
        line = bisect.bisect_right(self._line_starts, offset) - 1
        # Characters are counted in utf-16 code units, which is what the protocol means by
        # "character" unless a client negotiates otherwise. A degree sign in a unit costs one
        # and an emoji in a description costs two, and getting it wrong shifts every
        # underline on the line.
        prefix = self.text[self._line_starts[line] : offset]
        return {"line": line, "character": len(prefix.encode("utf-16-le")) // 2}


_POSITION_ZERO: Final = {"line": 0, "character": 0}


def _range(start: dict[str, int], end: dict[str, int]) -> dict[str, Any]:
    return {"start": start, "end": end}


def _parent(pointer: str) -> str:
    """``a.b[2].c`` -> ``a.b[2]`` -> ``a.b`` -> ``a`` -> ``''``."""
    cut = max(pointer.rfind("."), pointer.rfind("["))
    return pointer[:cut] if cut > 0 else ""


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, character in enumerate(text) if character == "\n")
    return starts


_SEGMENT: Final = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


def segments(pointer: str) -> list[str | int]:
    """``a.b[2].c`` -> ``['a', 'b', 2, 'c']``, the way into a parsed document."""
    return [
        int(index) if index is not None else key
        for index, key in (match.group(1, 2) for match in _SEGMENT.finditer(pointer))
    ]


def read(path: Path, cache: dict[Path, Document]) -> Document:
    """The text of a file, read once however many times it is pointed into.

    A file that cannot be read is not an error here: it still has findings against it - "does
    not exist" is one of them - and an empty document answers every question with nothing.
    """
    found = cache.get(path)
    if found is None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        found = Document(text)
        cache[path] = found
    return found


class _Scanner:
    """A recursive descent walk over known-good json, recording where each value sits."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.spans: dict[str, tuple[int, int]] = {}
        self.texts: dict[str, tuple[int, int]] = {}
        """Where the characters of a string value sit, without the quotes around them."""
        self.values: dict[str, tuple[int, int]] = {}
        """Where a value sits, of whatever shape, without the key in front of it."""
        self._skip_whitespace()

    def value(self, pointer: str, start: int | None = None) -> None:
        begin = self.pos
        character = self.text[self.pos]
        if character == "{":
            self._object(pointer)
        elif character == "[":
            self._array(pointer)
        elif character == '"':
            self._string()
            # Between the quotes: begin is the opening one, pos is just past the closing one.
            self.texts[pointer] = (begin + 1, self.pos - 1)
        else:
            self._literal()
        self.spans[pointer] = (begin if start is None else start, self.pos)
        self.values[pointer] = (begin, self.pos)

    def _object(self, pointer: str) -> None:
        self.pos += 1
        self._skip_whitespace()
        if self.text[self.pos] == "}":
            self.pos += 1
            return
        while True:
            self._skip_whitespace()
            key_start = self.pos
            key = self._string()
            self._skip_whitespace()
            self.pos += 1  # the ':'
            self._skip_whitespace()
            # The key is part of the span, so that the underline says which key is meant.
            self.value(f"{pointer}.{key}" if pointer else key, key_start)
            self._skip_whitespace()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            self.pos += 1  # the '}'
            return

    def _array(self, pointer: str) -> None:
        self.pos += 1
        self._skip_whitespace()
        if self.text[self.pos] == "]":
            self.pos += 1
            return
        index = 0
        while True:
            self._skip_whitespace()
            self.value(f"{pointer}[{index}]")
            index += 1
            self._skip_whitespace()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            self.pos += 1  # the ']'
            return

    def _string(self) -> str:
        self.pos += 1  # the opening quote
        start = self.pos
        while self.text[self.pos] != '"':
            # A backslash consumes whatever follows it, so an escaped quote does not end the
            # string. Escapes are not decoded: a key DDD reports is a plain identifier, and
            # the offsets have to stay offsets into the raw text.
            self.pos += 2 if self.text[self.pos] == "\\" else 1
        text = self.text[start : self.pos]
        self.pos += 1  # the closing quote
        return text

    def _literal(self) -> None:
        """A number, ``true``, ``false`` or ``null``: everything up to what can follow one."""
        while self.text[self.pos] not in _LITERAL_END:
            self.pos += 1

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in _WHITESPACE:
            self.pos += 1
