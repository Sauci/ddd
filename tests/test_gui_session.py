"""The project ddd gui has open: what it finds, what a revision holds, and how it follows disk."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import EXAMPLES, build_record, component, declare, project, write_tree
from ddd.diagnostics import SeverityPolicy, UnknownCheckError
from ddd.editing import STALE, UNREADABLE, EditError, FileChange, Operation, fingerprint
from ddd.gui import session as module
from ddd.gui.session import NoProjectError, NotInProjectError, Session, find_projects
from ddd.lsp.diagnostics import Run

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
    """A session on the project, past the one analysis more that opening it costs."""
    session = Session(project_file.parent, poll_interval=poll_interval)
    session.open(project_file)
    session.poll()
    return session


def saving_while_analysing(file: Path, unit: bytes) -> Callable[[Path], Run]:
    """``run_project``, and another editor saving the first unit of ``file`` as ``unit`` once the
    analysis has read the files but before the session has its answer."""
    real = module.run_project

    def run(project_file: Path) -> Run:
        answer = real(project_file)
        saved = re.sub(rb'"unit": "[^"]*"', b'"unit": ' + unit, file.read_bytes(), count=1)
        file.write_bytes(saved)
        return answer

    return run


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
        revision = Session(shared.parent).open(shared)
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
        revision = Session(shared.parent).open(shared)
        filed = {
            f.file.name for f in revision.findings if f.diagnostic.check == "definition-mismatch"
        }
        assert filed == {"a.ddd.json", "b.ddd.json"}
        counts = {f.path.name: f.errors for f in revision.files}
        assert counts["a.ddd.json"] == counts["b.ddd.json"] == 1

    def test_opening_again_makes_a_newer_revision(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        assert session.open(shared).number == 2

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
        revision = Session(tmp_path).open(tmp_path / "p.ddd.json")
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
        revision = Session(shared.parent).open(shared)
        broken = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert (broken.kind, broken.name, broken.loaded) == ("unknown", None, False)
        assert revision.dictionary is None

    def test_a_file_that_cannot_be_read_is_described_as_empty(self, tmp_path: Path) -> None:
        described = module._described(tmp_path / "gone.ddd.json", [])
        assert (described.kind, described.fingerprint) == ("unknown", fingerprint(b""))

    def test_a_description_of_no_known_kind_is_unknown(self) -> None:
        assert module._kind(Path("x.ddd.json"), {"other": 1}) == "unknown"


class TestFollowingTheDisk:
    def test_nothing_is_polled_while_no_project_is_open(self, tmp_path: Path) -> None:
        assert Session(tmp_path).poll() is False

    def test_after_the_one_analysis_more_opening_costs_an_unchanged_project_is_left_alone(
        self, shared: Path
    ) -> None:
        """Opening learns which files the project has from the analysis that reads them, so none
        of them was stamped before it was read, and the first poll analyses once more."""
        session = Session(shared.parent)
        session.open(shared)
        assert session.poll() is True
        assert session.poll() is False
        assert session.revision is not None and session.revision.number == 2

    def test_a_file_changed_on_disk_makes_a_new_revision(self, shared: Path) -> None:
        session = opened_and_settled(shared)
        (shared.parent / "b.ddd.json").write_text(
            (shared.parent / "b.ddd.json").read_text(encoding="utf-8").replace("rpm", "Hz") + " ",
            encoding="utf-8",
        )
        assert session.poll() is True
        assert session.revision is not None and session.revision.number == 3

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
        session.edit([unit_of_b(shared, "Hz")])
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

    def test_a_waiting_request_gets_the_newer_revision_as_soon_as_it_exists(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        threading.Timer(0.05, session.open, args=(shared,)).start()
        revision = session.wait(1, timeout=5)
        assert revision is not None and revision.number == 2

    def test_a_waiting_request_gets_the_current_revision_when_nothing_changes(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        revision = session.wait(1, timeout=0.05)
        assert revision is not None and revision.number == 1

    def test_the_polling_thread_notices_a_change(self, shared: Path) -> None:
        session = opened_and_settled(shared, poll_interval=0.02)
        session.start_polling()
        session.start_polling()  # a second start keeps the one thread
        try:
            (shared.parent / "a.ddd.json").write_text("{}", encoding="utf-8")
            revision = session.wait(2, timeout=5)
            assert revision is not None and revision.number == 3
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
            session.edit([name])
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
        revision, written = session.edit([unit_of_b(shared, "Hz")])
        assert revision.number == 2
        assert list(written) == [(shared.parent / "b.ddd.json").resolve()]
        assert {f.diagnostic.check for f in revision.findings} >= {"definition-mismatch"}

    def test_an_edit_outside_the_project_is_refused_and_nothing_is_written(
        self, shared: Path, tmp_path: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        outside = tmp_path / "outside.ddd.json"
        outside.write_text("{}", encoding="utf-8")
        with pytest.raises(NotInProjectError):
            session.edit([FileChange(outside, fingerprint(b"{}"), (Operation("set", "a", "1"),))])
        assert outside.read_text(encoding="utf-8") == "{}"

    def test_an_edit_from_a_stale_read_is_refused(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        stale = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.edit([stale])
        assert refused.value.code == STALE

    def test_an_edit_needs_an_open_project(self, shared: Path) -> None:
        with pytest.raises(NoProjectError):
            Session(shared.parent).edit([unit_of_b(shared, "Hz")])


def test_the_demo_opens_clean() -> None:
    demo = EXAMPLES / "demo" / "demo.ddd.json"
    revision = Session(demo.parent).open(demo)
    assert not [f for f in revision.findings if f.diagnostic.severity.value == "error"]
    assert {f.name for f in revision.files if f.kind == "component"} == {
        "Controller",
        "SensorHub",
        "UserInterface",
        "EventLogger",
    }
