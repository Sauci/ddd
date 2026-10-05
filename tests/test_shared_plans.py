"""What changing one of a project's constants takes, planned and never written."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from conftest import built_of, checks, component, declare, project, run_analysis, write_tree
from ddd import project_shared
from ddd.diagnostics import DiagnosticBag, Location, Severity
from ddd.editing import FileChange, Operation, edit_text, fingerprint
from ddd.gui.session import Session
from ddd.loading import included_files, load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.lsp.units import PlannedEdit
from ddd.project_shared import RASTERS, SECTIONS, Vocabulary
from ddd.shared_plans import (
    CONSTANTS_FILE,
    SharedPlan,
    SharedProject,
    SharedRefusalError,
    _raw,
    add_entry,
    project_of,
    remove_entry,
    rename_entry,
    set_entry,
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
    def test_the_vocabularys_own_files_come_in_the_order_includes_lists_them(
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.files] == [
            "second.ddd.json",
            "first.ddd.json",
        ]
        assert found.project == (tmp_path / "p.ddd.json").resolve()

    def test_a_file_that_does_not_parse_is_no_constants_file(self, tmp_path: Path) -> None:
        """What a file is cannot be told from one nobody could read, so it is not counted - and a
        new constant must not be appended to it."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": "{"})
        cache: dict[Path, Document] = {}
        assert project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache).files == ()

    def test_a_file_that_does_not_parse_is_named_among_the_ones_that_cannot_be_told(
        self, tmp_path: Path
    ) -> None:
        """Not counted is not the same as not there: counting it as no constants file at all left
        `files` empty, which `add_entry` read as "this project has no constants file"
        and answered by writing a second one beside the description. Named here instead, so the
        one verb that would create a file can see what it does not know."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": "{"})
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert (found.files, found.untellable) == ((), ())

    def test_a_project_naming_no_constants_file_has_none(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        cache: dict[Path, Document] = {}
        assert project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache).files == ()

    def test_one_file_named_twice_is_listed_once(self, tmp_path: Path) -> None:
        """A pattern and a literal entry can name the same file; the first is where a new constant
        goes, and a list holding it twice would say there are two places."""
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "c.ddd.json", "*.ddd.json"), "c.ddd.json": CONSTANTS},
        )
        cache: dict[Path, Document] = {}
        assert (
            len(project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache).files) == 1
        )

    def test_the_files_that_did_not_load_are_resolved_and_sorted(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        cache: dict[Path, Document] = {}
        unread = [tmp_path / "z.ddd.json", tmp_path / "a.ddd.json", tmp_path / "z.ddd.json"]
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", unread, cache)
        assert [file.name for file in found.unread] == ["a.ddd.json", "z.ddd.json"]

    def test_an_includes_that_is_not_a_list_names_nothing(self, tmp_path: Path) -> None:
        """A project whose `includes` is a number is refused by the loader; read here it has to
        answer no files rather than iterate a number."""
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 3}}})
        cache: dict[Path, Document] = {}
        assert project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache).files == ()


def test_the_file_a_project_without_one_gets_is_named_for_what_it_holds() -> None:
    assert CONSTANTS_FILE == "constants.ddd.json"


def test_a_refusal_carries_its_code_and_its_sentence() -> None:
    with pytest.raises(SharedRefusalError) as raised:
        raise SharedRefusalError("invalid", "'X' is already declared")
    assert (raised.value.code, raised.value.message) == ("invalid", "'X' is already declared")


def _index(tmp_path: Path, files: Mapping[str, Any]) -> Index:
    """The index `conftest.built_of` makes of this tree, discarding the root."""
    return built_of(tmp_path, **files)[0]


def _made(plan: SharedPlan) -> None:
    """Every edit of the plan made on disk by the edit engine, as `POST /api/edit` makes it, so
    that what a removal leaves can be loaded rather than only read off its operations."""
    for edit in plan.edits:
        assert not edit.creates
        text = edit_text(edit.path.read_text(encoding="utf-8"), edit.operations)
        edit.path.write_text(text, encoding="utf-8", newline="")


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


# A third tree, for removals that leave something behind: a constants file and a component's own
# list, each holding two constants, and no shape naming any of them. `TWO_HOMES` holds exactly one
# entry in each list, which is the other case: the last entry of a file's own list leaves it
# declaring nothing, and the last of a component's takes the component's `constants` key with it.
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
        plan = set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", "2.0", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("c.ddd.json", (Operation("set", "constants[0].value", "2.0"),))
        ]

    def test_a_description_is_set_on_the_entry(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_entry(
            project_shared.CONSTANTS, built, "TREND_SAMPLES", "description", '"a trend"', cache
        )
        assert plan.edits[0].operations == (
            Operation("set", "constants[0].description", '"a trend"'),
        )

    def test_a_description_may_be_taken_away(self, tmp_path: Path) -> None:
        """The model defaults it to empty, so a file without one loads - and part 3's chooser
        already offers to leave a key out wherever the format allows it."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_entry(
            project_shared.CONSTANTS, built, "TREND_SAMPLES", "description", None, cache
        )
        assert plan.edits[0].operations == (Operation("remove", "constants[0].description"),)

    def test_a_value_may_not_be_taken_away(self, tmp_path: Path) -> None:
        """`ConstantDeclaration` requires it, so the file would stop loading and the tab would
        have emptied itself in one press."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", None, cache)
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
        assert set_entry(
            project_shared.CONSTANTS, built, "CELLS", "description", None, cache
        ) == SharedPlan(())

    def test_a_key_a_constant_has_not_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "unit", '"rpm"', cache)
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
            set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "unit", '"rpm"', cache)
        assert "c.ddd.json" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(project_shared.CONSTANTS, built, "NOTHING", "value", "1", cache)
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
            set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", raw, cache)
        assert raised.value.code == "invalid"

    def test_a_value_no_shape_could_use_is_allowed(self, tmp_path: Path) -> None:
        """`2.5` is a legal constant. A shape naming it is what makes it wrong, and
        `dimension-value` is the check that says so - on the next revision, in the panel, with a
        route back to this value. The interface does not invent a rule the format has not."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_entry(
            project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", "2.5", cache
        ).edits

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
            set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "description", raw, cache)
        assert raised.value.code == "invalid"
        assert "c.ddd.json" in raised.value.message


class TestRemoving:
    def test_an_entry_nothing_names_is_taken_out(self, tmp_path: Path) -> None:
        built = _index(tmp_path, _TWO_EACH)
        cache: dict[Path, Document] = {}
        plan = remove_entry(project_shared.CONSTANTS, built, "SPARE", cache)
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
        plan = remove_entry(project_shared.CONSTANTS, built, "CELLS", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("a.ddd.json", (Operation("remove", "component.constants[0]"),))
        ]

    def test_the_only_constant_a_constants_file_declares_is_taken_out(self, tmp_path: Path) -> None:
        """A constants file's own list may be empty, so its last constant goes like any other:
        the file is left declaring nothing, loads, and is reported as `empty-vocabulary`.

        This was refused until `ConstantsFile.constants` went to `min_length=0`, because
        `{"constants": []}` answered `error[schema]` - and `ddd gui`, which cannot delete a
        file, then had no way to take a project from one constant to none."""
        built = _index(tmp_path, {"c.ddd.json": CONSTANTS})
        plan = remove_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", {})
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("c.ddd.json", (Operation("remove", "constants[0]"),))
        ]
        _made(plan)
        dictionary, bag = run_analysis(tmp_path, {}, root="p.ddd.json")
        assert dictionary is not None
        assert [(found.check, found.severity, found.location) for found in bag] == [
            (
                "empty-vocabulary",
                Severity.INFO,
                Location((tmp_path / "c.ddd.json").resolve(), "constants"),
            )
        ]

    def test_the_only_constant_a_component_declares_inline_takes_the_key_with_it(
        self, tmp_path: Path
    ) -> None:
        """`Component.constants` is still `min_length=1` - leaving the key out is how a component
        publishes none - so its last constant goes with the key holding it.

        Asserted by loading what the plan leaves, not by comparing its operations: the failure
        this is here to catch is `"constants": []` written into the component, which stops the
        component loading, so every variable it declares - `Trend` here - would leave the project
        along with the constant the reader meant to remove."""
        built = _index(tmp_path, TWO_HOMES)
        _made(remove_entry(project_shared.CONSTANTS, built, "CELLS", {}))
        dictionary, bag = run_analysis(tmp_path, {}, root="p.ddd.json")
        assert "schema" not in checks(bag)
        assert dictionary is not None
        assert [component.name for component in dictionary.components] == ["A"]
        assert [declared.name for declared in dictionary.objects] == ["Trend"]
        assert [declared.name for declared in dictionary.constants] == ["TREND_SAMPLES"]
        left = json.loads((tmp_path / "a.ddd.json").read_text(encoding="utf-8"))
        assert "constants" not in left["component"]

    def test_a_constant_a_shape_names_is_refused_with_where_it_is_named(
        self, tmp_path: Path
    ) -> None:
        """Removed, every shape naming it would be left naming nothing - `unknown-constant` on
        each, in files the reader was not looking at. Asked of the index, never of a file's text:
        that is the mistake part 11 filed against `variable_keys._storage_of`."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", cache)
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
            remove_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", cache)
        assert "is named by 2 shapes," in raised.value.message
        # The message names *the first* blocking shape. `a.ddd.json` comes before `b.ddd.json`
        # in `built.constant_uses["TREND_SAMPLES"]` here, so `used[0]` and `used[-1]` disagree -
        # the one place the single-use tests above cannot tell the two apart.
        assert "a.ddd.json" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_entry(project_shared.CONSTANTS, built, "NOTHING", cache)
        assert raised.value.code == "not-found"


def test_a_value_travels_as_the_json_text_it_would_be_written_as() -> None:
    """`_raw` has no caller in this module: `set_entry` and `remove_entry` both carry the
    text their caller already gave them, exactly because re-serialising a value is the mistake
    this module's own docstring warns against. It is written here for `rename_entry` and
    `add_entry` to share, which is why it is tested directly - a degree sign is what
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
        plan = rename_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "TREND_SLOTS", cache)
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
        plan = rename_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "TREND_SLOTS", cache)
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
            rename_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", to, cache)
        assert raised.value.code == "invalid"
        assert because in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_entry(project_shared.CONSTANTS, built, "NOTHING", "SOMETHING", cache)
        assert raised.value.code == "not-found"


class TestDeclaringOne:
    def test_it_is_appended_to_the_first_constants_file_the_project_includes(
        self, tmp_path: Path
    ) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "PRESSURE_CELLS",
            {"value": "8", "description": '""'},
            cache,
        )
        assert [edit.path.name for edit in plan.edits] == ["c.ddd.json"]
        assert plan.edits[0].operations[0].op == "insert"
        assert plan.edits[0].operations[0].pointer == "constants[1]"
        assert '"value": 8' in (plan.edits[0].operations[0].raw or "")
        assert plan.edits[0].creates is False

    def test_it_lands_in_the_first_of_two_constants_files_not_the_last(
        self, tmp_path: Path
    ) -> None:
        """Every other tree in this class has at most one constants file, so nothing above tells
        `files[0]` apart from `files[-1]`. `SharedProject.files`' own docstring promises "the first
        is where a new entry goes, so that it lands in the file a run of `ddd check` reads first" -
        this is the test that holds `add_entry` to
        that promise. The file that is first in `includes` sorts *last* alphabetically, so an
        implementation that quietly sorted the files instead of trusting their `includes` order
        would also be caught here."""
        files = {
            "z_first.ddd.json": {"constants": [{"name": "FIRST_ONE", "value": 1}]},
            "a_second.ddd.json": {"constants": [{"name": "SECOND_ONE", "value": 2}]},
        }
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert [f.name for f in found.files] == ["z_first.ddd.json", "a_second.ddd.json"]
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "NEW_ONE",
            {"value": "9", "description": '""'},
            cache,
        )
        assert plan.edits[0].path.name == "z_first.ddd.json"
        assert plan.edits[0].operations[0].pointer == "constants[1]"

    def test_the_value_is_embedded_as_the_text_it_was_given(self, tmp_path: Path) -> None:
        """`2.0` declares a fractional constant and `2` a whole one. Parsed and reprinted, a
        reader asking for one would get the other."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "GAIN",
            {"value": "2.0", "description": '""'},
            cache,
        )
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "GAIN",
            {"value": "1e3", "description": '""'},
            cache,
        )
        assert '"value": 1e3' in (plan.edits[0].operations[0].raw or "")

    def test_a_constants_file_whose_constants_is_not_a_list_still_gets_a_first_entry(
        self, tmp_path: Path
    ) -> None:
        """`project_of` only asks whether a file's top level holds its vocabulary's own container
        key, never
        whether that key is a list - so a file this broken can still be
        `project.files[0]`, and `add_entry` has to pick a pointer without crashing
        on it rather than assume every constants file loaded clean."""
        built = _index(tmp_path, TWO_HOMES)
        write_tree(tmp_path, {"weird.ddd.json": {"constants": "oops"}})
        cache: dict[Path, Document] = {}
        broken = SharedProject(tmp_path / "p.ddd.json", (tmp_path / "weird.ddd.json",), (), ())
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            broken,
            "NEW_CONST",
            {"value": "8", "description": '""'},
            cache,
        )
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "CELLS",
            {"value": "8", "description": '""'},
            cache,
        )
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
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            broken,
            "NEW_CONST",
            {"value": "8", "description": '""'},
            cache,
        )
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "CELLS",
                {"value": "8", "description": '""'},
                cache,
            )
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert found.files == ()
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "NEW_ONE",
                {"value": "8", "description": '""'},
                cache,
            )
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.untellable] == ["sizes.ddd.json"]
        plan = add_entry(
            project_shared.CONSTANTS,
            built,
            found,
            "NEW_ONE",
            {"value": "8", "description": '""'},
            cache,
        )
        assert [edit.path.name for edit in plan.edits] == ["c.ddd.json"]

    def test_a_constants_file_that_did_not_load_is_not_appended_to(self, tmp_path: Path) -> None:
        """It parses, so it is a constants file; it did not load, so what it already declares is
        unknown - and an entry appended to it could collide with one of them."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(
            project_shared.CONSTANTS, tmp_path / "p.ddd.json", [tmp_path / "c.ddd.json"], cache
        )
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "CELLS_2",
                {"value": "8", "description": '""'},
                cache,
            )
        assert raised.value.code == "unreadable"
        assert "c.ddd.json" in raised.value.message

    def test_a_name_the_project_already_declares_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "TREND_SAMPLES",
                {"value": "8", "description": '""'},
                cache,
            )
        assert raised.value.code == "invalid"

    def test_a_name_a_component_declares_inline_is_refused_before_a_file_is_created(
        self, tmp_path: Path
    ) -> None:
        """The collision guard has to run before the branch on `project.files`, not
        only where a constants file already exists: `_created` never calls `rename_problem`
        itself, so if the guard moved after `if not project.files: return
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
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        assert not found.files
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "CELLS",
                {"value": "8", "description": '""'},
                cache,
            )
        assert raised.value.code == "invalid"

    def test_a_value_the_format_would_refuse_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "CELLS_2",
                {"value": '"eight"', "description": '""'},
                cache,
            )
        assert raised.value.code == "invalid"

    def test_a_value_the_format_would_refuse_is_refused_when_creating_too(
        self, tmp_path: Path
    ) -> None:
        """The same guard, in the creating arm: a bad value must not reach a file that did not
        exist a moment ago either, and nothing above exercises `_value` there."""
        files = {"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "CELLS",
                {"value": '"eight"', "description": '""'},
                cache,
            )
        assert raised.value.code == "invalid"

    @pytest.mark.parametrize(
        ("vocabulary", "name", "raws"),
        [
            pytest.param(
                project_shared.CONSTANTS,
                "N",
                {"value": "3", "description": '""'},
                id="a constant",
            ),
            pytest.param(
                SECTIONS, ".fresh", {"access": '"read-write"', "alignment": "8"}, id="a section"
            ),
            pytest.param(RASTERS, "5ms", {"event": "2"}, id="a raster"),
        ],
    )
    def test_a_file_created_in_a_project_listing_no_includes_is_read_and_passes(
        self, tmp_path: Path, vocabulary: Vocabulary, name: str, raws: Mapping[str, str]
    ) -> None:
        """``includes`` may be left out of a description, and such a project - holding no file
        of any vocabulary - is one the creating arm is reached in. There is no list to insert
        the new file's name into, so the key is set to a list holding it alone, and the edit
        made through the session as ``POST /api/edit`` makes it leaves a project that passes."""
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "Bare"}}})
        root = tmp_path / "p.ddd.json"
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        cache: dict[Path, Document] = {}
        found = project_of(vocabulary, root, (), cache)
        plan = add_entry(vocabulary, index(workspace), found, name, raws, cache)
        assert [edit for edit in plan.edits if not edit.creates] == [
            PlannedEdit(
                root.resolve(),
                (Operation("set", "project.includes", f'["{vocabulary.filename}"]'),),
            )
        ]
        session = Session(tmp_path)
        session.open(root)
        session.edit(
            [
                FileChange(
                    edit.path,
                    None if edit.creates else fingerprint(edit.path.read_bytes()),
                    edit.operations,
                )
                for edit in plan.edits
            ],
            "the entry declared",
        )
        revision = session.revision
        assert revision is not None
        assert [
            (filed.file.name, filed.diagnostic.check)
            for filed in revision.findings
            if filed.diagnostic.severity is Severity.ERROR
        ] == []
        assert json.loads(root.read_text(encoding="utf-8"))["project"]["includes"] == [
            vocabulary.filename
        ]


# A fourth tree, for the one test whose constant is both the last its component declares inline
# and named by a shape of that component: `remove_entry` asks whether anything names an entry
# before it asks what taking it out leaves, and here the second answer would be the whole
# `constants` key. Copied in the corrected shape the trees above use - a `scope` of `output`, a
# `kind` of `measurement`, `conversion` and `volatile` both present.
SOLE_AND_NAMED = {
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 4}],
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "measurement",
                        "name": "Cells",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["CELLS"],
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
        plan = set_entry(project_shared.CONSTANTS, built, "TREND_SAMPLES", "value", "2.0", cache)
        # The whole expected plan spelled out - the file it lands in, the pointer inside it, and
        # the json text as written - rather than anything derived from another call of the verb
        # under test. Every part of the answer is stated here independently, so `set_entry`
        # ablated to `return SharedPlan(())`, or to an edit of the wrong file or the wrong key,
        # fails this line. Comparing one call against another cannot say any of that: it holds
        # whatever the function does today, which is the shape of an assertion that never fails.
        assert plan == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "c.ddd.json").resolve(),
                    (Operation("set", "constants[0].value", "2.0"),),
                ),
            )
        )

    def test_a_constant_both_named_and_last_of_its_list_is_refused_for_being_named(
        self, tmp_path: Path
    ) -> None:
        # Named-by-something is asked first, and on this entry the order is the difference
        # between a refusal and a broken project: `CELLS` is also the last constant its
        # component declares inline, and asked the other way round the plan would take the
        # component's `constants` key away while `Cells` still names what it held.
        built, _root = built_of(tmp_path, **SOLE_AND_NAMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_entry(project_shared.CONSTANTS, built, "CELLS", cache)
        assert raised.value.code == "invalid"
        assert "'CELLS' is named by 1 shape, the first in a.ddd.json" in raised.value.message

    def test_add_refuses_a_raw_key_the_vocabulary_does_not_have(self, tmp_path: Path) -> None:
        # `raws` is this task's own surface - the old `add_constant` took a single `raw` - so a
        # bad key in it is not a case that binding could ever have been asked about; this is
        # new ground `add_entry` has to cover itself, in `set_entry`'s own wording for the same
        # mistake.
        built, _root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = project_of(project_shared.CONSTANTS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(
                project_shared.CONSTANTS,
                built,
                found,
                "NEW_ONE",
                {"value": "8", "unit": '"rpm"'},
                cache,
            )
        assert raised.value.code == "invalid"
        assert "'unit'" in raised.value.message
        assert "description and value" in raised.value.message


# The second vocabulary, in the spelling `tests/test_project_shared.py` and `tests/test_lsp.py`
# both hold: copied by hand for the reason `TWO_HOMES` above is.
PLACED = {
    "s.ddd.json": {"sections": [{"section": ".calib", "access": "read-only", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "Gain", section=".calib")),
}

# Two sections, for the one refusal a project with a single section cannot reach: a rename onto a
# name the vocabulary already declares. Renaming `.calib` to itself would reach the same guard and
# say nothing about a reader's real mistake, which is picking a name another section took.
TWO_SECTIONS = {
    "s.ddd.json": {
        "sections": [
            {"section": ".calib", "access": "read-only", "alignment": 4},
            {"section": ".nvm", "access": "read-write", "alignment": 8},
        ]
    },
    "a.ddd.json": component("A", declare("output", "Gain", section=".calib")),
}


class TestSectionRefusals:
    @pytest.mark.parametrize(
        ("key", "raw"),
        [("access", '"read-sideways"'), ("alignment", "3"), ("alignment", "4.0")],
    )
    def test_a_value_the_model_would_refuse_is_refused_here(
        self, tmp_path: Path, key: str, raw: str
    ) -> None:
        # Measured on this checkout: `alignment: 3` answers `error[schema]: alignment 3 is not a
        # power of two`, and `4.0` is refused as not a whole number. Written, the file would not
        # load and every tab would empty because of one keystroke in this one. `access` reaches
        # here through the api whatever the panel's chooser offers.
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(SECTIONS, built, ".calib", key, raw, cache)
        assert raised.value.code == "invalid"
        assert "s.ddd.json" in raised.value.message

    def test_a_key_a_section_has_not_names_the_three_keys_it_states(self, tmp_path: Path) -> None:
        """The first vocabulary with three keys, and what `_listed` was written for: the generic
        `' and '.join` had only ever met two and read "access and alignment and description". The
        whole sentence is asserted, so the article in front of the kind is pinned here too. The
        constants spelling of the same sentence must stay "description and value" byte for byte,
        which `test_add_refuses_a_raw_key_the_vocabulary_does_not_have` above pins."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(SECTIONS, built, ".calib", "value", "1", cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == (
            "a section has no 'value' to set in s.ddd.json: it states access, alignment and "
            "description"
        )

    @pytest.mark.parametrize("key", ["access", "alignment"])
    def test_a_key_the_model_gives_no_default_may_not_be_taken_away(
        self, tmp_path: Path, key: str
    ) -> None:
        """Both of `SECTIONS.required`, deliberately and not as a side effect of some other
        assertion. A descriptor's field values are data, and the coverage gate cannot see data:
        `required` is a `frozenset` of two words, the `if key in vocabulary.required` branch is
        taken by either of them, and dropping one leaves both suites green at 100 %. Measured
        consequence of dropping `alignment`: `set_entry` plans
        `Operation("remove", "sections[0].alignment")`, the file stops validating, and every tab
        in the page empties over one keystroke in this one - the precise harm `set_entry`'s own
        docstring says the required check exists to prevent."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(SECTIONS, built, ".calib", key, None, cache)
        assert raised.value.code == "invalid"
        assert f"states an {key}" in raised.value.message
        assert "cannot be left without one in s.ddd.json" in raised.value.message

    def test_an_alignment_the_model_takes_is_planned(self, tmp_path: Path) -> None:
        """The other arm of the same judge, and the one that pins the placeholders `_aligned`
        builds its entry with: were either of them a value `SectionDeclaration` refuses, every
        alignment would be refused too and the three cases above would still pass."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        assert set_entry(SECTIONS, built, ".calib", "alignment", "8", cache) == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "s.ddd.json").resolve(),
                    (Operation("set", "sections[0].alignment", "8"),),
                ),
            )
        )

    def test_a_key_beginning_with_a_vowel_is_refused_in_english(self, tmp_path: Path) -> None:
        """`_judged`'s sentence writes an indefinite article in front of a word the descriptor
        supplies, and `alignment` and `access` are the first two such words to begin with a vowel:
        it read `3 is not a alignment a section may state` until `_article` was written. Constants
        were grammatical by luck - `value`, `description` and `constant` all begin with a consonant
        - which is why one vocabulary could not have found this. The same article in the sentence
        for a required key taken away is pinned by
        `test_a_key_the_model_gives_no_default_may_not_be_taken_away` above, for both keys."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as judged:
            set_entry(SECTIONS, built, ".calib", "alignment", "3", cache)
        assert "3 is not an alignment a section may state" in judged.value.message

    def test_a_name_the_pattern_refuses_is_refused(self, tmp_path: Path) -> None:
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_entry(SECTIONS, built, ".calib", ".cal ib", cache)
        assert raised.value.code == "invalid"

    def test_a_name_another_section_already_declares_is_refused(self, tmp_path: Path) -> None:
        """Refused rather than reported, though the file would still load: `duplicate-section` is
        a check and not a schema error, so the format permits two sections under one name - but
        they carry different `access` and `alignment`, and merging them would silently move data.
        The interface can see the name is taken and the reader can pick another."""
        built, _root = built_of(tmp_path, **TWO_SECTIONS)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_entry(SECTIONS, built, ".calib", ".nvm", cache)
        assert raised.value.code == "invalid"
        assert "already" in raised.value.message

    def test_a_section_may_be_renamed_to_a_name_no_c_identifier_allows(
        self, tmp_path: Path
    ) -> None:
        # The judge is the model's own pattern, not `rename_problem`: a leading dot is a normal
        # linker name and would fail a c identifier rule outright.
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        assert rename_entry(SECTIONS, built, ".calib", ".nvm", cache).edits

    def test_a_new_section_is_appended_to_the_file_the_project_keeps_them_in(
        self, tmp_path: Path
    ) -> None:
        """What `containers` and `name_key` are for, and the only test that can tell either of them
        has rotted: both are strings in the descriptor, and a descriptor's field values are data no
        coverage gate can see. `containers[0]` is asked twice here - `project_of` tells a sections
        file by that key at a document's top level, and the insert pointer is written from it - so
        `("bogus",)` would leave `files` empty and answer a two-edit plan creating a *second*
        sections file beside the project description. `name_key` is the first key of the entry text:
        `"name"` would declare `{"name": ".fresh", ...}`, which `extra="forbid"` rejects, so the
        file this wrote would no longer load. Latent until Task 5 wires the api, which is why it is
        pinned now."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        found = project_of(SECTIONS, tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.files] == ["s.ddd.json"]
        plan = add_entry(
            SECTIONS, built, found, ".fresh", {"access": '"read-write"', "alignment": "8"}, cache
        )
        assert plan == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "s.ddd.json").resolve(),
                    (
                        Operation(
                            "insert",
                            "sections[1]",
                            '{"section": ".fresh", "access": "read-write", "alignment": 8}',
                        ),
                    ),
                ),
            )
        )

    def test_a_project_with_no_sections_file_gets_one_named_for_what_it_holds(
        self, tmp_path: Path
    ) -> None:
        """What `filename` is for, and the only arm that reads it: the appending test above would
        pass with any spelling of it. Both edits in one plan, so a project can never list a file
        that was not written, and the whole created text is asserted rather than sampled - it is
        the one place `filename`, `containers[0]` and `name_key` are all three visible at once."""
        built = _index(tmp_path, {"a.ddd.json": component("A", declare("output", "Gain"))})
        cache: dict[Path, Document] = {}
        found = project_of(SECTIONS, tmp_path / "p.ddd.json", (), cache)
        assert found.files == ()
        plan = add_entry(
            SECTIONS, built, found, ".fresh", {"access": '"read-write"', "alignment": "8"}, cache
        )
        assert [(edit.path.name, edit.creates) for edit in plan.edits] == [
            ("p.ddd.json", False),
            ("sections.ddd.json", True),
        ]
        assert plan.edits[0].operations == (
            Operation("insert", "project.includes[1]", '"sections.ddd.json"'),
        )
        assert plan.edits[1].operations[0].raw == (
            '{\n  "sections": [\n'
            '    { "section": ".fresh", "access": "read-write", "alignment": 8 }\n'
            "  ]\n}\n"
        )

    def test_a_rename_reaches_the_entry_and_every_definition_placing_data_in_it(
        self, tmp_path: Path
    ) -> None:
        """What the assertion above only counts. A rename that reached the entry and not the
        placements would leave every definition naming a section nothing declares - an
        `unknown-section` apiece, in files the reader was not looking at."""
        built, _root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        assert rename_entry(SECTIONS, built, ".calib", ".nvm", cache) == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "a.ddd.json").resolve(),
                    (Operation("set", "component.interface[0].definition.section", _raw(".nvm")),),
                ),
                PlannedEdit(
                    (tmp_path / "s.ddd.json").resolve(),
                    (Operation("set", "sections[0].section", _raw(".nvm")),),
                ),
            )
        )


# The third vocabulary, in the spelling `tests/test_lsp.py` and `tests/test_project_shared.py`
# both hold: copied by hand for the reason `TWO_HOMES` above is. A rasters file declaring `10ms`,
# a component naming it as its own default, and a definition naming it too.
TIMED = {
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}

# Two rasters, for the refusals a project with a single raster cannot reach: an event another
# raster already claims, and a name another one already declares. Copied by hand from
# `tests/test_lsp.py`'s own `TWO_RASTERS`, which is the only other place it is written.
TWO_RASTERS = {
    "r.ddd.json": {
        "rasters": [
            {"raster": "10ms", "event": 1, "cycle": "10ms"},
            {"raster": "20ms", "event": 2, "cycle": "20ms"},
        ]
    },
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}


class TestRasterRefusals:
    # The whole sentence per case, written out rather than built from `RASTERS.judge`, because a
    # tail read back off the descriptor would agree with itself however it were reworded. Each is
    # the string this checkout actually produces, pasted from a run of `_judged`.
    _EVENT_TAIL = "a channel number xcp addresses - 0 to 65535 - written without a decimal point"
    _CYCLE_TAIL = (
        "a count of 1 to 255 times a decade from 1ns to 1s, written as one string - "
        "'1500us', '10ms'. A raster that is not cyclic states no cycle at all: the key is left "
        "out of its entry, which no value set here can do"
    )

    @pytest.mark.parametrize(
        ("key", "raw", "says"),
        [
            pytest.param(
                "event",
                "-1",
                "-1 is not an event a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_EVENT_TAIL}",
                id="event-below-zero",
            ),
            pytest.param(
                "event",
                "1e3",
                "1e3 is not an event a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_EVENT_TAIL}",
                id="event-with-an-exponent",
            ),
            pytest.param(
                "cycle",
                "4",
                "4 is not a cycle a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_CYCLE_TAIL}",
                id="cycle-that-is-no-string",
            ),
            pytest.param(
                "cycle",
                '"1234ms"',
                "\"1234ms\" is not a cycle a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_CYCLE_TAIL}",
                id="cycle-xcp-cannot-carry",
            ),
            pytest.param(
                "cycle",
                '"potato"',
                "\"potato\" is not a cycle a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_CYCLE_TAIL}",
                id="cycle-that-is-no-period",
            ),
            pytest.param(
                "cycle",
                '""',
                "\"\" is not a cycle a raster may state, so '10ms' cannot take it in "
                f"r.ddd.json: {_CYCLE_TAIL}",
                id="cycle-cleared",
            ),
            pytest.param(
                "description",
                "123",
                "123 is not a description a raster may state, so '10ms' cannot take it in "
                "r.ddd.json: a json string",
                id="description-that-is-no-string",
            ),
        ],
    )
    def test_a_value_the_model_would_refuse_is_refused_here(
        self, tmp_path: Path, key: str, raw: str, says: str
    ) -> None:
        """Every one of them measured against `RasterDeclaration` on this checkout, and three of
        them are why both judges wrap the whole model rather than a field's annotation. `1e3` is
        the float `1000.0`, which the published schema accepts and `strict=True` on the field
        refuses - `TypeAdapter(int)` would have coerced it to `1000` and waved it through.
        `"1234ms"` and `"potato"` are strings, so `TypeAdapter(str | None)` would take both, and
        the rule that refuses them is `_cycle_is_a_period_xcp_carries`, a model validator no
        adapter over the annotation can reach. Written, the file stops loading and every tab
        empties over one keystroke in this one.

        The *whole* sentence is asserted, not the code and the file name. A `Judgement` is two
        values and only the adapter was pinned: with all three tails replaced by `XXROTXX` the
        suite passed, because the tail is everything after the colon and nothing read it. That is
        how `cycle`'s shipped as `a json string, or nothing` - which is what `"potato"` already
        is, so the one actionable sentence a reader with a mistyped period ever sees told them to
        write what they had just written. The `cycle-cleared` row is the same defect's second
        half, and is why `""` is here beside `"potato"`: the corrected tail kept its `or nothing`,
        and clearing the field - which sends `""`, not the `raw=None` that would take the key
        out - is the commoner keystroke of the two, so the refusal still ended by offering the
        reader what they had just asked for and been refused. Sections escape by accident, their
        clauses being pinned at the http layer by
        `test_a_change_the_project_refuses_says_why_in_the_format_s_own_words`;
        these rows were written while rasters had no route at all, standing in for the http test
        that Task 5 has since added - `TestRaster`'s own copy of that name, which asserts the same
        three tails through `GET /api/raster-plan`. Kept rather than folded into it: a plan refused
        here needs no endpoint to be asked, and one layer pinning a sentence is what the other
        layer's rewording has to get past."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", key, raw, cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == says

    def test_an_event_the_model_takes_is_planned(self, tmp_path: Path) -> None:
        """The other arm of `_EVENT`, and the one that pins the placeholder `_evented` builds its
        entry with: were its `raster` a name the model refuses, every event would be refused too
        and the two `event` cases above would still pass. It also pins that the placeholder leaves
        `cycle` out - stated as anything the period rule dislikes, this legal event would be
        refused by a rule about a key nobody set."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        assert set_entry(RASTERS, built, "10ms", "event", "2", cache) == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "r.ddd.json").resolve(),
                    (Operation("set", "rasters[0].event", "2"),),
                ),
            )
        )

    @pytest.mark.parametrize("raw", ['"1500us"', "null"])
    def test_a_cycle_the_model_takes_is_planned(self, tmp_path: Path, raw: str) -> None:
        """The other arm of `_CYCLE`, pinning `_cycled`'s placeholders the same way: an `event` the
        model refused would refuse every cycle. `1500us` is a period XCP carries where `1234ms` is
        not, so this is the rule itself and not merely "a string". `null` is a real value rather
        than an omission - `cycle` is `str | None`, and an event that is not cyclic says so."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        assert set_entry(RASTERS, built, "10ms", "cycle", raw, cache) == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "r.ddd.json").resolve(),
                    (Operation("set", "rasters[0].cycle", raw),),
                ),
            )
        )

    def test_an_event_another_raster_claims_is_refused(self, tmp_path: Path) -> None:
        """Spec §4: `duplicate-event` is a check, not a schema error, so the file would load and
        the project would be wrong in a way only the analysis names. The reader can pick another
        channel, so the interface refuses."""
        built, _root = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", "event", "2", cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == "event 2 is already claimed by raster '20ms'"

    def test_a_raster_keeping_the_event_it_already_claims_is_not_refused(
        self, tmp_path: Path
    ) -> None:
        """A panel asks for a plan on every keystroke. Without the entry, a reader re-typing the
        `1` their own raster claims would be told it is taken - by themselves."""
        built, _root = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        assert set_entry(RASTERS, built, "10ms", "event", "1", cache).edits

    def test_declaring_a_raster_on_an_event_another_claims_is_refused(self, tmp_path: Path) -> None:
        """The same collision through the other verb. `add_entry` judges every raw it is given;
        asking `taken` in the set path alone would leave it saying nothing about what the project
        already claims, so the interface would refuse an event on edit and write it on create -
        the reader reaching the same wrong project by the longer route. The entry is `None` here,
        there being no entry yet for one to be exempt from."""
        built, _root = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        found = project_of(RASTERS, tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_entry(RASTERS, built, found, "5ms", {"event": "2"}, cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == "event 2 is already claimed by raster '20ms'"

    def test_a_raster_whose_file_has_dropped_its_event_since_claims_none(
        self, tmp_path: Path
    ) -> None:
        """The index recorded where the analysis read the declaration, and the file has changed
        since - the drift `_raster_uses` and `rename_edits` both already handle. `Index.rasters`
        holds a name and a site, never the event, so what each raster claims is read from the
        entry's own text, which here no longer states one. Unguarded, `json.loads("")` raises out
        of a plan the panel asked for on a keystroke; a declaration that states no event claims
        none, and the next revision says what it claims instead."""
        built, _root = built_of(tmp_path, **TWO_RASTERS)
        write_tree(
            tmp_path,
            {
                "r.ddd.json": {
                    "rasters": [
                        {"raster": "10ms", "event": 1, "cycle": "10ms"},
                        {"raster": "20ms", "cycle": "20ms"},
                    ]
                }
            },
        )
        cache: dict[Path, Document] = {}
        assert set_entry(RASTERS, built, "10ms", "event", "2", cache).edits

    def test_the_event_may_not_be_taken_away(self, tmp_path: Path) -> None:
        """`RASTERS.required`, deliberately and not as a side effect: a descriptor's field values
        are data, and the coverage gate cannot see data. Emptied, `set_entry` plans
        `Operation("remove", "rasters[0].event")`, the file stops validating - `event` has no
        default - and every tab in the page empties over one keystroke in this one."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", "event", None, cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == (
            "a raster states an event, so '10ms' cannot be left without one in r.ddd.json"
        )

    def test_a_key_a_raster_has_not_names_the_three_keys_it_states(self, tmp_path: Path) -> None:
        """What `RASTERS.keys` is for, asserted as the whole sentence so that dropping any one of
        the three fails here. The second vocabulary with three keys, so `_listed`'s three word arm
        is exercised by a second set of words. `event` is a third key across the vocabularies to
        begin with a vowel, and its article is pinned by the test above rather than by this one -
        `raster` begins with a consonant, so the article here is `a` either way."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", "value", "1", cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == (
            "a raster has no 'value' to set in r.ddd.json: it states cycle, description and event"
        )

    def test_a_name_another_raster_already_declares_is_refused(self, tmp_path: Path) -> None:
        """What `RASTERS.taken["raster"]` is for. Refused rather than reported, though the file
        would still load: `duplicate-raster` is a check and not a schema error, but each raster
        carries its own event and cycle, so merging two would silently sample one signal on
        another's channel."""
        built, _root = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_entry(RASTERS, built, "10ms", "20ms", cache)
        assert raised.value.code == "invalid"
        assert raised.value.message == "'20ms' is already a raster this project declares"

    def test_a_raster_may_be_renamed_to_a_name_no_c_identifier_allows(self, tmp_path: Path) -> None:
        # Which arm of `rename_problem` the judge asks, and the only test that can tell it by the
        # outcome: `1ms` opens with a digit, so the c identifier rule the constants judge answers
        # to would refuse it outright, and a raster's name is the short name of its XCP event
        # rather than an identifier. The refusal test above would notice the swap too, but only
        # because it asserts the whole sentence - a judge sent to the wrong arm still refuses
        # `20ms`, just for the wrong reason and in the wrong words.
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        assert rename_entry(RASTERS, built, "10ms", "1ms", cache).edits

    def test_a_new_raster_is_appended_to_the_file_the_project_keeps_them_in(
        self, tmp_path: Path
    ) -> None:
        """What `containers`, `name_key` and the *order* of `keys` are for - all three strings in
        the descriptor, which no coverage gate can see. `("bogus",)` would leave `files` empty and
        answer a plan creating a second rasters file beside the project description; `"name"` would
        declare `{"name": "5ms", ...}`, which `extra="forbid"` rejects, so the file this wrote
        would no longer load. The three values land in `keys`'s own order, which is the order the
        panel draws them in."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        found = project_of(RASTERS, tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.files] == ["r.ddd.json"]
        plan = add_entry(
            RASTERS,
            built,
            found,
            "5ms",
            {"description": '"fast task"', "event": "3", "cycle": '"5ms"'},
            cache,
        )
        assert plan == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "r.ddd.json").resolve(),
                    (
                        Operation(
                            "insert",
                            "rasters[1]",
                            '{"raster": "5ms", "event": 3, "cycle": "5ms", '
                            '"description": "fast task"}',
                        ),
                    ),
                ),
            )
        )

    def test_a_project_with_no_rasters_file_gets_one_named_for_what_it_holds(
        self, tmp_path: Path
    ) -> None:
        """What `filename` is for, and the only arm that reads it: the appending test above would
        pass with any spelling of it. Both edits in one plan, so a project can never list a file
        that was not written."""
        built = _index(tmp_path, {"a.ddd.json": component("A", declare("output", "Gain"))})
        cache: dict[Path, Document] = {}
        found = project_of(RASTERS, tmp_path / "p.ddd.json", (), cache)
        assert found.files == ()
        plan = add_entry(RASTERS, built, found, "5ms", {"event": "3"}, cache)
        assert [(edit.path.name, edit.creates) for edit in plan.edits] == [
            ("p.ddd.json", False),
            ("rasters.ddd.json", True),
        ]
        assert plan.edits[0].operations == (
            Operation("insert", "project.includes[1]", '"rasters.ddd.json"'),
        )
        assert plan.edits[1].operations[0].raw == (
            '{\n  "rasters": [\n    { "raster": "5ms", "event": 3 }\n  ]\n}\n'
        )

    def test_a_rename_reaches_the_entry_the_component_and_the_definition(
        self, tmp_path: Path
    ) -> None:
        """What `kind` is for: `rename_sites` is asked for it by name. A rename that reached the
        entry and not the two shapes naming it would leave both naming a raster nothing declares -
        an `unknown-raster` apiece, in a file the reader was not looking at. A component's own
        default is a shape neither of the other two vocabularies has."""
        built, _root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        assert rename_entry(RASTERS, built, "10ms", "5ms", cache) == SharedPlan(
            (
                PlannedEdit(
                    (tmp_path / "a.ddd.json").resolve(),
                    (
                        Operation("set", "component.raster", _raw("5ms")),
                        Operation("set", "component.interface[0].definition.raster", _raw("5ms")),
                    ),
                ),
                PlannedEdit(
                    (tmp_path / "r.ddd.json").resolve(),
                    (Operation("set", "rasters[0].raster", _raw("5ms")),),
                ),
            )
        )
