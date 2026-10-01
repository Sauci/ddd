"""The project ddd gui has open: what it finds, what a revision holds, and how it follows disk."""

from __future__ import annotations

import io
import json
import re
import shutil
import stat
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

import ddd.gui.session as session_module
from conftest import (
    EXAMPLES,
    Gated,
    begun,
    build_record,
    component,
    declare,
    first_revision,
    landed,
    project,
    stopped,
    write_tree,
)
from ddd.diagnostics import Severity, SeverityPolicy, UnknownCheckError
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    EditError,
    FileChange,
    Operation,
    fingerprint,
)
from ddd.gui import session as module
from ddd.gui.session import (
    MAX_UNDO,
    Filed,
    NoProjectError,
    NotAnalysedError,
    NotInProjectError,
    Revision,
    Session,
    Snapshot,
    find_projects,
    findings_with,
)
from ddd.lsp.diagnostics import Run, run_build

REGISTERING_PLUGIN = """
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    return None


PLUGIN = Plugin(
    name="demo",
    checks=(CheckInfo("demo/tagged", Severity.WARNING, "a demonstration check"),),
    check=check,
)
"""

UNPLACED_PLUGIN = """
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    context.bag.add("loose/unplaced", "said of no place in the project")


PLUGIN = Plugin(
    name="loose",
    checks=(CheckInfo("loose/unplaced", Severity.ERROR, "a finding with no place"),),
    check=check,
)
"""
"""A plugin whose check reports a finding without a location, which is filed on whichever file
the grouping falls back to."""

UNPARSED = (
    "{",
    '{"component": {"name": "B", "interface": [], "limit": NaN}}',
    '{"component": {"name": "B", "name": "C", "interface": []}}',
)
"""A component that is not json as the loader reads it: cut short, holding ``NaN``, and spelling
a key twice - the last two being json python's own parser reads."""


@pytest.fixture
def shared(tmp_path: Path) -> Path:
    """A producer and a consumer of one variable, agreeing; returns the project file."""
    write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
        },
    )
    return tmp_path / "p.ddd.json"


def unit_of_b(path: Path, unit: str) -> FileChange:
    target = path.parent / "b.ddd.json"
    pointer = "component.interface[0].definition.unit"
    return FileChange(
        target, fingerprint(target.read_bytes()), (Operation("set", pointer, f'"{unit}"'),)
    )


def mismatches(session: Session) -> int:
    """How many ``definition-mismatch`` findings the newest revision shows."""
    revision = session.revision
    assert revision is not None
    return sum(1 for filed in revision.findings if filed.diagnostic.check == "definition-mismatch")


def opened_and_settled(project_file: Path, poll_interval: float = 1.0) -> Session:
    """A session on the project, past any analysis more that opening it costs: one, where a
    sub-project's files had no stamp before the first analysis read them, and none for a flat
    project, whose files opening stamps."""
    session = Session(project_file.parent, poll_interval=poll_interval)
    session.open(project_file)
    session.poll()
    return session


def saving_while_analysing(file: Path, unit: bytes) -> Callable[..., Run]:
    """``run_project``, and another editor saving the first unit of ``file`` as ``unit`` once the
    analysis has read the files but before the session has its answer."""
    real = module.run_project

    def run(project_file: Path, *, includes: Sequence[str] | None = None) -> Run:
        answer = real(project_file, includes=includes)
        saved = re.sub(rb'"unit": "[^"]*"', b'"unit": ' + unit, file.read_bytes(), count=1)
        file.write_bytes(saved)
        return answer

    return run


NUL_ENTRY = "b\u0000.ddd.json"
"""An include entry naming a path no system lets a program even look at: it holds a NUL byte."""


def unreachable(base: Path) -> Path:
    """A project including a component and :data:`NUL_ENTRY`; returns the project file."""
    write_tree(
        base,
        {
            "p.ddd.json": project("P", "a.ddd.json", NUL_ENTRY),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
        },
    )
    return base / "p.ddd.json"


def unreadable(project_file: Path) -> tuple[str, str, str]:
    """The one finding a revision of :func:`unreachable`'s project carries - its file, its check
    and its words - the reason given in Python's own words, which are the platform's."""
    path = project_file.resolve().parent / NUL_ENTRY
    with pytest.raises(ValueError) as refused:
        path.read_text(encoding="utf-8-sig")
    return ("p.ddd.json", "file-not-found", f"cannot read '{path.as_posix()}': {refused.value}")


def findings_of(revision: Revision) -> list[tuple[str, str, str]]:
    return [(f.file.name, f.diagnostic.check, f.diagnostic.message) for f in revision.findings]


class TestFindingProjects:
    def test_project_descriptions_are_found_and_components_are_not(self, shared: Path) -> None:
        found = find_projects(shared.parent)
        assert [(p.path, p.name, p.images) for p in found.projects] == [(shared.resolve(), "P", ())]
        assert found.root == shared.parent.resolve()

    def test_the_walk_skips_hidden_directories_node_modules_and_build_trees(
        self, tmp_path: Path
    ) -> None:
        for directory in (".git", "node_modules", "build", "cmake-build-debug", "out", "src"):
            write_tree(tmp_path / directory, {"p.ddd.json": project(directory)})
        assert [p.name for p in find_projects(tmp_path).projects] == ["src"]

    def test_the_walk_goes_four_directories_deep_and_no_further(self, tmp_path: Path) -> None:
        write_tree(tmp_path / "1/2/3/4", {"p.ddd.json": project("four")})
        write_tree(tmp_path / "1/2/3/4/5", {"p.ddd.json": project("five")})
        assert [p.name for p in find_projects(tmp_path).projects] == ["four"]

    def test_a_file_that_is_not_json_is_not_a_project(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": "{", "q.ddd.json": '{"project": 7}'})
        assert find_projects(tmp_path).projects == ()

    def test_a_build_record_names_its_project_and_image(self, shared: Path) -> None:
        build_record(shared.parent, shared, image="firmware.elf")
        (found,) = find_projects(shared.parent).projects
        assert found.images == ("firmware.elf",)

    def test_a_project_a_record_names_that_does_not_exist_is_offered_without_a_name(
        self, tmp_path: Path
    ) -> None:
        build_record(tmp_path, tmp_path / "gone.ddd.json")
        (found,) = find_projects(tmp_path).projects
        assert (found.path.name, found.name) == ("gone.ddd.json", None)

    def test_a_record_that_cannot_be_used_is_reported_with_its_reason(self, shared: Path) -> None:
        build_record(shared.parent, shared, severity=["no-such-check=error"])
        with pytest.raises(UnknownCheckError) as expected:
            SeverityPolicy.from_strings(["no-such-check=error"], strict=False)
        found = find_projects(shared.parent)
        assert [reason for _, reason in found.refused] == [str(expected.value)]


class TestOpening:
    def test_a_file_that_is_not_a_project_description_is_refused(self, shared: Path) -> None:
        with pytest.raises(ValueError, match="not a project description"):
            Session(shared.parent).open(shared.parent / "a.ddd.json")

    def test_a_revision_describes_every_file_and_resolves_the_dictionary(
        self, shared: Path
    ) -> None:
        revision = first_revision(shared.parent, shared)
        described = {f.path.name: (f.kind, f.name, f.loaded) for f in revision.files}
        assert described == {
            "p.ddd.json": ("project", "P", True),
            "a.ddd.json": ("component", "A", True),
            "b.ddd.json": ("component", "B", True),
        }
        assert revision.number == 1
        assert revision.dictionary is not None
        assert all(f.fingerprint == fingerprint(f.path.read_bytes()) for f in revision.files)

    def test_a_disagreement_is_filed_on_both_sides(self, shared: Path) -> None:
        (shared.parent / "b.ddd.json").write_text(
            (shared.parent / "b.ddd.json").read_text(encoding="utf-8").replace("rpm", "Hz"),
            encoding="utf-8",
        )
        revision = first_revision(shared.parent, shared)
        filed = {
            f.file.name for f in revision.findings if f.diagnostic.check == "definition-mismatch"
        }
        assert filed == {"a.ddd.json", "b.ddd.json"}
        counts = {f.path.name: f.errors for f in revision.files}
        assert counts["a.ddd.json"] == counts["b.ddd.json"] == 1

    def test_opening_again_makes_a_newer_revision(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        session.open(shared)
        assert session.revision is not None and session.revision.number == 2

    def test_a_build_records_severities_and_plugin_checks_apply(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "tools/demo_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["unused-output=error"])
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        assert [b.image for b in revision.builds] == ["firmware.elf"]
        unused = [f.diagnostic for f in revision.findings if f.diagnostic.check == "unused-output"]
        assert [d.severity.value for d in unused] == ["error"]
        assert [info.identifier for info in revision.checks] == ["demo/tagged"]
        kinds = {f.path.name: f.kind for f in revision.files}
        assert kinds["demo_plugin.py"] == "plugin"

    @pytest.mark.parametrize("content", UNPARSED)
    def test_a_file_that_does_not_parse_is_listed_as_not_loaded(
        self, shared: Path, content: str
    ) -> None:
        (shared.parent / "b.ddd.json").write_text(content, encoding="utf-8")
        revision = first_revision(shared.parent, shared)
        broken = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert (broken.kind, broken.name, broken.loaded) == ("unknown", None, False)
        assert revision.dictionary is None

    def test_a_file_that_cannot_be_read_is_described_as_empty(self, tmp_path: Path) -> None:
        described = module._described(tmp_path / "gone.ddd.json", [])
        assert (described.kind, described.fingerprint) == ("unknown", fingerprint(b""))

    def test_a_description_of_no_known_kind_is_unknown(self) -> None:
        assert module.kind_of(Path("x.ddd.json"), {"other": 1}) == "unknown"


def test_a_revision_keeps_the_index_its_analysis_built(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
        },
    )
    revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
    assert revision.index is not None
    assert len(revision.index.declarations["Speed"]) == 2


class TestFollowingTheDisk:
    def test_nothing_is_polled_while_no_project_is_open(self, tmp_path: Path) -> None:
        assert Session(tmp_path).poll() is False

    def test_a_file_changed_on_disk_makes_a_new_revision(self, shared: Path) -> None:
        session = opened_and_settled(shared)
        (shared.parent / "b.ddd.json").write_text(
            (shared.parent / "b.ddd.json").read_text(encoding="utf-8").replace("rpm", "Hz") + " ",
            encoding="utf-8",
        )
        assert session.poll() is True
        assert session.revision is not None and session.revision.number == 2

    def test_a_file_removed_from_disk_makes_a_new_revision(self, shared: Path) -> None:
        session = opened_and_settled(shared)
        (shared.parent / "b.ddd.json").unlink()
        assert session.poll() is True

    def test_a_save_made_while_opening_analyses_is_picked_up_by_the_next_poll(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = Session(shared.parent)
        consumer = shared.parent / "b.ddd.json"
        monkeypatch.setattr(module, "run_project", saving_while_analysing(consumer, b'"Hz"'))
        session.open(shared)
        monkeypatch.undo()
        assert mismatches(session) == 0
        assert session.poll() is True
        assert mismatches(session) == 2

    def test_a_save_made_while_a_poll_analyses_is_picked_up_by_the_next_poll(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The stamps a revision keeps are the ones taken before its analysis read the files.

        Taken after it, a save landing while the analysis ran was already in them: no later
        poll saw a change, and the page kept the findings of bytes no longer on disk.
        """
        session = opened_and_settled(shared)
        consumer = shared.parent / "b.ddd.json"
        consumer.write_bytes(consumer.read_bytes().replace(b'"rpm"', b'"Hz"'))
        monkeypatch.setattr(module, "run_project", saving_while_analysing(consumer, b'"rpm"'))
        assert session.poll() is True
        monkeypatch.undo()
        assert mismatches(session) == 2
        assert session.poll() is True
        assert mismatches(session) == 0

    def test_a_save_made_while_an_edit_is_analysed_is_picked_up_by_the_next_poll(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = opened_and_settled(shared)
        consumer = shared.parent / "b.ddd.json"
        monkeypatch.setattr(module, "run_project", saving_while_analysing(consumer, b'"rpm"'))
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        monkeypatch.undo()
        assert mismatches(session) == 2
        assert session.poll() is True
        assert mismatches(session) == 0

    def test_a_save_made_to_a_file_the_analysis_brought_in_is_picked_up_by_the_next_poll(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file the project did not have when the poll stamped its files has no stamp of its
        own, so the next poll analyses once more - which is what catches a save made to it while
        the analysis that brought it in ran."""
        session = opened_and_settled(shared)
        write_tree(
            shared.parent,
            {
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
            },
        )
        newcomer = shared.parent / "c.ddd.json"
        monkeypatch.setattr(module, "run_project", saving_while_analysing(newcomer, b'"Hz"'))
        assert session.poll() is True
        monkeypatch.undo()
        assert mismatches(session) == 0
        assert session.poll() is True
        assert mismatches(session) == 2

    def test_a_waiting_request_gets_what_the_session_says_as_soon_as_it_changes(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        threading.Timer(0.05, session.open, args=(shared,)).start()
        assert session.wait(2, timeout=5).version > 2

    def test_a_waiting_request_gets_what_the_session_says_when_nothing_changes(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        snapshot = session.wait(2, timeout=0.05)
        assert snapshot.version == 2
        assert snapshot.revision is not None and snapshot.revision.number == 1

    def test_the_polling_thread_notices_a_change(self, shared: Path) -> None:
        session = opened_and_settled(shared, poll_interval=0.02)
        session.start_polling()
        session.start_polling()  # a second start keeps the one thread
        try:
            (shared.parent / "a.ddd.json").write_text("{}", encoding="utf-8")
            assert session.wait(2, timeout=5).version > 2
            revision = landed(session).revision
            assert revision is not None and revision.number == 2
        finally:
            session.stop()

    def test_a_poll_that_fails_says_so_and_polling_goes_on(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = Session(shared.parent, poll_interval=0.01)
        session.open(shared)
        calls = []

        def failing() -> bool:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            session._stopping.set()
            return False

        monkeypatch.setattr(session, "poll", failing)
        session._poll_until_stopped()
        assert "checking the project again failed: boom" in capsys.readouterr().err
        assert len(calls) == 2

    def test_stopping_a_session_that_never_polled_is_harmless(self, tmp_path: Path) -> None:
        Session(tmp_path).stop()


class Stepped(Session):
    """A session whose analyses announce that they have begun, as a :class:`Gated` one's do, and
    each wait for a go of its own: what lets a test let one analysis finish while the next one
    waits."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, poll_interval=3600)
        self.begun = threading.Semaphore(0)
        self.goes = (threading.Event(), threading.Event(), threading.Event())
        self.analyses = 0

    def _analysed(self, project: Path) -> Revision:
        go = self.goes[self.analyses]
        self.analyses += 1
        self.begun.release()
        assert go.wait(timeout=10), "the test never let this analysis go"
        return super()._analysed(project)


class SecondFails(Gated):
    """A gated session whose second analysis raises ``boom``."""

    def _analysed(self, project: Path) -> Revision:
        revision = super()._analysed(project)
        if self.analyses == 2:
            raise RuntimeError("boom")
        return revision


class TestTheAnalyser:
    def test_an_edit_answers_before_its_analysis_and_the_next_revision_includes_it(
        self, shared: Path
    ) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            session.gate.clear()
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            revision = session.revision
            assert revision is not None and revision.edits < at and mismatches(session) == 0
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == at and mismatches(session) == 2
        finally:
            session.gate.set()
            stopped(session)

    def test_edits_landing_while_an_analysis_runs_make_one_analysis_more_not_one_each(
        self, shared: Path
    ) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            session.settled(timeout=10)
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "one")
            begun(session)
            last = 0
            for unit in ("kPa", "Nm", "rpm"):
                last, _ = session.edit([unit_of_b(shared, unit)], unit)
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == last
            assert session.analyses == 3  # opening, the first edit, and the three after it
        finally:
            session.gate.set()
            stopped(session)

    def test_a_revision_counts_the_edits_on_disk_when_its_analysis_began(
        self, shared: Path
    ) -> None:
        """Not those written while it ran, whatever it happened to read: the analysis of the
        first edit here reads the disk after the second is written, and still counts only the
        first. The one after it counts the second."""
        session = Stepped(shared.parent)
        opening, first, second = session.goes
        opening.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            later, _ = session.edit([unit_of_b(shared, "kPa")], "the unit of Speed")
            first.set()
            begun(session)  # the second edit's analysis, begun once the first edit's is in
            revision = session.revision
            assert revision is not None and (revision.number, revision.edits) == (2, at)
            second.set()
            settled = session.settled(timeout=10)
            assert settled is not None and (settled.number, settled.edits) == (3, later)
        finally:
            for go in session.goes:
                go.set()
            stopped(session)

    def test_the_poll_does_not_take_an_edits_own_write_for_a_change_its_analysis_missed(
        self, shared: Path
    ) -> None:
        """While an analysis runs, the stamps it took before it read a file - after the edit's
        write - stand in for the last revision's."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.poll() is False
            session.gate.set()
            assert session.settled(timeout=10) is not None
            assert session.analyses == 2
        finally:
            session.gate.set()
            stopped(session)

    def test_another_project_opened_answers_for_none_of_the_last_ones_files(
        self, shared: Path
    ) -> None:
        """Until its own first analysis lands it has no revision, so that an edit of a file of
        the project open before it is refused as not analysed yet rather than written; and its
        stamps are its own, so that a save of such a file is no change of the project open."""
        write_tree(shared.parent, {"q.ddd.json": project("Q", "a.ddd.json")})
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            landed(session)
            session.gate.clear()
            session.open(shared.parent / "q.ddd.json")
            begun(session)
            assert session.revision is None
            b = shared.parent / "b.ddd.json"
            before = b.read_bytes()
            with pytest.raises(NotAnalysedError):
                session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert b.read_bytes() == before
            b.write_bytes(before + b" ")
            assert session.poll() is False
        finally:
            session.gate.set()
            stopped(session)

    def test_a_project_opened_while_another_is_analysed_throws_that_analysis_away(
        self, shared: Path
    ) -> None:
        write_tree(shared.parent, {"q.ddd.json": project("Q", "a.ddd.json")})
        other = shared.parent / "q.ddd.json"
        session = Gated(shared.parent)
        session.start()
        try:
            session.open(shared)
            begun(session)
            session.open(other)
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.project == other.resolve()
            assert (settled.number, session.analyses) == (1, 2)
        finally:
            session.gate.set()
            stopped(session)

    def test_an_analysis_failing_on_the_thread_is_printed_and_asked_for_again(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class Failing(Gated):
            def _analysed(self, project: Path) -> Revision:
                revision = super()._analysed(project)
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return revision

        session = Failing(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            first = session.settled(timeout=10)
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert session.settled(timeout=10) is first
            assert capsys.readouterr().err.splitlines()[-1] == (
                "ddd gui: analysing the project failed: boom"
            )
            assert session.poll() is True
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == at and mismatches(session) == 2
        finally:
            stopped(session)

    def test_where_no_analyser_runs_a_failing_analysis_is_raised_to_the_call_that_asked(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A session nobody started makes the analysis in the call that asked for it, as every
        call did before the analyser: the failure is that call's to report, printed by nothing
        here, and leaves no analysis running - the next poll asks again."""

        class Failing(Session):
            analyses = 0

            def _analysed(self, project: Path) -> Revision:
                self.analyses += 1
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return super()._analysed(project)

        session = Failing(shared.parent)
        session.open(shared)
        first = session.revision
        with pytest.raises(RuntimeError, match=r"^boom$"):
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        assert session.revision is first
        assert capsys.readouterr().err == ""
        assert session.poll() is True
        revision = session.revision
        assert revision is not None and revision.edits == 1 and mismatches(session) == 2

    def test_a_second_start_keeps_the_one_analyser(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.start()
        analyser = session._analyser
        try:
            session.start()
            assert analyser is not None and session._analyser is analyser
        finally:
            stopped(session)

    def test_a_failure_on_the_thread_is_printed_before_it_is_published(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """While the analysis that failed still runs, so that whatever waits for the failure to
        be published finds its line already written."""

        class Recording(io.StringIO):
            def __init__(self) -> None:
                super().__init__()
                self.running: list[bool] = []

            def write(self, text: str) -> int:
                if text.strip():
                    self.running.append(session._running)
                return super().write(text)

        session = SecondFails(shared.parent)
        recording = Recording()
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            monkeypatch.setattr(sys, "stderr", recording)
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.settled(timeout=10) is not None
        finally:
            stopped(session)
        assert recording.running == [True]
        assert recording.getvalue() == "ddd gui: analysing the project failed: boom\n"

    def test_a_failure_the_analyser_cannot_print_ends_nothing(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing raised outside the analysis ends the analyser - the line it could not print
        included: the next poll's analysis is made all the same."""

        class Unwritable(io.StringIO):
            def write(self, text: str) -> int:
                raise OSError("standard error is closed")

        session = SecondFails(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            first = session.settled(timeout=10)
            monkeypatch.setattr(sys, "stderr", Unwritable())
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.settled(timeout=10) is first
            monkeypatch.undo()
            assert session.poll() is True
            begun(session)
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == at and mismatches(session) == 2
        finally:
            stopped(session)

    def test_a_project_including_a_path_no_system_reads_is_analysed_to_its_end(
        self, tmp_path: Path
    ) -> None:
        """A path holding a NUL byte is stamped as a file that is not there and read as an empty
        one, so the analysis goes to its end and its revision carries what the loader reports of
        the path, with the analyser still there; stamped ``None`` again by every poll, the path
        asks for no analysis more."""
        project_file = unreachable(tmp_path)
        session = Gated(tmp_path)
        session.gate.set()
        session.start()
        try:
            session.open(project_file)
            begun(session)
            revision = session.settled(timeout=10)
            assert revision is not None and findings_of(revision) == [unreadable(project_file)]
            assert session._analyser is not None and session._analyser.is_alive()
            assert session.poll() is False
            assert session.poll() is False
            assert (session.revision, session.analyses) == (revision, 1)
        finally:
            stopped(session)

    def test_where_no_analyser_runs_a_project_including_a_path_no_system_reads_opens_all_the_same(
        self, tmp_path: Path
    ) -> None:
        """Opening answers with the revision, the path listed as an empty file of no kind and its
        refusal filed where the project names it, which leaves the project not loaded."""
        project_file = unreachable(tmp_path)
        session = Session(tmp_path)
        session.open(project_file)
        revision = session.revision
        assert revision is not None and findings_of(revision) == [unreadable(project_file)]
        described = {f.path.name: (f.kind, f.loaded, f.fingerprint) for f in revision.files}
        assert described == {
            "p.ddd.json": ("project", False, fingerprint(project_file.read_bytes())),
            "a.ddd.json": ("component", True, fingerprint((tmp_path / "a.ddd.json").read_bytes())),
            NUL_ENTRY: ("unknown", True, fingerprint(b"")),
        }
        (filed,) = revision.findings
        assert filed.diagnostic.location is not None
        assert filed.diagnostic.location.pointer == "project.includes[1]"
        assert session.poll() is False

    def test_a_file_named_for_one_analysis_is_not_watched_by_the_ones_after(
        self, shared: Path
    ) -> None:
        """What an edit or an undo wrote is carried into the stamps of the one analysis after it,
        and watched after that only while the project includes it: the units file an undone
        adoption took away, written again while a later edit's analysis runs, is no file of the
        project, and asks for nothing."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            at, _ = session.edit(adoption(shared), "the vocabulary adopted")
            begun(session)
            assert session.settled(timeout=10) is not None
            session.undo(at)
            begun(session)
            assert session.settled(timeout=10) is not None
            units = shared.parent / "units.ddd.json"
            assert not units.exists()
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            units.write_text('{"units": []}', encoding="utf-8")
            assert session.poll() is False
        finally:
            session.gate.set()
            stopped(session)

    def test_stopping_ends_the_analyser_and_the_poller(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        session.open(shared)
        session.settled(timeout=10)
        stopped(session)
        assert session._analyser is not None and not session._analyser.is_alive()
        assert session._poller is not None and not session._poller.is_alive()

    def test_the_project_open_is_known_before_its_first_analysis_lands(self, shared: Path) -> None:
        session = Gated(shared.parent)
        assert session.project is None
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert (session.project, session.revision) == (shared.resolve(), None)
        finally:
            session.gate.set()
            stopped(session)

    def test_settled_answers_after_its_timeout_while_an_analysis_waits(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=0.01) is None
        finally:
            session.gate.set()
            stopped(session)


def unit_of_a(path: Path, unit: str) -> FileChange:
    target = path.parent / "a.ddd.json"
    pointer = "component.interface[0].definition.unit"
    return FileChange(
        target, fingerprint(target.read_bytes()), (Operation("set", pointer, f'"{unit}"'),)
    )


class TestWhatTheSessionSays:
    """What one ``GET /api/state`` answers, read at once - the version, the project, the newest
    revision, whether an analysis is asked for or running and the undo entry - and the files an
    edit wrote that no analysis has read yet."""

    def test_a_session_with_nothing_open_says_so_at_version_nought(self, tmp_path: Path) -> None:
        assert Session(tmp_path).snapshot() == Snapshot(0, None, None, False, None)

    def test_a_snapshot_reads_the_undo_entry_with_the_stack_empty_and_with_one(
        self, shared: Path
    ) -> None:
        """``_snapshot`` reads the top of the stack in a conditional expression, which coverage
        counts no branch in: this is what pins both of its arms."""
        session = Session(shared.parent)
        session.open(shared)
        assert session.snapshot().undoable is None
        session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        top = session.snapshot().undoable
        assert top is not None and top is session.undoable
        assert (top.at, top.label) == (1, "the unit of Speed")

    def test_the_version_counts_each_analysis_asked_for_and_each_one_ended(
        self, shared: Path
    ) -> None:
        """Where no analyser runs, a call asks for its analysis and ends it before it answers: two
        versions a call. A poll finding nothing changed asks for nothing, and moves nothing."""
        session = Session(shared.parent)
        session.open(shared)
        assert session.snapshot().version == 2
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        assert session.snapshot().version == 4
        session.undo(at)
        assert session.snapshot().version == 6
        assert session.poll() is False
        assert session.snapshot().version == 6
        (shared.parent / "a.ddd.json").write_text("{}", encoding="utf-8")
        assert session.poll() is True
        assert session.snapshot().version == 8

    def test_an_analysis_that_failed_moves_the_version_as_one_published_does(
        self, shared: Path
    ) -> None:
        class Failing(Session):
            analyses = 0

            def _analysed(self, project: Path) -> Revision:
                self.analyses += 1
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return super()._analysed(project)

        session = Failing(shared.parent)
        session.open(shared)
        with pytest.raises(RuntimeError, match=r"^boom$"):
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        snapshot = session.snapshot()
        assert (snapshot.version, snapshot.analysing) == (4, False)
        assert snapshot.revision is not None and snapshot.revision.number == 1

    def test_an_edit_written_says_analysing_until_its_analysis_lands(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            first = landed(session)
            assert first.revision is not None and first.revision.number == 1
            session.gate.clear()
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            during = session.snapshot()
            assert (during.version, during.analysing) == (first.version + 1, True)
            assert during.revision is first.revision
            assert during.undoable is not None and during.undoable.at == at
            session.gate.set()
            after = landed(session)
            assert after.version == during.version + 1
            assert after.revision is not None
            assert (after.revision.number, after.revision.edits) == (2, at)
        finally:
            session.gate.set()
            stopped(session)

    def test_a_wait_answers_as_soon_as_the_version_moves_past_it(self, shared: Path) -> None:
        """An edit written while its analysis waits at the gate is answered at once, not when the
        analysis lands; the analysis landing moves the version once more, and answers the next
        wait."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            first = landed(session)
            session.gate.clear()
            answers: list[Snapshot] = []

            def waiting(after: int) -> threading.Thread:
                thread = threading.Thread(
                    target=lambda: answers.append(session.wait(after, timeout=30)), daemon=True
                )
                thread.start()
                return thread

            written = waiting(first.version)
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            written.join(timeout=10)
            assert not written.is_alive(), "the wait did not answer the edit written"
            (seen,) = answers
            assert (seen.version, seen.analysing) == (first.version + 1, True)
            assert seen.revision is first.revision
            answers.clear()
            analysed = waiting(seen.version)
            begun(session)
            session.gate.set()
            analysed.join(timeout=10)
            assert not analysed.is_alive(), "the wait did not answer the analysis landing"
            (seen,) = answers
            assert (seen.version, seen.analysing) == (first.version + 2, False)
            assert seen.revision is not None and seen.revision.number == 2
        finally:
            session.gate.set()
            stopped(session)

    def test_a_wait_answers_what_the_session_says_once_its_timeout_has_passed(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        now = session.snapshot()
        assert session.wait(now.version, timeout=0.01) == now

    def test_the_newest_revision_is_refused_before_a_project_and_before_its_first_analysis(
        self, shared: Path
    ) -> None:
        session = Gated(shared.parent)
        with pytest.raises(NoProjectError) as nothing:
            session.current()
        assert str(nothing.value) == "no project is open"
        session.start()
        try:
            session.open(shared)
            begun(session)
            snapshot = session.snapshot()
            assert (snapshot.project, snapshot.revision, snapshot.analysing) == (
                shared.resolve(),
                None,
                True,
            )
            with pytest.raises(NotAnalysedError) as waiting:
                session.current()
            assert str(waiting.value) == "the open project has not been analysed yet"
            with pytest.raises(NotAnalysedError):
                session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            session.gate.set()
            landed(session)
            assert session.current() is session.revision
        finally:
            session.gate.set()
            stopped(session)

    def test_another_project_opened_goes_on_counting_the_edits(self, shared: Path) -> None:
        """A page compares the number its own last edit took with the edits a revision includes,
        whatever project it shows: the numbers go on across projects, so that the first revision
        of the next one includes every edit made before it."""
        write_tree(shared.parent, {"q.ddd.json": project("Q", "a.ddd.json")})
        session = Session(shared.parent)
        session.open(shared)
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        session.open(shared.parent / "q.ddd.json")
        revision = session.revision
        assert revision is not None and revision.edits == at == 1

    def test_the_files_an_edit_wrote_wait_for_the_analysis_including_them(
        self, shared: Path
    ) -> None:
        """Until a revision includes an edit, the files it wrote are unanalysed by every revision
        before it; once a revision includes it, it is let go - and so no longer named for an
        older revision either, which a plan made against one cannot be helped by."""
        session = Stepped(shared.parent)
        opening, first, second = session.goes
        opening.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            oldest = landed(session).revision
            assert oldest is not None and session.unanalysed(oldest) == frozenset()
            a = (shared.parent / "a.ddd.json").resolve()
            b = (shared.parent / "b.ddd.json").resolve()
            session.edit([unit_of_b(shared, "Hz")], "the unit of B's Speed")
            begun(session)
            assert session.unanalysed(oldest) == {b}
            later, _ = session.edit([unit_of_a(shared, "Hz")], "the unit of A's Speed")
            assert session.unanalysed(oldest) == {a, b}
            first.set()
            begun(session)  # the second edit's analysis, begun once the first edit's landed
            middle = session.revision
            assert middle is not None and (middle.number, middle.edits) == (2, 1)
            assert session.unanalysed(middle) == {a}
            assert session.unanalysed(oldest) == {a}
            second.set()
            newest = landed(session).revision
            assert newest is not None and newest.edits == later
            assert session.unanalysed(newest) == frozenset()
        finally:
            for go in session.goes:
                go.set()
            stopped(session)

    def test_a_revision_including_an_edit_names_none_of_its_files(self, shared: Path) -> None:
        """The files named are those numbered past the revision's own ``edits``, whatever else
        lets them go. No revision this session publishes holds an edit still waiting - each
        analysis landing lets go of what it includes - so the revision asked of here is the
        newest one as an analysis including the edit would make it."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            oldest = landed(session).revision
            assert oldest is not None
            session.gate.clear()
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.unanalysed(oldest) == {(shared.parent / "b.ddd.json").resolve()}
            assert session.unanalysed(replace(oldest, edits=at)) == frozenset()
        finally:
            session.gate.set()
            stopped(session)

    def test_the_files_an_undo_put_back_wait_as_an_edits_do(self, shared: Path) -> None:
        session = Stepped(shared.parent)
        opening, first, second = session.goes
        opening.set()
        first.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            landed(session)
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            edited = landed(session).revision
            assert edited is not None and session.unanalysed(edited) == frozenset()
            session.undo(at)
            begun(session)
            assert session.unanalysed(edited) == {(shared.parent / "b.ddd.json").resolve()}
            second.set()
            undone = landed(session).revision
            assert undone is not None and session.unanalysed(undone) == frozenset()
        finally:
            for go in session.goes:
                go.set()
            stopped(session)

    def test_opening_forgets_the_files_written_before(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            oldest = landed(session).revision
            assert oldest is not None
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.unanalysed(oldest) == {(shared.parent / "b.ddd.json").resolve()}
            session.open(shared)
            assert session.unanalysed(oldest) == frozenset()
        finally:
            session.gate.set()
            stopped(session)


class TestStamps:
    def test_opening_a_project_analyses_it_once(self, shared: Path) -> None:
        """Opening stamps the description and every file its own includes name before the
        analysis reads one, so the first poll finds nothing changed. Opening used to learn which
        files the project has from the analysis that read them, none of them stamped before it
        was read, and the first poll analysed the whole project once more."""
        session = Session(shared.parent)
        session.open(shared)
        assert session.poll() is False
        assert session.revision is not None and session.revision.number == 1

    def test_a_sub_projects_files_still_cost_opening_one_analysis_more(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/s.ddd.json"),
                "sub/s.ddd.json": project("S", "c.ddd.json"),
                "sub/c.ddd.json": component("C", declare("output", "Speed", unit="rpm")),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        assert session.poll() is True
        assert session.poll() is False

    def test_a_file_an_edit_created_costs_no_second_analysis(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        session.edit(adoption(shared), "the vocabulary")
        assert session.poll() is False

    def test_an_undo_bringing_back_a_file_its_edit_wrote_and_left_out_costs_no_second_analysis(
        self, shared: Path
    ) -> None:
        """A file an edit both wrote and left out of the project left the stamps with it; the
        undo that brings it back is what stamps it again, before its analysis reads it."""
        session = Session(shared.parent)
        session.open(shared)
        left_out = FileChange(
            shared,
            fingerprint(shared.read_bytes()),
            (Operation("set", "project.includes", '["a.ddd.json"]'),),
        )
        at, _ = session.edit([left_out, unit_of_b(shared, "Hz")], "b changed and left out")
        revision = session.revision
        assert revision is not None and "b.ddd.json" not in {f.path.name for f in revision.files}
        session.undo(at)
        revision = session.revision
        assert revision is not None and "b.ddd.json" in {f.path.name for f in revision.files}
        assert session.poll() is False

    @pytest.mark.parametrize("entry", [NUL_ENTRY, "\ud800.ddd.json"])
    def test_a_path_the_system_refuses_to_look_at_is_stamped_as_not_there(
        self, tmp_path: Path, entry: str
    ) -> None:
        """A NUL byte is refused on every system. U+D800 is refused where a path is encoded to
        bytes, as on Linux, and names a file that is simply not there on Windows: ``None`` on
        both."""
        path = tmp_path / entry
        assert module.stamped([path]) == {path: None}

    def test_an_undo_takes_a_number_of_its_own_and_the_revision_includes_it(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        undone = session.undo(at)
        assert undone == at + 1
        assert session.revision is not None and session.revision.edits == undone


class TestReadingAndEditing:
    def test_a_description_file_is_read_with_its_fingerprint(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        content = session.read_file(shared.parent / "a.ddd.json")
        assert content.data["component"]["name"] == "A"
        assert content.error is None
        assert content.fingerprint == fingerprint((shared.parent / "a.ddd.json").read_bytes())

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            ("{", "Expecting property name"),
            (UNPARSED[1], "'NaN' is not valid json"),
            (UNPARSED[2], "key 'name' appears twice"),
        ],
    )
    def test_a_file_that_is_not_json_is_read_as_the_loaders_reason(
        self, shared: Path, content: str, reason: str
    ) -> None:
        """Read by the loader's rule: python's parser handed the page a ``NaN`` the page's own
        parser cannot read, and showed it a file the loader refuses under the last of its two
        names."""
        (shared.parent / "b.ddd.json").write_text(content, encoding="utf-8")
        session = Session(shared.parent)
        session.open(shared)
        read = session.read_file(shared.parent / "b.ddd.json")
        assert read.data is None
        assert read.error is not None and "is not json" in read.error and reason in read.error

    @pytest.mark.parametrize("content", UNPARSED)
    def test_an_edit_of_a_file_that_is_not_json_is_unreadable(
        self, shared: Path, content: str
    ) -> None:
        target = shared.parent / "b.ddd.json"
        target.write_text(content, encoding="utf-8")
        session = Session(shared.parent)
        session.open(shared)
        name = FileChange(
            target,
            fingerprint(target.read_bytes()),
            (Operation("set", "component.name", '"X"'),),
        )
        with pytest.raises(EditError) as refused:
            session.edit([name], "the name of B")
        assert refused.value.code == UNREADABLE
        assert target.read_text(encoding="utf-8") == content

    def test_a_file_that_vanished_is_read_as_its_reason(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        (shared.parent / "a.ddd.json").unlink()
        content = session.read_file(shared.parent / "a.ddd.json")
        assert content.error is not None and "cannot be read" in content.error

    def test_only_description_files_of_the_open_project_are_read(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "tools/demo_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
                "elsewhere.ddd.json": component("E"),
            },
        )
        session = Session(tmp_path)
        with pytest.raises(NoProjectError):
            session.read_file(tmp_path / "a.ddd.json")
        session.open(tmp_path / "p.ddd.json")
        for outside in ("elsewhere.ddd.json", "tools/demo_plugin.py"):
            with pytest.raises(NotInProjectError):
                session.read_file(tmp_path / outside)

    def test_an_edit_is_written_and_analysed_again(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        _, written = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        revision = session.revision
        assert revision is not None
        assert revision.number == 2
        assert [file.path for file in written] == [(shared.parent / "b.ddd.json").resolve()]
        assert {f.diagnostic.check for f in revision.findings} >= {"definition-mismatch"}

    def test_an_edit_outside_the_project_is_refused_and_nothing_is_written(
        self, shared: Path, tmp_path: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        outside = tmp_path / "outside.ddd.json"
        outside.write_text("{}", encoding="utf-8")
        with pytest.raises(NotInProjectError):
            session.edit(
                [FileChange(outside, fingerprint(b"{}"), (Operation("set", "a", "1"),))],
                "an edit outside the project",
            )
        assert outside.read_text(encoding="utf-8") == "{}"

    def test_an_edit_from_a_stale_read_is_refused(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        stale = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.edit([stale], "the unit of Torque")
        assert refused.value.code == STALE

    def test_an_edit_needs_an_open_project(self, shared: Path) -> None:
        with pytest.raises(NoProjectError):
            Session(shared.parent).edit([unit_of_b(shared, "Hz")], "the unit of Torque")

    def test_the_edits_written_are_counted_and_a_refused_one_is_not(self, shared: Path) -> None:
        """What a kept answer is keyed by beside its revision: each edit written counts one, the
        number an undo of it names, and one refused before anything was written counts none."""
        session = Session(shared.parent)
        session.open(shared)
        assert session.edits == 0
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        stale = unit_of_b(shared, "rad")
        session.edit([unit_of_b(shared, "rad")], "the unit of Torque")
        assert session.edits == 2
        top = session.undoable
        assert top is not None
        assert top.at == session.edits
        with pytest.raises(EditError):
            session.edit([stale], "the unit of Torque")
        assert session.edits == 2


def adoption(project_file: Path, name: str = "units.ddd.json") -> list[FileChange]:
    """What adopting a vocabulary posts: a units file created beside the project, and its name
    appended to the project's includes."""
    includes = json.loads(project_file.read_text(encoding="utf-8"))["project"]["includes"]
    return [
        FileChange(project_file.parent / name, None, (Operation("set", "", '{"units": ["rpm"]}'),)),
        FileChange(
            project_file,
            fingerprint(project_file.read_bytes()),
            (Operation("insert", f"project.includes[{len(includes)}]", json.dumps(name)),),
        ),
    ]


class TestCreatingAFile:
    """An edit creates a file only beside the project description, and only by including it."""

    def test_a_file_the_same_edit_includes_beside_the_project_is_created_and_read(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        units = (shared.parent / "units.ddd.json").resolve()
        _, written = session.edit(adoption(shared), "the vocabulary adopted")
        revision = session.revision
        assert revision is not None
        assert units.read_bytes() == b'{"units": ["rpm"]}'
        assert {file.path for file in written} == {units, shared.resolve()}
        described = {f.path.name: (f.kind, f.loaded) for f in revision.files}
        assert described["units.ddd.json"] == ("units", True)

    def test_a_created_file_takes_the_mode_of_the_project_description(self, shared: Path) -> None:
        shared.chmod(0o640)
        mode = stat.S_IMODE(shared.stat().st_mode)
        session = Session(shared.parent)
        session.open(shared)
        session.edit(adoption(shared), "the vocabulary adopted")
        assert stat.S_IMODE((shared.parent / "units.ddd.json").stat().st_mode) == mode

    def test_a_file_the_edit_does_not_include_is_not_created(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        created, _ = adoption(shared)
        with pytest.raises(EditError) as refused:
            session.edit([created], "the vocabulary adopted")
        assert refused.value.code == INVALID
        assert not (shared.parent / "units.ddd.json").exists()

    def test_a_change_of_the_description_that_leaves_the_file_out_is_not_enough(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        created, _ = adoption(shared)
        renamed = FileChange(
            shared, fingerprint(shared.read_bytes()), (Operation("set", "project.name", '"Q"'),)
        )
        before = shared.read_bytes()
        with pytest.raises(EditError) as refused:
            session.edit([created, renamed], "the vocabulary adopted")
        assert refused.value.code == INVALID
        assert not (shared.parent / "units.ddd.json").exists()
        assert shared.read_bytes() == before

    def test_a_file_is_created_only_beside_the_project_description(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        with pytest.raises(EditError) as refused:
            session.edit(adoption(shared, "vocabulary/units.ddd.json"), "the vocabulary adopted")
        assert refused.value.code == INVALID
        assert not (shared.parent / "vocabulary").exists()

    def test_a_description_changed_on_disk_since_is_stale(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        edit = adoption(shared)
        shared.write_text(shared.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.edit(edit, "the vocabulary adopted")
        assert refused.value.code == STALE
        assert not (shared.parent / "units.ddd.json").exists()


class TestUndoing:
    """One stack per open project: what each edit replaced, walked back one edit at a time."""

    def test_an_edit_is_pushed_with_the_label_it_was_applied_with(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        before = (shared.parent / "b.ddd.json").read_bytes()
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        top = session.undoable
        assert top is not None
        assert (top.at, top.label) == (1, "the unit of Torque")
        assert [file.before for file in top.files] == [before]

    def test_an_undo_puts_the_files_back_and_analyses_again(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        before = b.read_bytes()
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        session.undo(1)
        revision = session.revision
        assert revision is not None
        assert b.read_bytes() == before
        assert revision.number == 3
        assert session.undoable is None

    def test_an_undo_walks_back_one_edit_at_a_time(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        first = b.read_bytes()
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        second = b.read_bytes()
        session.edit([unit_of_b(shared, "rad")], "the unit of Torque")
        session.undo(2)
        assert b.read_bytes() == second
        session.undo(1)
        assert b.read_bytes() == first

    def test_anything_but_the_top_of_the_stack_is_refused(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        with pytest.raises(EditError) as refused:
            session.undo(7)
        assert refused.value.code == STALE
        assert session.undoable is not None

    def test_an_undo_with_nothing_to_undo_is_refused(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        with pytest.raises(EditError) as refused:
            session.undo(1)
        assert refused.value.code == STALE

    def test_a_refused_undo_leaves_the_stack_as_it_was(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        b.write_text('{"component": {"name": "B"}}', encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.undo(1)
        assert refused.value.code == STALE
        assert session.undoable is not None
        assert b.read_text(encoding="utf-8") == '{"component": {"name": "B"}}'

    def test_an_undo_takes_away_the_file_an_adoption_created(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        units = shared.parent / "units.ddd.json"
        described = shared.read_bytes()
        session.edit(adoption(shared), "the vocabulary adopted")
        session.undo(1)
        assert not units.exists()
        assert shared.read_bytes() == described

    def test_the_oldest_edit_falls_off_a_full_stack(self, shared: Path, monkeypatch) -> None:
        monkeypatch.setattr(session_module, "MAX_UNDO", 2)
        session = Session(shared.parent)
        session.open(shared)
        for unit in ("Hz", "rad", "rpm"):
            session.edit([unit_of_b(shared, unit)], f"the unit of {unit}")
        top = session.undoable
        assert top is not None and top.at == 3
        session.undo(3)
        session.undo(2)
        with pytest.raises(EditError):
            session.undo(1)

    def test_the_stack_holds_fifty_edits(self) -> None:
        assert MAX_UNDO == 50

    def test_opening_a_project_empties_the_stack(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        session.open(shared)
        assert session.undoable is None

    def test_an_undo_needs_an_open_project(self, shared: Path) -> None:
        with pytest.raises(NoProjectError):
            Session(shared.parent).undo(1)


@pytest.fixture
def vocabulary(tmp_path: Path) -> Path:
    """A copy of ``examples/vocabulary``, whose pump sizes a buffer by a constant only
    ``constants.ddd.json`` declares; returns the project file."""
    shutil.copytree(EXAMPLES / "vocabulary", tmp_path / "vocabulary")
    return tmp_path / "vocabulary" / "project.ddd.json"


def errors_of(findings: tuple[Filed, ...]) -> list[Filed]:
    return [filed for filed in findings if filed.diagnostic.severity is Severity.ERROR]


class TestFindingsWith:
    """What a revision's project would report with its root's ``includes`` replaced: the runs
    the revision was made from, again, with one list differing."""

    def test_a_file_left_out_is_analysed_as_gone(self, vocabulary: Path) -> None:
        revision = opened_and_settled(vocabulary).revision
        assert revision is not None
        listed = json.loads(vocabulary.read_text(encoding="utf-8"))["project"]["includes"]
        without = [entry for entry in listed if entry != "constants.ddd.json"]
        assert len(without) == len(listed) - 1
        found = [
            (filed.file.name, filed.diagnostic.check, filed.diagnostic.severity)
            for filed in findings_with(revision, without)
        ]
        assert found == [("pump.ddd.json", "unknown-constant", Severity.ERROR)]
        assert revision.findings == ()

    def test_each_build_is_run_again_under_its_own_severities(self, tmp_path: Path) -> None:
        """Focus 2: the revision was made through a build record raising ``unused-output`` to an
        error. Run under the project's defaults instead, the list unchanged would already answer
        other errors than the revision's, for a reason no change of the list made."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["unused-output=error"])
        revision = opened_and_settled(tmp_path / "p.ddd.json").revision
        assert revision is not None
        errors = errors_of(revision.findings)
        assert [filed.diagnostic.check for filed in errors] == ["unused-output"]
        assert errors_of(findings_with(revision, ["a.ddd.json"])) == errors

    def test_the_list_replaced_reaches_every_builds_run(self, tmp_path: Path) -> None:
        """The same record, over a consumer that reads the output: leaving the consumer out makes
        the output unread, which only the build's own run, given the list, reports as an error."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["unused-output=error"])
        revision = opened_and_settled(tmp_path / "p.ddd.json").revision
        assert revision is not None
        assert errors_of(revision.findings) == []
        found = errors_of(findings_with(revision, ["a.ddd.json"]))
        assert [(filed.file.name, filed.diagnostic.check) for filed in found] == [
            ("a.ddd.json", "unused-output")
        ]

    def test_every_build_is_run_again_not_the_first_alone(self, tmp_path: Path) -> None:
        """Two records raising different checks to errors, an unread output in `one.elf` and a
        missing id in `two.elf`: run through either record alone, the list unchanged would
        already answer other errors than the revision's."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, image="one.elf", severity=["unused-output=error"])
        build_record(tmp_path, project_file, image="two.elf", severity=["missing-id=error"])
        revision = opened_and_settled(project_file).revision
        assert revision is not None
        assert revision.analysed is True
        errors = errors_of(revision.findings)
        assert sorted(filed.diagnostic.check for filed in errors) == ["missing-id", "unused-output"]
        assert errors_of(findings_with(revision, ["a.ddd.json"])) == errors

    def test_a_finding_with_no_place_is_shown_on_the_project_file(self, tmp_path: Path) -> None:
        """Where the revision shows it: on the project file, the one file the reader is sure to
        have open."""
        write_tree(
            tmp_path,
            {
                "tools/loose_plugin.py": UNPLACED_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/loose_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        revision = opened_and_settled(tmp_path / "p.ddd.json").revision
        assert revision is not None
        for findings in (revision.findings, findings_with(revision, ["a.ddd.json"])):
            unplaced = [
                (filed.file, filed.diagnostic.check)
                for filed in findings
                if filed.diagnostic.location is None
            ]
            assert unplaced == [(revision.project, "loose/unplaced")]

    def test_the_findings_come_file_by_file_in_path_order(self, tmp_path: Path) -> None:
        """A revision's order, whatever the severities: leaving `c.ddd.json` out leaves a warning
        on `a.ddd.json` and an error on `b.ddd.json`, and the warning comes first although a run
        reports its errors first. :func:`ddd.file_plans.new_errors` keeps the order it is given."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Torque")),
                "c.ddd.json": component(
                    "C", declare("input", "Speed"), declare("output", "Torque")
                ),
            },
        )
        revision = opened_and_settled(tmp_path / "p.ddd.json").revision
        assert revision is not None
        answer = findings_with(revision, ["a.ddd.json", "b.ddd.json"])
        assert [(filed.file.name, filed.diagnostic.check) for filed in errors_of(answer)] == [
            ("b.ddd.json", "missing-producer")
        ]
        assert list(dict.fromkeys(filed.file.name for filed in answer)) == [
            "a.ddd.json",
            "b.ddd.json",
        ]


class TestEveryRunAnalysed:
    """Whether a revision's findings hold what every run it was made from would say: a run whose
    read reported an error never reaches the analysis, and another build's run that did does not
    speak for it, each grading the checks by its own severities."""

    def test_a_run_its_read_stopped_leaves_the_revision_unanalysed(self, tmp_path: Path) -> None:
        """`release` reads a dead pattern as an error and stops there; `dev` relaxes it and
        analyses, so the revision resolved. Removing the pattern would surface as new what
        `release`'s run never checked - its strictness raises `Unread` to an error."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "gone/*.ddd.json", "r.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X"), declare("output", "Unread")),
                "r.ddd.json": component("R", declare("input", "X")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, image="release.elf", strict=True)
        build_record(tmp_path, project_file, image="dev.elf", severity=["include-empty=warning"])
        revision = opened_and_settled(project_file).revision
        assert revision is not None
        found = [
            (filed.file.name, filed.diagnostic.check) for filed in errors_of(revision.findings)
        ]
        assert found == [("p.ddd.json", "include-empty")]
        assert revision.resolved is not None
        assert revision.analysed is False

    def test_a_run_its_read_stopped_hides_what_a_removal_would_break(self, tmp_path: Path) -> None:
        """The other way: `release` stops at a dead pattern, and `dev` relaxes that
        and `missing-producer`, so leaving out `u.ddd.json` - whose `Y` `R` reads - breaks
        nothing either run reports, while `release` without the pattern says it does."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P", "a.ddd.json", "u.ddd.json", "r.ddd.json", "z/*.ddd.json"
                ),
                "a.ddd.json": component("A", declare("output", "X")),
                "u.ddd.json": component("U", declare("output", "Y")),
                "r.ddd.json": component("R", declare("input", "X"), declare("input", "Y")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, image="release.elf")
        relaxed = ["include-empty=warning", "missing-producer=warning"]
        build_record(tmp_path, project_file, image="dev.elf", severity=relaxed)
        revision = opened_and_settled(project_file).revision
        assert revision is not None
        assert revision.resolved is not None
        assert revision.analysed is False
        without_u = ["a.ddd.json", "r.ddd.json", "z/*.ddd.json"]
        for findings in (revision.findings, findings_with(revision, without_u)):
            found = [(filed.file.name, filed.diagnostic.check) for filed in errors_of(findings)]
            assert found == [("p.ddd.json", "include-empty")]
        (release,) = [info for info in revision.builds if info.image == "release.elf"]
        run = run_build(release, includes=["a.ddd.json", "r.ddd.json"])
        assert [found.check for found in run.bag if found.severity is Severity.ERROR] == [
            "missing-producer"
        ]


def test_the_demo_opens_clean() -> None:
    demo = EXAMPLES / "demo" / "demo.ddd.json"
    revision = first_revision(demo.parent, demo)
    assert not [f for f in revision.findings if f.diagnostic.severity.value == "error"]
    assert {f.name for f in revision.files if f.kind == "component"} == {
        "Controller",
        "SensorHub",
        "UserInterface",
        "EventLogger",
    }
