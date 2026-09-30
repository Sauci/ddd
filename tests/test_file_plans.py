"""The Files tab's own rules: the root project's ``includes`` as the loader reads them, the plans
creating, adding and removing a file of it, and what a change of the list would break."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import pytest

import ddd.file_plans as file_plans
from conftest import (
    build_record,
    built_of,
    component,
    declare,
    directory_link,
    project,
    scalar_type,
    types,
    write_tree,
)
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.editing import FileChange, Operation, fingerprint
from ddd.file_plans import (
    FilePlan,
    FileRefusalError,
    IncludedEntry,
    Pair,
    add_plan,
    create_plan,
    included_entries,
    new_errors,
    remove_plan,
)
from ddd.gui.session import Revision, Session, findings_with
from ddd.loading import load_workspace
from ddd.lsp.diagnostics import finding_identity, run_project
from ddd.lsp.navigation import Index, index
from ddd.lsp.units import PlannedEdit, unit_project

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
        """The file declaring `TREND_SAMPLES` goes, and the error at the shape naming
        `TREND_SAMPLE` no longer suggests it."""
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
        copy of it. No revision lists one identity twice - the grouping drops a repeat - so this
        is the one input where what is reported is an error ``before`` reports word for word."""
        found = filed("unknown-constant", Severity.ERROR, A, "x", "'N' is …")
        assert new_errors((found,), (found, found)) == (found,)

    def test_word_for_word_matches_are_set_aside_wherever_they_are_listed(self) -> None:
        """A place had `e1` and `e2`, and lists `y`, `x`, `e1` after: `e1` is set aside first,
        though listed last, and of `y` and `x` the one past what is left of the count is
        reported - `x`, not the third one listed."""
        e1, e2, x, y = (
            filed("local-conflict", Severity.ERROR, A, DECLARATION, message)
            for message in ("e1", "e2", "x", "y")
        )
        assert new_errors((e1, e2), (y, x, e1)) == (x,)

    def test_the_error_quoted_as_new_is_one_the_project_does_not_have(self) -> None:
        """A place's one error becomes two, the new one listed first. The old one is matched
        word for word before anything is matched by place; taken by place alone in order, the new
        one used up the old one's place, and the old one was quoted as new."""
        old = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'Zq' is unread")
        new = filed("policy/unread", Severity.ERROR, PROJECT, "project.name", "'Ay' is unread")
        assert new_errors((old,), (new, old)) == (new,)

    @pytest.mark.parametrize(
        ("check", "at"),
        [
            ("unknown-constant", Location(A, DECLARATION)),
            ("file-extension", Location(A)),
            ("demo/tagged", None),
        ],
        ids=["a pointer", "a whole file", "no place"],
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


HERE = Location(A, DECLARATION)
THERE = Location(B, DECLARATION)
ELSEWHERE = Location(Path("/p/c.ddd.json"), DECLARATION)
CONFLICT = "'X' is written by component 'B' and by component 'A'; exactly one writer is allowed"


def finding(
    at: Location | None,
    *notes: Location | None,
    check: str = "multiple-producers",
    severity: Severity = Severity.ERROR,
    message: str = CONFLICT,
) -> Pair:
    """A finding with a note at each of ``notes``, shown on the file it is placed in, or on the
    project's where it is placed nowhere."""
    shown = PROJECT if at is None else at.path
    written = tuple(("also written here", note) for note in notes)
    return (shown, Diagnostic(check, severity, message, at, written))


class TestAMirrorIsNotCounted:
    """What is not counted: the mirror :func:`~ddd.lsp.diagnostics.group_findings` files of a
    finding for an editor at each place a note of it points to, as
    :func:`~ddd.lsp.diagnostics._mirrors` makes one - without notes, of a finding with a place,
    at a note's place other than the finding's own. A mirror is told by that shape: no notes, at
    a place a note of a finding of its check, severity and message points to."""

    def test_a_mirror_is_not_counted(self) -> None:
        """`B`'s conflict with `A`, reported on `B` with a note at `A`, and the mirror of it an
        editor is shown on `A`: one error."""
        reported = finding(THERE, HERE)
        assert new_errors((), (reported, finding(HERE))) == (reported,)

    def test_the_mirror_of_an_error_the_project_has_is_not_counted_either(self) -> None:
        """Read in another order, the conflict is reported on `A` with a note at `B`, where the
        project reports it on `B` and shows a mirror on `A`: `A` has an error it did not have."""
        other_way = (
            "'X' is written by component 'A' and by component 'B'; exactly one writer is allowed"
        )
        moved = finding(HERE, THERE, message=other_way)
        now = (moved, finding(THERE, message=other_way))
        assert new_errors((finding(THERE, HERE), finding(HERE)), now) == (moved,)

    def test_a_finding_where_no_note_points_is_counted(self) -> None:
        """Alike in all but its place, a finding where no note points is one of its own."""
        reported = finding(THERE, HERE)
        alike = finding(ELSEWHERE)
        assert new_errors((), (reported, alike)) == (reported, alike)

    @pytest.mark.parametrize(
        "noting",
        [
            finding(THERE, HERE, message="'Y' is written by component 'B' and by component 'A'"),
            finding(THERE, HERE, check="definition-mismatch"),
            finding(THERE, HERE, severity=Severity.WARNING),
        ],
        ids=["another message", "another check", "another severity"],
    )
    def test_a_finding_where_a_note_of_another_kind_points_is_counted(self, noting: Pair) -> None:
        """A mirror has its finding's check, severity and message: a finding with no notes that
        differs from the one noting its place in any of them is one of its own."""
        noted = finding(HERE)
        assert new_errors((noting,), (noting, noted)) == (noted,)

    def test_a_note_with_no_place_makes_no_mirror(self) -> None:
        """A finding placed nowhere is not taken for the mirror of a note placed nowhere."""
        reported = finding(THERE, None)
        unplaced = finding(None)
        assert new_errors((), (reported, unplaced)) == (reported, unplaced)

    def test_a_note_at_its_own_finding_makes_no_mirror(self) -> None:
        """No mirror is made at a finding's own place, so one alike there but for its notes is
        one of its own - two findings no revision lists together, the grouping filing one
        identity once."""
        reported = finding(THERE, THERE)
        alike = finding(THERE)
        assert new_errors((), (reported, alike)) == (reported, alike)

    def test_a_finding_placed_nowhere_makes_no_mirror(self) -> None:
        """Nothing is mirrored of a finding placed nowhere, whatever its notes point to."""
        reported = finding(None, HERE)
        noted = finding(HERE)
        assert new_errors((), (reported, noted)) == (reported, noted)

    def test_a_finding_with_notes_of_its_own_is_no_mirror(self) -> None:
        """A mirror has no notes: a finding where a note points, alike but noting another place,
        is one of its own."""
        reported = finding(THERE, HERE)
        noting = finding(HERE, ELSEWHERE)
        assert new_errors((), (reported, noting)) == (reported, noting)

    def test_what_is_counted_is_what_the_run_reports(self, tmp_path: Path) -> None:
        """The coupling to :func:`~ddd.lsp.diagnostics._mirrors` and
        :func:`~ddd.lsp.diagnostics.group_findings`, over the conflict of two writers whose reader
        disagrees with them: of everything the revision lists, mirrors included, what is counted
        is what a run of the checks over the project reports - its bag, before it is grouped -
        finding for finding. Should the mirrors keep their notes, or the grouping file anything
        else, this says so."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "r.ddd.json"),
                "w1.ddd.json": writing("W1", "X"),
                "w2.ddd.json": writing("W2", "X"),
                "r.ddd.json": component("R", declare("input", "X", "uint16")),
            },
        )
        root = tmp_path / "p.ddd.json"
        listed = [(filed.file, filed.diagnostic) for filed in Session(tmp_path).open(root).findings]
        reported = run_project(root).bag
        assert len(listed) > len(reported)
        counted = Counter(
            finding_identity(diagnostic) for _, diagnostic in file_plans._as_reported(listed)
        )
        assert counted == Counter(finding_identity(diagnostic) for diagnostic in reported)


def judged(
    base: Path,
    files: Mapping[str, Any],
    remove: str,
    *raised: str,
    relaxed: Sequence[str] = (),
) -> list[tuple[str, str, str]]:
    """What leaving ``remove`` out of the root's includes would break: a revision's findings
    against its own runs with the list replaced, each as the pairs :func:`new_errors` takes, and
    each error answered by its file, its check and its message - the whole of what a refusal
    would say. ``raised`` are the checks a build record of the project raises to errors, and
    ``relaxed`` the ones it lowers to warnings."""
    write_tree(base, files)
    severity = [f"{check}=error" for check in raised] + [f"{check}=warning" for check in relaxed]
    if severity:
        build_record(base, base / "p.ddd.json", severity=severity)
    revision = Session(base).open(base / "p.ddd.json")
    assert revision.analysed is True
    listed = json.loads((base / "p.ddd.json").read_text(encoding="utf-8"))["project"]["includes"]
    without = [entry for entry in listed if entry != remove]
    assert len(without) == len(listed) - 1
    before = [(filed.file, filed.diagnostic) for filed in revision.findings]
    after = [(filed.file, filed.diagnostic) for filed in findings_with(revision, without)]
    fresh = new_errors(before, after)
    return [(path.name, diagnostic.check, diagnostic.message) for path, diagnostic in fresh]


def writing(name: str, *variables: str, **definition: Any) -> dict[str, Any]:
    return component(name, *(declare("output", variable, **definition) for variable in variables))


def reading(name: str, *variables: str) -> dict[str, Any]:
    return component(name, *(declare("input", variable) for variable in variables))


def enum_of(name: str, *enumerators: tuple[str, int]) -> dict[str, Any]:
    """An enum conversion: a copy of the enum ``name``, as a declaration spells it out."""
    return {"kind": "enum", "name": name, "enumerators": dict(enumerators)}


def axis(scope: str, name: str, **definition: Any) -> dict[str, Any]:
    return declare(scope, name, "uint16", kind="axis", size=3, **definition)


def curve(scope: str, name: str, over: str) -> dict[str, Any]:
    return declare(scope, name, "uint16", kind="curve", axis=over)


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
    project is the error it was, a plugin's at an entry of the list is placed by the entry's
    position, and an error the removal makes is new."""

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
        assert judged(tmp_path, files, "u.ddd.json") == [
            (
                "r.ddd.json",
                "missing-producer",
                "'Y' is read by component 'R' but no component declares it as output",
            )
        ]

    def test_an_output_left_unread_is_new_though_another_unread_one_goes(
        self, tmp_path: Path
    ) -> None:
        """`unused-output`, raised to an error by the build, sits on the owner: removing `R`
        leaves `X` unread, an error at `A` the project does not have, and takes `R`'s own unread
        `Y` with it, from another place."""
        files = {
            "p.ddd.json": project("P", "a.ddd.json", "r.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "r.ddd.json": component("R", declare("input", "X"), declare("output", "Y")),
        }
        assert judged(tmp_path, files, "r.ddd.json", "unused-output") == [
            ("a.ddd.json", "unused-output", "'X' is written by component 'A' but read by nobody")
        ]

    def test_a_plugins_finding_at_an_entry_keeps_its_position(self, tmp_path: Path) -> None:
        """The plugin reads the list in the file, and files at the pattern's position there,
        `project.includes[3]`, before the change and after it. Removing `u.ddd.json`, listed
        before the pattern, changes nothing it says; keyed by the entry the changed list has at
        that position, its finding read as new."""
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


class TestAMirrorMoving:
    """A clash ddd reports against one of the declarations taking part - the owner, the first
    read, the first copy of an enum met, the raster whose name sorts first - and mirrors onto that
    one. Where a removal changes which declaration that is, and every finding ``ddd check``
    reports stays where it was, reworded or not, or leaves, only the mirrors move, and the removal
    is allowed."""

    def test_ending_a_conflict_of_writers_keeps_the_readers_disagreement(
        self, tmp_path: Path
    ) -> None:
        """`definition-mismatch`, and the removal the tab most needs: removing `W1` ends the
        conflict of two writers, and `R`'s disagreement with them - mirrored onto the owner, the
        writer whose component name sorts first - moves from `W1` onto `W2`."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "r.ddd.json"),
            "w1.ddd.json": writing("W1", "X"),
            "w2.ddd.json": writing("W2", "X"),
            "r.ddd.json": component("R", declare("input", "X", "uint16")),
        }
        assert judged(tmp_path, files, "w1.ddd.json") == []

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
            "ca.ddd.json": component(
                "CA", declare("local", "MA", conversion=enum_of("Mode_t", ("OFF", 0)))
            ),
            "cb.ddd.json": component(
                "CB", declare("local", "MB", conversion=enum_of("Mode_t", ("OFF", 0)))
            ),
            "cc.ddd.json": component(
                "CC", declare("local", "MC", conversion=enum_of("Mode_t", ("OFF", 1)))
            ),
        }
        assert judged(tmp_path, files, "ca.ddd.json") == []


class TestAFindingMovingByOrder:
    """The cost of counting per place. ddd reports some findings on declarations it picks by an
    order a removal can change - the order it reads the project in, the first declaration read
    of a name, the first local, the first copy of an enum met. Where a removal moves one of those
    onto a place without an error of its check and severity, it is refused, harmless as it is. So
    is one that relabels an error: a local gone from beside two writers, their ``local-conflict``
    reported as ``multiple-producers``."""

    def test_a_file_read_later_through_a_sub_project_is_refused_for_the_conflict_it_moves(
        self, tmp_path: Path
    ) -> None:
        """A diamond: `b.ddd.json` is the root's and the sub-project's. Removing the root's entry
        keeps it in the project, read after `a.ddd.json` now, and the conflict of the two
        writers, reported on every writer but the first read, moves from `A` onto `B`."""
        files = {
            "p.ddd.json": project("P", "b.ddd.json", "a.ddd.json", "sub.ddd.json", "r.ddd.json"),
            "a.ddd.json": writing("A", "X"),
            "b.ddd.json": writing("B", "X"),
            "sub.ddd.json": project("Sub", "b.ddd.json"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "b.ddd.json") == [
            (
                "b.ddd.json",
                "multiple-producers",
                "'X' is written by component 'B' and by component 'A'; exactly one writer is "
                "allowed",
            )
        ]

    def test_three_writers_read_in_another_order_are_refused_for_the_conflict_they_move(
        self, tmp_path: Path
    ) -> None:
        """`multiple-producers` is reported on every writer but the first read. Removing the
        root's entry for `b.ddd.json`, which the sub-project also lists, reads `B` last: `C`'s
        conflict stays, reworded, and `A`'s moves onto `B`."""
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
        assert judged(tmp_path, files, "b.ddd.json") == [
            (
                "b.ddd.json",
                "multiple-producers",
                "'X' is written by component 'B' and by component 'A'; exactly one writer is "
                "allowed",
            )
        ]

    def test_a_colliding_declaration_read_later_is_refused_for_the_collision_it_moves(
        self, tmp_path: Path
    ) -> None:
        """`name-collision` through a diamond: a variable `V` beside a type `V` is reported at
        its first declaration read. Removing the root's entry for `r1.ddd.json`, which the
        sub-project also lists, changes nothing but the order, and the collision moves from
        `R1`'s declaration onto `W`'s."""
        files = {
            "p.ddd.json": project("P", "r1.ddd.json", "w.ddd.json", "sub.ddd.json", "t.ddd.json"),
            "r1.ddd.json": reading("R1", "V"),
            "w.ddd.json": writing("W", "V"),
            "sub.ddd.json": project("Sub", "r1.ddd.json"),
            "t.ddd.json": types(scalar_type("V")),
        }
        assert judged(tmp_path, files, "r1.ddd.json") == [
            (
                "w.ddd.json",
                "name-collision",
                "'V' is declared as a variable and is also the name of a type; the types header "
                "makes that a typedef name, which c keeps in the same namespace as the variable",
            )
        ]

    def test_one_reader_of_a_name_a_type_takes_gone_is_refused_for_the_collision_it_moves(
        self, tmp_path: Path
    ) -> None:
        """`name-collision`: a variable `V` beside a type `V` is reported at its first
        declaration read, `R1`'s, and at `W`'s once `R1` goes; `R2` still reads `V`."""
        files = {
            "p.ddd.json": project("P", "r1.ddd.json", "w.ddd.json", "r2.ddd.json", "t.ddd.json"),
            "r1.ddd.json": reading("R1", "V"),
            "w.ddd.json": writing("W", "V"),
            "r2.ddd.json": reading("R2", "V"),
            "t.ddd.json": types(scalar_type("V")),
        }
        assert judged(tmp_path, files, "r1.ddd.json") == [
            (
                "w.ddd.json",
                "name-collision",
                "'V' is declared as a variable and is also the name of a type; the types header "
                "makes that a typedef name, which c keeps in the same namespace as the variable",
            )
        ]

    def test_a_reader_of_a_name_differing_in_case_gone_is_refused_for_the_finding_it_moves(
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
        assert judged(tmp_path, files, "r1.ddd.json", "name-similar") == [
            ("r2.ddd.json", "name-similar", "'speed' and 'Speed' differ only in upper/lower case")
        ]

    def test_two_locals_read_in_another_order_are_refused_for_the_conflict_they_move(
        self, tmp_path: Path
    ) -> None:
        """`local-conflict`: `L1` and `L2` both declare `X` local and `R` reads it, and every
        declaration but the first local read is reported - `L2` until the root's entry for it
        goes and it is read later, through the sub-project. `R`'s conflict stays, reworded, and
        the two locals' moves from `L1` onto `L2`."""
        files = {
            "p.ddd.json": project("P", "l2.ddd.json", "l1.ddd.json", "sub.ddd.json", "r.ddd.json"),
            "l1.ddd.json": component("L1", declare("local", "X")),
            "l2.ddd.json": component("L2", declare("local", "X")),
            "sub.ddd.json": project("Sub", "l2.ddd.json"),
            "r.ddd.json": reading("R", "X"),
        }
        assert judged(tmp_path, files, "l2.ddd.json") == [
            (
                "l2.ddd.json",
                "local-conflict",
                "'X' is local to component 'L1' but is also declared as local by component 'L2'",
            )
        ]

    def test_the_first_of_two_identical_enum_copies_gone_is_refused_for_the_value_it_moves(
        self, tmp_path: Path
    ) -> None:
        """The cost for `enum-duplicate-value`, raised to an error by the build: it is reported on
        the first copy of `Mode_t` met and on no other - `CA`'s, then `CB`'s identical one once
        `CA` goes, a place that had none."""
        twice = enum_of("Mode_t", ("OFF", 0), ("IDLE", 0))
        files = {
            "p.ddd.json": project("P", "ca.ddd.json", "cb.ddd.json"),
            "ca.ddd.json": component("CA", declare("local", "MA", conversion=twice)),
            "cb.ddd.json": component("CB", declare("local", "MB", conversion=twice)),
        }
        assert judged(tmp_path, files, "ca.ddd.json", "enum-duplicate-value") == [
            ("cb.ddd.json", "enum-duplicate-value", "enum 'Mode_t': OFF, IDLE all have the value 0")
        ]

    def test_a_local_gone_from_beside_its_two_writers_is_refused_for_the_conflict_it_relabels(
        self, tmp_path: Path
    ) -> None:
        """A relabel: `F` declares `X` local while `W1` and `W2` write it, a `local-conflict` on
        each, and writes `Y` and `V` beside `Y2` and `V2`. Removing `F` ends the conflicts over
        `Y` and `V`, and `W1` and `W2` writing `X` is reported as `multiple-producers` on `W2`,
        where the project reported a `local-conflict`."""
        files = {
            "p.ddd.json": project(
                "P",
                "f.ddd.json",
                "w1.ddd.json",
                "w2.ddd.json",
                "y2.ddd.json",
                "v2.ddd.json",
                "r.ddd.json",
            ),
            "f.ddd.json": component(
                "F", declare("local", "X"), declare("output", "Y"), declare("output", "V")
            ),
            "w1.ddd.json": writing("W1", "X"),
            "w2.ddd.json": writing("W2", "X"),
            "y2.ddd.json": writing("Y2", "Y"),
            "v2.ddd.json": writing("V2", "V"),
            "r.ddd.json": reading("R", "X", "Y", "V"),
        }
        assert judged(tmp_path, files, "f.ddd.json") == [
            (
                "w2.ddd.json",
                "multiple-producers",
                "'X' is written by component 'W2' and by component 'W1'; exactly one writer is "
                "allowed",
            )
        ]


class TestAClashARemovalBrings:
    """A removal can bring in an error the project does not have while an error of its check
    leaves. Counted each at its own place, the one hides the other only where both are at one
    place: each removal here is refused but the last, which pins that cost."""

    def test_a_relaxed_duplicate_let_in_is_refused_for_the_conflict_it_brings(
        self, tmp_path: Path
    ) -> None:
        """The build reports `duplicate-component` as a warning, so the loader keeps the first
        `A` and drops the second while the revision is analysed. Removing the first ends the
        conflict over `Y`, reported on `B`, and lets the second `A` in, writing `Z` beside `C` -
        a conflict the project did not have, reported on `C`."""
        files = {
            "p.ddd.json": project(
                "P", "a.ddd.json", "a2.ddd.json", "b.ddd.json", "c.ddd.json", "r.ddd.json"
            ),
            "a.ddd.json": writing("A", "Y"),
            "a2.ddd.json": writing("A", "Z"),
            "b.ddd.json": writing("B", "Y"),
            "c.ddd.json": writing("C", "Z"),
            "r.ddd.json": reading("R", "Y", "Z"),
        }
        assert judged(tmp_path, files, "a.ddd.json", relaxed=("duplicate-component",)) == [
            (
                "c.ddd.json",
                "multiple-producers",
                "'Z' is written by component 'C' and by component 'A'; exactly one writer is "
                "allowed",
            )
        ]

    def test_a_new_owner_drawing_a_curve_over_a_private_axis_is_refused(
        self, tmp_path: Path
    ) -> None:
        """`W1` owns `C`, drawn over its own `Ax1`, and reads `L`'s private `T2`; `W2` writes `C`
        over `T2`. Removing `W1` hands `C` to `W2`, and `C` reaches the dictionary bound to `T2` -
        a conflict the project did not have, while `W1`'s own read of `T2` leaves with it."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "l.ddd.json"),
            "w1.ddd.json": component(
                "W1", axis("output", "Ax1"), curve("output", "C", "Ax1"), axis("input", "T2")
            ),
            "w2.ddd.json": component("W2", curve("output", "C", "T2")),
            "l.ddd.json": component("L", axis("local", "T2")),
        }
        assert judged(tmp_path, files, "w1.ddd.json") == [
            (
                "w2.ddd.json",
                "local-conflict",
                "'T2' is local to component 'L' but is also used as the axis of 'C' by component "
                "'W2'",
            )
        ]

    def test_the_local_gone_to_end_a_conflict_is_refused_for_the_private_axis_it_binds(
        self, tmp_path: Path
    ) -> None:
        """`K1` declares `C` local, over its own axis, and `K2` writes `C` too, over `L`'s private
        `T2` - the conflict the project has. Removing `K1` is the natural fix, and it
        leaves `C` to `K2`, bound to `T2`: reported on `K2`, and shown to an editor on `L` as
        well. An axis measuring another component's private input takes the same path, not a
        test of its own: an axis's `input` and a curve's `axis` are both entries of the
        definition's `references`, walked by the one loop that calls the analysis's
        `_check_local_reference`."""
        files = {
            "p.ddd.json": project("P", "k1.ddd.json", "k2.ddd.json", "l.ddd.json"),
            "k1.ddd.json": component("K1", axis("local", "Ax1"), curve("local", "C", "Ax1")),
            "k2.ddd.json": component("K2", curve("output", "C", "T2")),
            "l.ddd.json": component("L", axis("local", "T2")),
        }
        use = "'T2' is local to component 'L' but is also used as the axis of 'C' by component 'K2'"
        assert judged(tmp_path, files, "k1.ddd.json") == [("k2.ddd.json", "local-conflict", use)]

    def test_a_copy_of_an_enum_nobody_checked_put_first_is_refused(self, tmp_path: Path) -> None:
        """`enum-duplicate-value` raised to an error by the build: `CA` holds the first copy
        of `Mode_t`, which is checked, and `Flag_t`, whose two enumerators share a value. Removing
        `CA` makes `CB`'s copy of `Mode_t` the one met first - two of its enumerators share a
        value too - while `Flag_t`'s leaves with `CA`."""
        files = {
            "p.ddd.json": project("P", "ca.ddd.json", "cb.ddd.json"),
            "ca.ddd.json": component(
                "CA",
                declare("local", "MA", conversion=enum_of("Mode_t", ("OFF", 0), ("ON", 1))),
                declare("local", "FA", conversion=enum_of("Flag_t", ("NO", 0), ("NONE", 0))),
            ),
            "cb.ddd.json": component(
                "CB", declare("local", "MB", conversion=enum_of("Mode_t", ("OFF", 0), ("IDLE", 0)))
            ),
        }
        assert judged(tmp_path, files, "ca.ddd.json", "enum-duplicate-value") == [
            ("cb.ddd.json", "enum-duplicate-value", "enum 'Mode_t': OFF, IDLE all have the value 0")
        ]

    def test_the_read_taking_an_axis_for_a_measurement_gone_is_refused_for_the_curve_let_in(
        self, tmp_path: Path
    ) -> None:
        """Under the default severities. Nothing writes `AX`: `RA`, read first, declares it a
        measurement, and `RB` an axis, a `definition-mismatch` on `RB`. `W` draws the curve `X`
        over it, a `reference-kind`, and `R`'s disagreement with `W` over `X` is never compared.
        Removing `RA` makes `AX` an axis, and the disagreement comes in, on `R`, as `AX`'s leaves
        `RB`."""
        files = {
            "p.ddd.json": project("P", "ra.ddd.json", "rb.ddd.json", "w.ddd.json", "r.ddd.json"),
            "ra.ddd.json": component("RA", declare("input", "AX", "uint16")),
            "rb.ddd.json": component("RB", axis("input", "AX")),
            "w.ddd.json": component("W", curve("output", "X", "AX")),
            "r.ddd.json": component("R", declare("input", "X", kind="curve", axis="AX")),
        }
        assert judged(tmp_path, files, "ra.ddd.json") == [
            (
                "r.ddd.json",
                "definition-mismatch",
                "'X' is declared differently by component 'R' than by 'W' "
                "(datatype: uint8 != uint16)",
            )
        ]

    def test_the_owner_gone_is_refused_for_the_disagreement_it_lets_in_though_fewer_are_left(
        self, tmp_path: Path
    ) -> None:
        """Under the default severities. `A` owns `X` and `Y`, its name sorting first, and
        holds no `definition-mismatch`. It states no limits for `X`, so the first declaration read
        that does, `R1`'s, is the one `B`, `R2` and `R3` differ from; and it draws `Y` over
        `NOPE`, which nobody declares, and `S`'s disagreement with `C` over `Y` is never compared.
        Removing `A` makes `B` the owner: only `R1` differs from its limits, reported on `R1` now,
        and `S`'s disagreement comes in - two errors, where three leave."""
        files = {
            "p.ddd.json": project(
                "P",
                "r1.ddd.json",
                "r2.ddd.json",
                "r3.ddd.json",
                "b.ddd.json",
                "c.ddd.json",
                "a.ddd.json",
                "s.ddd.json",
                "ax.ddd.json",
            ),
            "a.ddd.json": component("A", declare("output", "X"), curve("output", "Y", "NOPE")),
            "b.ddd.json": component("B", declare("output", "X", limits={"min": 0, "max": 20})),
            "r1.ddd.json": component("R1", declare("input", "X", limits={"min": 0, "max": 10})),
            "r2.ddd.json": component("R2", declare("input", "X", limits={"min": 0, "max": 20})),
            "r3.ddd.json": component("R3", declare("input", "X", limits={"min": 0, "max": 20})),
            "c.ddd.json": component("C", curve("output", "Y", "AX")),
            "s.ddd.json": component("S", declare("input", "Y", kind="curve", axis="AX")),
            "ax.ddd.json": component("AXO", axis("output", "AX")),
        }
        assert judged(tmp_path, files, "a.ddd.json") == [
            (
                "r1.ddd.json",
                "definition-mismatch",
                "'X' is declared differently by component 'R1' than by 'B' "
                "(limits: [0, 10] != [0, 20])",
            ),
            (
                "s.ddd.json",
                "definition-mismatch",
                "'Y' is declared differently by component 'S' than by 'C' "
                "(datatype: uint8 != uint16)",
            ),
        ]

    def test_the_owner_gone_lets_through_a_readers_disagreement_over_another_field(
        self, tmp_path: Path
    ) -> None:
        """The cost of counting per place, under the default severities: `W1` and `W2` both
        write `X`, `W1` owning it, its name sorting first, and `R` reads it with `W2`'s datatype
        and `W1`'s unit - a `definition-mismatch` with `W1` over its datatype, on `R`. Removing
        `W1` ends the writers' conflict and makes `W2` the owner, and `R`'s disagreement becomes
        one with `W2` over its unit: an error the project did not have, at the place the one it
        had leaves, so counted as that one and let through. The answer asserted is the one
        given."""
        files = {
            "p.ddd.json": project("P", "w1.ddd.json", "w2.ddd.json", "r.ddd.json"),
            "w1.ddd.json": writing("W1", "X", datatype="uint16", unit="rpm"),
            "w2.ddd.json": writing("W2", "X", datatype="uint32", unit="Nm"),
            "r.ddd.json": component("R", declare("input", "X", "uint32", unit="rpm")),
        }
        assert judged(tmp_path, files, "w1.ddd.json") == []


SAYS_PULLED_IN = (
    "sensors/a.ddd.json is part of this project already: the pattern 'sensors/*.ddd.json' "
    "brings it in"
)
SAYS_KIND = (
    "no file of kind 'project' can be created here; the kinds that can are component, types, "
    "units, constants, sections and rasters"
)
SAYS_NAME = (
    "'a.b' cannot name a new file: a name is one or more of the letters a to z and A to Z, the "
    "digits 0 to 9, '_' and '-', and .ddd.json is added to it"
)
SAYS_THERE = "a.ddd.json is there already, beside p.ddd.json"
SAYS_ITSELF = "p.ddd.json is this project's own description, which it cannot include"


def described(base: Path) -> Path:
    """The project description the tests below write, resolved as every plan resolves it."""
    return (base / "p.ddd.json").resolve()


def indexed(root: Path) -> Index:
    """The index of the project described at ``root``, as the analysis builds it."""
    workspace = load_workspace(root, DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def applied(root: Path, edits: Sequence[PlannedEdit]) -> Revision:
    """``edits`` made through the session, as ``POST /api/edit`` makes a plan - each file
    fingerprinted as it is on disk, a created one with none - and the project read and analysed
    again."""
    session = Session(root.parent)
    session.open(root)
    changes = [
        FileChange(
            edit.path,
            None if edit.creates else fingerprint(edit.path.read_bytes()),
            edit.operations,
        )
        for edit in edits
    ]
    revision, _ = session.edit(changes, "the files of the project")
    return revision


def errors_of(revision: Revision) -> list[tuple[str, str, str]]:
    """Every error the revision's project reports, by file, check and message."""
    return [
        (filed.file.name, filed.diagnostic.check, filed.diagnostic.message)
        for filed in revision.findings
        if filed.diagnostic.severity is Severity.ERROR
    ]


BARE: Final = {"project": {"name": "Bare"}}
"""A description with no ``includes``, which the format allows: ``docs/file_formats/project.rst``
calls it valid, and ``ddd check`` passes it."""


def creating(
    base: Path, kind: str, name: str, called: str | None = None, *, checks_units: bool = False
) -> tuple[PlannedEdit, ...]:
    """A file planned beside a project that loaded, of one component stating no unit: ``A``,
    in ``a.ddd.json``, whose name is taken."""
    built, root = built_of(base, **{"a.ddd.json": component("A")})
    units = unit_project(root / "p.ddd.json", [], {})
    return create_plan(
        root / "p.ddd.json", kind, name, called, ("A",), units, built, {}, checks_units=checks_units
    )


class TestIncludedEntries:
    """The root's ``includes`` as the loader's own rule reads them: each entry in order, the
    files it brings that exist, and the key its row is selected by."""

    def test_each_entry_in_order_with_what_it_reaches(self, tmp_path: Path) -> None:
        """A sub-project is one entry reaching one file: its own includes are not the root's."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "b.ddd.json", "sub/project.ddd.json", "a.ddd.json"),
                "a.ddd.json": component("A"),
                "b.ddd.json": component("B"),
                "sub/project.ddd.json": project("Sub", "c.ddd.json"),
                "sub/c.ddd.json": component("C"),
            },
        )
        a, b, sub = (
            (tmp_path / name).resolve()
            for name in ("a.ddd.json", "b.ddd.json", "sub/project.ddd.json")
        )
        assert included_entries(tmp_path / "p.ddd.json", {}) == (
            IncludedEntry(0, "b.ddd.json", True, b, (b,)),
            IncludedEntry(1, "sub/project.ddd.json", True, sub, (sub,)),
            IncludedEntry(2, "a.ddd.json", True, a, (a,)),
        )

    def test_a_pattern_lists_the_files_it_matched(self, tmp_path: Path) -> None:
        """In the loader's order, by path, and only what the pattern matches."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sensors/*.ddd.json"),
                "sensors/b.ddd.json": component("B"),
                "sensors/a.ddd.json": component("A"),
                "sensors/notes.json": {},
            },
        )
        sensors = (tmp_path / "sensors").resolve()
        assert included_entries(tmp_path / "p.ddd.json", {}) == (
            IncludedEntry(
                0,
                "sensors/*.ddd.json",
                False,
                (tmp_path / "sensors/*.ddd.json").resolve(),
                (sensors / "a.ddd.json", sensors / "b.ddd.json"),
            ),
        )

    @pytest.mark.parametrize(
        "entry", ["gone.ddd.json", "gone/*.ddd.json"], ids=["a path", "a pattern"]
    )
    def test_an_entry_whose_file_is_gone_names_nothing(self, tmp_path: Path, entry: str) -> None:
        """Focus 4: a plain entry naming no file is that missing file, which ``ddd check``
        reports ``file-not-found``, and one holding a wildcard is a pattern matching nothing,
        reported ``include-empty``. Either way it names nothing - ``names`` is False and
        ``files`` is empty - and nothing raises."""
        write_tree(tmp_path, {"p.ddd.json": project("P", entry)})
        (found,) = included_entries(tmp_path / "p.ddd.json", {})
        assert (found.index, found.entry, found.names, found.files) == (0, entry, False, ())
        assert found.key == (tmp_path / entry).resolve()

    def test_an_entry_naming_a_directory_names_nothing(self, tmp_path: Path) -> None:
        """A directory is no more a description file than a missing one - ``ddd check`` reports
        it ``file-not-found`` too - and none of the files in it is brought in."""
        write_tree(
            tmp_path, {"p.ddd.json": project("P", "sensors"), "sensors/a.ddd.json": component("A")}
        )
        assert included_entries(tmp_path / "p.ddd.json", {}) == (
            IncludedEntry(0, "sensors", False, (tmp_path / "sensors").resolve(), ()),
        )

    def test_an_entry_naming_a_file_is_that_file_whatever_it_spells(self, tmp_path: Path) -> None:
        """The loader tries an entry as a file before it reads it as a pattern: ``a[12]`` names
        the file of that name, and does not reach ``a1``."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a[12].ddd.json"),
                "a[12].ddd.json": component("A"),
                "a1.ddd.json": component("A1"),
            },
        )
        named = (tmp_path / "a[12].ddd.json").resolve()
        assert included_entries(tmp_path / "p.ddd.json", {}) == (
            IncludedEntry(0, "a[12].ddd.json", True, named, (named,)),
        )

    @pytest.mark.parametrize(
        "spelled", ["p.ddd.json", "sub/../p.ddd.json"], ids=["as it is", "through a directory"]
    )
    def test_the_project_description_is_never_among_a_patterns_files(
        self, tmp_path: Path, spelled: str
    ) -> None:
        """``*.ddd.json`` beside the description matches the description too, and the loader
        leaves it out, so that a project never includes itself. It is left out by its resolved
        path, which is why the description is resolved first, however it is spelled."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "*.ddd.json"),
                "a.ddd.json": component("A"),
                "sub/b.ddd.json": component("B"),
            },
        )
        a = (tmp_path / "a.ddd.json").resolve()
        assert included_entries(tmp_path / spelled, {}) == (
            IncludedEntry(0, "*.ddd.json", False, (tmp_path / "*.ddd.json").resolve(), (a,)),
        )

    def test_an_entry_that_is_no_string_is_no_row_and_the_others_keep_their_places(
        self, tmp_path: Path
    ) -> None:
        """The loader refuses such a list with a ``schema`` error. The entries that are strings
        are rows still, each at the index a finding filed at it names."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": {
                    "project": {"name": "P", "includes": ["a.ddd.json", 3, "b.ddd.json"]}
                },
                "a.ddd.json": component("A"),
                "b.ddd.json": component("B"),
            },
        )
        a, b = ((tmp_path / name).resolve() for name in ("a.ddd.json", "b.ddd.json"))
        assert included_entries(tmp_path / "p.ddd.json", {}) == (
            IncludedEntry(0, "a.ddd.json", True, a, (a,)),
            IncludedEntry(2, "b.ddd.json", True, b, (b,)),
        )

    @pytest.mark.parametrize(
        "text",
        ['{"project": {"name": "P", "includes": "a.ddd.json"}}', '{"project": {"name": "P", '],
        ids=["a string", "a description that does not parse"],
    )
    def test_includes_that_are_no_list_are_no_entries(self, tmp_path: Path, text: str) -> None:
        write_tree(tmp_path, {"p.ddd.json": text, "a.ddd.json": component("A")})
        assert included_entries(tmp_path / "p.ddd.json", {}) == ()


class TestCreate:
    """A file created beside the description and added to its includes in one plan, by the one
    recipe every plan creates a file by, :func:`ddd.lsp.units.created_beside`."""

    @pytest.mark.parametrize("kind", ["types", "constants", "sections", "rasters"])
    def test_a_vocabulary_file_is_created_declaring_nothing(
        self, tmp_path: Path, kind: str
    ) -> None:
        assert creating(tmp_path, kind, "shared") == (
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[1]", '"shared.ddd.json"'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "shared.ddd.json",
                (Operation("set", "", f'{{\n  "{kind}": []\n}}\n'),),
                creates=True,
            ),
        )

    def test_a_component_is_created_with_its_name_and_an_empty_interface(
        self, tmp_path: Path
    ) -> None:
        assert creating(tmp_path, "component", "pump", "Pump") == (
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[1]", '"pump.ddd.json"'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "pump.ddd.json",
                (
                    Operation(
                        "set",
                        "",
                        '{\n  "component": {\n    "name": "Pump",\n    "interface": []\n  }\n}\n',
                    ),
                ),
                creates=True,
            ),
        )

    def test_a_projects_first_units_file_lists_every_unit_it_states(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm"), declare("output", "Load", unit="%")
                ),
            },
        )
        units = unit_project(root / "p.ddd.json", [], {})
        planned = create_plan(
            root / "p.ddd.json", "units", "units", None, (), units, built, {}, checks_units=False
        )
        (made,) = [edit for edit in planned if edit.creates]
        assert made.path == described(tmp_path).parent / "units.ddd.json"
        # Parsed rather than compared as text: the layout is `created_beside`'s, pinned by
        # `test_unit_plans.TestCreatedBeside`.
        assert json.loads(made.operations[0].raw or "") == {
            "units": [{"unit": "%", "description": ""}, {"unit": "rpm", "description": ""}]
        }

    def test_a_unit_is_written_as_it_is_spelled(self, tmp_path: Path) -> None:
        """``°C`` arrives in the file as ``°C``, where json's default would write ``\\u00b0C``,
        as :func:`ddd.lsp.units.adopt_units` writes one."""
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Heat", unit="°C"))}
        )
        units = unit_project(root / "p.ddd.json", [], {})
        planned = create_plan(
            root / "p.ddd.json", "units", "units", None, (), units, built, {}, checks_units=False
        )
        (made,) = [edit for edit in planned if edit.creates]
        assert '"unit": "°C"' in (made.operations[0].raw or "")

    def test_a_units_file_of_a_project_a_sub_project_opted_in_is_created_empty(
        self, tmp_path: Path
    ) -> None:
        """A units file anywhere in the tree opts the whole project in, a sub-project's too, so
        the unit it lists, listed again in a new file of the root's, would be a
        ``duplicate-unit``. The root's own includes name no units file: what says the project
        is opted in is ``checks_units``, the tree's."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/project.ddd.json", "a.ddd.json"),
                "sub/project.ddd.json": project("Sub", "units.ddd.json"),
                "sub/units.ddd.json": {"units": [{"unit": "rpm", "description": ""}]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        root = tmp_path / "p.ddd.json"
        built = indexed(root)
        units = unit_project(root, [], {})
        assert (units.units_files, sorted(built.units)) == ((), ["rpm"])
        planned = create_plan(root, "units", "units", None, (), units, built, {}, checks_units=True)
        assert planned == (
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[2]", '"units.ddd.json"'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "units.ddd.json",
                (Operation("set", "", '{\n  "units": []\n}\n'),),
                creates=True,
            ),
        )

    def test_a_second_units_file_is_created_empty(self, tmp_path: Path) -> None:
        """The project is opted in already, so an empty file changes nothing it checks."""
        built, root = built_of(
            tmp_path,
            **{
                "units.ddd.json": {"units": [{"unit": "rpm", "description": ""}]},
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm"), declare("output", "Load", unit="%")
                ),
            },
        )
        units = unit_project(root / "p.ddd.json", [], {})
        planned = create_plan(
            root / "p.ddd.json", "units", "more", None, (), units, built, {}, checks_units=True
        )
        assert planned == (
            PlannedEdit(
                described(tmp_path).parent / "more.ddd.json",
                (Operation("set", "", '{\n  "units": []\n}\n'),),
                creates=True,
            ),
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[2]", '"more.ddd.json"'),),
            ),
        )

    def test_a_first_units_file_of_a_project_stating_no_unit_is_empty(self, tmp_path: Path) -> None:
        assert creating(tmp_path, "units", "units") == (
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[1]", '"units.ddd.json"'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "units.ddd.json",
                (Operation("set", "", '{\n  "units": []\n}\n'),),
                creates=True,
            ),
        )

    @pytest.mark.parametrize(
        ("listed", "position"),
        [
            pytest.param(("*.ddd.json",), 1, id="a pattern matching its name"),
            pytest.param(("a.ddd.json", "pump.ddd.json"), 2, id="an entry naming it missing"),
        ],
    )
    def test_a_file_an_entry_reaches_already_is_listed_by_its_name_again(
        self, tmp_path: Path, listed: tuple[str, ...], position: int
    ) -> None:
        """A file is created only where an entry of the edited ``includes`` names it as a file -
        a pattern is never expanded to find it - so the creation appends its own entry, and the
        file is listed twice: once by what reached it already, once by its name."""
        write_tree(tmp_path, {"p.ddd.json": project("P", *listed), "a.ddd.json": component("A")})
        root = tmp_path / "p.ddd.json"
        units = unit_project(root, [], {})
        planned = create_plan(
            root, "component", "pump", "Pump", ("A",), units, indexed(root), {}, checks_units=True
        )
        assert planned == (
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", f"project.includes[{position}]", '"pump.ddd.json"'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "pump.ddd.json",
                (
                    Operation(
                        "set",
                        "",
                        '{\n  "component": {\n    "name": "Pump",\n    "interface": []\n  }\n}\n',
                    ),
                ),
                creates=True,
            ),
        )

    def test_a_project_listing_no_includes_is_given_the_list_holding_the_file(
        self, tmp_path: Path
    ) -> None:
        """There is no list to insert into, and the edit engine refuses an insertion into none,
        so the key is set to a list holding the new file alone."""
        write_tree(tmp_path, {"p.ddd.json": BARE})
        root = tmp_path / "p.ddd.json"
        units = unit_project(root, [], {})
        planned = create_plan(
            root, "component", "pump", "Pump", (), units, indexed(root), {}, checks_units=False
        )
        assert planned == (
            PlannedEdit(
                described(tmp_path),
                (Operation("set", "project.includes", '["pump.ddd.json"]'),),
            ),
            PlannedEdit(
                described(tmp_path).parent / "pump.ddd.json",
                (
                    Operation(
                        "set",
                        "",
                        '{\n  "component": {\n    "name": "Pump",\n    "interface": []\n  }\n}\n',
                    ),
                ),
                creates=True,
            ),
        )

    def test_a_file_created_in_a_project_listing_no_includes_is_read_and_passes(
        self, tmp_path: Path
    ) -> None:
        """Made through the session, which creates a file only where the description's edited
        ``includes`` name it: the list set is such an edit, and the project read again passes."""
        write_tree(tmp_path, {"p.ddd.json": BARE})
        root = tmp_path / "p.ddd.json"
        units = unit_project(root, [], {})
        planned = create_plan(
            root, "component", "pump", "Pump", (), units, indexed(root), {}, checks_units=False
        )
        after = applied(root, planned)
        assert errors_of(after) == []
        assert [(file.path.name, file.kind, file.loaded) for file in after.files] == [
            ("p.ddd.json", "project", True),
            ("pump.ddd.json", "component", True),
        ]
        assert json.loads(root.read_text(encoding="utf-8")) == {
            "project": {"name": "Bare", "includes": ["pump.ddd.json"]}
        }

    @pytest.mark.parametrize(
        ("unread", "says"),
        [
            pytest.param(
                ("b.ddd.json",),
                "b.ddd.json did not load, so a first units file could not list every unit in use",
                id="one file",
            ),
            pytest.param(
                ("c.ddd.json", "b.ddd.json"),
                "b.ddd.json, c.ddd.json did not load, so a first units file could not list every "
                "unit in use",
                id="two files",
            ),
        ],
    )
    def test_a_first_units_file_is_refused_while_a_file_did_not_load(
        self, tmp_path: Path, unread: tuple[str, ...], says: str
    ) -> None:
        """What did not load may state a unit, and a first units file leaving it out would have
        it reported ``unknown-unit`` - the project failing in one click, which listing every
        unit is there to prevent. Refused as :func:`ddd.lsp.units.adoption` refuses, naming
        every file that did not load, in the order of their paths."""
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": '{"component": ',
                "c.ddd.json": '{"component": ',
            },
        )
        units = unit_project(root / "p.ddd.json", [root / name for name in unread], {})
        with pytest.raises(FileRefusalError) as refused:
            create_plan(
                root / "p.ddd.json",
                "units",
                "units",
                None,
                (),
                units,
                built,
                {},
                checks_units=False,
            )
        assert (refused.value.code, refused.value.message) == ("unreadable", says)

    def test_a_first_units_file_is_refused_where_the_project_was_not_read(
        self, tmp_path: Path
    ) -> None:
        """With no index there is no list of the units it states to write."""
        write_tree(
            tmp_path, {"p.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")}
        )
        units = unit_project(tmp_path / "p.ddd.json", [], {})
        with pytest.raises(FileRefusalError) as refused:
            create_plan(
                tmp_path / "p.ddd.json",
                "units",
                "units",
                None,
                (),
                units,
                None,
                {},
                checks_units=False,
            )
        assert (refused.value.code, refused.value.message) == (
            "unreadable",
            "p.ddd.json did not load, so a first units file could not list every unit in use",
        )

    def test_a_units_file_of_a_project_opted_in_is_created_though_a_file_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """Created empty, it lists nothing, so nothing that did not load can be missing from it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "b.ddd.json"),
                "units.ddd.json": {"units": []},
                "b.ddd.json": '{"component": ',
            },
        )
        units = unit_project(tmp_path / "p.ddd.json", [tmp_path / "b.ddd.json"], {})
        planned = create_plan(
            tmp_path / "p.ddd.json", "units", "more", None, (), units, None, {}, checks_units=True
        )
        assert planned == (
            PlannedEdit(
                described(tmp_path).parent / "more.ddd.json",
                (Operation("set", "", '{\n  "units": []\n}\n'),),
                creates=True,
            ),
            PlannedEdit(
                described(tmp_path),
                (Operation("insert", "project.includes[2]", '"more.ddd.json"'),),
            ),
        )

    @pytest.mark.parametrize(
        ("kind", "name", "called", "says"),
        [
            pytest.param("project", "sub", None, SAYS_KIND, id="a project"),
            pytest.param(
                "types",
                "sensors/a",
                None,
                "'sensors/a' cannot name a new file: a name is one or more of the letters a to z "
                "and A to Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it",
                id="a separator",
            ),
            pytest.param("types", "a.b", None, SAYS_NAME, id="a dot"),
            pytest.param(
                "types",
                "",
                None,
                "'' cannot name a new file: a name is one or more of the letters a to z and A to "
                "Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it",
                id="no name",
            ),
            pytest.param(
                "types",
                "été",
                None,
                "'été' cannot name a new file: a name is one or more of the letters a to z and A "
                "to Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it",
                id="letters beyond ascii",
            ),
            pytest.param("types", "a", None, SAYS_THERE, id="a file there already"),
            pytest.param(
                "component",
                "pump",
                "2Pump",
                "'2Pump' cannot name a component, not being a usable c identifier",
                id="no c identifier",
            ),
            pytest.param(
                "component",
                "pump",
                "int",
                "'int' cannot name a component, being reserved by c or by a header DDD generates",
                id="a c keyword",
            ),
            pytest.param(
                "component",
                "pump",
                "uint8_t",
                "'uint8_t' cannot name a component, being reserved by c or by a header DDD "
                "generates",
                id="a name stdint.h declares",
            ),
            pytest.param(
                "component",
                "pump",
                "_Pump",
                "'_Pump' cannot name a component, being reserved by c or by a header DDD generates",
                id="an underscore and a capital",
            ),
            pytest.param(
                "component",
                "pump",
                "Pump__x",
                "'Pump__x' cannot name a component, being reserved by c or by a header DDD "
                "generates",
                id="a double underscore",
            ),
            pytest.param(
                "component",
                "pump",
                "A",
                "this project has a component called 'A' already",
                id="a component's name taken",
            ),
            pytest.param(
                "component",
                "pump",
                "a",
                "this project has a component called 'A' already, and 'a' differs from it only "
                "in upper and lower case, so the two would ask for the same generated header",
                id="a name taken but for its case",
            ),
            pytest.param(
                "component",
                "pump",
                None,
                "a new component needs a name, besides its file's",
                id="no component's name",
            ),
        ],
    )
    def test_a_refused_creation_says_why(
        self, tmp_path: Path, kind: str, name: str, called: str | None, says: str
    ) -> None:
        with pytest.raises(FileRefusalError) as refused:
            creating(tmp_path, kind, name, called)
        assert (refused.value.code, refused.value.message) == ("invalid", says)

    @pytest.mark.parametrize(
        ("kind", "name", "called", "says"),
        [
            pytest.param("project", "a.b", None, SAYS_KIND, id="the kind before the name"),
            pytest.param("types", "a.b", None, SAYS_NAME, id="the name before a file there"),
            pytest.param("component", "a", "2A", SAYS_THERE, id="a file there before a component"),
        ],
    )
    def test_the_refusal_asked_first_is_the_one_said(
        self, tmp_path: Path, kind: str, name: str, called: str | None, says: str
    ) -> None:
        """Where two refusals apply, the reader hears the one asked first."""
        write_tree(tmp_path, {"a.b.ddd.json": component("B")})
        with pytest.raises(FileRefusalError) as refused:
            creating(tmp_path, kind, name, called)
        assert (refused.value.code, refused.value.message) == ("invalid", says)

    def test_a_name_taken_but_for_its_case_is_refused_whichever_case_each_is_in(
        self, tmp_path: Path
    ) -> None:
        """Both names lower-cased before they are compared, as the analysis groups components:
        neither ``PUMP`` nor ``Pump`` is lower case already."""
        built, root = built_of(tmp_path, **{"pump.ddd.json": component("Pump")})
        units = unit_project(root / "p.ddd.json", [], {})
        with pytest.raises(FileRefusalError) as refused:
            create_plan(
                root / "p.ddd.json",
                "component",
                "other",
                "PUMP",
                ("Pump",),
                units,
                built,
                {},
                checks_units=False,
            )
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "this project has a component called 'Pump' already, and 'PUMP' differs from it only "
            "in upper and lower case, so the two would ask for the same generated header",
        )

    @pytest.mark.parametrize(
        "called",
        [
            pytest.param("Int", id="a keyword with a capital"),
            pytest.param("uint8", id="a stdint.h name short of its _t"),
            pytest.param("_pump", id="an underscore and a small letter"),
            pytest.param("Pump_x", id="one underscore where two are reserved"),
            pytest.param("Speed", id="the name of a variable"),
            pytest.param("B_", id="a name taken but for an underscore"),
        ],
    )
    def test_a_component_the_refusals_let_through_leaves_a_passing_project_passing(
        self, tmp_path: Path, called: str
    ) -> None:
        """Beside each name refused, one that is not, made through the session into a project
        that passes: every check the refusals stand for passes it too, so the project passes
        still, with the component read under its name."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16")),
                "b.ddd.json": component("B", declare("input", "Speed", "uint16")),
            },
        )
        root = tmp_path / "p.ddd.json"
        before = Session(tmp_path).open(root)
        assert errors_of(before) == []
        units = unit_project(root, [], {})
        planned = create_plan(
            root,
            "component",
            "pump",
            called,
            ("A", "B"),
            units,
            before.index,
            {},
            checks_units=False,
        )
        after = applied(root, planned)
        assert errors_of(after) == []
        assert [(file.name, file.loaded) for file in after.files if file.kind == "component"] == [
            ("A", True),
            ("B", True),
            (called, True),
        ]


class TestAdd:
    """An existing file appended to the root's includes, its path as the reader wrote it: always
    a literal, never a pattern."""

    @pytest.mark.parametrize(
        "path",
        ["sensors/b.ddd.json", "./sensors/b.ddd.json", "sensors/été.ddd.json"],
        ids=["a path", "a path spelled from here", "a path of other letters"],
    )
    def test_an_existing_file_is_appended_as_written(self, tmp_path: Path, path: str) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A"),
                path: component("B"),
            },
        )
        assert add_plan(tmp_path / "p.ddd.json", path, {}) == FilePlan(
            (
                PlannedEdit(
                    described(tmp_path), (Operation("insert", "project.includes[1]", f'"{path}"'),)
                ),
            ),
            ("a.ddd.json", path),
        )

    @pytest.mark.parametrize(
        ("path", "code", "says"),
        [
            pytest.param(
                "missing.ddd.json",
                "not-found",
                "missing.ddd.json names no file; a file not there yet is created, not added",
                id="no file",
            ),
            pytest.param(
                "sensors",
                "not-found",
                "sensors names no file; a file not there yet is created, not added",
                id="a directory",
            ),
            pytest.param(
                "sensors/*.ddd.json",
                "not-found",
                "sensors/*.ddd.json names no file; a file not there yet is created, not added",
                id="a pattern",
            ),
            pytest.param("p.ddd.json", "invalid", SAYS_ITSELF, id="the description"),
            pytest.param(
                "sensors/../p.ddd.json",
                "invalid",
                "sensors/../p.ddd.json is this project's own description, which it cannot include",
                id="the description again",
            ),
            pytest.param(
                "a.ddd.json",
                "invalid",
                "a.ddd.json is part of this project already, as the entry 'a.ddd.json'",
                id="an entry",
            ),
            pytest.param(
                "./a.ddd.json",
                "invalid",
                "./a.ddd.json is part of this project already, as the entry 'a.ddd.json'",
                id="an entry spelled otherwise",
            ),
        ],
    )
    def test_a_refused_addition_says_why(
        self, tmp_path: Path, path: str, code: str, says: str
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A"),
                "sensors/b.ddd.json": component("B"),
            },
        )
        with pytest.raises(FileRefusalError) as refused:
            add_plan(tmp_path / "p.ddd.json", path, {})
        assert (refused.value.code, refused.value.message) == (code, says)

    def test_a_file_a_pattern_already_pulls_in_is_refused_naming_it(self, tmp_path: Path) -> None:
        """Focus 5: added again as a literal, the file would be listed twice and the pattern
        would still pull it in - so the reader is told the pattern already does."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sensors/*.ddd.json"),
                "sensors/a.ddd.json": component("A"),
            },
        )
        with pytest.raises(FileRefusalError) as refused:
            add_plan(tmp_path / "p.ddd.json", "sensors/a.ddd.json", {})
        assert refused.value.code == "invalid"
        assert refused.value.message == SAYS_PULLED_IN

    def test_the_description_is_refused_as_itself_though_an_entry_names_it(
        self, tmp_path: Path
    ) -> None:
        """Asked before whether an entry names it: a project listing its own description has it
        among an entry's files, and the reason no entry may name it is the one to hear."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "p.ddd.json")})
        with pytest.raises(FileRefusalError) as refused:
            add_plan(tmp_path / "p.ddd.json", "p.ddd.json", {})
        assert (refused.value.code, refused.value.message) == ("invalid", SAYS_ITSELF)

    def test_an_includes_that_is_no_list_takes_the_entry_at_its_front(self, tmp_path: Path) -> None:
        """Planned from the raw description, which nothing has validated: the edit engine
        refuses the insertion with a sentence of its own, where a length taken of ``3`` would
        have raised while the plan was made."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": {"project": {"name": "P", "includes": 3}},
                "a.ddd.json": component("A"),
            },
        )
        assert add_plan(tmp_path / "p.ddd.json", "a.ddd.json", {}) == FilePlan(
            (
                PlannedEdit(
                    described(tmp_path),
                    (Operation("insert", "project.includes[0]", '"a.ddd.json"'),),
                ),
            ),
            ("a.ddd.json",),
        )

    @pytest.mark.parametrize(
        "path",
        ["sensors/a.ddd.json", "sensors/été.ddd.json"],
        ids=["a path", "a path of other letters"],
    )
    def test_a_project_listing_no_includes_is_given_the_list_holding_the_entry(
        self, tmp_path: Path, path: str
    ) -> None:
        """Added as a created file's entry is, by the one rule both follow: the key set to a
        list holding the entry alone, as written, which is the list the change is judged by as
        well."""
        write_tree(tmp_path, {"p.ddd.json": BARE, path: component("A")})
        assert add_plan(tmp_path / "p.ddd.json", path, {}) == FilePlan(
            (
                PlannedEdit(
                    described(tmp_path),
                    (Operation("set", "project.includes", f'["{path}"]'),),
                ),
            ),
            (path,),
        )

    def test_a_file_added_to_a_project_listing_no_includes_is_read_and_passes(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {"p.ddd.json": BARE, "sensors/a.ddd.json": component("A")})
        root = tmp_path / "p.ddd.json"
        after = applied(root, add_plan(root, "sensors/a.ddd.json", {}).edits)
        assert errors_of(after) == []
        assert [(file.path.name, file.kind, file.loaded) for file in after.files] == [
            ("p.ddd.json", "project", True),
            ("a.ddd.json", "component", True),
        ]

    def test_the_description_is_refused_however_the_project_is_spelled(
        self, tmp_path: Path
    ) -> None:
        """Compared by its resolved path, the project's as well as the file's."""
        write_tree(tmp_path, {"p.ddd.json": project("P"), "sub/b.ddd.json": component("B")})
        with pytest.raises(FileRefusalError) as refused:
            add_plan(tmp_path / "sub" / ".." / "p.ddd.json", "p.ddd.json", {})
        assert (refused.value.code, refused.value.message) == ("invalid", SAYS_ITSELF)


class TestRemove:
    """An entry taken out of the root's includes by its row's key. The file stays on disk."""

    def test_a_literal_entry_is_taken_out(self, tmp_path: Path) -> None:
        """No entry left brings the file in, so it leaves the project: nothing keeps it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A"),
                "b.ddd.json": component("B"),
                "c.ddd.json": component("C"),
            },
        )
        key = (tmp_path / "b.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[1]"),)),),
            ("a.ddd.json", "c.ddd.json"),
            kept_by=None,
            removed=("b.ddd.json",),
        )

    def test_a_pattern_entry_is_taken_out_whole(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "sensors/*.ddd.json"),
                "a.ddd.json": component("A"),
                "sensors/b.ddd.json": component("B"),
                "sensors/c.ddd.json": component("C"),
            },
        )
        key = (tmp_path / "sensors/*.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[1]"),)),),
            ("a.ddd.json",),
            removed=("sensors/*.ddd.json",),
        )

    @pytest.mark.parametrize(
        "entry", ["gone.ddd.json", "gone/*.ddd.json"], ids=["a path", "a pattern"]
    )
    def test_an_entry_whose_file_is_gone_is_taken_out(self, tmp_path: Path, entry: str) -> None:
        """Focus 4: an entry naming nothing is a row of its own, removed by its own key."""
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", entry, "a.ddd.json"), "a.ddd.json": component("A")},
        )
        key = (tmp_path / entry).resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[0]"),)),),
            ("a.ddd.json",),
            removed=(entry,),
        )

    def test_an_entry_listed_twice_is_taken_out_everywhere(self, tmp_path: Path) -> None:
        """Two spellings of one file are one key, and removing its row is to take the file out
        of the project, so every entry naming it goes: the last first, since the edit engine
        makes a file's operations in turn, and with ``[0]`` gone first the other would be
        ``[1]``."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "./a.ddd.json"),
                "a.ddd.json": component("A"),
                "b.ddd.json": component("B"),
            },
        )
        key = (tmp_path / "a.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (
                PlannedEdit(
                    described(tmp_path),
                    (
                        Operation("remove", "project.includes[2]"),
                        Operation("remove", "project.includes[0]"),
                    ),
                ),
            ),
            ("b.ddd.json",),
            removed=("a.ddd.json", "./a.ddd.json"),
        )

    def test_a_file_a_pattern_pulled_in_is_refused_naming_the_pattern(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "sensors/*.ddd.json"),
                "a.ddd.json": component("A"),
                "sensors/b.ddd.json": component("B"),
                "sensors/c.ddd.json": component("C"),
            },
        )
        with pytest.raises(FileRefusalError) as refused:
            remove_plan(tmp_path / "p.ddd.json", (tmp_path / "sensors/b.ddd.json").resolve(), {})
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "b.ddd.json has no entry of its own: the pattern 'sensors/*.ddd.json' brings it in, "
            "and only the whole pattern can be removed",
        )

    @pytest.mark.parametrize(
        ("path", "says"),
        [
            pytest.param(
                "loose.ddd.json",
                "no entry of p.ddd.json's includes names loose.ddd.json, and none of its patterns "
                "matches it",
                id="a file beside it",
            ),
            pytest.param(
                "sub/c.ddd.json",
                "no entry of p.ddd.json's includes names c.ddd.json, and none of its patterns "
                "matches it",
                id="a file a sub-project includes",
            ),
        ],
    )
    def test_a_path_not_part_of_the_project_is_not_found(
        self, tmp_path: Path, path: str, says: str
    ) -> None:
        """Nor is a file a sub-project includes: its entry is the sub-project's, which opening
        the sub-project changes."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/project.ddd.json"),
                "sub/project.ddd.json": project("Sub", "c.ddd.json"),
                "sub/c.ddd.json": component("C"),
                "loose.ddd.json": component("L"),
            },
        )
        with pytest.raises(FileRefusalError) as refused:
            remove_plan(tmp_path / "p.ddd.json", (tmp_path / path).resolve(), {})
        assert (refused.value.code, refused.value.message) == ("not-found", says)

    def test_a_key_spelled_through_a_link_takes_out_the_entry_it_resolves_to(
        self, tmp_path: Path
    ) -> None:
        """A key is compared resolved, as :func:`included_entries` makes one: `link/b.ddd.json`
        is `lib/b.ddd.json`'s key, spelled through a link to its directory."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "lib/b.ddd.json"),
                "a.ddd.json": component("A"),
                "lib/b.ddd.json": component("B"),
            },
        )
        directory_link(tmp_path / "link", tmp_path / "lib")
        assert remove_plan(
            tmp_path / "p.ddd.json", tmp_path / "link" / "b.ddd.json", {}
        ) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[1]"),)),),
            ("a.ddd.json",),
            removed=("lib/b.ddd.json",),
        )

    def test_a_key_ending_in_a_link_is_refused_naming_the_link(self, tmp_path: Path) -> None:
        """Named as it was sent, never by what it resolves to: `elsewhere` leads to `outside`,
        a directory beside the project's, and the refusal names only what the caller wrote."""
        write_tree(
            tmp_path,
            {
                "served/p.ddd.json": project("P", "a.ddd.json"),
                "served/a.ddd.json": component("A"),
                "outside/secret.ddd.json": component("S"),
            },
        )
        directory_link(tmp_path / "served" / "elsewhere", tmp_path / "outside")
        with pytest.raises(FileRefusalError) as refused:
            remove_plan(tmp_path / "served" / "p.ddd.json", tmp_path / "served" / "elsewhere", {})
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "no entry of p.ddd.json's includes names elsewhere, and none of its patterns "
            "matches it",
        )

    def test_a_key_ending_in_a_link_to_a_patterns_file_is_refused_naming_the_link(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The pattern's refusal names the key as it was sent too. Only a link to a file ends in
        a file a pattern brings in, and making one takes a privilege an ordinary Windows account
        does not hold - a junction, the portable link, leads to a directory - so the key is made
        to resolve as it would through one: `alias.ddd.json` to `sensors/b.ddd.json`."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "sensors/*.ddd.json"),
                "a.ddd.json": component("A"),
                "sensors/b.ddd.json": component("B"),
            },
        )
        alias = tmp_path / "alias.ddd.json"
        target = (tmp_path / "sensors" / "b.ddd.json").resolve()
        resolving = file_plans.resolve_path
        monkeypatch.setattr(
            file_plans, "resolve_path", lambda path: target if path == alias else resolving(path)
        )
        with pytest.raises(FileRefusalError) as refused:
            remove_plan(tmp_path / "p.ddd.json", alias, {})
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "alias.ddd.json has no entry of its own: the pattern 'sensors/*.ddd.json' brings it "
            "in, and only the whole pattern can be removed",
        )

    def test_a_literal_entry_a_pattern_also_matches_is_taken_out_naming_the_pattern(
        self, tmp_path: Path
    ) -> None:
        """Its key is its row's, so it is the entry removed. The pattern left matches the file
        still and keeps it in the project, and the plan names it for the reader to be told."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sensors/a.ddd.json", "sensors/*.ddd.json"),
                "sensors/a.ddd.json": component("A"),
            },
        )
        key = (tmp_path / "sensors/a.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[0]"),)),),
            ("sensors/*.ddd.json",),
            kept_by="sensors/*.ddd.json",
            removed=("sensors/a.ddd.json",),
        )

    def test_a_pattern_left_matching_other_files_keeps_nothing(self, tmp_path: Path) -> None:
        """What keeps a file is a pattern left that brings it in, not any pattern left."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "sensors/*.ddd.json"),
                "a.ddd.json": component("A"),
                "sensors/b.ddd.json": component("B"),
            },
        )
        key = (tmp_path / "a.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (PlannedEdit(described(tmp_path), (Operation("remove", "project.includes[0]"),)),),
            ("sensors/*.ddd.json",),
            kept_by=None,
            removed=("a.ddd.json",),
        )

    def test_the_first_pattern_left_bringing_in_a_file_listed_twice_is_named(
        self, tmp_path: Path
    ) -> None:
        """Both spellings go, and neither is taken for what keeps the file: of the entries
        left, ``b.ddd.json`` names another file, and of the two patterns matching it the first
        is named."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P", "a.ddd.json", "b.ddd.json", "./a.ddd.json", "*.ddd.json", "a*.ddd.json"
                ),
                "a.ddd.json": component("A"),
                "b.ddd.json": component("B"),
            },
        )
        key = (tmp_path / "a.ddd.json").resolve()
        assert remove_plan(tmp_path / "p.ddd.json", key, {}) == FilePlan(
            (
                PlannedEdit(
                    described(tmp_path),
                    (
                        Operation("remove", "project.includes[2]"),
                        Operation("remove", "project.includes[0]"),
                    ),
                ),
            ),
            ("b.ddd.json", "*.ddd.json", "a*.ddd.json"),
            kept_by="*.ddd.json",
            removed=("a.ddd.json", "./a.ddd.json"),
        )


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
