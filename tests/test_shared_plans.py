"""What changing one of a project's constants takes, planned and never written."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from conftest import built_of, component, declare, project, write_tree
from ddd.editing import Operation
from ddd.loading import included_files
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document
from ddd.shared_plans import (
    CONSTANTS_FILE,
    SharedPlan,
    SharedRefusalError,
    _raw,
    remove_constant,
    set_constant,
    shared_project,
)

CONSTANTS = {"constants": [{"name": "TREND_SAMPLES", "value": 16, "description": "slots"}]}


class TestWhichFilesAnEntryNames:
    def test_an_entry_that_is_not_a_string_names_nothing(self, tmp_path: Path) -> None:
        assert included_files(tmp_path / "p.ddd.json", 3) == []

    def test_a_pattern_the_loader_cannot_expand_names_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forced rather than found: a NUL byte in a literal entry never reaches this function's
        own `except` at all, since :func:`~ddd.loading.resolve_path` swallows exactly that
        exception one frame further in and hands back an unresolved path instead - so the one
        arm this test can still reach is the pattern branch's, forced the way
        `test_unit_plans.py`'s own `test_an_entry_the_loader_cannot_expand_names_no_units_file`
        forces the same thing for the same reason."""

        def refuse(self: Path, pattern: str) -> object:
            raise NotImplementedError("Non-relative patterns are unsupported")

        monkeypatch.setattr(Path, "glob", refuse)
        assert included_files(tmp_path / "p.ddd.json", "*.ddd.json") == []

    def test_an_entry_names_the_file_beside_the_project(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": CONSTANTS})
        assert included_files(tmp_path / "p.ddd.json", "c.ddd.json") == [
            (tmp_path / "c.ddd.json").resolve()
        ]


class TestTheProjectAPlanIsMadeIn:
    def test_the_constants_files_come_in_the_order_includes_lists_them(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "second.ddd.json", "first.ddd.json", "a.ddd.json"),
                "second.ddd.json": CONSTANTS,
                "first.ddd.json": {"constants": [{"name": "CELLS", "value": 8}]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.constants_files] == [
            "second.ddd.json",
            "first.ddd.json",
        ]
        assert found.project == (tmp_path / "p.ddd.json").resolve()

    def test_a_file_that_does_not_parse_is_no_constants_file(self, tmp_path: Path) -> None:
        """What a file is cannot be told from one nobody could read, so it is not counted - and a
        new constant must not be appended to it."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": "{"})
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()

    def test_a_project_naming_no_constants_file_has_none(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()

    def test_one_file_named_twice_is_listed_once(self, tmp_path: Path) -> None:
        """A pattern and a literal entry can name the same file; the first is where a new constant
        goes, and a list holding it twice would say there are two places."""
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "c.ddd.json", "*.ddd.json"), "c.ddd.json": CONSTANTS},
        )
        cache: dict[Path, Document] = {}
        assert len(shared_project(tmp_path / "p.ddd.json", (), cache).constants_files) == 1

    def test_the_files_that_did_not_load_are_resolved_and_sorted(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        cache: dict[Path, Document] = {}
        unread = [tmp_path / "z.ddd.json", tmp_path / "a.ddd.json", tmp_path / "z.ddd.json"]
        found = shared_project(tmp_path / "p.ddd.json", unread, cache)
        assert [file.name for file in found.unread] == ["a.ddd.json", "z.ddd.json"]

    def test_an_includes_that_is_not_a_list_names_nothing(self, tmp_path: Path) -> None:
        """A project whose `includes` is a number is refused by the loader; read here it has to
        answer no files rather than iterate a number."""
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 3}}})
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()


def test_the_file_a_project_without_one_gets_is_named_for_what_it_holds() -> None:
    assert CONSTANTS_FILE == "constants.ddd.json"


def test_a_refusal_carries_its_code_and_its_sentence() -> None:
    with pytest.raises(SharedRefusalError) as raised:
        raise SharedRefusalError("invalid", "'X' is already declared")
    assert (raised.value.code, raised.value.message) == ("invalid", "'X' is already declared")


def _index(tmp_path: Path, files: Mapping[str, Any]) -> Index:
    """The index `conftest.built_of` makes of this tree, discarding the root: unlike
    `tests/test_project_shared.py`, nothing below reads a file back off disk, only the index."""
    return built_of(tmp_path, **files)[0]


# `p.ddd.json` is deliberately absent from every tree below: `conftest.built_of` writes it
# itself, from the other files it is handed, so a tree naming its own would fight the helper
# over the one file that matters least to the test reading it. This is the same shape
# `tests/test_project_shared.py` builds its own `TWO_HOMES` in - copied by hand rather than
# imported, since this repo does not import one test module's fixtures from another.
TWO_HOMES = {
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 2.0}],
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
}

# A second tree, only for the one test that needs a constant two shapes name rather than one:
# `_plural`'s conditional expression inside an f-string registers no branch with coverage.py, so
# nothing forces both wordings to be exercised - a test naming each count directly is what does.
_TWO_USES = {
    "c.ddd.json": {"constants": [{"name": "TREND_SAMPLES", "value": 16}]},
    "a.ddd.json": {
        "component": {
            "name": "A",
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
    "b.ddd.json": {
        "component": {
            "name": "B",
            "interface": [
                {
                    "scope": "input",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
}


class TestSettingAKey:
    def test_a_value_is_set_as_the_text_it_was_given(self, tmp_path: Path) -> None:
        """`2.0` stays fractional: the operation carries the three characters, not a parsed 2."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "value", "2.0", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("c.ddd.json", (Operation("set", "constants[0].value", "2.0"),))
        ]

    def test_a_description_is_set_on_the_entry(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "description", '"a trend"', cache)
        assert plan.edits[0].operations == (
            Operation("set", "constants[0].description", '"a trend"'),
        )

    def test_a_description_may_be_taken_away(self, tmp_path: Path) -> None:
        """The model defaults it to empty, so a file without one loads - and part 3's chooser
        already offers to leave a key out wherever the format allows it."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "description", None, cache)
        assert plan.edits[0].operations == (Operation("remove", "constants[0].description"),)

    def test_a_value_may_not_be_taken_away(self, tmp_path: Path) -> None:
        """`ConstantDeclaration` requires it, so the file would stop loading and the tab would
        have emptied itself in one press."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "value", None, cache)
        assert raised.value.code == "invalid"
        assert "c.ddd.json" in raised.value.message
        # Not just "invalid" naming the file: falling through to `_value(None, ...)` instead of
        # refusing explicitly raises the same code, naming the same file, in the confusing
        # wording "None is not a value a constant may state" - this phrase is the guard's own.
        assert "cannot be left without one" in raised.value.message

    def test_a_key_already_left_out_answers_no_edit_at_all(self, tmp_path: Path) -> None:
        """`CELLS` has no description to begin with. Asked to remove one anyway, the edit engine
        would refuse: `EditError: nothing to remove at component.constants[0].description` -
        measured, not guessed, by actually applying the operation the brief's own code would have
        planned here. `type_plans.set_key` answers an empty plan for the identical case on a
        type, and a reader who has only selected the row - not typed anything - must not be
        refused before they have done anything."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_constant(built, "CELLS", "description", None, cache) == SharedPlan(())

    def test_a_key_a_constant_has_not_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "unit", '"rpm"', cache)
        assert raised.value.code == "invalid"
        assert "description" in raised.value.message and "value" in raised.value.message
        # Not just what a constant *does* have: the key actually asked about, so a rewording
        # that drops `{key}` and only lists `SETTABLE` would still read as a correct refusal.
        assert "'unit'" in raised.value.message

    def test_a_key_a_constant_has_not_names_the_file_it_concerns(self, tmp_path: Path) -> None:
        """Every refusal names the file it concerns, the way `UnitRefusalError`'s docstring
        requires of the units plans - this key is not one an entry has, but the entry is still
        the reader's own, in a file the reader can open."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "unit", '"rpm"', cache)
        assert "c.ddd.json" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "NOTHING", "value", "1", cache)
        assert raised.value.code == "not-found"

    @pytest.mark.parametrize("raw", ['"eight"', "true", "null", "[1]", "1e400"])
    def test_a_value_the_format_would_refuse_is_refused_here(
        self, tmp_path: Path, raw: str
    ) -> None:
        """Written, the file would stop loading and the whole project with it - every tab empty
        because of one keystroke in this one. `ConstantValue` itself is the judge, so the
        interface and the loader cannot disagree about what a constant may hold."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "value", raw, cache)
        assert raised.value.code == "invalid"

    def test_a_value_no_shape_could_use_is_allowed(self, tmp_path: Path) -> None:
        """`2.5` is a legal constant. A shape naming it is what makes it wrong, and
        `dimension-value` is the check that says so - on the next revision, in the panel, with a
        route back to this value. The interface does not invent a rule the format has not."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_constant(built, "TREND_SAMPLES", "value", "2.5", cache).edits


class TestRemoving:
    def test_an_entry_nothing_names_is_taken_out(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = remove_constant(built, "CELLS", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("a.ddd.json", (Operation("remove", "component.constants[0]"),))
        ]

    def test_a_constant_a_shape_names_is_refused_with_where_it_is_named(
        self, tmp_path: Path
    ) -> None:
        """Removed, every shape naming it would be left naming nothing - `unknown-constant` on
        each, in files the reader was not looking at. Asked of the index, never of a file's text:
        that is the mistake part 11 filed against `variable_keys._storage_of`."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "TREND_SAMPLES", cache)
        assert raised.value.code == "invalid"
        assert "a.ddd.json" in raised.value.message
        # Not `"1 shape" in message`: that substring is also true of the wrong wording
        # "1 shapes", so it would survive `_plural` always adding the "s". The comma pins the
        # word's own end.
        assert "is named by 1 shape," in raised.value.message

    def test_a_constant_two_shapes_name_reads_the_plural(self, tmp_path: Path) -> None:
        """The other arm of `_plural`'s conditional expression: invisible to coverage.py, which
        counts no branch in a conditional expression at all, so only a test that reads the actual
        wording proves both counts ship - `TWO_HOMES` alone only ever puts one shape on a name."""
        built = _index(tmp_path, _TWO_USES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "TREND_SAMPLES", cache)
        assert "is named by 2 shapes," in raised.value.message
        # The message names *the first* blocking shape. `a.ddd.json` comes before `b.ddd.json`
        # in `built.constant_uses["TREND_SAMPLES"]` here, so `used[0]` and `used[-1]` disagree -
        # the one place the single-use tests above cannot tell the two apart.
        assert "a.ddd.json" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "NOTHING", cache)
        assert raised.value.code == "not-found"


def test_a_value_travels_as_the_json_text_it_would_be_written_as() -> None:
    """`_raw` has no caller in this module: `set_constant` and `remove_constant` both carry the
    text their caller already gave them, exactly because re-serialising a value is the mistake
    this module's own docstring warns against. It is written here for `rename_constant` and
    `add_constant` to share, which is why it is tested directly - a degree sign is what
    `json.dumps`'s default would escape, and the escaped spelling is not what this exists to
    prevent."""
    assert _raw("30\N{DEGREE SIGN}") == '"30\N{DEGREE SIGN}"'
