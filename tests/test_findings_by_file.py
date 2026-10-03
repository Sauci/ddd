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


def test_where_a_file_s_findings_stand_however_it_is_spelled(tmp_path: Path) -> None:
    """In the order given: the positions a page of one file's findings is read from."""
    (tmp_path / "sub").mkdir()
    a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
    pairs = [
        (a, found(a, "1")),
        (b, found(b, "2")),
        (tmp_path / "sub" / ".." / "a.ddd.json", found(a, "3")),
    ]
    grouped = FindingsByFile(pairs)
    assert grouped.positions(tmp_path / "sub" / ".." / "a.ddd.json") == (0, 2)
    assert grouped.positions(a) == (0, 2)
    assert grouped.positions(b) == (1,)
    assert grouped.positions(tmp_path / "c.ddd.json") == ()


def test_a_file_the_record_names_is_never_resolved_again(tmp_path: Path, monkeypatch) -> None:
    """Grouped by what the record says each file resolves to, and asked about the same way: a
    file it names is resolved neither as it is grouped nor as it is asked for, nor as it is
    compared (:meth:`FindingsByFile.resolve`); one it does not name is resolved, as before."""
    (tmp_path / "sub").mkdir()
    a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
    spelled = tmp_path / "sub" / ".." / "a.ddd.json"
    resolved: list[Path] = []
    real = Path.resolve
    monkeypatch.setattr(
        Path, "resolve", lambda self, strict=False: resolved.append(self) or real(self, strict)
    )
    grouped = FindingsByFile([(a, found(a, "1")), (b, found(b, "2"))], {a: a, b: b})
    assert grouped.positions(a) == (0,)
    assert grouped.on_any([b, a]) == [(a, found(a, "1")), (b, found(b, "2"))]
    assert grouped.resolve(b) == b
    assert resolved == []
    assert grouped.positions(spelled) == (0,)
    assert resolved == [spelled]
