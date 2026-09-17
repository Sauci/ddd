# Web GUI Milestone 1 (Walking Skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd gui` serves a browser page on the developer's PC that opens a project, lists its components with their findings, and changes a declaration's unit as a one-line edit of the description file, re-checked by the same engine as `ddd check`.

**Architecture:** A standard-library HTTP server (`src/ddd/gui/`) on 127.0.0.1 serves compiled React pages and a JSON API. A session holds the open project and numbers each analysis as a revision; the analysis is the language server's. Edits go through a new edit engine (`src/ddd/editing.py`) that changes only the text an operation touches, verifies the result by reading it back, and writes all files or none. The frontend (`gui/`) is compiled by Vite into `src/ddd/gui/static/`, which git ignores and the wheel carries.

**Tech Stack:** Python 3.12+ (stdlib `http.server`, `threading`, `hashlib`), pytest with the 100 % gate, ruff, mypy strict; Node 24, Vite 8.3.0, React 19.3.0, TypeScript 7.0.2, TanStack Query 5.103.1, Biome 2.5.14, Vitest 5.0.1, Playwright 1.63.0, json-schema-to-typescript 16.0.0.

**Spec:** `docs/superpowers/specs/2026-09-17-web-gui-design.md` (sections 4 to 6 are what this plan implements; read them before starting any task).

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip` anywhere (both are enforced by `tests/test_documentation.py`).
- The server binds `127.0.0.1` only. Token `secrets.token_urlsafe(32)`, cookie `ddd-gui` with `HttpOnly; SameSite=Strict; Path=/`. Accepted `Host`: `127.0.0.1:<port>` or `localhost:<port>`. Accepted `Origin` on POST: `http://127.0.0.1:<port>` or `http://localhost:<port>`, with `Content-Type: application/json`.
- Response headers on every response: `Content-Security-Policy` with `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; `Cache-Control: no-store` on the API.
- Poll interval 1 second; a waiting `GET /api/state?after=N` returns after at most 25 seconds.
- Fingerprints are the SHA-256 of a file's bytes, lowercase hex.
- Edit values are **raw JSON text**, never parsed values. Refusal codes: `stale`, `unreadable`, `invalid`, `unverified` (HTTP 409); `unwritable` (HTTP 500).
- Pointers are DDD's own spelling: `component.interface[3].definition.unit`.
- `ddd gui` exits 0 when interrupted, 2 on a usage error (not a project description, fixed port taken, no compiled pages). Its help strings contain no `*`, backtick or `|` (the generated reference is reStructuredText).
- `ddd gui` is labelled **preview** in its help, the README, SPEC.md, the command page and the changelog.
- Frontend: Node 24 (CI uses `node-version: "24"`, as the extension job does). Exact dependency versions as listed in Task 10. Vitest gate `thresholds: { 100: true }` over `src/api`, `src/lib`, `src/state`. Playwright runs Chromium on Ubuntu and Windows.
- Bundled JavaScript licences are limited to MIT, ISC, Apache-2.0, BSD-2-Clause, BSD-3-Clause.

## Prerequisites (before Task 1)

- The checkout's `.venv` exists with `pip install -e ".[dev]"` (see memory note on the local toolchain: run pytest from **Git Bash**, with `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH"`).
- **Node.js 24.15 or newer** installed on the machine for Tasks 10 to 13 (`node --version`). This machine had no Node on 2026-09-17: the maintainer installs it (for example `winget install OpenJS.NodeJS.LTS`) before Task 10 starts. Tasks 1 to 9 need no Node.
- Playwright on this machine drives the installed Edge (`PLAYWRIGHT_CHANNEL=msedge`), so no browser download is needed locally; CI installs Chromium.

## Conventions for every task

- Work on branch `feature/web-gui-skeleton`. Tests first: write the failing test, watch it fail, implement, watch it pass.
- One commit per task, message in the repository's style (a lowercase sentence saying what the change does), ending with the trailer `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Push after each task (`git push`).
- Before the task's commit, run the gate for what it touched. Before the last commit of the milestone (Task 14), run the whole gate, the documentation build included.
- Scratch files go to the session scratchpad, never into the repository.
- Record in the **Progress log** at the end of this plan the task's wall-clock duration and token count as the agent reports them; Task 14 turns them into the recalibration the spec asks for (section 6.13).

## File Structure

| File | Responsibility |
| --- | --- |
| `src/ddd/editing.py` (create) | The edit engine: raw values, layout, operations, verification, fingerprints, all-or-nothing writes |
| `src/ddd/lsp/ranges.py` (modify) | Public `Document.span_of` and `Document.position` |
| `src/ddd/identity.py` (modify) | Takes its line-ending and indentation helpers from the engine |
| `src/ddd/lsp/edits.py` (modify) | `_insert` and `_erase` become adapters over the engine |
| `src/ddd/lsp/diagnostics.py` (modify) | `Run`, `run_build`, `run_project`, public `group_findings` |
| `src/ddd/gui/__init__.py` (create) | Package docstring |
| `src/ddd/gui/session.py` (create) | Projects found, the open project, revisions, polling, reads and edits |
| `src/ddd/gui/api.py` (create) | JSON API: request in, `Reply` out |
| `src/ddd/gui/server.py` (create) | HTTP server, security, compiled pages, `run()` |
| `src/ddd/cli.py` (modify) | The `gui` subcommand |
| `tests/test_editing.py` (create) | Engine tests |
| `tests/test_gui_session.py`, `tests/test_gui_api.py`, `tests/test_gui_server.py` (create) | GUI Python tests |
| `tests/test_lsp.py`, `tests/test_cli.py`, `tests/test_documentation.py` (modify) | Runs, the command, the documentation rules |
| `gui/` (create) | Vite project: `package.json`, lock file, configs, `scripts/`, `src/`, `e2e/` |
| `README.md`, `SPEC.md`, `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst` (modify) | Documentation |
| `pyproject.toml`, `.gitignore`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/dependabot.yml` (modify) | Packaging and CI |

---

### Task 1: Raw values and their layout

The text-only half of the engine: reading a raw value, and writing one in the layout of the place it goes. Nothing here scans a document.

**Files:**
- Create: `src/ddd/editing.py`
- Test: `tests/test_editing.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `INVALID: Final = "invalid"`, `UNREADABLE: Final = "unreadable"`, `UNVERIFIED: Final = "unverified"`
  - `class EditError(ValueError)` with attribute `code: str`, constructed `EditError(code, message)`
  - `parse_raw(raw: object) -> Any`
  - `newline_at(text: str, offset: int) -> str`
  - `indent_of_line_at(text: str, offset: int) -> str`
  - `lay_out(raw: str, *, one_line: bool, indent: str, unit: str, newline: str) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_editing.py`:

```python
"""The edit engine: every change a description file is given, in the file's own layout."""

from __future__ import annotations

import pytest

from ddd.editing import (
    INVALID,
    EditError,
    indent_of_line_at,
    lay_out,
    newline_at,
    parse_raw,
)


class TestRawValues:
    @pytest.mark.parametrize(
        ("raw", "value"),
        [("1.0", 1.0), ('"rpm"', "rpm"), ("[1, 2]", [1, 2]), (" {} ", {}), ("null", None)],
    )
    def test_one_json_value_is_read(self, raw, value):
        assert parse_raw(raw) == value

    @pytest.mark.parametrize("raw", ["", "1 2", "NaN", "-Infinity", "{'a': 1}", "rpm"])
    def test_anything_else_is_refused_as_invalid(self, raw):
        with pytest.raises(EditError) as refused:
            parse_raw(raw)
        assert refused.value.code == INVALID

    def test_a_value_that_is_not_text_is_refused(self):
        with pytest.raises(EditError, match="json text") as refused:
            parse_raw(1)
        assert refused.value.code == INVALID


class TestLineEndingsAndIndentation:
    @pytest.mark.parametrize(
        ("text", "ending"),
        [
            ('{\r\n  "a": 1\r\n}', "\r\n"),
            ('{\r  "a": 1\r}', "\r"),
            ('{\n  "a": 1\n}', "\n"),
            ('{"a": 1}', "\n"),
            ('{\n "a": 1\r\n}', "\n"),
        ],
    )
    def test_a_new_line_ends_like_the_line_it_follows(self, text, ending):
        assert newline_at(text, 1) == ending

    @pytest.mark.parametrize(
        ("text", "offset", "indent"),
        [('{\n    "a": 1\n}', 8, "    "), ('{\n\t"a": 1\n}', 4, "\t"), ('{"a": 1}', 3, "")],
    )
    def test_the_indentation_is_the_one_of_the_line_the_offset_sits_on(
        self, text, offset, indent
    ):
        assert indent_of_line_at(text, offset) == indent


class TestLayingOutAValue:
    @staticmethod
    def layout(raw, *, one_line=False, indent="    ", unit="  ", newline="\n"):
        return lay_out(raw, one_line=one_line, indent=indent, unit=unit, newline=newline)

    @pytest.mark.parametrize("raw", ["1.0", "1e3", "-0", '"a\\"b"', '"a\\\\"', "true", "null"])
    def test_a_literal_keeps_its_spelling(self, raw):
        assert self.layout(f"  {raw} ") == raw

    def test_a_container_of_literals_goes_on_one_line(self):
        assert (
            self.layout('{"kind":"linear","factor":0.50}')
            == '{ "kind": "linear", "factor": 0.50 }'
        )
        assert self.layout("[1,\n 2.0]") == "[1, 2.0]"

    def test_an_empty_container_is_its_brackets(self):
        assert self.layout(" { } ") == "{}"
        assert self.layout("[ ]") == "[]"

    def test_a_container_of_containers_goes_one_entry_per_line(self):
        raw = (
            '{"scope":"input","definition":{"name":"A",'
            '"conversion":{"factor":1.0},"init":[0,1]}}'
        )
        assert self.layout(raw, newline="\r\n") == (
            "{\r\n"
            '      "scope": "input",\r\n'
            '      "definition": {\r\n'
            '        "name": "A",\r\n'
            '        "conversion": { "factor": 1.0 },\r\n'
            '        "init": [0, 1]\r\n'
            "      }\r\n"
            "    }"
        )

    def test_one_line_is_kept_when_asked_for_whatever_the_value_holds(self):
        assert (
            self.layout('{"a": {"b": [1, {"c": 2}]}}', one_line=True)
            == '{ "a": { "b": [1, { "c": 2 }] } }'
        )

    def test_a_key_keeps_its_spelling_escapes_included(self):
        assert self.layout('{"na\\u006de": 1}') == '{ "na\\u006de": 1 }'

    def test_a_value_that_is_not_json_is_refused_before_it_is_laid_out(self):
        with pytest.raises(EditError) as refused:
            self.layout("{")
        assert refused.value.code == INVALID
```

- [ ] **Step 2: Run the tests to watch them fail**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: collection error, `ModuleNotFoundError: No module named 'ddd.editing'`.

- [ ] **Step 3: Write the module**

Create `src/ddd/editing.py`:

```python
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
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: all pass.

- [ ] **Step 5: Check style and types**

Run: `python -m ruff format src/ddd/editing.py tests/test_editing.py`, then `python -m ruff check src/ddd/editing.py tests/test_editing.py` and `python -m mypy`
Expected: no findings. Let `ruff format` re-wrap any line past 100 characters.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/editing.py tests/test_editing.py
git commit -m "read a value as the json text it was given, and lay it out the way the file around it is written" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 2: Operations at a pointer, verified

The half of the engine that scans a document: `set`, `remove`, `insert` and `move` turned into text edits in the file's own layout, applied in order, and verified against the parsed document.

**Files:**
- Modify: `src/ddd/lsp/ranges.py` (add `Document.span_of`, next to `value_span_of`)
- Modify: `src/ddd/editing.py`
- Test: `tests/test_editing.py`

**Interfaces:**
- Consumes: Task 1's `EditError`, `INVALID`, `UNREADABLE`, `UNVERIFIED`, `parse_raw`, `lay_out`, `newline_at`, `indent_of_line_at`; `ddd.lsp.ranges.Document` (`value_at`, `value_span_of`, `raw_at`, `text`, `data`) and `ddd.lsp.ranges.segments`.
- Produces:
  - `Document.span_of(pointer: str) -> tuple[int, int] | None` (a member's key and value, or an element's value)
  - `@dataclass(frozen=True, slots=True) class TextEdit: start: int; end: int; text: str`
  - `@dataclass(frozen=True, slots=True) class Operation: op: str; pointer: str; raw: str | None = None; to: int | None = None`
  - `DEFAULT_INDENT_UNIT: Final = "  "`
  - `parent_pointer(pointer: str) -> str`
  - `indent_unit(document: Document) -> str`
  - `replacement(document: Document, pointer: str, raw: str) -> TextEdit`
  - `member_addition(document: Document, pointer: str, key: str, raw: str, *, verbatim: bool = False) -> TextEdit`
  - `removal(document: Document, pointer: str) -> TextEdit`
  - `insertion(document: Document, pointer: str, raw: str, *, verbatim: bool = False) -> TextEdit`
  - `edit_text(text: str, operations: Sequence[Operation]) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_editing.py` (and extend its import block with `UNREADABLE`, `UNVERIFIED`, `Operation`, `edit_text`, `indent_unit`, `member_addition`, plus `from ddd.lsp.ranges import Document` and `import ddd.editing as editing`):

```python
MULTI = (
    "{\n"
    '  "component": {\n'
    '    "name": "A",\n'
    '    "interface": [\n'
    "      {\n"
    '        "scope": "output",\n'
    '        "definition": { "name": "S", "kind": "measurement", "unit": "rpm", "factor": 1.0 }\n'
    "      }\n"
    "    ]\n"
    "  }\n"
    "}\n"
)
DEFINITION = "component.interface[0].definition"


def edited(text, *operations):
    return edit_text(text, operations)


class TestIndentationUnit:
    @pytest.mark.parametrize(
        ("text", "unit"),
        [
            ('{\n  "a": 1\n}', "  "),
            ('{\n    "a": {\n        "b": 1\n    }\n}', "    "),
            ('{\n\t"a": 1\n}', "\t"),
            ('{"a": {"b": 1}}', "  "),
            ('{\n"a": {\n   "b": 1}}', "   "),
        ],
    )
    def test_the_unit_is_read_off_the_first_entry_on_a_line_of_its_own(self, text, unit):
        assert indent_unit(Document(text)) == unit


class TestSet:
    def test_a_value_is_replaced_and_nothing_else_moves(self):
        assert edited(MULTI, Operation("set", f"{DEFINITION}.unit", '"Hz"')) == MULTI.replace(
            '"unit": "rpm"', '"unit": "Hz"'
        )

    def test_a_number_keeps_the_spelling_it_is_given(self):
        assert edited(MULTI, Operation("set", f"{DEFINITION}.factor", "2.50")) == MULTI.replace(
            '"factor": 1.0', '"factor": 2.50'
        )

    def test_a_member_joins_an_object_written_on_one_line_on_that_line(self):
        assert edited(MULTI, Operation("set", f"{DEFINITION}.volatile", "false")) == (
            MULTI.replace('"factor": 1.0 }', '"factor": 1.0, "volatile": false }')
        )

    def test_a_member_joins_an_object_written_one_per_line_on_a_line_of_its_own(self):
        assert edited(MULTI, Operation("set", "component.description", '"the pump"')) == (
            MULTI.replace('    ]\n  }\n}', '    ],\n    "description": "the pump"\n  }\n}')
        )

    def test_a_structured_value_is_laid_out_in_the_files_own_indentation(self):
        raw = '[{"name":"T","members":[{"name":"x","datatype":"uint8"}]}]'
        assert edited(MULTI, Operation("set", "component.types", raw)) == MULTI.replace(
            '    ]\n  }\n}',
            "    ],\n"
            '    "types": [\n'
            "      {\n"
            '        "name": "T",\n'
            '        "members": [\n'
            '          { "name": "x", "datatype": "uint8" }\n'
            "        ]\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "}",
        )

    def test_the_first_member_of_an_empty_object_takes_the_layout_around_it(self):
        assert edited('{"a": {}}', Operation("set", "a.k", '"v"')) == '{"a": { "k": "v" }}'

    def test_a_line_added_to_a_crlf_file_ends_with_crlf(self):
        assert edited('{\r\n  "a": 1\r\n}\r\n', Operation("set", "b", "2")) == (
            '{\r\n  "a": 1,\r\n  "b": 2\r\n}\r\n'
        )

    def test_a_key_written_with_an_escape_is_found_by_its_meaning(self):
        assert edited('{"na\\u006de": "A"}', Operation("set", "name", '"B"')) == (
            '{"na\\u006de": "B"}'
        )

    def test_the_whole_document_can_be_replaced(self):
        assert edited("[1]", Operation("set", "", "[2]")) == "[2]"

    def test_a_verbatim_member_keeps_the_text_it_was_copied_as(self):
        edit = member_addition(Document('{"a": 1}'), "", "c", '{ "kind":"linear" }', verbatim=True)
        assert edit.text == ', "c": { "kind":"linear" }'

    def test_a_member_that_is_already_written_is_not_added_again(self):
        with pytest.raises(EditError) as refused:
            member_addition(Document('{"a": 1}'), "", "a", "2")
        assert refused.value.code == INVALID


class TestRemove:
    def test_a_member_takes_the_comma_after_it(self):
        assert edited(MULTI, Operation("remove", "component.name")) == MULTI.replace(
            '    "name": "A",\n', ""
        )

    def test_the_last_element_takes_the_comma_before_it(self):
        assert edited('{"list": [1, 2, 3]}', Operation("remove", "list[2]")) == '{"list": [1, 2]}'

    def test_a_middle_element_takes_the_comma_after_it(self):
        assert edited('{"list": [1, 2, 3]}', Operation("remove", "list[1]")) == '{"list": [1, 3]}'

    def test_the_only_entry_leaves_its_brackets(self):
        assert edited('{"a": [7], "b": {"c": 1}}', Operation("remove", "a[0]")) == (
            '{"a": [], "b": {"c": 1}}'
        )


class TestInsert:
    ARRAY = '{\n  "includes": [\n    "a.ddd.json",\n    "b.ddd.json"\n  ]\n}\n'
    EMPTY = '{\n  "component": {\n    "name": "A",\n    "interface": []\n  }\n}\n'

    @pytest.mark.parametrize(
        ("pointer", "result"),
        [("list[0]", "[0, 1, 2, 3]"), ("list[2]", "[1, 2, 0, 3]"), ("list[3]", "[1, 2, 3, 0]")],
    )
    def test_an_element_goes_before_the_index_or_last(self, pointer, result):
        assert edited('{"list": [1, 2, 3]}', Operation("insert", pointer, "0")) == (
            f'{{"list": {result}}}'
        )

    def test_an_element_of_an_array_written_one_per_line_gets_a_line_of_its_own(self):
        assert edited(self.ARRAY, Operation("insert", "includes[1]", '"z.ddd.json"')) == (
            '{\n  "includes": [\n    "a.ddd.json",\n    "z.ddd.json",\n    "b.ddd.json"\n  ]\n}\n'
        )

    def test_the_first_declaration_of_an_empty_interface_is_laid_out_like_its_component(self):
        raw = '{"scope": "output", "definition": {"name": "S", "kind": "measurement"}}'
        assert edited(self.EMPTY, Operation("insert", "component.interface[0]", raw)) == (
            "{\n"
            '  "component": {\n'
            '    "name": "A",\n'
            '    "interface": [\n'
            "      {\n"
            '        "scope": "output",\n'
            '        "definition": { "name": "S", "kind": "measurement" }\n'
            "      }\n"
            "    ]\n"
            "  }\n"
            "}\n"
        )

    def test_an_element_of_an_empty_array_written_on_one_line_stays_on_it(self):
        assert edited('{"a": {"b": []}}', Operation("insert", "a.b[0]", "1")) == (
            '{"a": {"b": [1]}}'
        )


class TestMove:
    ARRAY = '{\n  "includes": [\n    "a",\n    "b",\n    "c"\n  ]\n}\n'

    def test_an_element_moves_forward(self):
        assert edited(self.ARRAY, Operation("move", "includes[0]", to=2)) == (
            '{\n  "includes": [\n    "b",\n    "c",\n    "a"\n  ]\n}\n'
        )

    def test_an_element_moves_backward(self):
        assert edited(self.ARRAY, Operation("move", "includes[2]", to=0)) == (
            '{\n  "includes": [\n    "c",\n    "a",\n    "b"\n  ]\n}\n'
        )

    def test_an_element_moved_to_where_it_is_changes_nothing(self):
        assert edited(self.ARRAY, Operation("move", "includes[1]", to=1)) == self.ARRAY

    def test_a_moved_element_keeps_its_own_text(self):
        text = '{"list": [{ "a":1 }, 2]}'
        assert edited(text, Operation("move", "list[0]", to=1)) == '{"list": [2, { "a":1 }]}'


class TestRefusals:
    def test_a_file_that_is_not_json_is_unreadable(self):
        with pytest.raises(EditError) as refused:
            edited("{", Operation("set", "a", "1"))
        assert refused.value.code == UNREADABLE

    @pytest.mark.parametrize(
        "operation",
        [
            Operation("rename", "a"),
            Operation("set", "a"),
            Operation("set", "a", "{"),
            Operation("set", "list[5]", "1"),
            Operation("set", "a.b", "1"),
            Operation("remove", "missing"),
            Operation("remove", ""),
            Operation("insert", "a", "1"),
            Operation("insert", "a[0]", "1"),
            Operation("insert", "list[3]", "1"),
            Operation("move", "a", to=0),
            Operation("move", "list[0]"),
            Operation("move", "list[0]", to=True),
            Operation("move", "list[5]", to=0),
            Operation("move", "list[0]", to=2),
        ],
    )
    def test_an_operation_that_does_not_fit_is_invalid(self, operation):
        with pytest.raises(EditError) as refused:
            edited('{"a": 1, "list": [1, 2]}', operation)
        assert refused.value.code == INVALID

    def test_operations_apply_in_order_each_to_the_text_the_last_one_left(self):
        assert edited(
            '{"list": [1, 2]}',
            Operation("insert", "list[0]", "0"),
            Operation("set", "list[2]", "5"),
        ) == '{"list": [0, 1, 5]}'

    def test_an_edit_that_reads_back_differently_is_unverified(self, monkeypatch):
        monkeypatch.setattr(editing, "lay_out", lambda raw, **layout: "2")
        with pytest.raises(EditError) as refused:
            edited('{"a": 1}', Operation("set", "a", "3"))
        assert refused.value.code == UNVERIFIED

    def test_an_edit_that_leaves_the_file_unreadable_is_unverified(self, monkeypatch):
        monkeypatch.setattr(editing, "lay_out", lambda raw, **layout: "{")
        with pytest.raises(EditError) as refused:
            edited('{"a": 1}', Operation("set", "a", "3"))
        assert refused.value.code == UNVERIFIED

    def test_the_next_operation_is_not_made_on_an_unreadable_text(self, monkeypatch):
        monkeypatch.setattr(editing, "lay_out", lambda raw, **layout: "{")
        with pytest.raises(EditError) as refused:
            edited('{"a": 1}', Operation("set", "a", "3"), Operation("set", "a", "4"))
        assert refused.value.code == UNVERIFIED
```

- [ ] **Step 2: Run the tests to watch them fail**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: collection error, `ImportError: cannot import name 'Operation' from 'ddd.editing'`.

- [ ] **Step 3: Add `Document.span_of`**

In `src/ddd/lsp/ranges.py`, directly after the `value_span_of` method of `Document`, add:

```python
    def span_of(self, pointer: str) -> tuple[int, int] | None:
        """Where an entry sits in the text, as offsets: a member's key and value together, or an
        element's value.

        What an edit that removes or moves an entry cuts along. :meth:`value_span_of` leaves a
        member's key out, which is right for replacing its value and wrong for taking the member
        away.
        """
        return self._spans.get(pointer)
```

- [ ] **Step 4: Add the operations to the engine**

In `src/ddd/editing.py`, extend the imports to:

```python
from __future__ import annotations

import copy
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from ddd.lsp.ranges import Document
```

add these constants beside `_OPENING`:

```python
DEFAULT_INDENT_UNIT: Final = "  "
"""The indentation unit of a file that nests nothing on a line of its own."""

_INDEXED: Final = re.compile(r"(.*)\[(\d+)\]")
```

and append to the end of the module:

```python
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


def parent_pointer(pointer: str) -> str:
    """``a.b[2].c`` -> ``a.b[2]`` -> ``a.b`` -> ``a`` -> ``''``."""
    cut = max(pointer.rfind("."), pointer.rfind("["))
    return pointer[:cut] if cut > 0 else ""


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
    from ddd.lsp.ranges import segments

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
```

- [ ] **Step 5: Run the tests to watch them pass**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: all pass. If an exact-text expectation fails, print the result (`print(repr(...))`) and compare it with the layout rules of the spec (section 6.6) before changing either side: the test states the rule.

- [ ] **Step 6: Check coverage of the module, style and types**

Run: `python -m pytest tests/test_editing.py --cov=ddd.editing --cov-branch --cov-report=term-missing --cov-fail-under=0`
Expected: `ddd/editing.py` at 100 % lines and branches. A missing line means a test is missing; add it rather than exempting the line.
Then: `python -m ruff format src tests`, `python -m ruff check .`, `python -m mypy`.

- [ ] **Step 7: Commit and push**

```bash
git add src/ddd/editing.py src/ddd/lsp/ranges.py tests/test_editing.py
git commit -m "turn a change at a pointer into an edit of the text in the file's own layout, and verify it reads back" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 3: One implementation of the layout rules

The language server's quick fixes and `ddd id --assign` each keep a private copy of the layout rules the engine now owns. Both move onto the engine; every existing test of both stays unchanged and has to pass.

**Files:**
- Modify: `src/ddd/lsp/ranges.py` (rename `Document._position` to the public `Document.position`)
- Modify: `src/ddd/identity.py` (delete `_newline_at` and `_indent_of_line_at`; use the engine's)
- Modify: `src/ddd/lsp/edits.py` (`_insert` and `_erase` become adapters over the engine)
- Test: `tests/test_lsp.py` (one new test for `Document.position`; nothing else changes)

**Interfaces:**
- Consumes: Task 1's `newline_at`, `indent_of_line_at`; Task 2's `TextEdit`, `member_addition`, `removal`, `Document.span_of`.
- Produces: `Document.position(offset: int) -> dict[str, int]` (a protocol position counted in UTF-16 code units, as `_position` did). `_insert` and `_erase` keep their names, signatures and return values: tests import them directly.

- [ ] **Step 1: Write the failing test**

In `tests/test_lsp.py`, inside `class TestPositions`, add:

```python
    def test_an_offset_becomes_the_position_the_protocol_counts(self) -> None:
        """Public because the edit engine hands out offsets and the quick fixes send positions."""
        document = Document('{\n  "unit": "°C 😀",\n  "a": 1\n}')
        offset = document.text.index('"a"')
        assert document.position(offset) == {"line": 2, "character": 2}
        after_emoji = document.text.index('",\n  "a"')
        assert document.position(after_emoji)["character"] == len('  "unit": "°C 😀') + 1
```

(`😀` counts two UTF-16 code units, which is why the expected character is one more than the Python length.)

- [ ] **Step 2: Run it to watch it fail**

Run: `python -m pytest tests/test_lsp.py -k "an_offset_becomes" --no-cov`
Expected: FAIL with `AttributeError: 'Document' object has no attribute 'position'`.

- [ ] **Step 3: Make `position` public**

In `src/ddd/lsp/ranges.py` rename the method `_position` to `position`, give it this docstring, and replace the three calls `self._position(` with `self.position(`:

```python
    def position(self, offset: int) -> dict[str, int]:
        """Where an offset into the text is, as the protocol counts: a line, and a character
        counted in utf-16 code units.

        Public for the quick fixes, which compute their edits as offsets through
        :mod:`ddd.editing` and send them as ranges.
        """
```

Keep the body (and its comment about utf-16) exactly as it was.

- [ ] **Step 4: Run the new test and the whole language server suite**

Run: `python -m pytest tests/test_lsp.py --no-cov`
Expected: all pass (the one symlink-privilege test this machine cannot run is the known exception, per the local toolchain note).

- [ ] **Step 5: Move `ddd id` onto the engine's helpers**

In `src/ddd/identity.py`:
- delete the functions `_newline_at` and `_indent_of_line_at`;
- add to the imports: `from ddd.editing import indent_of_line_at, newline_at`;
- in `insertions`, replace the two calls:

```python
            indent = indent_of_line_at(document.text, span[1])
            newline = newline_at(document.text, span[1])
```

`ddd.editing` imports nothing from `ddd.lsp` at module level, so this adds no import cycle: `ddd.lsp.edits` imports `ddd.identity`, which now imports `ddd.editing`, which imports `ddd.lsp.ranges` only inside the functions that scan.

- [ ] **Step 6: Move the quick fixes onto the engine**

In `src/ddd/lsp/edits.py`, add to the imports:

```python
from ddd.editing import TextEdit, member_addition, removal
```

Replace the body of `_erase` (keep its docstring) with:

```python
    members = document.value_at(definition)
    if not isinstance(members, dict) or key not in members or len(members) == 1:
        return None
    return _protocol_edit(document, removal(document, f"{definition}.{key}"))
```

Replace the body of `_insert` (keep its docstring) with:

```python
    members = document.value_at(definition)
    if not isinstance(members, dict) or not members:
        return None
    return _protocol_edit(document, member_addition(document, definition, key, raw, verbatim=True))
```

and add after `_insert`:

```python
def _protocol_edit(document: Document, edit: TextEdit) -> dict[str, Any]:
    """An edit the engine computed as offsets, as the protocol carries it: a range and a text."""
    return {
        "range": {"start": document.position(edit.start), "end": document.position(edit.end)},
        "newText": edit.text,
    }
```

Add one sentence to the `_erase` docstring's second paragraph so it stays true: "The cutting itself is :func:`ddd.editing.removal`'s, which the GUI's edits share; the refusal of an only child stays here, a decision about what a quick fix offers." Do the same for `_insert`: "Where the key goes and how it is separated is :func:`ddd.editing.member_addition`'s; the value travels verbatim, as the author of the other declaration wrote it."

`verbatim=True` is what keeps "the value is copied as source text, never re-serialised" true: the engine's layout would otherwise re-indent a multi-line value.

- [ ] **Step 7: Run everything the two modules touch**

Run: `python -m pytest tests/test_lsp.py tests/test_cli.py tests/test_editing.py tests/test_hardening.py --no-cov`
Expected: all pass, unchanged. In particular `test_the_indentation_is_the_one_of_the_line_positions_count` (NEL and U+2028 in the description) and the duplicate-key `_erase` test. If one fails, the engine's rule and the old helper disagree on that case: fix the engine (and add the case to `tests/test_editing.py`), never the old test.

- [ ] **Step 8: Full Python gate for the touched modules**

Run (Git Bash, with the PATH from the prerequisites): `python -m pytest`, then `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`
Expected: all green, coverage 100 %.

- [ ] **Step 9: Commit and push**

```bash
git add src/ddd/lsp/ranges.py src/ddd/identity.py src/ddd/lsp/edits.py tests/test_lsp.py
git commit -m "give the quick fixes and ddd id the engine's layout rules instead of copies of their own" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 4: Writing every file of an edit, or none

**Files:**
- Modify: `src/ddd/editing.py`
- Test: `tests/test_editing.py`

**Interfaces:**
- Consumes: Task 2's `Operation`, `edit_text`, `EditError`, `INVALID`, `UNREADABLE`.
- Produces:
  - `STALE: Final = "stale"`, `UNWRITABLE: Final = "unwritable"`, `STAGING_SUFFIX: Final = ".ddd-staging"`
  - `@dataclass(frozen=True, slots=True) class FileChange: path: Path; fingerprint: str; operations: tuple[Operation, ...]`
  - `fingerprint(data: bytes) -> str`
  - `apply_changes(changes: Sequence[FileChange]) -> dict[Path, str]` (path to its new fingerprint)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_editing.py` (imports: `codecs`, `from pathlib import Path`, and from `ddd.editing`: `STAGING_SUFFIX`, `STALE`, `UNWRITABLE`, `FileChange`, `apply_changes`, `fingerprint`; plus `from ddd.backends.base import STAGING_SUFFIX as ARTEFACT_STAGING_SUFFIX`):

```python
def change(path: Path, *operations: Operation) -> FileChange:
    return FileChange(path, fingerprint(path.read_bytes()), operations)


class TestWritingFiles:
    def test_every_file_is_written_and_its_new_fingerprint_handed_back(self, tmp_path):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"unit": "rpm"}')
        b.write_bytes(b'{"unit": "Hz"}')
        written = apply_changes(
            [change(a, Operation("set", "unit", '"V"')), change(b, Operation("set", "unit", '"A"'))]
        )
        assert a.read_bytes() == b'{"unit": "V"}'
        assert b.read_bytes() == b'{"unit": "A"}'
        assert written == {a: fingerprint(b'{"unit": "V"}'), b: fingerprint(b'{"unit": "A"}')}
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    def test_a_byte_order_mark_and_crlf_line_endings_survive(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(codecs.BOM_UTF8 + b'{\r\n  "a": 1\r\n}\r\n')
        apply_changes([change(path, Operation("set", "b", "2"))])
        assert path.read_bytes() == codecs.BOM_UTF8 + b'{\r\n  "a": 1,\r\n  "b": 2\r\n}\r\n'

    def test_a_file_changed_since_it_was_read_is_stale_and_nothing_is_written(self, tmp_path):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        changes = [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        b.write_bytes(b'{"x": 9}')
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == STALE
        assert a.read_bytes() == b'{"x": 1}'

    def test_a_file_that_vanished_is_stale(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b"{}")
        pending = change(path, Operation("set", "x", "1"))
        path.unlink()
        with pytest.raises(EditError) as refused:
            apply_changes([pending])
        assert refused.value.code == STALE

    def test_a_file_named_twice_is_invalid(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b"{}")
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "1"))] * 2)
        assert refused.value.code == INVALID

    def test_a_file_that_is_not_utf8_is_unreadable(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": "\xff"}')
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "a", "1"))])
        assert refused.value.code == UNREADABLE

    def test_a_refused_operation_names_its_file(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b"{}")
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("remove", "missing"))])
        assert refused.value.code == INVALID
        assert str(refused.value).startswith(str(path))

    def test_a_failed_write_puts_back_the_files_already_written(self, tmp_path, monkeypatch):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        real = editing._stage_and_replace

        def failing(path, data):
            if path == b:
                raise OSError("disk full")
            real(path, data)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
        with pytest.raises(EditError) as refused:
            apply_changes([change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert "put back" in str(refused.value)
        assert a.read_bytes() == b'{"x": 1}'

    def test_a_file_that_cannot_be_put_back_is_named(self, tmp_path, monkeypatch):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        real = editing._stage_and_replace
        calls = []

        def failing(path, data):
            calls.append(path)
            if path == b or calls.count(a) > 1:
                raise OSError("disk full")
            real(path, data)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
        with pytest.raises(EditError) as refused:
            apply_changes([change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert f"could not be put back: {a}" in str(refused.value)

    def test_a_write_that_fails_leaves_no_staging_file(self, tmp_path, monkeypatch):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b"{}")

        def refuse(self, target):
            raise OSError("held open by an editor")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(EditError):
            apply_changes([change(path, Operation("set", "x", "1"))])
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    def test_edits_stage_under_the_name_every_other_writer_stages_under(self):
        assert STAGING_SUFFIX == ARTEFACT_STAGING_SUFFIX
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: collection error, `ImportError: cannot import name 'STAGING_SUFFIX'`.

- [ ] **Step 3: Write the implementation**

In `src/ddd/editing.py` add `import codecs`, `import contextlib`, `import hashlib` and `from pathlib import Path` to the imports, these constants beside `UNVERIFIED`:

```python
STALE: Final = "stale"
"""A file's fingerprint is not the one on disk: it changed since the edit was computed."""

UNWRITABLE: Final = "unwritable"
"""A file could not be written; the ones already written were put back where they could be."""

STAGING_SUFFIX: Final = ".ddd-staging"
"""What a file's new bytes are staged under beside it: the name ``ddd id`` and the artefact
writer stage under, which no project gives a file of its own."""
```

and append to the module:

```python
@dataclass(frozen=True, slots=True)
class FileChange:
    """The operations for one file, and the fingerprint of the bytes they were computed for."""

    path: Path
    fingerprint: str
    operations: tuple[Operation, ...]


def fingerprint(data: bytes) -> str:
    """What says whether a file changed since it was read: the SHA-256 of its bytes, in hex."""
    return hashlib.sha256(data).hexdigest()


def apply_changes(changes: Sequence[FileChange]) -> dict[Path, str]:
    """Make every change or none of them, and hand back each file's new fingerprint.

    Every file is checked against its fingerprint and edited in memory before anything is
    written, so a refusal leaves every file as it was. Each write is staged beside its file and
    renamed onto it; when one fails, the files already written are written back from the bytes
    read before the edit, and the refusal names any that could not be.
    """
    staged: list[tuple[Path, bytes, bytes]] = []
    for pending in changes:
        if any(path == pending.path for path, _, _ in staged):
            raise EditError(INVALID, f"{pending.path} is named twice in one edit")
        original, new = _edited(pending)
        staged.append((pending.path, original, new))
    written: list[tuple[Path, bytes]] = []
    for path, original, new in staged:
        try:
            _stage_and_replace(path, new)
        except OSError as error:
            lost = [done for done, before in written if not _put_back(done, before)]
            outcome = (
                "these could not be put back: " + ", ".join(str(done) for done in lost)
                if lost
                else "the files already written were put back"
            )
            raise EditError(UNWRITABLE, f"{path} could not be written ({error}); {outcome}") from None
        written.append((path, original))
    return {path: fingerprint(new) for path, _, new in staged}


def _edited(pending: FileChange) -> tuple[bytes, bytes]:
    """A file's bytes as they are, and as the change leaves them."""
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
        edited = edit_text(text, pending.operations)
    except EditError as refusal:
        raise EditError(refusal.code, f"{pending.path}: {refusal}") from None
    return original, mark + edited.encode("utf-8")


def _stage_and_replace(path: Path, data: bytes) -> None:
    staging = path.with_name(path.name + STAGING_SUFFIX)
    try:
        staging.write_bytes(data)
        staging.replace(path)
    except OSError:
        with contextlib.suppress(OSError):
            staging.unlink()
        raise


def _put_back(path: Path, data: bytes) -> bool:
    try:
        _stage_and_replace(path, data)
    except OSError:
        return False
    return True
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_editing.py --no-cov`
Expected: all pass.

- [ ] **Step 5: Coverage, style, types**

Run: `python -m pytest tests/test_editing.py --cov=ddd.editing --cov-branch --cov-report=term-missing --cov-fail-under=0`, then `python -m ruff format src tests`, `python -m ruff check .`, `python -m mypy`
Expected: `ddd/editing.py` at 100 %, no findings.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/editing.py tests/test_editing.py
git commit -m "write every file of an edit or none, refusing a file that changed since it was read" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 5: Analysis runs the GUI can read

The language server discards two things the GUI needs: the dictionary an analysis resolved to, and a public way to file findings on both sides of a disagreement. This task keeps both, without changing anything the language server does.

**Files:**
- Modify: `src/ddd/lsp/diagnostics.py`
- Modify: `tests/test_lsp.py` (the one reference to `service._group`, and a new `TestRuns` class)

**Interfaces:**
- Consumes: `ddd.analysis.analyze` (returns `DataDictionary`), `ddd.ir.DataDictionary`, the module's existing `_run`, `_group`, `analyse`, `analyse_standalone`, `_analyse_root`.
- Produces:
  - `@dataclass(frozen=True, slots=True) class Run: bag: DiagnosticBag; covered: frozenset[Path]; dictionary: DataDictionary | None`
  - `run_build(info: BuildInfo) -> Run` (what `analyse` did, keeping the dictionary)
  - `run_project(root: Path) -> Run` (default severities)
  - `group_findings(bag: DiagnosticBag, fallback: Path, grouped: dict[Path, list[Diagnostic]]) -> set[Path]` (the renamed `_group`, unchanged behaviour)
  - `analyse(info)` and `analyse_standalone(path)` keep their signatures and results.

- [ ] **Step 1: Write the failing tests**

In `tests/test_lsp.py` replace `service._group(bag, tmp_path / "root.ddd.json", grouped)` with `service.group_findings(bag, tmp_path / "root.ddd.json", grouped)`, and add after `class TestDiagnostics` (add `from ddd.build_info import BuildInfo` to the imports; `DEMO`, `checks`, `component`, `declare`, `project`, `write_tree` come from `conftest`):

```python
class TestRuns:
    """What the GUI reads from an analysis: the findings, the files, and the dictionary."""

    def test_a_project_run_keeps_the_dictionary_it_resolved(self) -> None:
        run = service.run_project(DEMO)
        assert run.dictionary is not None
        assert run.dictionary.name == "DemoDevice"
        assert DEMO.resolve() in run.covered
        assert not run.bag.has_errors

    def test_a_read_that_reported_an_error_resolves_nothing(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": "{"})
        run = service.run_project(tmp_path / "p.ddd.json")
        assert run.dictionary is None
        assert "json-syntax" in checks(run.bag)

    def test_a_root_that_cannot_be_read_covers_itself_alone(self, tmp_path: Path) -> None:
        absent = tmp_path / "absent.ddd.json"
        run = service.run_project(absent)
        assert run.dictionary is None
        assert run.covered == frozenset({absent})

    def test_a_build_run_applies_the_builds_severities(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        info = BuildInfo(
            project=(tmp_path / "p.ddd.json").as_posix(), severity=("unused-output=error",)
        )
        run = service.run_build(info)
        assert run.dictionary is not None
        assert [d.severity for d in run.bag if d.check == "unused-output"] == [Severity.ERROR]

    def test_a_plugin_that_raises_during_the_analysis_leaves_no_dictionary(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_CHECK_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        run = service.run_project(tmp_path / "p.ddd.json")
        assert run.dictionary is None
        assert "plugin-invalid" in checks(run.bag)

    def test_the_old_answers_are_the_runs_answers(self) -> None:
        bag, covered = service.analyse(BuildInfo(project=DEMO.as_posix()))
        assert covered == service.run_project(DEMO).covered
        assert not bag.has_errors
```

(`checks` from `conftest` returns the check identifiers a bag holds; if its name differs, use `[d.check for d in run.bag]`.)

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_lsp.py -k "TestRuns or lands_on_the_root" --no-cov`
Expected: FAIL with `AttributeError: module 'ddd.lsp.diagnostics' has no attribute 'run_project'` (and `group_findings`).

- [ ] **Step 3: Implement**

In `src/ddd/lsp/diagnostics.py`:

1. Imports: add `from dataclasses import dataclass, replace` (replacing `from dataclasses import replace`) and `from ddd.ir import DataDictionary`.

2. Add after `_LSP_SEVERITY`:

```python
@dataclass(frozen=True, slots=True)
class Run:
    """One analysis of one project: what it reported, the files it covered, what it resolved to.

    ``dictionary`` is ``None`` when the analysis did not get that far - a read that reported an
    error is not analysed, and a plugin that raises stops the run - which is exactly when a
    reader of the dictionary has nothing it could trust.
    """

    bag: DiagnosticBag
    covered: frozenset[Path]
    dictionary: DataDictionary | None
```

3. Replace `analyse` with the pair below (the docstring of the old `analyse` moves to `run_build`, whose first line becomes "Run the checks over one configured project, exactly as its build would, keeping what it resolved to."):

```python
def analyse(info: BuildInfo) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over one configured project, exactly as its build would.

    The editor's answer; :func:`run_build` is the same run keeping the dictionary as well.
    """
    run = run_build(info)
    return run.bag, run.covered


def run_build(info: BuildInfo) -> Run:
    """<the old analyse docstring, first line as above>"""
    policy = SeverityPolicy.from_strings(list(info.severity), strict=info.strict)
    project = Path(info.project)
    run = _run(project, DiagnosticBag(policy))
    try:
        policy.verify(run.bag.registered)
    except UnknownCheckError as fault:
        run.bag.add("plugin-invalid", str(fault), Location(project))
    return run


def run_project(root: Path) -> Run:
    """Run the checks over a project description under the default severities, the way a
    project file no build configured is checked."""
    return _run(root, DiagnosticBag())
```

4. `analyse_standalone` becomes:

```python
def analyse_standalone(path: Path) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over a file read as "a component on its own"."""
    policy = SeverityPolicy.from_strings(list(STANDALONE_POLICY), strict=False, standalone=True)
    run = _run(path, DiagnosticBag(policy))
    return run.bag, run.covered
```

5. In `_analyse_root`, replace `return _run(path, DiagnosticBag())` with:

```python
        run = run_project(path)
        return run.bag, run.covered
```

6. `_run` returns a `Run` (keep its docstring):

```python
def _run(root: Path, bag: DiagnosticBag) -> Run:
    covered = frozenset({root})
    dictionary: DataDictionary | None = None
    try:
        workspace = load_workspace(root, bag)
        if workspace is None:
            return Run(bag, covered, None)
        covered = frozenset(workspace.sources())
        if not bag.has_errors:
            dictionary = analyze(workspace, bag)
    except PluginError as error:
        # (keep the existing comment)
        bag.add("plugin-invalid", str(error), Location(root))
    return Run(bag, covered, dictionary)
```

7. Rename `_group` to `group_findings` (definition and its two calls in `collect`); keep the docstring.

- [ ] **Step 4: Run the language server suite**

Run: `python -m pytest tests/test_lsp.py --no-cov`
Expected: all pass (the known symlink-privilege exception aside).

- [ ] **Step 5: Full Python gate**

Run (Git Bash): `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`
Expected: green, 100 %.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/lsp/diagnostics.py tests/test_lsp.py
git commit -m "keep the dictionary an analysis resolved to, and let another reader file findings the way the editor does" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 6: The session

**Files:**
- Create: `src/ddd/gui/__init__.py`
- Create: `src/ddd/gui/session.py`
- Test: `tests/test_gui_session.py`

**Interfaces:**
- Consumes: Task 4's `FileChange`, `apply_changes`, `fingerprint`; Task 5's `Run`, `run_build`, `run_project`, `group_findings`; `ddd.lsp.discovery.discover` and `BUILD_DIRECTORY_PATTERNS`; `ddd.diagnostics.CheckInfo`, `Diagnostic`, `Severity`; `ddd.build_info.BuildInfo`; `ddd.ir.DataDictionary`.
- Produces (all in `ddd.gui.session`):
  - `KINDS`, `LOAD_CHECKS`, `SEARCH_DEPTH = 4`
  - `FoundProject(path: Path, name: str | None, images: tuple[str, ...])`, `Found(root: Path, projects: tuple[FoundProject, ...], refused: tuple[tuple[Path, str], ...])`
  - `SourceFile(path, kind: str, name: str | None, loaded: bool, fingerprint: str, errors: int, warnings: int, infos: int)`
  - `Filed(file: Path, diagnostic: Diagnostic)`
  - `Revision(number: int, project: Path, builds: tuple[BuildInfo, ...], files: tuple[SourceFile, ...], findings: tuple[Filed, ...], dictionary: DataDictionary | None, checks: tuple[CheckInfo, ...])`
  - `FileContent(path: Path, fingerprint: str, data: Any, error: str | None)`
  - `class NoProject(RuntimeError)`, `class NotInProject(LookupError)`
  - `find_projects(root: Path, build_directories: Sequence[Path] = ()) -> Found`
  - `class Session(root: Path, build_directories: Sequence[Path] = (), *, poll_interval: float = 1.0)` with `root`, `build_directories`, `poll_interval`, property `revision -> Revision | None`, `open(project: Path) -> Revision` (raises `ValueError` for a file that is not a project description), `wait(after: int, timeout: float) -> Revision | None`, `poll() -> bool`, `start_polling() -> None`, `stop() -> None`, `read_file(path: Path) -> FileContent`, `edit(changes: Sequence[FileChange]) -> tuple[Revision, dict[Path, str]]`

- [ ] **Step 1: Create the package**

Create `src/ddd/gui/__init__.py`:

```python
"""``ddd gui``: a browser interface over one project's description files, on this computer only.

A preview. The pages are compiled from ``gui/`` into ``static/`` beside this file; the server
(:mod:`ddd.gui.server`) serves them and the JSON API (:mod:`ddd.gui.api`), which answers from
the open project (:mod:`ddd.gui.session`). Nothing is imported here, so that ``import
ddd.gui.session`` costs only what it uses.
"""
```

- [ ] **Step 2: Write the failing tests** (see the test file in the next part of this task)

- [ ] **Step 3: Write the session**

Create `src/ddd/gui/session.py`:

```python
"""The project ``ddd gui`` has open, and what its last analysis said about it.

The GUI holds no data of its own: the description files are the project, and a revision is one
analysis of them - the findings, the files it read with a fingerprint of each, and the
dictionary it resolved to. A new revision is made after every edit and whenever a file of the
project changes on disk, which a thread notices by comparing each file's modification time and
size once a second: the standard library has no file watcher, and re-checking a project of
thousands of declarations takes well under a second. A file a wildcard include would match only
once it exists is noticed when something else changes, which is a limit of the preview.

The analysis is the language server's, run the way ``ddd lsp`` runs it: under the severities of
every build record naming the project, or under the defaults when none does.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final

from ddd.build_info import BuildInfo
from ddd.diagnostics import CheckInfo, Diagnostic, Severity
from ddd.editing import FileChange, apply_changes, fingerprint
from ddd.ir import DataDictionary
from ddd.lsp.diagnostics import Run, group_findings, run_build, run_project
from ddd.lsp.discovery import BUILD_DIRECTORY_PATTERNS, discover

KINDS: Final = ("project", "component", "types", "units", "sections", "constants", "rasters")
"""The top-level keys that say what a description file is, as the loader reads them."""

LOAD_CHECKS: Final = frozenset({"file-not-found", "json-syntax", "file-kind", "schema"})
"""The checks whose error on a file means that file did not load."""

SEARCH_DEPTH: Final = 4
"""How many directories below the start the search for project descriptions goes."""


@dataclass(frozen=True, slots=True)
class FoundProject:
    """A project the start page offers."""

    path: Path
    name: str | None
    images: tuple[str, ...]
    """The build images a build record names this project for; empty for a file found alone."""


@dataclass(frozen=True, slots=True)
class Found:
    """Every project found under a directory, and the build records that could not be used."""

    root: Path
    projects: tuple[FoundProject, ...]
    refused: tuple[tuple[Path, str], ...]


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One file an analysis read: what it is, whether it loaded, and how much it has to fix."""

    path: Path
    kind: str
    name: str | None
    loaded: bool
    fingerprint: str
    errors: int
    warnings: int
    infos: int


@dataclass(frozen=True, slots=True)
class Filed:
    """A finding and the file it is shown on: both sides of a disagreement are filed."""

    file: Path
    diagnostic: Diagnostic


@dataclass(frozen=True, slots=True)
class Revision:
    """One analysis of the open project."""

    number: int
    project: Path
    builds: tuple[BuildInfo, ...]
    files: tuple[SourceFile, ...]
    findings: tuple[Filed, ...]
    dictionary: DataDictionary | None
    checks: tuple[CheckInfo, ...]
    """The plugin checks the analysis registered, beside the built-in ones every run has."""


@dataclass(frozen=True, slots=True)
class FileContent:
    """A description file as the page reads it: parsed, or the reason it cannot be."""

    path: Path
    fingerprint: str
    data: Any
    error: str | None


class NoProject(RuntimeError):
    """Asked about the open project while none is open."""


class NotInProject(LookupError):
    """Asked about a file that is not a description file of the open project."""


def find_projects(root: Path, build_directories: Sequence[Path] = ()) -> Found:
    """The projects under ``root``: those a build record names, and the project descriptions a
    bounded walk finds, hidden directories, ``node_modules`` and build trees left out."""
    base = root.resolve()
    refused: dict[Path, str] = {}
    images: dict[Path, list[str]] = {}
    for info in discover(base, build_directories, refused):
        images.setdefault(Path(info.project).resolve(), []).append(info.image)
    paths = sorted(set(images) | set(_descriptions(base)))
    projects = tuple(
        FoundProject(path, _name_in(_read_json(path), "project"), tuple(images.get(path, ())))
        for path in paths
    )
    return Found(base, projects, tuple(sorted(refused.items())))


class Session:
    """One open project at a time, analysed into numbered revisions."""

    def __init__(
        self, root: Path, build_directories: Sequence[Path] = (), *, poll_interval: float = 1.0
    ) -> None:
        self.root = root.resolve()
        self.build_directories = tuple(build_directories)
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._published = threading.Condition()
        self._revision: Revision | None = None
        self._signature: dict[Path, tuple[int, int] | None] = {}
        self._stopping = threading.Event()
        self._poller: threading.Thread | None = None

    @property
    def revision(self) -> Revision | None:
        """The newest revision, or ``None`` while no project is open."""
        return self._revision

    def open(self, project: Path) -> Revision:
        """Open a project description, replacing the project open before it."""
        path = project.resolve()
        if not _is_project(path):
            raise ValueError(f"{project} is not a project description")
        with self._lock:
            return self._publish(self._analysed(path))

    def wait(self, after: int, timeout: float) -> Revision | None:
        """The newest revision as soon as it is newer than ``after``, or after ``timeout``."""
        with self._published:
            self._published.wait_for(
                lambda: self._revision is not None and self._revision.number > after, timeout
            )
            return self._revision

    def poll(self) -> bool:
        """Analyse the open project again if a file of it changed on disk; say whether one did."""
        with self._lock:
            revision = self._revision
            if revision is None or _signature(self._signature) == self._signature:
                return False
            self._publish(self._analysed(revision.project))
            return True

    def start_polling(self) -> None:
        """Poll every ``poll_interval`` seconds on a thread of its own, until :meth:`stop`."""
        if self._poller is None:
            self._poller = threading.Thread(
                target=self._poll_until_stopped, name="ddd-gui-poll", daemon=True
            )
            self._poller.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._poller is not None:
            self._poller.join()

    def read_file(self, path: Path) -> FileContent:
        """A description file of the open project, parsed, with the fingerprint it was read at."""
        target = _source(self._required(), path)
        try:
            data = target.read_bytes()
        except OSError as error:
            return FileContent(target, fingerprint(b""), None, f"{target} cannot be read: {error}")
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except ValueError as error:
            return FileContent(target, fingerprint(data), None, f"{target} is not json: {error}")
        return FileContent(target, fingerprint(data), parsed, None)

    def edit(self, changes: Sequence[FileChange]) -> tuple[Revision, dict[Path, str]]:
        """Make an edit of description files of the open project, then analyse it again."""
        with self._lock:
            revision = self._required()
            confined = [
                FileChange(_source(revision, pending.path), pending.fingerprint, pending.operations)
                for pending in changes
            ]
            written = apply_changes(confined)
            return self._publish(self._analysed(revision.project)), written

    def _poll_until_stopped(self) -> None:
        while not self._stopping.wait(self.poll_interval):
            try:
                self.poll()
            except Exception as error:
                # A thread that dies here leaves a page that never updates again, and nothing
                # says why: the one line is that reason, and the next poll tries again.
                print(f"ddd gui: checking the project again failed: {error}", file=sys.stderr)

    def _required(self) -> Revision:
        if self._revision is None:
            raise NoProject("no project is open")
        return self._revision

    def _analysed(self, project: Path) -> Revision:
        ignored: dict[Path, str] = {}  # the start page is where a refused record is reported
        builds = tuple(
            info
            for info in discover(self.root, self.build_directories, ignored)
            if Path(info.project).resolve() == project
        )
        runs: list[Run] = [run_build(info) for info in builds] or [run_project(project)]
        grouped: dict[Path, list[Diagnostic]] = {}
        covered: set[Path] = set()
        for run in runs:
            covered |= run.covered | group_findings(run.bag, project, grouped)
        registered = {info.identifier: info for run in runs for info in run.bag.registered.values()}
        return Revision(
            number=1 if self._revision is None else self._revision.number + 1,
            project=project,
            builds=builds,
            files=tuple(_described(path, grouped.get(path, ())) for path in sorted(covered)),
            findings=tuple(Filed(path, found) for path in sorted(grouped) for found in grouped[path]),
            dictionary=next((run.dictionary for run in runs if run.dictionary is not None), None),
            checks=tuple(registered.values()),
        )

    def _publish(self, revision: Revision) -> Revision:
        with self._published:
            self._revision = revision
            self._signature = _signature(file.path for file in revision.files)
            self._published.notify_all()
        return revision


def _source(revision: Revision, path: Path) -> Path:
    resolved = path.resolve()
    if not any(file.path == resolved and file.kind != "plugin" for file in revision.files):
        raise NotInProject(f"{path} is not a description file of the open project")
    return resolved


def _described(path: Path, findings: Iterable[Diagnostic]) -> SourceFile:
    listed = list(findings)
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    parsed = None if path.suffix == ".py" else _parsed(data)
    kind = _kind(path, parsed)
    return SourceFile(
        path=path,
        kind=kind,
        name=_name_in(parsed, kind),
        loaded=not any(f.check in LOAD_CHECKS and f.severity is Severity.ERROR for f in listed),
        fingerprint=fingerprint(data),
        errors=sum(1 for f in listed if f.severity is Severity.ERROR),
        warnings=sum(1 for f in listed if f.severity is Severity.WARNING),
        infos=sum(1 for f in listed if f.severity is Severity.INFO),
    )


def _kind(path: Path, parsed: Any) -> str:
    if path.suffix == ".py":
        return "plugin"
    if isinstance(parsed, dict):
        return next((key for key in KINDS if key in parsed), "unknown")
    return "unknown"


def _descriptions(root: Path) -> list[Path]:
    found = []
    for directory, subdirectories, files in root.walk():
        depth = len(directory.relative_to(root).parts)
        subdirectories[:] = [
            name for name in subdirectories if depth < SEARCH_DEPTH and not _skipped(name)
        ]
        found.extend(
            directory / name
            for name in files
            if name.endswith(".ddd.json") and _is_project(directory / name)
        )
    return found


def _skipped(name: str) -> bool:
    return (
        name.startswith(".")
        or name == "node_modules"
        or any(fnmatch(name, pattern) for pattern in BUILD_DIRECTORY_PATTERNS)
    )


def _read_json(path: Path) -> Any:
    try:
        return _parsed(path.read_bytes())
    except OSError:
        return None


def _parsed(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8-sig"))
    except ValueError:
        return None


def _is_project(path: Path) -> bool:
    data = _read_json(path)
    return isinstance(data, dict) and isinstance(data.get("project"), dict)


def _name_in(data: Any, kind: str) -> str | None:
    block = data.get(kind) if isinstance(data, dict) else None
    name = block.get("name") if isinstance(block, dict) else None
    return name if isinstance(name, str) else None


def _signature(paths: Iterable[Path]) -> dict[Path, tuple[int, int] | None]:
    signature: dict[Path, tuple[int, int] | None] = {}
    for path in paths:
        try:
            status = path.stat()
        except OSError:
            signature[path] = None
        else:
            signature[path] = (status.st_mtime_ns, status.st_size)
    return signature
```

`UnicodeDecodeError` is a `ValueError`, so `_parsed` and `read_file` catch both with one clause.

The tests for Step 2 - create `tests/test_gui_session.py`:

```python
"""The project ddd gui has open: what it finds, what a revision holds, and how it follows disk."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from conftest import EXAMPLES, build_record, component, declare, project, write_tree
from ddd.diagnostics import SeverityPolicy, UnknownCheckError
from ddd.editing import STALE, EditError, FileChange, Operation, fingerprint
from ddd.gui import session as module
from ddd.gui.session import NoProject, NotInProject, Session, find_projects

REGISTERING_PLUGIN = """
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    return None


PLUGIN = Plugin(
    name="demo",
    checks=(CheckInfo("demo/tagged", Severity.WARNING, "a demonstration check"),),
    check=check,
)
"""


@pytest.fixture
def shared(tmp_path: Path) -> Path:
    """A producer and a consumer of one variable, agreeing; returns the project file."""
    write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
        },
    )
    return tmp_path / "p.ddd.json"


def unit_of_b(path: Path, unit: str) -> FileChange:
    target = path.parent / "b.ddd.json"
    pointer = "component.interface[0].definition.unit"
    return FileChange(target, fingerprint(target.read_bytes()), (Operation("set", pointer, f'"{unit}"'),))


class TestFindingProjects:
    def test_project_descriptions_are_found_and_components_are_not(self, shared: Path) -> None:
        found = find_projects(shared.parent)
        assert [(p.path, p.name, p.images) for p in found.projects] == [(shared.resolve(), "P", ())]
        assert found.root == shared.parent.resolve()

    def test_the_walk_skips_hidden_directories_node_modules_and_build_trees(
        self, tmp_path: Path
    ) -> None:
        for directory in (".git", "node_modules", "build", "cmake-build-debug", "out", "src"):
            write_tree(tmp_path / directory, {"p.ddd.json": project(directory)})
        assert [p.name for p in find_projects(tmp_path).projects] == ["src"]

    def test_the_walk_goes_four_directories_deep_and_no_further(self, tmp_path: Path) -> None:
        write_tree(tmp_path / "1/2/3/4", {"p.ddd.json": project("four")})
        write_tree(tmp_path / "1/2/3/4/5", {"p.ddd.json": project("five")})
        assert [p.name for p in find_projects(tmp_path).projects] == ["four"]

    def test_a_file_that_is_not_json_is_not_a_project(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": "{", "q.ddd.json": '{"project": 7}'})
        assert find_projects(tmp_path).projects == ()

    def test_a_build_record_names_its_project_and_image(self, shared: Path) -> None:
        build_record(shared.parent, shared, image="firmware.elf")
        (found,) = find_projects(shared.parent).projects
        assert found.images == ("firmware.elf",)

    def test_a_project_a_record_names_that_does_not_exist_is_offered_without_a_name(
        self, tmp_path: Path
    ) -> None:
        build_record(tmp_path, tmp_path / "gone.ddd.json")
        (found,) = find_projects(tmp_path).projects
        assert (found.path.name, found.name) == ("gone.ddd.json", None)

    def test_a_record_that_cannot_be_used_is_reported_with_its_reason(self, shared: Path) -> None:
        build_record(shared.parent, shared, severity=["no-such-check=error"])
        with pytest.raises(UnknownCheckError) as expected:
            SeverityPolicy.from_strings(["no-such-check=error"], strict=False)
        found = find_projects(shared.parent)
        assert [reason for _, reason in found.refused] == [str(expected.value)]


class TestOpening:
    def test_a_file_that_is_not_a_project_description_is_refused(self, shared: Path) -> None:
        with pytest.raises(ValueError, match="not a project description"):
            Session(shared.parent).open(shared.parent / "a.ddd.json")

    def test_a_revision_describes_every_file_and_resolves_the_dictionary(self, shared: Path) -> None:
        revision = Session(shared.parent).open(shared)
        described = {f.path.name: (f.kind, f.name, f.loaded) for f in revision.files}
        assert described == {
            "p.ddd.json": ("project", "P", True),
            "a.ddd.json": ("component", "A", True),
            "b.ddd.json": ("component", "B", True),
        }
        assert revision.number == 1
        assert revision.dictionary is not None
        assert all(f.fingerprint == fingerprint(f.path.read_bytes()) for f in revision.files)

    def test_a_disagreement_is_filed_on_both_sides(self, shared: Path) -> None:
        (shared.parent / "b.ddd.json").write_text(
            (shared.parent / "b.ddd.json").read_text(encoding="utf-8").replace("rpm", "Hz"),
            encoding="utf-8",
        )
        revision = Session(shared.parent).open(shared)
        filed = {f.file.name for f in revision.findings if f.diagnostic.check == "definition-mismatch"}
        assert filed == {"a.ddd.json", "b.ddd.json"}
        counts = {f.path.name: f.errors for f in revision.files}
        assert counts["a.ddd.json"] == counts["b.ddd.json"] == 1

    def test_opening_again_makes_a_newer_revision(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        assert session.open(shared).number == 2

    def test_a_build_records_severities_and_plugin_checks_apply(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "tools/demo_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["unused-output=error"])
        revision = Session(tmp_path).open(tmp_path / "p.ddd.json")
        assert [b.image for b in revision.builds] == ["firmware.elf"]
        unused = [f.diagnostic for f in revision.findings if f.diagnostic.check == "unused-output"]
        assert [d.severity.value for d in unused] == ["error"]
        assert [info.identifier for info in revision.checks] == ["demo/tagged"]
        kinds = {f.path.name: f.kind for f in revision.files}
        assert kinds["demo_plugin.py"] == "plugin"

    def test_a_file_that_does_not_parse_is_listed_as_not_loaded(self, shared: Path) -> None:
        (shared.parent / "b.ddd.json").write_text("{", encoding="utf-8")
        revision = Session(shared.parent).open(shared)
        broken = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert (broken.kind, broken.name, broken.loaded) == ("unknown", None, False)
        assert revision.dictionary is None

    def test_a_file_that_cannot_be_read_is_described_as_empty(self, tmp_path: Path) -> None:
        described = module._described(tmp_path / "gone.ddd.json", [])
        assert (described.kind, described.fingerprint) == ("unknown", fingerprint(b""))

    def test_a_description_of_no_known_kind_is_unknown(self) -> None:
        assert module._kind(Path("x.ddd.json"), {"other": 1}) == "unknown"


class TestFollowingTheDisk:
    def test_nothing_is_polled_while_no_project_is_open(self, tmp_path: Path) -> None:
        assert Session(tmp_path).poll() is False

    def test_an_unchanged_project_is_not_analysed_again(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        assert session.poll() is False
        assert session.revision is not None and session.revision.number == 1

    def test_a_file_changed_on_disk_makes_a_new_revision(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        (shared.parent / "b.ddd.json").write_text(
            (shared.parent / "b.ddd.json").read_text(encoding="utf-8").replace("rpm", "Hz") + " ",
            encoding="utf-8",
        )
        assert session.poll() is True
        assert session.revision is not None and session.revision.number == 2

    def test_a_file_removed_from_disk_makes_a_new_revision(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        (shared.parent / "b.ddd.json").unlink()
        assert session.poll() is True

    def test_a_waiting_request_gets_the_newer_revision_as_soon_as_it_exists(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        threading.Timer(0.05, session.open, args=(shared,)).start()
        revision = session.wait(1, timeout=5)
        assert revision is not None and revision.number == 2

    def test_a_waiting_request_gets_the_current_revision_when_nothing_changes(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        revision = session.wait(1, timeout=0.05)
        assert revision is not None and revision.number == 1

    def test_the_polling_thread_notices_a_change(self, shared: Path) -> None:
        session = Session(shared.parent, poll_interval=0.02)
        session.open(shared)
        session.start_polling()
        session.start_polling()  # a second start keeps the one thread
        try:
            (shared.parent / "a.ddd.json").write_text("{}", encoding="utf-8")
            revision = session.wait(1, timeout=5)
            assert revision is not None and revision.number == 2
        finally:
            session.stop()

    def test_a_poll_that_fails_says_so_and_polling_goes_on(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = Session(shared.parent, poll_interval=0.01)
        session.open(shared)
        calls = []

        def failing() -> bool:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            session._stopping.set()
            return False

        monkeypatch.setattr(session, "poll", failing)
        session._poll_until_stopped()
        assert "checking the project again failed: boom" in capsys.readouterr().err
        assert len(calls) == 2

    def test_stopping_a_session_that_never_polled_is_harmless(self, tmp_path: Path) -> None:
        Session(tmp_path).stop()


class TestReadingAndEditing:
    def test_a_description_file_is_read_with_its_fingerprint(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        content = session.read_file(shared.parent / "a.ddd.json")
        assert content.data["component"]["name"] == "A"
        assert content.error is None
        assert content.fingerprint == fingerprint((shared.parent / "a.ddd.json").read_bytes())

    def test_a_file_that_is_not_json_is_read_as_its_reason(self, shared: Path) -> None:
        (shared.parent / "b.ddd.json").write_text("{", encoding="utf-8")
        session = Session(shared.parent)
        session.open(shared)
        content = session.read_file(shared.parent / "b.ddd.json")
        assert content.data is None
        assert content.error is not None and "is not json" in content.error

    def test_a_file_that_vanished_is_read_as_its_reason(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        (shared.parent / "a.ddd.json").unlink()
        content = session.read_file(shared.parent / "a.ddd.json")
        assert content.error is not None and "cannot be read" in content.error

    def test_only_description_files_of_the_open_project_are_read(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "tools/demo_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
                "elsewhere.ddd.json": component("E"),
            },
        )
        session = Session(tmp_path)
        with pytest.raises(NoProject):
            session.read_file(tmp_path / "a.ddd.json")
        session.open(tmp_path / "p.ddd.json")
        for outside in ("elsewhere.ddd.json", "tools/demo_plugin.py"):
            with pytest.raises(NotInProject):
                session.read_file(tmp_path / outside)

    def test_an_edit_is_written_and_analysed_again(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        revision, written = session.edit([unit_of_b(shared, "Hz")])
        assert revision.number == 2
        assert list(written) == [(shared.parent / "b.ddd.json").resolve()]
        assert {f.diagnostic.check for f in revision.findings} >= {"definition-mismatch"}

    def test_an_edit_outside_the_project_is_refused_and_nothing_is_written(
        self, shared: Path, tmp_path: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        outside = tmp_path / "outside.ddd.json"
        outside.write_text("{}", encoding="utf-8")
        with pytest.raises(NotInProject):
            session.edit([FileChange(outside, fingerprint(b"{}"), (Operation("set", "a", "1"),))])
        assert outside.read_text(encoding="utf-8") == "{}"

    def test_an_edit_from_a_stale_read_is_refused(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        stale = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.edit([stale])
        assert refused.value.code == STALE

    def test_an_edit_needs_an_open_project(self, shared: Path) -> None:
        with pytest.raises(NoProject):
            Session(shared.parent).edit([unit_of_b(shared, "Hz")])


def test_the_demo_opens_clean() -> None:
    demo = EXAMPLES / "demo" / "demo.ddd.json"
    revision = Session(demo.parent).open(demo)
    assert not [f for f in revision.findings if f.diagnostic.severity.value == "error"]
    assert {f.name for f in revision.files if f.kind == "component"} == {
        "Controller",
        "SensorHub",
        "UserInterface",
        "EventLogger",
    }
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_gui_session.py --no-cov`
Expected: all pass.

- [ ] **Step 5: Coverage, style, types**

Run: `python -m pytest tests/test_gui_session.py --cov=ddd.gui --cov-branch --cov-report=term-missing --cov-fail-under=0`, then `python -m ruff format src tests`, `python -m ruff check .`, `python -m mypy`
Expected: `ddd/gui/session.py` and `ddd/gui/__init__.py` at 100 %, no findings. Ruff may flag `except Exception` (`BLE001` is not selected in this project, so it should not); keep the comment that says why it is broad.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/gui/__init__.py src/ddd/gui/session.py tests/test_gui_session.py
git commit -m "hold one open project for ddd gui and number each analysis of it, following the files on disk" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 7: The JSON API

**Files:**
- Create: `src/ddd/gui/api.py`
- Test: `tests/test_gui_api.py`

**Interfaces:**
- Consumes: Task 6's `Session`, `find_projects`, `NoProject`, `NotInProject`, `Revision`, `SourceFile`, `Filed`; Task 4's `FileChange`, `EditError` and the codes; Task 2's `Operation`; `ddd.diagnostics.CHECKS`, `CheckInfo`; `ddd.__version__`.
- Produces:
  - `WAIT_SECONDS: Final = 25.0`
  - `@dataclass(frozen=True, slots=True) class Reply: status: int; body: dict[str, Any]`
  - `class Api(session: Session, project: Path | None = None, *, wait_seconds: float = WAIT_SECONDS)` with attribute `session` and `handle(method: str, path: str, query: Mapping[str, Sequence[str]], body: bytes | None) -> Reply`
  - The JSON shapes below, which the frontend (Task 10, `src/api/types.ts`) mirrors exactly:
    - `GET /api/session` -> `{"version", "preview": true, "root", "project": null | {"path", "name"}, "builds": [{"image", "strict", "severity": [...]}]}`
    - `GET /api/projects` -> `{"root", "projects": [{"path", "name", "images": [...]}], "refused": [{"record", "reason"}]}`
    - `POST /api/open {"path"}` -> the session body; 404 `not-found`, 409 `not-a-project`, 400 `bad-request`
    - `GET /api/state[?after=N]` -> `{"revision", "project", "files": [{"path", "kind", "name", "loaded", "fingerprint", "findings": {"error", "warning", "info"}}], "findings": [{"file", "check", "severity", "message", "pointer", "notes": [{"message", "file", "pointer"}]}]}`; 409 `no-project`
    - `GET /api/file?path=P` -> `{"path", "fingerprint", "data", "error"}`; 404 `not-found`; 400 `bad-request`; 409 `no-project`
    - `GET /api/dictionary` -> `{"revision", "dictionary"}`; 409 `no-project`
    - `GET /api/checks` -> `{"checks": [{"check", "default_severity", "description", "overridable", "needs_every_component", "comparison"}]}`
    - `POST /api/edit {"changes": [{"file", "fingerprint", "operations": [{"op", "pointer", "raw"?, "to"?}]}]}` -> `{"revision", "files": [{"path", "fingerprint"}]}`; 409 with `stale`/`unreadable`/`invalid`/`unverified`; 500 `unwritable`; 404 `not-found`; 400 `bad-request`; 409 `no-project`
    - any other `/api/...` path: 404 `not-found`; a known path with the wrong method: 405 `method-not-allowed`
    - every error body is `{"error": <code>, "message": <sentence>}`; every path in a body is `Path.as_posix()`

- [ ] **Step 1: Write the failing tests** (the test file is in the next part of this task)

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_gui_api.py --no-cov`
Expected: collection error, `ModuleNotFoundError: No module named 'ddd.gui.api'`.

- [ ] **Step 3: Write the API**

Create `src/ddd/gui/api.py`:

```python
"""The JSON API of ``ddd gui``: each request answered from the session, as a status and a body.

Nothing here reads a socket or a header, which is the server's business. A request arrives as
its method, its path, its query and its body, and leaves as a :class:`Reply`, so every answer
the page can get is tested without a network in between. The API is internal - the page and the
server ship in one wheel - and changes with the package.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd import __version__
from ddd.diagnostics import CHECKS, CheckInfo
from ddd.editing import INVALID, STALE, UNREADABLE, UNVERIFIED, EditError, FileChange, Operation
from ddd.gui.session import (
    Filed,
    NoProject,
    NotInProject,
    Revision,
    Session,
    SourceFile,
    find_projects,
)

WAIT_SECONDS: Final = 25.0
"""How long a request for a newer revision waits before answering with the current one."""

REFUSALS: Final = frozenset({STALE, UNREADABLE, INVALID, UNVERIFIED})
"""The edit refusals a page can act on, answered 409; anything else an edit raises is a 500."""

OPERATIONS: Final = frozenset({"set", "remove", "insert", "move"})

type Query = Mapping[str, Sequence[str]]


@dataclass(frozen=True, slots=True)
class Reply:
    """An answer: the HTTP status and the JSON body."""

    status: int
    body: dict[str, Any]


class Api:
    """The requests the page makes, answered from one session."""

    def __init__(
        self, session: Session, project: Path | None = None, *, wait_seconds: float = WAIT_SECONDS
    ) -> None:
        self.session = session
        self.project = None if project is None else project.resolve()
        self.wait_seconds = wait_seconds

    def handle(self, method: str, path: str, query: Query, body: bytes | None) -> Reply:
        route = _ROUTES.get(path)
        if route is None:
            return _error(404, "not-found", f"{path} is not part of the api")
        expected, answer = route
        if method != expected:
            return _error(405, "method-not-allowed", f"{path} takes {expected}")
        try:
            return answer(self, query, body)
        except NoProject as error:
            return _error(409, "no-project", str(error))
        except NotInProject as error:
            return _error(404, "not-found", str(error))

    def _session(self, query: Query, body: bytes | None) -> Reply:
        return Reply(200, self._session_body())

    def _projects(self, query: Query, body: bytes | None) -> Reply:
        found = find_projects(self.session.root, self.session.build_directories)
        return Reply(
            200,
            {
                "root": found.root.as_posix(),
                "projects": [
                    {"path": p.path.as_posix(), "name": p.name, "images": list(p.images)}
                    for p in found.projects
                ],
                "refused": [
                    {"record": record.as_posix(), "reason": reason}
                    for record, reason in found.refused
                ],
            },
        )

    def _open(self, query: Query, body: bytes | None) -> Reply:
        request = _json_object(body)
        given = None if request is None else request.get("path")
        if not isinstance(given, str):
            return _error(400, "bad-request", 'open takes {"path": ...}')
        wanted = Path(given).resolve()
        found = find_projects(self.session.root, self.session.build_directories)
        allowed = {p.path for p in found.projects} | ({self.project} if self.project else set())
        if wanted not in allowed:
            return _error(404, "not-found", f"{given} is not a project found here")
        try:
            self.session.open(wanted)
        except ValueError as error:
            return _error(409, "not-a-project", str(error))
        return Reply(200, self._session_body())

    def _state(self, query: Query, body: bytes | None) -> Reply:
        after = _integer(query.get("after"))
        if after is None:
            revision = self.session.revision
        else:
            revision = self.session.wait(after, self.wait_seconds)
        if revision is None:
            raise NoProject("no project is open")
        return Reply(
            200,
            {
                "revision": revision.number,
                "project": revision.project.as_posix(),
                "files": [_file(file) for file in revision.files],
                "findings": [_finding(filed) for filed in revision.findings],
            },
        )

    def _file(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("path"))
        if path is None:
            return _error(400, "bad-request", "file takes ?path=")
        content = self.session.read_file(Path(path))
        return Reply(
            200,
            {
                "path": content.path.as_posix(),
                "fingerprint": content.fingerprint,
                "data": content.data,
                "error": content.error,
            },
        )

    def _dictionary(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        if revision is None:
            raise NoProject("no project is open")
        dictionary = revision.dictionary
        return Reply(
            200,
            {
                "revision": revision.number,
                "dictionary": None if dictionary is None else dictionary.model_dump(mode="json"),
            },
        )

    def _checks(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        plugins = () if revision is None else revision.checks
        return Reply(200, {"checks": [_check(info) for info in (*CHECKS.values(), *plugins)]})

    def _edit(self, query: Query, body: bytes | None) -> Reply:
        changes = _changes(_json_object(body))
        if changes is None:
            return _error(
                400,
                "bad-request",
                'edit takes {"changes": [{"file", "fingerprint", "operations": [...]}]}',
            )
        try:
            revision, written = self.session.edit(changes)
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        return Reply(
            200,
            {
                "revision": revision.number,
                "files": [
                    {"path": path.as_posix(), "fingerprint": stamp}
                    for path, stamp in written.items()
                ],
            },
        )

    def _session_body(self) -> dict[str, Any]:
        revision = self.session.revision
        return {
            "version": __version__,
            "preview": True,
            "root": self.session.root.as_posix(),
            "project": None if revision is None else _project(revision),
            "builds": []
            if revision is None
            else [
                {"image": info.image, "strict": info.strict, "severity": list(info.severity)}
                for info in revision.builds
            ],
        }


type Answer = Callable[[Api, Query, bytes | None], Reply]

_ROUTES: Final[dict[str, tuple[str, Answer]]] = {
    "/api/session": ("GET", Api._session),
    "/api/projects": ("GET", Api._projects),
    "/api/open": ("POST", Api._open),
    "/api/state": ("GET", Api._state),
    "/api/file": ("GET", Api._file),
    "/api/dictionary": ("GET", Api._dictionary),
    "/api/checks": ("GET", Api._checks),
    "/api/edit": ("POST", Api._edit),
}


def _error(status: int, code: str, message: str) -> Reply:
    return Reply(status, {"error": code, "message": message})


def _project(revision: Revision) -> dict[str, Any]:
    name = next((f.name for f in revision.files if f.path == revision.project), None)
    return {"path": revision.project.as_posix(), "name": name}


def _file(file: SourceFile) -> dict[str, Any]:
    return {
        "path": file.path.as_posix(),
        "kind": file.kind,
        "name": file.name,
        "loaded": file.loaded,
        "fingerprint": file.fingerprint,
        "findings": {"error": file.errors, "warning": file.warnings, "info": file.infos},
    }


def _finding(filed: Filed) -> dict[str, Any]:
    finding = filed.diagnostic
    return {
        "file": filed.file.as_posix(),
        "check": finding.check,
        "severity": finding.severity.value,
        "message": finding.message,
        "pointer": "" if finding.location is None else finding.location.pointer,
        "notes": [
            {
                "message": text,
                "file": None if note is None else note.path.as_posix(),
                "pointer": "" if note is None else note.pointer,
            }
            for text, note in finding.notes
        ],
    }


def _check(info: CheckInfo) -> dict[str, Any]:
    return {
        "check": info.identifier,
        "default_severity": info.default_severity.value,
        "description": info.description,
        "overridable": info.overridable,
        "needs_every_component": info.needs_every_component,
        "comparison": info.comparison,
    }


def _json_object(body: bytes | None) -> dict[str, Any] | None:
    try:
        parsed = json.loads(body or b"")
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _single(values: Sequence[str] | None) -> str | None:
    return values[0] if values else None


def _integer(values: Sequence[str] | None) -> int | None:
    text = _single(values)
    return int(text) if text is not None and text.isascii() and text.isdecimal() else None


def _changes(request: dict[str, Any] | None) -> list[FileChange] | None:
    entries = None if request is None else request.get("changes")
    if not isinstance(entries, list) or not entries:
        return None
    changes = []
    for entry in entries:
        change = _change(entry)
        if change is None:
            return None
        changes.append(change)
    return changes


def _change(entry: object) -> FileChange | None:
    if not isinstance(entry, dict):
        return None
    file, stamp, operations = entry.get("file"), entry.get("fingerprint"), entry.get("operations")
    if not (isinstance(file, str) and isinstance(stamp, str) and isinstance(operations, list)):
        return None
    parsed = [_operation(item) for item in operations]
    valid = [operation for operation in parsed if operation is not None]
    if not operations or len(valid) != len(operations):
        return None
    return FileChange(Path(file), stamp, tuple(valid))


def _operation(item: object) -> Operation | None:
    if not isinstance(item, dict):
        return None
    op, pointer, raw, to = item.get("op"), item.get("pointer"), item.get("raw"), item.get("to")
    if op not in OPERATIONS or not isinstance(pointer, str):
        return None
    if raw is not None and not isinstance(raw, str):
        return None
    if to is not None and (not isinstance(to, int) or isinstance(to, bool)):
        return None
    return Operation(op, pointer, raw, to)
```

The tests for Step 1 - create `tests/test_gui_api.py`:

```python
"""The JSON API of ddd gui, answered without a network: request in, reply out."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd import __version__
from ddd.diagnostics import CHECKS
from ddd.editing import UNWRITABLE, EditError, fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Session

UNIT = "component.interface[0].definition.unit"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            "other/q.ddd.json": project("Q"),
        },
    )
    return tmp_path


@pytest.fixture
def api(root: Path) -> Api:
    session = Session(root)
    session.open(root / "p.ddd.json")
    return Api(session, root / "p.ddd.json", wait_seconds=0.05)


def get(api: Api, path: str, **query: str) -> Reply:
    return api.handle("GET", path, {key: [value] for key, value in query.items()}, None)


def post(api: Api, path: str, body: object) -> Reply:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return api.handle("POST", path, {}, raw)


def unit_edit(api: Api, root: Path, unit: str, name: str = "b.ddd.json") -> dict:
    target = root / name
    return {
        "changes": [
            {
                "file": target.as_posix(),
                "fingerprint": fingerprint(target.read_bytes()),
                "operations": [{"op": "set", "pointer": UNIT, "raw": json.dumps(unit)}],
            }
        ]
    }


class TestRoutes:
    def test_an_unknown_path_is_not_found(self, api: Api) -> None:
        assert get(api, "/api/nothing") == Reply(
            404, {"error": "not-found", "message": "/api/nothing is not part of the api"}
        )

    def test_a_known_path_with_the_wrong_method_is_refused(self, api: Api) -> None:
        reply = api.handle("POST", "/api/state", {}, b"{}")
        assert (reply.status, reply.body["error"]) == (405, "method-not-allowed")


class TestSession:
    def test_the_open_project_and_the_version_are_described(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/session")
        assert reply.status == 200
        assert reply.body == {
            "version": __version__,
            "preview": True,
            "root": root.resolve().as_posix(),
            "project": {"path": (root / "p.ddd.json").resolve().as_posix(), "name": "P"},
            "builds": [],
        }

    def test_without_a_project_the_session_says_so(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/session")
        assert (reply.body["project"], reply.body["builds"]) == (None, [])

    def test_the_records_a_project_is_analysed_under_are_listed(self, root: Path) -> None:
        from conftest import build_record

        build_record(root, root / "p.ddd.json", severity=["unused-output=error"])
        session = Session(root)
        session.open(root / "p.ddd.json")
        assert get(Api(session), "/api/session").body["builds"] == [
            {"image": "firmware.elf", "strict": False, "severity": ["unused-output=error"]}
        ]


class TestProjects:
    def test_the_projects_found_are_listed(self, api: Api, root: Path) -> None:
        body = get(api, "/api/projects").body
        # sorted by path: other/q.ddd.json comes before p.ddd.json
        assert [(p["name"], p["images"]) for p in body["projects"]] == [("Q", []), ("P", [])]
        assert body["refused"] == []

    def test_a_refused_record_is_listed_with_its_reason(self, root: Path) -> None:
        from conftest import build_record

        record = build_record(root, root / "p.ddd.json", severity=["no-such-check=error"])
        body = get(Api(Session(root)), "/api/projects").body
        assert [entry["record"] for entry in body["refused"]] == [record.resolve().as_posix()]

    def test_a_project_found_can_be_opened(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/open", {"path": (root / "other" / "q.ddd.json").as_posix()})
        assert (reply.status, reply.body["project"]["name"]) == (200, "Q")

    def test_the_project_named_on_the_command_line_can_be_opened_from_anywhere(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        elsewhere = tmp_path_factory.mktemp("elsewhere")
        write_tree(elsewhere, {"p.ddd.json": project("Far")})
        start = tmp_path_factory.mktemp("start")
        api = Api(Session(start), elsewhere / "p.ddd.json")
        reply = post(api, "/api/open", {"path": (elsewhere / "p.ddd.json").as_posix()})
        assert reply.body["project"]["name"] == "Far"

    def test_a_path_that_is_not_a_project_found_is_not_opened(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/open", {"path": (root / "a.ddd.json").as_posix()})
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_record_naming_something_that_is_not_a_project_cannot_be_opened(
        self, root: Path
    ) -> None:
        from conftest import build_record

        build_record(root, root / "a.ddd.json")
        reply = post(Api(Session(root)), "/api/open", {"path": (root / "a.ddd.json").as_posix()})
        assert (reply.status, reply.body["error"]) == (409, "not-a-project")

    @pytest.mark.parametrize("body", [b"not json", b"[]", {"path": 7}, {}])
    def test_an_open_request_without_a_path_is_bad(self, api: Api, body: object) -> None:
        reply = post(api, "/api/open", body)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")


class TestState:
    def test_the_state_lists_every_file_and_finding(self, api: Api, root: Path) -> None:
        body = get(api, "/api/state").body
        assert body["revision"] == 1
        assert body["project"] == (root / "p.ddd.json").resolve().as_posix()
        files = {Path(f["path"]).name: f for f in body["files"]}
        assert files["a.ddd.json"]["kind"] == "component"
        assert files["a.ddd.json"]["name"] == "A"
        assert files["a.ddd.json"]["loaded"] is True
        assert files["a.ddd.json"]["findings"] == {"error": 0, "warning": 0, "info": 1}
        assert {f["check"] for f in body["findings"]} == {"missing-id"}

    def test_a_disagreement_carries_its_pointer_and_its_note(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "Hz")).status == 200
        findings = [f for f in get(api, "/api/state").body["findings"] if f["check"] == "definition-mismatch"]
        assert {Path(f["file"]).name for f in findings} == {"a.ddd.json", "b.ddd.json"}
        assert all(f["pointer"] == "component.interface[0].definition" for f in findings)
        noted = [f for f in findings if f["notes"]]
        assert noted and noted[0]["notes"][0]["pointer"] == "component.interface[0].definition"

    def test_a_note_without_a_place_is_carried_without_one(self, api: Api) -> None:
        from ddd.diagnostics import Diagnostic, Severity
        from ddd.gui.api import _finding
        from ddd.gui.session import Filed

        filed = Filed(Path("a.ddd.json"), Diagnostic("schema", Severity.ERROR, "m", None, (("n", None),)))
        assert _finding(filed)["notes"] == [{"message": "n", "file": None, "pointer": ""}]
        assert _finding(filed)["pointer"] == ""

    def test_asking_for_a_newer_revision_waits_for_one(self, api: Api, root: Path) -> None:
        threading.Timer(0.01, api.session.open, args=(root / "p.ddd.json",)).start()
        api.wait_seconds = 5
        assert get(api, "/api/state", after="1").body["revision"] == 2

    def test_asking_for_a_newer_revision_answers_with_the_current_one_after_waiting(
        self, api: Api
    ) -> None:
        assert get(api, "/api/state", after="1").body["revision"] == 1

    @pytest.mark.parametrize("after", ["", "-1", "one", "٣"])
    def test_an_after_that_is_not_a_number_does_not_wait(self, api: Api, after: str) -> None:
        api.wait_seconds = 30
        assert get(api, "/api/state", after=after).body["revision"] == 1

    def test_the_state_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root), wait_seconds=0.01), "/api/state", after="0")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestFiles:
    def test_a_description_file_is_read(self, api: Api, root: Path) -> None:
        body = get(api, "/api/file", path=(root / "a.ddd.json").as_posix()).body
        assert body["data"]["component"]["name"] == "A"
        assert body["fingerprint"] == fingerprint((root / "a.ddd.json").read_bytes())
        assert body["error"] is None

    def test_a_file_outside_the_project_is_not_found(self, api: Api, root: Path) -> None:
        reply = get(api, "/api/file", path=(root / "other" / "q.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_request_needs_a_path(self, api: Api) -> None:
        assert get(api, "/api/file").status == 400


class TestDictionaryAndChecks:
    def test_the_dictionary_of_the_current_revision_is_served(self, api: Api) -> None:
        body = get(api, "/api/dictionary").body
        assert body["revision"] == 1
        assert body["dictionary"]["name"] == "P"

    def test_a_project_that_does_not_resolve_has_no_dictionary(self, root: Path) -> None:
        (root / "b.ddd.json").write_text("{", encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        assert get(Api(session), "/api/dictionary").body["dictionary"] is None

    def test_the_dictionary_needs_an_open_project(self, root: Path) -> None:
        assert get(Api(Session(root)), "/api/dictionary").status == 409

    def test_the_built_in_checks_are_listed_without_a_project(self, root: Path) -> None:
        checks = get(Api(Session(root)), "/api/checks").body["checks"]
        assert [c["check"] for c in checks] == list(CHECKS)
        assert set(checks[0]) == {
            "check",
            "default_severity",
            "description",
            "overridable",
            "needs_every_component",
            "comparison",
        }

    def test_the_checks_of_the_open_projects_plugins_follow(self, api: Api, monkeypatch) -> None:
        from dataclasses import replace

        from ddd.diagnostics import CheckInfo, Severity

        revision = api.session.revision
        assert revision is not None
        extra = CheckInfo("demo/tagged", Severity.WARNING, "a demonstration check")
        monkeypatch.setattr(api.session, "_revision", replace(revision, checks=(extra,)))
        assert get(api, "/api/checks").body["checks"][-1]["check"] == "demo/tagged"


class TestEdit:
    def test_an_edit_is_written_and_the_new_revision_answered(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert reply.status == 200
        assert reply.body["revision"] == 2
        target = (root / "b.ddd.json").resolve()
        assert reply.body["files"] == [
            {"path": target.as_posix(), "fingerprint": fingerprint(target.read_bytes())}
        ]
        assert '"unit": "Hz"' in target.read_text(encoding="utf-8")

    def test_a_stale_edit_is_a_refusal_the_page_can_act_on(self, api: Api, root: Path) -> None:
        edit = unit_edit(api, root, "Hz")
        (root / "b.ddd.json").write_text("{}", encoding="utf-8")
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "stale")

    def test_an_edit_that_could_not_be_written_is_a_server_error(
        self, api: Api, root: Path, monkeypatch
    ) -> None:
        def unwritable(changes):
            raise EditError(UNWRITABLE, "disk full")

        monkeypatch.setattr(api.session, "edit", unwritable)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (500, "unwritable")

    def test_an_edit_outside_the_project_is_not_found(self, api: Api, root: Path) -> None:
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz", name="other/q.ddd.json"))
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_an_edit_needs_an_open_project(self, root: Path) -> None:
        reply = post(Api(Session(root)), "/api/edit", unit_edit(None, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (409, "no-project")

    @pytest.mark.parametrize(
        "body",
        [
            b"not json",
            {},
            {"changes": []},
            {"changes": [7]},
            {"changes": [{"file": 1, "fingerprint": "x", "operations": [{"op": "set", "pointer": "a", "raw": "1"}]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": []}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [7]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [{"op": "rename", "pointer": "a"}]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [{"op": "set", "pointer": 1}]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [{"op": "set", "pointer": "a", "raw": 1}]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [{"op": "move", "pointer": "a[0]", "to": "1"}]}]},
            {"changes": [{"file": "a", "fingerprint": "x", "operations": [{"op": "move", "pointer": "a[0]", "to": True}]}]},
        ],
    )
    def test_a_malformed_edit_is_a_bad_request(self, api: Api, body: object) -> None:
        reply = post(api, "/api/edit", body)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_pointer_that_names_nothing_is_an_invalid_edit(self, api: Api, root: Path) -> None:
        edit = unit_edit(api, root, "Hz")
        edit["changes"][0]["operations"][0]["pointer"] = "component.interface[5].definition.unit"
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "invalid")

    def test_an_edit_of_a_file_that_is_not_json_is_unreadable(self, root: Path) -> None:
        (root / "b.ddd.json").write_text("{", encoding="utf-8")
        session = Session(root)
        session.open(root / "p.ddd.json")
        api = Api(session)
        reply = post(api, "/api/edit", unit_edit(api, root, "Hz"))
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_move_carries_its_target_index(self, api: Api, root: Path) -> None:
        target = root / "p.ddd.json"
        edit = {
            "changes": [
                {
                    "file": target.as_posix(),
                    "fingerprint": fingerprint(target.read_bytes()),
                    "operations": [{"op": "move", "pointer": "project.includes[0]", "to": 1}],
                }
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        includes = json.loads(target.read_text(encoding="utf-8"))["project"]["includes"]
        assert includes == ["b.ddd.json", "a.ddd.json"]
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_gui_api.py --no-cov`
Expected: all pass.

- [ ] **Step 5: Coverage, style, types**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_session.py --cov=ddd.gui --cov-branch --cov-report=term-missing --cov-fail-under=0`, then `python -m ruff format src tests`, `python -m ruff check .`, `python -m mypy`
Expected: `ddd/gui/api.py` at 100 %; no findings (ruff format will re-wrap the long parametrize lines).

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/gui/api.py tests/test_gui_api.py
git commit -m "answer the page's requests from the session: the project, its findings, its files and its edits" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 8: The HTTP server

**Files:**
- Create: `src/ddd/gui/server.py`
- Test: `tests/test_gui_server.py`

**Interfaces:**
- Consumes: Task 7's `Api` (with `session`) and `Reply`; Task 6's `Session`; `ddd.cli.EXIT_OK`, `EXIT_USAGE`.
- Produces:
  - `COOKIE: Final = "ddd-gui"`, `MAX_BODY: Final = 1024 * 1024`, `CONTENT_TYPES`, `SECURITY_HEADERS`
  - `static_directory() -> Path`
  - `class GuiServer(ThreadingHTTPServer)`: `GuiServer(api: Api, static: Path, port: int = 0)`, attributes `api`, `static`, `token`, properties `port -> int`, `address -> str` (`http://127.0.0.1:<port>/open?token=<token>`)
  - `run(project: Path | None, build_directories: Sequence[Path], port: int, *, open_browser: bool, static: Path | None = None) -> int`; prints exactly one line `ddd gui (preview) serving <address>` to stdout, flushed, before serving
  - `/open` redirects to `/project` when a project is open, to `/` otherwise

- [ ] **Step 1: Write the failing tests** (the test file is in the next part of this task)

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_gui_server.py --no-cov`
Expected: collection error, `ModuleNotFoundError: No module named 'ddd.gui.server'`.

- [ ] **Step 3: Write the server**

Create `src/ddd/gui/server.py`:

```python
"""The web server of ``ddd gui``: the compiled pages and the JSON API, on this computer only.

Any web page open in the same browser can send requests to a server on the loopback address, so
this one trusts nothing it did not hand out itself:

* the address the command prints carries a token, which ``/open`` swaps for a cookie every other
  request has to present - ``SameSite=Strict``, so a request another site makes does not carry
  it;
* a request has to name this server's own host and port, which refuses a page whose domain was
  re-pointed at the loopback address;
* a request that changes anything has to come from this server's own origin, as json;
* no page of it can be framed, and only its own scripts run.

The pages are served with an explicit content type per extension. The platform's guess is not
used: on Windows ``mimetypes`` reads the registry, which can map ``.js`` to ``text/plain``, and a
browser told ``nosniff`` then refuses to run the page at all.
"""

from __future__ import annotations

import contextlib
import json
import secrets
import sys
import webbrowser
from collections.abc import Sequence
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import parse_qs, unquote, urlsplit

from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.gui.api import Api
from ddd.gui.session import Session

COOKIE: Final = "ddd-gui"

MAX_BODY: Final = 1024 * 1024
"""The largest request body accepted; an edit of a description file is a few hundred bytes."""

CONTENT_TYPES: Final = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
}

SECURITY_HEADERS: Final = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

SIGN_IN_PAGE: Final = (
    b'<!doctype html><html lang="en"><meta charset="utf-8"><title>ddd gui</title>'
    b"<p>Open the address <code>ddd gui</code> printed in its terminal.</p></html>"
)


def static_directory() -> Path:
    """Where the compiled pages are installed: ``static`` beside this module."""
    return Path(str(resources.files("ddd.gui").joinpath("static")))


class GuiServer(ThreadingHTTPServer):
    """The server one run of ``ddd gui`` answers on."""

    daemon_threads = True

    allow_reuse_address = sys.platform != "win32"
    """Not on Windows, where the socket option lets a second server bind a port the first still
    listens on, so a taken ``--port`` would be shared instead of refused."""

    def __init__(self, api: Api, static: Path, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.api = api
        self.static = static.resolve()
        self.token = secrets.token_urlsafe(32)

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def address(self) -> str:
        """The address to open; the token in it is what the cookie is given for."""
        return f"http://127.0.0.1:{self.port}/open?token={self.token}"

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A page that went away mid-answer - a reload, a closed tab - is not an error to print."""
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - the name the base class dispatches GET to
        self._answer("GET")

    def do_POST(self) -> None:  # noqa: N802 - the name the base class dispatches POST to
        self._answer("POST")

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: a request log in the terminal would bury the one line that matters."""

    @property
    def _gui(self) -> GuiServer:
        return cast(GuiServer, self.server)

    def _answer(self, method: str) -> None:
        port = self._gui.port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self._send(421, b"misdirected request", CONTENT_TYPES[".txt"])
            return
        url = urlsplit(self.path)
        if method == "GET" and url.path == "/open":
            self._sign_in(parse_qs(url.query))
            return
        api = url.path.startswith("/api/")
        if not self._signed_in():
            if api:
                self._send_json(401, {"error": "unauthorised", "message": _SIGN_IN})
            else:
                self._send(401, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        if method == "POST" and not self._from_this_page():
            self._send_json(403, {"error": "forbidden", "message": _FORBIDDEN})
            return
        if not api:
            if method == "GET":
                self._page(url.path)
            else:
                self._send_json(405, {"error": "method-not-allowed", "message": _PAGES_ARE_READ})
            return
        body = None
        if method == "POST":
            body = self._body()
            if body is None:
                return
        reply = self._gui.api.handle(method, url.path, parse_qs(url.query), body)
        self._send_json(reply.status, reply.body)

    def _sign_in(self, query: dict[str, list[str]]) -> None:
        given = (query.get("token") or [""])[0]
        if not secrets.compare_digest(given.encode("utf-8"), self._gui.token.encode("utf-8")):
            self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        target = "/project" if self._gui.api.session.revision is not None else "/"
        cookie = f"{COOKIE}={self._gui.token}; HttpOnly; SameSite=Strict; Path=/"
        self._send(303, b"", CONTENT_TYPES[".txt"], {"Location": target, "Set-Cookie": cookie})

    def _signed_in(self) -> bool:
        cookies: SimpleCookie = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        morsel = cookies.get(COOKIE)
        return morsel is not None and secrets.compare_digest(
            morsel.value.encode("utf-8"), self._gui.token.encode("utf-8")
        )

    def _from_this_page(self) -> bool:
        port = self._gui.port
        origin = self.headers.get("Origin")
        kind = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        own = (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
        return origin in own and kind == "application/json"

    def _body(self) -> bytes | None:
        length = self.headers.get("Content-Length", "0")
        if not (length.isascii() and length.isdecimal()):
            self._send_json(400, {"error": "bad-request", "message": "Content-Length is no length"})
            return None
        if int(length) > MAX_BODY:
            message = f"a request body is at most {MAX_BODY} bytes"
            self._send_json(413, {"error": "too-large", "message": message})
            return None
        return self.rfile.read(int(length))

    def _page(self, path: str) -> None:
        static = self._gui.static
        requested = (static / unquote(path).lstrip("/")).resolve()
        target = (
            requested
            if requested.is_relative_to(static) and requested.is_file()
            else static / "index.html"
        )
        kind = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), kind)

    def _send(
        self, status: int, data: bytes, kind: str, headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        for name, value in {**SECURITY_HEADERS, **(headers or {})}.items():
            self.send_header(name, value)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self._send(status, data, CONTENT_TYPES[".json"], {"Cache-Control": "no-store"})


_SIGN_IN: Final = "open the address ddd gui printed in its terminal"
_FORBIDDEN: Final = "only this server's own page may change anything, and only as json"
_PAGES_ARE_READ: Final = "pages are read with GET"


def run(
    project: Path | None,
    build_directories: Sequence[Path],
    port: int,
    *,
    open_browser: bool,
    static: Path | None = None,
) -> int:
    """Serve until interrupted; the exit code of ``ddd gui``."""
    pages = static_directory() if static is None else static
    if not (pages / "index.html").is_file():
        print(
            "ddd: this installation has no compiled pages for ddd gui; build them in the gui "
            "directory of a source checkout with 'npm ci' and 'npm run build'",
            file=sys.stderr,
        )
        return EXIT_USAGE
    session = Session(Path.cwd(), build_directories)
    if project is not None:
        try:
            session.open(project)
        except ValueError as error:
            print(f"ddd: {error}", file=sys.stderr)
            return EXIT_USAGE
    try:
        server = GuiServer(Api(session, project), pages, port)
    except OSError as error:
        print(f"ddd: cannot serve on port {port}: {error}", file=sys.stderr)
        return EXIT_USAGE
    print(f"ddd gui (preview) serving {server.address}", flush=True)
    if open_browser:
        webbrowser.open(server.address)
    session.start_polling()
    try:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
    finally:
        session.stop()
        server.server_close()
    return EXIT_OK
```

`BaseHTTPRequestHandler` itself answers any method other than GET and POST with 501; nothing here needs to.

The tests for Step 1 - create `tests/test_gui_server.py`:

```python
"""The server of ddd gui, over real HTTP: who may ask, what is served, and how it starts."""

from __future__ import annotations

import http.client
import json
import socket
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

import ddd
from conftest import component, declare, project, write_tree
from ddd.cli import EXIT_OK, EXIT_USAGE
from ddd.editing import fingerprint
from ddd.gui import server as module
from ddd.gui.api import Api
from ddd.gui.server import COOKIE, MAX_BODY, GuiServer, run, static_directory
from ddd.gui.session import Session


@pytest.fixture
def pages(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>stand-in</title>", encoding="utf-8")
    (static / "app.js").write_text("export {};", encoding="utf-8")
    (static / "data.bin").write_bytes(b"\x00")
    (tmp_path / "secret.txt").write_text("not for the page", encoding="utf-8")
    return static


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    write_tree(
        tmp_path / "project",
        {
            "p.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
        },
    )
    return tmp_path / "project" / "p.ddd.json"


def serving(api: Api, static: Path) -> Iterator[GuiServer]:
    server = GuiServer(api, static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def server(project_file: Path, pages: Path) -> Iterator[GuiServer]:
    session = Session(project_file.parent)
    session.open(project_file)
    yield from serving(Api(session, project_file, wait_seconds=0.05), pages)


def ask(
    server: GuiServer,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    host: str | None = None,
    origin: str | None = None,
    signed_in: bool = True,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> tuple[http.client.HTTPResponse, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    sent = {"Host": host or f"127.0.0.1:{server.port}"}
    if signed_in:
        sent["Cookie"] = f"{COOKIE}={server.token}"
    if origin is not None:
        sent["Origin"] = origin
    if body is not None:
        sent["Content-Type"] = content_type
    sent.update(headers or {})
    connection.request(method, path, body=body, headers=sent)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


class TestSigningIn:
    def test_the_token_is_swapped_for_a_strict_cookie_and_the_project_page(self, server) -> None:
        response, _ = ask(server, "GET", f"/open?token={server.token}", signed_in=False)
        assert response.status == 303
        assert response.getheader("Location") == "/project"
        assert response.getheader("Set-Cookie") == (
            f"{COOKIE}={server.token}; HttpOnly; SameSite=Strict; Path=/"
        )

    def test_without_an_open_project_the_redirect_is_to_the_start_page(
        self, project_file, pages
    ) -> None:
        for started in serving(Api(Session(project_file.parent)), pages):
            response, _ = ask(started, "GET", f"/open?token={started.token}", signed_in=False)
            assert response.getheader("Location") == "/"

    @pytest.mark.parametrize("query", ["", "?token=wrong", "?token=%C3%A9"])
    def test_a_wrong_or_missing_token_is_refused(self, server, query) -> None:
        response, data = ask(server, "GET", f"/open{query}", signed_in=False)
        assert response.status == 403
        assert b"Open the address" in data

    def test_the_api_without_the_cookie_is_unauthorised(self, server) -> None:
        response, data = ask(server, "GET", "/api/session", signed_in=False)
        assert response.status == 401
        assert json.loads(data)["error"] == "unauthorised"

    def test_a_page_without_the_cookie_says_where_to_sign_in(self, server) -> None:
        response, data = ask(server, "GET", "/", signed_in=False)
        assert (response.status, b"Open the address" in data) == (401, True)

    def test_a_cookie_with_another_value_is_not_signed_in(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", signed_in=False, headers={"Cookie": f"{COOKIE}=forged"}
        )
        assert response.status == 401


class TestWhoMayAsk:
    def test_a_foreign_host_is_refused(self, server) -> None:
        response, _ = ask(server, "GET", "/api/session", host=f"evil.example:{server.port}")
        assert response.status == 421

    def test_localhost_is_this_server_too(self, server) -> None:
        response, _ = ask(server, "GET", "/api/session", host=f"localhost:{server.port}")
        assert response.status == 200

    @pytest.mark.parametrize(
        ("origin", "content_type"),
        [
            (None, "application/json"),
            ("http://evil.example", "application/json"),
            ("http://127.0.0.1:1", "application/json"),
            ("OWN", "text/plain"),
        ],
    )
    def test_a_change_from_anywhere_but_this_page_is_forbidden(
        self, server, origin, content_type
    ) -> None:
        own = f"http://127.0.0.1:{server.port}"
        response, data = ask(
            server,
            "POST",
            "/api/open",
            body=b"{}",
            origin=own if origin == "OWN" else origin,
            content_type=content_type,
        )
        assert (response.status, json.loads(data)["error"]) == (403, "forbidden")

    def test_a_change_from_this_page_is_answered(self, server) -> None:
        response, _ = ask(
            server,
            "POST",
            "/api/open",
            body=b"{}",
            origin=f"http://localhost:{server.port}",
            content_type="application/json; charset=utf-8",
        )
        assert response.status == 400  # reached the API, which wants a path

    def test_a_body_larger_than_allowed_is_refused(self, server) -> None:
        response, _ = ask(
            server,
            "POST",
            "/api/edit",
            body=b"{}",
            origin=f"http://127.0.0.1:{server.port}",
            headers={"Content-Length": str(MAX_BODY + 1)},
        )
        assert response.status == 413

    def test_a_length_that_is_not_one_is_a_bad_request(self, server) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        connection.putrequest("POST", "/api/edit", skip_host=True)
        connection.putheader("Host", f"127.0.0.1:{server.port}")
        connection.putheader("Cookie", f"{COOKIE}={server.token}")
        connection.putheader("Origin", f"http://127.0.0.1:{server.port}")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "ten")
        connection.endheaders()
        assert connection.getresponse().status == 400
        connection.close()


class TestWhatIsServed:
    def test_every_response_carries_the_security_headers(self, server) -> None:
        for method, path in (("GET", "/"), ("GET", "/api/session"), ("GET", "/api/nothing")):
            response, _ = ask(server, method, path)
            policy = response.getheader("Content-Security-Policy")
            assert policy is not None and "frame-ancestors 'none'" in policy
            assert response.getheader("X-Content-Type-Options") == "nosniff"
            assert response.getheader("Referrer-Policy") == "no-referrer"

    def test_the_api_is_never_cached_and_the_pages_are_not_told_so(self, server) -> None:
        assert ask(server, "GET", "/api/session")[0].getheader("Cache-Control") == "no-store"
        assert ask(server, "GET", "/")[0].getheader("Cache-Control") is None

    @pytest.mark.parametrize(
        ("path", "kind", "text"),
        [
            ("/", "text/html; charset=utf-8", b"stand-in"),
            ("/app.js", "text/javascript; charset=utf-8", b"export {};"),
            ("/data.bin", "application/octet-stream", b"\x00"),
            ("/project", "text/html; charset=utf-8", b"stand-in"),
            ("/../secret.txt", "text/html; charset=utf-8", b"stand-in"),
            ("/%2e%2e/secret.txt", "text/html; charset=utf-8", b"stand-in"),
        ],
    )
    def test_a_page_is_served_with_its_own_content_type_or_the_index(
        self, server, path, kind, text
    ) -> None:
        response, data = ask(server, "GET", path)
        assert (response.status, response.getheader("Content-Type"), data) == (200, kind, text)

    def test_a_page_is_not_posted_to(self, server) -> None:
        response, _ = ask(
            server, "POST", "/project", body=b"{}", origin=f"http://127.0.0.1:{server.port}"
        )
        assert response.status == 405

    def test_an_edit_goes_all_the_way_to_the_file(self, server, project_file) -> None:
        target = project_file.parent / "a.ddd.json"
        before = target.read_bytes()
        edit = {
            "changes": [
                {
                    "file": target.as_posix(),
                    "fingerprint": fingerprint(before),
                    "operations": [
                        {
                            "op": "set",
                            "pointer": "component.interface[0].definition.unit",
                            "raw": '"Hz"',
                        }
                    ],
                }
            ]
        }
        response, data = ask(
            server,
            "POST",
            "/api/edit",
            body=json.dumps(edit).encode("utf-8"),
            origin=f"http://127.0.0.1:{server.port}",
        )
        assert response.status == 200, data
        assert target.read_bytes() == before.replace(b'"unit": "rpm"', b'"unit": "Hz"')

    def test_a_page_that_went_away_mid_answer_is_not_reported(self, server, capsys) -> None:
        try:
            raise ConnectionResetError("the tab was closed")
        except ConnectionResetError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""

    def test_any_other_failure_of_a_request_is_reported(self, server, capsys) -> None:
        try:
            raise ValueError("a defect")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert "ValueError: a defect" in capsys.readouterr().err

    def test_the_installed_pages_are_looked_for_beside_the_package(self) -> None:
        assert static_directory() == Path(ddd.__file__).parent / "gui" / "static"


class TestRunning:
    def test_an_installation_without_compiled_pages_is_a_usage_error(self, tmp_path, capsys) -> None:
        assert run(None, [], 0, open_browser=False, static=tmp_path) == EXIT_USAGE
        assert "npm run build" in capsys.readouterr().err

    def test_a_file_that_is_not_a_project_is_a_usage_error(self, project_file, pages, capsys) -> None:
        result = run(project_file.parent / "a.ddd.json", [], 0, open_browser=False, static=pages)
        assert result == EXIT_USAGE
        assert "is not a project description" in capsys.readouterr().err

    def test_a_taken_port_is_a_usage_error(self, pages, capsys) -> None:
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen()
            port = taken.getsockname()[1]
            assert run(None, [], port, open_browser=False, static=pages) == EXIT_USAGE
        assert f"cannot serve on port {port}" in capsys.readouterr().err

    @pytest.mark.parametrize("open_browser", [True, False])
    def test_it_prints_its_address_serves_and_exits_cleanly_when_interrupted(
        self, project_file, pages, monkeypatch, capsys, open_browser
    ) -> None:
        opened: list[str] = []
        stopped: list[bool] = []
        monkeypatch.setattr(module.webbrowser, "open", opened.append)
        monkeypatch.setattr(Session, "start_polling", lambda self: None)
        monkeypatch.setattr(Session, "stop", lambda self: stopped.append(True))

        def interrupted(self, poll_interval=0.5):
            raise KeyboardInterrupt

        monkeypatch.setattr(GuiServer, "serve_forever", interrupted)
        assert run(project_file, [], 0, open_browser=open_browser, static=pages) == EXIT_OK
        (line,) = capsys.readouterr().out.splitlines()
        assert line.startswith("ddd gui (preview) serving http://127.0.0.1:")
        assert "/open?token=" in line
        assert opened == ([line.rsplit(" ", 1)[1]] if open_browser else [])
        assert stopped == [True]

    def test_a_server_shut_down_from_elsewhere_also_ends_cleanly(
        self, pages, monkeypatch
    ) -> None:
        monkeypatch.setattr(GuiServer, "serve_forever", lambda self, poll_interval=0.5: None)
        assert run(None, [], 0, open_browser=False, static=pages) == EXIT_OK


def test_the_windows_server_does_not_share_a_port() -> None:
    assert GuiServer.allow_reuse_address is (sys.platform != "win32")
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_gui_server.py --no-cov`
Expected: all pass. `/%2e%2e/secret.txt` reaches the server percent-encoded, is unquoted to `../secret.txt` and resolves outside `static`, so the index is served.

- [ ] **Step 5: Coverage, style, types**

Run: `python -m pytest tests/test_gui_server.py tests/test_gui_api.py tests/test_gui_session.py --cov=ddd.gui --cov-branch --cov-report=term-missing --cov-fail-under=0`, then `python -m ruff format src tests`, `python -m ruff check .`, `python -m mypy`
Expected: all of `ddd/gui` at 100 %; no findings. If mypy asks for a type argument on `SimpleCookie`, annotate `cookies: SimpleCookie = SimpleCookie()` as mypy's message suggests for the installed typeshed.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/gui/server.py tests/test_gui_server.py
git commit -m "serve the pages and the api on the loopback address to the browser that was given the token, and nobody else" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 9: The command and its documentation

**Files:**
- Modify: `src/ddd/cli.py`
- Modify: `README.md`, `SPEC.md`, `docs/command_line_interface.rst`, `CHANGELOG.md`
- Test: `tests/test_cli.py`, `tests/test_documentation.py`

**Interfaces:**
- Consumes: Task 8's `ddd.gui.server.run(project, build_directories, port, *, open_browser, static=None) -> int`.
- Produces: `ddd gui [PROJECT] [-b DIR]... [--port N] [--no-browser]`; `_port(text: str) -> int` in `ddd.cli`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py` (`EXIT_OK`, `EXIT_USAGE`, `main`, `Path`, `pytest` are already imported there):

```python
class TestGui:
    """The command only hands its options to the server; tests/test_gui_server.py runs it."""

    @staticmethod
    def recorder(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
        seen: dict[str, object] = {}

        def run(project, build_directories, port, *, open_browser, static=None):
            seen.update(
                project=project,
                build_directories=build_directories,
                port=port,
                open_browser=open_browser,
            )
            return EXIT_OK

        monkeypatch.setattr("ddd.gui.server.run", run)
        return seen

    def test_the_options_reach_the_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = self.recorder(monkeypatch)
        arguments = ["gui", "p.ddd.json", "-b", "build", "--port", "8123", "--no-browser"]
        assert main(arguments) == EXIT_OK
        assert seen == {
            "project": Path("p.ddd.json"),
            "build_directories": [Path("build")],
            "port": 8123,
            "open_browser": False,
        }

    def test_by_default_the_system_picks_the_port_and_the_browser_is_opened(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self.recorder(monkeypatch)
        assert main(["gui"]) == EXIT_OK
        assert seen == {"project": None, "build_directories": [], "port": 0, "open_browser": True}

    @pytest.mark.parametrize("port", ["-1", "65536", "http", "٣"])
    def test_a_port_that_is_not_one_is_a_usage_error(
        self, port: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exited:
            main(["gui", "--port", port])
        assert exited.value.code == EXIT_USAGE
        assert "is not a port number from 0 to 65535" in capsys.readouterr().err
```

In `tests/test_documentation.py`, add `"gui",` to the set in `test_the_parser_offers_the_commands_this_suite_knows_about` (after `"lsp",`).

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_cli.py -k TestGui tests/test_documentation.py -k "Commands or CommandPage" --no-cov`
Expected: FAIL - `argument command: invalid choice: 'gui'`, and the documentation tests fail on the known-command set.

- [ ] **Step 3: Add the command**

In `src/ddd/cli.py`, in `_build_parser`, directly after `lsp.set_defaults(handler=_command_lsp)`, add:

```python
    gui = subparsers.add_parser(
        "gui",
        help="preview: edit a project's description files in a browser, on this computer only",
        description=(
            "Preview. Serves a browser interface over one project's description files on the "
            "loopback address of this computer, and opens the browser on it. Every change is "
            "written into the description files in their own layout and checked with the same "
            "analysis as ddd check. It runs until it is interrupted, and its options are not "
            "yet part of the stable interface."
        ),
    )
    gui.add_argument(
        "project",
        nargs="?",
        type=Path,
        metavar="PROJECT",
        help=(
            "the project description to open; without it the start page lists the projects "
            "found under the current directory"
        ),
    )
    gui.add_argument(
        "-b",
        "--build-directory",
        type=Path,
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "directory holding a build of the project, whose severities apply; repeatable. "
            "Without it the usual build directory names are searched"
        ),
    )
    gui.add_argument(
        "--port",
        type=_port,
        default=0,
        metavar="N",
        help="port to serve on; the default, 0, lets the system pick a free one",
    )
    gui.add_argument(
        "--no-browser",
        action="store_true",
        help="print the address without opening a browser on it",
    )
    gui.set_defaults(handler=_command_gui)
```

After `_command_lsp`, add:

```python
def _command_gui(args: argparse.Namespace) -> int:
    # Imported here, like the language server: the server brings up the loader, the analysis
    # and the edit engine, which no other command should pay for.
    from ddd.gui.server import run

    return int(
        run(args.project, args.build_directory, args.port, open_browser=not args.no_browser)
    )


def _port(text: str) -> int:
    """A port to serve on: a number from 0, which lets the system pick one, to 65535."""
    if not (text.isascii() and text.isdecimal()) or int(text) > 65535:
        raise argparse.ArgumentTypeError(f"{text!r} is not a port number from 0 to 65535")
    return int(text)
```

(`"-1"` is not decimal, so the lower bound needs no comparison of its own.)

- [ ] **Step 4: Document it**

1. `README.md`, in the table under `## Command line`, directly after the `ddd lsp` row, add:

```markdown
| `ddd gui [PROJECT]` | preview: a browser interface over one project's description files, on this computer only; a change is written into the files in their own layout and checked the way `ddd check` checks it |
```

2. `SPEC.md`, section 7: after `Protocol (`ddd lsp`, [section 7.2](#72-editor-integration));` insert the clause below, and re-wrap the paragraph to the width of its neighbours:

```markdown
editing a project's description files in a browser on the developer's own computer (`ddd gui`,
a preview whose options are not yet part of this interface);
```

3. `docs/command_line_interface.rst`:
   - Replace the sentence beginning "The one command that does not exit is ``ddd lsp``" (it runs to "writes for that server.") with:

```rst
Two commands do not exit: ``ddd lsp``, the language server an editor keeps running (see
:doc:`editor_integration`), and ``ddd gui``, the preview of a browser interface, which serves
until it is interrupted. The one file the tool leaves behind for its own use is the
``ddd-build.json`` that ``ddd build-info`` writes for the language server.
```

   - In the sentence "That leaves out ...", after "``lsp``, which speaks json-rpc," insert " ``gui``, which serves pages to a browser,".
   - In the command table, directly after the ``ddd lsp`` row, add:

```rst
   * - ``ddd gui [PROJECT]``
     - preview: serve a browser interface over one project's description files, on this
       computer only, and open the browser on it. Every change is written into the files in
       their own layout and checked the way ``ddd check`` checks them. ``-b DIR`` names a build
       directory as for ``ddd lsp``, ``--port N`` fixes the port and ``--no-browser`` only
       prints the address. It serves until interrupted, and its options are not yet part of
       the stable interface.
```

4. `CHANGELOG.md`: insert above `## 0.10.0`:

```markdown
## Unreleased

* **A browser interface, as a preview.**  `ddd gui` serves a browser interface over one
  project's description files on the developer's own computer and opens the browser on it:
  the project's components, the findings of each, and a declaration's unit changed in place -
  written into the file as a one-line change and checked the way `ddd check` checks it.  It is
  the first step of a GUI for developers who would rather not edit JSON, and its options are
  not yet part of the public interface.

```

5. `tests/test_documentation.py`, `class TestTheReleaseNote`: the three tests require the topmost note to *make* three claims that belong to the 0.10.0 note, so an `## Unreleased` section breaks them. Hold the note to the claims it makes instead. Replace the class docstring's last sentence with "A note is held to every claim it makes rather than required to make it: the note after a release starts with whatever its first change says.", and the three test bodies with:

```python
    def test_it_counts_the_checks_needing_every_component_as_the_registry_does(self) -> None:
        for word in project_wide_counts(UNRELEASED):
            assert NUMBER_WORDS[word.lower()] == len(project_wide_checks()), (
                f"the release note says {word} checks need every component of a project, and "
                f"{len(project_wide_checks())} do"
            )

    def test_it_counts_the_entries_the_review_of_the_whole_tool_wrote(self) -> None:
        entries = [line for line in UNRELEASED.splitlines() if line.startswith("* **")]
        found = sum(1 for entry in UNRELEASED.split("\n* **")[1:] if REVIEW_PHRASE in entry)
        stated = re.search(
            r"the (\w+) entries that follow are what that review found", flattened(UNRELEASED)
        )
        if stated is None:
            assert found == 0, "entries say they answer the review, and the note does not count them"
            return
        assert NUMBER_WORDS[stated.group(1)] == found, (
            f"the release note says {stated.group(1)} of its {len(entries)} entries come from "
            f"the review, and {found} of them say so"
        )

    def test_it_states_the_format_of_the_dictionary_it_ships(self) -> None:
        """Three entries tell a reader which format to expect; one bump makes all three wrong."""
        from ddd.ir import DICTIONARY_FORMAT

        stated = re.findall(
            r"(?:dictionary (?:is|stays)|still) format (\d+)", flattened(UNRELEASED)
        )
        assert {int(number) for number in stated} <= {DICTIONARY_FORMAT}, (
            f"the release note announces dictionary format {sorted(set(stated))}, and the "
            f"tool writes {DICTIONARY_FORMAT}"
        )
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_cli.py tests/test_documentation.py tests/test_transcripts.py --no-cov` (from Git Bash)
Expected: all pass. `test_no_help_string_carries_markup_characters` passes because the help strings contain no `*`, backtick or `|`.

- [ ] **Step 6: Build the documentation**

Run (Git Bash, with `JAVA` and `PLANTUML_JAR` set as the local toolchain note says): `python -m sphinx -M html docs "$SCRATCH/docs_out" -W`
Expected: `build succeeded`, with `ddd gui` in the generated command-line reference.

- [ ] **Step 7: Full Python gate**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`
Expected: green, 100 %.

- [ ] **Step 8: Commit and push**

```bash
git add src/ddd/cli.py tests/test_cli.py tests/test_documentation.py README.md SPEC.md docs/command_line_interface.rst CHANGELOG.md
git commit -m "offer ddd gui as a preview command, and say so wherever the commands are listed" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 10: The frontend project and its logic modules

**Requires Node.js 24.15 or newer** (see Prerequisites). All commands of this task run in `gui/` unless stated.

**Files:**
- Modify: `.gitignore`
- Create: `gui/package.json`, `gui/package-lock.json` (generated by npm), `gui/tsconfig.json`, `gui/vite.config.ts`, `gui/biome.json`, `gui/index.html`
- Create: `gui/scripts/schemas.mjs`, `gui/scripts/licenses.mjs`
- Create: `gui/src/main.tsx` (a placeholder Task 11 replaces), `gui/src/vite-env.d.ts`
- Create: `gui/src/api/types.ts`, `gui/src/api/client.ts`, `gui/src/api/client.test.ts`
- Create: `gui/src/lib/pointer.ts`, `gui/src/lib/pointer.test.ts`, `gui/src/lib/values.ts`, `gui/src/lib/values.test.ts`, `gui/src/lib/edits.ts`, `gui/src/lib/edits.test.ts`, `gui/src/lib/route.ts`, `gui/src/lib/route.test.ts`, `gui/src/lib/formats.ts`
- Create: `gui/src/state/revisions.ts`, `gui/src/state/revisions.test.ts`
- Create: `gui/src/census.test.ts`

**Interfaces:**
- Consumes: the JSON shapes of Task 7; `ddd schema all -o DIR` (installed package); the compiled pages directory `src/ddd/gui/static/` of Task 8.
- Produces (TypeScript, used by Tasks 11 and 12):
  - `src/api/types.ts`: `SessionInfo`, `FoundProject`, `Found`, `Severity`, `Note`, `Finding`, `SourceFile`, `State`, `FileContent`, `Operation`, `Change`, `Changes`, `EditReply`
  - `src/api/client.ts`: `class ApiError extends Error { status: number; code: string }`, `class ServerUnreachable extends Error`, `request<T>(path, init?, fetchImpl?)`, `getSession(fetchImpl?)`, `getProjects(fetchImpl?)`, `openProject(path, fetchImpl?)`, `getState(after: number | null, signal?: AbortSignal, fetchImpl?)`, `getFile(path, fetchImpl?)`, `postEdit(changes, fetchImpl?)`
  - `src/lib/pointer.ts`: `segments(pointer): (string | number)[]`, `pointerOf(parts): string`, `valueAt(data: unknown, pointer: string): unknown`, `within(pointer: string, entry: string): boolean`
  - `src/lib/values.ts`: `asText(value: unknown): string | undefined`, `asList(value: unknown): readonly unknown[]`
  - `src/lib/edits.ts`: `jsonText(text: string): string`, `setValue(file, fingerprint, pointer, raw): Changes`
  - `src/lib/route.ts`: `type Route = { page: "start" } | { page: "project" } | { page: "component"; file: string }`, `parseRoute(pathname: string, search: string): Route`, `hrefOf(route: Route): string`
  - `src/lib/formats.ts`: `type ComponentFile` (the generated root type of the component schema)
  - `src/state/revisions.ts`: `interface Follow`, `followRevisions(follow: Follow): Promise<void>`, `wait(ms: number, signal: AbortSignal): Promise<void>`
  - npm scripts: `schemas`, `typecheck`, `lint`, `format`, `test`, `build`, `watch`, `e2e`

- [ ] **Step 1: Ignore what the frontend generates**

Append to the repository's `.gitignore`:

```gitignore
src/ddd/gui/static/
gui/src/generated/
gui/test-results/
gui/playwright-report/
```

(`node_modules/` is already ignored everywhere.)

- [ ] **Step 2: Create the project files**

`gui/package.json`:

```json
{
  "name": "ddd-gui",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=24.15.0"
  },
  "scripts": {
    "schemas": "node scripts/schemas.mjs",
    "typecheck": "tsc --noEmit",
    "lint": "biome check .",
    "format": "biome check --write .",
    "test": "vitest run --coverage",
    "build": "vite build && node scripts/licenses.mjs",
    "watch": "vite build --watch",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@tanstack/react-query": "5.103.1",
    "react": "19.3.0",
    "react-dom": "19.3.0"
  },
  "devDependencies": {
    "@biomejs/biome": "2.5.14",
    "@playwright/test": "1.63.0",
    "@types/node": "24.13.5",
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "@vitejs/plugin-react": "6.1.1",
    "@vitest/coverage-v8": "5.0.1",
    "json-schema-to-typescript": "16.0.0",
    "typescript": "7.0.2",
    "vite": "8.3.0",
    "vitest": "5.0.1"
  }
}
```

`gui/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client", "node"]
  },
  "include": ["src", "e2e", "vite.config.ts", "playwright.config.ts"]
}
```

`gui/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The compiled pages go where the Python package serves them from; git ignores that directory
// and the wheel carries it. The coverage gate covers the modules that hold logic: the screens
// are covered end to end by Playwright (e2e/).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/ddd/gui/static",
    emptyOutDir: true,
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      include: ["src/api/**/*.ts", "src/lib/**/*.ts", "src/state/**/*.ts"],
      exclude: ["src/**/*.test.ts"],
      reporter: ["text"],
      thresholds: { 100: true },
    },
  },
});
```

`gui/biome.json`:

```json
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "files": {
    "includes": ["**", "!src/generated", "!test-results", "!playwright-report"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true }
  },
  "javascript": {
    "formatter": { "quoteStyle": "double" }
  }
}
```

If `npx biome check .` reports this configuration invalid for 2.5.14, run `npx biome migrate --write` and keep what it writes.

`gui/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ddd gui</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`gui/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

`gui/src/main.tsx` (placeholder; Task 11 replaces it):

```tsx
import { createRoot } from "react-dom/client";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");
createRoot(root).render(<p>ddd gui</p>);
```

- [ ] **Step 3: Install and lock**

Run: `npm install`
Expected: `package-lock.json` created; `npm ls --depth=0` lists exactly the versions above.

- [ ] **Step 4: Write the two scripts**

`gui/scripts/schemas.mjs`:

```js
// TypeScript types for the description files and the dictionary, generated from the json
// schemas `ddd schema all` writes, so that a change of the file formats the page has not caught
// up with fails the type check instead of reaching a user. Needs the package installed
// (`pip install -e .` at the root of the checkout); DDD names another `ddd` executable.
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compileFromFile } from "json-schema-to-typescript";

const schemas = mkdtempSync(join(tmpdir(), "ddd-schemas-"));
try {
  const ddd = process.env.DDD ?? "ddd";
  const result = spawnSync(ddd, ["schema", "all", "-o", schemas], { stdio: "inherit" });
  if (result.error !== undefined || result.status !== 0) {
    console.error(`'${ddd} schema all' failed: install the package first (pip install -e .)`);
    process.exit(1);
  }
  const target = new URL("../src/generated/", import.meta.url);
  mkdirSync(target, { recursive: true });
  for (const name of readdirSync(schemas).sort()) {
    const kind = name.replace(/^ddd_/, "").replace(/\.schema\.json$/, "");
    const source = await compileFromFile(join(schemas, name), {
      bannerComment: "/* Generated by scripts/schemas.mjs from `ddd schema all`. Do not edit. */",
      additionalProperties: false,
      style: { printWidth: 100 },
    });
    writeFileSync(new URL(`${kind}.ts`, target), source);
  }
} finally {
  rmSync(schemas, { recursive: true, force: true });
}
```

`gui/scripts/licenses.mjs`:

```js
// Writes the licence of every package bundled into the compiled pages beside them, and refuses a
// licence outside the ones this project accepts. Only production dependencies are bundled, so
// only they are listed.
import { execSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ALLOWED = new Set(["MIT", "ISC", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]);
const tree = JSON.parse(execSync("npm ls --omit=dev --all --long --json", { encoding: "utf8" }));

const packages = new Map();
const visit = (dependencies) => {
  for (const [name, entry] of Object.entries(dependencies ?? {})) {
    const key = `${name}@${entry.version}`;
    if (!packages.has(key)) {
      packages.set(key, { name, version: entry.version, path: entry.path });
      visit(entry.dependencies);
    }
  }
};
visit(tree.dependencies);

const sections = [];
const refused = [];
for (const { name, version, path } of [...packages.values()].sort((a, b) =>
  a.name.localeCompare(b.name),
)) {
  const manifest = JSON.parse(readFileSync(join(path, "package.json"), "utf8"));
  const licence = typeof manifest.license === "string" ? manifest.license : "UNKNOWN";
  if (!ALLOWED.has(licence)) refused.push(`${name}@${version}: ${licence}`);
  const file = readdirSync(path).find((entry) => /^(licen[cs]e|copying)(\.|$)/i.test(entry));
  const text = file ? readFileSync(join(path, file), "utf8").trim() : `${licence} (no licence file)`;
  sections.push(`${name} ${version}\n${licence}\n\n${text}`);
}
if (refused.length > 0) {
  console.error(`bundled packages under a licence outside ${[...ALLOWED].join(", ")}:`);
  for (const entry of refused) console.error(`  ${entry}`);
  process.exit(1);
}
const out = join("..", "src", "ddd", "gui", "static", "third-party-licenses.txt");
writeFileSync(out, `${sections.join("\n\n----------------------------------------\n\n")}\n`);
console.log(`wrote the licences of ${sections.length} bundled packages to ${out}`);
```

(`execSync` runs through the shell, which is what finds `npm.cmd` on Windows; the command line is fixed text.)

- [ ] **Step 5: Generate the types and check the root type's name**

Run (with the venv's `ddd` on the PATH): `npm run schemas`
Expected: `src/generated/component.ts`, `constants.ts`, `dictionary.ts`, `project.ts`, `rasters.ts`, `sections.ts`, `types.ts`, `units.ts`. Open `src/generated/component.ts` and find the exported type generated from the schema title `DDD component description`: json-schema-to-typescript names it `DDDComponentDescription`. If the file names it otherwise, use that name in Step 6's `formats.ts`.

- [ ] **Step 6: Write the failing tests of the logic modules**

`gui/src/lib/pointer.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { pointerOf, segments, valueAt, within } from "./pointer";

describe("pointers, spelled the way ddd reports them", () => {
  test.each([
    ["a.b[2].c", ["a", "b", 2, "c"]],
    ["component.interface[10].definition", ["component", "interface", 10, "definition"]],
    ["[0]", [0]],
    ["", []],
  ])("%s has the segments ddd.lsp.ranges.segments gives it", (pointer, parts) => {
    expect(segments(pointer)).toEqual(parts);
    expect(pointerOf(parts)).toBe(pointer);
  });

  test("a value is read at a pointer, and undefined where nothing is written", () => {
    const data = { component: { interface: [{ definition: { unit: "rpm" } }] } };
    expect(valueAt(data, "component.interface[0].definition.unit")).toBe("rpm");
    expect(valueAt(data, "")).toBe(data);
    expect(valueAt(data, "component.interface[1].definition")).toBeUndefined();
    expect(valueAt(data, "component[0]")).toBeUndefined();
    expect(valueAt(data, "component.interface.name")).toBeUndefined();
    expect(valueAt(data, "component.toString")).toBeUndefined();
    expect(valueAt(null, "a")).toBeUndefined();
  });

  test("a finding belongs to the entry it is at or inside", () => {
    expect(within("component.interface[0].definition", "component.interface[0]")).toBe(true);
    expect(within("component.interface[0]", "component.interface[0]")).toBe(true);
    expect(within("component.interface[0][1]", "component.interface[0]")).toBe(true);
    expect(within("component.interface[01]", "component.interface[0]")).toBe(false);
    expect(within("component.interface[10]", "component.interface[1]")).toBe(false);
  });
});
```

`gui/src/lib/values.test.ts`:

```ts
import { expect, test } from "vitest";
import { asList, asText } from "./values";

test("text is text, anything else is undefined", () => {
  expect(asText("rpm")).toBe("rpm");
  expect(asText(7)).toBeUndefined();
});

test("a list is a list, anything else is empty", () => {
  expect(asList([1, 2])).toEqual([1, 2]);
  expect(asList({ 0: 1 })).toEqual([]);
});
```

`gui/src/lib/edits.test.ts`:

```ts
import { expect, test } from "vitest";
import { jsonText, setValue } from "./edits";

test("a string travels as its json text", () => {
  expect(jsonText('say "hi"')).toBe('"say \\"hi\\""');
});

test("setting one value is one change with one operation", () => {
  expect(setValue("/p/a.ddd.json", "abc", "component.name", '"A"')).toEqual({
    changes: [
      {
        file: "/p/a.ddd.json",
        fingerprint: "abc",
        operations: [{ op: "set", pointer: "component.name", raw: '"A"' }],
      },
    ],
  });
});
```

`gui/src/lib/route.test.ts`:

```ts
import { expect, test } from "vitest";
import { hrefOf, parseRoute } from "./route";

test.each([
  ["/", "", { page: "start" }],
  ["/project", "", { page: "project" }],
  ["/component", "?file=C%3A%2Fp%2Fa.ddd.json", { page: "component", file: "C:/p/a.ddd.json" }],
  ["/component", "", { page: "start" }],
  ["/elsewhere", "", { page: "start" }],
] as const)("%s%s is the %o page", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "start" }, "/"],
  [{ page: "project" }, "/project"],
  [{ page: "component", file: "C:/p/a b.ddd.json" }, "/component?file=C%3A%2Fp%2Fa%20b.ddd.json"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});
```

`gui/src/api/client.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  ApiError,
  getFile,
  getProjects,
  getSession,
  getState,
  openProject,
  postEdit,
  request,
  ServerUnreachable,
} from "./client";

function answering(status: number, body: string) {
  return vi.fn(async (_path: string, _init?: RequestInit) => new Response(body, { status }));
}

describe("requests to the server", () => {
  test("a success is its parsed body, asked for with the page's own cookie", async () => {
    const fetchImpl = answering(200, '{"version": "0.10.0"}');
    await expect(request("/api/session", {}, fetchImpl)).resolves.toEqual({ version: "0.10.0" });
    expect(fetchImpl).toHaveBeenCalledWith("/api/session", { credentials: "same-origin" });
  });

  test("a refusal carries the code and message the server gave", async () => {
    const refused = request("/api/edit", {}, answering(409, '{"error": "stale", "message": "changed"}'));
    await expect(refused).rejects.toMatchObject({ status: 409, code: "stale", message: "changed" });
    await expect(refused).rejects.toBeInstanceOf(ApiError);
  });

  test("a failure without the server's error shape is named by its status", async () => {
    const failed = request("/api/state", {}, answering(502, "Bad Gateway"));
    await expect(failed).rejects.toMatchObject({ status: 502, code: "http-502" });
  });

  test("a server that does not answer is unreachable", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toBeInstanceOf(ServerUnreachable);
  });

  test("an aborted request stays aborted", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    await expect(request("/api/state", {}, fetchImpl)).rejects.toMatchObject({ name: "AbortError" });
  });

  test("each call asks the path and method the api expects", async () => {
    const fetchImpl = answering(200, "{}");
    const signal = new AbortController().signal;
    await getSession(fetchImpl);
    await getProjects(fetchImpl);
    await openProject("C:/p/p.ddd.json", fetchImpl);
    await getState(null, undefined, fetchImpl);
    await getState(3, signal, fetchImpl);
    await getFile("C:/p/a b.ddd.json", fetchImpl);
    await postEdit({ changes: [] }, fetchImpl);
    expect(fetchImpl.mock.calls).toEqual([
      ["/api/session", { credentials: "same-origin" }],
      ["/api/projects", { credentials: "same-origin" }],
      [
        "/api/open",
        {
          credentials: "same-origin",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"path":"C:/p/p.ddd.json"}',
        },
      ],
      ["/api/state", { credentials: "same-origin" }],
      ["/api/state?after=3", { credentials: "same-origin", signal }],
      ["/api/file?path=C%3A%2Fp%2Fa%20b.ddd.json", { credentials: "same-origin" }],
      [
        "/api/edit",
        {
          credentials: "same-origin",
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"changes":[]}',
        },
      ],
    ]);
  });
});
```

`gui/src/state/revisions.test.ts`:

```ts
import { expect, test, vi } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import type { State } from "../api/types";
import { followRevisions, wait } from "./revisions";

const state = (revision: number): State => ({ revision, project: "/p.ddd.json", files: [], findings: [] });
const aborted = () => new DOMException("aborted", "AbortError");

test("each newer revision is handed on once, and the next request asks for anything newer", async () => {
  const controller = new AbortController();
  const answers = [state(1), state(1), state(2)];
  const asked: (number | null)[] = [];
  const seen: number[] = [];
  await followRevisions({
    getState: async (after) => {
      asked.push(after);
      const next = answers.shift();
      if (next === undefined) {
        controller.abort();
        throw aborted();
      }
      return next;
    },
    onState: (current) => seen.push(current.revision),
    onStopped: () => {
      throw new Error("the server never stopped");
    },
    signal: controller.signal,
  });
  expect(seen).toEqual([1, 2]);
  expect(asked).toEqual([null, 1, 1, 2]);
});

test("a server that stops answering is reported once, retried, and reported back", async () => {
  const controller = new AbortController();
  const reports: boolean[] = [];
  const sleeps: number[] = [];
  let calls = 0;
  await followRevisions({
    getState: async () => {
      calls += 1;
      if (calls <= 2) throw new ServerUnreachable(new TypeError("fetch failed"));
      if (calls === 3) return state(4);
      controller.abort();
      throw aborted();
    },
    onState: () => {},
    onStopped: (stopped) => reports.push(stopped),
    signal: controller.signal,
    retryMs: 5,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
  });
  expect(reports).toEqual([true, false]);
  expect(sleeps).toEqual([5, 5]);
});

test("by default the retry waits on the follow's own signal", async () => {
  const controller = new AbortController();
  await followRevisions({
    getState: async () => {
      throw new ServerUnreachable(new TypeError("fetch failed"));
    },
    onState: () => {},
    onStopped: () => controller.abort(),
    signal: controller.signal,
  });
  expect(controller.signal.aborted).toBe(true);
});

test("any other failure ends the follow with that failure", async () => {
  const follow = followRevisions({
    getState: async () => {
      throw new ApiError(409, "no-project", "no project is open");
    },
    onState: () => {},
    onStopped: () => {},
    signal: new AbortController().signal,
  });
  await expect(follow).rejects.toThrow("no project is open");
});

test("a follow aborted before it starts asks nothing", async () => {
  const controller = new AbortController();
  controller.abort();
  const getState = vi.fn();
  await followRevisions({ getState, onState: () => {}, onStopped: () => {}, signal: controller.signal });
  expect(getState).not.toHaveBeenCalled();
});

test("wait ends after its delay, when aborted, or at once when already aborted", async () => {
  vi.useFakeTimers();
  try {
    const controller = new AbortController();
    const timed = wait(1000, controller.signal);
    await vi.advanceTimersByTimeAsync(1000);
    await timed;
    const interrupted = wait(1000, controller.signal);
    controller.abort();
    await interrupted;
    await wait(1000, controller.signal);
  } finally {
    vi.useRealTimers();
  }
});
```

`gui/src/census.test.ts`:

```ts
import { expect, test } from "vitest";

// Every logic module is imported, so the coverage gate also sees a module no test touches.
const modules = import.meta.glob(["./api/*.ts", "./lib/*.ts", "./state/*.ts", "!./**/*.test.ts"], {
  eager: true,
});

test("every logic module is loaded under the coverage gate", () => {
  expect(Object.keys(modules).length).toBeGreaterThanOrEqual(7);
});
```

Run: `npm test`
Expected: FAIL, the modules do not exist.

- [ ] **Step 7: Write the modules**

`gui/src/api/types.ts`:

```ts
// The JSON the server answers with (src/ddd/gui/api.py), shape for shape.

export interface SessionInfo {
  version: string;
  preview: boolean;
  root: string;
  project: { path: string; name: string | null } | null;
  builds: { image: string; strict: boolean; severity: string[] }[];
}

export interface FoundProject {
  path: string;
  name: string | null;
  images: string[];
}

export interface Found {
  root: string;
  projects: FoundProject[];
  refused: { record: string; reason: string }[];
}

export type Severity = "error" | "warning" | "info";

export interface Note {
  message: string;
  file: string | null;
  pointer: string;
}

export interface Finding {
  file: string;
  check: string;
  severity: Severity;
  message: string;
  pointer: string;
  notes: Note[];
}

export interface SourceFile {
  path: string;
  kind: string;
  name: string | null;
  loaded: boolean;
  fingerprint: string;
  findings: Record<Severity, number>;
}

export interface State {
  revision: number;
  project: string;
  files: SourceFile[];
  findings: Finding[];
}

export interface FileContent {
  path: string;
  fingerprint: string;
  data: unknown;
  error: string | null;
}

export type Operation =
  | { op: "set"; pointer: string; raw: string }
  | { op: "remove"; pointer: string }
  | { op: "insert"; pointer: string; raw: string }
  | { op: "move"; pointer: string; to: number };

export interface Change {
  file: string;
  fingerprint: string;
  operations: Operation[];
}

export interface Changes {
  changes: Change[];
}

export interface EditReply {
  revision: number;
  files: { path: string; fingerprint: string }[];
}
```

`gui/src/api/client.ts`:

```ts
import type { Changes, EditReply, FileContent, Found, SessionInfo, State } from "./types";

type Fetch = (path: string, init?: RequestInit) => Promise<Response>;

/** A refusal or a failure the server answered with, carrying its code for the page to act on. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** The server did not answer at all: it stopped, or the connection was refused. */
export class ServerUnreachable extends Error {
  constructor(cause: unknown) {
    super("ddd gui is not answering", { cause });
    this.name = "ServerUnreachable";
  }
}

export async function request<T>(path: string, init: RequestInit = {}, fetchImpl: Fetch = fetch): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(path, { credentials: "same-origin", ...init });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ServerUnreachable(error);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const code = isRecord(body) && typeof body.error === "string" ? body.error : `http-${response.status}`;
    const message = isRecord(body) && typeof body.message === "string" ? body.message : response.statusText;
    throw new ApiError(response.status, code, message);
  }
  return body as T;
}

export const getSession = (fetchImpl: Fetch = fetch) => request<SessionInfo>("/api/session", {}, fetchImpl);

export const getProjects = (fetchImpl: Fetch = fetch) => request<Found>("/api/projects", {}, fetchImpl);

export const openProject = (path: string, fetchImpl: Fetch = fetch) =>
  request<SessionInfo>("/api/open", post({ path }), fetchImpl);

export const getState = (after: number | null, signal?: AbortSignal, fetchImpl: Fetch = fetch) =>
  request<State>(
    after === null ? "/api/state" : `/api/state?after=${after}`,
    signal === undefined ? {} : { signal },
    fetchImpl,
  );

export const getFile = (path: string, fetchImpl: Fetch = fetch) =>
  request<FileContent>(`/api/file?path=${encodeURIComponent(path)}`, {}, fetchImpl);

export const postEdit = (changes: Changes, fetchImpl: Fetch = fetch) =>
  request<EditReply>("/api/edit", post(changes), fetchImpl);

function post(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
```

`gui/src/lib/pointer.ts`:

```ts
const SEGMENT = /\[(\d+)\]|([^.[\]]+)/g;

/** `a.b[2].c` -> `["a", "b", 2, "c"]`: the twin of `ddd.lsp.ranges.segments`. */
export function segments(pointer: string): (string | number)[] {
  return Array.from(pointer.matchAll(SEGMENT), (match) =>
    match[1] === undefined ? (match[2] as string) : Number(match[1]),
  );
}

/** The pointer the segments spell, the way ddd spells it. */
export function pointerOf(parts: readonly (string | number)[]): string {
  return parts.reduce<string>((pointer, part) => {
    if (typeof part === "number") return `${pointer}[${part}]`;
    return pointer === "" ? part : `${pointer}.${part}`;
  }, "");
}

/** What is written at a pointer of a parsed document, or `undefined` where nothing is. */
export function valueAt(data: unknown, pointer: string): unknown {
  let value: unknown = data;
  for (const part of segments(pointer)) {
    if (typeof part === "number") {
      if (!Array.isArray(value)) return undefined;
      value = value[part];
    } else {
      if (typeof value !== "object" || value === null || Array.isArray(value) || !Object.hasOwn(value, part)) {
        return undefined;
      }
      value = (value as Record<string, unknown>)[part];
    }
  }
  return value;
}

/** Whether a finding at `pointer` is about the entry at `entry` or about something inside it. */
export function within(pointer: string, entry: string): boolean {
  return pointer === entry || pointer.startsWith(`${entry}.`) || pointer.startsWith(`${entry}[`);
}
```

`gui/src/lib/values.ts`:

```ts
/** A string written in a description, or `undefined` for anything else. */
export function asText(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/** An array written in a description, or an empty one for anything else. */
export function asList(value: unknown): readonly unknown[] {
  return Array.isArray(value) ? value : [];
}
```

`gui/src/lib/edits.ts`:

```ts
import type { Changes } from "../api/types";

/** The json text of a string, which is how a value travels to the server. */
export function jsonText(text: string): string {
  return JSON.stringify(text);
}

/** An edit writing `raw` at one pointer of one file, as that file was read at `fingerprint`. */
export function setValue(file: string, fingerprint: string, pointer: string, raw: string): Changes {
  return { changes: [{ file, fingerprint, operations: [{ op: "set", pointer, raw }] }] };
}
```

`gui/src/lib/route.ts`:

```ts
export type Route = { page: "start" } | { page: "project" } | { page: "component"; file: string };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  if (pathname === "/project") return { page: "project" };
  const file = new URLSearchParams(search).get("file");
  if (pathname === "/component" && file) return { page: "component", file };
  return { page: "start" };
}

/** The address of a page. */
export function hrefOf(route: Route): string {
  switch (route.page) {
    case "start":
      return "/";
    case "project":
      return "/project";
    case "component":
      return `/component?file=${encodeURIComponent(route.file)}`;
  }
}
```

`gui/src/lib/formats.ts`:

```ts
import type { DDDComponentDescription } from "../generated/component";

/** A component description, as `ddd schema component` defines it. */
export type ComponentFile = DDDComponentDescription;
```

`gui/src/state/revisions.ts`:

```ts
import { ServerUnreachable } from "../api/client";
import type { State } from "../api/types";

export interface Follow {
  getState: (after: number | null, signal: AbortSignal) => Promise<State>;
  onState: (state: State) => void;
  onStopped: (stopped: boolean) => void;
  signal: AbortSignal;
  retryMs?: number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

/**
 * Keeps a page on the newest revision: asks for anything newer than the revision it has - which
 * the server answers when there is one, or after waiting - and asks again. A server that stops
 * answering is reported once and retried; when it answers again that is reported too. Any other
 * failure ends the follow with it.
 */
export async function followRevisions(follow: Follow): Promise<void> {
  const { getState, onState, onStopped, signal } = follow;
  const retryMs = follow.retryMs ?? 2000;
  const sleep = follow.sleep ?? wait;
  let after: number | null = null;
  let stopped = false;
  while (!signal.aborted) {
    try {
      const state = await getState(after, signal);
      if (stopped) {
        stopped = false;
        onStopped(false);
      }
      if (after === null || state.revision > after) onState(state);
      after = state.revision;
    } catch (error) {
      if (signal.aborted) return;
      if (!(error instanceof ServerUnreachable)) throw error;
      if (!stopped) {
        stopped = true;
        onStopped(true);
      }
      await sleep(retryMs, signal);
    }
  }
}

/** Resolves after `ms`, or as soon as `signal` is aborted. */
export function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const done = (): void => {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    };
    timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
  });
}
```

- [ ] **Step 8: Run the gate of the frontend**

Run: `npm run lint`, then `npm run typecheck`, then `npm test`
Expected: Biome clean (run `npm run format` first if it only reports formatting), no type errors, all tests pass with coverage 100 % on `src/api`, `src/lib`, `src/state`. A branch reported uncovered means a missing test: add it.

- [ ] **Step 9: Build and check what the build leaves**

Run: `npm run build`, then from the repository root `git status --short`
Expected: `src/ddd/gui/static/index.html`, an `assets/` directory and `third-party-licenses.txt` (listing `@tanstack/query-core`, `@tanstack/react-query`, `react`, `react-dom`, `scheduler`, all MIT) exist, and `git status` shows none of them - only the new files under `gui/` and `.gitignore`.

- [ ] **Step 10: Commit and push**

```bash
git add .gitignore gui/package.json gui/package-lock.json gui/tsconfig.json gui/vite.config.ts gui/biome.json gui/index.html gui/scripts gui/src
git commit -m "start the browser pages: the build, the api client, the pointers and the revision follower, under their coverage gate" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

(`gui/src/generated/` is ignored and stays out of the commit.)

### Task 11: The screens

The three screens of the walking skeleton. Plain on purpose: milestone 2 chooses the look. Their behaviour is tested end to end in Task 12, which is why this task ends with a build and a manual look rather than unit tests.

**Files:**
- Replace: `gui/src/main.tsx`
- Create: `gui/src/app/App.tsx`, `gui/src/app/useRoute.ts`, `gui/src/app/useProjectState.ts`
- Create: `gui/src/screens/StartPage.tsx`, `gui/src/screens/ProjectPage.tsx`, `gui/src/screens/ComponentPage.tsx`
- Create: `gui/src/components/Banner.tsx`, `gui/src/components/UnitEditor.tsx`
- Create: `gui/src/styles/tokens.css`, `gui/src/styles/app.css`

**Interfaces:**
- Consumes: everything Task 10 produces.
- Produces, for Task 12's selectors (keep these accessible names exactly):
  - the project page's heading is the project's name (`role=heading`); each component is a button named by the component's name
  - on the component page, each declaration's unit is a button named `Change unit of <Name>` whose text is the unit (or `none`); editing it shows a textbox named `Unit of <Name>`; Enter confirms, Escape cancels, leaving the field cancels
  - the findings of a component are a list with the class `findings`, each item showing the check identifier; with none, the text `None.`
  - a refusal or a stale edit is shown in `role=status`; a stopped server in `role=alert` containing `stopped`
  - the masthead has a button `Projects` that opens the start page

- [ ] **Step 1: Write the entry point and the hooks**

`gui/src/main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./styles/tokens.css";
import "./styles/app.css";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
```

`gui/src/app/useRoute.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import { hrefOf, parseRoute, type Route } from "../lib/route";

/** The page the address shows, and a way to go to another one that the back button undoes. */
export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState(() => parseRoute(window.location.pathname, window.location.search));
  useEffect(() => {
    const followHistory = () => setRoute(parseRoute(window.location.pathname, window.location.search));
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route) => {
    window.history.pushState(null, "", hrefOf(next));
    setRoute(next);
  }, []);
  return [route, navigate];
}
```

`gui/src/app/useProjectState.ts`:

```ts
import { useEffect, useState } from "react";
import { getState } from "../api/client";
import type { State } from "../api/types";
import { followRevisions } from "../state/revisions";

/** The newest revision of the open project, and whether the server stopped answering. */
export function useProjectState(open: boolean): { state: State | null; stopped: boolean; failure: string | null } {
  const [state, setState] = useState<State | null>(null);
  const [stopped, setStopped] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    followRevisions({
      getState: (after, signal) => getState(after, signal),
      onState: setState,
      onStopped: setStopped,
      signal: controller.signal,
    }).catch((error: unknown) => setFailure(error instanceof Error ? error.message : String(error)));
    return () => controller.abort();
  }, [open]);
  return { state, stopped, failure };
}
```

- [ ] **Step 2: Write the two components**

`gui/src/components/Banner.tsx`:

```tsx
import type { ReactNode } from "react";

/** A message across the page: an error is announced at once, a warning when the reader is ready. */
export function Banner({ tone, children }: { tone: "error" | "warning"; children: ReactNode }) {
  return (
    <div className={`banner ${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
```

`gui/src/components/UnitEditor.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";

interface Props {
  name: string;
  unit: string;
  disabled: boolean;
  onConfirm: (unit: string) => void;
}

/** A unit shown as a button; editing it takes Enter to confirm and Escape to cancel. */
export function UnitEditor({ name, unit, disabled, onConfirm }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(unit);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) input.current?.focus();
  }, [editing]);

  if (!editing) {
    return (
      <button
        type="button"
        className="value"
        aria-label={`Change unit of ${name}`}
        disabled={disabled}
        onClick={() => {
          setDraft(unit);
          setEditing(true);
        }}
      >
        {unit === "" ? <span className="quiet">none</span> : unit}
      </button>
    );
  }
  return (
    <input
      ref={input}
      className="unit"
      aria-label={`Unit of ${name}`}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          setEditing(false);
          if (draft !== unit) onConfirm(draft);
        } else if (event.key === "Escape") {
          setEditing(false);
        }
      }}
      onBlur={() => setEditing(false)}
    />
  );
}
```

- [ ] **Step 3: Write the three screens**

`gui/src/screens/StartPage.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { getProjects, openProject } from "../api/client";
import { Banner } from "../components/Banner";

/** The projects found where `ddd gui` was started, to open one of them. */
export function StartPage({ onOpened }: { onOpened: () => void }) {
  const found = useQuery({ queryKey: ["projects"], queryFn: () => getProjects() });
  const open = useMutation({ mutationFn: (path: string) => openProject(path), onSuccess: onOpened });

  if (found.isPending) return <p className="quiet">Looking for projects…</p>;
  if (found.isError) return <Banner tone="error">{found.error.message}</Banner>;
  return (
    <section>
      <h1>Open a project</h1>
      <p className="quiet">Found under {found.data.root}</p>
      {found.data.projects.length === 0 ? (
        <p>No project description was found here. Start ddd gui with the path of one.</p>
      ) : (
        <ul className="projects">
          {found.data.projects.map((project) => (
            <li key={project.path}>
              <button type="button" disabled={open.isPending} onClick={() => open.mutate(project.path)}>
                <span className="name">{project.name ?? "Unnamed project"}</span>
                <span className="path">{project.path}</span>
                {project.images.length > 0 && <span className="quiet">built as {project.images.join(", ")}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {found.data.refused.length > 0 && (
        <>
          <h2>Build records not used</h2>
          <ul className="refused">
            {found.data.refused.map((entry) => (
              <li key={entry.record}>
                <span className="path">{entry.record}</span>: {entry.reason}
              </li>
            ))}
          </ul>
        </>
      )}
      {open.isError && <Banner tone="error">{open.error.message}</Banner>}
    </section>
  );
}
```

`gui/src/screens/ProjectPage.tsx`:

```tsx
import type { State } from "../api/types";

interface Props {
  name: string;
  state: State | null;
  onComponent: (file: string) => void;
}

/** The open project: its components and how many findings each has. */
export function ProjectPage({ name, state, onComponent }: Props) {
  if (state === null) return <p className="quiet">Checking the project…</p>;
  const components = state.files.filter((file) => file.kind === "component");
  const total = (severity: "error" | "warning") =>
    state.findings.filter((finding) => finding.severity === severity).length;
  return (
    <section>
      <h1>{name}</h1>
      <p className="summary">
        {total("error")} errors, {total("warning")} warnings
      </p>
      <table className="components">
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col">Errors</th>
            <th scope="col">Warnings</th>
            <th scope="col">File</th>
          </tr>
        </thead>
        <tbody>
          {components.map((file) => (
            <tr key={file.path} className={file.findings.error > 0 ? "has-error" : undefined}>
              <td>
                <button type="button" className="link" onClick={() => onComponent(file.path)}>
                  {file.name ?? file.path}
                </button>
              </td>
              <td>{file.findings.error}</td>
              <td>{file.findings.warning}</td>
              <td className="path">{file.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

`gui/src/screens/ComponentPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getFile, postEdit } from "../api/client";
import type { State } from "../api/types";
import { Banner } from "../components/Banner";
import { UnitEditor } from "../components/UnitEditor";
import { jsonText, setValue } from "../lib/edits";
import type { ComponentFile } from "../lib/formats";
import { valueAt, within } from "../lib/pointer";
import { asList, asText } from "../lib/values";

interface Props {
  file: string;
  state: State | null;
  disabled: boolean;
}

/** One component: its declarations, a unit editor on each, and the findings located in it. */
export function ComponentPage({ file, state, disabled }: Props) {
  const queries = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const content = useQuery({ queryKey: ["file", file, state?.revision], queryFn: () => getFile(file) });
  const edit = useMutation({
    mutationFn: ({ pointer, unit }: { pointer: string; unit: string }) => {
      if (content.data === undefined) throw new Error("the file has not been read yet");
      return postEdit(setValue(content.data.path, content.data.fingerprint, pointer, jsonText(unit)));
    },
    onSuccess: () => setNotice(null),
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setNotice("This file changed on disk, so the change was not made. The page now shows the file as it is.");
      } else {
        setNotice(`The change was refused: ${error.message}`);
      }
    },
    onSettled: () => queries.invalidateQueries({ queryKey: ["file", file] }),
  });

  if (content.isPending) return <p className="quiet">Reading the file…</p>;
  if (content.isError) return <Banner tone="error">{content.error.message}</Banner>;
  if (content.data.error !== null) return <Banner tone="error">{content.data.error}</Banner>;

  const data = content.data.data;
  const name = (data as ComponentFile).component?.name ?? "Unnamed component";
  const findings = (state?.findings ?? []).filter((finding) => finding.file === file);
  return (
    <section>
      <h1>{name}</h1>
      {notice !== null && <Banner tone="warning">{notice}</Banner>}
      <table className="declarations">
        <thead>
          <tr>
            <th scope="col">Scope</th>
            <th scope="col">Name</th>
            <th scope="col">Kind</th>
            <th scope="col">Type</th>
            <th scope="col">Unit</th>
            <th scope="col">Findings</th>
          </tr>
        </thead>
        <tbody>
          {asList(valueAt(data, "component.interface")).map((_, index) => {
            const at = `component.interface[${index}]`;
            const declared = asText(valueAt(data, `${at}.definition.name`)) ?? `declaration ${index + 1}`;
            const own = findings.filter((finding) => within(finding.pointer, at));
            return (
              <tr key={at} className={own.some((finding) => finding.severity === "error") ? "has-error" : undefined}>
                <td>{asText(valueAt(data, `${at}.scope`))}</td>
                <td>{declared}</td>
                <td>{asText(valueAt(data, `${at}.definition.kind`))}</td>
                <td>
                  {asText(valueAt(data, `${at}.definition.datatype`)) ??
                    asText(valueAt(data, `${at}.definition.typename`))}
                </td>
                <td>
                  <UnitEditor
                    name={declared}
                    unit={asText(valueAt(data, `${at}.definition.unit`)) ?? ""}
                    disabled={disabled || edit.isPending}
                    onConfirm={(unit) => edit.mutate({ pointer: `${at}.definition.unit`, unit })}
                  />
                </td>
                <td>
                  {own.map((finding) => (
                    <span key={`${finding.check}:${finding.pointer}`} className={`badge ${finding.severity}`}>
                      {finding.check}
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h2>Findings in this component</h2>
      {findings.length === 0 ? (
        <p className="quiet">None.</p>
      ) : (
        <ul className="findings">
          {findings.map((finding, index) => (
            <li key={`${index}:${finding.check}`} className={finding.severity}>
              <span className="check">{finding.check}</span> <span className="message">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
```

If `DDDComponentDescription` makes `component` required, drop the `?.` - the type check says which.

`gui/src/app/App.tsx`:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSession } from "../api/client";
import { Banner } from "../components/Banner";
import { ComponentPage } from "../screens/ComponentPage";
import { ProjectPage } from "../screens/ProjectPage";
import { StartPage } from "../screens/StartPage";
import { useProjectState } from "./useProjectState";
import { useRoute } from "./useRoute";

export function App() {
  const queries = useQueryClient();
  const [route, navigate] = useRoute();
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const opened = session.data?.project ?? null;
  const { state, stopped, failure } = useProjectState(opened !== null);

  let page;
  if (session.isPending) {
    page = <p className="quiet">Connecting…</p>;
  } else if (session.isError) {
    page = <Banner tone="error">{session.error.message}</Banner>;
  } else if (opened === null || route.page === "start") {
    page = (
      <StartPage
        onOpened={() => {
          void queries.invalidateQueries({ queryKey: ["session"] });
          navigate({ page: "project" });
        }}
      />
    );
  } else if (route.page === "project") {
    page = (
      <ProjectPage
        name={opened.name ?? opened.path}
        state={state}
        onComponent={(file) => navigate({ page: "component", file })}
      />
    );
  } else {
    page = <ComponentPage file={route.file} state={state} disabled={stopped} />;
  }

  return (
    <div className="app">
      <header className="masthead">
        <span className="brand">ddd gui</span>
        <span className="preview">preview</span>
        <nav>
          <button type="button" className="link" onClick={() => navigate({ page: "start" })}>
            Projects
          </button>
          {opened !== null && (
            <button type="button" className="link" onClick={() => navigate({ page: "project" })}>
              {opened.name ?? opened.path}
            </button>
          )}
        </nav>
      </header>
      {stopped && (
        <Banner tone="error">ddd gui has stopped. Start it again and open the address it prints.</Banner>
      )}
      {failure !== null && <Banner tone="error">{failure}</Banner>}
      <main>{page}</main>
    </div>
  );
}
```

- [ ] **Step 4: Write the styles**

`gui/src/styles/tokens.css`:

```css
/* The skeleton's few tokens. Milestone 2 replaces them with the visual style it chooses. */
:root {
  --ink: #1d2a2f;
  --ink-quiet: #5b6b71;
  --ground: #f7f9f9;
  --surface: #ffffff;
  --rule: #d9e2e5;
  --accent: #0e6b7c;
  --error: #b3261e;
  --error-ground: #fdecea;
  --warning: #7a4f00;
  --warning-ground: #fff4dc;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --text-small: 13px;
  --text-body: 15px;
  --text-title: 22px;
  --font: "Segoe UI", system-ui, sans-serif;
  --mono: "Cascadia Mono", Consolas, monospace;
}
```

`gui/src/styles/app.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink); font: var(--text-body) / 1.5 var(--font); }
.app { max-width: 1100px; margin: 0 auto; padding: var(--space-4); }
.masthead { display: flex; align-items: baseline; gap: var(--space-3); padding-block: var(--space-2); border-bottom: 1px solid var(--rule); }
.masthead nav { margin-left: auto; display: flex; gap: var(--space-3); }
.brand { font-weight: 600; }
.preview { font-size: var(--text-small); color: var(--ink-quiet); text-transform: uppercase; letter-spacing: 0.06em; }
h1 { font-size: var(--text-title); margin: var(--space-6) 0 var(--space-2); }
h2 { font-size: var(--text-body); margin: var(--space-6) 0 var(--space-2); }
.quiet, .path { color: var(--ink-quiet); }
.path { font: var(--text-small) var(--mono); }
.summary { margin-top: 0; }
table { width: 100%; border-collapse: collapse; background: var(--surface); }
th, td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--rule); vertical-align: top; }
tr.has-error td:first-child { box-shadow: inset 3px 0 var(--error); }
button { font: inherit; }
button.link, button.value { background: none; border: none; padding: 0; color: var(--accent); cursor: pointer; text-align: left; }
button.link:hover, button.value:hover { text-decoration: underline; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
input.unit { font: inherit; width: 8em; padding: 2px var(--space-1); }
.projects { list-style: none; padding: 0; display: grid; gap: var(--space-2); }
.projects button { display: grid; width: 100%; text-align: left; padding: var(--space-3); background: var(--surface); border: 1px solid var(--rule); border-radius: 6px; cursor: pointer; }
.projects .name { font-weight: 600; }
.badge { display: inline-block; margin-right: var(--space-1); padding: 0 var(--space-2); border-radius: 10px; font-size: var(--text-small); }
.badge.error { background: var(--error-ground); color: var(--error); }
.badge.warning, .badge.info { background: var(--warning-ground); color: var(--warning); }
.findings { padding-left: var(--space-4); }
.findings .check { font-family: var(--mono); font-size: var(--text-small); }
.findings .error .check { color: var(--error); }
.banner { margin-block: var(--space-3); padding: var(--space-3); border-radius: 6px; }
.banner.error { background: var(--error-ground); color: var(--error); }
.banner.warning { background: var(--warning-ground); color: var(--warning); }
```

- [ ] **Step 5: Lint, type check, build**

Run: `npm run format`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
Expected: all clean (the coverage gate is unaffected: screens are outside it), the pages rebuilt into `src/ddd/gui/static/`.

- [ ] **Step 6: Look at it once**

From the repository root in Git Bash: `python -m ddd gui examples/demo/demo.ddd.json`, open the printed address in Edge, click Controller, change ValueA's unit to `rpm` and back to `%`, then stop the server with Ctrl+C. Expected: the project page lists the four components; the edit shows `definition-mismatch` and withdraws it; `git status` shows `examples/demo` unchanged after changing the unit back (if it does not, restore it with `git checkout examples/demo` and note what differed in the progress log).

- [ ] **Step 7: Commit and push**

```bash
git add gui/src
git commit -m "show the open project, its components and their findings, and let a declaration's unit be changed in place" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 12: End-to-end journeys

Every step of the spec's section 6.1, driven in a real browser against the real `ddd gui`, over a temporary copy of `examples/demo`.

**Files:**
- Create: `gui/playwright.config.ts`, `gui/e2e/fixtures.ts`, `gui/e2e/skeleton.spec.ts`

**Interfaces:**
- Consumes: the command of Task 9 (`python -m ddd gui PROJECT --no-browser`, first stdout line `ddd gui (preview) serving <address>`); the accessible names Task 11 produces; the compiled pages of Task 11 (`npm run build` first).
- Produces: `npm run e2e`. Environment: `DDD_PYTHON` names the interpreter with the package installed (default `python`); `PLAYWRIGHT_CHANNEL=msedge` drives the installed Edge instead of Playwright's Chromium.

- [ ] **Step 1: Write the configuration and the fixtures**

`gui/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

// One worker: every test starts its own `ddd gui` over its own copy of the demo, and the journeys
// are few. Locally, PLAYWRIGHT_CHANNEL=msedge drives the installed Edge, which needs no download.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    browserName: "chromium",
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    trace: "retain-on-failure",
  },
});
```

`gui/e2e/fixtures.ts`:

```ts
import { type ChildProcess, spawn } from "node:child_process";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base } from "@playwright/test";

const DEMO = fileURLToPath(new URL("../../examples/demo/", import.meta.url));

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The temporary copy of examples/demo the server edits. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** `ddd gui` over a fresh copy of the demo, with the project named or not. */
async function started(named: boolean, use: (gui: Gui) => Promise<void>): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "ddd-gui-e2e-"));
  cpSync(DEMO, directory, { recursive: true });
  const project = named ? [join(directory, "demo.ddd.json")] : [];
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(process.env.DDD_PYTHON ?? "python", ["-m", "ddd", "gui", ...project, "--no-browser"], {
    cwd: directory,
    stdio: ["ignore", "pipe", "inherit"],
  });
  let stopped = false;
  const stop = async () => {
    if (!stopped) {
      stopped = true;
      await terminated(child);
    }
  };
  try {
    await use({ address: await served(child), directory, stop });
  } finally {
    await stop();
    rmSync(directory, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

function served(child: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    if (child.stdout === null) {
      reject(new Error("ddd gui has no stdout"));
      return;
    }
    createInterface({ input: child.stdout }).on("line", (line) => {
      const found = /serving (\S+)/.exec(line);
      if (found?.[1] !== undefined) resolve(found[1]);
    });
    child.once("exit", (code) => reject(new Error(`ddd gui exited with ${code} before serving`)));
  });
}

function terminated(child: ChildProcess): Promise<void> {
  return new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }
    child.once("exit", () => resolve());
    child.kill();
  });
}

export const test = base.extend<{ gui: Gui; bareGui: Gui }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  gui: async ({}, use) => started(true, use),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  bareGui: async ({}, use) => started(false, use),
});

export { expect } from "@playwright/test";
```

- [ ] **Step 2: Write the journeys**

`gui/e2e/skeleton.spec.ts`:

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./fixtures";

const CONTROLLER = join("components", "controller.ddd.json");
const COMPONENTS = ["Controller", "SensorHub", "UserInterface", "EventLogger"];

test("the demo opens on its project page, with every component", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  for (const name of COMPONENTS) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
});

test("a unit is written as one value and the disagreement is shown on both sides", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByRole("button", { name: "Change unit of ValueA" })).toHaveText("rpm");
  const expected = Buffer.from(before.toString("utf8").replace('"unit": "%"', '"unit": "rpm"'), "utf8");
  await expect.poll(() => readFileSync(file).equals(expected)).toBe(true);
  await expect(page.locator(".findings").getByText("definition-mismatch")).toBeVisible();

  await page.getByRole("button", { name: "DemoDevice" }).click();
  await page.getByRole("button", { name: "SensorHub", exact: true }).click();
  await expect(page.locator(".findings").getByText("definition-mismatch")).toBeVisible();

  await page.goBack();
  await page.goBack();
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("%");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByText("None.")).toBeVisible();
  await expect.poll(() => readFileSync(file).equals(before)).toBe(true);
});

test("escape leaves a unit as it was", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Escape");
  await expect(page.getByRole("button", { name: "Change unit of ValueA" })).toHaveText("%");
  expect(readFileSync(file).equals(before)).toBe(true);
});

test("a change saved by another editor reaches the page", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("V");
  writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("mV", { timeout: 5_000 });
});

test("an edit made from a page that is out of date is refused, and the file reloaded", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("V");
  await page.route("**/api/edit", async (route) => {
    writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
    await route.continue();
  });
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByRole("status")).toContainText("changed on disk");
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("mV");
  expect(readFileSync(file, "utf8")).toContain('"unit": "%"');
});

test("the page says so when the server stops", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await gui.stop();
  await expect(page.getByRole("alert")).toContainText("stopped");
});

test("without a project the start page lists the ones found and opens the one chosen", async ({ page, bareGui }) => {
  await page.goto(bareGui.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  await page.getByRole("button", { name: /DemoDevice/ }).click();
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});
```

The start page also lists `subsystems/logging/logging.ddd.json`; the regular expression picks the DemoDevice entry by its name.

- [ ] **Step 3: Run the journeys**

Run (in `gui/`, Git Bash, with the venv's python): `npm run build`, then `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`
Expected: 7 passed. A failure leaves a trace under `test-results/`; open it with `npx playwright show-trace <trace.zip>`. A journey that fails on the page's behaviour is a defect of Task 11 or of the server to fix there, not a selector to loosen.

- [ ] **Step 4: Commit and push**

```bash
git add gui/playwright.config.ts gui/e2e
git commit -m "drive the walking skeleton end to end in a browser, over a copy of the demo" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 13: Packaging, CI and the developer page

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/dependabot.yml`
- Modify: `docs/developer_documentation.rst`
- Test: `tests/test_documentation.py`

**Interfaces:**
- Consumes: the npm scripts of Tasks 10 and 12; `src/ddd/gui/static/` as Task 10's build writes it.
- Produces: a wheel and an sdist that carry `ddd/gui/static/` when it has been built; a `gui` CI job; a publish build that compiles the pages first and checks the wheel has them.

- [ ] **Step 1: Write the failing tests**

In `tests/test_documentation.py`, `class TestPackagedResources`, add:

```python
    def test_the_archives_carry_the_compiled_gui_pages(self) -> None:
        """git ignores the pages npm compiles, and only an artifact pattern puts a file git
        ignores into an archive - without it the wheel installs a ddd gui with nothing to serve."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        targets = metadata["tool"]["hatch"]["build"]["targets"]
        assert "/src/ddd/gui/static" in targets["wheel"]["artifacts"]
        assert "/src/ddd/gui/static" in targets["sdist"]["artifacts"]
        assert "/gui" in targets["sdist"]["include"]
```

Replace the helper `dependabot()` and the two tests that read it:

```python
def dependabot() -> dict[str, list[str]]:
    """Each ecosystem dependabot watches, to the directories it watches it in.

    Read with a regex rather than a yaml parser, as the pre-commit hook definition is: the
    file is a handful of ``key: value`` lines, and a yaml dependency in the test requirements
    would be a larger commitment than the thing being read.
    """
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    entries = re.findall(
        r"package-ecosystem:\s*\"?([\w-]+)\"?.*?directory:\s*\"?([^\s\"]+)", text, flags=re.S
    )
    assert len(entries) == text.count("package-ecosystem:"), (
        "an entry of dependabot.yml names no directory"
    )
    watched: dict[str, list[str]] = {}
    for ecosystem, directory in entries:
        watched.setdefault(ecosystem, []).append(directory)
    return watched
```

```python
    @pytest.mark.parametrize("ecosystem", ["github-actions", "pip", "npm"])
    def test_every_manifest_of_this_repository_is_watched(self, ecosystem: str) -> None:
        watched = dependabot()
        assert ecosystem in watched, (
            f"nothing proposes an update for {ecosystem}, so those pins move only when a "
            f"release is already blocked by one of them"
        )
        for directory in watched[ecosystem]:
            assert (ROOT / directory.lstrip("/")).resolve().is_dir(), (
                f"{ecosystem} is watched in {directory}, which is not a directory"
            )

    def test_the_node_manifests_are_watched_where_they_live(self) -> None:
        """A directory that does not hold the manifest is watched in silence: dependabot
        reports "no dependencies found" on its own page and nothing else."""
        watched = {Path(directory.lstrip("/")) for directory in dependabot()["npm"]}
        assert watched == {Path("editors/vscode"), Path("gui")}
        for directory in watched:
            assert (ROOT / directory / "package.json").is_file()
            assert (ROOT / directory / "package-lock.json").is_file()
```

Run: `python -m pytest tests/test_documentation.py -k "compiled_gui_pages or watched" --no-cov`
Expected: FAIL (no `artifacts` key; `npm` watched only in `/editors/vscode`).

- [ ] **Step 2: Packaging**

In `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ddd"]
# The compiled pages of `ddd gui` are written by `npm run build` in gui/ and ignored by git, and
# hatch leaves out what git ignores - except an artifact. Absent pages are no error: an editable
# install without them makes `ddd gui` say how to build them.
artifacts = ["/src/ddd/gui/static"]
```

In `[tool.hatch.build.targets.sdist]`, add `"/gui",` to `include` (after `"/editors/vscode",`) and add, after the `exclude` list:

```toml
# The same pages, so that a wheel built from the sdist carries them as well.
artifacts = ["/src/ddd/gui/static"]
```

(Keep the `force-include` table where it is; the artifact paths overlap none of its entries.)

- [ ] **Step 3: Check the archives for real**

From the repository root, with the pages built (Task 11): `python -m pip wheel . --no-deps -w "$SCRATCH/wheel"` and `python -m zipfile -l "$SCRATCH"/wheel/ddd_tool-*.whl | grep gui/static`
Expected: `ddd/gui/static/index.html`, `ddd/gui/static/third-party-licenses.txt` and the `assets/` files are listed. If they are listed under `src/ddd/gui/static/` instead, the artifact path is being matched without the package's `src` rewrite: report it in the progress log and move the pattern to `[tool.hatch.build]` (the table all targets share), then build again.

- [ ] **Step 4: The CI job**

In `.github/workflows/ci.yml`, add after the `extension` job:

```yaml
  gui:
    # The browser interface: its types generated from the schemas, its lint and type check, its
    # logic under the coverage gate, its pages compiled, and those pages driven in a browser
    # against the real `ddd gui` - on both systems the package claims to run on. Node 24, as the
    # extension job has it; the python package is installed because the types and the server
    # both come from it.
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        working-directory: gui
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements*.txt
      - uses: actions/setup-node@v5
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: gui/package-lock.json
      - run: pip install -e ..
      - run: npm ci
      - run: npm run schemas
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
      - run: npx playwright install --with-deps chromium
      - run: npm run e2e
      - if: failure()
        uses: actions/upload-artifact@v7
        with:
          name: playwright-report-${{ matrix.os }}
          path: gui/playwright-report
```

- [ ] **Step 5: The publish build**

In `.github/workflows/publish.yml`, job `build`, replace the step `- run: python -m build` with:

```yaml
      # The wheel carries the compiled pages of `ddd gui`, which git does not track: they are
      # compiled here, against types generated by the package itself, hence its install first.
      - uses: actions/setup-node@v5
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: gui/package-lock.json
      - run: pip install -e .
      - run: npm ci && npm run schemas && npm run build
        working-directory: gui
      - run: python -m build
      - name: Check the wheel carries the compiled pages
        run: |
          python - <<'EOF'
          import glob, sys, zipfile
          names = zipfile.ZipFile(glob.glob("dist/*.whl")[0]).namelist()
          if "ddd/gui/static/index.html" not in names:
              sys.exit("the wheel has no ddd/gui/static/index.html: ddd gui would have nothing to serve")
          EOF
```

- [ ] **Step 6: Dependabot**

In `.github/dependabot.yml`, add after the extension's entry:

```yaml
  # The browser interface, whose package-lock.json is what `npm ci` installs from in the gui job
  # and in the release build that compiles the pages into the wheel.
  - package-ecosystem: npm
    directory: /gui
    schedule:
      interval: weekly
```

- [ ] **Step 7: The developer page**

In `docs/developer_documentation.rst`, section "Continuous integration":
- replace "in two jobs, and two more the commands above do not cover." with "in two jobs, and three more the commands above do not cover.";
- after the paragraph about ``extension``, add:

```rst
``gui`` builds and tests the browser interface on ubuntu and windows: it installs the package and
node, generates the TypeScript types from ``ddd schema``, runs Biome, the type check and Vitest
with its coverage gate, compiles the pages, and drives them in Chromium against a real
``ddd gui`` with Playwright. The pages it compiles are thrown away; the release build compiles
them again, into the wheel.
```

- in the last paragraph, replace "for the actions, the requirements files and the extension" with "for the actions, the requirements files, the extension and the browser interface".

Then add a section after "Delivering the editor extension" (match the underline style of its neighbours):

```rst
The browser interface
---------------------

``ddd gui`` serves pages compiled from ``gui/``, a Vite project in TypeScript and React, into
``src/ddd/gui/static/``. git ignores the compiled pages; the release build compiles them before
it builds the wheel, which then carries them. A source checkout needs Node.js 24 to build them,
with the package installed so that its types can be generated:

.. code-block:: text

   cd gui
   npm ci
   npm run schemas     # TypeScript types, from ddd schema all
   npm run build       # the pages, and third-party-licenses.txt beside them
   npm run watch       # rebuilds on every change; reload the page ddd gui serves

``npm run lint`` and ``npm run typecheck`` are the frontend's ruff and mypy, and ``npm test``
runs Vitest with a 100 % gate over the modules that hold logic - ``src/api``, ``src/lib`` and
``src/state``. The screens are covered by ``npm run e2e``: Playwright drives the real ``ddd gui``
over a copy of ``examples/demo``, started with the interpreter ``DDD_PYTHON`` names, and
``PLAYWRIGHT_CHANNEL=msedge`` drives the installed Edge on a machine without Playwright's own
Chromium. The build refuses a bundled package whose licence is not MIT, ISC, Apache-2.0 or BSD.
```

- [ ] **Step 8: Run the documentation tests and the documentation build**

Run: `python -m pytest tests/test_documentation.py --no-cov`, then the sphinx build of Task 9 Step 6.
Expected: all pass; `build succeeded`.

- [ ] **Step 9: Full Python gate**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`
Expected: green, 100 %.

- [ ] **Step 10: Commit and push**

```bash
git add pyproject.toml .github/workflows/ci.yml .github/workflows/publish.yml .github/dependabot.yml docs/developer_documentation.rst tests/test_documentation.py
git commit -m "carry the compiled pages in the wheel, build and drive them in ci, and compile them for every release" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

### Task 14: Milestone gate and recalibration

Done by the controlling session, not by an implementer: it closes the milestone and answers the question milestone 1 was for.

**Files:**
- Modify: this plan's Progress log
- Update: the estimate page (https://claude.ai/artifact/HT1HxkAp8Cg2rAqbYb7EL6), through its URL

- [ ] **Step 1: The whole gate, from a clean build**

From Git Bash at the repository root, with the PATH, `JAVA` and `PLANTUML_JAR` of the local toolchain note:

```bash
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m sphinx -M html docs "$SCRATCH/docs_out" -W
cd gui && npm ci && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build
DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e
```

Expected: every command succeeds; pytest at 100 % with the one known symlink-privilege exception on this machine.

- [ ] **Step 2: CI on the branch**

The branch is pushed but `ci.yml` runs on pull requests and on master. Ask the maintainer whether to dispatch it on the branch (`gh workflow run CI --ref feature/web-gui-skeleton`, which the workflow's `workflow_dispatch` exists for) or to open the pull request; do neither without the answer. When a run exists, wait for every job, the `gui` job on both systems included, and fix what fails.

- [ ] **Step 3: Recalibrate**

From the Progress log, sum the duration of Tasks 1 to 13 by the estimate's kinds of work: the edit engine (Tasks 1 to 4), the local server (Tasks 5 to 9), the frontend foundation and the skeleton's screens (Tasks 10 to 13). Divide each package's conventional likely person-days from the estimate (server 9, edit engine 10, frontend foundation 12, plus about 3 for the skeleton's screens) by the working days spent, counting 8 hours as a day. That is the measured speed-up of each kind of work. Replace the assumed factors on the estimate page with the measured ones, recompute the with-Claude totals (the page's `build.py` does this from its factor table), republish the page to the same URL, and state in the progress log what changed.

- [ ] **Step 4: Hand over**

Tell the maintainer: the gate's result, the CI result, the measured factors and the new estimate range, and anything the implementers deferred. Ask before opening the pull request (the push-work-as-you-go note). Record the milestone's state in the web GUI feature memory.

---

## Progress log

| Task | Started | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |
| 11 | | | | |
| 12 | | | | |
| 13 | | | | |
| 14 | | | | |

## Left open by the implementers

(Anything a task deferred, with the reason, so that milestone 2 starts from it.)
