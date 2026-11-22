"""``ddd.findings_by_file``: findings grouped by resolved file, given back in the order given."""

from __future__ import annotations

from pathlib import Path

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.findings_by_file import FindingsByFile, noted_at


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


def noted(path: Path, pointer: str, at: Path, there: str) -> Diagnostic:
    """A finding shown at ``pointer`` of ``path``, with a note naming ``there`` of ``at``."""
    return Diagnostic(
        "duplicate-constant",
        Severity.ERROR,
        "declared already",
        Location(path, pointer),
        notes=(("first declared here", Location(at, there)),),
    )


def test_the_findings_noting_a_place_come_back_however_it_is_spelled(tmp_path: Path) -> None:
    """What ties a finding to a place it is not shown on: the loader's refusal of a later entry
    repeating a name is shown on that entry's file, and names the first entry by its note. In the
    order given, each once however many of its notes name the place, however the place's file is
    spelled - and none for a place no note names, a note naming no place among them."""
    (tmp_path / "sub").mkdir()
    c, w = tmp_path / "c.ddd.json", tmp_path / "w.ddd.json"
    spelled = tmp_path / "sub" / ".." / "c.ddd.json"
    twice = Diagnostic(
        "duplicate-constant",
        Severity.ERROR,
        "declared already",
        Location(w, "constants[1]"),
        notes=(
            ("first declared here", Location(spelled, "constants[0]")),
            ("hint", None),
            ("and here", Location(c, "constants[0]")),
        ),
    )
    pairs = [
        (w, noted(w, "constants[0]", c, "constants[0]")),
        (c, found(c, "constants[0]")),
        (w, twice),
        (w, noted(w, "constants[2]", c, "constants[1]")),
    ]
    grouped = FindingsByFile(pairs)
    assert grouped.noting(spelled, "constants[0]") == (pairs[0], pairs[2])
    assert grouped.noting(c, "constants[1]") == (pairs[3],)
    assert grouped.noting(c, "constants") == ()
    assert grouped.noting(w, "constants[0]") == ()


def test_a_note_s_file_is_resolved_once_as_a_finding_s_is(tmp_path: Path, monkeypatch) -> None:
    a, c = tmp_path / "a.ddd.json", tmp_path / "c.ddd.json"
    resolved: list[Path] = []
    real = Path.resolve
    monkeypatch.setattr(
        Path, "resolve", lambda self, strict=False: resolved.append(self) or real(self, strict)
    )
    FindingsByFile([(a, noted(a, str(n), c, "constants[0]")) for n in range(5)])
    assert resolved == [a, c]


def test_a_note_names_a_place_by_its_file_resolved_and_its_pointer(tmp_path: Path) -> None:
    """One finding's question: a note with no place of its own names none, and a note naming the
    pointer of another file, or another pointer of the file, names another place."""
    (tmp_path / "sub").mkdir()
    c, w = tmp_path / "c.ddd.json", tmp_path / "w.ddd.json"
    spelled = tmp_path / "sub" / ".." / "c.ddd.json"
    hinted = Diagnostic(
        "duplicate-constant",
        Severity.ERROR,
        "declared already",
        Location(w, "constants[0]"),
        notes=(("hint", None), ("first declared here", Location(spelled, "constants[0]"))),
    )
    resolve = FindingsByFile(()).resolve
    assert noted_at(hinted, c, "constants[0]", resolve)
    assert not noted_at(hinted, c, "constants[1]", resolve)
    assert not noted_at(hinted, w, "constants[0]", resolve)
    assert not noted_at(found(w, "constants[0]"), c, "constants[0]", resolve)
