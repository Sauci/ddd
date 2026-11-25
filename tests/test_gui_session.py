"""The project ddd gui has open: what it finds, what a revision holds, and how it follows disk."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest

import ddd.gui.session as session_module
from conftest import (
    EXAMPLES,
    Gated,
    begun,
    build_record,
    collected_project,
    component,
    declare,
    directory_link,
    first_revision,
    landed,
    lying_under,
    membership,
    offered_beside,
    project,
    stopped,
    write_tree,
)
from ddd.build_info import BUILD_INFO_FORMAT, BuildInfo, build_info_text
from ddd.diagnostics import Diagnostic, Severity, SeverityPolicy, UnknownCheckError
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    UNWRITABLE,
    EditError,
    FileChange,
    Operation,
    fingerprint,
)
from ddd.gui import queries
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
    walk_finds,
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
    return unit_of(path.parent / "b.ddd.json", unit)


def unit_of(target: Path, unit: str) -> FileChange:
    """The change setting the unit of the one declaration ``target`` states, from its bytes as
    they stand."""
    pointer = "component.interface[0].definition.unit"
    return FileChange(
        target, fingerprint(target.read_bytes()), (Operation("set", pointer, f'"{unit}"'),)
    )


def refusing_renames(after: dict[Path, int]) -> Callable[[Path, Any], Path]:
    """``Path.replace`` refusing a target, as a full disk would, once it has been asked for it
    ``after[target]`` times: 1 refuses the first rename onto it, 2 lets the first by - the put
    back of a file an undo writes - and refuses the second, its write forward again."""
    real = Path.replace
    seen: dict[Path, int] = {}

    def renaming(self: Path, target: Any) -> Path:
        target = Path(target)
        seen[target] = seen.get(target, 0) + 1
        if seen[target] >= after.get(target, seen[target] + 1):
            raise OSError("disk full")
        return real(self, target)

    return renaming


def mismatches(session: Session) -> int:
    """How many ``definition-mismatch`` findings the newest revision shows."""
    revision = session.revision
    assert revision is not None
    return sum(1 for filed in revision.findings if filed.diagnostic.check == "definition-mismatch")


def opened_and_settled(project_file: Path, poll_interval: float = 1.0) -> Session:
    """A session on the project, past any analysis more that opening it costs - one, where a
    sub-project's files had no stamp before the first analysis read them, which its revision asks
    for at once, and none for a flat project, whose files opening stamps - and polled once, which
    finds nothing then."""
    session = Session(project_file.parent, poll_interval=poll_interval)
    session.open(project_file)
    session.poll()
    return session


def with_a_sub_project(base: Path) -> Path:
    """A project including a sub-project, whose own ``includes`` name its one component - files
    opening does not stamp, since it reads no sub-project's ``includes``; returns the project
    file."""
    write_tree(
        base,
        {
            "p.ddd.json": project("P", "sub/s.ddd.json"),
            "sub/s.ddd.json": project("S", "c.ddd.json"),
            "sub/c.ddd.json": component("C", declare("output", "Speed", unit="rpm")),
        },
    )
    return base / "p.ddd.json"


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

NUL_PLUGIN = NUL_ENTRY.removesuffix(".ddd.json") + ".py"
"""A plugin named by a path no system lets a program look at, as :data:`NUL_ENTRY` is."""


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

    def test_a_file_that_does_not_parse_is_listed_as_unreadable_with_why(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {"good/p.ddd.json": project("P"), "brokenone/broken.ddd.json": "{"})
        found = find_projects(tmp_path)
        assert [p.name for p in found.projects] == ["P"]
        ((path, reason),) = found.unreadable
        assert path == (tmp_path / "brokenone" / "broken.ddd.json").resolve()
        assert reason.startswith("does not parse: Expecting property name")

    def test_a_file_that_parses_and_states_no_project_is_not_listed_as_unreadable(
        self, shared: Path, tmp_path: Path
    ) -> None:
        """A component's description is no project, and is not one that failed to be read."""
        write_tree(tmp_path, {"q.ddd.json": '{"project": 7}', "r.ddd.json": "[]"})
        assert find_projects(tmp_path).unreadable == ()
        assert find_projects(shared.parent).unreadable == ()

    def test_a_file_that_is_not_utf8_is_listed_as_unreadable_with_why(self, tmp_path: Path) -> None:
        (tmp_path / "p.ddd.json").write_bytes(b'{"project": {"name": "\xff"}}')
        ((_, reason),) = find_projects(tmp_path).unreadable
        assert reason == "is not UTF-8 text"

    def test_a_file_that_cannot_be_opened_is_listed_as_unreadable_with_why(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        real = Path.read_bytes

        def refusing(self: Path) -> bytes:
            if self.name == "p.ddd.json":
                raise PermissionError(13, "Permission denied")
            return real(self)

        monkeypatch.setattr(Path, "read_bytes", refusing)
        found = find_projects(tmp_path)
        assert found.projects == ()
        assert [reason for _, reason in found.unreadable] == ["cannot be read: Permission denied"]

    def test_a_file_a_record_offers_that_does_not_parse_is_listed_once_as_a_project(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {"p.ddd.json": "{"})
        build_record(tmp_path, tmp_path / "p.ddd.json", image="firmware.elf")
        found = find_projects(tmp_path)
        assert [(p.path.name, p.name) for p in found.projects] == [("p.ddd.json", None)]
        assert found.unreadable == ()

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

    def test_a_record_that_names_no_image_offers_its_project_and_lists_none(
        self, tmp_path: Path
    ) -> None:
        """``ddd build-info`` without ``--image`` writes ``"image": ""``: not an image, and the
        start page printed ``built as`` for it with nothing after."""
        build_record(tmp_path, tmp_path / "gone.ddd.json", image="")
        (found,) = find_projects(tmp_path).projects
        assert (found.path.name, found.images) == ("gone.ddd.json", ())

    def test_an_image_two_records_name_is_listed_once_in_the_order_of_the_records(
        self, shared: Path
    ) -> None:
        """Two build trees configured for one image name it twice, one record each."""
        build_record(shared.parent, shared, image="firmware.elf")
        build_record(shared.parent, shared, image="tests.elf")
        again = shared.parent / "out" / "ddd-build.json"
        again.parent.mkdir()
        payload = {"format": 1, "project": shared.as_posix(), "image": "firmware.elf"}
        again.write_text(json.dumps(payload), encoding="utf-8")
        (found,) = find_projects(shared.parent).projects
        assert found.images == ("firmware.elf", "tests.elf")

    def test_a_record_that_cannot_be_used_is_reported_with_its_reason(self, shared: Path) -> None:
        build_record(shared.parent, shared, severity=["no-such-check=error"])
        with pytest.raises(UnknownCheckError) as expected:
            SeverityPolicy.from_strings(["no-such-check=error"], strict=False)
        found = find_projects(shared.parent)
        assert [reason for _, reason in found.refused] == [str(expected.value)]


class TestWhatTheWalkFindsAskedOfOnePath:
    """``walk_finds``, which ``POST /api/open`` asks of a path it holds before it walks (14:M14):
    held to the walk's own answer over every path of a tree holding each kind of place the walk
    leaves out, and each one's reason asked of it alone."""

    TREE: Final = {
        "p.ddd.json": project("Top"),
        ".hidden.ddd.json": project("Hidden file"),
        "a.ddd.json": component("A"),
        "notes.json": project("Not a description's name"),
        "cut.ddd.json": '{"project": {"name": "Cut"',
        "1/2/3/4/deep.ddd.json": project("Four deep"),
        "1/2/3/4/5/deeper.ddd.json": project("Five deep"),
        "src/s.ddd.json": project("Source"),
        ".git/g.ddd.json": project("Hidden"),
        "node_modules/m.ddd.json": project("Modules"),
        "build/b.ddd.json": project("Build"),
        "cmake-build-debug/c.ddd.json": project("CMake build"),
        "out/o.ddd.json": project("Out"),
        "elsewhere/e.ddd.json": project("Linked to"),
    }
    """A project description at each kind of place, and a file at each kind the walk passes."""

    def linked(self, tmp_path: Path) -> Path:
        """:attr:`TREE` under ``tmp_path / "root"``, its ``linked`` directory a link to its
        ``elsewhere``; returns the root."""
        root = tmp_path / "root"
        write_tree(root, self.TREE)
        directory_link(root / "linked", root / "elsewhere")
        return root

    def test_it_finds_what_the_walk_finds_and_nothing_else(self, tmp_path: Path) -> None:
        """The description reached through the link included, whichever way the platform's
        walk takes the link: a symbolic link is passed over, and so is Windows' junction, which
        ``directory_link`` makes there (``Path.walk`` on 3.13 and later takes it for a file;
        the walk states the rule itself for the 3.12 that would go into it). A path through a
        file is one no walk lists on any platform."""
        root = self.linked(tmp_path)
        walked = {found.path for found in find_projects(root).projects}
        paths = {path for path in root.rglob("*") if path.is_file()}
        paths |= {
            root / "linked" / "e.ddd.json",
            root / "a.ddd.json" / "x.ddd.json",
            root,
            root.parent / "p.ddd.json",
        }
        asked = {path for path in paths if walk_finds(root, path)}
        assert asked == walked
        assert sorted(
            path.relative_to(root).as_posix() for path in asked if "linked" not in path.parts
        ) == [
            ".hidden.ddd.json",
            "1/2/3/4/deep.ddd.json",
            "elsewhere/e.ddd.json",
            "p.ddd.json",
            "src/s.ddd.json",
        ]

    def test_a_junction_on_the_way_is_passed_over_as_the_walk_passes_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A directory answering ``is_junction()`` is not gone into, by the walk or by the
        question: Linux has no junctions, so one directory is made to answer so, as Windows'
        answers for the one ``directory_link`` makes there."""
        root = tmp_path / "root"
        write_tree(root, {"joined/j.ddd.json": project("Joined"), "p.ddd.json": project("Plain")})
        junction = root / "joined"
        is_junction = Path.is_junction

        def answering(self: Path) -> bool:
            return self == junction or is_junction(self)

        monkeypatch.setattr(Path, "is_junction", answering)
        walked = {found.path for found in find_projects(root).projects}
        assert walked == {root / "p.ddd.json"}
        assert walk_finds(root, root / "p.ddd.json")
        assert not walk_finds(root, junction / "j.ddd.json")

    def test_a_project_only_a_record_offers_is_not_one_it_finds(self, tmp_path: Path) -> None:
        """The walk offers it by the record, which this does not read."""
        root = tmp_path / "root"
        write_tree(tmp_path, {"far/f.ddd.json": project("Far"), "root/p.ddd.json": project("P")})
        build_record(root, tmp_path / "far" / "f.ddd.json")
        assert (tmp_path / "far" / "f.ddd.json").resolve() in {
            found.path for found in find_projects(root).projects
        }
        assert not walk_finds(root, (tmp_path / "far" / "f.ddd.json").resolve())

    @pytest.mark.parametrize(
        "locked", ["", "locked"], ids=["the-start-directory", "a-directory-under-it"]
    )
    def test_a_description_in_a_directory_the_walk_cannot_list_is_not_one_it_finds(
        self, tmp_path: Path, locked: str
    ) -> None:
        """A directory its owner may go through and not list - the start directory itself, or
        one under it: the walk cannot list it and passes it over, though a path through it reads
        the description, so neither finds what it holds. Windows keeps no mode that stops its
        owner listing a directory, and there the two find it alike; so does a process no mode
        binds."""
        root = tmp_path / "root"
        write_tree(root, {"locked/l.ddd.json": project("Locked")})
        description = root / "locked" / "l.ddd.json"
        (root / locked).chmod(0o311)
        try:
            walked = {found.path for found in find_projects(root).projects}
            asked = walk_finds(root, description)
        finally:
            (root / locked).chmod(0o755)
        assert asked is (description in walked)
        if os.name != "nt" and os.geteuid() != 0:
            assert not asked


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

    def test_a_record_naming_it_by_a_network_path_in_its_own_directory_feeds_its_analysis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A project outside the start directory, on a share, its build record naming it by a
        network path there: the record is read under every directory a request is served, the
        project's own among them, and its severities apply. The project's directory is taken for
        the share by its spelling, as Windows reads ``//server/share``: a network path is readable
        only under a directory spelled as one, and no directory a test makes is spelled so."""
        start = tmp_path / "start"
        far = tmp_path / "far"
        write_tree(
            far,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        start.mkdir()
        project_file = (far / "p.ddd.json").resolve()
        build_record(start, project_file, strict=True)
        monkeypatch.setattr(queries, "_NETWORK", re.compile(re.escape(far.resolve().as_posix())))
        revision = first_revision(start, project_file)
        assert [b.image for b in revision.builds] == ["firmware.elf"]
        unused = [f.diagnostic for f in revision.findings if f.diagnostic.check == "unused-output"]
        assert [d.severity.value for d in unused] == ["error"]

    @pytest.mark.parametrize("content", UNPARSED)
    def test_a_file_that_does_not_parse_is_listed_as_not_loaded(
        self, shared: Path, content: str
    ) -> None:
        (shared.parent / "b.ddd.json").write_text(content, encoding="utf-8")
        revision = first_revision(shared.parent, shared)
        broken = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert (broken.kind, broken.name, broken.loaded) == ("unknown", None, False)
        assert revision.dictionary is None

    def test_an_include_naming_a_file_that_is_not_there_is_the_file_that_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """The description holding the entry read and matched its shape, and the file the entry
        names is the one nothing could read: listed the other way round, every route told the
        reader the project description was what to repair."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "gone.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        described = {f.path.name: (f.kind, f.loaded) for f in revision.files}
        assert described == {
            "p.ddd.json": ("project", True),
            "a.ddd.json": ("component", True),
            "gone.ddd.json": ("unknown", False),
        }
        # The finding stays where the entry is: the description is the file to open to mend it.
        assert [(f.file.name, f.diagnostic.check) for f in revision.findings] == [
            ("p.ddd.json", "file-not-found")
        ]

    def test_an_include_naming_several_files_leaves_the_error_on_the_description(
        self, tmp_path: Path
    ) -> None:
        """A pattern does not say which of the files it matches could not be read, so none is
        named for it: the description holding it stays the file that did not load."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "lib/*.ddd.json"),
                "lib/a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        (tmp_path / "lib" / "bad.ddd.json").write_bytes(b"\xff\xfe{")
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        assert {f.path.name: f.loaded for f in revision.files} == {
            "p.ddd.json": False,
            "a.ddd.json": True,
            "bad.ddd.json": True,
        }

    def test_a_load_error_that_names_no_place_is_the_file_it_is_filed_on(
        self, tmp_path: Path
    ) -> None:
        """A finding with no place goes on the project description, and is about it."""
        project_file = tmp_path / "p.ddd.json"
        refusal = Diagnostic("schema", Severity.ERROR, "refused")
        warning = Diagnostic("schema", Severity.WARNING, "only a warning")
        assert module._unloaded({project_file: [refusal]}) == {project_file}
        assert module._unloaded({project_file: [warning]}) == set()

    def test_a_file_that_cannot_be_read_is_described_as_empty(self, tmp_path: Path) -> None:
        described = module._described(tmp_path / "gone.ddd.json", [], None)
        assert (described.kind, described.fingerprint) == ("unknown", fingerprint(b""))

    def test_a_plugin_which_no_read_parses_is_fingerprinted_as_it_stands(
        self, tmp_path: Path
    ) -> None:
        """A plugin is imported, never parsed, so no run's read records its bytes: it is read
        once the analysis is over, and named by nothing in it."""
        write_tree(
            tmp_path,
            {
                "tools/demo_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        plugin = next(f for f in revision.files if f.path.name == "demo_plugin.py")
        source = (tmp_path / "tools" / "demo_plugin.py").read_bytes()
        assert (plugin.kind, plugin.name, plugin.fingerprint) == (
            "plugin",
            None,
            fingerprint(source),
        )

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

    def test_a_revision_fingerprints_the_bytes_its_analysis_read(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file is fingerprinted as the analysis read it, never as the disk holds it once the
        analysis is over: the fingerprint is what every plan made from the revision's index
        carries, and of bytes saved after the read it would let a plan pointing into the bytes
        that were read be applied to the ones saved."""
        consumer = shared.parent / "b.ddd.json"
        read = consumer.read_bytes()
        monkeypatch.setattr(module, "run_project", saving_while_analysing(consumer, b'"Hz"'))
        session = Session(shared.parent)
        session.open(shared)
        monkeypatch.undo()
        revision = session.revision
        assert revision is not None
        described = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert consumer.read_bytes() != read
        assert described.fingerprint == fingerprint(read)

    def test_an_edit_planned_from_that_revision_is_refused_as_stale(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An edit carrying the fingerprint that revision gives the file meets the save on disk
        and is refused as stale, the save kept as it was written: what the edit was planned from
        is not what the file holds."""
        consumer = shared.parent / "b.ddd.json"
        monkeypatch.setattr(module, "run_project", saving_while_analysing(consumer, b'"Hz"'))
        session = Session(shared.parent)
        session.open(shared)
        monkeypatch.undo()
        revision = session.revision
        assert revision is not None
        described = next(f for f in revision.files if f.path.name == "b.ddd.json")
        saved = consumer.read_bytes()
        change = FileChange(
            consumer,
            described.fingerprint,
            (Operation("set", "component.interface[0].definition.unit", '"V"'),),
        )
        with pytest.raises(EditError) as refused:
            session.edit([change], "the unit of Speed")
        assert refused.value.code == STALE
        assert consumer.read_bytes() == saved

    def test_a_file_two_builds_read_differently_is_fingerprinted_as_the_first_read_it(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each build naming the project is a run of its own, and each reads every file: a save
        landing between two of them makes them read it differently. The first run's read is the
        one the revision's index comes from, and so the fingerprint the revision gives the file,
        which a plan made from that index carries."""
        build_record(shared.parent, shared, image="one.elf")
        build_record(shared.parent, shared, image="two.elf")
        consumer = shared.parent / "b.ddd.json"
        read = consumer.read_bytes()
        real = module.run_build
        ran: list[str] = []

        def run(info: BuildInfo, *, includes: Sequence[str] | None = None) -> Run:
            answer = real(info, includes=includes)
            ran.append(info.image)
            if len(ran) == 1:
                consumer.write_bytes(read.replace(b'"rpm"', b'"Hz"'))
            return answer

        monkeypatch.setattr(module, "run_build", run)
        session = Session(shared.parent)
        session.open(shared)
        monkeypatch.undo()
        revision = session.revision
        assert revision is not None and len(ran) == 2
        described = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert described.fingerprint == fingerprint(read)

    def test_a_file_two_builds_read_differently_is_fingerprinted_as_the_index_s_run_read_it(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The revision's index is the first run's that built one: where the first run read the
        project description no further - its ``includes`` no list - it is the second run's. The
        description, saved whole between the two runs and put back after, is fingerprinted as the
        index's run read it, so that a plan made from that index is refused as stale against the
        bytes put back, rather than applied to bytes the index does not describe."""
        build_record(shared.parent, shared, image="one.elf")
        build_record(shared.parent, shared, image="two.elf")
        whole = shared.read_bytes()
        cut = json.dumps({"project": {"name": "P", "includes": 7}}).encode()
        shared.write_bytes(cut)
        real = module.run_build
        ran: list[str] = []

        def run(info: BuildInfo, *, includes: Sequence[str] | None = None) -> Run:
            answer = real(info, includes=includes)
            ran.append(info.image)
            if len(ran) == 1:
                shared.write_bytes(whole)
            elif len(ran) == 2:
                shared.write_bytes(cut)
            return answer

        monkeypatch.setattr(module, "run_build", run)
        session = Recording(shared.parent)
        session.open(shared)
        monkeypatch.undo()
        first = session.left[0].revision
        assert first is not None and first.index is not None
        assert ran[:2] == ["one.elf", "two.elf"]
        described = next(f for f in first.files if f.path == shared.resolve())
        assert described.fingerprint == fingerprint(whole)

    def test_a_root_read_no_further_is_fingerprinted_as_read_though_saved_since(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A project description the loader reads no further than - its ``includes`` no list -
        still makes a revision, of that one file: described as the analysis read it, though
        saved before the revision lands."""
        root = tmp_path / "p.ddd.json"
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 7}}})
        read = root.read_bytes()
        real = module.run_project

        def run(project_file: Path, *, includes: Sequence[str] | None = None) -> Run:
            answer = real(project_file, includes=includes)
            write_tree(tmp_path, {"p.ddd.json": project("Q")})
            return answer

        monkeypatch.setattr(module, "run_project", run)
        session = Session(tmp_path)
        session.open(root)
        monkeypatch.undo()
        revision = session.revision
        assert revision is not None and revision.index is None
        (described,) = revision.files
        assert (described.kind, described.name, described.fingerprint) == (
            "project",
            "P",
            fingerprint(read),
        )

    def test_a_file_the_analysis_found_missing_is_described_as_found_though_saved_since(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing when the analysis read it, and saved before the revision lands: the revision
        describes it as the analysis found it, of no kind and fingerprinted of no bytes at all,
        so that nothing takes it for a file read as it now stands - the analysis's findings say
        it does not exist."""
        consumer = shared.parent / "b.ddd.json"
        saved = consumer.read_bytes()
        consumer.unlink()
        real = module.run_project

        def run(project_file: Path, *, includes: Sequence[str] | None = None) -> Run:
            answer = real(project_file, includes=includes)
            consumer.write_bytes(saved)
            return answer

        monkeypatch.setattr(module, "run_project", run)
        session = Session(shared.parent)
        session.open(shared)
        monkeypatch.undo()
        revision = session.revision
        assert revision is not None
        described = next(f for f in revision.files if f.path.name == "b.ddd.json")
        assert (described.kind, described.name, described.fingerprint) == (
            "unknown",
            None,
            fingerprint(b""),
        )
        assert "file-not-found" in {filed.diagnostic.check for filed in revision.findings}

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

    def test_a_save_made_to_a_file_the_analysis_brought_in_is_picked_up_by_the_analysis_it_asks(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file the project did not have when the poll stamped its files has no stamp of its
        own, so the revision that read it asks for one analysis more at once - which is what
        catches a save made to it while the analysis that brought it in ran, with no poll after
        it: this session polls an hour apart. The analysis it asks for is held while revision 2 is
        read, whose lack of any disagreement shows that the analysis bringing the file in read it
        before the save."""
        session = Stepped(shared.parent)
        opening, bringing, asked = session.goes
        opening.set()
        bringing.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            landed(session)
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
            begun(session)  # the analysis bringing c.ddd.json in, saving it once it has read it
            begun(session)  # the one its revision asks for, held
            monkeypatch.undo()
            brought = session.revision
            assert brought is not None and brought.number == 2
            assert mismatches(session) == 0
            asked.set()
            caught = landed(session).revision
            assert caught is not None and caught.number == 3
            assert mismatches(session) == 2
        finally:
            for go in session.goes:
                go.set()
            stopped(session)

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


class Recording(Session):
    """A session that keeps what it says at the end of each analysis, read in the same hold of the
    lock that published what the analysis left: what it says from that moment, since no reader -
    a page's long poll, the journeys' fixture - can read it in between, every one holding the lock
    to read."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, poll_interval=3600)
        self.left: list[Snapshot] = []

    def _finished(
        self, begun: module._Begun, revision: Revision | None, failed: str | None
    ) -> None:
        super()._finished(begun, revision, failed)
        self.left.append(self._snapshot())


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
            landed(session)
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
            landed(session)
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
            landed(session)
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            assert session.poll() is False
            session.gate.set()
            landed(session)
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

    def test_an_analysis_failing_on_the_thread_is_said_until_one_succeeds(
        self, shared: Path
    ) -> None:
        """14:M7. The reason an analysis raised is part of what the session says, the revision
        before it standing as the newest meanwhile - not that revision alone, as though no
        analysis had been asked for - until an analysis succeeds."""
        session = SecondFails(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            first = landed(session)
            assert first.failed is None
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            failed = landed(session)
            assert (failed.revision, failed.failed) == (first.revision, "boom")
            assert failed.version > first.version
            assert session.poll() is True
            mended = landed(session)
            assert mended.revision is not first.revision and mended.failed is None
        finally:
            stopped(session)

    def test_a_first_analysis_failing_is_said_with_no_revision_to_stand(self, shared: Path) -> None:
        """14:M7. Before any revision the page was told the project was being analysed, and
        nothing else, for as long as each analysis failed."""

        class FirstFails(Gated):
            def _analysed(self, project: Path) -> Revision:
                revision = super()._analysed(project)
                if self.analyses == 1:
                    raise RuntimeError("boom")
                return revision

        session = FirstFails(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            failed = landed(session)
            assert (failed.revision, failed.failed) == (None, "boom")
            assert session.poll() is True
            mended = landed(session)
            assert mended.revision is not None and mended.failed is None
        finally:
            stopped(session)

    def test_where_no_analyser_runs_a_failure_is_said_as_well_as_raised(self, shared: Path) -> None:
        """The call that asked for the analysis is told by the exception, and every other reader
        of the session by what it says, as from the analyser's thread."""

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
        assert session.snapshot().failed == "boom"
        assert session.poll() is True
        assert session.snapshot().failed is None

    def test_a_failure_with_no_words_is_said_by_its_class(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An exception raised with nothing to say - ``RuntimeError()`` - is said by its class's
        name, in the terminal and in what the session says alike, rather than as nothing: an
        empty reason reads as no failure at all."""

        class Wordless(SecondFails):
            def _analysed(self, project: Path) -> Revision:
                try:
                    return super()._analysed(project)
                except RuntimeError:
                    raise RuntimeError() from None

        session = Wordless(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            landed(session)
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert landed(session).failed == "RuntimeError"
            assert capsys.readouterr().err.splitlines()[-1] == (
                "ddd gui: analysing the project failed: RuntimeError"
            )
        finally:
            stopped(session)

    def test_opening_a_project_lets_go_of_the_last_ones_failure(self, shared: Path) -> None:
        """The failure is the open project's: another opened is said not to have failed while
        its own first analysis runs."""
        write_tree(shared.parent, {"other/q.ddd.json": project("Q")})

        class FirstFails(Gated):
            def _analysed(self, project: Path) -> Revision:
                revision = super()._analysed(project)
                if self.analyses == 1:
                    raise RuntimeError("boom")
                return revision

        session = FirstFails(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert landed(session).failed == "boom"
            session.gate.clear()
            session.open(shared.parent / "other" / "q.ddd.json")
            begun(session)
            opened = session.snapshot()
            assert (opened.revision, opened.analysing, opened.failed) == (None, True, None)
        finally:
            session.gate.set()
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
            landed(session)
            monkeypatch.setattr(sys, "stderr", recording)
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            landed(session)
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
        """Opening answers with the revision, the path listed as an empty file of no kind that did
        not load, and its refusal filed where the project names it."""
        project_file = unreachable(tmp_path)
        session = Session(tmp_path)
        session.open(project_file)
        revision = session.revision
        assert revision is not None and findings_of(revision) == [unreadable(project_file)]
        described = {f.path.name: (f.kind, f.loaded, f.fingerprint) for f in revision.files}
        assert described == {
            "p.ddd.json": ("project", True, fingerprint(project_file.read_bytes())),
            "a.ddd.json": ("component", True, fingerprint((tmp_path / "a.ddd.json").read_bytes())),
            NUL_ENTRY: ("unknown", False, fingerprint(b"")),
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
            landed(session)
            at, _ = session.edit(adoption(shared), "the vocabulary adopted")
            begun(session)
            landed(session)
            session.undo(at)
            begun(session)
            landed(session)
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
        assert Session(tmp_path).snapshot() == Snapshot(0, None, None, False, None, None)

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

    def test_an_analysis_asked_for_is_analysing_before_any_runs(self, shared: Path) -> None:
        """Asked for counts as running does: the version moves when an edit asks, not when the
        analyser takes the request up, so a second window hearing of the edit has to hear
        ``analysing`` then. With the analyser stopped, nothing takes the request up and nothing
        runs - only the request says so."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            landed(session)
        finally:
            stopped(session)
        session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        snapshot = session.snapshot()
        assert (snapshot.analysing, session.analyses) == (True, 1)

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

    def test_a_sub_projects_files_cost_opening_one_analysis_more_asked_at_once(
        self, tmp_path: Path
    ) -> None:
        """Opening reads no sub-project's own ``includes``, so the first analysis reads its files
        with no stamp from before: the revision it publishes asks for the next analysis itself,
        and opening ends with both made, leaving the poll nothing to find."""
        session = Session(tmp_path)
        session.open(with_a_sub_project(tmp_path))
        assert session.revision is not None and session.revision.number == 2
        assert session.poll() is False

    def test_a_revision_that_read_a_file_with_no_stamp_is_published_analysing(
        self, tmp_path: Path
    ) -> None:
        """Said in the hold of the lock that publishes the revision, so that no reader ever hears
        the first one with nothing analysing: whatever waits for the project to be analysed - a
        page, or the journeys' own fixture - waits for the second too, rather than hearing that
        the findings have settled and then that they are updating again. Asked in a hold of its
        own after that one, the request would leave a moment in which the session said so."""
        session = Recording(tmp_path)
        session.open(with_a_sub_project(tmp_path))
        first, second = session.left
        assert first.revision is not None and first.revision.number == 1
        assert first.analysing is True
        assert second.revision is not None and second.revision.number == 2
        assert second.analysing is False

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


def moved(path: Path) -> None:
    """``path``'s modification time moved back ten seconds, its access time kept: what creating or
    removing an entry does to a directory's time, made sure of. A directory written in the tick
    its stamp was taken in can keep the time it had, the clock's granularity deciding, and its
    size says nothing on most systems; a test of what the poll stamps leaves neither to chance."""
    status = path.stat()
    os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns - 10**10))


def checks_of(session: Session) -> dict[str, Severity]:
    """Each check the newest revision reports, at the severity it reports it at."""
    revision = session.revision
    assert revision is not None
    return {filed.diagnostic.check: filed.diagnostic.severity for filed in revision.findings}


NAMED_PLUGIN = 'from ddd.plugins import Plugin\n\nPLUGIN = Plugin(name="named")\n'
"""A plugin that loads and does nothing."""

MODELLED_PLUGIN = """
from pydantic import BaseModel, field_validator

from ddd.plugins import Plugin


class Settings(BaseModel):
    level: int = 0

    @field_validator("level")
    @classmethod
    def broken(cls, value: int) -> int:
        raise RuntimeError("the model is broken")


PLUGIN = Plugin(name="modelled", project_model=Settings)
"""
"""A plugin whose own model raises on the project's block: what ends the read of a project naming
it, ``plugin-invalid``, the run covering the project description alone."""


def a_pattern_of_writers(base: Path, pattern: str, first: str) -> Path:
    """A project including ``pattern``, and the file ``first`` it matches, writing ``Speed``;
    returns the project file."""
    write_tree(
        base,
        {
            "p.ddd.json": project("P", pattern),
            first: component("W", declare("output", "Speed", unit="rpm")),
        },
    )
    return base / "p.ddd.json"


def a_second_writer(path: Path) -> None:
    """A component at ``path`` writing ``Speed`` too: ``multiple-producers``, once it is read."""
    write_tree(path.parent, {path.name: component("X", declare("output", "Speed", unit="rpm"))})


def record_beside(project_file: Path) -> Path:
    """The build record every revision watches beside its project description, there or not:
    the one that says whether a build generates it."""
    return project_file.resolve().parent / "ddd-build.json"


class TestWhatThePollWatches:
    """Beside the files an analysis read, the poll stamps what decides which files there are and
    how they are graded (14:I5): the directory each wildcard include expands in, every file a
    ``plugins`` list names by its path, loaded or not, and every build record the search finds, a
    refused one among them. A change none of the files shows makes a new revision all the same,
    and it says what ``ddd check`` says then."""

    def test_a_component_added_on_a_pattern_makes_a_new_revision(self, tmp_path: Path) -> None:
        """``comps/*.ddd.json`` matches a second writer of ``Speed`` once it is saved there, which
        ``ddd check`` reports as ``multiple-producers``: so does the next revision, the directory
        the pattern expands in having moved."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*.ddd.json", "comps/w.ddd.json")
        session = opened_and_settled(project_file)
        assert "multiple-producers" not in checks_of(session)
        a_second_writer(tmp_path / "comps" / "x.ddd.json")
        moved(tmp_path / "comps")
        assert session.poll() is True
        assert checks_of(session)["multiple-producers"] is Severity.ERROR

    def test_a_file_saved_where_a_recursive_pattern_walks_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``lib/**/*.ddd.json`` expands in every directory it walks, the ones below ``lib``
        among them."""
        project_file = a_pattern_of_writers(tmp_path, "lib/**/*.ddd.json", "lib/a/w.ddd.json")
        session = opened_and_settled(project_file)
        a_second_writer(tmp_path / "lib" / "a" / "x.ddd.json")
        moved(tmp_path / "lib" / "a")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_a_directory_made_where_a_recursive_pattern_walks_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``lib/**/c.ddd.json`` looks ``c.ddd.json`` up in every directory the ``**`` walks, and
        lists each of them for its subdirectories: one made below ``lib/a``, holding one, is
        noticed by the time of ``lib/a``."""
        project_file = a_pattern_of_writers(tmp_path, "lib/**/c.ddd.json", "lib/a/c.ddd.json")
        session = opened_and_settled(project_file)
        a_second_writer(tmp_path / "lib" / "a" / "b" / "c.ddd.json")
        moved(tmp_path / "lib" / "a")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_a_file_saved_where_a_second_wildcard_matches_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``lib/*/*.ddd.json`` matches its last name in each directory its first wildcard
        matches: a writer saved in ``lib/a`` is noticed by the time of ``lib/a``."""
        project_file = a_pattern_of_writers(tmp_path, "lib/*/*.ddd.json", "lib/a/w.ddd.json")
        session = opened_and_settled(project_file)
        a_second_writer(tmp_path / "lib" / "a" / "x.ddd.json")
        moved(tmp_path / "lib" / "a")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_a_directory_made_where_a_wildcard_matches_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``comps/*/c.ddd.json`` lists ``comps`` for the directories its wildcard matches, and
        looks ``c.ddd.json`` up in each: a directory made there, holding one, is noticed by the
        time of ``comps``."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*/c.ddd.json", "comps/a/c.ddd.json")
        session = opened_and_settled(project_file)
        a_second_writer(tmp_path / "comps" / "b" / "c.ddd.json")
        moved(tmp_path / "comps")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_a_file_saved_in_a_directory_a_wildcard_matched_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``c.ddd.json`` is looked up in every directory ``comps/*`` matches, there or not: one
        saved in ``comps/b``, which held none, is noticed by its own stamp, though no directory
        the pattern lists gained an entry."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*/c.ddd.json", "comps/a/c.ddd.json")
        (tmp_path / "comps" / "b").mkdir()
        session = opened_and_settled(project_file)
        a_second_writer(tmp_path / "comps" / "b" / "c.ddd.json")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_the_directory_a_pattern_names_made_with_a_file_in_it_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``extra/*.ddd.json`` names a directory that is not there yet: stamped as not there, it
        is noticed once it is made, a second writer of ``Speed`` in it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "extra/*.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert "include-empty" in checks_of(session)
        a_second_writer(tmp_path / "extra" / "x.ddd.json")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_the_directory_a_recursive_pattern_starts_in_made_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        """``extra/**/*.ddd.json`` walks nothing while ``extra`` is not there, so ``extra`` is
        watched itself, stamped as not there: made with a writer below it, it is noticed."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "extra/**/*.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        session = opened_and_settled(tmp_path / "p.ddd.json")
        a_second_writer(tmp_path / "extra" / "a" / "x.ddd.json")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    def test_a_file_saved_where_no_pattern_expands_asks_for_nothing(self, tmp_path: Path) -> None:
        """An editor's swap file beside the description: ``comps/*.ddd.json`` looks ``comps`` up
        there and lists nothing else, so that directory's time is no stamp of the project."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*.ddd.json", "comps/w.ddd.json")
        session = opened_and_settled(project_file)
        (tmp_path / ".p.ddd.json.swp").write_bytes(b"")
        moved(tmp_path)
        assert session.poll() is False

    def test_a_file_saved_in_a_directory_a_pattern_only_passes_through_asks_for_nothing(
        self, tmp_path: Path
    ) -> None:
        """``src/components/*.ddd.json`` looks ``src`` up on its way to ``components`` and lists
        only that: a swap file of a C source saved in ``src`` is no change of the project. The
        path ``src/components`` is stamped there or not, so its being made is noticed all the
        same."""
        project_file = a_pattern_of_writers(
            tmp_path, "src/components/*.ddd.json", "src/components/w.ddd.json"
        )
        session = opened_and_settled(project_file)
        (tmp_path / "src" / ".main.c.swp").write_bytes(b"")
        moved(tmp_path / "src")
        assert session.poll() is False
        assert session.revision is not None and session.revision.number == 1

    def test_a_file_saved_beside_the_checkout_a_pattern_climbs_out_of_asks_for_nothing(
        self, tmp_path: Path
    ) -> None:
        """``../shared/*.ddd.json`` climbs out of the project's directory to ``shared``: the
        directory holding the checkout, where a sibling clone lies, is only passed through."""
        checkout = tmp_path / "project"
        write_tree(
            tmp_path,
            {
                "project/p.ddd.json": project("P", "../shared/*.ddd.json"),
                "shared/w.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
            },
        )
        session = opened_and_settled(checkout / "p.ddd.json")
        (tmp_path / "sibling").mkdir()
        moved(tmp_path)
        assert session.poll() is False
        a_second_writer(tmp_path / "shared" / "x.ddd.json")
        moved(tmp_path / "shared")
        assert session.poll() is True
        assert "multiple-producers" in checks_of(session)

    @pytest.mark.parametrize(
        ("pattern", "other"),
        [("lib/**/*.ddd.json", "lib/a/notes.txt"), ("lib/*/*.ddd.json", "lib/n")],
    )
    def test_a_file_no_pattern_matches_rewritten_where_one_walks_asks_for_nothing(
        self, tmp_path: Path, pattern: str, other: str
    ) -> None:
        """A pattern's walk is watched by its directories alone: a file it passes over, rewritten
        in place, is no change of the project, though pathlib's walk meets it - ``**`` yields
        files too from python 3.13 on, and a wildcard followed by a name matches them as well.
        The directory it lies in keeps its time, as a write in place leaves it."""
        project_file = a_pattern_of_writers(tmp_path, pattern, "lib/a/w.ddd.json")
        passed_over = tmp_path / other
        passed_over.write_text("notes", encoding="utf-8")
        session = opened_and_settled(project_file)
        status = passed_over.parent.stat()
        passed_over.write_text("notes, longer", encoding="utf-8")
        os.utime(passed_over.parent, ns=(status.st_atime_ns, status.st_mtime_ns))
        assert session.poll() is False

    def test_a_pattern_with_its_wildcards_in_its_last_name_is_listed_by_the_loader_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``comps/*.ddd.json`` expands in ``comps``, which its names lead to: watching it lists no
        directory, and the one listing of ``comps`` an analysis makes is the loader's own, over
        what is most of a large project's files."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*.ddd.json", "comps/w.ddd.json")
        session = opened_and_settled(project_file)
        globbed: list[str] = []
        real = Path.glob

        def counted(self: Path, pattern: str, *arguments: Any, **keywords: Any) -> object:
            globbed.append(pattern)
            return real(self, pattern, *arguments, **keywords)

        monkeypatch.setattr(Path, "glob", counted)
        project_file.write_bytes(project_file.read_bytes() + b" ")
        assert session.poll() is True
        revision = session.revision
        assert revision is not None
        assert revision.watched == ((tmp_path / "comps").resolve(), record_beside(project_file))
        assert globbed.count("comps/*.ddd.json") == 1

    def test_an_analysis_reads_the_descriptions_again_and_no_component(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """What a revision watches is read off the project descriptions its analysis read, read
        again for their lists: never off a component, which states neither and is most of a large
        project's bytes."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*.ddd.json", "comps/w.ddd.json")
        session = opened_and_settled(project_file)
        read: list[str] = []
        real = module.read_json

        def recorded(path: Path) -> Any:
            read.append(path.name)
            return real(path)

        monkeypatch.setattr(module, "read_json", recorded)
        (tmp_path / "comps" / "w.ddd.json").write_text(
            json.dumps(component("W", declare("output", "Speed", unit="Hz"))), encoding="utf-8"
        )
        assert session.poll() is True
        assert "p.ddd.json" in read
        assert "w.ddd.json" not in read

    def test_an_entry_naming_a_file_not_there_watches_no_directory(self, tmp_path: Path) -> None:
        """``sub/gone.ddd.json`` names a file, stamped as not there by the revision's files: the
        directory ``sub`` it would lie in is not watched, and a file saved there is no change."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "sub/gone.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "sub/kept.txt": "kept",
            },
        )
        session = opened_and_settled(tmp_path / "p.ddd.json")
        (tmp_path / "sub" / "other.txt").write_text("other", encoding="utf-8")
        moved(tmp_path / "sub")
        assert session.poll() is False

    def test_an_entry_naming_a_file_watches_no_directory(self, tmp_path: Path) -> None:
        """``v[2].ddd.json`` names the file of that name, which the loader reads before it reads
        the entry as a pattern: ``v2.ddd.json`` saved beside it is no file of the project."""
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "v[2].ddd.json"), "v[2].ddd.json": component("V")},
        )
        session = opened_and_settled(tmp_path / "p.ddd.json")
        a_second_writer(tmp_path / "v2.ddd.json")
        moved(tmp_path)
        assert session.poll() is False

    def test_a_pattern_the_platform_refuses_to_expand_is_analysed_all_the_same(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Platforms disagree about which patterns they accept: the analysis reports one refused
        as ``include-empty``, and it watches no directory. Refused for the include's pattern
        alone, the search for build records globbing its own."""
        project_file = a_pattern_of_writers(tmp_path, "lib/**/*.ddd.json", "lib/a/w.ddd.json")
        real = Path.glob

        def refuse(self: Path, pattern: str, *arguments: Any, **keywords: Any) -> object:
            if pattern.startswith("lib/"):
                msg = "Non-relative patterns are unsupported"
                raise NotImplementedError(msg)
            return real(self, pattern, *arguments, **keywords)

        monkeypatch.setattr(Path, "glob", refuse)
        session = Session(tmp_path)
        session.open(project_file)
        assert "include-empty" in checks_of(session)
        revision = session.revision
        assert revision is not None and revision.watched == (record_beside(project_file),)

    def test_a_plugin_named_and_then_created_makes_a_new_revision(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["named.py"])})
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert "plugin-not-found" in checks_of(session)
        (tmp_path / "named.py").write_text(NAMED_PLUGIN, encoding="utf-8")
        assert session.poll() is True
        assert checks_of(session) == {}

    def test_a_plugin_that_failed_to_import_and_is_mended_makes_a_new_revision(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["named.py"])})
        (tmp_path / "named.py").write_text('raise RuntimeError("broken")\n', encoding="utf-8")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert "plugin-invalid" in checks_of(session)
        (tmp_path / "named.py").write_text(NAMED_PLUGIN, encoding="utf-8")
        assert session.poll() is True
        assert checks_of(session) == {}

    def test_a_plugin_named_beside_one_that_ends_the_read_is_watched_all_the_same(
        self, tmp_path: Path
    ) -> None:
        """A plugin whose model raises on the project's block ends the read, and the run covers
        the project description alone: another plugin the description names by its path, missing
        then created, is watched though no run noted its file."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P",
                    plugins=["modelled.py", "named.py"],
                    extensions={"modelled": {"level": 1}},
                ),
            },
        )
        (tmp_path / "modelled.py").write_text(MODELLED_PLUGIN, encoding="utf-8")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        revision = session.revision
        assert revision is not None and [file.path.name for file in revision.files] == [
            "p.ddd.json"
        ]
        assert "plugin-not-found" in checks_of(session)
        (tmp_path / "named.py").write_text(NAMED_PLUGIN, encoding="utf-8")
        assert session.poll() is True
        assert "plugin-not-found" not in checks_of(session)

    def test_a_plugin_named_as_a_module_is_watched_by_the_files_its_run_noted(
        self, tmp_path: Path
    ) -> None:
        """A module is no path: finding its file can import its parents, so the watch passes it
        over, and its files are the ones the run noted, which the revision's files stamp. The
        standard library's ``json`` is a module no plugin is made of: ``plugin-invalid``."""
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["json"])})
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        assert "plugin-invalid" in {filed.diagnostic.check for filed in revision.findings}
        assert revision.watched == (record_beside(tmp_path / "p.ddd.json"),)
        assert Path(json.__file__).resolve() in {file.path for file in revision.files}

    def test_a_nul_in_a_plugin_path_beside_a_schema_error_ends_no_analysis(
        self, tmp_path: Path
    ) -> None:
        """A description that does not validate loads none of the plugins it names, and ``ddd
        check`` reports the error it does not validate for, ``schema``: so does the analysis,
        the description naming a plugin by a path holding a NUL beside that error. The watch
        reads every description's ``plugins``, one that does not validate among them, and
        resolving that path raised, so that every analysis failed, at every poll."""
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=[NUL_PLUGIN], unknown=1)})
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert checks_of(session) == {"schema": Severity.ERROR}
        assert session.poll() is False

    @pytest.mark.parametrize(
        "error",
        [
            OSError(40, "Too many levels of symbolic links"),
            ValueError("embedded null byte"),
            RuntimeError("Symlink loop from 'loop.py'"),
            RecursionError("maximum recursion depth exceeded"),
        ],
        ids=["an-os-error", "a-nul", "a-loop-on-python-3.12", "a-chain-of-links-on-python-3.12"],
    )
    def test_a_plugin_path_that_cannot_be_resolved_is_not_watched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        """Each exception ``Path.resolve`` raises for a path the system will not resolve, as the
        loader's ``resolve_path`` lists them, one test each, so that none drops out of the watch's
        guard unseen: the path names no file to watch, and the analysis reports what ``ddd
        check`` reports of the description, here that it does not validate."""
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["loop.py"], unknown=1)})
        real = Path.resolve

        def refuse(self: Path, *args: Any, **kwargs: Any) -> Path:
            if self.name == "loop.py":
                raise error
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", refuse)
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert checks_of(session) == {"schema": Severity.ERROR}
        revision = session.revision
        assert revision is not None
        assert revision.watched == (record_beside(tmp_path / "p.ddd.json"),)

    def test_a_build_record_rewritten_makes_a_new_revision_under_its_severities(
        self, tmp_path: Path
    ) -> None:
        """A reconfigure with ``--strict``: ``ddd check --strict`` reports the output nobody reads
        as an error, and so does the next revision."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        record = build_record(tmp_path, project_file)
        session = opened_and_settled(project_file)
        assert checks_of(session)["unused-output"] is Severity.WARNING
        build_record(tmp_path, project_file, strict=True)
        assert session.poll() is True
        assert checks_of(session)["unused-output"] is Severity.ERROR
        assert record.is_file()

    def test_a_refused_build_record_mended_makes_a_new_revision_under_its_severities(
        self, tmp_path: Path
    ) -> None:
        """A record a newer DDD wrote is refused, and the project analysed under the defaults; the
        record written again by this one's build applies."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, format=99)
        session = opened_and_settled(project_file)
        assert session.revision is not None and session.revision.builds == ()
        build_record(tmp_path, project_file, strict=True)
        assert session.poll() is True
        assert session.revision is not None and len(session.revision.builds) == 1
        assert checks_of(session)["unused-output"] is Severity.ERROR

    def test_a_refused_build_record_is_carried_by_its_revision_and_printed_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """14:M11. A record this DDD cannot use was said on the start page alone, which a project
        opened on the command line never draws, and the terminal said nothing: the revision
        carries it now, with its reason, and the terminal gets its line as the language server
        logs one - once, and again whenever that changes, never at every analysis."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        record = build_record(tmp_path, project_file, format=99).resolve()
        reason = (
            f"written in format 99 by a newer DDD, and this one understands up to format "
            f"{BUILD_INFO_FORMAT}"
        )
        line = (
            f"ddd gui: {record}: {reason}; this record is ignored, so its severities apply to "
            "no analysis"
        )
        session = opened_and_settled(project_file)
        assert session.revision is not None and session.revision.refused == ((record, reason),)
        assert capsys.readouterr().err.splitlines() == [line]
        component_file = tmp_path / "a.ddd.json"
        component_file.write_text(
            component_file.read_text(encoding="utf-8").replace('"rpm"', '"Hz"'), encoding="utf-8"
        )
        assert session.poll() is True
        assert session.revision.refused == ((record, reason),)
        assert capsys.readouterr().err == ""
        build_record(tmp_path, project_file)
        assert session.poll() is True
        assert session.revision.refused == ()
        assert capsys.readouterr().err == ""
        build_record(tmp_path, project_file, format=99)
        assert session.poll() is True
        assert capsys.readouterr().err.splitlines() == [line]

    def test_a_record_refused_again_for_another_reason_is_told_again(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """14:M11. The line says why the record is ignored, so the same record refused for
        another reason, with no mending between, is a new line."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        record = build_record(tmp_path, project_file, format=99).resolve()
        session = opened_and_settled(project_file)
        first = capsys.readouterr().err.splitlines()
        assert len(first) == 1 and "format 99" in first[0]
        build_record(tmp_path, project_file, severity=["nonesuch"])
        component_file = tmp_path / "a.ddd.json"
        component_file.write_text(
            component_file.read_text(encoding="utf-8").replace('"rpm"', '"Hz"'), encoding="utf-8"
        )
        assert session.poll() is True
        assert session.revision is not None and len(session.revision.refused) == 1
        refused, reason = session.revision.refused[0]
        assert refused == record and "format 99" not in reason
        assert capsys.readouterr().err.splitlines() == [
            f"ddd gui: {record}: {reason}; this record is ignored, so its severities apply to "
            "no analysis"
        ]

    def test_a_refused_record_s_line_that_cannot_be_printed_ends_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The line is printed by whichever call made the analysis - opening the project, here,
        where no analyser runs - and lost where standard error cannot be written, as a failure's
        is: the call is answered all the same, and the revision published (14:M11)."""

        class Unwritable(io.StringIO):
            def write(self, text: str) -> int:
                raise OSError("standard error is closed")

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, format=99)
        session = Session(tmp_path)
        monkeypatch.setattr(sys, "stderr", Unwritable())
        session.open(project_file)
        assert session.revision is not None and len(session.revision.refused) == 1

    def test_a_revision_watches_every_description_s_patterns_its_plugins_and_the_records(
        self, tmp_path: Path
    ) -> None:
        """A sub-project's pattern as much as the project's own, the plugin a description names
        by its path, the records the search finds and the one beside the project description,
        which is not there."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "comps/*.ddd.json", "sub/s.ddd.json"),
                "comps/w.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
                "sub/s.ddd.json": project("S", "lib/*.ddd.json", plugins=["named.py"]),
                "sub/named.py": NAMED_PLUGIN,
            },
        )
        project_file = tmp_path / "p.ddd.json"
        record = build_record(tmp_path, project_file)
        revision = first_revision(tmp_path, project_file)
        root = tmp_path.resolve()
        assert revision.watched == tuple(
            sorted(
                {
                    root / "comps",
                    root / "sub" / "lib",
                    root / "sub" / "named.py",
                    record.resolve(),
                    record_beside(project_file),
                }
            )
        )

    def test_opening_a_project_with_a_pattern_and_a_build_record_analyses_it_once(
        self, tmp_path: Path
    ) -> None:
        """Opening stamps the directories its own patterns expand in, and the build records the
        search finds, before the first analysis reads anything, as it stamps the files its own
        includes name: watched from that analysis on, they cost it no second one."""
        project_file = a_pattern_of_writers(tmp_path, "comps/*.ddd.json", "comps/w.ddd.json")
        build_record(tmp_path, project_file)
        session = Session(tmp_path)
        session.open(project_file)
        assert session.revision is not None and session.revision.number == 1
        assert session.poll() is False


SAYING_PLUGIN = """
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    context.bag.add("plug/say", "{words}")


PLUGIN = Plugin(
    name="plug",
    checks=(CheckInfo("plug/say", Severity.WARNING, "says the words its file holds"),),
    check=check,
)
"""
"""A plugin filing ``plug/say`` in the words its file holds, ``{words}`` filled in: what a revision
says of it tells which bytes of it the analysis ran."""


def a_saying_plugin(base: Path, words: str) -> Path:
    """A project naming ``plug.py`` by its path, which files ``plug/say`` in ``words``; returns the
    plugin's file."""
    write_tree(base, {"p.ddd.json": project("P", plugins=["plug.py"])})
    plugin = base / "plug.py"
    plugin.write_text(SAYING_PLUGIN.format(words=words), encoding="utf-8")
    return plugin


def said(session: Session) -> list[str]:
    """What the newest revision's ``plug/say`` findings say."""
    revision = session.revision
    assert revision is not None
    return [
        filed.diagnostic.message
        for filed in revision.findings
        if filed.diagnostic.check == "plug/say"
    ]


def told_changed(session: Session) -> list[tuple[Path, Severity, str]]:
    """The newest revision's ``plugin-changed`` findings: the file each is filed on, its severity
    and its words."""
    revision = session.revision
    assert revision is not None
    return [
        (filed.file, filed.diagnostic.severity, filed.diagnostic.message)
        for filed in revision.findings
        if filed.diagnostic.check == "plugin-changed"
    ]


def changed_words(name: str) -> str:
    """What ``plugin-changed`` says of the plugin file named ``name``."""
    return (
        f"'{name}' changed since ddd gui imported it: a module is imported once per process, so "
        "ddd gui runs the old code until it is restarted"
    )


class TestAPluginChangedSinceItWasImported:
    """A module is imported once per process (14:I4, decision 14.2): a plugin saved with other
    bytes once the server imported it is noticed by the poll, which stamps its file, and the
    revision that follows runs the module imported first. It carries ``plugin-changed`` on the
    plugin's file, an error by default, saying the server has to be restarted."""

    def test_a_plugin_edited_is_told_changed_on_its_file_as_an_error(self, tmp_path: Path) -> None:
        """``plug.py`` files ``OLD WORDS``, then is saved filing ``NEW WORDS``: the next revision
        still says the old words, its module being the one imported first, and says why, on the
        plugin's own file, which counts the error."""
        plugin = a_saying_plugin(tmp_path, "OLD WORDS")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert (said(session), told_changed(session)) == (["OLD WORDS"], [])
        plugin.write_text(SAYING_PLUGIN.format(words="NEW WORDS"), encoding="utf-8")
        moved(plugin)
        assert session.poll() is True
        assert said(session) == ["OLD WORDS"]
        assert told_changed(session) == [
            (plugin.resolve(), Severity.ERROR, changed_words("plug.py"))
        ]
        revision = session.revision
        assert revision is not None
        assert [
            (file.kind, file.errors) for file in revision.files if file.path.name == "plug.py"
        ] == [("plugin", 1)]

    def test_a_plugin_written_again_with_the_same_bytes_is_told_nothing(
        self, tmp_path: Path
    ) -> None:
        """Its stamp moves, so the poll asks for an analysis, and the module the server holds was
        imported from the very bytes the file holds: no change."""
        plugin = a_saying_plugin(tmp_path, "OLD WORDS")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        plugin.write_bytes(plugin.read_bytes())
        moved(plugin)
        assert session.poll() is True
        assert (said(session), told_changed(session)) == (["OLD WORDS"], [])

    def test_a_plugin_given_back_the_bytes_it_was_imported_from_is_told_nothing_again(
        self, tmp_path: Path
    ) -> None:
        """Saved back as it was imported, its file holds the very bytes the server's module was run
        from: ``plugin-changed`` goes with the next revision, no restart taken. Moved back twice,
        so that its stamp cannot be the one the edit left, whatever the clock's granularity."""
        plugin = a_saying_plugin(tmp_path, "OLD WORDS")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        imported = plugin.read_bytes()
        plugin.write_text(SAYING_PLUGIN.format(words="NEW WORDS"), encoding="utf-8")
        moved(plugin)
        assert session.poll() is True
        assert [severity for _, severity, _ in told_changed(session)] == [Severity.ERROR]
        plugin.write_bytes(imported)
        moved(plugin)
        moved(plugin)
        assert session.poll() is True
        assert (said(session), told_changed(session)) == (["OLD WORDS"], [])

    def test_a_plugin_whose_model_ended_the_read_is_told_changed_once_mended(
        self, tmp_path: Path
    ) -> None:
        """A plugin whose own model raises on the project's block ends the read, and the run covers
        the project description alone. Mended, its file is noticed, and the analysis runs the model
        the server imported, which raises again: ``plugin-changed`` is filed on that file all the
        same, no run having noted it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P", plugins=["modelled.py"], extensions={"modelled": {"level": 1}}
                ),
            },
        )
        plugin = tmp_path / "modelled.py"
        plugin.write_text(MODELLED_PLUGIN, encoding="utf-8")
        session = opened_and_settled(tmp_path / "p.ddd.json")
        assert told_changed(session) == []
        mended = MODELLED_PLUGIN.replace(
            'raise RuntimeError("the model is broken")', "return value"
        )
        assert mended != MODELLED_PLUGIN
        plugin.write_text(mended, encoding="utf-8")
        moved(plugin)
        assert session.poll() is True
        assert checks_of(session)["plugin-invalid"] is Severity.ERROR
        assert told_changed(session) == [
            (plugin.resolve(), Severity.ERROR, changed_words("modelled.py"))
        ]

    def test_each_build_grades_it_as_it_grades_any_other_check(self, tmp_path: Path) -> None:
        """``SEVERITY plugin-changed=warning`` in one build and nothing in the other: each build's
        run files it under that build's severities, and both grades are told, as two builds
        grading any finding apart are."""
        plugin = a_saying_plugin(tmp_path, "OLD WORDS")
        project_file = tmp_path / "p.ddd.json"
        build_record(tmp_path, project_file, image="fw1", severity=["plugin-changed=warning"])
        build_record(tmp_path, project_file, image="fw2")
        session = opened_and_settled(project_file)
        assert session.revision is not None and len(session.revision.builds) == 2
        plugin.write_text(SAYING_PLUGIN.format(words="NEW WORDS"), encoding="utf-8")
        moved(plugin)
        assert session.poll() is True
        told = told_changed(session)
        assert len(told) == 2
        assert set(told) == {
            (plugin.resolve(), Severity.WARNING, changed_words("plug.py")),
            (plugin.resolve(), Severity.ERROR, changed_words("plug.py")),
        }

    def test_a_project_walking_a_directory_named_in_no_utf_8_is_analysed(
        self, tmp_path: Path
    ) -> None:
        """``comps/**/*.ddd.json`` walks ``comps/caf\\xe9``, a directory named in Latin-1 as an old
        archive leaves one, which python spells with a lone surrogate: the revision watches it, as
        it watches every directory such a pattern walks, and asks nothing of it."""
        project_file = a_pattern_of_writers(tmp_path, "comps/**/*.ddd.json", "comps/w.ddd.json")
        unnamed = tmp_path / "comps" / "caf\udce9"
        unnamed.mkdir()
        revision = first_revision(tmp_path, project_file)
        assert revision.number == 1
        assert unnamed.resolve() in revision.watched
        assert {filed.diagnostic.check for filed in revision.findings} == {
            "missing-id",
            "unused-output",
        }

    def test_of_what_a_revision_watches_its_plugin_files_alone_are_asked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A directory a pattern expands in, a build record found, the record beside the project
        description and a plugin file are each watched; only the plugin is asked whether it changed
        since it was imported, which no directory or record could be."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "comps/*.ddd.json", plugins=["named.py"]),
                "comps/w.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
                "named.py": NAMED_PLUGIN,
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        asked: list[Path] = []
        real = module.changed_since_imported

        def recorded(path: Path) -> bool:
            asked.append(path)
            return real(path)

        monkeypatch.setattr(module, "changed_since_imported", recorded)
        revision = first_revision(tmp_path, tmp_path / "p.ddd.json")
        assert len(revision.watched) == 4
        assert asked and set(asked) == {(tmp_path / "named.py").resolve()}


class TestEachPathResolvedOnce:
    def test_a_revision_names_each_of_its_paths_resolved_by_the_loaders_rule(
        self, tmp_path: Path
    ) -> None:
        """Every file it read and every file a finding is filed on, resolved once by the analysis,
        as the loader resolves one: examples/demo's sub-project's files included."""
        shutil.copytree(EXAMPLES / "demo", tmp_path / "demo")
        revision = first_revision(tmp_path / "demo", tmp_path / "demo" / "demo.ddd.json")
        named = {file.path for file in revision.files} | {f.file for f in revision.findings}
        assert revision.resolved_paths == {path: path.resolve() for path in named}
        assert len(named) == 6

    def test_a_path_no_system_reads_is_named_as_it_is(self, tmp_path: Path) -> None:
        """The loader's rule hands such a path back unresolved, where resolving it raised."""
        project_file = unreachable(tmp_path)
        revision = first_revision(tmp_path, project_file)
        nul = project_file.resolve().parent / NUL_ENTRY
        assert revision.resolved_paths[nul] == nul
        assert set(revision.resolved_paths) == {file.path for file in revision.files}


class Held:
    """A stand-in for a function of the session module that, called on the thread named
    ``thread``, says so and waits there until the test lets it go - the first such call alone;
    every other call is the real one's."""

    def __init__(self, real: Callable[..., object], thread: str) -> None:
        self.real = real
        self.thread = thread
        self.inside = threading.Event()
        self.going = threading.Event()
        self.held = False

    def __call__(self, *arguments: object) -> object:
        if threading.current_thread().name == self.thread and not self.held:
            self.held = True
            self.inside.set()
            assert self.going.wait(timeout=10), "the test never let the call go"
        return self.real(*arguments)


def finished[T](call: Callable[[], T]) -> T:
    """What ``call`` answers, called on a thread of its own, failing the test where five seconds
    pass first: what a call waiting for a lock held across a held call would do. Five, so that it
    fails before the held call gives up waiting (:class:`Held`, ten) and lets the lock go."""
    answers: list[T] = []
    thread = threading.Thread(target=lambda: answers.append(call()), name="asking", daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "the call waited for the session's lock"
    (answer,) = answers
    return answer


class TestNothingIsReadHoldingTheLock:
    """The poll stamps the files without the session's lock, an analysis stamps those it is about
    to read without it, and opening reads what a project includes before taking it: while another
    thread computes, every system call waits for that thread's turn, and one of these held across
    a project's thousands of files held every edit, every state and every plan behind it for
    seconds. Each is held here mid-way, on its own thread, while another thread's call is
    answered."""

    def test_a_poll_stamps_the_files_without_holding_the_lock(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """While the poll stamps, the session says what it says and an edit is written and
        analysed. The edit's analysis replaced the stamps the poll was comparing with, so that
        round passes rather than taking the edit's own write for a change: the edit's analysis
        read it, and the next poll compares with the stamps it took."""
        session = opened_and_settled(shared)
        held = Held(module.stamped, "polling")
        monkeypatch.setattr(module, "stamped", held)
        polled: list[bool] = []
        polling = threading.Thread(
            target=lambda: polled.append(session.poll()), name="polling", daemon=True
        )
        polling.start()
        try:
            assert held.inside.wait(timeout=10), "the poll never stamped"
            assert finished(session.snapshot).analysing is False
            at, _ = finished(lambda: session.edit([unit_of_b(shared, "Hz")], "the unit of Speed"))
        finally:
            held.going.set()
            polling.join(timeout=10)
        assert not polling.is_alive()
        assert polled == [False]
        revision = session.revision
        assert revision is not None and (revision.number, revision.edits) == (2, at)
        assert mismatches(session) == 2
        assert session.poll() is False

    def test_an_analysis_stamps_the_files_it_reads_without_holding_the_lock(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """While the analysis an edit asked for stamps the files it is about to read, the session
        says it is analysing and another edit is written. The analysis counts the edits on disk
        when it took its request up, before it stamped: the edit written while it stamped is the
        next analysis's, as one written while it read the files is."""
        session = Stepped(shared.parent)
        opening, first, second = session.goes
        opening.set()
        session.start()
        held = Held(module.stamped, "ddd-gui-analyse")
        try:
            session.open(shared)
            begun(session)
            landed(session)
            monkeypatch.setattr(module, "stamped", held)
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of B's Speed")
            assert held.inside.wait(timeout=10), "the analysis never stamped"
            assert finished(session.snapshot).analysing is True
            later, _ = finished(
                lambda: session.edit([unit_of_a(shared, "Hz")], "the unit of A's Speed")
            )
            held.going.set()
            begun(session)
            first.set()
            begun(session)  # the second edit's analysis, begun once the first edit's landed
            revision = session.revision
            assert revision is not None and (revision.number, revision.edits) == (2, at)
            second.set()
            settled = landed(session).revision
            assert settled is not None and (settled.number, settled.edits) == (3, later)
        finally:
            held.going.set()
            for go in session.goes:
                go.set()
            stopped(session)

    def test_a_poll_while_an_analysis_stamps_asks_for_nothing(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """While an analysis's stamps are being taken there are none to compare with, and the poll
        finds nothing - as it finds nothing once they are taken
        (``test_the_poll_does_not_take_an_edits_own_write_for_a_change_its_analysis_missed``):
        the edit's own write, made before that analysis took its request up, is one it is about
        to read."""
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        held = Held(module.stamped, "ddd-gui-analyse")
        try:
            session.open(shared)
            begun(session)
            landed(session)
            monkeypatch.setattr(module, "stamped", held)
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert held.inside.wait(timeout=10), "the analysis never stamped"
            assert session.poll() is False
            held.going.set()
            begun(session)
            landed(session)
            assert session.analyses == 2
        finally:
            held.going.set()
            session.gate.set()
            stopped(session)

    def test_a_project_opened_while_an_analysis_stamps_keeps_stamps_of_its_own(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The analysis of the project open before is thrown away when it ends, as one the opening
        found reading the files is
        (``test_a_project_opened_while_another_is_analysed_throws_that_analysis_away``), and what
        it stamped is not taken for the new project's stamps: a save of a file the new project
        does not have asks for nothing."""
        write_tree(shared.parent, {"q.ddd.json": project("Q", "a.ddd.json")})
        other = shared.parent / "q.ddd.json"
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        held = Held(module.stamped, "ddd-gui-analyse")
        try:
            session.open(shared)
            begun(session)
            landed(session)
            monkeypatch.setattr(module, "stamped", held)
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert held.inside.wait(timeout=10), "the analysis never stamped"
            session.open(other)
            held.going.set()
            begun(session)  # the edit's analysis, of the project open before, held at the gate
            b = shared.parent / "b.ddd.json"
            b.write_bytes(b.read_bytes() + b" ")
            assert session.poll() is False
            session.gate.set()
            settled = landed(session).revision
            assert settled is not None and settled.project == other.resolve()
        finally:
            held.going.set()
            session.gate.set()
            stopped(session)

    def test_opening_reads_what_a_project_includes_without_holding_the_lock(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Opening reads the description and expands its includes to know which files to stamp
        before the first analysis reads them; meanwhile the session answers for what was open
        before."""
        session = Session(shared.parent)
        session.open(shared)
        before = session.snapshot()
        held = Held(module.named_by, "opening")
        monkeypatch.setattr(module, "named_by", held)
        opening = threading.Thread(target=lambda: session.open(shared), name="opening", daemon=True)
        opening.start()
        try:
            assert held.inside.wait(timeout=10), "opening never read what the project includes"
            assert finished(session.snapshot) == before
        finally:
            held.going.set()
            opening.join(timeout=10)
        assert not opening.is_alive()
        assert session.revision is not None and session.revision.number == 2
        assert session.poll() is False


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

    def test_a_stale_refusal_asks_for_an_analysis_a_change_the_poll_cannot_see_needs(
        self, shared: Path
    ) -> None:
        """A save of the same size with its modification time put back leaves the stamps as
        they were: the poll sees nothing, and the plan keeps the old fingerprint. The refusal
        itself asks for the analysis, whose revision fingerprints the bytes on disk, so that a
        plan asked again applies."""
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        before = b.stat()
        old = unit_of_b(shared, "Hz")
        saved = b.read_bytes().replace(b'"rpm"', b'"rad"')
        assert len(saved) == before.st_size
        b.write_bytes(saved)
        os.utime(b, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert session.poll() is False
        first = session.current().number
        with pytest.raises(EditError) as refused:
            session.edit([old], "the unit of Torque")
        assert refused.value.code == STALE
        assert session.current().number > first
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        assert b'"Hz"' in b.read_bytes()

    def test_an_analysis_failing_after_a_stale_refusal_does_not_replace_it(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The change that made the edit stale may leave the project unanalysable: the caller
        still gets the ``stale`` refusal, the failure is printed as the analyser prints its own,
        and the next poll asks again."""

        class Failing(Session):
            analyses = 0

            def _analysed(self, project: Path) -> Revision:
                self.analyses += 1
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return super()._analysed(project)

        session = Failing(shared.parent)
        session.open(shared)
        old = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        first = session.revision
        with pytest.raises(EditError) as refused:
            session.edit([old], "the unit of Torque")
        assert refused.value.code == STALE
        assert refused.value.__cause__ is None
        assert "ddd gui: analysing the project failed: boom" in capsys.readouterr().err
        assert session.revision is first
        assert session.poll() is True

    def test_a_wordless_failure_after_a_stale_refusal_is_printed_as_the_state_says_it(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal's line says the reason in the words the session says it: an exception
        raised with nothing to say by its class's name, never an empty reason (14:M7)."""

        class Failing(Session):
            analyses = 0

            def _analysed(self, project: Path) -> Revision:
                self.analyses += 1
                if self.analyses == 2:
                    raise RuntimeError()
                return super()._analysed(project)

        session = Failing(shared.parent)
        session.open(shared)
        old = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        with pytest.raises(EditError):
            session.edit([old], "the unit of Torque")
        assert capsys.readouterr().err.splitlines()[-1] == (
            "ddd gui: analysing the project failed: RuntimeError"
        )
        assert session.snapshot().failed == "RuntimeError"

    def test_a_failure_after_a_stale_refusal_that_cannot_be_printed_leaves_the_refusal(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Where standard error cannot be written - closed, or a pipe nobody reads any more - the
        line is lost, as the analyser loses its own, and the caller still gets the ``stale``
        refusal: what the page acts on, never the failing print in its place."""

        class Failing(Session):
            analyses = 0

            def _analysed(self, project: Path) -> Revision:
                self.analyses += 1
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return super()._analysed(project)

        class Unwritable(io.StringIO):
            def write(self, text: str) -> int:
                raise OSError("standard error is closed")

        session = Failing(shared.parent)
        session.open(shared)
        old = unit_of_b(shared, "Hz")
        (shared.parent / "b.ddd.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(sys, "stderr", Unwritable())
        with pytest.raises(EditError) as refused:
            session.edit([old], "the unit of Torque")
        assert refused.value.code == STALE
        assert session.analyses == 2

    def test_a_refusal_that_is_not_stale_asks_for_no_analysis(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        change = unit_of_b(shared, "Hz")
        b.chmod(0o444)
        first = session.current()
        try:
            with pytest.raises(EditError) as refused:
                session.edit([change], "the unit of Torque")
        finally:
            b.chmod(0o644)
        assert refused.value.code == UNWRITABLE
        assert session.current() is first

    def test_an_undo_of_an_edit_no_longer_on_top_is_refused_asking_no_analysis(
        self, shared: Path
    ) -> None:
        """A second window's undo of an edit this one has undone or covered since: the stack
        moved, and no file did, so the refusal is ``stale`` and asks for nothing - not the
        analysis a write refused ``stale`` asks for, which would read the disk as the session
        already knows it. Neither does an undo with nothing left to undo."""
        session = Session(shared.parent)
        session.open(shared)
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        for asked in (at + 5, at - 1, None):
            if asked is None:
                session.undo(at)
                asked = at
            revision, said = session.current(), session.snapshot().version
            with pytest.raises(EditError) as refused:
                session.undo(asked)
            assert refused.value.code == STALE
            assert session.current() is revision
            assert session.snapshot().version == said

    def test_an_undo_whose_put_back_is_refused_stale_asks_for_an_analysis(
        self, shared: Path
    ) -> None:
        """The undo of the edit on top, refused because its file was saved since, is a write
        refused ``stale``: it asks for the analysis that reads what is on disk, as an edit's
        refusal does, whether or not the poll could see the save - and takes that edit off the
        stack (:class:`TestUndoing`)."""
        session = Session(shared.parent)
        session.open(shared)
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        b = shared.parent / "b.ddd.json"
        b.write_bytes(b.read_bytes().replace(b'"Hz"', b'"rad"'))
        first = session.current().number
        with pytest.raises(EditError) as refused:
            session.undo(at)
        assert refused.value.code == STALE
        assert session.current().number > first
        assert session.undoable is None

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

    def test_a_created_path_the_system_will_not_resolve_is_confined_as_given(
        self, shared: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Resolved as the loader resolves a path (``ddd.loading.resolve_path``), which hands back
        one the system will not look at rather than raise: Windows may answer a lookup with an
        error ``Path.resolve`` does not walk past, and resolved directly it failed the edit,
        ``500``. Its name was judged before, so nothing is left to the answer."""
        session = Session(shared.parent)
        session.open(shared)
        revision = session.revision
        assert revision is not None
        created, described = adoption(shared)
        resolve = Path.resolve

        def refusing(path: Path, strict: bool = False) -> Path:
            if path.name == "units.ddd.json":
                raise OSError("the system will not look this name up")
            return resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", refusing)
        assert module._confined(revision, created, [created, described]) == FileChange(
            created.path, None, created.operations, like=revision.project
        )


def collected_sources(root: Path) -> list[Path]:
    """The two components of the source tree a build collects into
    :func:`conftest.collected_project`'s project, a producer and a consumer of one variable, each
    registered by the CMakeLists.txt beside it, as the module's own example lays one out."""
    write_tree(
        root / "src",
        {
            "pump/pump.ddd.json": component("Pump", declare("output", "Pressure", unit="bar")),
            "pump/CMakeLists.txt": "ddd_add_component(pump JSON pump.ddd.json)\n",
            "valve/valve.ddd.json": component("Valve", declare("input", "Pressure", unit="bar")),
            "valve/CMakeLists.txt": "ddd_add_component(valve JSON valve.ddd.json)\n",
        },
    )
    return [root / "src" / "pump" / "pump.ddd.json", root / "src" / "valve" / "valve.ddd.json"]


def an_include_taken_out(described: Path) -> FileChange:
    """The last entry of a project description's includes taken out."""
    data = described.read_bytes()
    listed = json.loads(data)["project"]["includes"]
    return FileChange(
        described, fingerprint(data), (Operation("remove", f"project.includes[{len(listed) - 1}]"),)
    )


def refusal_of(session: Session, changes: Sequence[FileChange]) -> tuple[str, str]:
    """The code and the sentence ``session`` refuses the edit ``changes`` with."""
    with pytest.raises(EditError) as refused:
        session.edit(changes, "a change")
    return refused.value.code, str(refused.value)


def unread_beside(root: Path) -> str:
    """What a change writing under the build tree of :func:`conftest.collected_project`'s project
    is refused with while the record beside its description does not read as one: the record
    named, and the tree nothing is written under."""
    record = (root / "b" / "ddd" / "fw" / "ddd-build.json").resolve().as_posix()
    return (
        f"Fw.ddd.json may be generated by a build: the build record beside it, {record}, does not "
        f"read as one, so nothing under {(root / 'b').resolve().as_posix()} is written from here "
        "until it does"
    )


def a_unit_set(path: Path, unit: str) -> FileChange:
    """The unit of the first declaration of the component ``path`` set to ``unit``."""
    pointer = "component.interface[0].definition.unit"
    return FileChange(
        path, fingerprint(path.read_bytes()), (Operation("set", pointer, f'"{unit}"'),)
    )


class TestAProjectTheBuildGenerates:
    """A project ``ddd_generate`` collected out of an image's link closure, its build record
    beside it naming it (:func:`conftest.collected_project`): the build writes it again at every
    configure, out of what ``ddd_add_component`` registers. Its revision says which build that is
    and the tree it builds in, and the session writes nothing under that tree - a change of the
    description is undone by that configure, a file created beside it falls out of the project,
    and whatever else the tree holds goes with it - while the components the build collects from
    the source tree are written as in any other project."""

    def test_its_revision_names_its_image_and_build_tree(self, tmp_path: Path) -> None:
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        generated = first_revision(tmp_path, described).generated
        assert generated is not None
        assert (generated.image, generated.tree) == ("fw", (tmp_path / "b").resolve())

    def test_a_project_a_record_elsewhere_names_is_one_somebody_wrote(self, shared: Path) -> None:
        """``ddd_generate(... PROJECT p.ddd.json)``: its record lies in the build tree and names a
        description of the source tree, which is the project's own to edit."""
        build_record(shared.parent, shared, image="fw")
        revision = first_revision(shared.parent, shared)
        assert revision.builds != ()
        assert revision.generated is None

    def test_a_record_beside_it_naming_another_description_does_not_make_it_the_builds(
        self, tmp_path: Path
    ) -> None:
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        other = BuildInfo(project=(described.parent / "Other.ddd.json").as_posix(), image="fw")
        (described.parent / "ddd-build.json").write_text(build_info_text(other), encoding="utf-8")
        assert first_revision(tmp_path, described).generated is None

    @pytest.mark.parametrize(
        "record", ['{"format": 1, "image": "fw"}', '{"format": 1, "project": 7, "image": "fw"}']
    )
    def test_a_record_beside_it_naming_no_description_does_not_either(
        self, tmp_path: Path, record: str
    ) -> None:
        """One naming no project, and one naming it by no path."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        (described.parent / "ddd-build.json").write_text(record, encoding="utf-8")
        assert first_revision(tmp_path, described).generated is None

    @pytest.mark.parametrize("record", ['{"format": 1, "project": "', "", "[]"])
    def test_a_record_beside_it_that_does_not_read_is_refused_as_the_builds_naming_it(
        self, tmp_path: Path, record: str
    ) -> None:
        """A record cut short - a write of it that died - an empty one, and one that is no object:
        whether the build writes the description beside it cannot be told, so it is refused as
        though the build did, the sentence naming the record, and nothing is written."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        beside = described.parent / "ddd-build.json"
        beside.write_text(record, encoding="utf-8")
        session = Session(tmp_path)
        session.open(described)
        before = described.read_bytes()
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", unread_beside(tmp_path))
        assert described.read_bytes() == before

    def test_a_record_beside_it_mended_is_read_again(self, tmp_path: Path) -> None:
        """Watched whether or not the search for build records finds it - ``b`` is no name a
        build directory is looked for under - so its repair makes a new revision, which reads the
        build it names."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        beside = described.parent / "ddd-build.json"
        whole = beside.read_text(encoding="utf-8")
        beside.write_text(whole[: len(whole) // 2], encoding="utf-8")
        session = Session(tmp_path)
        session.open(described)
        assert session.poll() is False
        assert refusal_of(session, [an_include_taken_out(described)])[1] == unread_beside(tmp_path)
        beside.write_text(whole, encoding="utf-8")
        assert session.poll() is True
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))

    @pytest.mark.parametrize(
        "unusable",
        [{"format": 99, "kept": "by a newer DDD"}, {"severity": ["no-such-check=error"]}],
    )
    def test_a_record_this_version_does_not_apply_still_makes_it_the_builds(
        self, tmp_path: Path, unusable: dict[str, object]
    ) -> None:
        """A record a newer DDD wrote - a format past this one's, a key this one does not know -
        and one naming a check this one has not got: neither is applied, its severities being
        unknown here, and the description beside each is written again at every configure all
        the same."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        written = {**json.loads(record.read_text(encoding="utf-8")), **unusable}
        record.write_text(json.dumps(written), encoding="utf-8")
        session = Session(tmp_path, [tmp_path / "b"])
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert revision.builds == ()
        before = described.read_bytes()
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))
        assert described.read_bytes() == before

    def test_a_project_given_to_the_build_beside_its_record_is_written(
        self, tmp_path: Path
    ) -> None:
        """``ddd_generate(... PROJECT p.ddd.json OUTPUT_DIRECTORY <its own directory>)``, the
        defect's own layout: a project somebody wrote in the source tree, and beside it the
        record the build writes into that directory, naming it and saying it was given. It is
        the project's own to edit, and an edit of it is answered as written."""
        sources = collected_sources(tmp_path)
        described = tmp_path / "src" / "project" / "Hand.ddd.json"
        write_tree(
            described.parent,
            {
                "Hand.ddd.json": {
                    "project": {
                        "name": "Hand",
                        "includes": ["../pump/pump.ddd.json", "../valve/valve.ddd.json"],
                    }
                }
            },
        )
        given = BuildInfo(project=described.as_posix(), image="fw", origin="given")
        record = described.parent / "ddd-build.json"
        record.write_text(build_info_text(given), encoding="utf-8")
        assert json.loads(record.read_text(encoding="utf-8"))["origin"] == "given"
        session = Session(tmp_path)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert revision.generated is None
        _, written = session.edit([an_include_taken_out(described)], "an include taken out")
        assert [file.path for file in written] == [described.resolve()]
        assert sources[1].is_file()

    def test_a_given_project_under_a_build_tree_is_written_too(self, tmp_path: Path) -> None:
        """The same record laid where ``collected_project`` lays one, a cache above it."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        given = BuildInfo(project=described.as_posix(), image="fw", origin="given")
        record.write_text(build_info_text(given), encoding="utf-8")
        session = Session(tmp_path)
        session.open(described)
        _, written = session.edit([an_include_taken_out(described)], "an include taken out")
        assert [file.path for file in written] == [described.resolve()]

    def test_a_record_of_a_collected_description_is_the_builds(self, tmp_path: Path) -> None:
        """What ``ddd_generate`` without ``PROJECT`` writes, with no key of the origin: refused,
        with the sentence that says the build writes the description at every configure."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = json.loads((described.parent / "ddd-build.json").read_text(encoding="utf-8"))
        assert "origin" not in record
        session = Session(tmp_path)
        session.open(described)
        before = described.read_bytes()
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))
        assert described.read_bytes() == before

    def test_a_record_saying_collected_is_the_builds_too(self, tmp_path: Path) -> None:
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        written = {**json.loads(record.read_text(encoding="utf-8")), "origin": "collected"}
        record.write_text(json.dumps(written), encoding="utf-8")
        session = Session(tmp_path)
        session.open(described)
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))

    def test_a_given_project_with_a_record_of_an_older_module_beside_it_is_still_refused(
        self, tmp_path: Path
    ) -> None:
        """A record written before the key says nothing of how the build has the description,
        and is read as it was until the build is configured again and writes it with the key."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        written = json.loads(record.read_text(encoding="utf-8"))
        assert written["format"] == 1 and "origin" not in written
        session = Session(tmp_path)
        session.open(described)
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))

    @pytest.mark.parametrize("word", ["guessed", "", 7, None])
    def test_a_record_saying_anything_but_given_is_the_builds(
        self, tmp_path: Path, word: object
    ) -> None:
        """Edited only where the record says given; a word this version does not know, or
        none, is no reason to let an edit through the next configure undoes."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        written = {**json.loads(record.read_text(encoding="utf-8")), "origin": word}
        record.write_text(json.dumps(written), encoding="utf-8")
        generated = first_revision(tmp_path, described).generated
        assert generated is not None

    @pytest.mark.parametrize("image", ["", 7])
    def test_a_record_naming_no_image_is_said_to_be_the_builds(
        self, tmp_path: Path, image: str | int
    ) -> None:
        """``ddd build-info`` without ``--image`` writes ``"image": ""``; a record naming its
        image by no string - by a number - names none either."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        record = described.parent / "ddd-build.json"
        written = {**json.loads(record.read_text(encoding="utf-8")), "image": image}
        record.write_text(json.dumps(written), encoding="utf-8")
        session = Session(tmp_path)
        session.open(described)
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path, build="the build"))

    def test_an_edit_of_its_description_is_refused_and_writes_nothing(self, tmp_path: Path) -> None:
        """Taking a component out of its includes, which the next configure would put back."""
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        session = Session(tmp_path)
        session.open(described)
        before = described.read_bytes()
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path))
        assert described.read_bytes() == before
        assert (session.edits, session.undoable) == (0, None)

    def test_a_file_created_beside_it_is_refused_and_offered_beside_a_source_file(
        self, tmp_path: Path
    ) -> None:
        """A vocabulary adopted beside the description: offered instead beside the first
        description the build collects from the source tree, with the line registering it."""
        sources = collected_sources(tmp_path)
        described = collected_project(tmp_path, *sources)
        session = Session(tmp_path)
        session.open(described)
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))
        assert not (described.parent / "units.ddd.json").exists()

    def test_a_file_created_beside_it_alone_is_refused_as_the_builds(self, tmp_path: Path) -> None:
        """Created by an edit that leaves the includes alone, which a project somebody wrote
        refuses as made only by an edit including it there: here an include there would be
        refused too, so the refusal is the build's, and nothing is created."""
        sources = collected_sources(tmp_path)
        described = collected_project(tmp_path, *sources)
        session = Session(tmp_path)
        session.open(described)
        created, _ = adoption(described)
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, [created])
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))
        assert not (described.parent / "units.ddd.json").exists()

    def test_a_component_of_the_source_tree_is_written(self, tmp_path: Path) -> None:
        sources = collected_sources(tmp_path)
        described = collected_project(tmp_path, *sources)
        session = Session(tmp_path)
        session.open(described)
        pump = sources[0]
        _, written = session.edit([a_unit_set(pump, "kPa")], "the unit of Pressure")
        assert [file.path for file in written] == [pump.resolve()]
        assert '"unit": "kPa"' in pump.read_text(encoding="utf-8")

    def test_a_file_listed_beside_it_is_refused_naming_it(self, tmp_path: Path) -> None:
        """A description somebody put beside it and listed there by hand, an entry the next
        configure takes back out: the file is named, since the reader asked to change it."""
        sources = collected_sources(tmp_path)
        write_tree(tmp_path / "b" / "ddd" / "fw", {"units.ddd.json": {"units": ["bar"]}})
        units = tmp_path / "b" / "ddd" / "fw" / "units.ddd.json"
        described = collected_project(tmp_path, *sources, units)
        session = Session(tmp_path)
        session.open(described)
        renamed = FileChange(
            units, fingerprint(units.read_bytes()), (Operation("set", "units[0]", '"kPa"'),)
        )
        refused = refusal_of(session, [renamed])
        assert refused == ("generated", lying_under(tmp_path, "units.ddd.json"))

    def test_a_description_generated_elsewhere_in_its_build_tree_is_refused_naming_it(
        self, tmp_path: Path
    ) -> None:
        """A description a custom command writes into a directory of the build tree of its own,
        registered with ``ddd_add_component`` as the module allows: under the tree, where the
        build writes it again, so an edit of it is refused, naming it, and nothing is written."""
        sources = collected_sources(tmp_path)
        write_tree(
            tmp_path / "b" / "gen",
            {"gauge.ddd.json": component("Gauge", declare("input", "Pressure", unit="bar"))},
        )
        gauge = tmp_path / "b" / "gen" / "gauge.ddd.json"
        described = collected_project(tmp_path, *sources, gauge)
        session = Session(tmp_path)
        session.open(described)
        before = gauge.read_bytes()
        refused = refusal_of(session, [a_unit_set(gauge, "kPa")])
        assert refused == ("generated", lying_under(tmp_path, "gauge.ddd.json"))
        assert gauge.read_bytes() == before

    @pytest.mark.parametrize("source", ["", "project"])
    def test_a_build_tree_holding_its_source_tree_is_the_builds_in_its_output_directory_alone(
        self, tmp_path: Path, source: str
    ) -> None:
        """An in-source build, the cache in the source tree's own top directory, and a source tree
        configured inside its build tree: refusing the whole tree would refuse every component, so
        the build's is the directory it generates the description into, and the components are
        written."""
        sources = collected_sources(tmp_path / source)
        described = collected_project(tmp_path, *sources, build=".", source=tmp_path / source)
        session = Session(tmp_path)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert revision.generated is not None
        assert revision.generated.tree == described.parent.resolve()
        refused = refusal_of(session, [an_include_taken_out(described)])
        assert refused == ("generated", membership(tmp_path, tree="ddd/fw"))
        _, written = session.edit([a_unit_set(sources[0], "kPa")], "the unit of Pressure")
        assert [file.path for file in written] == [sources[0].resolve()]

    def test_with_no_cmake_cache_above_it_its_output_directory_is_the_builds(
        self, tmp_path: Path
    ) -> None:
        """A record no CMake build tree holds: ``ddd build-info`` run by another build system, or
        an output directory outside the build tree."""
        described = collected_project(tmp_path, *collected_sources(tmp_path), cache=False)
        generated = first_revision(tmp_path, described).generated
        assert generated is not None
        assert generated.tree == described.parent.resolve()

    def test_a_cache_naming_no_source_tree_leaves_its_output_directory_the_builds(
        self, tmp_path: Path
    ) -> None:
        """A ``CMakeCache.txt`` without ``CMAKE_HOME_DIRECTORY`` cannot say that the source tree
        is not under it."""
        described = collected_project(tmp_path, *collected_sources(tmp_path), cache=False)
        cache = tmp_path / "b" / "CMakeCache.txt"
        cache.write_text("# This is the CMakeCache file.\n", encoding="utf-8")
        generated = first_revision(tmp_path, described).generated
        assert generated is not None
        assert generated.tree == described.parent.resolve()

    def test_an_empty_source_tree_in_the_cache_names_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``CMAKE_HOME_DIRECTORY`` spelling nothing says nothing, as no entry does: read as a
        path, it was the directory ``ddd gui`` was started in, which decided how much of the
        build tree was refused."""
        described = collected_project(tmp_path, *collected_sources(tmp_path), cache=False)
        cache = tmp_path / "b" / "CMakeCache.txt"
        cache.write_text(
            "# This is the CMakeCache file.\nCMAKE_HOME_DIRECTORY:INTERNAL=\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        generated = first_revision(tmp_path, described).generated
        assert generated is not None
        assert generated.tree == described.parent.resolve()

    def test_a_cache_that_cannot_be_read_leaves_its_output_directory_the_builds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        described = collected_project(tmp_path, *collected_sources(tmp_path))
        read_text = Path.read_text

        def refusing(path: Path, *arguments: Any, **keywords: Any) -> str:
            if path.name == "CMakeCache.txt":
                raise PermissionError(f"{path} cannot be read")
            return read_text(path, *arguments, **keywords)

        monkeypatch.setattr(Path, "read_text", refusing)
        generated = first_revision(tmp_path, described).generated
        assert generated is not None
        assert generated.tree == described.parent.resolve()

    def test_with_no_description_outside_its_build_tree_a_new_file_goes_in_the_source_tree(
        self, tmp_path: Path
    ) -> None:
        """An image linking no registered component is collected into a description with no
        includes, so there is no description of the source tree to put a new file beside."""
        described = collected_project(tmp_path)
        session = Session(tmp_path)
        session.open(described)
        assert refusal_of(session, adoption(described)) == (
            "generated",
            f"{membership(tmp_path)}; create units.ddd.json in the source tree instead, and add "
            "ddd_add_component(<target> JSON units.ddd.json) to the CMakeLists.txt beside it, "
            "replacing <target> with your component's target",
        )

    def test_a_component_beside_it_is_not_where_a_new_file_is_offered(self, tmp_path: Path) -> None:
        """A component created beside the description and listed there by hand, ``newcomp``,
        until the next configure drops its entry: the first description of the project after the
        project's own, and passed over for the first one the build collects from the source
        tree."""
        sources = collected_sources(tmp_path)
        write_tree(tmp_path / "b" / "ddd" / "fw", {"newcomp.ddd.json": component("NewComp")})
        newcomp = tmp_path / "b" / "ddd" / "fw" / "newcomp.ddd.json"
        described = collected_project(tmp_path, *sources, newcomp)
        session = Session(tmp_path)
        session.open(described)
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))

    def test_a_description_of_its_build_tree_is_not_where_a_new_file_is_offered(
        self, tmp_path: Path
    ) -> None:
        """A dependency fetched into the build tree, ``FetchContent`` style, its own CMakeLists.txt
        beside its description, which sorts ahead of every other file: under the tree, where the
        new file would go with the tree. Passed over for the first description of the source
        tree."""
        sources = collected_sources(tmp_path)
        fetched = tmp_path / "b" / "_deps" / "lib-src"
        write_tree(
            fetched,
            {
                "lib.ddd.json": component("Lib"),
                "CMakeLists.txt": "ddd_add_component(lib JSON lib.ddd.json)\n",
            },
        )
        described = collected_project(tmp_path, fetched / "lib.ddd.json", *sources)
        session = Session(tmp_path)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert revision.files[0].path.name == "lib.ddd.json"
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))

    def test_a_description_outside_what_is_served_is_not_where_a_new_file_is_offered(
        self, tmp_path: Path
    ) -> None:
        """A checkout beside this one, added to the build with its own CMakeLists.txt, outside the
        directory ``ddd gui`` was started in, and sorting ahead of the source tree's: no place to
        send a reader the page does not reach. Passed over for the first description it
        serves."""
        work = tmp_path / "work"
        sources = collected_sources(work)
        write_tree(
            tmp_path / "vendor",
            {
                "vendor.ddd.json": component("Vendor"),
                "CMakeLists.txt": "ddd_add_component(vendor JSON vendor.ddd.json)\n",
            },
        )
        described = collected_project(work, tmp_path / "vendor" / "vendor.ddd.json", *sources)
        session = Session(work)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert revision.files[0].path.name == "vendor.ddd.json"
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(work, "units.ddd.json", pump))

    def test_a_description_no_cmakelists_lies_beside_is_not_where_a_new_file_is_offered(
        self, tmp_path: Path
    ) -> None:
        """A description generated into a ``build`` directory beside the source tree, which no
        CMake cache marks as a build tree, and sorting ahead of it: no CMakeLists.txt beside it
        for the line to go into. Passed over for the first description that has one."""
        sources = collected_sources(tmp_path)
        write_tree(tmp_path / "build" / "gen", {"gen.ddd.json": component("Gen")})
        gen = tmp_path / "build" / "gen" / "gen.ddd.json"
        described = collected_project(tmp_path, gen, *sources)
        session = Session(tmp_path)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert [file.path.name for file in revision.files][:2] == ["Fw.ddd.json", "gen.ddd.json"]
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))

    def test_a_plugin_is_not_where_a_new_file_is_offered(self, tmp_path: Path) -> None:
        """``ddd_generate(fw ... PLUGINS plugins/demo_plugin.py)``: the plugin is a file of the
        project sorting ahead of its descriptions, a CMakeLists.txt beside it, and no description:
        ``PLUGINS`` names it, no ``ddd_add_component`` call. Passed over for the first description
        the build collects from the source tree."""
        sources = collected_sources(tmp_path)
        write_tree(
            tmp_path / "plugins",
            {"demo_plugin.py": REGISTERING_PLUGIN, "CMakeLists.txt": "# the plugins' own\n"},
        )
        plugin = tmp_path / "plugins" / "demo_plugin.py"
        described = collected_project(tmp_path, *sources, plugins=[plugin])
        session = Session(tmp_path)
        session.open(described)
        revision = session.revision
        assert revision is not None
        assert [file.path.name for file in revision.files][:3] == [
            "Fw.ddd.json",
            "demo_plugin.py",
            "pump.ddd.json",
        ]
        pump = sources[0].resolve().as_posix()
        refused = refusal_of(session, adoption(described))
        assert refused == ("generated", offered_beside(tmp_path, "units.ddd.json", pump))


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

    def test_an_undo_refused_because_its_file_changed_on_disk_takes_its_edit_off_the_stack(
        self, shared: Path
    ) -> None:
        """A file the edit wrote, saved from outside since: the disk has moved past that edit,
        which can never be put back as the file stands, so its undo is refused ``stale``, the
        save is left as it was, and the edit is taken off the stack."""
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        b.write_text('{"component": {"name": "B"}}', encoding="utf-8")
        said = session.snapshot().version
        with pytest.raises(EditError) as refused:
            session.undo(1)
        assert refused.value.code == STALE
        assert session.undoable is None
        assert session.snapshot().version > said
        assert b.read_text(encoding="utf-8") == '{"component": {"name": "B"}}'

    def test_an_undo_refused_because_its_file_changed_on_disk_brings_the_edit_beneath_in_reach(
        self, shared: Path
    ) -> None:
        """Two edits, then a save from outside of the file the second wrote: the second's undo is
        refused ``stale`` and that edit taken off the stack, and the first, which wrote another
        file, is the one to undo - put back as an undo of it always was."""
        session = Session(shared.parent)
        session.open(shared)
        a = shared.parent / "a.ddd.json"
        b = shared.parent / "b.ddd.json"
        before = a.read_bytes()
        first, _ = session.edit([unit_of(a, "Hz")], "the unit of Speed")
        second, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        b.write_bytes(b.read_bytes().replace(b'"Hz"', b'"rad"'))
        with pytest.raises(EditError) as refused:
            session.undo(second)
        assert refused.value.code == STALE
        top = session.undoable
        assert top is not None and (top.at, top.label) == (first, "the unit of Speed")
        session.undo(first)
        assert a.read_bytes() == before
        assert b'"rad"' in b.read_bytes()
        assert session.undoable is None

    def test_an_undo_refused_unwritable_keeps_its_edit_on_the_stack(self, shared: Path) -> None:
        """A file the undo cannot write - kept read-only - is refused before anything is put
        back, and the edit stays where it was: the reader may make the file writable and ask
        again, and the undo then puts it back."""
        session = Session(shared.parent)
        session.open(shared)
        b = shared.parent / "b.ddd.json"
        before = b.read_bytes()
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        written = b.read_bytes()
        b.chmod(0o444)
        try:
            with pytest.raises(EditError) as refused:
                session.undo(at)
        finally:
            b.chmod(0o644)
        assert refused.value.code == UNWRITABLE
        top = session.undoable
        assert top is not None and top.at == at
        assert b.read_bytes() == written
        session.undo(at)
        assert b.read_bytes() == before

    def test_an_undo_left_half_written_forward_is_taken_off_once_asked_again(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An undo that put one file back, then could neither put back the next nor write the
        first forward again, is refused ``unwritable``, and its edit stays on the stack to be
        asked again. Asked again, that first file is not as the edit left it, so the undo is
        refused ``stale`` and the edit taken off: the one beneath it comes within reach."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        a, b, c = (tmp_path.resolve() / f"{name}.ddd.json" for name in "abc")
        before = c.read_bytes()
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        first, _ = session.edit([unit_of(c, "Hz")], "the unit of Speed in C")
        second, _ = session.edit([unit_of(a, "Hz"), unit_of(b, "Hz")], "the unit of Speed")
        # a is put back, b refuses, and a's write forward again refuses as well.
        monkeypatch.setattr(Path, "replace", refusing_renames({b: 1, a: 2}))
        with pytest.raises(EditError) as half:
            session.undo(second)
        assert half.value.code == UNWRITABLE
        assert str(half.value).endswith(f"these could not be written forward again: {a}")
        top = session.undoable
        assert top is not None and top.at == second
        monkeypatch.undo()
        with pytest.raises(EditError) as refused:
            session.undo(second)
        assert refused.value.code == STALE
        top = session.undoable
        assert top is not None and top.at == first
        session.undo(first)
        assert c.read_bytes() == before

    def test_a_preview_refused_stale_takes_its_edit_off_where_it_is_still_on_top(
        self, shared: Path
    ) -> None:
        """What ``GET /api/undo`` tells the session of a preview it refused: ``stale``, a file the
        edit would put back changed on disk since, takes that edit off the stack as its own undo
        would, where it is still the one on top, and the version moves with the stack; any other
        refusal, or one of an edit no longer on top, leaves the stack as it is. None asks for an
        analysis: a preview writes nothing, and runs no plugin."""
        session = Session(shared.parent)
        session.open(shared)
        first, _ = session.edit([unit_of(shared.parent / "a.ddd.json", "Hz")], "the unit of Speed")
        second, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Torque")
        stale = EditError(STALE, "b.ddd.json changed on disk since it was written")
        revision, said = session.current().number, session.snapshot().version
        session.preview_refused(first, stale)
        session.preview_refused(second, EditError(UNWRITABLE, "disk full"))
        top = session.undoable
        assert top is not None and top.at == second
        assert session.snapshot().version == said
        session.preview_refused(second, stale)
        top = session.undoable
        assert top is not None and top.at == first
        assert session.snapshot().version > said
        assert session.current().number == revision
        assert not session.snapshot().analysing

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
