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


def found(
    file: Path,
    severity: Severity,
    pointer: str = "component.interface[0]",
    check: str = "unused-output",
    message: str = "read by nobody",
) -> Filed:
    """A finding on ``file`` at ``pointer``, as the analysis files one."""
    return Filed(file, Diagnostic(check, severity, message, Location(file, pointer)))


class TestTheFindingsTabsOrder:
    """What every page of the Findings tab is read from: the revision's findings worst first,
    each with its repeat among findings of equal content, and how many there are of each
    severity - derived once, however many pages are asked for."""

    def test_the_worst_come_first_and_within_a_severity_in_the_revision_s_order(
        self, tmp_path: Path
    ) -> None:
        project, a, b = tmp_path / "p.ddd.json", tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
        findings = (
            found(a, Severity.INFO, "component.interface[0]"),
            found(a, Severity.ERROR, "component.interface[1]"),
            found(a, Severity.WARNING, "component.interface[2]"),
            found(b, Severity.INFO, "component.interface[0]"),
            found(b, Severity.ERROR, "component.interface[1]"),
            found(b, Severity.WARNING, "component.interface[2]"),
        )
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.ranked == (1, 4, 2, 5, 0, 3)

    def test_two_findings_of_equal_content_on_one_file_are_told_apart_by_their_repeat(
        self, tmp_path: Path
    ) -> None:
        """Equal file, severity, check, place and words: the second is repeat 1, and a finding
        between them in the revision's order changes neither."""
        project, a = tmp_path / "p.ddd.json", tmp_path / "a.ddd.json"
        twice = found(a, Severity.ERROR, check="definition-mismatch", message="disagrees")
        findings = (twice, found(a, Severity.INFO), twice, found(a, Severity.ERROR))
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.repeats == (0, 0, 1, 0)

    @pytest.mark.parametrize(
        "other",
        [
            {"file": "b.ddd.json"},
            {"severity": Severity.ERROR},
            {"check": "missing-id"},
            {"pointer": "component.interface[1]"},
            {"message": "read by everybody"},
        ],
        ids=["file", "severity", "check", "place", "words"],
    )
    def test_a_finding_differing_in_any_of_the_five_is_no_repeat(
        self, tmp_path: Path, other: dict[str, object]
    ) -> None:
        project = tmp_path / "p.ddd.json"
        fields: dict[str, object] = {
            "file": "a.ddd.json",
            "severity": Severity.WARNING,
            "pointer": "component.interface[0]",
            "check": "unused-output",
            "message": "read by nobody",
        }

        def made_of(given: dict[str, object]) -> Filed:
            file = tmp_path / str(given["file"])
            diagnostic = Diagnostic(
                str(given["check"]),
                Severity(given["severity"]),
                str(given["message"]),
                Location(file, str(given["pointer"])),
            )
            return Filed(file, diagnostic)

        findings = (made_of(fields), made_of({**fields, **other}), made_of(fields))
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.repeats == (0, 0, 1)

    def test_a_finding_placed_nowhere_repeats_another_placed_nowhere(self, tmp_path: Path) -> None:
        project = tmp_path / "p.ddd.json"
        nowhere = Filed(project, Diagnostic("schema", Severity.ERROR, "unreadable", None))
        made = derived(revision_of(project, (described(project, "project"),), (nowhere, nowhere)))
        assert made.repeats == (0, 1)

    def test_each_severity_is_counted(self, tmp_path: Path) -> None:
        project, a = tmp_path / "p.ddd.json", tmp_path / "a.ddd.json"
        findings = (
            found(a, Severity.WARNING),
            found(a, Severity.INFO),
            found(a, Severity.ERROR),
            found(a, Severity.INFO),
            found(a, Severity.INFO, "component.interface[3]"),
        )
        made = derived(revision_of(project, (described(project, "project"),), findings))
        assert made.counts == (1, 1, 3)

    def test_a_revision_without_findings_has_none_of_each(self, tmp_path: Path) -> None:
        project = tmp_path / "p.ddd.json"
        made = derived(revision_of(project, (described(project, "project"),), ()))
        assert (made.ranked, made.repeats, made.counts) == ((), (), (0, 0, 0))
