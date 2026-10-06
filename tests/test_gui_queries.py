"""The types a query's values are read as, and every query model's refusals."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, ClassVar, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, model_validator

import ddd.gui.queries as queries_module
from ddd.gui.api import Api, Reply, _query_message
from ddd.gui.queries import (
    MAX_DEPTH,
    MAX_DIGITS,
    MAX_NAME,
    MAX_PATH,
    CompareQuery,
    FindingsQuery,
    FixQuery,
    NoQuery,
    Serving,
    SettleQuery,
    StateQuery,
    _Query,
    actions_of,
    file_path,
    json_text,
    named,
    refusal,
    whole,
)
from ddd.gui.routes import Route
from ddd.gui.session import Session

SAID = "this route takes ?it= as a whole number from 0"


class Whole(BaseModel):
    it: Annotated[int, whole(SAID)]


@pytest.mark.parametrize("text", ["0", "7", "007", "9" * MAX_DIGITS])
def test_a_whole_number_is_its_ascii_digits(text) -> None:
    assert Whole.model_validate({"it": text}).it == int(text)


@pytest.mark.parametrize(
    "text", ["", "-1", "+1", "1.5", "1_000", " 1", "\u0663", "1" * (MAX_DIGITS + 1), "1" * 4301]
)
def test_anything_else_is_refused_with_the_routes_own_sentence(text) -> None:
    with pytest.raises(ValidationError) as refused:
        Whole.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == SAID


class FromOne(BaseModel):
    it: Annotated[int, whole(SAID, least=1)]


def test_a_whole_number_below_its_least_is_refused_and_its_least_is_not() -> None:
    assert FromOne.model_validate({"it": "1"}).it == 1
    with pytest.raises(ValidationError) as refused:
        FromOne.model_validate({"it": "0"})
    assert refused.value.errors()[0]["msg"] == SAID


def test_a_value_that_is_not_text_is_refused_by_every_type() -> None:
    """Only an in-process caller can hand a model anything but text: a query arrives as text."""
    for model in (Whole, Pathed, Named, Json):
        with pytest.raises(ValidationError) as refused:
            model.model_validate({"it": 7})
        assert refused.value.errors()[0]["msg"] == SAID


class Pathed(BaseModel):
    it: Annotated[str, file_path(SAID)]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "/a/b\x00.ddd.json",
        "/a/b\ud800.ddd.json",
        "a/b.ddd.json",
        "b.ddd.json",
        "C:b.ddd.json",
        "\\a\\b.ddd.json",
        "\\\\server\\share\\a",
        "//server/share/a",
        "/\\server\\share\\a",
        "\\\\?\\C:\\a",
        "\\\\.\\pipe\\a",
        "/" + "a" * MAX_PATH,
    ],
    ids=[
        "empty",
        "a NUL inside",
        "a lone surrogate inside",
        "relative",
        "a bare name",
        "a drive with no root",
        "rooted without a drive",
        "a network share",
        "a network share spelt with slashes",
        "a network share spelt with both",
        "a device path",
        "a device namespace",
        "one character too long",
    ],
)
def test_a_path_is_refused_with_the_routes_own_sentence(text) -> None:
    """Each spelt as a string, never through ``Path``, whose reading changes with the platform:
    each is refused on every platform."""
    with pytest.raises(ValidationError) as refused:
        Pathed.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == SAID


@pytest.mark.parametrize(
    "text",
    ["/a/b.ddd.json", "C:/a/b.ddd.json", "c:\\a\\b.ddd.json", "/" + "a" * (MAX_PATH - 1)],
    ids=["posix", "windows, slashes", "windows, backslashes", "as long as a path may be"],
)
def test_an_absolute_path_is_answered_as_given(text) -> None:
    """Both spellings on every platform: the page names a file as the server answered it,
    ``C:/...`` on Windows and ``/...`` elsewhere."""
    assert Pathed.model_validate({"it": text}).it == text


SERVED = Serving(root="//server/share/p", served=("//server/share/p",))
"""What ``ddd gui`` started in a mapped network drive serves on Windows, whose ``Path.resolve``
names the drive's directory by its network path: the paths it answers, and the page sends back,
are spelt so too."""


@pytest.mark.parametrize(
    "text",
    [
        "//server/share/p/a.ddd.json",
        "\\\\server\\share\\p\\a.ddd.json",
        "//server/share/p\\sub/a.ddd.json",
        "//server/share/p",
    ],
    ids=["slashes", "backslashes", "both", "the directory itself"],
)
def test_a_network_path_under_a_directory_served_is_a_path_like_any_other(text) -> None:
    assert Pathed.model_validate({"it": text}, context=SERVED).it == text


@pytest.mark.parametrize(
    "text",
    [
        "//server/share/a.ddd.json",
        "//server/share/project/a.ddd.json",
        "//other/share/p/a.ddd.json",
        "\\\\?\\UNC\\server\\share\\p\\a.ddd.json",
        "\\\\.\\pipe\\p",
    ],
    ids=[
        "above it",
        "beside it, its name begun alike",
        "on another server",
        "the device form of a path under it",
        "a device",
    ],
)
def test_a_network_path_outside_every_directory_served_is_refused(text) -> None:
    with pytest.raises(ValidationError) as refused:
        Pathed.model_validate({"it": text}, context=SERVED)
    assert refused.value.errors()[0]["msg"] == SAID


@pytest.mark.parametrize("context", [None, SERVED, Serving(root="/srv/p", served=("/srv/p",))])
def test_an_ordinary_path_is_read_alike_whatever_is_served(context) -> None:
    for text in ("/a/b.ddd.json", "C:/a/b.ddd.json"):
        assert Pathed.model_validate({"it": text}, context=context).it == text


@pytest.mark.parametrize(("caseless", "accepted"), [(True, True), (False, False)])
def test_a_network_path_is_compared_in_one_case_where_the_platform_compares_so(
    monkeypatch, caseless, accepted
) -> None:
    """Windows compares a path without its case, and no other platform does: both readings,
    on every platform."""
    monkeypatch.setattr(queries_module, "_CASELESS", caseless)
    asked = {"it": "//SERVER/Share/P/a.ddd.json"}
    if accepted:
        assert Pathed.model_validate(asked, context=SERVED).it == asked["it"]
    else:
        with pytest.raises(ValidationError) as refused:
            Pathed.model_validate(asked, context=SERVED)
        assert refused.value.errors()[0]["msg"] == SAID


def test_case_is_folded_on_windows_alone() -> None:
    assert queries_module._CASELESS is (sys.platform == "win32")


class Named(BaseModel):
    it: Annotated[str, named(SAID)]


@pytest.mark.parametrize(
    "text", ["", "Value\x00A", "x" * (MAX_NAME + 1)], ids=["empty", "a NUL inside", "too long"]
)
def test_a_name_is_refused_with_the_routes_own_sentence(text) -> None:
    with pytest.raises(ValidationError) as refused:
        Named.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == SAID


@pytest.mark.parametrize("text", ["ValueA", "°C", ".calib$1", "x" * MAX_NAME])
def test_a_name_is_answered_as_given(text) -> None:
    assert Named.model_validate({"it": text}).it == text


class Json(BaseModel):
    it: Annotated[str, json_text(SAID)]


def nested(depth: int) -> str:
    return "[" * depth + "]" * depth


@pytest.mark.parametrize(
    "text",
    ["1.0", '"rpm"', '{"min": 0, "max": 1e3}', "null", nested(MAX_DEPTH), '"' + "[" * 100 + '"'],
    ids=[
        "a number",
        "a string",
        "an object",
        "null",
        "nested as deep as json may be",
        "brackets inside a string",
    ],
)
def test_json_text_is_answered_as_it_was_typed(text) -> None:
    """Never parsed into a value and written back: ``1.0`` stays the three characters it was
    typed as, which is what an edit writes into a file."""
    assert Json.model_validate({"it": text}).it == text


@pytest.mark.parametrize(
    "text",
    [
        "1e999",
        "-1e999",
        "[1, 2e400]",
        "NaN",
        "Infinity",
        nested(MAX_DEPTH + 1),
        "1" * 4301,
        "not json",
        "",
        '{"a": 1, "a": 2}',
    ],
    ids=[
        "too large a number",
        "too large a negative number",
        "too large a number inside",
        "NaN",
        "Infinity",
        "nested one level too deep",
        "4301 digits",
        "not json",
        "empty",
        "a key twice",
    ],
)
def test_anything_else_is_refused_as_json_with_the_routes_own_sentence(text) -> None:
    with pytest.raises(ValidationError) as refused:
        Json.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == SAID


def test_three_thousand_levels_are_refused_before_anything_parses_them(monkeypatch) -> None:
    """Counted over the text, so no parser ever recurses into it: the edit engine's own reader
    is what ran out of stack on a settle three thousand levels deep."""
    parsed: list[object] = []
    monkeypatch.setattr(queries_module, "parse_raw", parsed.append)
    with pytest.raises(ValidationError) as refused:
        Json.model_validate({"it": nested(3000)})
    assert refused.value.errors()[0]["msg"] == SAID
    assert parsed == []


@pytest.mark.parametrize(
    "text",
    [
        '"\\"' + "[" * 100 + '"',
        '["\\\\", ' + nested(MAX_DEPTH - 1) + "]",
        '{"a\\"b": ' + nested(MAX_DEPTH - 1) + "}",
    ],
    ids=["an escaped quote", "an escaped backslash", "an escaped quote in a key"],
)
def test_a_string_s_escapes_end_where_its_quote_does(text) -> None:
    """Brackets inside a string are not nesting, and a quote after a backslash does not end
    the string: each of these is at most ``MAX_DEPTH`` deep."""
    assert Json.model_validate({"it": text}).it == text


def test_a_backslash_escaped_before_a_quote_lets_the_quote_end_the_string() -> None:
    """``"\\\\"`` is one backslash and then the end of the string: the brackets after it nest."""
    with pytest.raises(ValidationError) as refused:
        Json.model_validate({"it": '["\\\\", ' + nested(MAX_DEPTH) + "]"})
    assert refused.value.errors()[0]["msg"] == SAID


class Raw(BaseModel):
    it: Annotated[str, json_text()]


@pytest.mark.parametrize(
    ("text", "sentence"),
    [
        (
            "not json",
            "'not json' is not one json value: Expecting value: line 1 column 1 (char 0)",
        ),
        (
            "NaN",
            "'NaN' is not one json value: 'NaN' is not valid json; DDD has no representation "
            "for it",
        ),
        (
            '{"a": 1, "a": 2}',
            "'{\"a\": 1, \"a\": 2}' is not one json value: key 'a' appears twice in one object; "
            "json would silently keep the last spelling, so decide which one stays",
        ),
        (
            "1e999",
            "'1e999' is not one json value: '1e999' is not a finite number; DDD has no "
            "representation for it",
        ),
        (
            "[0.5, -2e308]",
            "'[0.5, -2e308]' is not one json value: '-2e308' is not a finite number; DDD has no "
            "representation for it",
        ),
        (
            nested(MAX_DEPTH + 1),
            f"{nested(MAX_DEPTH + 1)!r} is not one json value: the json is nested too deeply to "
            "read",
        ),
    ],
    ids=[
        "not json",
        "NaN",
        "a key twice, its braces said as written",
        "too large a number",
        "too large a number inside",
        "too deep",
    ],
)
def test_without_a_sentence_json_is_refused_in_parse_raws_own_words(text, sentence) -> None:
    """What settle has always answered for a value it cannot write: ``parse_raw``'s sentence,
    and the same words for a value too deep or too large, which it never refused before. A
    sentence is said as written, braces and all: it is never read as a template."""
    with pytest.raises(ValidationError) as refused:
        Raw.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == sentence


def test_a_sentence_echoing_a_lone_surrogate_says_it_as_its_escape() -> None:
    """A refusal echoes what was typed, and pydantic cannot carry a lone surrogate in a message:
    the sentence keeps every character it can say, and says that one as its escape."""
    with pytest.raises(ValidationError) as refused:
        Raw.model_validate({"it": '{"\ud800": 1, "\ud800": 2}'})
    assert refused.value.errors()[0]["msg"] == (
        "'{\"\\ud800\": 1, \"\\ud800\": 2}' is not one json value: key '\\ud800' appears twice in "
        "one object; json would silently keep the last spelling, so decide which one stays"
    )


def test_too_deep_is_said_before_anything_else_is_wrong_with_the_text() -> None:
    """Counted first: text both too deep and malformed further on is refused for its depth."""
    text = "[" * (MAX_DEPTH + 1) + "x"
    with pytest.raises(ValidationError) as refused:
        Raw.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == (
        f"{text!r} is not one json value: the json is nested too deeply to read"
    )


def test_the_limits() -> None:
    assert (MAX_DIGITS, MAX_PATH, MAX_NAME, MAX_DEPTH) == (9, 4096, 1024, 64)


class Blanks(BaseModel):
    file: Annotated[str, file_path(SAID, blank="")]
    raw: Annotated[str | None, json_text(blank=None)]


def test_a_blank_is_what_the_route_says_it_is_where_the_route_lets_it_through() -> None:
    blank = Blanks.model_validate({"file": "", "raw": ""})
    assert (blank.file, blank.raw) == ("", None)
    given = Blanks.model_validate({"file": "/a.ddd.json", "raw": "1"})
    assert (given.file, given.raw) == ("/a.ddd.json", "1")


class Strictly(_Query):
    """A query of two plain-typed keys, as a model of a later route may have."""

    count: int = 0
    flag: bool = False


class TestTheModels:
    """What each model answers its handler: a value read as its type, a blank as the route
    has always read it, and a key left out as its default."""

    def test_a_query_is_closed_frozen_and_strict(self) -> None:
        assert _Query.model_config["extra"] == "forbid"
        assert _Query.model_config["frozen"] is True
        assert _Query.model_config["strict"] is True
        query = FindingsQuery.model_validate({})
        with pytest.raises(ValidationError):
            query.offset = 1

    @pytest.mark.parametrize(
        "given",
        [{"count": "1_000"}, {"count": " 7 "}, {"count": "1.0"}, {"flag": "yes"}, {"flag": "on"}],
    )
    def test_a_value_is_never_coerced_into_a_type_it_is_not(self, given) -> None:
        """Strict, as a body's models are: a key a model reads as a plain type takes that type
        alone, never text pydantic would otherwise make one of."""
        with pytest.raises(ValidationError) as refused:
            Strictly.model_validate(given)
        assert refused.value.errors()[0]["type"] in ("int_type", "bool_type")

    def test_a_route_with_no_query_takes_no_key(self) -> None:
        assert NoQuery.model_fields == {}
        assert NoQuery.missing == ""

    @pytest.mark.parametrize(
        ("given", "after"),
        [
            ({}, None),
            ({"after": "0"}, 0),
            ({"after": "007"}, 7),
            ({"after": "9" * MAX_DIGITS}, int("9" * MAX_DIGITS)),
            ({"after": ""}, None),
            ({"after": "-1"}, None),
            ({"after": "one"}, None),
            ({"after": "\u0663"}, None),
            ({"after": "1" * (MAX_DIGITS + 1)}, None),
            ({"after": "1" * 4301}, None),
        ],
    )
    def test_the_state_waits_past_a_whole_number_and_answers_anything_else_at_once(
        self, given, after
    ) -> None:
        assert StateQuery.model_validate(given).after == after

    def test_a_page_of_findings_is_every_finding_from_the_first_unless_asked_otherwise(
        self,
    ) -> None:
        query = FindingsQuery.model_validate({})
        assert (query.offset, query.limit, query.severity, query.file, query.check) == (
            0,
            None,
            None,
            None,
            None,
        )
        asked = FindingsQuery.model_validate(
            {"offset": "100", "limit": "50", "severity": "info", "file": "/a.ddd.json"}
        )
        assert (asked.offset, asked.limit, asked.severity, asked.file) == (
            100,
            50,
            "info",
            "/a.ddd.json",
        )

    def test_a_blank_file_or_check_filters_findings_to_none(self) -> None:
        """What a blank has always meant here: a filter, by a file or a check nothing has."""
        query = FindingsQuery.model_validate({"file": "", "check": ""})
        assert (query.file, query.check) == ("", "")

    def test_a_blank_raw_takes_the_key_away_as_leaving_it_out_does(self) -> None:
        for given in (
            {"name": "ValueA", "key": "unit"},
            {"name": "ValueA", "key": "unit", "raw": ""},
        ):
            assert SettleQuery.model_validate(given).raw is None

    def test_a_blank_pointer_fixes_the_whole_file(self) -> None:
        query = FixQuery.model_validate({"file": "/a.ddd.json", "pointer": "", "check": "x"})
        assert query.pointer == ""

    def test_a_baseline_is_named_as_the_reader_typed_it(self) -> None:
        """Relative to the directory ddd gui serves, or absolute: compare.py reads it, and
        refuses in its own words what it cannot read."""
        for baseline in ("baseline.json", "/srv/p/baseline.json", "base\x00line.json"):
            assert CompareQuery.model_validate({"baseline": baseline}).baseline == baseline


NAMED = [
    ("variable", "a variable's"),
    ("unit", "a unit's"),
    ("type", "a type's"),
    ("constant", "a constant's"),
    ("section", "a section's"),
    ("raster", "a raster's"),
    ("values", "an object's"),
]

SETTLE = "settle takes ?name= and ?key=, and ?raw= unless the key goes"
FIX = "fix takes ?file=, ?pointer= and ?check="
DEEP = "[" * 3000 + "]" * 3000

REFUSED = [
    ("/api/state", {"x": "1"}, "state takes no ?x="),
    ("/api/findings", {"offset": "1" * 4301}, "findings takes ?offset= as a whole number from 0"),
    ("/api/findings", {"offset": "1" * 10}, "findings takes ?offset= as a whole number from 0"),
    ("/api/findings", {"limit": "1" * 4301}, "findings takes ?limit= as a whole number from 1"),
    (
        "/api/findings",
        {"severity": "ignore"},
        "findings takes ?severity= as error, warning or info",
    ),
    ("/api/findings", {"file": "\x00"}, "findings takes ?file= as a file's path"),
    ("/api/findings", {"file": "a.ddd.json"}, "findings takes ?file= as a file's path"),
    (
        "/api/findings",
        {"file": "//server/share/a.ddd.json"},
        "findings takes ?file= as a file's path",
    ),
    ("/api/findings", {"check": "missing\x00id"}, "findings takes ?check= as a check's name"),
    ("/api/findings", {"check": "x" * (MAX_NAME + 1)}, "findings takes ?check= as a check's name"),
    ("/api/findings", {"limit": "1", "page": "2"}, "findings takes no ?page="),
    ("/api/file", {}, "file takes ?path="),
    ("/api/file", {"path": ""}, "file takes ?path="),
    ("/api/file", {"path": "/p/a\x00.ddd.json"}, "file takes ?path= as a file's path"),
    ("/api/file", {"path": "\\\\server\\share\\a.ddd.json"}, "file takes ?path= as a file's path"),
    ("/api/file", {"path": "a.ddd.json"}, "file takes ?path= as a file's path"),
    *[(f"/api/{route}", {}, f"{route} takes ?name=") for route, _ in NAMED],
    *[(f"/api/{route}", {"name": ""}, f"{route} takes ?name=") for route, _ in NAMED],
    *[
        (f"/api/{route}", {"name": "Value\x00A"}, f"{route} takes ?name= as {what} name")
        for route, what in NAMED
    ],
    *[
        (f"/api/{route}", {"name": "x" * (MAX_NAME + 1)}, f"{route} takes ?name= as {what} name")
        for route, what in NAMED
    ],
    ("/api/settle", {}, SETTLE),
    ("/api/settle", {"name": "ValueA"}, SETTLE),
    ("/api/settle", {"key": "unit"}, SETTLE),
    ("/api/settle", {"name": "", "key": "unit"}, SETTLE),
    ("/api/settle", {"name": "ValueA", "key": ""}, SETTLE),
    (
        "/api/settle",
        {"name": "ValueA", "key": "description"},
        "'description' is not a key the declarations of a variable share",
    ),
    (
        "/api/settle",
        {"name": "ValueA", "key": "unit", "raw": "not json"},
        "'not json' is not one json value: Expecting value: line 1 column 1 (char 0)",
    ),
    (
        "/api/settle",
        {"name": "ValueA", "key": "unit", "raw": DEEP},
        f"{DEEP!r} is not one json value: the json is nested too deeply to read",
    ),
    (
        "/api/settle",
        {"name": "ValueA", "key": "unit", "raw": "1e999"},
        "'1e999' is not one json value: '1e999' is not a finite number; DDD has no "
        "representation for it",
    ),
    (
        "/api/settle",
        {"name": "Value\x00A", "key": "unit"},
        "settle takes ?name= as a variable's name",
    ),
    (
        "/api/settle",
        {"name": "ValueA", "key": "\ud800"},
        "'\\ud800' is not a key the declarations of a variable share",
    ),
    ("/api/fix", {}, FIX),
    ("/api/fix", {"file": "/p/a.ddd.json"}, FIX),
    ("/api/fix", {"file": "/p/a.ddd.json", "pointer": ""}, FIX),
    ("/api/fix", {"file": "", "pointer": "", "check": "missing-id"}, FIX),
    ("/api/fix", {"file": "/p/a.ddd.json", "pointer": "", "check": ""}, FIX),
    (
        "/api/fix",
        {"file": "/p/a\x00.ddd.json", "pointer": "", "check": "missing-id"},
        "fix takes ?file= as a file's path",
    ),
    (
        "/api/fix",
        {"file": "/p/a.ddd.json", "pointer": "component\x00", "check": "missing-id"},
        "fix takes ?pointer= as a place in the file",
    ),
    (
        "/api/fix",
        {"file": "/p/a.ddd.json", "pointer": "", "check": "x" * (MAX_NAME + 1)},
        "fix takes ?check= as a check's name",
    ),
    ("/api/declarable", {}, "declarable takes ?file="),
    ("/api/declarable", {"file": ""}, "declarable takes ?file="),
    ("/api/declarable", {"file": "/p/\x00"}, "declarable takes ?file= as a file's path"),
    ("/api/compare", {}, "compare takes ?baseline="),
    ("/api/compare", {"baseline": ""}, "compare takes ?baseline="),
    ("/api/compare", {"baseline": "base\ud800.json"}, "compare takes ?baseline= as a file's path"),
    *[
        (f"/api/{route}", {"x": "1"}, f"{route} takes no ?x=")
        for route in (
            "session",
            "projects",
            "dictionary",
            "graph",
            "checks",
            "units",
            "types",
            "shared",
            "files",
            "undo",
        )
    ],
]


@pytest.mark.parametrize(
    ("route", "query", "sentence"),
    REFUSED,
    ids=[
        f"{route.removeprefix('/api/')}-{'&'.join(query) or 'nothing'}-{at}"
        for at, (route, query, _) in enumerate(REFUSED)
    ],
)
def test_every_route_refuses_what_it_cannot_read_in_its_own_words_before_any_project(
    tmp_path: Path, route: str, query: dict[str, str], sentence: str
) -> None:
    """Asked with no project open: the query is read first, on every route, so the answer is
    the query's refusal rather than the 409 of a missing project."""
    api = Api(Session(tmp_path))
    reply = api.handle("GET", route, {key: [value] for key, value in query.items()}, None)
    assert reply == Reply(400, {"error": "bad-request", "message": sentence})


@pytest.mark.parametrize(
    ("route", "body"),
    [
        ("/api/open", b'{"path": "/p/p.ddd.json"}'),
        ("/api/edit", b"{}"),
        ("/api/undo", b'{"at": 1}'),
    ],
)
def test_a_route_that_takes_a_body_takes_no_query(tmp_path: Path, route: str, body: bytes) -> None:
    reply = Api(Session(tmp_path)).handle("POST", route, {"x": ["1"]}, body)
    named = route.rsplit("/", 1)[1]
    assert reply == Reply(400, {"error": "bad-request", "message": f"{named} takes no ?x="})


class Rename(_Query):
    missing: ClassVar[str] = "rename takes ?unit= and ?to="
    action: Literal["rename"]
    unit: Annotated[str, named("rename takes ?unit= as a unit's name")]
    to: str


class Add(_Query):
    missing: ClassVar[str] = "add takes ?unit="
    action: Literal["add"]
    unit: Annotated[str, named("add takes ?unit= as a unit's name")]


class Planned(RootModel[Annotated[Rename | Add, Field(discriminator="action")]]):
    """A query of one model per action, shaped as the plan routes' are to be: a RootModel over
    a union discriminated by ``action``, which refuses an action it does not take before the
    union is read."""

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _taken(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("action") in ("rename", "add"):
            return value
        raise refusal("toy-plan takes ?action= one of rename, add")


class TestAQueryOfOneModelPerAction:
    """Where a refusal of a query read as one model per action is placed: under the action
    given, whose model says what it requires and whose name says what it does not take."""

    def test_the_model_of_each_action_is_found_by_its_action(self) -> None:
        assert actions_of(Planned) == {"rename": Rename, "add": Add}
        assert actions_of(FindingsQuery) == {}

    @pytest.mark.parametrize(
        ("query", "sentence"),
        [
            ({}, "toy-plan takes ?action= one of rename, add"),
            ({"action": "move"}, "toy-plan takes ?action= one of rename, add"),
            ({"action": "rename", "unit": "rpm"}, "rename takes ?unit= and ?to="),
            ({"action": "rename", "unit": "", "to": "Hz"}, "rename takes ?unit= and ?to="),
            (
                {"action": "rename", "unit": "r\x00m", "to": "Hz"},
                "rename takes ?unit= as a unit's name",
            ),
            ({"action": "add"}, "add takes ?unit="),
            ({"action": "add", "unit": "rpm", "to": "Hz"}, "add takes no ?to="),
        ],
    )
    def test_each_problem_is_said_in_the_words_of_the_action_it_is_under(
        self, query: dict[str, str], sentence: str
    ) -> None:
        route = Route("/api/toy-plan", "GET", Planned, None, lambda *_: None)
        with pytest.raises(ValidationError) as refused:
            Planned.model_validate(query)
        assert _query_message(route, refused.value) == sentence
