"""One variable as the unit panel of ddd gui shows it, and what settling one of its keys takes."""

from __future__ import annotations

import difflib
import json
import random
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    FLOAT_BESIDE_ENUM,
    STRING_TYPE_BESIDE_SCALAR,
    TEXT,
    UNIT_BESIDE_TEXT,
    component,
    declare,
    project,
    scalar_type,
    types,
    write_tree,
)
from ddd import variables
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.editing import UNREADABLE, EditError, Operation, TextEdit, edit_text, fingerprint
from ddd.loading import load_workspace
from ddd.lsp.edits import Settlement, Unsettled, settle
from ddd.lsp.navigation import Index, Site, index
from ddd.lsp.ranges import Document, read
from ddd.variables import (
    Hunk,
    declarations_of,
    hunks,
    lines_replaced,
    located_on,
    planned,
    preview,
    refusal,
    units_in_use,
    unloadable,
    vocabulary_of,
)

DEFINITION = "component.interface[0].definition"
UNIT = f"{DEFINITION}.unit"


def built(tmp_path: Path, **files: Any) -> Index:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def speed(tmp_path: Path, reader_unit: str = "%") -> Index:
    return built(
        tmp_path,
        **{
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit=reader_unit)),
        },
    )


def stamps(tmp_path: Path, *names: str) -> dict[Path, str]:
    return {
        (tmp_path / name).resolve(): fingerprint((tmp_path / name).read_bytes()) for name in names
    }


class TestDeclarations:
    def test_every_declaration_is_listed_with_its_component_and_role(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        assert [(entry.component, entry.role) for entry in found] == [
            ("A", "produces"),
            ("B", "reads"),
        ]
        assert found[1].stated["unit"] == '"%"'
        assert found[1].stated["kind"] == '"measurement"'
        assert "typename" not in found[1].stated
        assert (found[1].type_name, dict(found[1].fixed)) == (None, {})

    def test_a_local_declaration_is_local(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("local", "Speed", unit="rpm"))}
        )
        assert [entry.role for entry in declarations_of(idx, "Speed", {})] == ["local"]

    def test_a_declaration_naming_a_type_carries_what_the_type_fixes(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
            },
        )
        (entry,) = declarations_of(idx, "Speed", {})
        assert entry.type_name == "Speed_t"
        assert entry.fixed["unit"] == '"rpm"'
        assert entry.fixed["datatype"] == '"uint16"'
        assert "limits" not in entry.fixed

    def test_a_type_the_project_does_not_declare_fixes_nothing(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", typename="Nowhere_t"))},
        )
        (entry,) = declarations_of(idx, "Speed", {})
        assert (entry.type_name, dict(entry.fixed)) == ("Nowhere_t", {})

    def test_a_declaration_its_file_no_longer_holds_is_left_out(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "Torque"))})
        assert [entry.component for entry in declarations_of(idx, "Speed", {})] == ["A"]

    def test_a_file_rewritten_without_a_name_or_a_scope_is_named_by_its_file(
        self, tmp_path: Path
    ) -> None:
        idx = speed(tmp_path)
        rewritten = {"component": {"interface": [{"definition": {"name": "Speed"}}]}}
        write_tree(tmp_path, {"b.ddd.json": rewritten})
        assert [(entry.component, entry.role) for entry in declarations_of(idx, "Speed", {})] == [
            ("A", "produces"),
            ("b", "reads"),
        ]


class TestFindings:
    def finding(self, path: Path, pointer: str | None) -> Diagnostic:
        location = None if pointer is None else Location(path, pointer)
        return Diagnostic("definition-mismatch", Severity.ERROR, "differs", location)

    def test_a_finding_on_a_declaration_or_under_it_is_located_on_it(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        b = tmp_path / "b.ddd.json"
        assert located_on(found, b, self.finding(b, "component.interface[0]"))
        assert located_on(found, b, self.finding(b, UNIT))
        assert located_on(found, b, self.finding(b, "component.interface[0][1]"))

    def test_a_finding_elsewhere_is_not(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        b = tmp_path / "b.ddd.json"
        assert not located_on(found, b, self.finding(b, "component.interface[1]"))
        assert not located_on(found, b, self.finding(b, "component.interface[10]"))
        assert not located_on(found, tmp_path / "p.ddd.json", self.finding(b, UNIT))
        assert not located_on(found, b, self.finding(b, None))


class TestUnits:
    def test_the_units_in_use_are_counted_by_variable_most_used_first(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("output", "Torque", unit="Nm"),
                    declare("output", "Idle", unit="rpm"),
                    declare("output", "Plain", unit=""),
                    declare("output", "Bare"),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert units_in_use(idx) == (("rpm", 2), ("Nm", 1))

    def test_without_a_units_file_the_vocabulary_is_none(self) -> None:
        assert vocabulary_of([]) is None

    def test_a_vocabulary_lists_its_units_with_their_descriptions(self) -> None:
        declared = Document(
            json.dumps(
                {
                    "units": [
                        "rpm",
                        {"unit": "Nm", "description": "torque"},
                        {"unit": "degC", "description": 3},
                        {"description": "no unit here"},
                        7,
                    ]
                }
            )
        )
        broken = Document(json.dumps({"units": "rpm"}))
        assert vocabulary_of([declared, broken]) == (
            ("rpm", None),
            ("Nm", "torque"),
            ("degC", None),
        )


class TestPreview:
    def test_a_preview_is_the_edit_and_the_lines_it_changes(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        b = tmp_path / "b.ddd.json"
        before = b.read_bytes()
        (planned,) = preview(
            settle(idx, "Speed", "unit", '"rpm"', {}), "unit", stamps(tmp_path, "b.ddd.json")
        )
        lines = before.decode("utf-8").splitlines()
        line = next(number for number, text in enumerate(lines, 1) if '"unit": "%"' in text)
        assert planned.path.name == "b.ddd.json"
        assert planned.fingerprint == fingerprint(before)
        assert planned.operations == (Operation("set", UNIT, '"rpm"'),)
        assert planned.hunks == (
            Hunk(line, (lines[line - 1],), (lines[line - 1].replace('"%"', '"rpm"'),)),
        )
        assert b.read_bytes() == before

    def test_taking_a_key_out_is_a_removal(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        planned = preview(
            settle(idx, "Speed", "unit", None, {}),
            "unit",
            stamps(tmp_path, "a.ddd.json", "b.ddd.json"),
        )
        assert [(entry.path.name, entry.operations) for entry in planned] == [
            ("a.ddd.json", (Operation("remove", UNIT),)),
            ("b.ddd.json", (Operation("remove", UNIT),)),
        ]
        assert all(not any("unit" in text for text in entry.hunks[0].after) for entry in planned)

    def test_a_file_the_analysis_did_not_read_is_unreadable(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        with pytest.raises(EditError) as refused:
            preview(settle(idx, "Speed", "unit", '"rpm"', {}), "unit", {})
        assert refused.value.code == UNREADABLE

    @pytest.mark.parametrize("damage", ["remove", "latin-1"])
    def test_a_file_that_can_no_longer_be_read_as_utf8_is_unreadable(
        self, tmp_path: Path, damage: str
    ) -> None:
        idx = speed(tmp_path)
        settlement = settle(idx, "Speed", "unit", '"rpm"', {})
        known = stamps(tmp_path, "b.ddd.json")
        b = tmp_path / "b.ddd.json"
        if damage == "remove":
            b.unlink()
        else:
            b.write_bytes(b"\xff\xfe not utf-8")
        with pytest.raises(EditError) as refused:
            preview(settlement, "unit", known)
        assert refused.value.code == UNREADABLE


class TestRefusal:
    @pytest.mark.parametrize(
        ("reason", "code", "says"),
        [
            ("type", "fixed-by-type", "names the type 'Speed_t', which fixes its unit"),
            ("kind", "invalid", "is of a kind that does not allow that unit"),
            (
                "storage",
                "invalid",
                "would not load with that unit: storage is named exactly once, and a "
                "'datatype' comes with a 'conversion'",
            ),
            (
                "load",
                "invalid",
                "would not load with that unit: a string has no unit",
            ),
            ("unreachable", "unreadable", "is no longer where the last analysis found it"),
        ],
    )
    def test_each_reason_has_its_code_and_names_the_declaration(
        self, reason: Any, code: str, says: str
    ) -> None:
        refused = Unsettled(
            Site(Path("/w/b.ddd.json"), DEFINITION), reason, "Speed_t", "a string has no unit"
        )
        assert refusal(refused, "Speed", "unit") == (
            code,
            f"the declaration of 'Speed' in b.ddd.json {says}",
        )

    def test_a_variable_nobody_produces_is_refused_limits_nobody_states(self) -> None:
        """3:I2. Not one declaration's fault but the variable's: every one reads it, and a reader
        leaves its limits to the declaration producing it, which none does."""
        refused = Unsettled(Site(Path("/w/b.ddd.json"), DEFINITION), "unproduced")
        assert refusal(refused, "Speed", "limits") == (
            "invalid",
            "no declaration of 'Speed' produces it, and a declaration reading it leaves its "
            "limits to the one that does",
        )


class TestUnloadable:
    """What the panel says of a settlement its reader chose, which a button's is withheld for."""

    def test_a_declaration_the_settlement_leaves_unloadable_is_said_to_be_one(
        self, tmp_path: Path
    ) -> None:
        idx = built(tmp_path, **FLOAT_BESIDE_ENUM)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "datatype", '"float32"', cache, withholding=False)
        assert unloadable(settlement, "V", "datatype", cache) == (
            "the declaration of 'V' in r.ddd.json would not load with that datatype: "
            "enum conversion 'Mode_t' requires an integer datatype, got 'float32'",
        )

    def test_a_settlement_that_leaves_every_declaration_loading_says_nothing(
        self, tmp_path: Path
    ) -> None:
        idx = built(tmp_path, **FLOAT_BESIDE_ENUM)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "conversion", '{"kind": "identity"}', cache)
        assert settlement.changes
        assert unloadable(settlement, "V", "conversion", cache) == ()

    def test_only_the_declarations_that_would_not_load_are_said(self, tmp_path: Path) -> None:
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint16")),
            "r1.ddd.json": component("R1", declare("input", "V", "uint32")),
            "r2.ddd.json": component(
                "R2", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
        }
        idx = built(tmp_path, **files)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "datatype", '"uint16"', cache, withholding=False)
        assert [change.site.path.name for change in settlement.changes] == [
            "r1.ddd.json",
            "r2.ddd.json",
        ]
        assert unloadable(settlement, "V", "datatype", cache) == (
            "the declaration of 'V' in r2.ddd.json would not load with that datatype: "
            "a string conversion needs a byte datatype, uint8 or sint8, got 'uint16'",
        )

    def test_the_sentences_follow_the_files_by_path(self, tmp_path: Path) -> None:
        """The project lists its components in the order it includes them, which is not the order
        the plan's own files are drawn in: sorted by path, as the preview's are."""
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint16")),
            "r2.ddd.json": component(
                "R2", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
            "r1.ddd.json": component(
                "R1", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
        }
        idx = built(tmp_path, **files)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "datatype", '"uint16"', cache, withholding=False)
        why = "a string conversion needs a byte datatype, uint8 or sint8, got 'uint16'"
        assert unloadable(settlement, "V", "datatype", cache) == (
            f"the declaration of 'V' in r1.ddd.json would not load with that datatype: {why}",
            f"the declaration of 'V' in r2.ddd.json would not load with that datatype: {why}",
        )

    def test_taking_a_key_out_is_said_as_writing_one_is(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **UNIT_BESIDE_TEXT)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "dimensions", None, cache, withholding=False)
        (said,) = unloadable(settlement, "V", "dimensions", cache)
        assert said.startswith(
            "the declaration of 'V' in r.ddd.json would not load with that dimensions: "
            "a string states exactly one dimension"
        )

    def test_the_type_a_declaration_names_is_asked_where_the_project_is_given(
        self, tmp_path: Path
    ) -> None:
        """A reader naming a string type states one dimension, and settling none takes it: the
        models take that, and the analysis does not - with the types of the project beside it."""
        from ddd.lsp.edits import type_conversions

        idx = built(tmp_path, **STRING_TYPE_BESIDE_SCALAR)
        cache: dict[Path, Document] = {}
        settlement = settle(idx, "V", "dimensions", None, cache, withholding=False)
        assert unloadable(settlement, "V", "dimensions", cache) == ()
        assert unloadable(
            settlement, "V", "dimensions", cache, types=type_conversions(idx, cache)
        ) == (
            "the declaration of 'V' in r.ddd.json would not load with that dimensions: "
            "'V' is declared as 'Text_t', which is a string: a string states exactly one "
            "dimension, its length in bytes, got none; an array of strings is written as an "
            "array of structures with a string member",
        )


def test_a_settlement_with_nothing_to_change_previews_nothing() -> None:
    assert preview(Settlement((), ()), "unit", {}) == ()


# ``hunks`` as it stood before it answered a change made in place without difflib, verbatim but
# for its name: the oracle of the tests below. Kept because ``hunks`` claims to answer what this
# answers, difflib over the whole of both texts, on every pair of texts.


def _reference_hunks(before: str, after: str) -> tuple[Hunk, ...]:
    """The lines a change replaces in a text, each run of them numbered as the text stood."""
    old, new = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return tuple(
        Hunk(first + 1, tuple(old[first:last]), tuple(new[start:end]))
        for tag, first, last, start, end in matcher.get_opcodes()
        if tag != "equal"
    )


BASE = (
    json.dumps(
        component(
            "A",
            *(declare("output", f"S{k}", unit=("rpm", "Nm", "kPa")[k % 3]) for k in range(6)),
        ),
        indent=2,
    )
    + "\n"
)
"""Six declarations of one component, written out as a description file is: their lines are
spelled alike but for each declaration's name and unit."""

LINES = BASE.splitlines()


def text_of(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def replaced(**lines: str) -> str:
    """``BASE`` with each line ``_<number>`` - counted from 1 - replaced by the text given."""
    changed = list(LINES)
    for spelled, text in lines.items():
        changed[int(spelled.removeprefix("_")) - 1] = text
    return text_of(changed)


class TestHunks:
    """``hunks`` answers what difflib answers over the whole of both texts: each case is compared
    with ``_reference_hunks``, and the cases a change in place answers are written out too."""

    @pytest.mark.parametrize(
        ("after", "expected"),
        [
            (replaced(_1="[{"), (Hunk(1, ("{",), ("[{",)),)),
            (replaced(**{f"_{len(LINES)}": "}]"}), (Hunk(len(LINES), ("}",), ("}]",)),)),
            (
                replaced(_34='          "name": "Speed",'),
                (Hunk(34, ('          "name": "S2",',), ('          "name": "Speed",',)),),
            ),
            (
                replaced(_8='          "name": "Engine",', _60='          "name": "Pump",'),
                (
                    Hunk(8, ('          "name": "S0",',), ('          "name": "Engine",',)),
                    Hunk(60, ('          "name": "S4",',), ('          "name": "Pump",',)),
                ),
            ),
            (
                replaced(_3='    "name": "Bench",', _4='    "declarations": ['),
                (
                    Hunk(
                        3,
                        ('    "name": "A",', '    "interface": ['),
                        ('    "name": "Bench",', '    "declarations": ['),
                    ),
                ),
            ),
            (
                replaced(_15='          "unit": "Hz"', _54='          "unit": "Hz"'),
                (
                    Hunk(15, ('          "unit": "rpm"',), ('          "unit": "Hz"',)),
                    Hunk(54, ('          "unit": "rpm"',), ('          "unit": "Hz"',)),
                ),
            ),
            (
                text_of([f"other {line}" for line in LINES]),
                (Hunk(1, tuple(LINES), tuple(f"other {line}" for line in LINES)),),
            ),
            (BASE, ()),
        ],
        ids=[
            "the-first-line",
            "the-last-line",
            "a-line-in-the-middle",
            "two-separate-lines",
            "two-lines-together",
            "a-unit-renamed-everywhere",
            "nothing-in-common-as-long",
            "nothing-changed",
        ],
    )
    def test_a_change_in_place_is_answered_without_difflib(
        self, after: str, expected: tuple[Hunk, ...], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each line changed is replaced by one the old text holds nowhere, and is itself held
        nowhere in the new text - as renaming a unit everywhere, to a spelling nothing uses,
        replaces its every statement.
        Before, difflib took 0.95 of the 0.97 ms ``hunks`` took over one such file - a component
        of 455 lines of a generated project, one unit renamed in it, the best of nine rounds of
        two hundred calls each - on the Linux development PC."""
        reference = _reference_hunks(BASE, after)

        def refused(*arguments: object, **keywords: object) -> None:
            raise AssertionError("difflib was asked")

        monkeypatch.setattr(difflib, "SequenceMatcher", refused)
        assert hunks(BASE, after) == expected == reference

    @pytest.mark.parametrize(
        "after",
        [
            # A line inserted.
            text_of([*LINES[:9], '          "description": "a speed",', *LINES[9:]]),
            # The first declaration taken out: thirteen lines, most of them spelled as the next
            # declaration's are, which difflib numbers from line 5 - matching the shared head and
            # tail first would number them from line 8.
            text_of([*LINES[:4], *LINES[17:]]),
            # A line taken out, at the end.
            text_of(LINES[:-1]),
            # Nothing in common, and not as long.
            text_of([f"other {line}" for line in LINES[:20]]),
            # A unit replaced by one another declaration states, as merging two spellings does.
            replaced(_15='          "unit": "Nm"'),
            # A unit replaced while another declaration still states it.
            replaced(_15='          "unit": "Hz"'),
            # A file created, and one emptied.
            "",
        ],
        ids=[
            "an-insertion",
            "a-removal",
            "a-removal-at-the-end",
            "nothing-in-common-and-shorter",
            "into-a-line-held-elsewhere",
            "out-of-a-line-held-elsewhere",
            "emptied",
        ],
    )
    def test_any_other_change_is_numbered_as_difflib_numbers_it(self, after: str) -> None:
        assert hunks(BASE, after) == _reference_hunks(BASE, after)
        assert hunks(after, BASE) == _reference_hunks(after, BASE)

    @pytest.mark.parametrize(
        ("before", "after", "expected"),
        [
            ("X\nX\n", "Y\nX\n", (Hunk(1, (), ("Y",)), Hunk(2, ("X",), ()))),
            ("A\nB\n", "B\nB\n", (Hunk(1, ("A",), ()), Hunk(3, (), ("B",)))),
        ],
        ids=["the-line-taken-out-held-in-the-new-text", "the-line-put-in-held-in-the-old-text"],
    )
    def test_a_line_matched_elsewhere_is_not_answered_in_place(
        self, before: str, after: str, expected: tuple[Hunk, ...]
    ) -> None:
        """Why a change in place takes out only lines the new text holds nowhere and puts in only
        lines the old text holds nowhere: each of these replaces one line where it stands, and
        difflib matches the line taken out, or the one put in, at another place."""
        assert hunks(before, after) == expected == _reference_hunks(before, after)

    def test_the_removal_is_numbered_from_where_difflib_numbers_it(self) -> None:
        """Written out: the case above where the shared head and tail would have moved it."""
        assert hunks(BASE, text_of([*LINES[:4], *LINES[17:]])) == (Hunk(5, tuple(LINES[4:17]), ()),)

    def test_random_changes_are_numbered_as_difflib_numbers_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lines replaced, inserted and taken out at random among a few spellings, some of them
        new: every answer is difflib's, made in place or by difflib itself."""
        generator = random.Random(11)
        asked = []
        matcher = difflib.SequenceMatcher

        def counted(*arguments: Any, **keywords: Any) -> difflib.SequenceMatcher[str]:
            asked.append(1)
            return matcher(*arguments, **keywords)

        cases = 3_000
        for case in range(cases):
            spellings = [f"line {index}" for index in range(generator.randint(1, 5))]
            old = [generator.choice(spellings) for _ in range(generator.randint(0, 12))]
            new = list(old)
            for _ in range(generator.randint(0, 4)):
                fresh = [*spellings, f"new {case}", f"new {case} again"]
                roll = generator.random()
                if roll < 0.6 and new:
                    new[generator.randrange(len(new))] = generator.choice(fresh)
                elif roll < 0.8:
                    new.insert(generator.randint(0, len(new)), generator.choice(fresh))
                elif new:
                    del new[generator.randrange(len(new))]
            expected = _reference_hunks(text_of(old), text_of(new))
            monkeypatch.setattr(difflib, "SequenceMatcher", counted)
            assert hunks(text_of(old), text_of(new)) == expected
            monkeypatch.setattr(difflib, "SequenceMatcher", matcher)
        assert 0 < len(asked) < cases


UNITS_FILE = json.dumps({"units": ["rpm", "Nm", "kPa", "degC"]}, indent=2) + "\n"
"""A units file listing four units, one to a line."""

DECLARATION = json.dumps(declare("output", "Torque", unit="Nm"))
"""A declaration as a plan adding one writes it: json text, laid out by the engine."""

PLANS = {
    # The plan of a panel picking a unit another declaration of the file states already: the line
    # it writes is held elsewhere in the file, as it is in any file stating a unit twice.
    "a-unit-into-a-line-held-elsewhere": (
        BASE,
        (Operation("set", "component.interface[1].definition.unit", '"rpm"'),),
    ),
    "a-declaration-taken-out": (BASE, (Operation("remove", "component.interface[0]"),)),
    "the-last-declaration-taken-out": (BASE, (Operation("remove", "component.interface[5]"),)),
    "a-member-added": (
        BASE,
        (Operation("set", "component.interface[2].definition.description", '"a speed"'),),
    ),
    "a-declaration-added-first": (
        BASE,
        (Operation("insert", "component.interface[0]", DECLARATION),),
    ),
    "a-declaration-added-last": (
        BASE,
        (Operation("insert", "component.interface[6]", DECLARATION),),
    ),
    "a-structure-set-over-lines": (
        BASE,
        (
            Operation(
                "set",
                "component.interface[0].definition.conversion",
                '{"kind": "linear", "factor": 2, "offset": 0}',
            ),
        ),
    ),
    # A merge of two spellings takes the entries listing the old one out, the furthest down first,
    # each made on the text the one before left.
    "entries-taken-out-in-turn": (
        UNITS_FILE,
        (Operation("remove", "units[2]"), Operation("remove", "units[0]")),
    ),
}
"""Plans of one file each, as the routes make them: a set in place, a removal, a member and a
declaration added, a structure written over lines, and operations made one after another."""


def plan_of(tmp_path: Path, text: str, operations: tuple[Operation, ...]) -> Any:
    """``planned`` of ``operations`` over a file holding ``text``, the file stamped as the analysis
    would have stamped it."""
    path = tmp_path / "planned.ddd.json"
    path.write_text(text, encoding="utf-8", newline="")
    return planned(path, operations, {path.resolve(): fingerprint(path.read_bytes())})


class TestAPlansLinesComeFromItsSpans:
    """14:I6. The lines a plan shows are read off the spans its operations replace, which the
    engine knows, rather than found by comparing the whole file before and after: that comparison
    took 6.8 s over the 48,350 lines of the largest component of a generated project of 100,000
    declarations, and the plan of a variable declared there and in a component as large 13.4 s
    (Linux development PC)."""

    @pytest.mark.parametrize(("text", "operations"), PLANS.values(), ids=PLANS.keys())
    def test_no_plan_asks_difflib(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        text: str,
        operations: tuple[Operation, ...],
    ) -> None:
        """Each answers the lines difflib answered for it, its natural reading, without asking
        difflib anything."""
        expected = _reference_hunks(text, edit_text(text, operations))
        assert expected

        def refused(*arguments: object, **keywords: object) -> None:
            raise AssertionError("difflib was asked")

        monkeypatch.setattr(difflib, "SequenceMatcher", refused)
        assert plan_of(tmp_path, text, operations).hunks == expected

    def test_a_unit_written_where_another_line_states_it_is_that_one_line(
        self, tmp_path: Path
    ) -> None:
        operations = PLANS["a-unit-into-a-line-held-elsewhere"][1]
        assert plan_of(tmp_path, BASE, operations).hunks == (
            Hunk(28, ('          "unit": "Nm"',), ('          "unit": "rpm"',)),
        )

    def test_a_declaration_taken_out_is_its_own_lines(self, tmp_path: Path) -> None:
        """The removal reaches into the first line of the declaration after it, which reads the
        same once it is made: that line is the next declaration's, so the lines taken out are
        the first declaration's own, 5 to 17."""
        operations = PLANS["a-declaration-taken-out"][1]
        assert plan_of(tmp_path, BASE, operations).hunks == (Hunk(5, tuple(LINES[4:17]), ()),)

    def test_a_file_a_plan_creates_is_its_whole_text_without_difflib(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ddd.plans import PlannedEdit
        from ddd.project_units import previewed

        def refused(*arguments: object, **keywords: object) -> None:
            raise AssertionError("difflib was asked")

        monkeypatch.setattr(difflib, "SequenceMatcher", refused)
        created = PlannedEdit(
            tmp_path / "units.ddd.json", (Operation("set", "", UNITS_FILE),), True
        )
        (made,) = previewed((created,), {})
        assert (made.fingerprint, made.hunks) == (
            None,
            (Hunk(1, (), tuple(UNITS_FILE.splitlines())),),
        )


@pytest.fixture
def compared(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """How many lines each comparison a plan's lines are found by is handed, both texts' lines
    together: difflib's, the comparison of each line in place, and the comparison of the lines
    at each end of the lines a span lies on, which is the only one a plan makes now."""
    counted: list[int] = []
    matcher = difflib.SequenceMatcher
    in_place = variables._replaced_in_place

    def matching(*arguments: Any, **keywords: Any) -> difflib.SequenceMatcher[str]:
        counted.append(len(keywords["a"]) + len(keywords["b"]))
        return matcher(*arguments, **keywords)

    def placed(old: list[str], new: list[str]) -> tuple[Hunk, ...] | None:
        counted.append(len(old) + len(new))
        return in_place(old, new)

    monkeypatch.setattr(difflib, "SequenceMatcher", matching)
    monkeypatch.setattr(variables, "_replaced_in_place", placed)
    ends = getattr(variables, "_alike_at_the_ends", None)
    if ends is not None:

        def alike(before: Sequence[str], after: Sequence[str]) -> tuple[int, int]:
            counted.append(len(before) + len(after))
            return ends(before, after)

        monkeypatch.setattr(variables, "_alike_at_the_ends", alike)
    return counted


def declarations_unit_by_unit(count: int) -> str:
    """A component of ``count`` output declarations, ``V0`` onwards, stating three units in turn,
    as a description file is written."""
    declared = (declare("output", f"V{n}", unit=("rpm", "Nm", "kPa")[n % 3]) for n in range(count))
    return json.dumps(component("B", *declared), indent=2) + "\n"


CHANGES = {
    "a-unit-spelled-anew": lambda count: (
        Operation("set", f"component.interface[{count // 2}].definition.unit", '"Hz"'),
    ),
    "a-unit-held-elsewhere": lambda count: (
        Operation("set", f"component.interface[{count // 2}].definition.unit", '"rpm"'),
    ),
    "a-declaration-taken-out": lambda count: (
        Operation("remove", f"component.interface[{count // 2}]"),
    ),
}
"""Each change a plan makes in the middle declaration of a component of ``count``."""


class TestTheLinesAPlanComparesStayAroundItsSpans:
    """14:I6. Counted, never timed: the lines a plan's comparisons are handed are those its spans
    lie on, the same few whether the file holds a thousand declarations or four thousand. Before,
    every line of the file was compared - in place, or by difflib."""

    @pytest.mark.parametrize("change", CHANGES.values(), ids=CHANGES.keys())
    def test_however_long_the_file(self, tmp_path: Path, compared: list[int], change: Any) -> None:
        def lines_compared(count: int) -> int:
            compared.clear()
            plan_of(tmp_path, declarations_unit_by_unit(count), change(count))
            return sum(compared)

        small = lines_compared(1_000)
        assert 0 < small == lines_compared(4_000)


class TestTheLinesASpanLiesOn:
    """``lines_replaced``: the lines spans of a text replace, read off the spans alone."""

    TEXT = "one\ntwo\nthree\nfour\nfive\n"
    """Its second line, ``two``, from offset 4 to 7; ``three`` from 8; ``four`` from 14."""

    def test_spans_on_one_line_are_one_run(self) -> None:
        replaced = (TextEdit(4, 5, "T"), TextEdit(6, 7, "O"))
        assert lines_replaced(self.TEXT, replaced) == (Hunk(2, ("two",), ("TwO",)),)

    def test_spans_on_lines_next_to_one_another_are_one_run(self) -> None:
        replaced = (TextEdit(4, 7, "2"), TextEdit(8, 13, "3"))
        assert lines_replaced(self.TEXT, replaced) == (Hunk(2, ("two", "three"), ("2", "3")),)

    def test_spans_a_line_apart_are_two(self) -> None:
        replaced = (TextEdit(4, 7, "2"), TextEdit(14, 18, "4"))
        assert lines_replaced(self.TEXT, replaced) == (
            Hunk(2, ("two",), ("2",)),
            Hunk(4, ("four",), ("4",)),
        )

    def test_a_span_written_as_it_was_changes_no_line(self) -> None:
        assert lines_replaced(self.TEXT, (TextEdit(4, 7, "two"),)) == ()
        assert lines_replaced(self.TEXT, ()) == ()

    def test_a_span_over_lines_is_its_lines_but_those_alike_at_either_end(self) -> None:
        """``three`` stays where it was, and ``two`` and ``four`` are written anew around it:
        one run, from the first line changed to the last."""
        replaced = (TextEdit(4, 18, "TWO\nthree\nFOUR"),)
        assert lines_replaced(self.TEXT, replaced) == (
            Hunk(2, ("two", "three", "four"), ("TWO", "three", "FOUR")),
        )

    def test_lines_put_in_go_before_the_line_they_are_put_in_front_of(self) -> None:
        assert lines_replaced(self.TEXT, (TextEdit(4, 4, "new\n"),)) == (Hunk(2, (), ("new",)),)
        assert lines_replaced(self.TEXT, (TextEdit(3, 3, "\nnew"),)) == (Hunk(2, (), ("new",)),)

    @pytest.mark.parametrize(
        ("text", "replaced", "expected"),
        [
            ("a\nb\n", TextEdit(4, 4, "c\n"), Hunk(3, (), ("c",))),
            ("a\nb", TextEdit(3, 3, "\nc"), Hunk(3, (), ("c",))),
            ("a\nb", TextEdit(2, 3, ""), Hunk(2, ("b",), ())),
            ("", TextEdit(0, 0, "a\nb\n"), Hunk(1, (), ("a", "b"))),
            ("a\nb\n", TextEdit(0, 4, ""), Hunk(1, ("a", "b"), ())),
        ],
        ids=[
            "after-the-last-line-break",
            "after-a-last-line-without-one",
            "a-last-line-without-one-emptied",
            "an-empty-text-given-lines",
            "every-line-taken-out",
        ],
    )
    def test_at_the_ends_of_a_text(self, text: str, replaced: TextEdit, expected: Hunk) -> None:
        assert lines_replaced(text, (replaced,)) == (expected,)

    @pytest.mark.parametrize(
        ("text", "replaced", "expected"),
        [
            ("a\rX\nb", TextEdit(2, 3, ""), Hunk(2, ("X",), ())),
            ("a\r", TextEdit(2, 2, "\nb"), Hunk(2, (), ("b",))),
            ("a\r\nb\r\n", TextEdit(3, 4, "B"), Hunk(2, ("b",), ("B",))),
        ],
        ids=[
            "a-line-feed-left-after-a-carriage-return",
            "a-line-feed-written-after-a-carriage-return",
            "carriage-returns-and-line-feeds",
        ],
    )
    def test_line_breaks_of_two_characters(
        self, text: str, replaced: TextEdit, expected: Hunk
    ) -> None:
        """A carriage return ending a line, and a line feed after it once the span is made, are one
        line break: ``X`` taken out joins its line feed to the line before, and leaves no empty
        line where it was."""
        before, after = text.splitlines(), applied(text, (replaced,)).splitlines()
        assert lines_replaced(text, (replaced,)) == (expected,)
        assert patched(before, (expected,)) == after

    def test_random_spans_of_random_texts(self) -> None:
        """Each answer is a change of the text's lines into the edited text's: its runs in order,
        a line left as it was between each two, no run holding a line alike at either end of
        both sides, and no more runs than spans. Where every span lies within one line and writes
        no line break, the answer is the lines changed in place, run by run."""
        generator = random.Random(17)
        pieces = ("a", "b", "ab", " ", "\n", "\r\n", "\r", "\N{LINE SEPARATOR}")
        in_place = 0
        for _ in range(3_000):
            text = "".join(generator.choice(pieces) for _ in range(generator.randint(0, 30)))
            ends = sorted(
                generator.randint(0, len(text)) for _ in range(2 * generator.randint(0, 4))
            )
            replaced = tuple(
                TextEdit(
                    start,
                    end,
                    "".join(generator.choice(pieces) for _ in range(generator.randint(0, 3))),
                )
                for start, end in zip(ends[::2], ends[1::2], strict=True)
            )
            before, after = text.splitlines(), applied(text, replaced).splitlines()
            answered = lines_replaced(text, replaced)
            assert patched(before, answered) == after
            assert len(answered) <= len(replaced)
            for hunk, following in pairwise(answered):
                assert hunk.line + len(hunk.before) < following.line
            for hunk in answered:
                assert hunk.before or hunk.after
                if hunk.before and hunk.after:
                    assert hunk.before[0] != hunk.after[0]
                    assert hunk.before[-1] != hunk.after[-1]
            if len(before) == len(after) and all(within_a_line(text, edit) for edit in replaced):
                found = variables._replaced_in_place(before, after)
                if found is not None:
                    in_place += 1
                    assert answered == found
        assert in_place > 100


def applied(text: str, replaced: Sequence[TextEdit]) -> str:
    """``text`` with each span replaced, the last first."""
    for edit in reversed(replaced):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text


def patched(lines: Sequence[str], answered: Sequence[Hunk]) -> list[str]:
    """``lines`` with each hunk's lines replaced, at the line it names."""
    made = list(lines)
    for hunk in reversed(answered):
        assert made[hunk.line - 1 : hunk.line - 1 + len(hunk.before)] == list(hunk.before)
        made[hunk.line - 1 : hunk.line - 1 + len(hunk.before)] = hunk.after
    return made


def within_a_line(text: str, edit: TextEdit) -> bool:
    """Whether a span neither holds nor writes a line break: it begins and ends on one line."""
    return not breaks(text[edit.start : edit.end]) and not breaks(edit.text)


def breaks(text: str) -> bool:
    """Whether ``text`` holds a line break, as ``str.splitlines`` reads one."""
    return text != "" and text.splitlines() != [text]


class TestThePlannedFilesStamp:
    """A file's stamp is looked up as the file is spelled, and the file resolved only where that
    finds none: a plan renaming a unit stated in every file of a large project resolved every one
    of them again, though each was spelled as its stamp's own resolved path."""

    def test_a_file_spelled_as_its_stamp_is_not_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speed(tmp_path)
        b = (tmp_path / "b.ddd.json").resolve()
        known = stamps(tmp_path, "b.ddd.json")
        asked: list[Path] = []
        real = Path.resolve
        monkeypatch.setattr(
            Path, "resolve", lambda self, strict=False: asked.append(self) or real(self, strict)
        )
        made = planned(b, (Operation("set", UNIT, '"rpm"'),), known)
        assert (made.path, made.fingerprint) == (b, known[b])
        assert asked == []

    def test_a_file_spelled_otherwise_is_resolved_to_find_its_stamp(self, tmp_path: Path) -> None:
        speed(tmp_path)
        (tmp_path / "sub").mkdir()
        spelled = tmp_path / "sub" / ".." / "b.ddd.json"
        known = stamps(tmp_path, "b.ddd.json")
        made = planned(spelled, (Operation("set", UNIT, '"rpm"'),), known)
        assert (made.path, made.fingerprint) == (
            spelled,
            known[(tmp_path / "b.ddd.json").resolve()],
        )


class TestThePlannedEditIsMadeFromThePlansOwnDocument:
    """``planned`` makes the edit from the document its cache holds for the file, which whoever
    planned it read already: the file is scanned once more, as the edit leaves it, to read it
    back."""

    def test_the_document_read_for_the_plan_is_not_scanned_again(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speed(tmp_path)
        b = (tmp_path / "b.ddd.json").resolve()
        cache: dict[Path, Document] = {}
        read(b, cache)
        operations = (Operation("set", UNIT, '"rpm"'),)
        expected = planned(b, operations, stamps(tmp_path, "b.ddd.json"))
        scanned: list[str] = []
        init = Document.__init__

        def scanning(document: Document, text: str) -> None:
            scanned.append(text)
            init(document, text)

        monkeypatch.setattr(Document, "__init__", scanning)
        assert planned(b, operations, stamps(tmp_path, "b.ddd.json"), cache) == expected
        assert scanned == [b.read_text(encoding="utf-8").replace('"%"', '"rpm"')]

    def test_a_file_read_otherwise_than_it_is_written_is_scanned_as_it_is(
        self, tmp_path: Path
    ) -> None:
        """Ending its lines with carriage returns and line feeds, which the plan's reading made
        line feeds: edited as the file spells them."""
        speed(tmp_path)
        b = (tmp_path / "b.ddd.json").resolve()
        b.write_bytes(b.read_bytes().replace(b"\n", b"\r\n"))
        cache: dict[Path, Document] = {}
        assert "\r" not in read(b, cache).text
        made = planned(b, (Operation("set", UNIT, '"rpm"'),), stamps(tmp_path, "b.ddd.json"), cache)
        assert [hunk.after for hunk in made.hunks] == [('          "unit": "rpm"',)]
