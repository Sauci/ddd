"""The Files tab's own rules: what a change of the root project's ``includes`` would break."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

import ddd.file_plans as file_plans
from conftest import build_record, component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.file_plans import Pair, new_errors
from ddd.gui.session import Session, findings_with
from ddd.lsp.diagnostics import finding_identity, run_project

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


class TestAMirrorMoving:
    """A clash ddd reports against one of the declarations taking part - the owner, the first
    read, the first copy of an enum met, the raster whose name sorts first - and mirrors onto that
    one. Where a removal changes which declaration that is, and every finding ``ddd check``
    reports stays where it was, reworded or not, or leaves, only the mirrors move, and the removal
    is allowed."""

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
    onto a place without an error of its check and severity, it is refused, harmless as it is."""

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


class TestAClashARemovalBrings:
    """A removal can bring in an error the project does not have while an error of its check
    leaves from another place. Counted each at its own place, the one does not hide the other:
    each removal here is refused."""

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
        """H1: `W1` owns `C`, drawn over its own `Ax1`, and reads `L`'s private `T2`; `W2` writes
        `C` over `T2`. Removing `W1` hands `C` to `W2`, and `C` reaches the dictionary bound to
        `T2` - a conflict the project did not have, while `W1`'s own read of `T2` leaves with
        it."""
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
        """H1b: `K1` declares `C` local, over its own axis, and `K2` writes `C` too, over `L`'s
        private `T2` - the conflict the project has. Removing `K1` is the natural fix, and it
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
        """H2, `enum-duplicate-value` raised to an error by the build: `CA` holds the first copy
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
        """T5, under the default severities. Nothing writes `AX`: `RA`, read first, declares it a
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
        """E1, under the default severities. `A` owns `X` and `Y`, its name sorting first, and
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
