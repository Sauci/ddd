"""The edit engine: every change a description file is given, in the file's own layout."""

from __future__ import annotations

import codecs
import errno
import os
import re
import stat
import sys
import threading
import time
import types
from pathlib import Path

import pytest

import ddd.editing as editing
from ddd.backends.base import STAGING_SUFFIX as ARTEFACT_STAGING_SUFFIX
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    UNVERIFIED,
    UNWRITABLE,
    EditError,
    FileChange,
    Operation,
    Written,
    apply_changes,
    edit_text,
    fingerprint,
    indent_of_line_at,
    indent_unit,
    lay_out,
    member_addition,
    newline_at,
    parse_raw,
    removal,
    replacement,
    restore,
    unchanged,
)
from ddd.file_names import CREATED_NAME_MAX, NAME_MAX, STAGING_SUFFIX
from ddd.lsp.ranges import Document


class TestRawValues:
    @pytest.mark.parametrize(
        ("raw", "value"),
        [("1.0", 1.0), ('"rpm"', "rpm"), ("[1, 2]", [1, 2]), (" {} ", {}), ("null", None)],
    )
    def test_one_json_value_is_read(self, raw, value):
        assert parse_raw(raw) == value

    @pytest.mark.parametrize(
        "raw", ["", "1 2", "NaN", "-Infinity", "{'a': 1}", "rpm", '{"a": 1, "a": 2}']
    )
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
    def test_the_indentation_is_the_one_of_the_line_the_offset_sits_on(self, text, offset, indent):
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
            self.layout('{"kind":"linear","factor":0.50}') == '{ "kind": "linear", "factor": 0.50 }'
        )
        assert self.layout("[1,\n 2.0]") == "[1, 2.0]"

    def test_an_empty_container_is_its_brackets(self):
        assert self.layout(" { } ") == "{}"
        assert self.layout("[ ]") == "[]"

    def test_a_container_of_containers_goes_one_entry_per_line(self):
        raw = '{"scope":"input","definition":{"name":"A","conversion":{"factor":1.0},"init":[0,1]}}'
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

    @pytest.mark.parametrize("depth", [600, 3000], ids=["writing", "reading"])
    def test_a_value_too_deep_to_lay_out_is_refused_as_too_deep_to_read(self, depth):
        """Python's parser reads a value far deeper than its layout goes: reading the tokens
        spends a frame of the stack a level, and writing them out two, so six hundred levels
        outrun the writing and three thousand the reading as well. Either is refused as the
        loader refuses a document deeper than the parser goes, rather than raising
        ``RecursionError``, which ``ddd gui`` answered an edit carrying one with: a ``500``."""
        raw = "[" * depth + "]" * depth
        with pytest.raises(EditError) as refused:
            self.layout(raw)
        assert (refused.value.code, str(refused.value)) == (
            INVALID,
            f"{raw!r} is not one json value: the json is nested too deeply to read",
        )


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
            MULTI.replace("    ]\n  }\n}", '    ],\n    "description": "the pump"\n  }\n}')
        )

    def test_a_structured_value_is_laid_out_in_the_files_own_indentation(self):
        raw = '[{"name":"T","members":[{"name":"x","datatype":"uint8"}]}]'
        assert edited(MULTI, Operation("set", "component.types", raw)) == MULTI.replace(
            "    ]\n  }\n}",
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

    def test_a_whole_document_that_is_a_literal_can_be_replaced(self):
        assert edited("5", Operation("set", "", "6")) == "6"

    def test_a_verbatim_member_keeps_the_text_it_was_copied_as(self):
        edit = member_addition(Document('{"a": 1}'), "", "c", '{ "kind":"linear" }', verbatim=True)
        assert edit.text == ', "c": { "kind":"linear" }'

    def test_a_member_that_is_already_written_is_not_added_again(self):
        with pytest.raises(EditError) as refused:
            member_addition(Document('{"a": 1}'), "", "a", "2")
        assert refused.value.code == INVALID

    def test_replacing_a_value_that_is_not_written_is_invalid(self):
        with pytest.raises(EditError) as refused:
            replacement(Document('{"a": 1}'), "b", "2")
        assert refused.value.code == INVALID


UNSTAMPED = (
    "{\n"
    '  "component": {\n'
    '    "name": "A",\n'
    '    "interface": [\n'
    "      {\n"
    '        "scope": "output",\n'
    '        "definition": {\n'
    '          "name": "S",\n'
    '          "kind": "measurement",\n'
    '          "volatile": false\n'
    "        }\n"
    "      }\n"
    "    ]\n"
    "  }\n"
    "}\n"
)
"""A component whose one declaration states its name first and no id."""

STAMPED_AS = '          "name": "S",\n          "id": "k7m2q9xr4t8w",\n'
"""The lines of :data:`UNSTAMPED` an id given to the declaration goes into: right after its name."""


class TestAnIdentity:
    """An id is written after the ``name`` it identifies, where ``ddd id`` has always written it
    and the examples spell it, and where the page's fix and the editor's must put it as well:
    which of them gave a declaration its id is not something its file should show."""

    def test_an_id_goes_after_the_name_and_not_after_the_last_member(self):
        stamped = edited(UNSTAMPED, Operation("set", f"{DEFINITION}.id", '"k7m2q9xr4t8w"'))
        assert stamped == UNSTAMPED.replace('          "name": "S",\n', STAMPED_AS)

    def test_the_line_it_adds_ends_like_the_line_it_follows(self):
        crlf = UNSTAMPED.replace("\n", "\r\n")
        stamped = edited(crlf, Operation("set", f"{DEFINITION}.id", '"k7m2q9xr4t8w"'))
        assert stamped == crlf.replace(
            '          "name": "S",\r\n', STAMPED_AS.replace("\n", "\r\n")
        )

    def test_an_id_joins_an_object_written_on_one_line_after_its_name_on_that_line(self):
        stamped = edited(MULTI, Operation("set", f"{DEFINITION}.id", '"k7m2q9xr4t8w"'))
        assert stamped == MULTI.replace(
            '"name": "S", "kind"', '"name": "S", "id": "k7m2q9xr4t8w", "kind"'
        )

    def test_an_id_goes_last_in_an_object_with_no_name_to_follow(self):
        stamped = edited('{"a": 1, "b": 2}', Operation("set", "id", '"k7m2q9xr4t8w"'))
        assert stamped == '{"a": 1, "b": 2, "id": "k7m2q9xr4t8w"}'

    def test_an_id_stated_as_null_is_replaced_where_it_stands(self):
        text = '{ "name": "S", "kind": "measurement", "id": null, "volatile": false }'
        stamped = edited(text, Operation("set", "id", '"k7m2q9xr4t8w"'))
        assert stamped == text.replace("null", '"k7m2q9xr4t8w"')

    def test_any_other_member_still_goes_after_the_last(self):
        """The rule is the id's: a key that identifies nothing is written where the file ends
        its object."""
        stamped = edited(UNSTAMPED, Operation("set", f"{DEFINITION}.unit", '"rpm"'))
        assert stamped == UNSTAMPED.replace(
            '          "volatile": false\n',
            '          "volatile": false,\n          "unit": "rpm"\n',
        )

    def test_the_ids_of_two_declarations_and_the_edit_after_them_are_made_in_one_batch(self):
        """Each is verified against the document it was meant to leave, in the order the file
        spells it: an id written after the name and expected after the last member would read
        back as another document, and nothing would be written."""
        two = UNSTAMPED.replace(
            "      }\n    ]",
            "      },\n      {\n"
            '        "scope": "output",\n'
            '        "definition": {\n'
            '          "name": "T",\n'
            '          "kind": "measurement",\n'
            '          "volatile": false\n'
            "        }\n"
            "      }\n    ]",
        )
        stamped = edited(
            two,
            Operation("set", "component.interface[0].definition.id", '"k7m2q9xr4t8w"'),
            Operation("set", "component.interface[1].definition.id", '"b3n5p8s2v6y9"'),
            Operation("set", "component.interface[1].definition.unit", '"rpm"'),
        )
        name = '          "name": "T",\n'
        last = '          "volatile": false\n        }\n      }\n    ]'
        assert stamped == (
            two.replace('          "name": "S",\n', STAMPED_AS)
            .replace(name, name + '          "id": "b3n5p8s2v6y9",\n')
            .replace(last, last.replace("false\n", 'false,\n          "unit": "rpm"\n', 1))
        )


class TestTabs:
    """A file indented with tabs is edited with tabs."""

    TABBED = (
        "{\n"
        '\t"component": {\n'
        '\t\t"name": "A",\n'
        '\t\t"interface": [\n'
        "\t\t\t{\n"
        '\t\t\t\t"scope": "output",\n'
        '\t\t\t\t"definition": {\n'
        '\t\t\t\t\t"name": "S",\n'
        '\t\t\t\t\t"unit": "rpm"\n'
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t]\n"
        "\t}\n"
        "}\n"
    )

    def test_a_value_is_set_in_place(self):
        pointer = f"{DEFINITION}.unit"
        assert edited(self.TABBED, Operation("set", pointer, '"Hz"')) == self.TABBED.replace(
            '"unit": "rpm"', '"unit": "Hz"'
        )

    def test_a_member_is_added_on_a_line_indented_like_the_one_before_it(self):
        pointer = f"{DEFINITION}.kind"
        assert edited(self.TABBED, Operation("set", pointer, '"measurement"')) == (
            self.TABBED.replace(
                '\t\t\t\t\t"unit": "rpm"\n',
                '\t\t\t\t\t"unit": "rpm",\n\t\t\t\t\t"kind": "measurement"\n',
            )
        )

    def test_a_structured_member_is_laid_out_one_tab_per_level(self):
        raw = '[{"name":"T","members":[{"name":"x","datatype":"uint8"}]}]'
        assert edited(self.TABBED, Operation("set", "component.types", raw)) == (
            self.TABBED.replace(
                "\t\t]\n\t}\n}",
                "\t\t],\n"
                '\t\t"types": [\n'
                "\t\t\t{\n"
                '\t\t\t\t"name": "T",\n'
                '\t\t\t\t"members": [\n'
                '\t\t\t\t\t{ "name": "x", "datatype": "uint8" }\n'
                "\t\t\t\t]\n"
                "\t\t\t}\n"
                "\t\t]\n"
                "\t}\n"
                "}",
            )
        )


class TestRemove:
    def test_a_member_takes_the_comma_after_it(self):
        assert edited(MULTI, Operation("remove", "component.name")) == MULTI.replace(
            '    "name": "A",\n', ""
        )

    def test_the_last_member_of_an_object_takes_the_comma_before_it(self):
        assert edited(MULTI, Operation("remove", "component.interface")) == (
            '{\n  "component": {\n    "name": "A"\n  }\n}\n'
        )
        assert edited(MULTI, Operation("remove", f"{DEFINITION}.factor")) == MULTI.replace(
            ', "factor": 1.0', ""
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
    @pytest.mark.parametrize(
        "text",
        [
            "{",
            '{"a": NaN}',
            '{"a": 1, "a": 2}',
            '{"a": {"b": 1}, "a": 2}',
            "[" * 600 + "]" * 600,
        ],
    )
    def test_a_file_the_loader_does_not_read_as_json_is_unreadable(self, text):
        """Python's parser takes ``NaN`` and a key spelled twice, which the loader refuses: read
        by it, a file ``ddd check`` cannot read was edited as though it could, and the scan
        followed ``a.b`` into the first ``a`` of the fourth while the document held the second.
        The last one parses, and is deeper than the scan walks."""
        with pytest.raises(EditError) as refused:
            edited(text, Operation("set", "a.b", "1"))
        assert refused.value.code == UNREADABLE

    def test_an_edit_that_would_spell_a_key_twice_is_unverified(self, monkeypatch):
        """Read back by python's parser, the text kept the last spelling of the key and compared
        equal to the intended document, and a file ``ddd check`` refuses was written."""
        monkeypatch.setattr(editing, "lay_out", lambda raw, **layout: '2, "b": 2')
        with pytest.raises(EditError) as refused:
            edited('{"a": 1}', Operation("set", "b", "2"))
        assert refused.value.code == UNVERIFIED

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

    @pytest.mark.parametrize(
        ("text", "operation"),
        [
            ('{"a.b": 1}', Operation("set", "a.b", "2")),
            ('{"a.b": 1}', Operation("remove", "a.b")),
            ('{"a": {"b": [1, 2]}, "a.b": [0, 0, 0, 0]}', Operation("set", "a.b[3]", "9")),
            ('{"a": {"b": [1]}}', Operation("insert", "a..b[0]", "2")),
            ('{"a]": 1}', Operation("set", "a]", "2")),
        ],
    )
    def test_a_pointer_the_parsed_document_cannot_follow_is_invalid(self, text, operation):
        """A key holding a dot or a bracket is recorded under a pointer the grammar reads as more
        steps than it is, so a pointer can name text the parsed document has nothing at, and a
        pointer can be spelled in ways the grammar reads but no scan writes. Each of these used
        to raise out of the engine - an assertion, a plain ``ValueError``, an ``IndexError`` -
        or, for the last, to be refused as unverified after the wrong member was rewritten."""
        with pytest.raises(EditError) as refused:
            edited(text, operation)
        assert refused.value.code == INVALID

    @pytest.mark.parametrize(
        "operation",
        [
            Operation("set", "list[" + "9" * 4301 + "]", "1"),
            Operation("set", "list[" + "9" * 4301 + "]", "[1]"),
            Operation("insert", "list[" + "1" * 4301 + "]", "1"),
            Operation("set", "a.b[" + "1" * 4301 + "].c", "1"),
            Operation("set", "list[" + "9" * 20 + "]", "1"),
        ],
        ids=["set-a-literal", "set-a-list", "insert", "within", "twenty-digits"],
    )
    def test_an_index_longer_than_any_array_needs_is_not_a_pointer(self, operation):
        """``int()`` refuses a string of more than 4,300 digits with a plain ``ValueError``,
        which the pointer's own grammar met before anything could refuse it - reached through
        the check of whether a batch can be made at once as much as through the operation's
        own, and answered ``500``. No list holds more than ``sys.maxsize`` elements, so an index
        spelled with more digits than that number names nothing, and is refused as a pointer
        before it is read."""
        with pytest.raises(EditError) as refused:
            edited('{"a": 1, "list": [1, 2]}', operation)
        assert (refused.value.code, str(refused.value)) == (
            INVALID,
            f"{operation.pointer!r} is not a pointer",
        )

    def test_an_index_of_as_many_digits_as_an_array_can_need_is_still_read(self):
        """Nineteen digits, as many as ``sys.maxsize`` has on a 64-bit python: read as an index,
        which names nothing in this array."""
        index = "9" * len(str(sys.maxsize))
        with pytest.raises(EditError) as refused:
            edited('{"a": 1, "list": [1, 2]}', Operation("set", f"list[{index}]", "1"))
        assert (refused.value.code, str(refused.value)) == (
            INVALID,
            f"nothing is written at list[{index}]",
        )

    def test_an_operation_that_did_not_read_back_stops_the_ones_after_it(self):
        """Verified after every operation: the next one is checked against the text the last one
        left and made on the document that one was meant to leave, which have to be the same
        document - here the first rewrote the member spelled ``b.c``, and the second reached
        into the 3 it had meant to write and raised a ``TypeError``."""
        text = '{"a": {"b": {"c": {"k": 1}}, "b.c": 2}}'
        with pytest.raises(EditError) as refused:
            edited(text, Operation("set", "a.b.c", "3"), Operation("set", "a.b.c.k", "9"))
        assert refused.value.code == UNVERIFIED

    def test_a_removal_of_a_member_the_parsed_document_has_not_got_is_invalid(self):
        with pytest.raises(EditError) as refused:
            removal(Document('{"a.b": 1}'), "a.b")
        assert refused.value.code == INVALID

    def test_operations_apply_in_order_each_to_the_text_the_last_one_left(self):
        assert (
            edited(
                '{"list": [1, 2]}',
                Operation("insert", "list[0]", "0"),
                Operation("set", "list[2]", "5"),
            )
            == '{"list": [0, 1, 5]}'
        )

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


def change(path: Path, *operations: Operation) -> FileChange:
    return FileChange(path, fingerprint(path.read_bytes()), operations)


def saves_while_staging(
    monkeypatch: pytest.MonkeyPatch, staged_for: Path, saves: dict[Path, bytes | None]
) -> None:
    """Another editor saves ``saves`` - a file taken away, for ``None`` - at the seam of the
    write of ``staged_for``: once its stage is written and given its access, and before the file
    is looked at again to be renamed over.

    The second actor the engine's check right before a rename is for, with no thread and no
    sleep: the access a stage is given is the last thing done to it before then, so that the
    save lands there at every write of a file that is given one."""
    real = editing._keep_access

    def saving(original: Path, staged: Path) -> None:
        real(original, staged)
        if staged.name.startswith(staged_for.name + "."):
            for target, data in saves.items():
                if data is None:
                    target.unlink()
                else:
                    target.write_bytes(data)

    monkeypatch.setattr(editing, "_keep_access", saving)


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
        assert written == (
            Written(a, b'{"unit": "rpm"}', fingerprint(b'{"unit": "V"}')),
            Written(b, b'{"unit": "Hz"}', fingerprint(b'{"unit": "A"}')),
        )
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    def test_an_edited_file_keeps_its_permissions(self, tmp_path):
        """A file written afresh takes this process's umask rather than the file's own mode: a
        file kept group-writable came back without it after one edit."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        path.chmod(0o640)
        before = stat.S_IMODE(path.stat().st_mode)
        apply_changes([change(path, Operation("set", "a", "2"))])
        assert stat.S_IMODE(path.stat().st_mode) == before

    def test_an_edited_file_is_given_back_to_its_owner(self, tmp_path, monkeypatch):
        """An edit made as another user - root, in a container over a checkout mounted from the
        host - left the file to that user, and its owner could no longer save it."""
        given = []
        monkeypatch.setattr(
            editing.os, "chown", lambda _, uid, gid: given.append((uid, gid)), raising=False
        )
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        owner = path.stat()
        apply_changes([change(path, Operation("set", "a", "2"))])
        assert given == [(owner.st_uid, owner.st_gid)]

    def test_an_owner_this_process_may_not_give_it_to_leaves_the_file_written(
        self, tmp_path, monkeypatch
    ):
        def refuse(*_):
            raise PermissionError("only root gives a file away")

        monkeypatch.setattr(editing.os, "chown", refuse, raising=False)
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        apply_changes([change(path, Operation("set", "a", "2"))])
        assert path.read_bytes() == b'{"a": 2}'

    def test_a_system_without_owners_writes_the_file_all_the_same(self, tmp_path, monkeypatch):
        monkeypatch.delattr(editing.os, "chown", raising=False)
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        apply_changes([change(path, Operation("set", "a", "2"))])
        assert path.read_bytes() == b'{"a": 2}'

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

    def test_a_save_landing_during_an_edit_is_refused_not_overwritten(self, tmp_path, monkeypatch):
        """The fingerprint was checked once, before anything was written, so a file another
        editor saved while the edit ran - after that check, before the rename - was overwritten
        by it, and the edit answered written."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        pending = change(path, Operation("set", "x", "2"))
        real = editing._keep_access

        def someone_saves(original: Path, staged: Path) -> None:
            path.write_bytes(b'{"x": 9}')  # another editor saves after the check, before the rename
            real(original, staged)

        monkeypatch.setattr(editing, "_keep_access", someone_saves)
        with pytest.raises(EditError) as refused:
            apply_changes([pending])
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{path} changed on disk while it was being written; "
            "the files already written were put back"
        )
        assert path.read_bytes() == b'{"x": 9}', "the other editor's save was overwritten"
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_save_landing_while_a_later_file_is_written_puts_back_the_files_already_written(
        self, tmp_path, monkeypatch
    ):
        """The refusal is the whole edit's: the first file was renamed already, and goes back to
        what it held, while the file that was saved keeps the save."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        changes = [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        saves_while_staging(monkeypatch, b, {b: b'{"x": 9}'})
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{b} changed on disk while it was being written; "
            "the files already written were put back"
        )
        assert a.read_bytes() == b'{"x": 1}'
        assert b.read_bytes() == b'{"x": 9}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_file_saved_since_an_edit_wrote_it_is_not_put_back_over_the_save(
        self, tmp_path, monkeypatch
    ):
        """Putting a file back is a write like any other: one another editor saved after the
        edit renamed it, and before the refusal of a later file came to put it back, is not
        overwritten with the bytes it held before the edit - and the refusal names it, while
        the file after it is put back all the same. A file that was not put back makes the
        refusal ``unwritable``, whose sentence the page shows: ``stale`` is the one it answers
        with "nothing was written"."""
        a, b, c = (tmp_path / f"{name}.ddd.json" for name in "abc")
        for path in (a, b, c):
            path.write_bytes(b'{"x": 1}')
        changes = [change(path, Operation("set", "x", "2")) for path in (a, b, c)]
        saves_while_staging(monkeypatch, c, {a: b'{"x": 7}', c: b'{"x": 9}'})
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{c} changed on disk while it was being written; these could not be put back: {a}"
        )
        assert a.read_bytes() == b'{"x": 7}'
        assert b.read_bytes() == b'{"x": 1}'
        assert c.read_bytes() == b'{"x": 9}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name, c.name]

    def test_a_save_landing_is_answered_unwritable_when_a_file_written_cannot_be_put_back(
        self, tmp_path, monkeypatch
    ):
        """``stale`` tells a person nothing was written, which holds only when every file the
        edit wrote went back. Here the disk refuses the put-back of the first file after the
        second is found saved: the first still holds the edit's bytes, and the refusal that says
        so, and names it, is ``unwritable``."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        changes = [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        saves_while_staging(monkeypatch, b, {b: b'{"x": 9}'})
        monkeypatch.setattr(Path, "replace", _refusing_renames({a: 2}))
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} changed on disk while it was being written; these could not be put back: {a}"
        )
        assert a.read_bytes() == b'{"x": 2}'
        assert b.read_bytes() == b'{"x": 9}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_file_taken_away_during_an_edit_is_refused_as_stale(self, tmp_path, monkeypatch):
        """Deleted after the check and before the rename - by a branch switch, say: the rename
        would bring back a file somebody took away."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        pending = change(path, Operation("set", "x", "2"))
        saves_while_staging(monkeypatch, path, {path: None})
        with pytest.raises(EditError) as refused:
            apply_changes([pending])
        assert refused.value.code == STALE
        assert not path.exists()
        assert list(tmp_path.iterdir()) == []

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
        monkeypatch.setattr(Path, "replace", _refusing_renames({b: 1}))
        with pytest.raises(EditError) as refused:
            apply_changes(
                [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
            )
        assert refused.value.code == UNWRITABLE
        assert "put back" in str(refused.value)
        assert a.read_bytes() == b'{"x": 1}'

    def test_a_file_that_cannot_be_put_back_is_named(self, tmp_path, monkeypatch):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        monkeypatch.setattr(Path, "replace", _refusing_renames({b: 1, a: 2}))
        with pytest.raises(EditError) as refused:
            apply_changes(
                [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
            )
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

    def test_a_stage_ends_in_the_suffix_the_artefact_writer_stages_under(self):
        """A spelling and nothing more: what a stage a killed process left behind is known by,
        whichever writer it was."""
        assert STAGING_SUFFIX == ARTEFACT_STAGING_SUFFIX

    def test_what_an_edit_answers_is_true_of_the_file_when_another_writer_stages(
        self, tmp_path, monkeypatch
    ):
        """The engine staged every write under one name beside the file, so a second writer
        applying its own change to the same file at the same instant wrote its bytes into this
        edit's stage, and the rename put them in place under an answer that said this edit's - or
        took the stage away from under the rename, which on Windows left no file at all. The
        second writer here stages under that one name, between this edit's stage and its
        rename."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        pending = change(path, Operation("set", "x", "2"))
        real = editing._keep_access

        def another_writer_stages(original: Path, staged: Path) -> None:
            # A second writer, applying its own change to the same file at this instant, writes
            # its stage - under the one name the engine used to stage every write under.
            (path.parent / (path.name + STAGING_SUFFIX)).write_bytes(b'{"x": 3}')
            real(original, staged)

        monkeypatch.setattr(editing, "_keep_access", another_writer_stages)
        written = apply_changes([pending])
        meant = b'{"x": 2}'
        assert written[0].fingerprint == fingerprint(meant)
        assert fingerprint(path.read_bytes()) == written[0].fingerprint, (
            f"answered written {meant!r}, the file holds {path.read_bytes()!r}"
        )

    def test_each_write_stages_under_a_name_of_its_own(self, tmp_path, monkeypatch):
        """No two writes of one file share a stage, whether or not the one before left its own
        behind: the file's name, eight random hexadecimal digits and the suffix, beside the
        file."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        stages: list[Path] = []
        real = Path.replace

        def watching(self, target):
            stages.append(self)
            return real(self, target)

        monkeypatch.setattr(Path, "replace", watching)
        apply_changes([change(path, Operation("set", "x", "2"))])
        apply_changes([change(path, Operation("set", "x", "3"))])
        assert len(stages) == 2
        assert stages[0] != stages[1]
        shape = re.escape(path.name) + r"\.[0-9a-f]{8}" + re.escape(STAGING_SUFFIX)
        for stage in stages:
            assert stage.parent == tmp_path
            assert re.fullmatch(shape, stage.name), stage.name
            # As much longer than the file's name as the longest name a file is created under
            # leaves room for.
            assert len(stage.name) - len(path.name) == NAME_MAX - CREATED_NAME_MAX

    def test_a_stage_another_writer_holds_under_the_name_drawn_is_left_alone(
        self, tmp_path, monkeypatch
    ):
        """A name is taken only where nothing is: the stage of another writer, or one a killed
        process left, is neither written over nor taken away, and the name is drawn again."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        held = tmp_path / f"a.ddd.json.aaaaaaaa{STAGING_SUFFIX}"
        held.write_bytes(b"another writer's bytes")
        drawn = iter(["aaaaaaaa", "bbbbbbbb"])
        monkeypatch.setattr(
            editing, "secrets", types.SimpleNamespace(token_hex=lambda nbytes: next(drawn))
        )
        apply_changes([change(path, Operation("set", "x", "2"))])
        assert path.read_bytes() == b'{"x": 2}'
        assert held.read_bytes() == b"another writer's bytes"
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [path.name, held.name]

    def test_a_write_that_fails_takes_away_its_own_stage_and_no_other(self, tmp_path, monkeypatch):
        """The stage of the write that failed is the one file it deletes: another writer's - here
        under the name the engine used to stage every write under, in the middle of its own
        write - is still there, still holding its bytes."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b"{}")
        other = tmp_path / (path.name + STAGING_SUFFIX)
        other.write_bytes(b"another writer's bytes")

        def refuse(self, target):
            raise OSError("held open by an editor")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "1"))])
        assert refused.value.code == UNWRITABLE
        assert other.read_bytes() == b"another writer's bytes"
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [path.name, other.name]

    def test_a_write_that_dies_partway_leaves_no_stage_behind(self, tmp_path, monkeypatch):
        """A disk that fills up halfway through the stage's bytes: the half stage is taken
        away, and the file is as it was."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        real = editing._new_stage

        class FillingUp:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *exception):
                self.handle.close()

            def write(self, data):
                self.handle.write(data[: len(data) // 2])
                raise OSError(errno.ENOSPC, "No space left on device")

        def filling_up(target, *access):
            staging, handle = real(target, *access)
            return staging, FillingUp(handle)

        monkeypatch.setattr(editing, "_new_stage", filling_up)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert path.read_bytes() == b'{"x": 1}'
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_file_kept_readable_by_everyone_stays_so_under_a_strict_umask(self, tmp_path):
        """What a stage is created with is the umask's and the writer's alone, ``0600`` under a
        strict one: the edited file takes its own mode back before the rename."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        path.chmod(0o644)
        before = stat.S_IMODE(path.stat().st_mode)
        strict = os.umask(0o077)
        try:
            apply_changes([change(path, Operation("set", "a", "2"))])
        finally:
            os.umask(strict)
        assert stat.S_IMODE(path.stat().st_mode) == before

    def test_a_file_a_reader_holds_open_is_written_once_the_reader_lets_go(
        self, tmp_path, monkeypatch
    ):
        """Windows refuses to rename over a file another handle holds open - ``ddd gui``'s
        analysis reading it on a thread of its own - and the read lets go within milliseconds:
        the rename is tried again, rather than the edit refused."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        real = Path.replace
        tries = []

        def held_twice(self, target):
            tries.append(target)
            if len(tries) < 3:
                raise PermissionError(13, "Access is denied")
            return real(self, target)

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", held_twice)
        apply_changes([change(path, Operation("set", "x", "2"))])
        assert path.read_bytes() == b'{"x": 2}'
        assert tries == [path, path, path]

    def test_a_save_landing_while_the_rename_is_tried_again_is_refused_not_overwritten(
        self, tmp_path, monkeypatch
    ):
        """Windows refuses the rename while another handle holds the file, and it is tried again
        up to a second after the first try: a file another editor saves in between is looked at
        again before the next try, and not overwritten by it."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        pending = change(path, Operation("set", "x", "2"))
        tries = []

        def held_while_saved(self, target):
            tries.append(target)
            path.write_bytes(b'{"x": 9}')
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", held_while_saved)
        with pytest.raises(EditError) as refused:
            apply_changes([pending])
        assert refused.value.code == STALE
        assert tries == [path]
        assert path.read_bytes() == b'{"x": 9}'
        assert list(tmp_path.iterdir()) == [path]

    def test_a_file_held_open_past_every_try_is_refused(self, tmp_path, monkeypatch):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        tries = []

        def held(self, target):
            tries.append(target)
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", held)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert tries == [path, path, path]
        assert path.read_bytes() == b'{"x": 1}'
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    def test_a_refusal_is_final_where_one_try_is_all(self, tmp_path, monkeypatch):
        """Posix's own count: a rename there never waits on a reader, so it is not tried
        again."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        tries = []

        def held(self, target):
            tries.append(target)
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 1)
        monkeypatch.setattr(Path, "replace", held)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert tries == [path]

    def test_a_rename_failing_for_another_reason_is_refused_at_once(self, tmp_path, monkeypatch):
        """Only a refusal of access waits for a reader to let go: a full disk does not."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        tries = []

        def full(self, target):
            tries.append(target)
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", full)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert tries == [path]

    def test_a_created_file_held_open_is_taken_away_once_the_reader_lets_go(
        self, tmp_path, monkeypatch
    ):
        """Putting back a file an edit created takes it away, which windows refuses too while
        another handle holds it open."""
        path = tmp_path / "units.ddd.json"
        path.write_bytes(b"{}")
        real = Path.unlink
        tries = []

        def held_once(self, missing_ok=False):
            tries.append(self)
            if len(tries) < 2:
                raise PermissionError(13, "Access is denied")
            return real(self, missing_ok)

        monkeypatch.setattr(editing, "REPLACE_TRIES", 2)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "unlink", held_once)
        editing._put_back(path, None, b"{}")
        assert not path.exists()
        assert tries == [path, path]

    def test_a_save_landing_while_a_created_file_is_taken_away_again_is_kept(
        self, tmp_path, monkeypatch
    ):
        """The removal is tried again as the rename is, and the file looked at again before
        each try: one another editor saves between two of them is not deleted."""
        path = tmp_path / "units.ddd.json"
        written = apply_changes([created(path, UNITS_FILE)])
        tries = []

        def held_while_saved(self, missing_ok=False):
            tries.append(self)
            path.write_bytes(b'{"units": ["Nm"]}')
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "unlink", held_while_saved)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE
        assert tries == [path]
        assert path.read_bytes() == b'{"units": ["Nm"]}'

    def test_a_file_is_tried_fifty_times_a_fiftieth_of_a_second_apart_on_windows_alone(self):
        on_this_system = 50 if os.name == "nt" else 1
        assert on_this_system == editing.REPLACE_TRIES
        assert editing.REPLACE_PAUSE == 0.02

    def test_a_stage_that_took_a_read_only_mode_is_made_writable_before_it_is_taken_away(
        self, tmp_path, monkeypatch
    ):
        """A stage takes the access of the file it is like, and a read-only file's is read-only:
        Windows refuses to delete such a file, so that each refused write left its stage beside
        the file for good. Here the file the new one is like is read-only and not written by the
        edit - the stage is the one read-only file the engine ever has to take away - and the
        rename is refused: the stage is writable when it is deleted, and gone."""
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        like.chmod(0o444)
        path = tmp_path / "units.ddd.json"
        writable_when_deleted = []
        real = Path.unlink

        def refused(self, target):
            raise PermissionError(13, "Access is denied")

        def deleting(self, missing_ok=False):
            writable_when_deleted.append(bool(stat.S_IMODE(self.stat().st_mode) & stat.S_IWRITE))
            return real(self, missing_ok)

        monkeypatch.setattr(editing, "REPLACE_TRIES", 1)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", refused)
        monkeypatch.setattr(Path, "unlink", deleting)
        with pytest.raises(EditError) as refusal:
            apply_changes([created(path, UNITS_FILE, like)])
        assert refusal.value.code == UNWRITABLE
        assert writable_when_deleted == [True]
        assert [entry.name for entry in tmp_path.iterdir()] == [like.name]

    def test_a_stage_that_is_gone_already_does_not_hide_the_refusal_that_brought_the_write_there(
        self, tmp_path, monkeypatch
    ):
        """Whoever took the stage away - another process sweeping ``*.ddd-staging`` up - leaves
        nothing to make writable or to delete, and the sentence is still the one of the rename
        that was refused."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')

        def taken_away_and_refused(self, target):
            self.unlink()
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(editing, "REPLACE_TRIES", 1)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(Path, "replace", taken_away_and_refused)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{path} could not be written ([Errno 13] Access is denied); "
            "the files already written were put back"
        )
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    @pytest.mark.parametrize("kind", ["an edit", "a created file", "an undo"])
    def test_the_staged_bytes_are_synced_before_they_are_renamed_into_place(
        self, tmp_path, monkeypatch, kind
    ):
        """A rename can reach the disk ahead of the bytes it moves, so that a power cut leaves
        an empty file where there was a file: every write syncs its stage first, whatever
        it is - an edit's, a created file's, an undo's. The stage is closed before it is synced,
        so the size the descriptor has when it is synced is the whole of what was written."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2"))])
        events = []
        real_sync, real_rename = os.fsync, Path.replace

        def syncing(descriptor):
            events.append(("sync", os.fstat(descriptor).st_size))
            real_sync(descriptor)

        def renaming(self, target):
            events.append(("rename", self.read_bytes()))
            return real_rename(self, target)

        monkeypatch.setattr(editing.os, "fsync", syncing)
        monkeypatch.setattr(Path, "replace", renaming)
        if kind == "an edit":
            apply_changes([change(path, Operation("set", "x", "3"))])
            meant = b'{"x": 3}'
        elif kind == "a created file":
            apply_changes([created(tmp_path / "units.ddd.json", UNITS_FILE)])
            meant = UNITS_FILE.encode("utf-8")
        else:
            restore(written)
            meant = b'{"x": 1}'
        assert events == [("sync", len(meant)), ("rename", meant)]

    def test_a_stage_that_cannot_be_synced_is_refused_and_taken_away(self, tmp_path, monkeypatch):
        """A write the disk reports failed only when it is synced - a full disk, a failing one -
        is not one to rename over the file: the file keeps its bytes, and no stage is left."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')

        def failing(descriptor):
            raise OSError(errno.EIO, "Input/output error")

        monkeypatch.setattr(editing.os, "fsync", failing)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{path} could not be written ([Errno 5] Input/output error); "
            "the files already written were put back"
        )
        assert path.read_bytes() == b'{"x": 1}'
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_file_put_back_after_a_refusal_is_synced_before_it_is_renamed(
        self, tmp_path, monkeypatch
    ):
        """The put-back of a file an edit had renamed is the one write that is made one file at
        a time, and its stage is synced like any other: after the two stages of the edit and the
        rename of the first file, which the second's refusal sends back."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        events = []
        real_sync, real_rename = os.fsync, Path.replace

        def syncing(descriptor):
            events.append("sync")
            real_sync(descriptor)

        def renaming(self, target):
            events.append(f"rename {Path(target).name}")
            if Path(target) == b:
                raise OSError("disk full")
            return real_rename(self, target)

        monkeypatch.setattr(editing.os, "fsync", syncing)
        monkeypatch.setattr(Path, "replace", renaming)
        with pytest.raises(EditError):
            apply_changes(
                [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
            )
        assert events == [
            "sync",
            "sync",
            f"rename {a.name}",
            f"rename {b.name}",
            "sync",
            f"rename {a.name}",
        ]
        assert a.read_bytes() == b'{"x": 1}'

    @pytest.mark.parametrize("code", [errno.EINVAL, errno.ENOTSUP], ids=["einval", "enotsup"])
    def test_a_file_system_that_cannot_sync_is_written_all_the_same(
        self, tmp_path, monkeypatch, code
    ):
        """A network share, a virtual file system: some offer no sync, and answer it ``EINVAL``
        or ``ENOTSUP``. That is no failure of the write, which they have no better way to make:
        the file is written without. Any other error - ``EIO`` above - still refuses it."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')

        def unsupported(descriptor):
            raise OSError(code, os.strerror(code))

        monkeypatch.setattr(editing.os, "fsync", unsupported)
        apply_changes([change(path, Operation("set", "x", "2"))])
        assert path.read_bytes() == b'{"x": 2}'
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_stage_another_process_holds_is_synced_once_it_lets_go(self, tmp_path, monkeypatch):
        """The stage is closed and opened again to be synced, and Windows refuses to open a file
        for writing while another handle holds it without sharing the write - what a scanner
        does with a file just closed - and lets go within milliseconds: the open is tried again,
        as the rename is."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        real = os.open
        refusals = []

        def holding(file, flags, *mode):
            if not flags & os.O_CREAT and len(refusals) < 2:
                refusals.append((Path(file), flags))
                raise PermissionError(13, "Access is denied")
            return real(file, flags, *mode)

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(editing.os, "open", holding)
        apply_changes([change(path, Operation("set", "x", "2"))])
        assert path.read_bytes() == b'{"x": 2}'
        assert len(refusals) == 2
        assert all(file.name.endswith(STAGING_SUFFIX) for file, _ in refusals)
        # Opened for writing, which is what Windows asks of a handle that is to flush a file.
        assert all(flags & (os.O_WRONLY | os.O_RDWR) for _, flags in refusals)

    def test_a_stage_opened_again_to_be_synced_is_closed_again_whatever_the_sync_says(
        self, tmp_path, monkeypatch
    ):
        """A descriptor kept for each of the stages of an edit of hundreds of files is more
        than a process is given, and the sync that fails is the one that would leak it."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        lock = threading.Lock()
        real_open, real_close, real_sync = os.open, os.close, os.fsync
        opened = []
        closed = []

        def opening(file, flags, *mode):
            descriptor = real_open(file, flags, *mode)
            if not flags & os.O_CREAT:
                with lock:
                    opened.append(descriptor)
            return descriptor

        def closing(descriptor):
            with lock:
                closed.append(descriptor)
            real_close(descriptor)

        def failing(descriptor):
            raise OSError(errno.EIO, "Input/output error")

        monkeypatch.setattr(editing.os, "open", opening)
        monkeypatch.setattr(editing.os, "close", closing)
        apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        assert len(opened) == 2
        monkeypatch.setattr(editing.os, "fsync", failing)
        with pytest.raises(EditError):
            apply_changes([change(a, Operation("set", "x", "3"))])
        monkeypatch.setattr(editing.os, "fsync", real_sync)
        assert len(opened) == 3
        assert sorted(closed) == sorted(opened)

    def test_a_stage_held_past_every_try_is_refused_and_taken_away(self, tmp_path, monkeypatch):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        real = os.open
        tries = []

        def held(file, flags, *mode):
            if not flags & os.O_CREAT:
                tries.append(Path(file))
                raise PermissionError(13, "Access is denied")
            return real(file, flags, *mode)

        monkeypatch.setattr(editing, "REPLACE_TRIES", 3)
        monkeypatch.setattr(editing, "REPLACE_PAUSE", 0)
        monkeypatch.setattr(editing.os, "open", held)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{path} could not be written ([Errno 13] Access is denied); "
            "the files already written were put back"
        )
        assert len(tries) == 3
        assert path.read_bytes() == b'{"x": 1}'
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_name_that_stays_taken_is_given_up_on_after_a_few_draws(self, tmp_path, monkeypatch):
        """The name of a stage is drawn again where another stage holds it, which a file system
        that answers every name as taken would have kept doing for ever: the write is refused
        as one that could not be made - and the stage in the way is left alone."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        held = tmp_path / f"a.ddd.json.aaaaaaaa{STAGING_SUFFIX}"
        held.write_bytes(b"another writer's bytes")
        draws = []

        def always_the_same(nbytes):
            draws.append(nbytes)
            assert len(draws) <= 1000, "the name was drawn again and again, for ever"
            return "aaaaaaaa"

        monkeypatch.setattr(editing, "secrets", types.SimpleNamespace(token_hex=always_the_same))
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{path} could not be written ([Errno 17] every name drawn for its stage is taken: "
            f"{str(path)!r}); the files already written were put back"
        )
        assert len(draws) == editing.STAGE_TRIES == 16
        assert path.read_bytes() == b'{"x": 1}'
        assert held.read_bytes() == b"another writer's bytes"
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [path.name, held.name]

    def test_a_stage_is_private_to_its_owner_from_the_moment_it_exists(self, tmp_path, monkeypatch):
        """A stage was created with the umask's mode, ``0644`` under the usual one, and narrowed
        to the file's own only afterwards: the new bytes of a ``0600`` description were readable
        by every other user of the machine for as long as that took. A write that takes a
        file's access creates its stage for its owner alone, and the file ends as it was (Windows
        has no such mode: a file there is writable, and so its stage)."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        path.chmod(0o600)
        mode = stat.S_IMODE(path.stat().st_mode)
        real = editing._keep_access
        seen = []

        def watching(original: Path, staged: Path) -> None:
            seen.append(stat.S_IMODE(staged.stat().st_mode))
            real(original, staged)

        monkeypatch.setattr(editing, "_keep_access", watching)
        previous = os.umask(0o022)
        try:
            apply_changes([change(path, Operation("set", "x", "2"))])
        finally:
            os.umask(previous)
        assert seen == [mode]
        assert stat.S_IMODE(path.stat().st_mode) == mode


class TestAnEditStagesEveryFileBeforeItRenamesAny:
    """A sync waits for the disk, milliseconds a file on a file system that journals: an edit of
    hundreds of files - a unit renamed where hundreds state it - waited for it hundreds of
    times, each stage synced just before its own rename, while the session's lock was held. Every
    file is staged first and every stage synced, together, before the first is renamed; each
    file is then looked at once more and renamed, one after the other."""

    @staticmethod
    def files(tmp_path, names="abc"):
        paths = [tmp_path / f"{name}.ddd.json" for name in names]
        for path in paths:
            path.write_bytes(b'{"x": 1}')
        return paths, [change(path, Operation("set", "x", "2")) for path in paths]

    def test_every_stage_is_made_and_synced_before_any_file_is_renamed(self, tmp_path, monkeypatch):
        paths, changes = self.files(tmp_path)
        events = []
        renamed = []
        real_stage, real_sync, real_rename = editing._new_stage, os.fsync, Path.replace

        def staging(target, *access):
            events.append("stage")
            return real_stage(target, *access)

        def syncing(descriptor):
            events.append("sync")
            real_sync(descriptor)

        def renaming(self, target):
            events.append("rename")
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing, "_new_stage", staging)
        monkeypatch.setattr(editing.os, "fsync", syncing)
        monkeypatch.setattr(Path, "replace", renaming)
        apply_changes(changes)
        assert events == ["stage"] * 3 + ["sync"] * 3 + ["rename"] * 3
        assert renamed == paths
        assert [path.read_bytes() for path in paths] == [b'{"x": 2}'] * 3

    def test_the_stages_are_synced_at_once_and_not_one_after_the_other(self, tmp_path, monkeypatch):
        """Two syncs that each wait for the other to begin are both in flight at once, or the
        barrier breaks: a sync that waited for the one before it never meets the second."""
        _, changes = self.files(tmp_path, "ab")
        barrier = threading.Barrier(2, timeout=2)
        real = os.fsync

        def meeting(descriptor):
            barrier.wait()
            real(descriptor)

        monkeypatch.setattr(editing.os, "fsync", meeting)
        apply_changes(changes)
        assert [change.path.read_bytes() for change in changes] == [b'{"x": 2}'] * 2

    def test_no_more_stages_are_synced_at_once_than_the_edit_allows(self, tmp_path, monkeypatch):
        _, changes = self.files(tmp_path, "abcdef")
        monkeypatch.setattr(editing, "SYNC_WORKERS", 2)
        lock = threading.Lock()
        real = os.fsync
        active = 0
        peak = 0

        def slowly(descriptor):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            real(descriptor)
            with lock:
                active -= 1

        monkeypatch.setattr(editing.os, "fsync", slowly)
        apply_changes(changes)
        assert peak == 2

    def test_an_edit_syncs_sixty_four_stages_at_once_at_most(self):
        assert editing.SYNC_WORKERS == 64

    def test_a_sync_that_fails_for_a_later_file_refuses_the_edit_before_any_file_is_renamed(
        self, tmp_path, monkeypatch
    ):
        """The file renamed before the sync that failed had to be put back, which writes - and
        syncs - once more, on the disk that has just failed. Nothing is renamed: the sentence
        is the same, and no file has been touched."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"xx": 1}')
        renamed = []
        real_rename = Path.replace

        def failing(descriptor):
            # b's new bytes are one longer than a's, which is how this tells its stage.
            if os.fstat(descriptor).st_size == len(b'{"xx": 2}'):
                raise OSError(errno.EIO, "Input/output error")

        def renaming(self, target):
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing.os, "fsync", failing)
        monkeypatch.setattr(Path, "replace", renaming)
        with pytest.raises(EditError) as refused:
            apply_changes(
                [change(a, Operation("set", "x", "2")), change(b, Operation("set", "xx", "2"))]
            )
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} could not be written ([Errno 5] Input/output error); "
            "the files already written were put back"
        )
        assert renamed == []
        assert (a.read_bytes(), b.read_bytes()) == (b'{"x": 1}', b'{"xx": 1}')
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_stage_that_cannot_be_made_for_a_later_file_refuses_the_edit_before_any_rename(
        self, tmp_path, monkeypatch
    ):
        """The stage of the file before it is taken away, and nothing is renamed."""
        paths, changes = self.files(tmp_path, "ab")
        a, b = paths
        renamed = []
        real_stage, real_rename = editing._new_stage, Path.replace

        def staging(target, *access):
            if target == b:
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_stage(target, *access)

        def renaming(self, target):
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing, "_new_stage", staging)
        monkeypatch.setattr(Path, "replace", renaming)
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} could not be written ([Errno 28] No space left on device); "
            "the files already written were put back"
        )
        assert renamed == []
        assert [path.read_bytes() for path in paths] == [b'{"x": 1}'] * 2
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_rename_refused_takes_away_the_stages_of_the_files_not_renamed_and_no_other(
        self, tmp_path, monkeypatch
    ):
        """Every stage of the edit is beside its file when the second is refused: the file
        before it goes back, and the stage of the refused one and the one after it are taken
        away - the stage of the file renamed is not, there being none."""
        paths, changes = self.files(tmp_path)
        a, b, c = paths
        unlinked = []
        real = Path.unlink

        def unlinking(self, missing_ok=False):
            unlinked.append(self.name)
            return real(self, missing_ok)

        monkeypatch.setattr(Path, "replace", _refusing_renames({b: 1}))
        monkeypatch.setattr(Path, "unlink", unlinking)
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == UNWRITABLE
        assert [path.read_bytes() for path in paths] == [b'{"x": 1}'] * 3
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name, c.name]
        assert sorted(name.split(".")[0] for name in unlinked) == ["b", "c"]


def created(path: Path, raw: str, like: Path | None = None) -> FileChange:
    return FileChange(path, None, (Operation("set", "", raw),), like)


UNITS_FILE = '{\n  "units": [\n    { "unit": "rpm", "description": "" }\n  ]\n}\n'


class TestCreatingAFile:
    """A change without a fingerprint creates its file: the one a vocabulary's adoption writes."""

    def test_a_created_file_holds_its_one_set_exactly_as_given(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        written = apply_changes([created(path, UNITS_FILE)])
        assert path.read_bytes() == UNITS_FILE.encode("utf-8")
        assert written == (Written(path, None, fingerprint(UNITS_FILE.encode("utf-8"))),)
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    @pytest.mark.parametrize(
        "operations",
        [
            (),
            (Operation("set", "", "{}"), Operation("set", "units", "[]")),
            (Operation("insert", "", "{}"),),
            (Operation("set", "units", '["rpm"]'),),
            (Operation("set", ""),),
        ],
    )
    def test_a_file_is_created_only_whole_by_one_set_at_its_top(self, tmp_path, operations):
        path = tmp_path / "units.ddd.json"
        with pytest.raises(EditError) as refused:
            apply_changes([FileChange(path, None, operations)])
        assert refused.value.code == INVALID
        assert str(refused.value).startswith(str(path))
        assert not path.exists()

    @pytest.mark.parametrize("raw", ["{", '{"units": NaN}', '{"units": [], "units": []}'])
    def test_a_file_is_never_created_holding_what_the_loader_does_not_read(self, tmp_path, raw):
        path = tmp_path / "units.ddd.json"
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, raw)])
        assert refused.value.code == INVALID
        assert not path.exists()

    def test_a_file_is_never_created_under_a_name_too_long_to_stage(self, tmp_path):
        """235 bytes, 256 once staged: past the 255 a file system takes. ``ddd gui`` refuses the
        name before this is asked (``ddd.gui.session``); this is the engine's own rule, for any
        other caller."""
        path = tmp_path / ("n" * 226 + ".ddd.json")
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == INVALID
        assert str(refused.value) == (
            f"{path} cannot be created: its name is 235 bytes long, and a name is at most 234 - "
            "the file is staged under the name, a dot, 8 hexadecimal digits of its own and "
            "'.ddd-staging' first, and ext4 takes a name of at most 255 bytes, NTFS one of at "
            "most 255 UTF-16 units, which 255 bytes never exceed"
        )
        assert list(tmp_path.iterdir()) == []

    def test_a_file_is_created_under_the_longest_name_its_stage_leaves_room_for(self, tmp_path):
        """234 bytes, 255 once staged: the most a file system takes, so that the stage - a name
        of its own, 21 bytes longer than the file's - is created, and renamed away."""
        path = tmp_path / ("n" * 225 + ".ddd.json")
        assert len(path.name.encode("utf-8")) == 234
        apply_changes([created(path, UNITS_FILE)])
        assert path.read_bytes() == UNITS_FILE.encode("utf-8")
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_file_is_never_created_under_a_name_windows_keeps_for_a_device(self, tmp_path):
        """On every system: Windows reads ``com1.ddd.json`` as its first serial port."""
        path = tmp_path / "com1.ddd.json"
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == INVALID
        assert str(refused.value) == (
            f"{path} cannot be created: Windows reads its name as the device COM1, which it would "
            "open instead of a file"
        )
        assert list(tmp_path.iterdir()) == []

    def test_a_file_that_exists_by_the_time_of_the_edit_is_stale(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        path.write_bytes(b'{"units": ["Nm"]}')
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == STALE
        assert path.read_bytes() == b'{"units": ["Nm"]}'

    def test_a_file_that_comes_to_exist_during_the_edit_is_refused_not_overwritten(
        self, tmp_path, monkeypatch
    ):
        """Nothing is there when the change is made, and a rename onto the name would replace
        what is by the time it happens: another editor creating the same file in between -
        after the check that it does not exist, before the rename - loses it."""
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        path = tmp_path / "units.ddd.json"
        saves_while_staging(monkeypatch, path, {path: b'{"units": ["Nm"]}'})
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE, like)])
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{path} changed on disk while it was being written; "
            "the files already written were put back"
        )
        assert path.read_bytes() == b'{"units": ["Nm"]}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [like.name, path.name]

    def test_a_file_created_like_no_file_is_checked_before_its_rename_too(
        self, tmp_path, monkeypatch
    ):
        """A file created like no file is given no access to copy, so the seam of the tests above
        is never reached: the other editor's file lands as soon as the stage is written."""
        path = tmp_path / "units.ddd.json"
        real = editing._new_stage

        class SavedOnceWritten:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *exception):
                self.handle.close()
                path.write_bytes(b'{"units": ["Nm"]}')

            def write(self, data):
                self.handle.write(data)

        def saving_once_written(target, *access):
            staging, handle = real(target, *access)
            return staging, SavedOnceWritten(handle)

        monkeypatch.setattr(editing, "_new_stage", saving_once_written)
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == STALE
        assert path.read_bytes() == b'{"units": ["Nm"]}'
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_created_file_is_taken_away_when_a_later_file_is_saved_during_the_edit(
        self, tmp_path, monkeypatch
    ):
        """An adoption writes the vocabulary's file and then the project that includes it: a
        save of the project in between refuses the edit, and the file it created goes."""
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        changes = [
            created(units, UNITS_FILE, project),
            change(project, Operation("set", "project.includes", '["units.ddd.json"]')),
        ]
        saves_while_staging(monkeypatch, project, {project: b'{"project": {"includes": ["x"]}}'})
        with pytest.raises(EditError) as refused:
            apply_changes(changes)
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{project} changed on disk while it was being written; "
            "the files already written were put back"
        )
        assert not units.exists()
        assert project.read_bytes() == b'{"project": {"includes": ["x"]}}'
        assert [entry.name for entry in tmp_path.iterdir()] == [project.name]

    def test_a_created_file_is_taken_away_when_a_later_file_fails(self, tmp_path, monkeypatch):
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        monkeypatch.setattr(Path, "replace", _refusing_renames({project: 1}))
        with pytest.raises(EditError) as refused:
            apply_changes(
                [
                    created(units, UNITS_FILE),
                    change(project, Operation("insert", "project.includes[0]", '"units.ddd.json"')),
                ]
            )
        assert refused.value.code == UNWRITABLE
        assert "put back" in str(refused.value)
        assert not units.exists()
        assert project.read_bytes() == b'{"project": {"includes": []}}'

    def test_a_created_file_takes_the_mode_of_the_file_it_is_like(self, tmp_path):
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        like.chmod(0o640)
        mode = stat.S_IMODE(like.stat().st_mode)
        path = tmp_path / "units.ddd.json"
        apply_changes([created(path, UNITS_FILE, like)])
        assert stat.S_IMODE(path.stat().st_mode) == mode

    def test_a_created_file_is_given_to_the_owner_of_the_file_it_is_like(
        self, tmp_path, monkeypatch
    ):
        """What ``ddd gui`` run as root in its container needs: the units file an adoption
        writes into a checkout mounted from the host belongs to whoever owns the project."""
        given = []
        monkeypatch.setattr(
            editing.os, "chown", lambda _, uid, gid: given.append((uid, gid)), raising=False
        )
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        owner = like.stat()
        apply_changes([created(tmp_path / "units.ddd.json", UNITS_FILE, like)])
        assert given == [(owner.st_uid, owner.st_gid)]

    def test_a_file_created_like_no_file_keeps_the_access_a_new_file_gets(
        self, tmp_path, monkeypatch
    ):
        given = []
        monkeypatch.setattr(editing.os, "chown", lambda *args: given.append(args), raising=False)
        path = tmp_path / "units.ddd.json"
        apply_changes([created(path, UNITS_FILE)])
        assert path.read_bytes() == UNITS_FILE.encode("utf-8")
        assert given == []

    def test_a_file_created_like_no_file_gets_the_mode_any_new_file_gets(self, tmp_path):
        """The umask's, as a file written the ordinary way has it - not the ``0600`` a stage
        created for its owner alone would carry over."""
        path = tmp_path / "units.ddd.json"
        ordinary = tmp_path / "ordinary"
        previous = os.umask(0o027)
        try:
            ordinary.write_bytes(b"{}")
            apply_changes([created(path, UNITS_FILE)])
        finally:
            os.umask(previous)
        assert stat.S_IMODE(path.stat().st_mode) == stat.S_IMODE(ordinary.stat().st_mode)

    def test_a_file_that_exists_keeps_its_own_mode_whatever_it_is_said_to_be_like(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        path.chmod(0o600)
        mode = stat.S_IMODE(path.stat().st_mode)
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        like.chmod(0o644)
        pending = FileChange(
            path, fingerprint(b'{"a": 1}'), (Operation("set", "a", "2"),), like=like
        )
        apply_changes([pending])
        assert stat.S_IMODE(path.stat().st_mode) == mode


class TestAFileThisProcessMayNotWrite:
    """A read-only file is refused, whatever the system and before anything is staged.

    Windows renamed the stage, which took the file's read-only flag, only to be refused after a
    second of tries, and left that stage beside the file; Linux renamed over the file, since a
    rename asks the directory's permission and not the file's, wrote it through and kept it
    read-only. A checkout somebody kept read-only has no protection but the tool's refusal."""

    def test_a_read_only_file_is_refused_with_its_bytes_and_mode_untouched_and_no_stage_left(
        self, tmp_path
    ):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        path.chmod(0o444)
        mode = stat.S_IMODE(path.stat().st_mode)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == f"{path} is read-only, so nothing was written"
        assert path.read_bytes() == b'{"x": 1}'
        assert stat.S_IMODE(path.stat().st_mode) == mode
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_the_next_edit_is_made_once_the_file_is_writable(self, tmp_path):
        """Windows left the stage of the refused edit beside the file, read-only like it, and
        the edits after it were refused until somebody deleted that: nothing is left, so that
        once the file is writable again the next edit of it is made."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        path.chmod(0o444)
        with pytest.raises(EditError):
            apply_changes([change(path, Operation("set", "x", "2"))])
        path.chmod(0o644)
        written = apply_changes([change(path, Operation("set", "x", "3"))])
        assert path.read_bytes() == b'{"x": 3}'
        assert written == (Written(path, b'{"x": 1}', fingerprint(b'{"x": 3}')),)
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_read_only_file_among_several_refuses_the_whole_edit_before_any_is_staged(
        self, tmp_path, monkeypatch
    ):
        """No file of the edit is written, or staged to be written, so that nothing has to be
        put back - and the sentence does not say it was."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        b.chmod(0o444)
        staged = []
        real = editing._new_stage

        def watching(target, *access):
            staged.append(target)
            return real(target, *access)

        monkeypatch.setattr(editing, "_new_stage", watching)
        with pytest.raises(EditError) as refused:
            apply_changes(
                [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
            )
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == f"{b} is read-only, so nothing was written"
        assert staged == []
        assert a.read_bytes() == b'{"x": 1}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_an_undo_is_refused_before_any_file_is_put_back_when_one_is_read_only_since(
        self, tmp_path
    ):
        """The undo is made of the same writes: a file somebody has since kept read-only is
        refused with the others untouched, and is put back once it is writable again."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        b.chmod(0o444)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == f"{b} is read-only, so nothing was put back"
        assert a.read_bytes() == b'{"x": 2}'
        assert b.read_bytes() == b'{"x": 2}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]
        b.chmod(0o644)
        restore(written)
        assert (a.read_bytes(), b.read_bytes()) == (b'{"x": 1}', b'{"x": 1}')

    def test_a_file_nobody_may_write_is_refused_to_a_process_that_may_write_anything(
        self, tmp_path, monkeypatch
    ):
        """``root`` - ``ddd gui`` in a container, over a checkout mounted from the host - is
        asked by no permission, and a file kept read-only is the protection the checkout was
        given: refused to it too."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        path.chmod(0o444)
        monkeypatch.setattr(editing.os, "access", lambda *asked, **how: True)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert str(refused.value) == f"{path} is read-only, so nothing was written"
        assert path.read_bytes() == b'{"x": 1}'

    @pytest.mark.parametrize("mode", [0o464, 0o446], ids=["its-group-only", "everyone-else-only"])
    def test_a_file_one_class_of_users_may_write_is_not_read_only_to_a_process_that_may_write_all(
        self, tmp_path, monkeypatch, mode
    ):
        """No permission to write at all is what makes a file read-only to ``root``: one the
        owner may not write but the group, or everyone else, may is a file somebody may write,
        and the system - which is what is asked of a process that may not - is the one to say
        that this one may not."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        path.chmod(mode)
        monkeypatch.setattr(editing.os, "access", lambda *asked, **how: True)
        edit = [change(path, Operation("set", "x", "2"))]
        if os.name == "nt":
            # Windows keeps one read-only flag, which chmod sets whenever the owner may not
            # write: there is no group, and no one else, to ask.
            with pytest.raises(EditError) as refused:
                apply_changes(edit)
            assert refused.value.code == UNWRITABLE
        else:
            apply_changes(edit)
            assert path.read_bytes() == b'{"x": 2}'

    def test_a_file_the_system_says_this_process_may_not_write_is_refused_whatever_its_mode(
        self, tmp_path, monkeypatch
    ):
        """A file of another user's that says ``0644``, or one on a read-only mount: its mode
        allows a write, and the system does not."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        monkeypatch.setattr(editing.os, "access", lambda *asked, **how: False)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert str(refused.value) == f"{path} is read-only, so nothing was written"
        assert path.read_bytes() == b'{"x": 1}'

    def test_a_file_taken_away_after_it_was_read_is_stale_rather_than_read_only(
        self, tmp_path, monkeypatch
    ):
        """Nothing is left to ask about, and the edit was computed from a file that is not
        there now."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        real = editing.edited

        def taking_it_away(pending):
            computed = real(pending)
            pending.path.unlink()
            return computed

        monkeypatch.setattr(editing, "edited", taking_it_away)
        with pytest.raises(EditError) as refused:
            apply_changes([change(path, Operation("set", "x", "2"))])
        assert refused.value.code == STALE
        assert str(refused.value) == f"{path} can no longer be read"


class TestPuttingAnEditBack:
    """What ``ddd gui``'s undo is made of: the bytes an edit replaced, written back."""

    def test_a_file_is_put_back_exactly_as_it_was(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{\n  "unit": "rpm"\n}\n')
        written = apply_changes([change(path, Operation("set", "unit", '"V"'))])
        restore(written)
        assert path.read_bytes() == b'{\n  "unit": "rpm"\n}\n'
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    def test_a_created_file_is_taken_away_again(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        written = apply_changes([created(path, UNITS_FILE)])
        assert written == (Written(path, None, fingerprint(UNITS_FILE.encode("utf-8"))),)
        restore(written)
        assert not path.exists()

    def test_a_file_that_changed_since_is_refused_before_anything_is_written(self, tmp_path):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        b.write_bytes(b'{"x": 3}')
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE
        assert str(b) in str(refused.value)
        # The first file was not touched: every file is checked before any is written.
        assert a.read_bytes() == b'{"x": 2}'

    def test_a_file_that_can_no_longer_be_read_is_refused(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2"))])
        path.unlink()
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE

    def test_unchanged_answers_the_bytes_the_edit_left(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2"))])
        assert unchanged(written[0]) == b'{"x": 2}'

    def test_a_save_landing_during_an_undo_is_refused_not_overwritten(self, tmp_path, monkeypatch):
        """Every file is checked before anything is written, which is not the moment of the
        rename: a file another editor saved after that check and before its rename was
        overwritten with the bytes from before the edit, and the undo answered done."""
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2"))])
        saves_while_staging(monkeypatch, path, {path: b'{"x": 9}'})
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{path} changed on disk while it was being written; "
            "the files already put back were written forward again"
        )
        assert path.read_bytes() == b'{"x": 9}', "the other editor's save was overwritten"
        assert [entry.name for entry in tmp_path.iterdir()] == [path.name]

    def test_a_save_landing_while_a_later_file_is_put_back_writes_the_earlier_ones_forward(
        self, tmp_path, monkeypatch
    ):
        """The first file is back as it was when the second is found saved, so it is written
        forward to what the edit left, and the undo stays one that can be asked again."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        saves_while_staging(monkeypatch, b, {b: b'{"x": 9}'})
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{b} changed on disk while it was being written; "
            "the files already put back were written forward again"
        )
        assert a.read_bytes() == b'{"x": 2}'
        assert b.read_bytes() == b'{"x": 9}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_file_saved_since_it_was_put_back_is_not_written_forward_over_the_save(
        self, tmp_path, monkeypatch
    ):
        """The first file was put back and saved after, when the third is found saved: the
        refusal names it and leaves it, while the second is written forward all the same. A
        file that was not written forward leaves the undo half made, so the refusal is
        ``unwritable``, whose sentence the page shows, and not ``stale``."""
        a, b, c = (tmp_path / f"{name}.ddd.json" for name in "abc")
        for path in (a, b, c):
            path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2")) for path in (a, b, c)])
        saves_while_staging(monkeypatch, c, {a: b'{"x": 7}', c: b'{"x": 9}'})
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{c} changed on disk while it was being written; "
            f"these could not be written forward again: {a}"
        )
        assert a.read_bytes() == b'{"x": 7}'
        assert b.read_bytes() == b'{"x": 2}'
        assert c.read_bytes() == b'{"x": 9}'

    def test_a_save_landing_is_answered_unwritable_when_a_file_put_back_cannot_be_written_forward(
        self, tmp_path, monkeypatch
    ):
        """``stale`` tells a person nothing was put back, which holds only when every file the
        undo had put back went forward again. Here the disk refuses that for the first file after
        the second is found saved: the first is left as it was before the edit, half the undo, and
        the refusal that says so, and names it, is ``unwritable``."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        saves_while_staging(monkeypatch, b, {b: b'{"x": 9}'})
        monkeypatch.setattr(Path, "replace", _refusing_renames({a: 2}))
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} changed on disk while it was being written; "
            f"these could not be written forward again: {a}"
        )
        assert a.read_bytes() == b'{"x": 1}'
        assert b.read_bytes() == b'{"x": 9}'
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_save_landing_on_a_created_file_during_an_undo_keeps_it(self, tmp_path, monkeypatch):
        """A file the edit created is taken away with no stage to wait on, so the save lands
        right after the checks: it is kept, and the project it was included from is left as the
        edit wrote it."""
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        written = apply_changes(
            [
                created(units, UNITS_FILE, project),
                change(project, Operation("set", "project.includes", '["units.ddd.json"]')),
            ]
        )
        real = editing.unchanged

        def saved_after_the_last_check(entry: Written) -> bytes:
            current = real(entry)
            if entry.path == project:
                units.write_bytes(b'{"units": ["Nm"]}')
            return current

        monkeypatch.setattr(editing, "unchanged", saved_after_the_last_check)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == STALE
        assert str(refused.value) == (
            f"{units} changed on disk while it was being written; "
            "the files already put back were written forward again"
        )
        assert units.read_bytes() == b'{"units": ["Nm"]}'
        assert project.read_bytes() == b'{"project": {"includes": ["units.ddd.json"]}}'

    def test_the_files_already_put_back_are_written_forward_when_one_cannot_be(
        self, tmp_path, monkeypatch
    ):
        """The rollback of an undo, and the case that needs it most: an adoption's created file
        is taken away first, so it has to be put there again when the second file refuses."""
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        written = apply_changes(
            [
                created(units, UNITS_FILE, project),
                change(project, Operation("set", "project.includes", '["units.ddd.json"]')),
            ]
        )
        monkeypatch.setattr(Path, "replace", _refusing_renames({project: 1}))
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert "written forward again" in str(refused.value)
        assert units.read_bytes() == UNITS_FILE.encode("utf-8")

    def test_a_file_that_cannot_be_written_forward_is_named(self, tmp_path, monkeypatch):
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"x": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "x", "2"))]
        )
        # b refuses at once; a's own put-back is let by, and its write forward refuses.
        monkeypatch.setattr(Path, "replace", _refusing_renames({b: 1, a: 2}))
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert f"these could not be written forward again: {a}" in str(refused.value)

    def test_a_restored_file_keeps_its_permissions(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        path.chmod(0o640)
        mode = stat.S_IMODE(path.stat().st_mode)
        restore(apply_changes([change(path, Operation("set", "a", "2"))]))
        assert stat.S_IMODE(path.stat().st_mode) == mode


class TestAnUndoStagesEveryFileBeforeItPutsAnyBack:
    """An undo is waited on as an edit is, and wrote the files of a rename across hundreds of
    them one after the other, each stage synced just before its own rename, with the session's
    lock held: it takes as long to put an edit back as it took to make it, and more. Its stages are
    made first and synced together, as an edit's are, and only then is each file put back, one
    after the other, looked at once more right before."""

    @staticmethod
    def edited_files(tmp_path, names="abc"):
        paths = [tmp_path / f"{name}.ddd.json" for name in names]
        for path in paths:
            path.write_bytes(b'{"x": 1}')
        written = apply_changes([change(path, Operation("set", "x", "2")) for path in paths])
        return paths, written

    def test_every_stage_is_made_and_synced_before_any_file_is_put_back(
        self, tmp_path, monkeypatch
    ):
        paths, written = self.edited_files(tmp_path)
        events = []
        renamed = []
        real_stage, real_sync, real_rename = editing._new_stage, os.fsync, Path.replace

        def staging(target, *access):
            events.append("stage")
            return real_stage(target, *access)

        def syncing(descriptor):
            events.append("sync")
            real_sync(descriptor)

        def renaming(self, target):
            events.append("rename")
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing, "_new_stage", staging)
        monkeypatch.setattr(editing.os, "fsync", syncing)
        monkeypatch.setattr(Path, "replace", renaming)
        restore(written)
        assert events == ["stage"] * 3 + ["sync"] * 3 + ["rename"] * 3
        assert renamed == paths
        assert [path.read_bytes() for path in paths] == [b'{"x": 1}'] * 3

    def test_the_stages_are_synced_at_once_and_not_one_after_the_other(self, tmp_path, monkeypatch):
        """Two syncs that each wait for the other to begin are both in flight at once, or the
        barrier breaks."""
        paths, written = self.edited_files(tmp_path, "ab")
        barrier = threading.Barrier(2, timeout=2)
        real = os.fsync

        def meeting(descriptor):
            barrier.wait()
            real(descriptor)

        monkeypatch.setattr(editing.os, "fsync", meeting)
        restore(written)
        assert [path.read_bytes() for path in paths] == [b'{"x": 1}'] * 2

    def test_a_created_file_is_taken_away_once_every_stage_is_synced(self, tmp_path, monkeypatch):
        """An adoption's undo takes the units file away, which has no stage and nothing to sync,
        and writes the project back: the file is taken away where it comes in the undo, after the
        sync of the project's stage."""
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        written = apply_changes(
            [
                created(units, UNITS_FILE, project),
                change(project, Operation("set", "project.includes", '["units.ddd.json"]')),
            ]
        )
        events = []
        real_stage, real_sync = editing._new_stage, os.fsync
        real_rename, real_unlink = Path.replace, Path.unlink

        def staging(target, *access):
            events.append(f"stage {target.name}")
            return real_stage(target, *access)

        def syncing(descriptor):
            events.append("sync")
            real_sync(descriptor)

        def renaming(self, target):
            events.append(f"rename {Path(target).name}")
            return real_rename(self, target)

        def unlinking(self, missing_ok=False):
            events.append(f"unlink {self.name}")
            return real_unlink(self, missing_ok)

        monkeypatch.setattr(editing, "_new_stage", staging)
        monkeypatch.setattr(editing.os, "fsync", syncing)
        monkeypatch.setattr(Path, "replace", renaming)
        monkeypatch.setattr(Path, "unlink", unlinking)
        restore(written)
        assert events == [
            f"stage {project.name}",
            "sync",
            f"unlink {units.name}",
            f"rename {project.name}",
        ]
        assert not units.exists()
        assert project.read_bytes() == b'{"project": {"includes": []}}'

    def test_a_sync_that_fails_for_a_later_file_refuses_the_undo_before_any_file_is_put_back(
        self, tmp_path, monkeypatch
    ):
        """The file put back before the sync that failed had to be written forward again, on the
        disk that has just failed. Nothing is put back, and the sentence is the one it was."""
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        a.write_bytes(b'{"x": 1}')
        b.write_bytes(b'{"xx": 1}')
        written = apply_changes(
            [change(a, Operation("set", "x", "2")), change(b, Operation("set", "xx", "2"))]
        )
        renamed = []
        real_rename = Path.replace

        def failing(descriptor):
            # b's previous bytes are one longer than a's, which is how this tells its stage.
            if os.fstat(descriptor).st_size == len(b'{"xx": 1}'):
                raise OSError(errno.EIO, "Input/output error")

        def renaming(self, target):
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing.os, "fsync", failing)
        monkeypatch.setattr(Path, "replace", renaming)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} could not be put back; the files already put back were written forward again"
        )
        assert renamed == []
        assert (a.read_bytes(), b.read_bytes()) == (b'{"x": 2}', b'{"xx": 2}')
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_a_sync_that_fails_in_an_undo_that_takes_a_file_away_names_the_file_it_failed_for(
        self, tmp_path, monkeypatch
    ):
        """The file the edit created has no stage, so the stage that fails is the second file's
        and the first stage's: the refusal names the project, and the units file is not yet
        taken away - nothing is, before every stage is synced."""
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        written = apply_changes(
            [
                created(units, UNITS_FILE, project),
                change(project, Operation("set", "project.includes", '["units.ddd.json"]')),
            ]
        )
        unlinked = []
        real_unlink = Path.unlink

        def failing(descriptor):
            raise OSError(errno.EIO, "Input/output error")

        def unlinking(self, missing_ok=False):
            unlinked.append(self.name)
            return real_unlink(self, missing_ok)

        monkeypatch.setattr(editing.os, "fsync", failing)
        monkeypatch.setattr(Path, "unlink", unlinking)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{project} could not be put back; "
            "the files already put back were written forward again"
        )
        assert units.read_bytes() == UNITS_FILE.encode("utf-8")
        assert project.read_bytes() == b'{"project": {"includes": ["units.ddd.json"]}}'
        assert [name for name in unlinked if not name.endswith(STAGING_SUFFIX)] == []
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [project.name, units.name]

    def test_a_stage_that_cannot_be_made_for_a_later_file_refuses_the_undo_before_any_rename(
        self, tmp_path, monkeypatch
    ):
        paths, written = self.edited_files(tmp_path, "ab")
        a, b = paths
        renamed = []
        real_stage, real_rename = editing._new_stage, Path.replace

        def staging(target, *access):
            if target == b:
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_stage(target, *access)

        def renaming(self, target):
            renamed.append(Path(target))
            return real_rename(self, target)

        monkeypatch.setattr(editing, "_new_stage", staging)
        monkeypatch.setattr(Path, "replace", renaming)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} could not be put back; the files already put back were written forward again"
        )
        assert renamed == []
        assert [path.read_bytes() for path in paths] == [b'{"x": 2}'] * 2
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name]

    def test_an_undo_refused_takes_away_the_stages_of_the_files_not_put_back_and_no_other(
        self, tmp_path, monkeypatch
    ):
        """The file put back goes forward again, and the stage of the refused one and the one
        after it are taken away - the stage of the file put back is not, there being none."""
        paths, written = self.edited_files(tmp_path)
        a, b, c = paths
        unlinked = []
        real = Path.unlink

        def unlinking(self, missing_ok=False):
            unlinked.append(self.name)
            return real(self, missing_ok)

        monkeypatch.setattr(Path, "replace", _refusing_renames({b: 1}))
        monkeypatch.setattr(Path, "unlink", unlinking)
        with pytest.raises(EditError) as refused:
            restore(written)
        assert refused.value.code == UNWRITABLE
        assert str(refused.value) == (
            f"{b} could not be put back; the files already put back were written forward again"
        )
        assert [path.read_bytes() for path in paths] == [b'{"x": 2}'] * 3
        assert sorted(entry.name for entry in tmp_path.iterdir()) == [a.name, b.name, c.name]
        assert sorted(name.split(".")[0] for name in unlinked) == ["b", "c"]


def _refusing_renames(after: dict[Path, int]):
    """``Path.replace`` that refuses a target once it has been asked for it that many times: 1
    refuses the first rename onto it outright, 2 lets the first by and refuses the second, which
    is the put-back of a file an edit renamed, or the write forward of one an undo had put back.
    A refusal that is no refusal of access, as a full disk is none, is final at once."""
    real = Path.replace
    seen: dict[Path, int] = {}

    def renaming(self, target):
        target = Path(target)
        seen[target] = seen.get(target, 0) + 1
        if seen[target] >= after.get(target, seen[target] + 1):
            raise OSError("disk full")
        return real(self, target)

    return renaming
