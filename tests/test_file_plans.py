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
from conftest import build_record, component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import CHECKS, Diagnostic, Location, Severity
from ddd.file_plans import REATTRIBUTED, Pair, new_errors
from ddd.gui.session import Session, findings_with

PROJECT = Path("/p/p.ddd.json")
A = Path("/p/a.ddd.json")
B = Path("/p/b.ddd.json")
DECLARATION = "component.interface[0]"


def filed(check: str, severity: Severity, path: Path, pointer: str, message: str) -> Pair:
    return (path, Diagnostic(check, severity, message, Location(path, pointer)))


class TestNewErrors:
    def test_an_error_the_project_does_not_have_now_is_new(self) -> None:
        found = filed("unknown-constant", Severity.ERROR, Path("/p/a.ddd.json"), "x", "'N' is …")
        assert new_errors((), (found,)) == (found,)

    def test_one_it_has_now_is_not(self) -> None:
        found = filed("unknown-constant", Severity.ERROR, Path("/p/a.ddd.json"), "x", "'N' is …")
        assert new_errors((found,), (found,)) == ()

    def test_a_warning_is_never_new(self) -> None:
        found = filed("unused-output", Severity.WARNING, Path("/p/a.ddd.json"), "x", "…")
        assert new_errors((), (found,)) == ()

    def test_a_finding_placed_nowhere_is_matched_whole(self) -> None:
        """A plugin's check may report where the project cannot place it; the finding is
        filed on the root, and it is the same one when everything else about it is."""
        found = (PROJECT, Diagnostic("demo/tagged", Severity.ERROR, "…"))
        assert new_errors((found,), (found,)) == ()

    def test_an_error_worded_otherwise_at_its_place_is_the_one_it_has(self) -> None:
        """Important 1: the file declaring `TREND_SAMPLES` goes, and the error at the shape
        naming `TREND_SAMPLE` no longer suggests it."""
        pointer = "component.interface[0].definition.dimensions[0]"
        typo = "'Trend' is dimensioned by 'TREND_SAMPLE', which is not a constant any file declares"
        suggesting = f"{typo} - did you mean 'TREND_SAMPLES'?"
        was = filed("unknown-constant", Severity.ERROR, A, pointer, suggesting)
        now = filed("unknown-constant", Severity.ERROR, A, pointer, typo)
        assert new_errors((was,), (now,)) == ()

    def test_an_error_of_another_check_at_its_place_is_new(self) -> None:
        was = filed("unknown-type", Severity.ERROR, A, DECLARATION, "…")
        now = filed("missing-producer", Severity.ERROR, A, DECLARATION, "…")
        assert new_errors((was,), (now,)) == (now,)

    def test_one_more_error_at_a_place_than_it_had_is_new(self) -> None:
        """Counted, not matched: a check filing every finding at the project's name has one
        there now and two after, and one of the two is new whatever each says."""
        had = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'Q' is unread")
        first = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'R' is unread")
        second = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'S' is unread")
        assert new_errors((had,), (first, second)) == (second,)

    def test_an_error_twice_where_the_project_has_it_once_is_new_once(self) -> None:
        """Word for word is counted too: one error the project has uses up one match, not every
        copy of it."""
        found = filed("unknown-constant", Severity.ERROR, A, "x", "'N' is …")
        assert new_errors((found,), (found, found)) == (found,)

    def test_the_error_quoted_as_new_is_one_the_project_does_not_have(self) -> None:
        """Case j: a place's one error becomes two, the new one listed first. The old one is
        matched word for word before anything is matched by place; taken by place alone in
        order, the new one used up the old one's place, and the old one was quoted as new."""
        old = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'Zq' is unread")
        new = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'Ay' is unread")
        assert new_errors((old,), (new, old)) == (new,)

    @pytest.mark.parametrize(
        ("check", "at"),
        [
            ("unknown-constant", Location(A, DECLARATION)),
            ("file-extension", Location(A)),
            ("demo/tagged", None),
            ("multiple-producers", Location(A, DECLARATION)),
        ],
        ids=["a pointer", "a whole file", "no place", "a clash placed by order"],
    )
    def test_an_error_where_the_project_has_a_warning_is_new(
        self, check: str, at: Location | None
    ) -> None:
        """Whatever the key: a warning is not an error, and the error is new."""
        was = (A, Diagnostic(check, Severity.WARNING, "…", at))
        now = (A, Diagnostic(check, Severity.ERROR, "…", at))
        assert new_errors((was,), (now,)) == (now,)

    @pytest.mark.parametrize("at", [Location(PROJECT), None], ids=["a whole file", "no place"])
    def test_where_nothing_narrower_places_them_errors_differ_by_their_wording(
        self, at: Location | None
    ) -> None:
        """A finding on a whole file, or on no place at all, keeps its message in its key: two
        differently worded errors there are two errors, not one worded twice."""
        was = (PROJECT, Diagnostic("plugin-invalid", Severity.ERROR, "one reason", at))
        now = (PROJECT, Diagnostic("plugin-invalid", Severity.ERROR, "another reason", at))
        assert new_errors((was,), (now,)) == (now,)

    def test_a_whole_file_is_not_a_place_whose_pointer_reads_like_its_message(self) -> None:
        """The keys of a placed finding, of one on a whole file and of one on no place are of
        three lengths: no wording can make one of them read as another."""
        was = filed("demo/tagged", Severity.ERROR, A, DECLARATION, "…")
        now = (A, Diagnostic("demo/tagged", Severity.ERROR, DECLARATION, Location(A)))
        assert new_errors((was,), (now,)) == (now,)

    def test_a_clash_placed_by_order_is_counted_wherever_it_sits(self) -> None:
        """A check of :data:`REATTRIBUTED` is counted per check and severity: the conflict of
        three writers, reported at `A` now and at `B` once `A` goes, is the one it was."""
        was = filed("multiple-producers", Severity.ERROR, A, DECLARATION, "'X' … 'B' … 'A'")
        now = filed("multiple-producers", Severity.ERROR, B, DECLARATION, "'X' … 'C' … 'B'")
        assert new_errors((was,), (now,)) == ()

    def test_one_more_clash_placed_by_order_than_the_project_has_is_new(self) -> None:
        was = filed("multiple-producers", Severity.ERROR, A, DECLARATION, "'X' … 'B' … 'A'")
        more = filed("multiple-producers", Severity.ERROR, B, DECLARATION, "'Y' … 'C' … 'B'")
        assert new_errors((was,), (was, more)) == (more,)

    def test_a_clash_of_another_check_placed_by_order_is_new(self) -> None:
        was = filed("multiple-producers", Severity.ERROR, A, DECLARATION, "…")
        now = filed("definition-mismatch", Severity.ERROR, A, f"{DECLARATION}.definition", "…")
        assert new_errors((was,), (now,)) == (now,)

    def test_every_check_counted_by_order_is_one_the_analysis_reports(self) -> None:
        """A member spelt otherwise than the check would match no finding and leave the check
        counted per place; a comparison check is never reported by the analysis a change is
        judged by."""
        assert sorted(REATTRIBUTED - CHECKS.keys()) == []
        assert [check for check in sorted(REATTRIBUTED) if CHECKS[check].comparison] == []


def judged(
    base: Path, files: Mapping[str, Any], remove: str, *raised: str
) -> list[tuple[str, str]]:
    """What leaving ``remove`` out of the root's includes would break: a revision's findings
    against its own runs with the list replaced, each as the pairs :func:`new_errors` takes.
    ``raised`` are the checks a build record of the project raises to errors."""
    write_tree(base, files)
    if raised:
        build_record(base, base / "p.ddd.json", severity=[f"{check}=error" for check in raised])
    revision = Session(base).open(base / "p.ddd.json")
    assert revision.analysed is True
    listed = json.loads((base / "p.ddd.json").read_text(encoding="utf-8"))["project"]["includes"]
    without = [entry for entry in listed if entry != remove]
    assert len(without) == len(listed) - 1
    before = [(filed.file, filed.diagnostic) for filed in revision.findings]
    after = [(filed.file, filed.diagnostic) for filed in findings_with(revision, without)]
    return [(path.name, diagnostic.check) for path, diagnostic in new_errors(before, after)]


def writing(name: str, *variables: str, **definition: Any) -> dict[str, Any]:
    return component(name, *(declare("output", variable, **definition) for variable in variables))


def reading(name: str, *variables: str) -> dict[str, Any]:
    return component(name, *(declare("input", variable) for variable in variables))


def mode(*enumerators: tuple[str, int]) -> dict[str, Any]:
    """An enum conversion every copy of which is named ``Mode_t``."""
    return {"kind": "enum", "name": "Mode_t", "enumerators": dict(enumerators)}


PATTERNS_PLUGIN = """
import json
from pathlib import Path

from ddd.diagnostics import CheckInfo, Location, Severity
from ddd.plugins import CheckContext, Plugin

ROOT = Path(__file__).resolve().parents[1] / "p.ddd.json"


def check(context: CheckContext) -> None:
    listed = json.loads(ROOT.read_text(encoding="utf-8"))["project"]["includes"]
    for index, entry in enumerate(listed):
        if "*" in entry:
            context.bag.add(
                "policy/no-patterns",
                f"entry '{entry}' is a pattern; list every file by name",
                Location(ROOT, f"project.includes[{index}]"),
            )


PLUGIN = Plugin(
    name="policy",
    checks=(CheckInfo("policy/no-patterns", Severity.ERROR, "an include is a pattern"),),
    check=check,
)
"""
"""A project policy a plugin may hold - no includes by pattern - read the only way a plugin can:
from the project file on disk, since its check is not told the list a run was given."""


class TestJudgingAProject:
    """Over projects the reviewers built: an error whose wording depends on the rest of the
    project is the error it was, and one whose place ddd chooses by order is counted per check.
    """

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

    def test_an_output_left_unread_is_new_though_another_unread_one_goes(
        self, tmp_path: Path
    ) -> None:
        """Why `unused-output` is counted per place, although it sits on the owner: removing `R`
        leaves `X` unread, an error at `A` the project does not have, and takes `R`'s own unread
        `Y` with it - counted per check, the one would hide behind the other."""
        files = {
            "p.ddd.json": project("P", "a.ddd.json", "r.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "r.ddd.json": component("R", declare("input", "X"), declare("output", "Y")),
        }
        assert judged(tmp_path, files, "r.ddd.json", "unused-output") == [
            ("a.ddd.json", "unused-output")
        ]

    def test_a_plugins_finding_at_an_entry_keeps_its_position(self, tmp_path: Path) -> None:
        """Case k: the plugin reads the list in the file, and files at the pattern's position
        there, `project.includes[3]`, before the change and after it. Removing `u.ddd.json`,
        listed before the pattern, changes nothing it says; keyed by the entry the changed
        list has at that position, its finding read as new."""
        files = {
            "tools/policy.py": PATTERNS_PLUGIN,
            "p.ddd.json": project(
                "P",
                "u.ddd.json",
                "a.ddd.json",
                "b.ddd.json",
                "lib/*.ddd.json",
                "r.ddd.json",
                plugins=["tools/policy.py"],
            ),
            "u.ddd.json": component("U", declare("local", "Scratch")),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "Y"),
            "lib/c.ddd.json": reading("C", "Y"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "u.ddd.json") == []


class TestAClashPlacedByOrder:
    """One project per member of :data:`REATTRIBUTED`, where a harmless removal moves an error
    the project has from one place to another - each the case a member is there for."""

    def test_three_writers_read_in_another_order_are_the_conflict_they_were(
        self, tmp_path: Path
    ) -> None:
        """Case a, `multiple-producers`: every writer but the first read is reported, mirrored
        onto the first. Removing the root's entry for `b.ddd.json`, which the sub-project also
        lists, reads `B` last, and the mirrors move from `B` onto `A`."""
        files = {
            "p.ddd.json": project(
                "P", "b.ddd.json", "a.ddd.json", "c.ddd.json", "sub.ddd.json", "r.ddd.json"
            ),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "X"),
            "c.ddd.json": writing("C", "X"),
            "sub.ddd.json": project("Sub", "b.ddd.json"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "b.ddd.json") == []

    def test_ending_a_conflict_of_writers_keeps_the_readers_disagreement(
        self, tmp_path: Path
    ) -> None:
        """Case b, `definition-mismatch`, and Important 1's own workflow: removing `W1` ends the
        conflict of two writers, and `R`'s disagreement with them - mirrored onto the owner, the
        writer whose component name sorts first - moves from `W1` onto `W2`."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "r.ddd.json"),
            "w1.ddd.json": writing("W1", "X"),
            "w2.ddd.json": writing("W2", "X"),
            "r.ddd.json": component("R", declare("input", "X", "uint16")),
        }
        assert judged(tmp_path, files, "w1.ddd.json") == []

    def test_one_reader_of_a_name_a_type_takes_gone_moves_the_collision(
        self, tmp_path: Path
    ) -> None:
        """Case c, `name-collision`: a variable `V` beside a type `V` is reported at its first
        declaration read, `R1`'s, and at `W`'s once `R1` goes; `R2` still reads `V`."""
        files = {
            "p.ddd.json": project("P", "r1.ddd.json", "w.ddd.json", "r2.ddd.json", "t.ddd.json"),
            "r1.ddd.json": reading("R1", "V"),
            "w.ddd.json": writing("W", "V"),
            "r2.ddd.json": reading("R2", "V"),
            "t.ddd.json": types(scalar_type("V")),
        }
        assert judged(tmp_path, files, "r1.ddd.json") == []

    def test_a_colliding_declaration_read_later_moves_the_collision(self, tmp_path: Path) -> None:
        """Case d, `name-collision` through a diamond: removing the root's entry for
        `r1.ddd.json`, which the sub-project also lists, changes nothing but the order, and the
        first declaration read of `V` becomes `W`'s."""
        files = {
            "p.ddd.json": project("P", "r1.ddd.json", "w.ddd.json", "sub.ddd.json", "t.ddd.json"),
            "r1.ddd.json": reading("R1", "V"),
            "w.ddd.json": writing("W", "V"),
            "sub.ddd.json": project("Sub", "r1.ddd.json"),
            "t.ddd.json": types(scalar_type("V")),
        }
        assert judged(tmp_path, files, "r1.ddd.json") == []

    def test_two_locals_read_in_another_order_are_the_conflict_they_were(
        self, tmp_path: Path
    ) -> None:
        """`local-conflict`: `L1` and `L2` both declare `X` local and `R` reads it, each conflict
        mirrored onto the first local read - `L2` until the root's entry for it goes, and it is
        read later through the sub-project."""
        files = {
            "p.ddd.json": project("P", "l2.ddd.json", "l1.ddd.json", "sub.ddd.json", "r.ddd.json"),
            "l1.ddd.json": component("L1", declare("local", "X")),
            "l2.ddd.json": component("L2", declare("local", "X")),
            "sub.ddd.json": project("Sub", "l2.ddd.json"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "l2.ddd.json") == []

    def test_the_owner_gone_moves_a_storage_disagreement(self, tmp_path: Path) -> None:
        """`storage-mismatch`, raised to an error by the build: `W3` presents `X` otherwise than
        `W1` and `W2` do, and the disagreement, mirrored onto the owner, moves onto `W2`."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "w3.ddd.json"),
            "w1.ddd.json": writing("W1", "X", a2l={"format": "%8.2"}),
            "w2.ddd.json": writing("W2", "X", a2l={"format": "%8.2"}),
            "w3.ddd.json": writing("W3", "X", a2l={"format": "%8.3"}),
        }
        assert judged(tmp_path, files, "w1.ddd.json", "storage-mismatch") == []

    def test_the_owner_gone_moves_a_condition_disagreement(self, tmp_path: Path) -> None:
        """`condition-mismatch`, raised to an error by the build: `W3` alone writes `X` under a
        condition, and the disagreement, mirrored onto the owner, moves onto `W2`."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "w3.ddd.json"),
            "w1.ddd.json": writing("W1", "X"),
            "w2.ddd.json": writing("W2", "X"),
            "w3.ddd.json": component("W3", declare("output", "X", condition="FEATURE")),
        }
        assert judged(tmp_path, files, "w1.ddd.json", "condition-mismatch") == []

    def test_a_reader_of_a_name_differing_in_case_gone_moves_the_finding(
        self, tmp_path: Path
    ) -> None:
        """`name-similar`, raised to an error by the build: `speed` beside `Speed` is reported at
        the first declaration read of `speed`, `R1`'s, and at `R2`'s once `R1` goes."""
        files = {
            "p.ddd.json": project(
                "P", "r1.ddd.json", "r2.ddd.json", "w.ddd.json", "q.ddd.json", "s.ddd.json"
            ),
            "r1.ddd.json": reading("R1", "speed"),
            "r2.ddd.json": reading("R2", "speed"),
            "w.ddd.json": writing("W", "speed"),
            "q.ddd.json": writing("Q", "Speed"),
            "s.ddd.json": reading("S", "Speed"),
        }
        assert judged(tmp_path, files, "r1.ddd.json", "name-similar") == []

    def test_a_shared_id_is_mirrored_onto_the_next_declaration_read(self, tmp_path: Path) -> None:
        """`duplicate-id`: `A` and `B` carry one id, and the finding on `B` is mirrored onto the
        first declaration read of `A` - `P1`'s, then `P2`'s once `P1` goes, which ends the
        conflict of `A`'s two writers too."""
        files = {
            "p.ddd.json": project("P", "p1.ddd.json", "p2.ddd.json", "q.ddd.json", "r.ddd.json"),
            "p1.ddd.json": writing("P1", "A", id="k7m2q9xr4t8w"),
            "p2.ddd.json": writing("P2", "A", id="k7m2q9xr4t8w"),
            "q.ddd.json": writing("Q", "B", id="k7m2q9xr4t8w"),
            "r.ddd.json": reading("R", "A", "B"),
        }
        assert judged(tmp_path, files, "p1.ddd.json") == []

    def test_the_raster_named_first_gone_moves_the_claims_on_its_event(
        self, tmp_path: Path
    ) -> None:
        """`duplicate-event`: four rasters claim one event, every one but `a`, whose name sorts
        first, reported and mirrored onto it; once `a` goes, `b` takes the mirrors of the two
        left, where it had one finding of its own."""
        rasters = {
            f"r{name}.ddd.json": {"rasters": [{"raster": name, "event": 5, "cycle": "10ms"}]}
            for name in "abcd"
        }
        files = {"p.ddd.json": project("P", *rasters), **rasters}
        assert judged(tmp_path, files, "ra.ddd.json") == []

    def test_the_first_copy_of_an_enum_gone_moves_the_conflict(self, tmp_path: Path) -> None:
        """`enum-conflict`: `CC`'s copy of `Mode_t` differs from the first read, `CA`'s, and the
        conflict is mirrored onto it; once `CA` goes, onto `CB`'s, which agreed and had none."""
        files = {
            "p.ddd.json": project("P", "ca.ddd.json", "cb.ddd.json", "cc.ddd.json"),
            "ca.ddd.json": component("CA", declare("local", "MA", conversion=mode(("OFF", 0)))),
            "cb.ddd.json": component("CB", declare("local", "MB", conversion=mode(("OFF", 0)))),
            "cc.ddd.json": component("CC", declare("local", "MC", conversion=mode(("OFF", 1)))),
        }
        assert judged(tmp_path, files, "ca.ddd.json") == []

    def test_the_first_copy_of_an_enum_gone_moves_its_shared_value(self, tmp_path: Path) -> None:
        """`enum-duplicate-value`, raised to an error by the build: it is reported on the first
        copy of `Mode_t` read, and on no other - `CA`'s, then `CB`'s once `CA` goes."""
        twice = mode(("OFF", 0), ("IDLE", 0))
        files = {
            "p.ddd.json": project("P", "ca.ddd.json", "cb.ddd.json"),
            "ca.ddd.json": component("CA", declare("local", "MA", conversion=twice)),
            "cb.ddd.json": component("CB", declare("local", "MB", conversion=twice)),
        }
        assert judged(tmp_path, files, "ca.ddd.json", "enum-duplicate-value") == []


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
