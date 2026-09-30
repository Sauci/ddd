"""``ddd.gui.derived``: what the api derives from one revision, once."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import directory_link
from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.gui.derived import derived
from ddd.gui.session import Filed, Revision, SourceFile


def described(path: Path, kind: str = "component") -> SourceFile:
    return SourceFile(path, kind, None, True, "0" * 64, 0, 0, 0)


def filed(file: Path, location: Location | None, check: str = "include-empty") -> Filed:
    return Filed(file, Diagnostic(check, Severity.ERROR, "a finding", location))


def revision_of(
    project: Path, files: tuple[SourceFile, ...], findings: tuple[Filed, ...], number: int = 7
) -> Revision:
    return Revision(
        number=number,
        project=project,
        builds=(),
        files=files,
        findings=findings,
        resolved=None,
        analysed=True,
        checks=(),
        index=None,
        served=(project.parent,),
    )


def test_each_finding_s_file_is_described_in_the_revision_s_order(tmp_path: Path) -> None:
    """``None`` for a finding on a file the revision did not list, which leads nowhere."""
    project, a = tmp_path / "p.ddd.json", tmp_path / "a.ddd.json"
    files = (described(project, "project"), described(a))
    findings = (
        filed(a, Location(a, "component")),
        filed(tmp_path / "gone.ddd.json", None),
        filed(project, None),
        filed(a, Location(a, "component.interface[0]")),
    )
    made = derived(revision_of(project, files, findings))
    assert made.number == 7
    assert made.sources == (files[1], None, files[0], files[1])
    assert made.files == {project.resolve(): files[0], a.resolve(): files[1]}
    assert list(made.findings) == [(entry.file, entry.diagnostic) for entry in findings]


def test_a_file_spelled_another_way_is_described_as_the_file_it_is(tmp_path: Path) -> None:
    (tmp_path / "lib").mkdir()
    directory_link(tmp_path / "link", tmp_path / "lib")
    project, a = tmp_path / "p.ddd.json", (tmp_path / "lib" / "a.ddd.json").resolve()
    files = (described(project, "project"), described(a))
    findings = (filed(tmp_path / "link" / "a.ddd.json", None),)
    assert derived(revision_of(project, files, findings)).sources == (files[1],)


def test_a_file_is_resolved_as_often_however_many_findings_it_carries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, a = tmp_path / "p.ddd.json", tmp_path / "a.ddd.json"
    files = (described(project, "project"), described(a))
    real = Path.resolve
    resolved: list[Path] = []

    def counted(self: Path, strict: bool = False) -> Path:
        resolved.append(self)
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", counted)
    asked = []
    for many in (1, 50):
        resolved.clear()
        derived(revision_of(project, files, tuple(filed(a, None) for _ in range(many))))
        asked.append(resolved.count(a))
    assert asked[0] == asked[1]


class TestTheFindingsAtEachEntry:
    """Counted as the Files tab always compared them: a whole location, the description's own
    path with an entry's pointer, never resolved."""

    def test_each_entry_counts_the_findings_filed_at_it(self, tmp_path: Path) -> None:
        project = tmp_path / "p.ddd.json"
        findings = (
            filed(project, Location(project, "project.includes[2]")),
            filed(project, Location(project, "project.includes[0]")),
            filed(project, Location(project, "project.includes[2]"), check="file-not-found"),
            filed(project, None),
        )
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.at_entry == {0: 1, 2: 2}

    @pytest.mark.parametrize(
        "pointer",
        [
            "project.includes[2].x",
            "x.project.includes[2]",
            "project.includes[02]",
            "project.includes[\N{ARABIC-INDIC DIGIT TWO}]",
            "project.includes[2]\n",
            "project.includes",
        ],
    )
    def test_a_place_that_is_not_an_entry_s_own_pointer_is_no_entry_s(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """A key inside an entry, the same words nested elsewhere, and an index spelled any other
        way than ``f"project.includes[{i}]"`` spells one."""
        project = tmp_path / "p.ddd.json"
        findings = (filed(project, Location(project, pointer)),)
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.at_entry == {}

    def test_a_sub_project_s_entry_of_the_same_index_is_not_the_root_s(
        self, tmp_path: Path
    ) -> None:
        project, sub = tmp_path / "p.ddd.json", tmp_path / "sub.ddd.json"
        findings = (filed(sub, Location(sub, "project.includes[0]")),)
        files = (described(project, "project"), described(sub, "project"))
        assert derived(revision_of(project, files, findings)).at_entry == {}

    def test_an_entry_s_finding_with_a_line_or_spelled_through_a_link_is_not_its_own(
        self, tmp_path: Path
    ) -> None:
        """The whole location is compared, its line and column with it, and its path as filed."""
        (tmp_path / "real").mkdir()
        directory_link(tmp_path / "link", tmp_path / "real")
        project = (tmp_path / "real" / "p.ddd.json").resolve()
        elsewhere = tmp_path / "link" / "p.ddd.json"
        findings = (
            filed(project, Location(project, "project.includes[1]", line=3)),
            filed(elsewhere, Location(elsewhere, "project.includes[1]")),
        )
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.at_entry == {}
