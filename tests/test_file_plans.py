"""The Files tab's own rules: what a change of the root project's ``includes`` would break."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import ddd.file_plans as file_plans
from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.file_plans import Pair, new_errors

PROJECT = Path("/p/p.ddd.json")


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
        """A list with no entry at the finding's index cannot say which entry it names."""
        found = filed("include-empty", Severity.ERROR, PROJECT, "project.includes[3]", "…")
        assert new_errors(PROJECT, (found,), ("a.ddd.json",), (found,), ("a.ddd.json",)) == ()

    def test_a_finding_placed_nowhere_is_matched_whole(self) -> None:
        """A plugin's check may report where the project cannot place it; the finding is
        filed on the root, and it is the same one when everything else about it is."""
        found = (PROJECT, Diagnostic("demo/tagged", Severity.ERROR, "…"))
        assert new_errors(PROJECT, (found,), (), (found,), ()) == ()


def test_the_module_imports_nothing_of_the_gui() -> None:
    """A core module the gui calls, never one that calls the gui: it takes findings as
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
