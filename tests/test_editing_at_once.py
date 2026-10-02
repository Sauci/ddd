"""A file edited at many places is read once more after the edit, not once per place.

``edit_text`` makes a batch of sets none of which can depend on what another one writes from the
one reading of the file, and reads the text it leaves once; ``_independent`` decides which batches
those are. Every other batch, and one that is refused or does not read back once made at once, is
made one operation at a time and verified after each, as before. Both ways have to answer alike:
``oracle`` below is ``edit_text`` as it stood before a batch could be made at once, and the engine
is held to its every answer - the text, or the refusal's code and sentence - on every example's
files, on a generated project's rename, and on random documents and batches.
"""

from __future__ import annotations

import copy
import json
import random
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from generate_project import generate

import ddd.editing as editing
from conftest import EXAMPLES
from ddd.diagnostics import DiagnosticBag
from ddd.editing import (
    INVALID,
    UNREADABLE,
    UNVERIFIED,
    EditError,
    Operation,
    TextEdit,
    edit_text,
    fingerprint,
)
from ddd.loading import load_workspace
from ddd.lsp.navigation import index
from ddd.lsp.ranges import Document
from ddd.lsp.units import rename_unit, unit_project
from ddd.variables import hunks, planned


def oracle(text: str, operations: Sequence[Operation]) -> str:
    """``edit_text`` as it stood before a batch could be made at once, its body copied but for the
    module its helpers are named through: every operation in order, each verified against the
    parsed document before the next one."""
    unreadable = "the file is not json DDD reads, so no pointer names a place in it"
    document = editing._read(text, UNREADABLE, unreadable)
    expected = copy.deepcopy(document.data)
    for operation in operations:
        text, expected = editing._made(document, operation, expected)
        document = editing._read(text, UNVERIFIED, "an edit left the file unreadable")
        if editing._canonical(document.data) != editing._canonical(expected):
            raise EditError(
                UNVERIFIED, "the edited file does not read back as the intended document"
            )
    return text


def answer(
    edit: Callable[[str, Sequence[Operation]], str], text: str, operations: Sequence[Operation]
) -> tuple[str, str]:
    """What an engine answers: ``("text", the text it leaves)``, or a refusal's code and its
    whole sentence."""
    try:
        return "text", edit(text, operations)
    except EditError as refused:
        return refused.code, str(refused)


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every text ``_read`` is given while a test runs: each one parsed by the loader's rule and
    scanned for where its values sit."""
    read: list[str] = []
    real = editing._read

    def counted(text: str, code: str, refusal: str) -> Document:
        read.append(text)
        return real(text, code, refusal)

    monkeypatch.setattr(editing, "_read", counted)
    return read


def alike(text: str, operations: Sequence[Operation], read: list[str]) -> tuple[int, int]:
    """Asserts that the engine answers exactly what the oracle answers, and hands back how many
    texts each of the two read to answer it: the engine's, then the oracle's."""
    read.clear()
    expected = answer(oracle, text, operations)
    by_oracle = len(read)
    read.clear()
    assert answer(edit_text, text, operations) == expected
    return len(read), by_oracle


def at_once(text: str, operations: Sequence[Operation]) -> bool:
    return editing._independent(Document(text), operations)


@pytest.fixture
def tried(monkeypatch: pytest.MonkeyPatch, reads: list[str]) -> list[tuple[bool, int]]:
    """Every batch the engine tried to make at once: whether that answered, and how many texts
    it read trying - one, the text the edits left, or none when an operation was refused first."""
    attempts: list[tuple[bool, int]] = []
    real = editing._made_at_once

    def recorded(document: Document, operations: Sequence[Operation]) -> str | None:
        before = len(reads)
        made = real(document, operations)
        attempts.append((made is not None, len(reads) - before))
        return made

    monkeypatch.setattr(editing, "_made_at_once", recorded)
    return attempts


def literal_leaves(value: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    """Every value of a parsed document that is not a container, with the pointer naming it, in
    document order - but for those under a key holding a dot or a bracket, which no pointer can
    name the way the scan spells it."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not any(mark in key for mark in ".[]"):
                yield from literal_leaves(item, f"{pointer}.{key}" if pointer else key)
    elif isinstance(value, list):
        for index_, item in enumerate(value):
            yield from literal_leaves(item, f"{pointer}[{index_}]")
    else:
        yield pointer, value


def another(value: Any, rng: random.Random) -> str:
    """A literal to set in place of ``value``, as json text: a string with a quote, a backslash
    and characters outside ascii added, written as themselves or as escapes; the other truth
    value; or a number in one of several spellings."""
    if isinstance(value, str):
        return json.dumps(f'{value}"\\é😀', ensure_ascii=rng.random() < 0.5)
    if isinstance(value, bool):
        return json.dumps(not value)
    if value is None:
        return rng.choice(["0", '"none"'])
    return rng.choice(["1.0", "-0", "2.50", "1E+2", "-7"])


class TestABatchIsReadOnce:
    def test_a_file_set_at_many_places_is_read_twice_not_once_per_place(self, reads):
        """Read once as it was given and once as it was left, where one operation after another
        read it again after each of them: 41 times for these forty places."""
        text = json.dumps({"units": [{"unit": f"u{n}", "described": n} for n in range(40)]})
        operations = [Operation("set", f"units[{n}].unit", f'"v{n}"') for n in range(40)]
        assert alike(text, operations, reads) == (2, 41)
        assert reads[-1] == text.replace('"unit": "u', '"unit": "v')


class TestWhichBatchIsMadeAtOnce:
    TEXT = '{"a": {"b": 1, "c": "x"}, "list": [1, 2, 3], "d": null}'

    def test_sets_of_literals_at_places_apart_are_made_at_once(self, reads):
        operations = [
            Operation("set", "a.b", "2.0"),
            Operation("set", "list[2]", '"\\u00e9"'),
            Operation("set", "d", "true"),
            Operation("set", "a.c", ' "y" '),
        ]
        assert at_once(self.TEXT, operations)
        assert alike(self.TEXT, operations, reads) == (2, 5)
        assert edit_text(self.TEXT, operations) == (
            '{"a": {"b": 2.0, "c": "y"}, "list": [1, 2, "\\u00e9"], "d": true}'
        )

    def test_the_whole_document_set_alone_is_made_at_once(self, reads):
        operations = [Operation("set", "", "7")]
        assert at_once(self.TEXT, operations)
        assert alike(self.TEXT, operations, reads) == (2, 2)

    @pytest.mark.parametrize(
        "operations",
        [
            [Operation("set", "a.b", "2"), Operation("insert", "list[0]", "0")],
            [Operation("set", "a.b", "2"), Operation("remove", "list[0]")],
            [Operation("set", "a.b", "2"), Operation("move", "list[0]", to=2)],
            [Operation("set", "a", "1"), Operation("set", "a.b", "2")],
            [Operation("set", "a.b", "2"), Operation("set", "a", "1")],
            [Operation("set", "list[1]", "5"), Operation("set", "list", "0")],
            [Operation("set", "", "1"), Operation("set", "d", "2")],
            [Operation("set", "a.b", "2"), Operation("set", "a.b", "3")],
            [Operation("set", "a.b", "2"), Operation("set", "a.e", "3")],
            [Operation("set", "a.b", "2"), Operation("set", "list[3]", "4")],
            [Operation("set", "a.b", "2"), Operation("set", "d", '{"k": [1]}')],
            [Operation("set", "a.b", "2"), Operation("set", "d", " [1]")],
            [Operation("set", "a.b", "2"), Operation("set", "d")],
            [Operation("set", "a.b", "2"), Operation("set", "a..c", '"y"')],
        ],
        ids=[
            "an insert",
            "a removal",
            "a move",
            "a pointer nesting within one before it",
            "a pointer nesting within one after it",
            "an element of an array set beside the array",
            "the whole document beside one of its values",
            "the same pointer twice",
            "a member its object has not got",
            "an element past the end of its array",
            "an object",
            "an array, after whitespace",
            "no value",
            "a pointer not spelled the way the scan spells one",
        ],
    )
    def test_any_other_batch_is_made_one_operation_at_a_time(self, operations, reads):
        """As before, and reading what it read before: no more, the batch not being tried at
        once first."""
        assert not at_once(self.TEXT, operations)
        made, by_oracle = alike(self.TEXT, operations, reads)
        assert made == by_oracle

    def test_a_batch_that_does_not_read_back_is_refused_as_one_at_a_time_refuses_it(self, reads):
        """A key holding a dot is recorded under the pointer of the member it spells, the last
        one written winning, so ``a.b`` names the 1 in the parsed document and the 2 in the scan:
        the batch was made at once, did not read back, and was made again one operation at a
        time, which refuses it after its first operation, as it always has."""
        text = '{"a": {"b": 1}, "a.b": 2, "c": 3}'
        operations = [Operation("set", "a.b", "5"), Operation("set", "c", "4")]
        assert at_once(text, operations)
        assert answer(edit_text, text, operations) == (
            UNVERIFIED,
            "the edited file does not read back as the intended document",
        )
        assert alike(text, operations, reads) == (3, 2)

    def test_a_value_that_is_not_json_is_refused_as_one_at_a_time_refuses_it(self, reads):
        """Refused before the text it would have left is read, and made again one operation at a
        time, which reads the text the first operation leaves and refuses the second."""
        text = '{"a": 1, "b": 2}'
        operations = [Operation("set", "a", "3"), Operation("set", "b", "NaN")]
        assert at_once(text, operations)
        assert answer(edit_text, text, operations) == (
            INVALID,
            "'NaN' is not one json value: 'NaN' is not valid json; DDD has no representation "
            "for it",
        )
        assert alike(text, operations, reads) == (2, 2)

    @pytest.mark.parametrize(
        ("text", "operations", "made"),
        [
            (
                '{"a": {\n"x": 1\n}, "b": 2}',
                [Operation("set", "a", "1"), Operation("set", "c", "3")],
                '{"a": 1, "b": 2, "c": 3}',
            ),
            (
                '{\n  "a": {\n      "deep": 1\n    }\n}',
                [Operation("set", "a", "1"), Operation("set", "x", "2")],
                '{\n  "a": 1,\n  "x": 2\n}',
            ),
        ],
        ids=["onto the line a set left", "indented like the line a set left"],
    )
    def test_a_member_added_goes_where_the_sets_before_it_left_the_text(
        self, text, operations, made, reads
    ):
        """Laid out to fit the lines around it, which a set beside it can change. Replacing the
        value an object writes over several lines with a literal puts the object on one line,
        which the member added then joins; and it moves the end of the member the new one follows
        to another line, whose indentation the new one takes. Laid out from the lines as they were
        read, as a batch made at once would lay it out, either member went on a line of its own,
        indented like the replaced value's closing line."""
        assert not at_once(text, operations)
        assert answer(edit_text, text, operations) == ("text", made)
        alike(text, operations, reads)

    def test_a_container_set_is_laid_out_in_the_indentation_the_sets_before_it_left(self, reads):
        """The indentation unit is read off the first entry the file writes on a line of its own,
        here inside the array the first set replaces with a literal: laid out after it, the
        object takes the unit read off ``b``'s line, two spaces, where laid out from the lines as
        they were read it took the array's eight."""
        text = '{"a": [\n        1.0\n    ],\n  "b": 2\n}'
        operations = [Operation("set", "a", "0"), Operation("set", "b", '{"k": {"m": null}}')]
        assert not at_once(text, operations)
        assert answer(edit_text, text, operations) == (
            "text",
            '{"a": 0,\n  "b": {\n    "k": { "m": null }\n  }\n}',
        )
        alike(text, operations, reads)


class TestEditsMadeFromTheBack:
    def test_every_edit_lands_where_the_text_as_read_puts_it(self):
        """Made from the last back, so that one making the text longer or shorter moves none of
        those before it."""
        edits = [TextEdit(1, 2, "one"), TextEdit(7, 10, ""), TextEdit(4, 5, "[two]")]
        assert editing._all_applied("[a, b, ccc, d]", edits) == "[one, [two], , d]"

    def test_no_edit_leaves_the_text_as_it_was(self):
        assert editing._all_applied("[1]", []) == "[1]"


class TestTheSameAnswer:
    @pytest.mark.parametrize(
        "path",
        sorted(EXAMPLES.rglob("*.json")),
        ids=lambda path: path.relative_to(EXAMPLES).as_posix(),
    )
    def test_every_example(self, path: Path, reads):
        """Every value of the file that is not a container set anew, made at once; then random
        batches of every kind over the same file."""
        text = path.read_text(encoding="utf-8-sig")
        rng = random.Random(path.name)
        operations = [
            Operation("set", pointer, another(value, rng))
            for pointer, value in literal_leaves(json.loads(text))
        ]
        rng.shuffle(operations)
        assert at_once(text, operations)
        assert alike(text, operations, reads) == (2, len(operations) + 1)
        for _ in range(40):
            alike(text, batch(json.loads(text), rng), reads)

    def test_a_generated_projects_rename(self, tmp_path: Path, reads):
        """The unit the bench renames - ``A``, stated in every file and first by spelling - of a
        project of three thousand declarations in thirty components, as ``GET /api/unit-plan``
        plans it: every file made at once, and previewed with the lines one operation after
        another changed."""
        made = generate(tmp_path / "p", 3_000, "large")
        workspace = load_workspace(made.project, DiagnosticBag())
        assert workspace is not None
        cache: dict[Path, Document] = {}
        plan = rename_unit(
            index(workspace), unit_project(made.project, (), cache), "A", "A2", cache
        )
        assert len(plan.edits) == 31
        assert sum(len(edit.operations) for edit in plan.edits) == 375
        for edit in plan.edits:
            data = edit.path.read_bytes()
            text = data.decode("utf-8")
            assert alike(text, edit.operations, reads) == (2, len(edit.operations) + 1)
            previewed = planned(
                edit.path, edit.operations, {edit.path.resolve(): fingerprint(data)}
            )
            assert previewed.hunks == hunks(text, oracle(text, edit.operations))

    def test_random_documents_and_batches(self, reads, tried):
        """Documents of literals, strings with escapes, nested objects and arrays, laid out on
        one line, one entry per line, or both, with line feeds, carriage returns, both, or a mix;
        batches of sets at places apart and of everything else. Of these three thousand batches,
        1,025 are made at once; 21 are tried at once and do not read back, and 8 are refused while
        their edits are computed, each of those then made one operation at a time; and 1,946 are
        made one operation at a time from the start."""
        rng = random.Random(11)
        ways = {"at once": 0, "did not read back": 0, "refused computing": 0, "in turn": 0}
        for _ in range(3_000):
            text = document(rng)
            operations = batch(json.loads(text), rng)
            tried.clear()
            made, by_oracle = alike(text, operations, reads)
            if not at_once(text, operations):
                assert tried == []
                assert made == by_oracle
                ways["in turn"] += 1
            elif tried[0][0]:
                assert made == 2
                ways["at once"] += 1
            else:
                assert made == by_oracle + tried[0][1]
                ways["did not read back" if tried[0][1] else "refused computing"] += 1
        assert ways == {
            "at once": 1025,
            "did not read back": 21,
            "refused computing": 8,
            "in turn": 1946,
        }


LITERALS = (
    "0",
    "-0",
    "7",
    "1.0",
    "0.50",
    "-2.5e3",
    "1E+2",
    "true",
    "false",
    "null",
    '""',
    '"rpm"',
    '"°C"',
    '"\\u00b0C"',
    '"say \\"hi\\""',
    '"back\\\\"',
    '"a\\nb"',
    '"\\ud83d\\ude00"',
    '"😀"',
    '"\\/"',
    '"tab\\t"',
)
"""Literals as a file may spell them: numbers in several spellings, the three words, and strings
with escapes of several kinds, and with characters outside ascii and outside the basic plane,
written as themselves and as escapes."""

CONTAINERS = ('{"p": [1, {"q": "r"}]}', "[1, 2.0]", "{}", "[]", ' {"k": {"m": null}} ')
"""Values a set may write that are objects or arrays: nested, holding only literals, empty, or with
whitespace around them."""

NOT_JSON = ("x", "NaN", "{", "1 2", '"open')
"""Values a set may be given that are not one json value."""

KEYS = ("a", "b", "c", "unit", "name", "x y", "°", 'q"t', "back\\", "a.b", "k[0]", "b.c")
"""The keys of a random object's members, as json means them: some needing escapes, and some
holding a dot or a bracket, which the scan records under a pointer naming something else."""


def document(rng: random.Random) -> str:
    """A random document, laid out at random: line feeds, carriage returns, both, or a mix."""
    newlines = rng.choice([("\n",), ("\r\n",), ("\r",), ("\n", "\r\n")])
    unit = rng.choice(["  ", "    ", "\t", " "])
    top = _container(rng, 0, "", newlines, unit)
    return rng.choice(["", " ", "\n"]) + top + rng.choice(["", "\n", "\r\n"])


def _value(
    rng: random.Random, depth: int, indent: str, newlines: tuple[str, ...], unit: str
) -> str:
    if depth >= 4 or rng.random() < 0.5:
        return rng.choice(LITERALS)
    return _container(rng, depth, indent, newlines, unit)


def _container(
    rng: random.Random, depth: int, indent: str, newlines: tuple[str, ...], unit: str
) -> str:
    """An object or an array of up to five entries: on one line, one entry per line, or its first
    entry on the line it opens on and the others one per line."""
    is_object = rng.random() < 0.6
    opening, closing = ("{", "}") if is_object else ("[", "]")
    count = rng.choice([0, 1, 2, 3, 5])
    layout = rng.choice(["one line", "one per line", "first on the opening line"])
    deeper = indent if layout == "one line" else indent + unit
    keys = rng.sample(KEYS, count) if is_object else [None] * count
    parts = []
    for key in keys:
        value = _value(rng, depth + 1, deeper, newlines, unit)
        if key is None:
            parts.append(value)
        else:
            spelled = json.dumps(key, ensure_ascii=rng.random() < 0.5)
            parts.append(spelled + rng.choice([":", ": ", " : "]) + value)
    if not parts:
        return opening + rng.choice(["", " ", rng.choice(newlines) + indent]) + closing
    if layout == "one line":
        inner = rng.choice([",", ", "]).join(parts)
        return opening + rng.choice(["", " "]) + inner + rng.choice(["", " "]) + closing
    lines = [f"{part}," for part in parts[:-1]] + [parts[-1]]
    head = "" if layout == "one per line" else lines.pop(0)
    body = "".join(rng.choice(newlines) + deeper + line for line in lines)
    return opening + head + body + rng.choice(newlines) + indent + closing


def _pointers(value: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    """Every value of a parsed document with a pointer spelled the way the scan spells one, the
    top of the file included: under a key holding a dot or a bracket, that pointer names
    something else, or nothing."""
    yield pointer, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _pointers(item, f"{pointer}.{key}" if pointer else key)
    elif isinstance(value, list):
        for index_, item in enumerate(value):
            yield from _pointers(item, f"{pointer}[{index_}]")


def batch(data: Any, rng: random.Random) -> list[Operation]:
    """A random batch over ``data``: half the time up to six sets of literals at places none of
    which nests within another; otherwise up to five operations of every kind, sets of anything
    anywhere among them."""
    found = list(_pointers(data))
    if rng.random() < 0.5:
        apart: list[str] = []
        for pointer, _ in rng.sample(found, len(found)):
            if not any(_nests(pointer, other) or _nests(other, pointer) for other in apart):
                apart.append(pointer)
        return [Operation("set", pointer, rng.choice(LITERALS)) for pointer in apart[:6]]
    operations: list[Operation] = []
    for _ in range(rng.randint(1, 5)):
        pointer, value = rng.choice(found)
        roll = rng.random()
        if roll < 0.6:
            operations.append(Operation("set", pointer, _raw(rng)))
        elif roll < 0.7 and isinstance(value, dict):
            added = f"{pointer}.{rng.choice(KEYS)}" if pointer else rng.choice(KEYS)
            operations.append(Operation("set", added, _raw(rng)))
        elif roll < 0.8 and isinstance(value, list):
            at = f"{pointer}[{rng.randint(0, len(value))}]"
            operations.append(Operation(rng.choice(["insert", "set"]), at, _raw(rng)))
        elif roll < 0.9:
            operations.append(Operation("remove", pointer))
        else:
            operations.append(Operation("move", pointer, to=rng.randint(0, 3)))
    return operations


def _raw(rng: random.Random) -> str | None:
    roll = rng.random()
    if roll < 0.75:
        return rng.choice(LITERALS)
    if roll < 0.9:
        return rng.choice(CONTAINERS)
    if roll < 0.97:
        return rng.choice(NOT_JSON)
    return None


def _nests(pointer: str, within: str) -> bool:
    return pointer == within or within == "" or pointer.startswith((f"{within}.", f"{within}["))
