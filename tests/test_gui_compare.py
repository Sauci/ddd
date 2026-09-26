"""Tests for ``ddd.gui.compare``: whether the open project can stand in for a baseline.

Every revision these tests need is built through ``opened``/``unloaded`` of ``test_gui_api.py`` -
the one place this suite already knows how to put a small project on disk and open a
``Session`` over it - reached as ``api.session.revision``, exactly as that module's own tests
reach it. A second way to build one here would be the duplication this series keeps paying for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import build_record, component, declare, project, write_tree
from ddd.cli import EXIT_OK, main
from ddd.gui.api import _finding
from ddd.gui.compare import BaselineCache, BaselineRefusedError, compared
from ddd.gui.session import Revision, Session
from test_gui_api import opened, unloaded


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


class TestTheFourRefusals:
    """The spec names four reasons a baseline is refused; the fourth is the one nobody thinks
    of - a perfectly valid json file that is simply something else."""

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

    def test_a_baseline_that_is_neither_a_dictionary_nor_a_description_is_refused(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "project"
        revision = _revision(root, {"p.ddd.json": project("P")})
        (root / "odd.json").write_text(json.dumps({"something": "else"}))
        with pytest.raises(BaselineRefusedError, match="neither a dictionary nor a description"):
            compared(revision, root / "odd.json", root, {})


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
        says "in the baseline" - and both are inert on the page: `_finding` resolves a route
        only for a file in `revision.files`, and a baseline file never is one, so this is the
        same `route: null` an unopenable finding already gets for any other reason.
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
        forwarded = [f for f in result.findings if f.diagnostic.check == "multiple-producers"]
        assert len(forwarded) == 2
        assert {f.file for f in forwarded} == {
            (root / "baseline" / "a.ddd.json").resolve(),
            (root / "baseline" / "b.ddd.json").resolve(),
        }
        assert all(f.diagnostic.message.startswith("in the baseline: ") for f in forwarded)
        assert all(_finding(f, None, {})["route"] is None for f in forwarded)


class TestTheCache:
    def test_the_cache_keys_on_path_and_fingerprint_not_path_alone(self, tmp_path: Path) -> None:
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

        # A re-dump changes the fingerprint: read again, never served stale - the one thing a
        # comparison must not do.
        write_tree(
            old, {"a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm"))}
        )
        _dumped(old / "p.ddd.json", dump)
        after = compared(revision, dump, root, cache)
        assert after.verdict is False
        assert len(cache) == 2
