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
