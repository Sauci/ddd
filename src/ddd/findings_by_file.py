"""Findings grouped by the file they are shown on, each file resolved once.

Every per-name question the browser interface asks - which findings are a variable's, a unit's,
a type's, a shared entry's - comes down to a finding shown on a file one of the name's places is
in. Asked finding by finding, each question resolved both paths: ``GET /api/variable`` spent
2.9 s of its 3.9 s in :meth:`pathlib.Path.resolve`, the same 1,200 files resolved for every
finding - one run profiled with cProfile, which roughly doubles a Python call's time, on the Linux
development PC while this part was planned, over the 36,000-declaration "many" project of the
spec's section 2 probe: 1,200 components, 66,005 findings, about two a declaration. Grouped
here once, a question reads only the findings of the files it is about, and gets them in the
order they were given - the revision's own - so that an answer asked this way is the answer asked
of them all.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

from ddd.diagnostics import Diagnostic

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on."""


class FindingsByFile:
    """The findings of one analysis, each with the file it is shown on, grouped by that file
    resolved: each distinct file resolved once, however many findings it carries - or not at all,
    where ``resolved`` says already what it resolves to.

    ``resolved`` is what each of some paths is known to resolve to: a revision's own record, made
    by the analysis (:attr:`ddd.gui.session.Revision.resolved_paths`). Every path asked about -
    a finding's file as it is grouped, a file asked for, a place compared - is looked up there
    first, and only one it does not name is resolved: each resolution a system call per directory
    of the path, which while an analysis runs waits out the analysis's turn of the interpreter.
    """

    def __init__(self, pairs: Iterable[Pair], resolved: Mapping[Path, Path] | None = None) -> None:
        self._pairs = tuple(pairs)
        # Two statements rather than a conditional expression, which coverage.py counts no
        # branch in.
        known: Mapping[Path, Path] = {}
        if resolved is not None:
            known = resolved
        self._known = known
        seen: dict[Path, Path] = {}
        grouped: dict[Path, list[int]] = {}
        for index, (file, _) in enumerate(self._pairs):
            key = seen.get(file)
            if key is None:
                key = self.resolve(file)
                seen[file] = key
            grouped.setdefault(key, []).append(index)
        self._grouped = {key: tuple(indexes) for key, indexes in grouped.items()}

    def __iter__(self) -> Iterator[Pair]:
        """Every finding, in the order given."""
        return iter(self._pairs)

    def resolve(self, path: Path) -> Path:
        """``path`` resolved: as ``resolved`` has it where it names it, else resolved now. Public
        for what compares the places a finding is filed at with places of its own - a unit's, a
        type's, a constant's - which asks it of both, rather than resolving either again."""
        known = self._known.get(path)
        if known is not None:
            return known
        return path.resolve()

    def on(self, path: Path) -> tuple[Pair, ...]:
        """The findings shown on ``path``, however it is spelled, in the order given."""
        return tuple(self._pairs[index] for index in self._grouped.get(self.resolve(path), ()))

    def positions(self, path: Path) -> tuple[int, ...]:
        """Where in the order given the findings shown on ``path`` stand, however it is spelled:
        what a page of one file's findings is read from."""
        return self._grouped.get(self.resolve(path), ())

    def on_any(self, paths: Iterable[Path]) -> list[Pair]:
        """The findings shown on any of ``paths``, each once, in the order given - never in the
        order the paths are named, which would reorder a panel's list by its declarations."""
        indexes: set[int] = set()
        for path in paths:
            indexes.update(self._grouped.get(self.resolve(path), ()))
        return [self._pairs[index] for index in sorted(indexes)]
