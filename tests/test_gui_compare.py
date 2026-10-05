"""Tests for ``ddd.gui.compare``: whether the open project can stand in for a baseline.

Every revision these tests need is built through ``opened``/``unloaded`` of ``test_gui_api.py`` -
the one place this suite already knows how to put a small project on disk and open a
``Session`` over it - reached as ``api.session.revision``, exactly as that module's own tests
reach it. A second way to build one here would be the duplication this series keeps paying for.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import (
    EXAMPLES,
    build_record,
    component,
    declare,
    first_revision,
    project,
    write_tree,
)
from ddd.cli import EXIT_OK, main
from ddd.deliveries import Refusal
from ddd.diagnostics import Severity
from ddd.gui.api import _finding
from ddd.gui.compare import (
    _REASONS,
    MAX_BASELINES,
    BaselineCache,
    BaselineRefusedError,
    compared,
)
from ddd.gui.session import Revision, Session
from test_gui_api import opened, unloaded

RAISING_PLUGIN = """
from ddd.plugins import CompareContext, Plugin


def compare(context: CompareContext) -> None:
    raise RuntimeError("the compare hook of this plugin is broken")


PLUGIN = Plugin(name="demo", compare=compare)
"""
"""A plugin whose comparison hook raises, to prove the route answers a finding rather than an
exception - the promise ``ddd.lsp.diagnostics._run`` already makes for a check hook."""

RAISING_CHECK_PLUGIN = """
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    raise RuntimeError("this hook is broken")


PLUGIN = Plugin(name="old", check=check)
"""
"""A plugin whose *check* hook raises, for a baseline description that names it: the defect is
met while the baseline is being read, before any comparison is run."""


def _revision(root: Path, files: dict[str, object]) -> Revision:
    """A revision over a small project written under ``root``, through ``opened`` - the one way
    this test suite builds a session, not a second one invented for this module."""
    api = opened(root, files)
    assert api.session.revision is not None
    return api.session.revision


def _dumped(source: Path, target: Path) -> None:
    """``target`` as ``ddd dump`` would write it for the project description at ``source``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    assert main(["dump", str(source), "-o", str(target)]) == EXIT_OK


def _layout(tmp_path: Path) -> Path:
    """``examples/layout`` and the plugin it names, copied under ``tmp_path`` so that a test may
    edit them; returns the project description, with ``tmp_path`` as the session root.

    The repository's own proof that a plugin's comparison rules exist: ``ddd_layout.py``
    registers five of them, three at ``Severity.ERROR``. Used rather than a plugin written here
    because a rule nobody ships is a rule this module could have got wrong in the same way twice.
    """
    shutil.copytree(EXAMPLES / "layout", tmp_path / "layout")
    shutil.copytree(EXAMPLES / "plugins", tmp_path / "plugins")
    return tmp_path / "layout" / "project.ddd.json"


def _moved_key(tmp_path: Path) -> None:
    """Move ``EngineHours`` from layout key 12 to 112, which ``layout/key-changed`` is about:
    every dataset keyed on 12 now reads an entry the delivery has orphaned."""
    storage = tmp_path / "layout" / "storage.ddd.json"
    storage.write_text(
        storage.read_text(encoding="utf-8").replace('"key": 12,', '"key": 112,'), encoding="utf-8"
    )


def _unstamped(tmp_path: Path) -> None:
    """Take the plugin out of the candidate, blocks and all: a delivery that no longer stamps
    what the baseline was stamped with, which is what ``missing-plugin`` exists to say."""
    for path in (tmp_path / "layout").glob("*.ddd.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        for block in (document.get("project", {}), *_definitions(document)):
            block.pop("plugins", None)
            block.pop("extensions", None)
        path.write_text(json.dumps(document), encoding="utf-8")


def _definitions(document: dict[str, object]) -> list[dict[str, object]]:
    component = document.get("component")
    entries = component.get("interface", []) if isinstance(component, dict) else []
    return [entry["definition"] for entry in entries]


class TestThePathRule:
    def test_a_baseline_outside_the_root_is_refused(self, tmp_path: Path) -> None:
        # The page has never read a file that is not a file of the open project. A path that
        # climbs out of the session's root is refused with its reason, not clamped to something
        # inside it - a silent clamp would compare against a delivery nobody named.
        root = tmp_path / "project"
        root.mkdir()
        outside = tmp_path / "elsewhere.json"
        outside.write_text("{}")
        revision = _revision(root, {"p.ddd.json": project("P")})
        with pytest.raises(BaselineRefusedError) as refused:
            compared(revision, outside, root, {})
        # The reason travels, not merely the refusal: a reader who is told "no" and not "why"
        # cannot act on it, and the path they typed is the thing they have to correct.
        assert outside.as_posix() in str(refused.value)
        assert "outside" in str(refused.value)

    def test_a_baseline_inside_the_root_is_read(self, tmp_path: Path) -> None:
        """The mirror of the refusal above: a path that does not climb out is read, not refused
        for the same reason a sibling of the project would be."""
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        inside = root / "baseline.json"
        _dumped(root / "p.ddd.json", inside)
        result = compared(revision, inside, root, {})
        assert result.verdict is True

    def test_what_the_named_baseline_includes_is_read_where_it_points(self, tmp_path: Path) -> None:
        """The confinement is on the file the reader names, and not on the tree that file pulls
        in: a description under the root whose ``includes`` climb out of it is read, and one of
        its own findings comes back filed outside the root.

        Deliberate, and the reason is that the include tree is the baseline project's own
        business - ``ddd compare`` reads it the same way, and a second reading of "which files a
        delivery is made of" here is the drift this part exists to remove. It is not the
        file-read primitive spec §3 weighs either: it needs a description *under* the root
        already pointing where somebody wants to look, and whoever can reach the port cannot put
        one there.
        """
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "baseline/p.ddd.json": project("P", "a.ddd.json", "../../outside/b.ddd.json"),
                "baseline/a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        write_tree(
            tmp_path / "outside",
            {"b.ddd.json": component("B", declare("output", "Speed", unit="rpm"))},
        )
        result = compared(revision, root / "baseline" / "p.ddd.json", root, {})
        forwarded = {
            f.file for f in result.baseline_findings if f.diagnostic.check == "multiple-producers"
        }
        assert (tmp_path / "outside" / "b.ddd.json").resolve() in forwarded


class TestTheRefusals:
    """Why a baseline was refused: outside the root and unreadable, which this module settles
    itself, and whichever of the reader's own :class:`Refusal` reasons it came back with.

    Each is the reader's own answer, never a classification of one diagnostic out of the bag -
    which named a description with a missing include "neither a dictionary nor a description"
    and sent a reader off to replace a file whose only fault was the missing include.
    """

    def test_a_missing_baseline_is_unreadable(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        with pytest.raises(BaselineRefusedError, match="unreadable"):
            compared(revision, root / "missing.json", root, {})

    def test_a_directory_named_as_a_baseline_is_unreadable(self, tmp_path: Path) -> None:
        """Reading a directory's bytes is the same ``OSError`` an unreadable file raises, not a
        shape a reader would ever call json - the loader's own ``_read_text`` treats it the
        same way, and this does not invent a second rule for it."""
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        directory = root / "a_directory"
        directory.mkdir()
        with pytest.raises(BaselineRefusedError, match="unreadable"):
            compared(revision, directory, root, {})

    def test_a_baseline_that_is_not_json_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "bad.json").write_text("{not json at all")
        with pytest.raises(BaselineRefusedError, match="not valid json"):
            compared(revision, root / "bad.json", root, {})

    def test_the_reason_does_not_repeat_the_baseline_it_already_names(self, tmp_path: Path) -> None:
        """``read_baseline``'s ``"in the baseline: "`` marks a finding shown beside a run's own
        findings. Inside a sentence that has already named the baseline it is a stutter, and it
        was on the page's own refusal banner."""
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "empty.json").write_text("")
        with pytest.raises(BaselineRefusedError) as refused:
            compared(revision, root / "empty.json", root, {})
        assert "in the baseline" not in str(refused.value)
        assert str(refused.value).endswith("is not valid json: Expecting value")

    def test_a_baseline_that_is_neither_a_dictionary_nor_a_description_is_refused(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "odd.json").write_text(json.dumps({"something": "else"}))
        with pytest.raises(BaselineRefusedError, match="neither a dictionary nor a description"):
            compared(revision, root / "odd.json", root, {})

    def test_a_description_whose_include_is_missing_is_not_called_the_wrong_kind_of_file(
        self, tmp_path: Path
    ) -> None:
        """Measured, and with no race in it: this is a description, and it was told it was
        neither - which reads as "you named the wrong file" and is answered by replacing one
        whose only fault is a missing include."""
        root = tmp_path / "project"
        revision = _revision(
            root, {"p.ddd.json": project("P"), "old/p.ddd.json": project("P", "gone.ddd.json")}
        )
        with pytest.raises(BaselineRefusedError) as refused:
            compared(revision, root / "old" / "p.ddd.json", root, {})
        assert "is a description that could not be read" in str(refused.value)
        assert "gone.ddd.json" in str(refused.value)

    def test_a_description_that_does_not_validate_is_still_a_description(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "named.ddd.json").write_text(json.dumps(project("P ")), encoding="utf-8")
        with pytest.raises(BaselineRefusedError, match="is a description that could not be read"):
            compared(revision, root / "named.ddd.json", root, {})

    def test_a_dump_this_ddd_cannot_read_is_still_a_dump(self, tmp_path: Path) -> None:
        """A dictionary from a newer DDD is precisely the file this one cannot judge by its own
        contract, which is why ``load_dictionary`` gates on ``format`` before validating. Told
        it is neither, a reader would look for a file that is not the one they want."""
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "newer.json").write_text(json.dumps({"format": 999, "name": "P"}))
        with pytest.raises(BaselineRefusedError) as refused:
            compared(revision, root / "newer.json", root, {})
        assert "is a dumped dictionary that could not be read" in str(refused.value)
        assert "use a newer DDD to read it" in str(refused.value)

    def test_a_lone_component_description_is_a_baseline(self, tmp_path: Path) -> None:
        """``holds_a_description`` answers for a component file too, so one is read as a
        delivery of its own - which is what the field's own sentence says it accepts."""
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed", "uint16", unit="rpm")),
            },
        )
        result = compared(revision, root / "a.ddd.json", root, {})
        assert result.verdict is True

    def test_a_baseline_whose_own_plugin_raises_is_refused_rather_than_thrown(
        self, tmp_path: Path
    ) -> None:
        """A description's plugins are loaded and run while it is read, and a defect in one
        raises instead of reporting - past the guard around the comparison's own hooks, which is
        reached later. It was a traceback in the terminal and a 500 telling the reader to go and
        read it, where spec §6 promises a reason."""
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P"),
                "old/tools/broken.py": RAISING_CHECK_PLUGIN,
                "old/p.ddd.json": project("P", plugins=["tools/broken.py"]),
            },
        )
        with pytest.raises(BaselineRefusedError) as refused:
            compared(revision, root / "old" / "p.ddd.json", root, {})
        assert "is a description that could not be read" in str(refused.value)
        assert "failed in its check hook" in str(refused.value)

    def test_every_refusal_the_reader_can_answer_has_words_for_it(self) -> None:
        """The mapping is the whole classification: a reason added to the reader and left out
        here would be a ``KeyError`` on the route rather than a sentence."""
        assert set(_REASONS) == set(Refusal)


class TestTheComparison:
    def test_a_project_compared_against_a_dump_of_itself_matches(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(root / "p.ddd.json", dump)
        result = compared(revision, dump, root, {})
        assert result.verdict is True
        assert result.findings == ()
        assert result.baseline_findings == ()
        assert result.renames == ()

    def test_a_drifted_datatype_fails_the_verdict(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        old = tmp_path / "old"
        write_tree(
            old,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(old / "p.ddd.json", dump)
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        result = compared(revision, dump, root, {})
        assert result.verdict is False
        changed = [f for f in result.findings if f.diagnostic.check == "changed-interface"]
        assert len(changed) == 1
        # `compare()` takes one location for the whole call, the way `ddd compare`'s own report
        # does, so every finding of one comparison is filed at the candidate's own project file -
        # never at the component that happens to declare the object.
        assert changed[0].file == (root / "p.ddd.json").resolve()

    def test_a_rename_is_listed_and_alone_does_not_fail_the_verdict(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        old = tmp_path / "old"
        write_tree(
            old,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Speed", "uint16", unit="rpm", id="k7m2q9xr4t8w")
                ),
            },
        )
        dump = root / "baseline.json"
        _dumped(old / "p.ddd.json", dump)
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Velocity", "uint16", unit="rpm", id="k7m2q9xr4t8w")
                ),
            },
        )
        result = compared(revision, dump, root, {})
        assert result.renames == ({"id": "k7m2q9xr4t8w", "from": "Speed", "to": "Velocity"},)
        # Only `renamed-object`, a warning: nothing about the object's interface changed.
        assert result.verdict is True

    def test_a_revision_with_no_dictionary_cannot_be_compared(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        api = unloaded(root)
        assert api.session.revision is not None
        baseline = root / "baseline.json"
        baseline.write_text("{}")
        with pytest.raises(ValueError, match="did not resolve"):
            compared(api.session.revision, baseline, root, {})

    def test_the_severity_policy_is_the_sessions_own_not_a_new_one(self, tmp_path: Path) -> None:
        """A build record's own ``-W`` grades a comparison check exactly as it grades every
        other one - no separate control this route invents."""
        root = tmp_path / "project"
        old = tmp_path / "old"
        write_tree(
            old,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(old / "p.ddd.json", dump)
        write_tree(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        build_record(root, root / "p.ddd.json", severity=["changed-interface=warning"])
        session = Session(root)
        session.open(root / "p.ddd.json")
        revision = session.revision
        assert revision is not None and revision.builds
        result = compared(revision, dump, root, {})
        assert result.verdict is True

    def test_the_strictest_of_several_builds_governs_not_the_one_that_sorts_first(
        self, tmp_path: Path
    ) -> None:
        """A verdict must not depend on an image's name. Two build records disagreeing about
        ``changed-interface``'s severity used to produce opposite verdicts for the identical
        comparison depending on which one ``build_files``' own sort (by path, which orders by
        image name) put first in ``revision.builds`` - here, deliberately, the lenient one."""
        root = tmp_path / "project"
        old = tmp_path / "old"
        write_tree(
            old,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(old / "p.ddd.json", dump)
        write_tree(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        build_record(
            root,
            root / "p.ddd.json",
            image="aaa_lenient",
            severity=["changed-interface=warning"],
        )
        build_record(root, root / "p.ddd.json", image="zzz_strict")
        session = Session(root)
        session.open(root / "p.ddd.json")
        revision = session.revision
        assert revision is not None
        # Proof the lenient record really is the one `revision.builds[0]` used to trust.
        assert [build.image for build in revision.builds] == ["aaa_lenient", "zzz_strict"]
        result = compared(revision, dump, root, {})
        assert result.verdict is False

    def test_a_baseline_only_finding_files_its_mirror_on_the_baseline_too(
        self, tmp_path: Path
    ) -> None:
        """The judgement call: a comparison finding's own location and notes are always inside
        the open project - `compare()` takes one `location` for the whole call - but an error
        `read_baseline` forwards from the baseline's own analysis carries that analysis's own
        notes unchanged, and a baseline given as a multi-file project description can have a
        `multiple-producers` whose note points at a *second* baseline file. `group_findings`'s
        `_mirrors` step files a copy there too, same as it would for two files of an open
        project. Both copies are correctly attributed to the baseline - the message already
        says "in the baseline" - and both are kept in `baseline_findings`, never `findings`,
        which is what answers `route: null` for them regardless of where either path resolves
        to (see the next test for why that distinction, and not the path, is load-bearing).
        """
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "baseline/p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "baseline/a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "baseline/b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
            },
        )
        result = compared(revision, root / "baseline" / "p.ddd.json", root, {})
        assert not any(f.diagnostic.check == "multiple-producers" for f in result.findings)
        forwarded = [
            f for f in result.baseline_findings if f.diagnostic.check == "multiple-producers"
        ]
        assert len(forwarded) == 2
        assert {f.file for f in forwarded} == {
            (root / "baseline" / "a.ddd.json").resolve(),
            (root / "baseline" / "b.ddd.json").resolve(),
        }
        assert all(f.diagnostic.message.startswith("in the baseline: ") for f in forwarded)
        assert all(_finding(f, None, {})["route"] is None for f in forwarded)

    def test_a_baseline_finding_never_routes_even_when_its_file_is_also_the_open_projects(
        self, tmp_path: Path
    ) -> None:
        """The regression: comparing a project against itself is the first thing a reader
        tries, and a baseline only has to be read from under the session root - it is not
        required to sit outside the candidate's own files, so ``?baseline=`` may legally name
        the project already open. When it does, a baseline finding's file is, path for path, a
        real file of ``revision.files`` - proved below rather than assumed. Answering a route
        by asking "is this file one of the open project's" got that case wrong: a message that
        says "in the baseline: ..." wired a live link into the candidate. What actually marks a
        finding as the baseline's is being in ``baseline_findings`` rather than ``findings``,
        which is a fact about which list it is in, not about where its path resolves to.
        """
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
            },
        )
        # The baseline is the project itself, read a second time.
        result = compared(revision, root / "p.ddd.json", root, {})
        forwarded = [
            f for f in result.baseline_findings if f.diagnostic.check == "multiple-producers"
        ]
        assert len(forwarded) == 2
        sources = {file.path.resolve(): file for file in revision.files}
        for filed in forwarded:
            # Each file really is one of the open project's - the coincidence a path check
            # alone cannot tell apart from a baseline kept in a directory of its own.
            assert filed.file in sources
            assert _finding(filed, sources[filed.file], {})["route"] is not None
            # What the caller actually does: never look a source up for one of these at all.
            assert _finding(filed, None, {})["route"] is None
        # `compare()`'s own findings agree the project can replace itself: no differences.
        assert result.findings == ()


class TestThePluginsComparisonRules:
    """A comparison that ran ``compare()`` and stopped answered a confident "can replace" for a
    delivery ``ddd compare`` exits 1 on: both commands follow it with ``run_compare_hooks``
    (``cli._command_compare``, ``cli._command_check``), and the page did not. ``missing-plugin``
    could not close the hole either, being filed by those same hooks.
    """

    def test_a_plugins_comparison_check_turns_the_verdict(self, tmp_path: Path) -> None:
        description = _layout(tmp_path)
        dump = tmp_path / "baseline.json"
        _dumped(description, dump)
        _moved_key(tmp_path)
        revision = first_revision(tmp_path, description)
        result = compared(revision, dump, tmp_path, {})
        assert result.verdict is False
        assert [f.diagnostic.check for f in result.findings] == ["layout/key-changed"]

    def test_a_plugins_comparison_finding_leads_to_the_declaration_it_names(
        self, tmp_path: Path
    ) -> None:
        """Running the hooks gives the tab something it never had: a comparison finding filed at
        a component of the open project with a real pointer, where ``compare()``'s own are all
        filed at the project file with an empty one. ``route_of`` routes by that pointer, so it
        leads exactly where a consistency finding filed there leads - and the page must let it,
        rather than answering ``null`` by hand."""
        description = _layout(tmp_path)
        dump = tmp_path / "baseline.json"
        _dumped(description, dump)
        _moved_key(tmp_path)
        revision = first_revision(tmp_path, description)
        result = compared(revision, dump, tmp_path, {})
        (filed,) = result.findings
        assert filed.file == (tmp_path / "layout" / "storage.ddd.json").resolve()
        sources = {file.path.resolve(): file for file in revision.files}
        answered = _finding(filed, sources[filed.file], {})
        assert answered["pointer"] == "component.interface[0]"
        assert answered["route"] == {"kind": "variable", "name": "EngineHours"}

    def test_a_plugin_of_the_baseline_the_candidate_does_not_name_is_reported(
        self, tmp_path: Path
    ) -> None:
        """``missing-plugin`` says a rule did not run, which is the one thing a silent partial
        verdict must not leave out - and it is filed by the hooks, so it went with them."""
        description = _layout(tmp_path)
        dump = tmp_path / "baseline.json"
        _dumped(description, dump)
        _unstamped(tmp_path)
        revision = first_revision(tmp_path, description)
        result = compared(revision, dump, tmp_path, {})
        missing = [f.diagnostic for f in result.findings if f.diagnostic.check == "missing-plugin"]
        assert len(missing) == 1
        assert "'layout'" in missing[0].message
        assert missing[0].severity is Severity.WARNING

    def test_a_build_records_override_grades_a_plugins_comparison_check(
        self, tmp_path: Path
    ) -> None:
        """The session's own policy, over a plugin's check as over a built-in one. Without the
        candidate's checks registered on the comparison's bag the policy has no entry to read
        and ``resolve`` falls back to ``Severity.ERROR``, so a ``-W`` the build states would be
        ignored and the verdict would stand against the project's own wishes."""
        description = _layout(tmp_path)
        dump = tmp_path / "baseline.json"
        _dumped(description, dump)
        _moved_key(tmp_path)
        build_record(tmp_path, description, severity=["layout/key-changed=warning"])
        revision = first_revision(tmp_path, description)
        assert [build.image for build in revision.builds] == ["firmware.elf"]
        result = compared(revision, dump, tmp_path, {})
        assert [f.diagnostic.severity.value for f in result.findings] == ["warning"]
        assert result.verdict is True

    def test_a_compare_hook_that_raises_is_a_finding_and_not_an_exception(
        self, tmp_path: Path
    ) -> None:
        """``ddd check`` reports a broken hook as a usage error; the server promises findings and
        never an exception, so it lands as ``plugin-invalid`` here exactly as it does in
        ``ddd.lsp.diagnostics._run`` - and, being an error, it refuses the verdict rather than
        answering one a rule never graded."""
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "tools/demo_plugin.py": RAISING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/demo_plugin.py"]),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(root / "p.ddd.json", dump)
        result = compared(revision, dump, root, {})
        assert [f.diagnostic.check for f in result.findings] == ["plugin-invalid"]
        assert "failed in its compare hook" in result.findings[0].diagnostic.message
        assert result.verdict is False


class TestTheCache:
    def test_a_re_dump_in_place_is_read_again_and_still_holds_one_entry(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "project"
        old = tmp_path / "old"
        write_tree(
            old,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(old / "p.ddd.json", dump)
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm")),
            },
        )
        cache: BaselineCache = {}
        first = compared(revision, dump, root, cache)
        assert first.verdict is True
        assert len(cache) == 1

        # Asked again with nothing changed: served from the cache, not read a second time.
        again = compared(revision, dump, root, cache)
        assert again.verdict is True
        assert len(cache) == 1

        # A re-dump in place moves the file's stamp: read again, never served stale - the one
        # thing a comparison must not do. One entry per path, the newest read holding it.
        write_tree(
            old, {"a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm"))}
        )
        _dumped(old / "p.ddd.json", dump)
        after = compared(revision, dump, root, cache)
        assert after.verdict is False
        assert len(cache) == 1

    def test_an_edit_to_a_file_the_baseline_includes_is_read_again(self, tmp_path: Path) -> None:
        """A dumped dictionary is its own file; a project description is its whole include tree,
        and that tree is the delivery being compared against. Keyed on the named file alone, an
        edit to a file that file includes left the entry looking untouched and a stale verdict
        was served - a comparison answering ``True`` about bytes no longer on disk."""
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
                "old/p.ddd.json": project("P", "a.ddd.json"),
                "old/a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        baseline = root / "old" / "p.ddd.json"
        cache: BaselineCache = {}
        assert compared(revision, baseline, root, cache).verdict is True

        # The baseline's own component, not the file `?baseline=` names, which is untouched.
        write_tree(
            root / "old",
            {"a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm"))},
        )
        after = compared(revision, baseline, root, cache)
        assert after.verdict is False
        assert [f.diagnostic.check for f in after.findings] == ["changed-interface"]

    def test_a_project_can_replace_itself_however_warm_the_cache(self, tmp_path: Path) -> None:
        """The first thing anyone compares against (spec §3), and the sharpest form of the
        staleness above: with the baseline the open project's own description, a warm entry read
        before an edit was compared against the revision made after it, and the tab said a
        project could not replace itself. Which of the two answers a reader got depended on
        nothing but whether the cache happened to be warm, and nothing short of restarting the
        server could clear it - a cache "in the strict sense: discarding it changes speed and
        nothing else" (spec §4) may never decide an answer."""
        root = tmp_path / "project"
        api = opened(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        session = api.session
        first = session.revision
        assert first is not None
        cache: BaselineCache = {}
        assert compared(first, root / "p.ddd.json", root, cache).verdict is True

        write_tree(
            root, {"a.ddd.json": component("A", declare("output", "Speed", "uint8", unit="rpm"))}
        )
        assert session.poll() is True
        second = session.revision
        assert second is not None and second.number == 2
        assert compared(second, root / "p.ddd.json", root, cache).verdict is True

    def test_a_baseline_that_was_refused_is_never_served_from_the_cache(
        self, tmp_path: Path
    ) -> None:
        """The cache holds deliveries, and a refusal is not one: nothing is kept for a file that
        did not resolve, so the reason a reader is given is always this ask's own - and fixing
        the file is answered rather than met with the refusal it earned a minute ago."""
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        baseline = root / "baseline.json"
        baseline.write_text("{not json at all", encoding="utf-8")
        cache: BaselineCache = {}
        with pytest.raises(BaselineRefusedError, match="not valid json"):
            compared(revision, baseline, root, cache)
        assert cache == {}
        _dumped(root / "p.ddd.json", baseline)
        assert compared(revision, baseline, root, cache).verdict is True

    def test_the_cache_keeps_only_the_last_few_baselines(self, tmp_path: Path) -> None:
        """It lives as long as the server and every entry holds a whole dictionary - the 45 MB
        one of a thousand object project - so how many paths one session can be made to hold is
        not a question to leave to whoever can reach the port."""
        root = tmp_path / "project"
        revision = _revision(
            root,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm")),
            },
        )
        dump = root / "baseline.json"
        _dumped(root / "p.ddd.json", dump)
        archived = [root / f"baseline_{number}.json" for number in range(MAX_BASELINES + 1)]
        cache: BaselineCache = {}
        for copy in archived:
            shutil.copy(dump, copy)
            assert compared(revision, copy, root, cache).verdict is True
        assert len(cache) == MAX_BASELINES
        # The oldest fell off; the newest is still there, and the one that fell off is read
        # again rather than refused when it is asked for next.
        assert archived[0].resolve() not in cache
        assert archived[-1].resolve() in cache
        assert compared(revision, archived[0], root, cache).verdict is True
