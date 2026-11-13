"""A file edited at many places is read once more after the edit, not once per place.

``edit_text`` makes a batch of sets none of which can depend on what another one writes from the
one reading of the file, and reads the text it leaves once; ``_independent`` decides which batches
those are - literals set in place of values, and members added to objects, as ``ddd id`` gives
every declaration of a file its id. Every other batch, and one that is refused or does not read
back once made at once, is made one operation at a time and verified after each, as before. Both
ways have to answer alike: ``oracle`` below is ``edit_text`` as it stood before a batch could be
made at once, and the engine is held to its every answer - the text, or the refusal's code and
sentence - on every example's files, on a generated project's rename and ids, on random documents
and batches, and on batches one operation of which is made wrong. What an edit reads is counted,
never timed, and grows with the file rather than with its square.
"""

from __future__ import annotations

import copy
import json
import math
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from generate_project import generate

import ddd.editing as editing
from conftest import EXAMPLES, component, declare
from ddd import identity
from ddd.diagnostics import DiagnosticBag
from ddd.editing import (
    DEFAULT_INDENT_UNIT,
    INVALID,
    UNREADABLE,
    UNVERIFIED,
    EditError,
    FileChange,
    Operation,
    TextEdit,
    apply_changes,
    edit_text,
    fingerprint,
    indent_unit,
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


class OverBudgetError(AssertionError):
    """An edit read more characters than the work it was allowed (:class:`Work`)."""


@dataclass
class Work:
    """The characters an edit reads: every character of each text it parses, and every one a
    slice of a parsed text copies or a search of one goes over, the search for a line's
    indentation among them - up to ``budget``, past which the edit is stopped rather than
    finished."""

    count: int = 0
    budget: float = math.inf

    def add(self, characters: int) -> None:
        self.count += characters
        if self.count > self.budget:
            raise OverBudgetError(f"the edit read more than {self.budget:,.0f} characters")


class Counted(str):
    """A text whose slices and searches count into ``work`` the characters they copy or go over:
    what each of the engine's measures of the lines around a place costs, which python's own
    methods do not say."""

    work: Work

    def __new__(cls, text: str, work: Work) -> Counted:
        made = super().__new__(cls, text)
        made.work = work
        return made

    def __getitem__(self, key):
        found = str.__getitem__(self, key)
        self.work.add(len(found))
        return found

    def find(self, sub, start=None, end=None):
        begin, stop, _ = slice(start, end).indices(len(self))
        found = str.find(self, sub, begin, stop)
        self.work.add(max(0, (found + len(sub) if found >= 0 else stop) - begin))
        return found

    def rfind(self, sub, start=None, end=None):
        begin, stop, _ = slice(start, end).indices(len(self))
        found = str.rfind(self, sub, begin, stop)
        self.work.add(max(0, stop - (found if found >= 0 else begin)))
        return found


@pytest.fixture
def work(monkeypatch: pytest.MonkeyPatch) -> Work:
    """The work of every edit made while a test runs: each text ``_read`` parses is counted
    whole, and read on as a :class:`Counted` text, so that the document every measure is taken
    of counts as well; and each search for a line's indentation, which a regular expression
    makes, by the characters it goes over - the indentation, and the one ending it."""
    counted = Work()
    real_read = editing._read
    real_indentation = editing._indentation

    def read(text: str, code: str, refusal: str) -> Document:
        counted.add(len(text))
        return real_read(Counted(text, counted), code, refusal)

    def indentation(text: str, start: int) -> str:
        found = real_indentation(text, start)
        counted.add(len(found) + 1)
        return found

    monkeypatch.setattr(editing, "_read", read)
    monkeypatch.setattr(editing, "_indentation", indentation)
    return counted


def grows_linearly(work: Work, edit: Callable[[int], object]) -> None:
    """Asserts that ``edit`` made at 4,000 declarations reads between three and five times the
    characters it reads at 1,000. Four times the file is four times the reading for work that
    grows with the file, and sixteen for work that grows with its square - which is stopped at
    five times rather than finished."""
    work.count, work.budget = 0, math.inf
    edit(1_000)
    small = work.count
    work.count, work.budget = 0, 5 * small
    edit(4_000)
    assert work.count >= 3 * small


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


def objects_of(value: Any, pointer: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Every object of a parsed document that holds members, with the pointer naming it, in
    document order - but for those under a key holding a dot or a bracket, as
    :func:`literal_leaves` leaves them out."""
    if isinstance(value, dict):
        if value:
            yield pointer, value
        for key, item in value.items():
            if not any(mark in key for mark in ".[]"):
                yield from objects_of(item, f"{pointer}.{key}" if pointer else key)
    elif isinstance(value, list):
        for index_, item in enumerate(value):
            yield from objects_of(item, f"{pointer}[{index_}]")


def another(value: Any, rng: random.Random) -> str:
    """A literal to set in place of ``value``, as json text: a string with a quote, a backslash
    and characters outside ascii added, written as themselves or as escapes; the other truth
    value; for a null, 0 or a string; or a number in one of several spellings."""
    if isinstance(value, str):
        return json.dumps(f'{value}"\\é😀', ensure_ascii=rng.random() < 0.5)
    if isinstance(value, bool):
        return json.dumps(not value)
    if value is None:
        return rng.choice(["0", '"none"'])
    return rng.choice(["1.0", "-0", "2.50", "1E+2", "-7"])


def declarations(count: int) -> dict[str, Any]:
    """A component of ``count`` output declarations, ``V0`` onwards, none of which states an id."""
    return component("B", *(declare("output", f"V{n}") for n in range(count)))


def ids_for(text: str) -> list[Operation]:
    """``ddd id``'s batch for a file: an id for every producing declaration it states none for,
    each id told apart from the others by the declaration's place."""
    return [
        Operation("set", f"{definition}.id", f'"k{index:011d}"')
        for index, (definition, _) in enumerate(identity.unstamped(Document(text)))
    ]


class TestABatchIsReadOnce:
    def test_a_file_set_at_many_places_is_read_twice_not_once_per_place(self, reads):
        """Read once as it was given and once as it was left, where one operation after another
        read it again after each of them: 41 times for these forty places."""
        text = json.dumps({"units": [{"unit": f"u{n}", "described": n} for n in range(40)]})
        operations = [Operation("set", f"units[{n}].unit", f'"v{n}"') for n in range(40)]
        assert alike(text, operations, reads) == (2, 41)
        assert reads[-1] == text.replace('"unit": "u', '"unit": "v')

    def test_a_file_given_an_id_at_many_places_is_read_twice_not_once_per_place(self, reads):
        """``ddd id``'s batch: an id added after the name of every declaration, each on a line of
        its own. Made one operation after another, the file was read 41 times for these forty."""
        text = json.dumps(declarations(40), indent=2)
        operations = ids_for(text)
        assert len(operations) == 40
        assert alike(text, operations, reads) == (2, 41)
        assert reads[-1].count('"id": "k') == 40


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

    def test_members_added_to_objects_apart_are_made_at_once(self, reads):
        """A member its object has not got, added to an object that holds members already and is
        given no other: laid out from the lines around it, which neither a literal set in place
        of another nor a member added to another object changes."""
        operations = [
            Operation("set", "a.e", "3"),
            Operation("set", "e", '"z"'),
            Operation("set", "a.b", "2.0"),
            Operation("set", "list[2]", "4"),
        ]
        assert at_once(self.TEXT, operations)
        assert alike(self.TEXT, operations, reads) == (2, 5)
        assert edit_text(self.TEXT, operations) == (
            '{"a": {"b": 2.0, "c": "x", "e": 3}, "list": [1, 2, 4], "d": null, "e": "z"}'
        )

    def test_ids_given_to_the_declarations_of_a_file_are_made_at_once(self, reads):
        """``ddd id``'s batch over a file whose definitions are written one member to a line, on
        one line, with the name last, and with an id stated as ``null``: each id after the name,
        on a line of its own or on the name's, and in place of the ``null``."""
        text = (
            '{\n  "component": {\n    "name": "A",\n    "interface": [\n'
            '      {"scope": "output", "definition": {\n'
            '        "name": "S",\n        "kind": "measurement"\n      }},\n'
            '      {"scope": "local", "definition": {"name": "T", "kind": "measurement"}},\n'
            '      {"scope": "output", "definition": {"kind": "measurement", "name": "U"}},\n'
            '      {"scope": "output", "definition": {"name": "W", "id": null, "kind": "v"}}\n'
            "    ]\n  }\n}\n"
        )
        operations = ids_for(text)
        assert at_once(text, operations)
        assert alike(text, operations, reads) == (2, 5)
        assert edit_text(text, operations) == (
            text.replace('"name": "S",\n', '"name": "S",\n        "id": "k00000000000",\n')
            .replace('"name": "T",', '"name": "T", "id": "k00000000001",')
            .replace('"name": "U"}', '"name": "U", "id": "k00000000002"}')
            .replace('"id": null', '"id": "k00000000003"')
        )

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
            [Operation("set", "a.e", "2"), Operation("set", "a.f", "3")],
            [Operation("set", "a", "1"), Operation("set", "e", "3")],
            [Operation("set", "e", "3"), Operation("set", "list", '"none"')],
            [Operation("set", "a.b", "2"), Operation("set", "a.e", '{"k": 1}')],
            [Operation("set", "a.b", "2"), Operation("set", "d.k", "3")],
            [Operation("set", "a.b", "2"), Operation("set", "x.k", "3")],
            [Operation("set", "a.b", "2"), Operation("set", "a[0]", "3")],
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
            "two members added to one object",
            "a member added beside an object set in place of a literal",
            "a member added beside an array set in place of a literal",
            "a member added holding an object",
            "a member of a literal",
            "a member of nothing",
            "an index into an object",
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

    def test_a_member_added_to_an_object_holding_none_is_made_one_operation_at_a_time(self, reads):
        """Its object is written anew, the member on a line of its own indented by the file's
        unit, which the member added before it changes: that one goes on a line of its own
        indented deeper than its object opens, the first entry the file so writes, and the unit
        is read off it - four spaces, where read off the lines as they were it was the two of a
        file that nests nothing that way."""
        text = '{"name": {"q": 1\n    },\n"e": {}}'
        operations = [Operation("set", "id", '"abc"'), Operation("set", "e.k", "1")]
        assert not at_once(text, operations)
        assert answer(edit_text, text, operations) == (
            "text",
            '{"name": {"q": 1\n    },\n    "id": "abc",\n"e": {\n    "k": 1\n}}',
        )
        made, by_oracle = alike(text, operations, reads)
        assert made == by_oracle

    def test_a_member_whose_pointer_a_key_holding_a_dot_spells_is_made_one_operation_at_a_time(
        self, reads
    ):
        """The member ``"b.c"`` is recorded under the pointer the ``c`` added to ``b`` takes,
        which names the member added from then on: one operation after another, the member added
        to the top of the file next finds ``b``'s ``c`` the last entry the top of the file
        writes, goes after it, inside ``b``, and does not read back. Made at once, from the text
        as it was read, it went after ``b`` and read back - an answer no order of the operations
        gives."""
        text = '{"b.c": 1, "b": {"a": 2}}'
        operations = [Operation("set", "b.c", "3"), Operation("set", "d", "4")]
        assert not at_once(text, operations)
        assert answer(edit_text, text, operations) == (
            UNVERIFIED,
            "the edited file does not read back as the intended document",
        )
        made, by_oracle = alike(text, operations, reads)
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

    def test_a_batch_that_reads_back_as_1_where_1_0_was_meant_is_refused(self, reads):
        """Compared as the text each document dumps to, which tells ``1`` from ``1.0``. Here the
        1.0 meant for ``a``'s ``b`` is written over the member spelled ``a.b``, as above, but each
        held 1: compared with python's ``==``, which takes 1 and 1.0 for one value, the batch read
        back as the document it was meant to leave, and the text it left was answered, to be
        written into the file."""
        text = '{"a": {"b": 1}, "a.b": 1, "c": 3}'
        operations = [Operation("set", "a.b", "1.0"), Operation("set", "c", "4")]
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

    def test_a_value_not_given_as_text_is_refused_as_one_at_a_time_refuses_it(self, reads):
        """What is tried at once is decided by the value's text, and a value given as anything
        else has none: the batch is made one operation at a time from the start, which refuses
        it, rather than raising while the batch is looked at."""
        operations = [Operation("set", "a.b", "2"), Operation("set", "d", 5)]
        assert not at_once(self.TEXT, operations)
        assert answer(edit_text, self.TEXT, operations) == (
            INVALID,
            "a value is given as json text",
        )
        made, by_oracle = alike(self.TEXT, operations, reads)
        assert made == by_oracle

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
        """Laid out to fit the lines around it, which a set beside it can change. In the first,
        the one value the object writes over several lines is replaced with a literal, which puts
        the object on one line, and the member added then joins it; in the second, replacing it
        moves the end of the member the new one follows to another line, whose indentation the new
        one takes. Laid out from the lines as they were
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


# Ways a member's edit can be made wrong: each is handed the document the edit was made on, the
# definition the member goes into, and the edit the engine made, and answers the edit made wrong.


def another_id(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    return TextEdit(edit.start, edit.end, edit.text.replace('"k', '"x'))


def another_key(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    return TextEdit(edit.start, edit.end, edit.text.replace('"id"', '"di"'))


def the_key_twice(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    return TextEdit(edit.start, edit.end, edit.text * 2)


def no_comma(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    return TextEdit(edit.start, edit.end, edit.text.removeprefix(","))


def nothing(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    return TextEdit(edit.start, edit.end, "")


def in_another_declaration(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    """After the name of the declaration that follows, or of the first for the last."""
    index = int(definition.removeprefix("component.interface[").split("]")[0])
    count = len(document.value_at("component.interface"))
    span = document.span_of(f"component.interface[{(index + 1) % count}].definition.name")
    assert span is not None
    return TextEdit(span[1], span[1], edit.text)


def in_the_entry_around_it(document: Document, definition: str, edit: TextEdit) -> TextEdit:
    """After the entry's ``scope``: the entry states the id, and its definition none."""
    span = document.span_of(f"{definition.removesuffix('.definition')}.scope")
    assert span is not None
    return TextEdit(span[1], span[1], edit.text)


class TestOneOperationOfABatchMadeWrong:
    """A batch made at once is verified once, against the document every one of its operations
    was meant to leave, where one operation after another is verified after each of them.
    Whatever one operation's edit is made to write wrong, wherever it sits in the batch, that one
    reading catches it as the reading after the operation did: the batch made at once does not
    read back, and made again one operation at a time it is refused at that operation, as it
    always was."""

    TEXT = json.dumps(declarations(40), indent=2)
    IDS = ids_for(TEXT)

    @pytest.mark.parametrize("wrong", [0, 17, 39], ids=["first", "within", "last"])
    @pytest.mark.parametrize(
        "way",
        [
            another_id,
            another_key,
            the_key_twice,
            no_comma,
            nothing,
            in_another_declaration,
            in_the_entry_around_it,
        ],
        ids=lambda way: way.__name__.replace("_", " "),
    )
    def test_a_member_added_wrong_is_refused_as_the_reading_after_it_refused_it(
        self, monkeypatch, reads, tried, wrong, way
    ):
        """The id of the first, a middle or the last declaration written wrong: refused at that
        operation, as the oracle refuses it, after the one reading of the batch made at once."""
        real = editing.member_addition
        definition = f"component.interface[{wrong}].definition"

        def added(document, pointer, key, raw, *, verbatim=False):
            edit = real(document, pointer, key, raw, verbatim=verbatim)
            return way(document, pointer, edit) if pointer == definition else edit

        monkeypatch.setattr(editing, "member_addition", added)
        assert at_once(self.TEXT, self.IDS)
        refused, by_engine, by_oracle = refusals(self.TEXT, self.IDS, reads)
        assert refused[0] == UNVERIFIED
        assert tried == [(False, 1)]
        assert (by_engine, by_oracle) == (wrong + 3, wrong + 2)

    NULLED = json.dumps(
        component(
            "B", *(declare("output", f"V{n}", **({"id": None} if n % 2 else {})) for n in range(40))
        ),
        indent=2,
    )
    """Every other declaration stating its id as ``null``, which the id is set in place of."""

    @pytest.mark.parametrize(
        "written",
        ['"x00000000017"', '"k00000000017", "id": "x"', '"k00000000017" "x"', "17"],
        ids=["another id", "the key twice", "no json", "a number"],
    )
    def test_an_id_set_in_place_of_a_null_wrong_is_refused_as_the_reading_after_it_refused_it(
        self, monkeypatch, reads, tried, written
    ):
        """A set in place of a value, in a batch whose other half adds members: the id of the
        eighteenth declaration, which states it as ``null``, written wrong."""
        operations = ids_for(self.NULLED)
        assert operations[17].raw == '"k00000000017"'
        assert self.NULLED.count('"id": null') == 20
        real = editing.lay_out
        monkeypatch.setattr(
            editing,
            "lay_out",
            lambda raw, **layout: written if raw == '"k00000000017"' else real(raw, **layout),
        )
        assert at_once(self.NULLED, operations)
        refused, by_engine, by_oracle = refusals(self.NULLED, operations, reads)
        assert refused[0] == UNVERIFIED
        assert tried == [(False, 1)]
        assert (by_engine, by_oracle) == (20, 19)

    @pytest.mark.parametrize("wrong", [16, 17], ids=["a set in place", "a member added"])
    def test_a_number_written_in_another_spelling_is_refused(
        self, monkeypatch, reads, tried, wrong
    ):
        """``1`` where ``1.0`` was meant is another value to DDD, the first an integer: the one
        reading tells the two apart as the reading after the operation did."""
        text = json.dumps({"list": [{"f": 0.5} for _ in range(40)]}, indent=2)
        operations = [
            Operation("set", f"list[{n}].{'g' if n % 2 else 'f'}", f"{n}.0") for n in range(40)
        ]
        real = editing.lay_out
        monkeypatch.setattr(
            editing,
            "lay_out",
            lambda raw, **layout: str(wrong) if raw == f"{wrong}.0" else real(raw, **layout),
        )
        assert at_once(text, operations)
        refused, by_engine, by_oracle = refusals(text, operations, reads)
        assert refused == (
            UNVERIFIED,
            "the edited file does not read back as the intended document",
        )
        assert tried == [(False, 1)]
        assert (by_engine, by_oracle) == (wrong + 3, wrong + 2)

    @pytest.mark.parametrize(
        ("pointer", "sentence"),
        [
            (
                "component.interface[40].definition.id",
                "component.interface[40].definition is not an object",
            ),
            ("component.name.id", "component.name is not an object"),
            (
                "component.interface[3]..definition.id",
                "'component.interface[3]..definition.id' is not a pointer",
            ),
        ],
        ids=["a declaration the file has not got", "a member of a string", "no pointer"],
    )
    def test_an_operation_that_names_nothing_is_refused_among_operations_that_do(
        self, reads, tried, pointer, sentence
    ):
        """Never tried at once: made one operation at a time from the start, and refused at it."""
        operations = [*self.IDS[:17], Operation("set", pointer, '"k99999999999"'), *self.IDS[17:]]
        assert not at_once(self.TEXT, operations)
        refused, by_engine, by_oracle = refusals(self.TEXT, operations, reads)
        assert refused == (INVALID, sentence)
        assert tried == []
        assert (by_engine, by_oracle) == (18, 18)


def refusals(
    text: str, operations: Sequence[Operation], read: list[str]
) -> tuple[tuple[str, str], int, int]:
    """Asserts that the engine refuses the batch as the oracle refuses it, and hands back the
    refusal's code and sentence and how many texts each of the two read: the engine's, then the
    oracle's."""
    read.clear()
    refused = answer(edit_text, text, operations)
    by_engine = len(read)
    read.clear()
    assert answer(oracle, text, operations) == refused
    assert refused[0] != "text"
    return refused, by_engine, len(read)


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
        """Every value of the file that is not a container set anew, made at once; every object
        holding members given one more, made at once; then random batches of every kind over the
        same file."""
        text = path.read_text(encoding="utf-8-sig")
        rng = random.Random(path.name)
        operations = [
            Operation("set", pointer, another(value, rng))
            for pointer, value in literal_leaves(json.loads(text))
        ]
        rng.shuffle(operations)
        assert at_once(text, operations)
        assert alike(text, operations, reads) == (2, len(operations) + 1)
        added = [
            Operation("set", f"{pointer}.{key}" if pointer else key, rng.choice(LITERALS))
            for pointer, members in objects_of(json.loads(text))
            for key in [next(key for key in ("id", "added", "added2") if key not in members)]
        ]
        rng.shuffle(added)
        assert at_once(text, added)
        assert alike(text, added, reads) == (2, len(added) + 1)
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

    def test_a_generated_projects_ids(self, tmp_path: Path, reads):
        """``ddd id --assign`` over a project of three thousand declarations in thirty components,
        no output of which states an id: every file's ids made at once."""
        made = generate(tmp_path / "p", 3_000, "large", missing_ids=1.0)
        files = sorted((made.project.parent / "components").glob("*.ddd.json"))
        assert len(files) == 30
        stamped = 0
        for path in files:
            text = path.read_text(encoding="utf-8")
            operations = ids_for(text)
            stamped += len(operations)
            assert alike(text, operations, reads) == (2, len(operations) + 1)
        assert stamped == made.unnamed > 0

    def test_random_documents_and_batches(self, reads, tried):
        """Documents of literals, strings with escapes, nested objects and arrays, laid out on
        one line, one entry per line, or both, with line feeds, carriage returns, both, or a mix;
        batches of sets at places apart and of everything else. Of these three thousand batches,
        1,028 are made at once; 21 are tried at once and do not read back, and 9 are refused while
        their edits are computed, each of those then made one operation at a time; and 1,942 are
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
            "at once": 1028,
            "did not read back": 21,
            "refused computing": 9,
            "in turn": 1942,
        }

    def test_random_documents_and_batches_of_places_apart(self, reads, tried):
        """Documents as above, and batches of sets of literals at places none of which nests
        within another: in place of a value, or a member added to an object - an ``id`` where it
        states a ``name``, or another key it has not got - at most one to an object. Of these
        three thousand batches, 1,205 are made at once; 29 are tried at once and do not read back,
        each then made one operation at a time, and none is refused while its edits are computed;
        and 1,766 are made one operation at a time from the start - a member added to an object
        holding none, or beside an object or an array a literal is set in place of, among them."""
        rng = random.Random(13)
        ways = {"at once": 0, "did not read back": 0, "refused computing": 0, "in turn": 0}
        for _ in range(3_000):
            text = document(rng)
            operations = apart(json.loads(text), rng)
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
            "at once": 1205,
            "did not read back": 29,
            "refused computing": 0,
            "in turn": 1766,
        }


class TestTheWorkGrowsWithTheFile:
    """What an edit reads grows with the file it edits, not with the square of it: counted in
    the characters it parses, copies and searches (:class:`Work`), at 1,000 declarations and at
    4,000, and never timed."""

    @pytest.mark.parametrize(
        "newline",
        ["\n", "\r\n", "\r"],
        ids=["line feeds", "carriage return and line feed", "carriage returns"],
    )
    @pytest.mark.parametrize(
        "indent", [2, None, 0], ids=["indented", "on one line", "on lines indented by nothing"]
    )
    def test_ddd_id_over_one_file(self, tmp_path, work, indent, newline):
        """``ddd id --assign`` hands the engine one batch for the file, an id for every
        declaration. Made one id after another, each verified, the file was read again for every
        id; and each id's line was measured by copying the rest of the text, and by searching it
        to its end for a carriage return - and, in a file that nests nothing on a line of its
        own, the whole document looked through for the indentation unit, which no id is laid out
        in."""

        def stamped(count: int) -> None:
            path = tmp_path / f"{count}.ddd.json"
            text = json.dumps(declarations(count), indent=indent).replace("\n", newline)
            path.write_bytes(text.encode("utf-8"))
            assert identity.assign(path) == count

        grows_linearly(work, stamped)

    @pytest.mark.parametrize(
        ("key", "raw", "written"),
        [
            ("unit", '"rpm"', '"rpm"'),
            ("limits", '{"min":0,"max":255}', '{ "min": 0, "max": 255 }'),
        ],
        ids=["a literal", "an object"],
    )
    def test_a_member_added_to_a_file_written_on_one_line(self, tmp_path, work, key, raw, written):
        """Added to the last declaration of the component, as ``ddd gui`` applies it: the member
        joins its object's line, which reads nothing of the lines around it. The engine looked
        for the file's indentation unit first, asking every entry of the file whether it sat on
        a line of its own, and with what indentation - copying the rest of the text for each."""

        def added(count: int) -> None:
            path = tmp_path / f"{count}.ddd.json"
            path.write_text(json.dumps(declarations(count)), encoding="utf-8")
            pointer = f"component.interface[{count - 1}].definition.{key}"
            operation = Operation("set", pointer, raw)
            apply_changes([FileChange(path, fingerprint(path.read_bytes()), (operation,))])
            assert path.read_text(encoding="utf-8").endswith(f', "{key}": {written}}}}}]}}}}')

        grows_linearly(work, added)

    @pytest.mark.parametrize(
        ("indent", "margin"),
        [(None, 0), (0, 0), (None, 10)],
        ids=["on one line", "on lines indented by nothing", "on one line indented far"],
    )
    def test_the_indentation_unit_of_a_file_that_nests_nothing_on_a_line_of_its_own(
        self, work, indent, margin
    ):
        """Read off the first entry written on a line of its own, indented deeper than the line
        its container opens on - which none of these files has, so that every entry is looked
        at, and each used to copy the rest of the text to find its own indentation. The last is
        indented by ten spaces a declaration, which every one of its entries sits on: read once
        for the line, and not again for each."""

        def unit(count: int) -> None:
            spelled = " " * (margin * count) + json.dumps(declarations(count), indent=indent)
            assert indent_unit(Document(Counted(spelled, work))) == DEFAULT_INDENT_UNIT

        grows_linearly(work, unit)


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


def apart(data: Any, rng: random.Random) -> list[Operation]:
    """A random batch of up to six sets of literals at places none of which nests within another:
    in place of a value, or - for an object, more often than not - a member it has not got added
    to it, an ``id`` where it states a ``name``, or one of :data:`KEYS`; at most one to an
    object, every object being looked at once."""
    found = list(_pointers(data))
    chosen: list[str] = []
    for pointer, value in rng.sample(found, len(found)):
        target = pointer
        if isinstance(value, dict) and rng.random() < 0.6:
            keys = [key for key in KEYS if key not in value]
            if "name" in value and "id" not in value and rng.random() < 0.5:
                keys = ["id"]
            key = rng.choice(keys)
            target = f"{pointer}.{key}" if pointer else key
        if not any(_nests(target, other) or _nests(other, target) for other in chosen):
            chosen.append(target)
    return [Operation("set", target, rng.choice(LITERALS)) for target in chosen[:6]]


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
