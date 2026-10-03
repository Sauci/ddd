"""What the api derives from one revision, derived once for it rather than once per request.

A revision is immutable, so anything computed from it alone holds for as long as it is the newest:
each file's description by resolved path, and its fingerprint, each finding's own file's
description, the findings grouped by file, how many findings each root entry carries, and the
order the Findings tab lists them in, with how many there are of each severity. ``GET /api/state``
resolved every finding's file to find its description; ``GET /api/files`` counted every finding
once per entry; every plan resolved every file again for the fingerprints its edits carry; and
every page of the Findings tab would sort the whole revision again to find its own findings.

Nothing here resolves a path the revision's own analysis resolved already
(:attr:`ddd.gui.session.Revision.resolved_paths`): each resolution is a system call per directory
of the path, and while another analysis runs each waits out its turn of the interpreter. Measured
on the Linux development PC over a generated project of 100,000 declarations (``--shape mixed
--missing-ids 1 --unread 0.5``: 1,683 files, 125,002 findings), the derivation asked 0.5 to 2.5 s
into an analysis took 2.3 to 3.6 s while it resolved every path, the analysis over by the time it
answered, and 170 to 543 ms with :meth:`pathlib.Path.resolve` answering from a table made
beforehand, the analysis still running - one run at each of four moments, each way.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.diagnostics import Location, Severity
from ddd.findings_by_file import FindingsByFile
from ddd.gui.session import Filed, Revision, SourceFile
from ddd.loading import resolve_path

_ENTRY: Final = re.compile(r"project\.includes\[(0|[1-9][0-9]*)\]")
"""The pointer of one entry of a project description's ``includes``, matched whole: its index in
ascii digits with no leading zero, which is the one way ``f"project.includes[{i}]"`` spells it."""


@dataclass(frozen=True, slots=True)
class Derived:
    """What the api derives from one revision."""

    number: int
    """The revision's, which is what says whether this is still the newest."""

    resolved_paths: Mapping[Path, Path]
    """Each path the revision names - each file's and each finding's - and what it resolves to:
    the revision's own record, with any path it lacks resolved once here."""

    files: Mapping[Path, SourceFile]
    """Each file the revision read, by resolved path."""

    stamps: Mapping[Path, str]
    """Each file's fingerprint as the revision read it, by resolved path: what a plan's edits
    carry (:func:`ddd.variables.planned`), so that an Apply after the file changed is refused as
    stale. Made here once, where every plan request made it again, resolving every file."""

    sources: tuple[SourceFile | None, ...]
    """Each finding's file as the revision describes it, in the revision's order: ``None`` for a
    file the revision did not list."""

    findings: FindingsByFile
    """The revision's findings, grouped by the file each is shown on."""

    at_entry: Mapping[int, int]
    """How many findings are filed at ``project.includes[i]`` of the project description, by
    ``i``, compared as the Files tab has always compared them: a whole location, the
    description's own path and the entry's pointer."""

    ranked: tuple[int, ...]
    """The findings' positions in the Findings tab's order: worst first, and within a severity
    in the revision's own order - a stable sort by :attr:`~ddd.diagnostics.Severity.rank`, the
    order the page sorted ``GET /api/state``'s list into before findings came a page at a
    time."""

    repeats: tuple[int, ...]
    """By position, which repeat each finding is among those of equal file, severity, check,
    place and words - ``0`` for the first, ``1`` for the next - counted along :attr:`ranked`,
    which keeps findings of one severity, and so any of equal content, in the revision's order:
    what tells two findings of equal content apart in their keys (:func:`key_of`)."""

    counts: tuple[int, int, int]
    """How many errors, warnings and informational findings the revision has."""

    def resolve(self, path: Path) -> Path:
        """``path`` resolved: as the revision's own record has it where it names it, else
        resolved now - a path the revision does not name."""
        known = self.resolved_paths.get(path)
        if known is not None:
            return known
        return path.resolve()


def derived(revision: Revision) -> Derived:
    """Everything :class:`Derived` holds of ``revision``: each finding's description and entry
    read in one pass over the findings, each distinct path looked up in what the revision's own
    analysis resolved - and resolved here, once, where it resolved none - and the findings
    grouped by file."""
    resolved = _resolved(revision)
    files = {resolved[file.path]: file for file in revision.files}
    sources: list[SourceFile | None] = []
    at_entry: dict[int, int] = {}
    for filed in revision.findings:
        sources.append(files.get(resolved[filed.file]))
        entry = _entry_of(revision.project, filed.diagnostic.location)
        if entry is not None:
            at_entry[entry] = at_entry.get(entry, 0) + 1
    ranked = _ranked(revision.findings)
    return Derived(
        number=revision.number,
        resolved_paths=resolved,
        files=files,
        stamps={path: file.fingerprint for path, file in files.items()},
        sources=tuple(sources),
        findings=FindingsByFile(
            ((filed.file, filed.diagnostic) for filed in revision.findings), resolved
        ),
        at_entry=at_entry,
        ranked=ranked,
        repeats=_repeats(revision.findings, ranked),
        counts=_counts(revision.findings),
    )


def _resolved(revision: Revision) -> dict[Path, Path]:
    """:attr:`Derived.resolved_paths` of ``revision``: its own record, and each path it names that
    the record does not, resolved once by the loader's own rule - every path, for a revision made
    by hand rather than by an analysis."""
    resolved = dict(revision.resolved_paths)
    for path in (*(file.path for file in revision.files), *(f.file for f in revision.findings)):
        if path not in resolved:
            resolved[path] = resolve_path(path)
    return resolved


def content_of(filed: Filed) -> tuple[str, str, str, str, str]:
    """What a finding's key is made of, its repeat aside: the file it is shown on, its severity,
    its check, its place and its words, each as ``GET /api/findings`` answers it."""
    found = filed.diagnostic
    pointer = "" if found.location is None else found.location.pointer
    return (filed.file.as_posix(), found.severity.value, found.check, pointer, found.message)


def key_of(filed: Filed, repeat: int) -> str:
    """A finding's key: its :func:`content_of` and its repeat, as a compact json array - so that no
    two different findings share one, whatever their words hold. The page reads it as opaque."""
    return json.dumps([*content_of(filed), repeat], separators=(",", ":"))


def _ranked(findings: Sequence[Filed]) -> tuple[int, ...]:
    """:attr:`Derived.ranked` of ``findings``."""
    return tuple(
        sorted(
            range(len(findings)), key=lambda position: findings[position].diagnostic.severity.rank
        )
    )


def _repeats(findings: Sequence[Filed], ranked: Sequence[int]) -> tuple[int, ...]:
    """:attr:`Derived.repeats` of ``findings``, counted along ``ranked``."""
    seen: dict[tuple[str, str, str, str, str], int] = {}
    repeats = [0] * len(findings)
    for position in ranked:
        content = content_of(findings[position])
        repeats[position] = seen.get(content, 0)
        seen[content] = repeats[position] + 1
    return tuple(repeats)


def _counts(findings: Iterable[Filed]) -> tuple[int, int, int]:
    """:attr:`Derived.counts` of ``findings``."""
    counted = Counter(filed.diagnostic.severity for filed in findings)
    return (counted[Severity.ERROR], counted[Severity.WARNING], counted[Severity.INFO])


def _entry_of(project: Path, location: Location | None) -> int | None:
    """Which entry of ``project``'s own ``includes`` a finding is filed at, or ``None``: the
    ``i`` for which ``location`` is ``Location(project, f"project.includes[{i}]")``, so that a
    sub-project's finding at its own entry of that index is not the root's, a key inside an
    entry is not the entry, and a finding placed nowhere is no entry's either."""
    if location is None:
        return None
    matched = _ENTRY.fullmatch(location.pointer)
    if matched is None or location != Location(project, location.pointer):
        return None
    return int(matched[1])
