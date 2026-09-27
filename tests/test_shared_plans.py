"""What changing one of a project's constants takes, planned and never written."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from conftest import built_of, component, declare, project, write_tree
from ddd import project_shared
from ddd.editing import Operation
from ddd.loading import included_files
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document
from ddd.shared_plans import (
    CONSTANTS_FILE,
    SharedPlan,
    SharedProject,
    SharedRefusalError,
    _raw,
    add_constant,
    remove_constant,
    remove_entry,
    rename_constant,
    set_constant,
    set_entry,
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

    def test_a_file_that_does_not_parse_is_named_among_the_ones_that_cannot_be_told(
        self, tmp_path: Path
    ) -> None:
        """Not counted is not the same as not there: counting it as no constants file at all left
        `constants_files` empty, which `add_constant` read as "this project has no constants file"
        and answered by writing a second one beside the description. Named here instead, so the
        one verb that would create a file can see what it does not know."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": "{"})
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.untellable] == ["c.ddd.json"]

    def test_a_file_the_project_includes_and_does_not_have_cannot_hide_a_constant(
        self, tmp_path: Path
    ) -> None:
        """A file that is not there reads exactly as one that did not parse - `Document.data` is
        `None` for both - and the two must not be answered the same way: a file that does not
        exist declares nothing, so it hides no name a new constants file could collide with, and
        an `includes` entry naming nothing is a finding `ddd check` already files. Counted as
        untellable it would stop `add` creating for every project that has a stale entry in its
        `includes`."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "gone.ddd.json")})
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert (found.constants_files, found.untellable) == ((), ())

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


# A third tree, for the removals that are allowed: a constants file and a component's own list,
# each holding two constants, and no shape naming any of them. `TWO_HOMES` cannot serve - each of
# its two lists holds exactly one entry, which is the case a removal is now refused in, since the
# list left behind would be empty and `constants` is `min_length=1` in both homes.
_TWO_EACH = {
    "c.ddd.json": {
        "constants": [
            {"name": "SPARE", "value": 3, "description": "goes"},
            {"name": "KEPT", "value": 1, "description": "stays"},
        ]
    },
    "a.ddd.json": component(
        "A",
        declare("output", "Speed", unit="rpm"),
        constants=[{"name": "CELLS", "value": 2.0}, {"name": "ROWS", "value": 4}],
    ),
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

    @pytest.mark.parametrize("raw", ["123", "true", "null", "[1]", '{"a": 1}', "not json"])
    def test_a_description_the_format_would_refuse_is_refused_here(
        self, tmp_path: Path, raw: str
    ) -> None:
        """`value` is validated against the format; until now `description` was not, so
        `?action=set&key=description&raw=123` planned `"description": 123` - a number where
        `ConstantDeclaration` wants a string - and the file it landed in stopped loading,
        emptying every tab in the page over one keystroke. This is `_value`'s own asymmetry,
        closed the same way for `description`."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "description", raw, cache)
        assert raised.value.code == "invalid"
        assert "c.ddd.json" in raised.value.message


class TestRemoving:
    def test_an_entry_nothing_names_is_taken_out(self, tmp_path: Path) -> None:
        built = _index(tmp_path, _TWO_EACH)
        cache: dict[Path, Document] = {}
        plan = remove_constant(built, "SPARE", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("c.ddd.json", (Operation("remove", "constants[0]"),))
        ]

    def test_an_entry_of_a_component_s_own_list_is_taken_out_of_that_list(
        self, tmp_path: Path
    ) -> None:
        """The other home, whose entries sit at `component.constants[i]` rather than
        `constants[i]`: the list a removal has to count is the one holding the entry, which is a
        different pointer in each home - `parent_pointer` is what turns one into the other, as
        `lsp/units.py` already uses it to."""
        built = _index(tmp_path, _TWO_EACH)
        cache: dict[Path, Document] = {}
        plan = remove_constant(built, "CELLS", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("a.ddd.json", (Operation("remove", "component.constants[0]"),))
        ]

    def test_the_only_constant_a_constants_file_declares_stays(self, tmp_path: Path) -> None:
        """`ConstantsFile.constants` is `min_length=1`, so the file this would leave holding
        `{"constants": []}` no longer loads: measured through the endpoint, `ddd check` answers
        `error[schema]: Tuple should have at least 1 item after validation, not 0` and exits 1.
        `lsp/units.py`'s `_taken_out` refuses the last unit of a units file in the same words and
        for the same reason."""
        built = _index(tmp_path, {"c.ddd.json": CONSTANTS})
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "TREND_SAMPLES", cache)
        assert raised.value.code == "invalid"
        assert "'TREND_SAMPLES' is all c.ddd.json declares" in raised.value.message

    def test_the_only_constant_a_component_declares_inline_stays(self, tmp_path: Path) -> None:
        """`Component.constants` carries the same `min_length=1`, and the consequence there is
        worse than a file that does not load: the component stops loading, so every variable it
        declares leaves the project along with the constant. Two clicks from this branch's own
        add flow - declare a constant into a project that has none, then remove it, since nothing
        names it and Remove is offered."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "CELLS", cache)
        assert raised.value.code == "invalid"
        assert "'CELLS' is all a.ddd.json declares" in raised.value.message

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


class TestRenaming:
    def test_the_entry_and_every_shape_naming_it_are_rewritten_in_one_edit(
        self, tmp_path: Path
    ) -> None:
        """All or nothing: a rename that reached the entry but not the shapes would leave the
        project with `unknown-constant` on every one of them."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = rename_constant(built, "TREND_SAMPLES", "TREND_SLOTS", cache)
        assert {edit.path.name: edit.operations for edit in plan.edits} == {
            "a.ddd.json": (
                Operation(
                    "set",
                    "component.interface[0].definition.dimensions[0]",
                    '"TREND_SLOTS"',
                ),
            ),
            "c.ddd.json": (Operation("set", "constants[0].name", '"TREND_SLOTS"'),),
        }

    def test_the_edits_come_sorted_by_path(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = rename_constant(built, "TREND_SAMPLES", "TREND_SLOTS", cache)
        assert [edit.path.name for edit in plan.edits] == ["a.ddd.json", "c.ddd.json"]

    @pytest.mark.parametrize(
        ("to", "because"),
        [
            ("2CELLS", "not a usable c identifier"),
            ("CELLS", "the name of the declared constant"),
            ("int", "reserved by c"),
        ],
    )
    def test_a_name_the_editor_refuses_is_refused_here_in_its_words(
        self, tmp_path: Path, to: str, because: str
    ) -> None:
        """`rename_problem` is the editor's own judge, and the tab asks it rather than deciding
        for itself: two clients that refused different names would disagree about what a project
        may be called. The fragments are read off what that function actually returns for this
        tree, not guessed: `CELLS` is an existing *constant*, so it is refused as `occupied`
        rather than as `already declared` - the wording `built.declarations` gets, which only
        variables are recorded under, `Trend` among them here but not asked for."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_constant(built, "TREND_SAMPLES", to, cache)
        assert raised.value.code == "invalid"
        assert because in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_constant(built, "NOTHING", "SOMETHING", cache)
        assert raised.value.code == "not-found"


class TestDeclaringOne:
    def test_it_is_appended_to_the_first_constants_file_the_project_includes(
        self, tmp_path: Path
    ) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "PRESSURE_CELLS", "8", cache)
        assert [edit.path.name for edit in plan.edits] == ["c.ddd.json"]
        assert plan.edits[0].operations[0].op == "insert"
        assert plan.edits[0].operations[0].pointer == "constants[1]"
        assert '"value": 8' in (plan.edits[0].operations[0].raw or "")
        assert plan.edits[0].creates is False

    def test_it_lands_in_the_first_of_two_constants_files_not_the_last(
        self, tmp_path: Path
    ) -> None:
        """Every other tree in this class has at most one constants file, so nothing above tells
        `constants_files[0]` apart from `constants_files[-1]`. `SharedProject.constants_files`'
        own docstring promises "the first is where a new constant goes, so that it lands in the
        file a run of `ddd check` reads first" - this is the test that holds `add_constant` to
        that promise. The file that is first in `includes` sorts *last* alphabetically, so an
        implementation that quietly sorted the files instead of trusting their `includes` order
        would also be caught here."""
        files = {
            "z_first.ddd.json": {"constants": [{"name": "FIRST_ONE", "value": 1}]},
            "a_second.ddd.json": {"constants": [{"name": "SECOND_ONE", "value": 2}]},
        }
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert [f.name for f in found.constants_files] == ["z_first.ddd.json", "a_second.ddd.json"]
        plan = add_constant(built, found, "NEW_ONE", "9", cache)
        assert plan.edits[0].path.name == "z_first.ddd.json"
        assert plan.edits[0].operations[0].pointer == "constants[1]"

    def test_the_value_is_embedded_as_the_text_it_was_given(self, tmp_path: Path) -> None:
        """`2.0` declares a fractional constant and `2` a whole one. Parsed and reprinted, a
        reader asking for one would get the other."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "GAIN", "2.0", cache)
        assert '"value": 2.0' in (plan.edits[0].operations[0].raw or "")

    def test_a_spelling_that_round_trips_differently_is_still_kept_as_written(
        self, tmp_path: Path
    ) -> None:
        """`2.0` happens to come back `2.0` even parsed and reprinted through json, so the test
        above would not notice a plan that did that. `1e3` would not: reprinted, it is `1000.0` -
        the module's own docstring names this exact number - so this is the case that actually
        tells a verbatim `raw` apart from a parsed-and-reprinted one."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "GAIN", "1e3", cache)
        assert '"value": 1e3' in (plan.edits[0].operations[0].raw or "")

    def test_a_constants_file_whose_constants_is_not_a_list_still_gets_a_first_entry(
        self, tmp_path: Path
    ) -> None:
        """`shared_project` only asks whether a file's top level holds a `constants` key, never
        whether that key is a list - so a file this broken can still be
        `project.constants_files[0]`, and `add_constant` has to pick a pointer without crashing
        on it rather than assume every constants file loaded clean."""
        built = _index(tmp_path, TWO_HOMES)
        write_tree(tmp_path, {"weird.ddd.json": {"constants": "oops"}})
        cache: dict[Path, Document] = {}
        broken = SharedProject(tmp_path / "p.ddd.json", (tmp_path / "weird.ddd.json",), (), ())
        plan = add_constant(built, broken, "NEW_CONST", "8", cache)
        assert plan.edits[0].path.name == "weird.ddd.json"
        assert plan.edits[0].operations[0].pointer == "constants[0]"
        assert '"name": "NEW_CONST"' in (plan.edits[0].operations[0].raw or "")

    def test_a_project_with_no_constants_file_gets_one_beside_its_description(
        self, tmp_path: Path
    ) -> None:
        """Both edits in one plan, so a project can never list a file that was not written.
        `Session._confined` allows exactly this shape of creation and no other."""
        files = {"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "CELLS", "8", cache)
        assert [(edit.path.name, edit.creates) for edit in plan.edits] == [
            ("constants.ddd.json", True),
            ("p.ddd.json", False),
        ]
        whole = plan.edits[0].operations[0].raw or ""
        assert whole.startswith("{\n") and whole.endswith("}\n")
        assert '"name": "CELLS"' in whole
        assert plan.edits[1].operations == (
            Operation("insert", "project.includes[1]", '"constants.ddd.json"'),
        )

    def test_a_project_whose_includes_is_not_a_list_still_gets_a_first_entry(
        self, tmp_path: Path
    ) -> None:
        """The creating arm's own version of the guard above: a project this broken never
        reaches `ddd gui` in the first place, but the plan reads the raw document before
        anything validates it, so a length taken unconditionally would raise while building the
        plan rather than answer with a pointer at all."""
        built = _index(tmp_path, TWO_HOMES)
        write_tree(tmp_path, {"solo.ddd.json": {"project": {"name": "P", "includes": 3}}})
        cache: dict[Path, Document] = {}
        broken = SharedProject(tmp_path / "solo.ddd.json", (), (), ())
        plan = add_constant(built, broken, "NEW_CONST", "8", cache)
        assert [(edit.path.name, edit.creates) for edit in plan.edits] == [
            ("constants.ddd.json", True),
            ("solo.ddd.json", False),
        ]
        assert plan.edits[1].operations == (
            Operation("insert", "project.includes[0]", '"constants.ddd.json"'),
        )

    def test_a_file_of_that_name_already_there_is_refused_rather_than_overwritten(
        self, tmp_path: Path
    ) -> None:
        files = {"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        built = _index(tmp_path, files)
        write_tree(tmp_path, {"constants.ddd.json": "not a description"})
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS", "8", cache)
        assert raised.value.code == "invalid"
        assert "constants.ddd.json" in raised.value.message

    def test_a_file_nobody_could_read_stops_a_second_constants_file_being_created(
        self, tmp_path: Path
    ) -> None:
        """The creating arm's premise is "this project has no constants file", and that is not
        something anyone knows while one of its files is mid-save: measured through the endpoint,
        a project including a `sizes.ddd.json` truncated as an editor leaves it answered a
        two-edit plan creating a second `constants.ddd.json` and an `includes` entry naming it.
        The harm is the one `test_a_constants_file_that_did_not_load_is_not_appended_to` below
        exists to prevent - what that file declares is unknown, so the name declared here can
        collide with one in it the moment it is saved. `lsp/units.py`'s `add_unit` refuses the
        same situation, having no creating arm to fall into."""
        files = {"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        built = _index(tmp_path, files)
        write_tree(tmp_path, {"p.ddd.json": project("P", "sizes.ddd.json", "a.ddd.json")})
        (tmp_path / "sizes.ddd.json").write_text('{"constants": [{"name": "', encoding="utf-8")
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert found.constants_files == ()
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "NEW_ONE", "8", cache)
        assert raised.value.code == "unreadable"
        assert "sizes.ddd.json did not parse" in raised.value.message
        assert not (tmp_path / CONSTANTS_FILE).exists()

    def test_a_file_nobody_could_read_does_not_stop_an_append_to_one_that_loaded(
        self, tmp_path: Path
    ) -> None:
        """The refusal above belongs to the creating arm alone. Where the project has a constants
        file that loaded, `add` knows both where the entry goes and what that file declares, and
        the name is refused by `rename_problem` if the project declares it already - so a second
        file nobody could read is no reason to refuse the one thing this project asked for. The
        guard placed a line earlier, before the branch, would have refused it."""
        built = _index(tmp_path, TWO_HOMES)
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "c.ddd.json", "sizes.ddd.json", "a.ddd.json")},
        )
        (tmp_path / "sizes.ddd.json").write_text("{", encoding="utf-8")
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.untellable] == ["sizes.ddd.json"]
        plan = add_constant(built, found, "NEW_ONE", "8", cache)
        assert [edit.path.name for edit in plan.edits] == ["c.ddd.json"]

    def test_a_constants_file_that_did_not_load_is_not_appended_to(self, tmp_path: Path) -> None:
        """It parses, so it is a constants file; it did not load, so what it already declares is
        unknown - and an entry appended to it could collide with one of them."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", [tmp_path / "c.ddd.json"], cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS_2", "8", cache)
        assert raised.value.code == "unreadable"
        assert "c.ddd.json" in raised.value.message

    def test_a_name_the_project_already_declares_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "TREND_SAMPLES", "8", cache)
        assert raised.value.code == "invalid"

    def test_a_name_a_component_declares_inline_is_refused_before_a_file_is_created(
        self, tmp_path: Path
    ) -> None:
        """The collision guard has to run before the branch on `project.constants_files`, not
        only where a constants file already exists: `_created` never calls `rename_problem`
        itself, so if the guard moved after `if not project.constants_files: return
        _created(...)`, a component's own inline `CELLS` would not stop a brand new
        `constants.ddd.json` from declaring a second one of that name - "two components share
        storage neither of them meant to", in `rename_problem`'s own words."""
        files = {
            "a.ddd.json": component(
                "A",
                declare("output", "Speed", unit="rpm"),
                constants=[{"name": "CELLS", "value": 2.0}],
            )
        }
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert not found.constants_files
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS", "8", cache)
        assert raised.value.code == "invalid"

    def test_a_value_the_format_would_refuse_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS_2", '"eight"', cache)
        assert raised.value.code == "invalid"

    def test_a_value_the_format_would_refuse_is_refused_when_creating_too(
        self, tmp_path: Path
    ) -> None:
        """The same guard, in the creating arm: a bad value must not reach a file that did not
        exist a moment ago either, and nothing above exercises `_value` there."""
        files = {"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS", '"eight"', cache)
        assert raised.value.code == "invalid"


# A fourth tree, for the one test whose constant is both the sole entry of its file and named by
# a shape at once: `remove_entry`'s two guards both apply, and which sentence a reader meets must
# not depend on the order a dict happened to yield. Copied in the corrected shape the trees above
# use - a `scope` of `output`, a `kind` of `measurement`, `conversion` and `volatile` both present.
SOLE_AND_NAMED = {
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
}


class TestTheDescriptorsVerbs:
    def test_a_key_is_set_through_the_vocabulary_it_belongs_to(self, tmp_path: Path) -> None:
        built, _root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_entry(
            project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", "2.0", cache
        ) == set_constant(built, "TREND_SAMPLES", "value", "2.0", cache)

    def test_a_constant_both_named_and_alone_is_refused_for_being_named(
        self, tmp_path: Path
    ) -> None:
        # Both guards apply at once, and which sentence a reader meets must not depend on the
        # order a dict happened to yield. Named-by-something is checked first, because it names a
        # place the reader can go and undo; being alone in its file names only the file.
        built, _root = built_of(tmp_path, **SOLE_AND_NAMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", cache)
        assert "is named by" in raised.value.message
        assert "is all" not in raised.value.message
