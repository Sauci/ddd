"""The Files tab's own rules: what a change of the root project's ``includes`` would break."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

import ddd.file_plans as file_plans
from conftest import component, declare, project, write_tree
from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.file_plans import Pair, new_errors
from ddd.gui.session import Session, findings_with

PROJECT = Path("/p/p.ddd.json")
A = Path("/p/a.ddd.json")


def filed(check: str, severity: Severity, path: Path, pointer: str, message: str) -> Pair:
    return (path, Diagnostic(check, severity, message, Location(path, pointer)))


class TestNewErrors:
    def test_an_error_the_project_does_not_have_now_is_new(self) -> None:
        found = filed("unknown-constant", Severity.ERROR, Path("/p/a.ddd.json"), "x", "'N' is …")
        assert new_errors(PROJECT, (), ("a.ddd.json",), (found,), ("a.ddd.json",)) == (found,)

    def test_one_it_has_now_is_not(self) -> None:
        found = filed("unknown-constant", Severity.ERROR, Path("/p/a.ddd.json"), "x", "'N' is …")
        assert new_errors(PROJECT, (found,), ("a.ddd.json",), (found,), ("a.ddd.json",)) == ()

    def test_a_warning_is_never_new(self) -> None:
        found = filed("unused-output", Severity.WARNING, Path("/p/a.ddd.json"), "x", "…")
        assert new_errors(PROJECT, (), (), (found,), ()) == ()

    def test_a_later_entrys_finding_is_not_new_for_having_moved_up(self) -> None:
        """Focus 3: `z.ddd.json` names nothing, at index 2 before and index 1 once `b` goes."""
        message = "pattern 'z.ddd.json' matches no file"
        before = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[2]", message)
        after = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[1]", message)
        assert (
            new_errors(
                PROJECT,
                (before,),
                ("a.ddd.json", "b.ddd.json", "z.ddd.json"),
                (after,),
                ("a.ddd.json", "z.ddd.json"),
            )
            == ()
        )

    def test_an_entry_past_the_tenth_is_keyed_by_its_entry_too(self) -> None:
        """An index is as many digits as it takes: `z.ddd.json` at 10, and at 9 once `0` goes."""
        listed = (*(f"{n}.ddd.json" for n in range(10)), "z.ddd.json")
        message = "pattern 'z.ddd.json' matches no file"
        before = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[10]", message)
        after = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[9]", message)
        assert new_errors(PROJECT, (before,), listed, (after,), listed[1:]) == ()

    def test_a_sub_projects_own_entry_is_matched_where_it_is(self) -> None:
        """Only the root's list is replaced, so a sub-project's entries keep their places: read
        by the root's list, entry 0 of `sub.ddd.json` would be `a.ddd.json` before and
        `sub.ddd.json` after, and a finding the project already has would read as new."""
        sub = Path("/p/sub.ddd.json")
        message = "pattern 'x.ddd.json' matches no file"
        found = filed("include-empty", Severity.ERROR, sub, "project.includes[0]", message)
        listed, without_a = ("a.ddd.json", "sub.ddd.json"), ("sub.ddd.json",)
        assert new_errors(PROJECT, (found,), listed, (found,), without_a) == ()

    def test_a_finding_elsewhere_in_the_root_is_matched_where_it_is(self) -> None:
        found = filed("plugin-not-found", Severity.ERROR, PROJECT, "project.plugins[0]", "…")
        assert new_errors(PROJECT, (found,), ("a.ddd.json",), (found,), ()) == ()

    def test_an_entry_the_list_does_not_reach_is_matched_where_it_is(self) -> None:
        """A list with no entry at the finding's index cannot say which entry it names - and the
        first index past its end is one it does not reach."""
        found = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[1]", "…")
        assert new_errors(PROJECT, (found,), ("a.ddd.json",), (found,), ("a.ddd.json",)) == ()

    def test_a_finding_placed_nowhere_is_matched_whole(self) -> None:
        """A plugin's check may report where the project cannot place it; the finding is
        filed on the root, and it is the same one when everything else about it is."""
        found = (PROJECT, Diagnostic("demo/tagged", Severity.ERROR, "…"))
        assert new_errors(PROJECT, (found,), (), (found,), ()) == ()

    def test_an_error_worded_otherwise_at_its_place_is_the_one_it_has(self) -> None:
        """Important 1: of three writers of `X`, `A` goes, and the conflict left at `B`'s
        declaration names another pair of writers than it did."""
        b = Path("/p/b.ddd.json")
        pointer = "component.interface[0]"
        was = filed("multiple-producers", Severity.ERROR, b, pointer, "'X' is ... 'B' and ... 'A'")
        now = filed("multiple-producers", Severity.ERROR, b, pointer, "'X' is ... 'C' and ... 'B'")
        listed = ("a.ddd.json", "b.ddd.json", "c.ddd.json")
        assert new_errors(PROJECT, (was,), listed, (now,), listed[1:]) == ()

    def test_an_error_of_another_check_at_its_place_is_new(self) -> None:
        was = filed("definition-mismatch", Severity.ERROR, A, "component.interface[0]", "…")
        now = filed("missing-producer", Severity.ERROR, A, "component.interface[0]", "…")
        assert new_errors(PROJECT, (was,), (), (now,), ()) == (now,)

    def test_one_more_error_at_a_place_than_it_had_is_new(self) -> None:
        """Counted, not matched: where the project has one conflict at `A`'s declaration and
        two after, the one listed later is the new one, whatever each says."""
        pointer = "component.interface[0]"
        had = filed("multiple-producers", Severity.ERROR, A, pointer, "'X' is ... 'B' and ... 'A'")
        first = filed(
            "multiple-producers", Severity.ERROR, A, pointer, "'X' is ... 'C' and ... 'A'"
        )
        second = filed(
            "multiple-producers", Severity.ERROR, A, pointer, "'X' is ... 'D' and ... 'A'"
        )
        assert new_errors(PROJECT, (had,), (), (first, second), ()) == (second,)

    @pytest.mark.parametrize(
        ("was_at", "now_at", "listed", "now_listed"),
        [
            (
                Location(PROJECT, "project.includes[1]"),
                Location(PROJECT, "project.includes[0]"),
                ("a.ddd.json", "z.ddd.json"),
                ("z.ddd.json",),
            ),
            (Location(A, "component.interface[0]"), Location(A, "component.interface[0]"), (), ()),
            (Location(A), Location(A), (), ()),
            (None, None, (), ()),
        ],
        ids=["an entry", "a pointer", "a whole file", "no place"],
    )
    def test_an_error_where_the_project_has_a_warning_is_new(
        self,
        was_at: Location | None,
        now_at: Location | None,
        listed: tuple[str, ...],
        now_listed: tuple[str, ...],
    ) -> None:
        """Whatever the place: a warning is not an error, and the error is new."""
        was = (PROJECT, Diagnostic("include-empty", Severity.WARNING, "…", was_at))
        now = (PROJECT, Diagnostic("include-empty", Severity.ERROR, "…", now_at))
        assert new_errors(PROJECT, (was,), listed, (now,), now_listed) == (now,)

    @pytest.mark.parametrize("at", [Location(PROJECT), None], ids=["a whole file", "no place"])
    def test_where_nothing_narrower_places_them_errors_differ_by_their_wording(
        self, at: Location | None
    ) -> None:
        """A finding on a whole file, or on no place at all, keeps its message in its key: two
        differently worded errors there are two errors, not one worded twice."""
        was = (PROJECT, Diagnostic("plugin-invalid", Severity.ERROR, "one reason", at))
        now = (PROJECT, Diagnostic("plugin-invalid", Severity.ERROR, "another reason", at))
        assert new_errors(PROJECT, (was,), (), (now,), ()) == (now,)


def judged(base: Path, files: Mapping[str, Any], remove: str) -> list[tuple[str, str]]:
    """What leaving ``remove`` out of the root's includes would break: a revision's findings
    against its own runs with the list replaced, each as the pairs :func:`new_errors` takes."""
    write_tree(base, files)
    revision = Session(base).open(base / "p.ddd.json")
    assert revision.analysed is True
    listed = json.loads((base / "p.ddd.json").read_text(encoding="utf-8"))["project"]["includes"]
    without = [entry for entry in listed if entry != remove]
    assert len(without) == len(listed) - 1
    before = [(filed.file, filed.diagnostic) for filed in revision.findings]
    after = [(filed.file, filed.diagnostic) for filed in findings_with(revision, without)]
    fresh = new_errors(revision.project, before, listed, after, without)
    return [(path.name, diagnostic.check) for path, diagnostic in fresh]


def writing(name: str, *variables: str) -> dict[str, Any]:
    return component(name, *(declare("output", variable) for variable in variables))


def reading(name: str, *variables: str) -> dict[str, Any]:
    return component(name, *(declare("input", variable) for variable in variables))


class TestJudgingAProject:
    """Important 1, over projects the reviewer built: an error whose wording depends on the rest
    of the project is the error it was, at the place it was."""

    def test_removing_one_of_three_writers_leaves_the_conflict_it_had(self, tmp_path: Path) -> None:
        """A removal a reader makes on the way to ending the conflict: the two writers left
        name each other now, where each named `A`."""
        files = {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json", "r.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "X"),
            "c.ddd.json": writing("C", "X"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "a.ddd.json") == []

    def test_a_file_read_later_through_a_sub_project_changes_no_error(self, tmp_path: Path) -> None:
        """A diamond: `b.ddd.json` is the root's and the sub-project's. Removing the root's entry
        keeps it in the project, read after `a.ddd.json` now, and the conflict names the two
        the other way round."""
        files = {
            "p.ddd.json": project("P", "b.ddd.json", "a.ddd.json", "sub.ddd.json", "r.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "X"),
            "sub.ddd.json": project("Sub", "b.ddd.json"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "b.ddd.json") == []

    def test_an_error_no_longer_suggesting_a_near_miss_is_the_one_it_had(
        self, tmp_path: Path
    ) -> None:
        """`TREND_SAMPLE` is a typo the project has now, suggested `TREND_SAMPLES` while a file
        declares that; removing the file drops the suggestion, not the error."""
        files = {
            "p.ddd.json": project("P", "k.ddd.json", "extra.ddd.json", "a.ddd.json", "r.ddd.json"),
            "k.ddd.json": {"constants": [{"name": "CELLS", "value": 4}]},
            "extra.ddd.json": {"constants": [{"name": "TREND_SAMPLES", "value": 4}]},
            "a.ddd.json": component(
                "A",
                declare("output", "Trend", dimensions=["TREND_SAMPLE"]),
                declare("output", "Cells", dimensions=["CELLS"]),
            ),
            "r.ddd.json": reading("R", "Trend", "Cells"),
        }
        assert judged(tmp_path, files, "extra.ddd.json") == []

    def test_removing_the_only_writer_of_what_a_component_reads_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Still refused amid a conflict the project has now: `Y` read with no writer is an error
        at a place that had none."""
        files = {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "r.ddd.json", "u.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "X"),
            "r.ddd.json": reading("R", "X", "Y"),
            "u.ddd.json": writing("U", "Y"),
        }
        assert judged(tmp_path, files, "u.ddd.json") == [("r.ddd.json", "missing-producer")]


def test_the_module_imports_nothing_of_the_gui() -> None:
    """A core module for the gui to call, never one that calls the gui: it takes findings as
    ``(path, diagnostic)`` pairs rather than the session's ``Filed`` for that reason.

    Imported in an interpreter of its own, so that what is counted is everything it pulls in
    and not what this suite happens to have loaded already - and from the source this suite
    tests, which is not always the one installed.
    """
    source = Path(file_plans.__file__).resolve().parents[1]
    finished = subprocess.run(
        [sys.executable, "-c", "import sys, ddd.file_plans; print(' '.join(sorted(sys.modules)))"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(source)},
    )
    loaded = finished.stdout.split()
    assert "ddd.file_plans" in loaded
    assert [name for name in loaded if name == "ddd.gui" or name.startswith("ddd.gui.")] == []
