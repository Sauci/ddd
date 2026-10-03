"""One variable as the unit panel of ddd gui shows it, and what settling one of its keys takes."""

from __future__ import annotations

import difflib
import json
import random
from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.editing import UNREADABLE, EditError, Operation, fingerprint
from ddd.loading import load_workspace
from ddd.lsp.edits import Settlement, Unsettled, settle
from ddd.lsp.navigation import Index, Site, index
from ddd.lsp.ranges import Document
from ddd.variables import (
    Hunk,
    declarations_of,
    hunks,
    located_on,
    planned,
    preview,
    refusal,
    units_in_use,
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
            ("unreachable", "unreadable", "is no longer where the last analysis found it"),
        ],
    )
    def test_each_reason_has_its_code_and_names_the_declaration(
        self, reason: Any, code: str, says: str
    ) -> None:
        refused = Unsettled(Site(Path("/w/b.ddd.json"), DEFINITION), reason, "Speed_t")
        assert refusal(refused, "Speed", "unit") == (
            code,
            f"the declaration of 'Speed' in b.ddd.json {says}",
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
        of 455 lines of a generated project, one unit renamed in it - on the Linux development
        PC."""
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
