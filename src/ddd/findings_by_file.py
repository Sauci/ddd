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

One finding about a name is shown on a file none of the name's places is in: the loader's refusal
of a later entry repeating a name, shown on that entry's file, which no index records, the
analysis keeping nothing of it - and naming the first entry by a note. So the findings are grouped
by the place each of their notes names too, once, as they are by file
(:meth:`FindingsByFile.noting`).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

from ddd.diagnostics import Diagnostic
from ddd.loading import resolve_path

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on."""


class FindingsByFile:
    """The findings of one analysis, each with the file it is shown on, grouped by that file
    resolved, and by the place each of their notes names: each distinct file resolved once,
    however many findings it carries or notes name it - or not at all, where ``resolved`` says
    already what it resolves to.

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

        def once(path: Path) -> Path:
            """``path`` resolved, each spelling of it once however often it is named."""
            key = seen.get(path)
            if key is None:
                key = self.resolve(path)
                seen[path] = key
            return key

        grouped: dict[Path, list[int]] = {}
        noted: dict[tuple[Path, str], list[int]] = {}
        for index, (file, found) in enumerate(self._pairs):
            grouped.setdefault(once(file), []).append(index)
            for _, note in found.notes:
                if note is None:
                    continue
                held = noted.setdefault((once(note.path), note.pointer), [])
                # Once however many of its notes name the place: they are listed in order.
                if not held or held[-1] != index:
                    held.append(index)
        self._grouped = {key: tuple(indexes) for key, indexes in grouped.items()}
        self._noted = {place: tuple(indexes) for place, indexes in noted.items()}

    def __iter__(self) -> Iterator[Pair]:
        """Every finding, in the order given."""
        return iter(self._pairs)

    def resolve(self, path: Path) -> Path:
        """``path`` resolved: as ``resolved`` has it where it names it, else resolved now, as the
        loader resolves a path (:func:`ddd.loading.resolve_path`) - so that a path the system will
        not resolve, a file the page asks the findings of through a loop of links, is one with no
        findings rather than an error. Public for what compares the places a finding is filed at
        with places of its own - a unit's, a type's, a constant's - which asks it of both, rather
        than resolving either again."""
        known = self._known.get(path)
        if known is not None:
            return known
        return resolve_path(path)

    def on(self, path: Path) -> tuple[Pair, ...]:
        """The findings shown on ``path``, however it is spelled, in the order given."""
        return tuple(self._pairs[index] for index in self._grouped.get(self.resolve(path), ()))

    def positions(self, path: Path) -> tuple[int, ...]:
        """Where in the order given the findings shown on ``path`` stand, however it is spelled:
        what a page of one file's findings is read from."""
        return self._grouped.get(self.resolve(path), ())

    def noting(self, path: Path, pointer: str) -> tuple[Pair, ...]:
        """The findings a note of which names ``pointer`` of ``path``, however the file is
        spelled, each once, in the order given: what ties a finding to a place it is not shown on,
        as the loader's refusal of a later entry repeating a name names the first entry."""
        return tuple(
            self._pairs[index] for index in self._noted.get((self.resolve(path), pointer), ())
        )

    def on_any(self, paths: Iterable[Path]) -> list[Pair]:
        """The findings shown on any of ``paths``, each once, in the order given - never in the
        order the paths are named, which would reorder a panel's list by its declarations."""
        indexes: set[int] = set()
        for path in paths:
            indexes.update(self._grouped.get(self.resolve(path), ()))
        return [self._pairs[index] for index in sorted(indexes)]
