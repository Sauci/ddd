"""What the api derives from one revision, derived once for it rather than once per request.

A revision is immutable, so anything computed from it alone holds for as long as it is the newest:
each file's description by resolved path, each finding's own file's, the findings grouped by file,
and how many findings each root entry carries. ``GET /api/state`` resolved every finding's file
to find its description; ``GET /api/files`` counted every finding once per entry.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.diagnostics import Location
from ddd.findings_by_file import FindingsByFile
from ddd.gui.session import Revision, SourceFile

_ENTRY: Final = re.compile(r"project\.includes\[(0|[1-9][0-9]*)\]")
"""The pointer of one entry of a project description's ``includes``, matched whole: its index in
ascii digits with no leading zero, which is the one way ``f"project.includes[{i}]"`` spells it."""


@dataclass(frozen=True, slots=True)
class Derived:
    """What the api derives from one revision."""

    number: int
    """The revision's, which is what says whether this is still the newest."""

    files: Mapping[Path, SourceFile]
    """Each file the revision read, by resolved path."""

    sources: tuple[SourceFile | None, ...]
    """Each finding's file as the revision describes it, in the revision's order: ``None`` for a
    file the revision did not list."""

    findings: FindingsByFile
    """The revision's findings, grouped by the file each is shown on."""

    at_entry: Mapping[int, int]
    """How many findings are filed at ``project.includes[i]`` of the project description, by
    ``i``, compared as the Files tab has always compared them: a whole location, the
    description's own path and the entry's pointer."""


def derived(revision: Revision) -> Derived:
    """Everything :class:`Derived` holds of ``revision``: each finding's description and entry
    read in one pass over the findings, each distinct file a finding is filed on resolved once
    for its description however many findings it carries, and the findings grouped by file."""
    files = {file.path.resolve(): file for file in revision.files}
    described: dict[Path, SourceFile | None] = {}
    sources: list[SourceFile | None] = []
    at_entry: dict[int, int] = {}
    for filed in revision.findings:
        if filed.file not in described:
            described[filed.file] = files.get(filed.file.resolve())
        sources.append(described[filed.file])
        entry = _entry_of(revision.project, filed.diagnostic.location)
        if entry is not None:
            at_entry[entry] = at_entry.get(entry, 0) + 1
    return Derived(
        number=revision.number,
        files=files,
        sources=tuple(sources),
        findings=FindingsByFile((filed.file, filed.diagnostic) for filed in revision.findings),
        at_entry=at_entry,
    )


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
