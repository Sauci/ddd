"""``ddd.findings_by_file``: findings grouped by resolved file, given back in the order given."""

from __future__ import annotations

from pathlib import Path

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.findings_by_file import FindingsByFile


def found(path: Path, pointer: str) -> Diagnostic:
    return Diagnostic("unused-output", Severity.WARNING, "not read", Location(path, pointer))


def test_a_file_is_asked_about_however_it_is_spelled(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    a = tmp_path / "a.ddd.json"
    pairs = [(a, found(a, "x")), (tmp_path / "sub" / ".." / "a.ddd.json", found(a, "y"))]
    grouped = FindingsByFile(pairs)
    assert grouped.on(tmp_path / "sub" / ".." / "a.ddd.json") == tuple(pairs)
    assert grouped.on(tmp_path / "b.ddd.json") == ()


def test_several_files_come_back_in_the_order_given_not_the_order_named(tmp_path: Path) -> None:
    a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
    pairs = [(a, found(a, "1")), (b, found(b, "2")), (a, found(a, "3"))]
    grouped = FindingsByFile(pairs)
    assert grouped.on_any([b, a, b]) == pairs
    assert list(grouped) == pairs


def test_each_file_is_resolved_once(tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.ddd.json"
    resolved: list[Path] = []
    real = Path.resolve
    monkeypatch.setattr(
        Path, "resolve", lambda self, strict=False: resolved.append(self) or real(self, strict)
    )
    FindingsByFile([(a, found(a, str(n))) for n in range(5)])
    assert resolved == [a]
