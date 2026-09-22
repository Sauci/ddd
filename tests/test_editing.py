"""The edit engine: every change a description file is given, in the file's own layout."""

from __future__ import annotations

import codecs
import stat
from pathlib import Path

import pytest

import ddd.editing as editing
from ddd.backends.base import STAGING_SUFFIX as ARTEFACT_STAGING_SUFFIX
from ddd.editing import (
    INVALID,
    STAGING_SUFFIX,
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

        def failing(path, data, like):
            if path == b:
                raise OSError("disk full")
            real(path, data, like)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
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
        real = editing._stage_and_replace
        calls = []

        def failing(path, data, like):
            calls.append(path)
            if path == b or calls.count(a) > 1:
                raise OSError("disk full")
            real(path, data, like)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
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

    def test_edits_stage_under_the_name_every_other_writer_stages_under(self):
        assert STAGING_SUFFIX == ARTEFACT_STAGING_SUFFIX


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

    def test_a_file_that_exists_by_the_time_of_the_edit_is_stale(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        path.write_bytes(b'{"units": ["Nm"]}')
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == STALE
        assert path.read_bytes() == b'{"units": ["Nm"]}'

    def test_a_created_file_is_taken_away_when_a_later_file_fails(self, tmp_path, monkeypatch):
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        real = editing._stage_and_replace

        def failing(path, data, like):
            if path == project:
                raise OSError("disk full")
            real(path, data, like)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
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
        real = editing._stage_and_replace

        def failing(path, data, like):
            if path == project:
                raise OSError("disk full")
            real(path, data, like)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
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
        monkeypatch.setattr(editing, "_stage_and_replace", _refusing({b: 1, a: 2}))
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


def _refusing(after: dict[Path, int]):
    """``_stage_and_replace`` that refuses a path once it has been asked for it that many
    times: 1 refuses it outright, 2 lets the first write by and refuses the second."""
    real = editing._stage_and_replace
    seen: dict[Path, int] = {}

    def staged(path, data, like):
        seen[path] = seen.get(path, 0) + 1
        if seen[path] >= after.get(path, seen[path] + 1):
            raise OSError("disk full")
        real(path, data, like)

    return staged
