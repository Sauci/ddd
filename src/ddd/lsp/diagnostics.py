"""Turning a run of the checks into what an editor draws.

Nothing here decides anything about a project. ``load_workspace`` and ``analyze`` do the same
work they do for ``ddd check``, under the same severity policy the build uses, and this module
only rearranges the result: findings are grouped by the file they belong to and each one is
given a range instead of a pointer.

Two choices shape the rest:

* **Every source of a project is published, not only the file that was saved.** A finding
  about a component is very often *caused* by another one - two components disagreeing about a
  unit is one finding on each side - so publishing only the saved file would leave half of
  every disagreement invisible until somebody happened to open the other half.
* **A file with nothing wrong is published as an empty list.** That is how the protocol says a
  previous complaint is withdrawn; leaving it out instead leaves the old squiggle on screen
  after the mistake is fixed, which is worse than never having shown it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from ddd.analysis import analyze
from ddd.build_info import BuildInfo
from ddd.diagnostics import CHECKS, Diagnostic, DiagnosticBag, Severity, SeverityPolicy
from ddd.loading import load_workspace
from ddd.lsp.ranges import Document, read

SOURCE: Final = "ddd"
"""What the editor shows next to each finding, so its origin is never in doubt."""

_LSP_SEVERITY: Final[dict[Severity, int]] = {
    Severity.ERROR: 1,
    Severity.WARNING: 2,
    Severity.INFO: 3,
}

STANDALONE_POLICY: Final = tuple(
    f"{identifier}=ignore"
    for identifier, check in sorted(CHECKS.items())
    if check.needs_every_component
)
"""What is silenced for a file that belongs to no configured build.

A component read on its own has inputs nobody produces, outputs nobody reads and axes declared
in files nobody handed over - all by construction rather than by mistake. Reporting those fills
the editor with findings whose only cause is what the run was not shown, and buries the ones
about the file in front of the reader.

Derived from the registry rather than listed here, because listing it here is how this went
wrong once already: ``missing-producer`` was silenced and ``unused-output``, which is the same
mistake seen from the other end, was not. A check that needs the whole project now says so
where it is defined, and is covered without anyone remembering this file exists.
"""


def analyse(info: BuildInfo) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over one configured project, exactly as its build would."""
    policy = SeverityPolicy.from_strings(list(info.severity), strict=info.strict)
    return _run(Path(info.project), DiagnosticBag(policy))


def analyse_standalone(path: Path) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over a file that no build in this workspace claims."""
    policy = SeverityPolicy.from_strings(list(STANDALONE_POLICY), strict=False)
    return _run(path, DiagnosticBag(policy))


def _run(root: Path, bag: DiagnosticBag) -> tuple[DiagnosticBag, frozenset[Path]]:
    """The two phases of a run, and which files it turned out to cover.

    The early return when reading reported an error is the same one ``ddd check`` makes: there
    is no point resolving references between files that could not all be read. In an editor it
    shows as the semantic findings dropping away while a file is briefly unparseable, and
    coming back with the next save.
    """
    workspace = load_workspace(root, bag)
    if workspace is None:
        return bag, frozenset({root})
    sources = frozenset(workspace.sources())
    if not bag.has_errors:
        analyze(workspace, bag)
    return bag, sources


def collect(
    builds: Sequence[BuildInfo], documents: Iterable[Path] = ()
) -> dict[Path, list[dict[str, Any]]]:
    """Findings for every file the given builds cover, plus any document they do not.

    The result has an entry for every file that was looked at, whether or not anything is
    wrong with it, because an empty entry is what withdraws a finding that has been fixed.
    """
    grouped: dict[Path, list[Diagnostic]] = {}
    covered: set[Path] = set()
    for info in builds:
        bag, sources = analyse(info)
        covered |= sources
        _group(bag, Path(info.project), grouped)
    for document in documents:
        if document in covered:
            continue
        bag, sources = analyse_standalone(document)
        covered |= sources
        _group(bag, document, grouped)

    cache: dict[Path, Document] = {}
    return {
        path: [_as_lsp(finding, cache) for finding in grouped.get(path, ())]
        for path in sorted(covered | set(grouped))
    }


def _group(bag: DiagnosticBag, fallback: Path, grouped: dict[Path, list[Diagnostic]]) -> None:
    """Sort the findings of one run onto the files they belong to.

    A finding with no location at all is about the project rather than about a place in it -
    an include that matched nothing, for one - and goes on the file the run started from,
    which is the only file the reader can be sure is open.
    """
    for finding in bag.sorted:
        path = finding.location.path if finding.location else fallback
        grouped.setdefault(path, []).append(finding)
        for mirrored in _mirrors(finding):
            grouped.setdefault(mirrored.location.path, []).append(mirrored)  # type: ignore[union-attr]


def _mirrors(finding: Diagnostic) -> list[Diagnostic]:
    """The same finding again, at each other place that takes part in it.

    A conflict has two sides and neither is the wrong one. ``ddd check`` reports it once, with
    a note pointing at the other declaration, which is right for a terminal: the list is read
    whole and saying it twice would be noise.

    An editor reads the other way round. Findings are attached to files, so a file with no
    finding on it looks *correct* - and of two components declaring the same output, only one
    would carry a mark, as though the other were the innocent party. Both are marked here.

    The message needs no rewriting because it already names both sides: "written by component
    'ComponentB' and by component 'ComponentA'" is as true on one as on the other. The notes
    are dropped from the copy: they read in one direction, and the copy points the other way.
    """
    if finding.location is None:
        return []
    seen = {finding.location}
    mirrors = []
    for _, location in finding.notes:
        if location is None or location in seen:
            continue
        seen.add(location)
        mirrors.append(replace(finding, location=location, notes=()))
    return mirrors


def _as_lsp(finding: Diagnostic, cache: dict[Path, Document]) -> dict[str, Any]:
    location = finding.location
    document = read(location.path, cache) if location else None
    pointer = location.pointer if location else ""
    published: dict[str, Any] = {
        "range": document.range_of(pointer) if document else _WHOLE_FIRST_LINE,
        "severity": _LSP_SEVERITY[finding.severity],
        "code": finding.check,
        "source": SOURCE,
        "message": finding.message,
    }
    related = [_related(text, note, cache) for text, note in finding.notes]
    if related:
        # Left out entirely rather than sent empty: this is where the "and here is the other
        # declaration" of a mismatch lands, and an empty list is a clickable nothing.
        published["relatedInformation"] = related
    return published


def _related(text: str, location: Any, cache: dict[Path, Document]) -> dict[str, Any]:
    """One note of a finding, as somewhere the reader can jump to.

    A note without a location of its own belongs where its finding is, which the protocol has
    no way to say: every piece of related information carries a location. It is therefore
    given the first line of the file the finding is on.
    """
    if location is None:
        return {"location": {"uri": "", "range": _WHOLE_FIRST_LINE}, "message": text}
    document = read(location.path, cache)
    return {
        "location": {
            "uri": location.path.as_uri(),
            "range": document.range_of(location.pointer),
        },
        "message": text,
    }


_WHOLE_FIRST_LINE: Final = {
    "start": {"line": 0, "character": 0},
    "end": {"line": 0, "character": 0},
}
