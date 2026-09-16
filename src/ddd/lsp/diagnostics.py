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
from ddd.diagnostics import (
    STANDALONE_POLICY,
    Diagnostic,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.loading import load_workspace
from ddd.lsp.navigation import Loaded, resolve_projects
from ddd.lsp.ranges import Document, read
from ddd.plugins import PluginError

SOURCE: Final = "ddd"
"""What the editor shows next to each finding, so its origin is never in doubt."""

_LSP_SEVERITY: Final[dict[Severity, int]] = {
    Severity.ERROR: 1,
    Severity.WARNING: 2,
    Severity.INFO: 3,
}


def analyse(info: BuildInfo) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over one configured project, exactly as its build would.

    Including the last step of "exactly", which used to be missing: an override naming a
    plugin's check is provisional until the project has been read, because which plugins
    there are is a property of the project, and holding it to what actually registered is
    what ``ddd check`` does before it reports anything. The server cannot answer that with a
    usage error - it has a session to keep - so it says so where the mistake is, on the
    project file the record names. Silently accepted, a build silencing a check by a name
    nothing registers looks exactly like a build silencing one that exists.
    """
    policy = SeverityPolicy.from_strings(list(info.severity), strict=info.strict)
    bag = DiagnosticBag(policy)
    project = Path(info.project)
    bag, covered = _run(project, bag)
    try:
        policy.verify(bag.registered)
    except UnknownCheckError as fault:
        bag.add("plugin-invalid", str(fault), Location(project))
    return bag, covered


def analyse_standalone(path: Path) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over a file read as "a component on its own"."""
    policy = SeverityPolicy.from_strings(list(STANDALONE_POLICY), strict=False)
    return _run(path, DiagnosticBag(policy))


def _analyse_root(path: Path, cache: dict[Path, Document]) -> tuple[DiagnosticBag, frozenset[Path]]:
    """Run the checks over a file no build and no project above it claims.

    A project file is the whole project, whatever no build record says about it: it lists the
    components, so every check has what it needs, and the ten that need the whole project are
    exactly the ones somebody opening a project file wants to see. Reading it under the
    standalone policy silenced them for every file of the project - and, because opening a
    file republishes everything it covers, withdrew them from the components as well.

    The thinner policy stays for what it was written for: a component read alone really does
    have inputs nobody produces and outputs nobody reads, by construction rather than by
    mistake.
    """
    if _declares_a_project(path, cache):
        return _run(path, DiagnosticBag())
    return analyse_standalone(path)


def _declares_a_project(path: Path, cache: dict[Path, Document]) -> bool:
    """Whether the file is a project file, keyed on what the loader keys the kind on."""
    data = read(path, cache).data
    return isinstance(data, dict) and "project" in data


def _analysed(loaded: Loaded) -> tuple[DiagnosticBag, frozenset[Path]]:
    """The second phase of a run, over a project somebody has already read.

    The search for a document's containing project loads every candidate to ask whether it
    includes the document, so by the time one is found the read is done and its findings are
    in the bag it reported into. Running :func:`_run` on it read the same project a second
    time, every refresh - half a second per save on a flat project of two hundred components.
    Only the analysis is left to do, and only when the read reported no error, which is the
    same guard :func:`_run` applies for the same reason.
    """
    bag = loaded.bag
    try:
        if not bag.has_errors:
            analyze(loaded.workspace, bag)
    except PluginError as error:
        bag.add("plugin-invalid", str(error), Location(loaded.path))
    return bag, frozenset(loaded.workspace.sources())


def _run(root: Path, bag: DiagnosticBag) -> tuple[DiagnosticBag, frozenset[Path]]:
    """The two phases of a run, and which files it turned out to cover.

    The early return when reading reported an error is the same one ``ddd check`` makes: there
    is no point resolving references between files that could not all be read. In an editor it
    shows as the semantic findings dropping away while a file is briefly unparseable, and
    coming back with the next save.

    Both phases run under the one guard, not just the second: a plugin's own model is run
    while the files are read, to validate the ``extensions`` blocks against it, so a defect in
    that model raises before the analysis is ever reached. ``covered`` is settled as each
    phase learns it, so a plugin defect during the analysis still withdraws the findings of
    every file the project covers, rather than of the project file alone.
    """
    covered = frozenset({root})
    try:
        workspace = load_workspace(root, bag)
        if workspace is None:
            return bag, covered
        covered = frozenset(workspace.sources())
        if not bag.has_errors:
            analyze(workspace, bag)
    except PluginError as error:
        # A hook or a model raising is a defect of the plugin, not of the project: ``ddd
        # check`` reports it as a usage error, but the server promises findings and never an
        # exception, so it is turned into one here, on the project file itself.
        bag.add("plugin-invalid", str(error), Location(root))
    return bag, covered


def collect(
    builds: Sequence[BuildInfo],
    documents: Iterable[Path] = (),
    root: Path | None = None,
) -> dict[Path, list[dict[str, Any]]]:
    """Findings for every file the given builds cover, plus any document they do not.

    The result has an entry for every file that was looked at, whether or not anything is
    wrong with it, because an empty entry is what withdraws a finding that has been fixed.

    A document no build claims is checked through the project that includes it, if one lies
    above it, and only on its own when none does. That is the same order the hover and the
    jumps follow, and they have to agree: a squiggle saying a datatype names nothing, next to a
    hover that describes it in full, is worse than either answer on its own.

    A file is counted as covered by what a run *reported on*, not only by what the run managed
    to load. The two differ exactly when a run stopped early - a plugin defect ends the read
    after every file has been read and before the analysis - and counting only the load would
    then check an open file a second time on its own and publish everything about it twice.

    Every key is a resolved path, the document included, because that is the one spelling the
    loader hands back and two spellings of one file would be published as two files. Which
    words each one goes out in is the server's to decide, one layer up, where what the client
    called each document is known.
    """
    cache: dict[Path, Document] = {}
    grouped: dict[Path, list[Diagnostic]] = {}
    covered: set[Path] = set()
    for info in builds:
        bag, sources = analyse(info)
        covered |= sources | _group(bag, Path(info.project), grouped)
    for document in documents:
        resolved = document.resolve()
        if resolved in covered:
            continue
        containing = resolve_projects(resolved, root)
        # A candidate that could not be read is named at its own file. Without this the reader
        # gets the thin standalone analysis below and nothing at all saying why: the project
        # that would have given the full answer is broken, and only the plugin can fix it.
        # Once per file: a candidate an earlier document of this call already named, or
        # that was itself a document, is not named again by a later search that meets it.
        unreadable = DiagnosticBag()
        for path in sorted(set(containing.failed) - covered):
            unreadable.add("plugin-invalid", containing.failed[path], Location(path))
        covered |= _group(unreadable, resolved, grouped)
        if containing.projects:
            for loaded in containing.projects:
                bag, sources = _analysed(loaded)
                covered |= sources | _group(bag, loaded.path, grouped)
            continue
        bag, sources = _analyse_root(resolved, cache)
        covered |= sources | _group(bag, resolved, grouped)

    return {
        path: [_as_lsp(finding, cache, path) for finding in grouped.get(path, ())]
        for path in sorted(covered | set(grouped))
    }


def _group(bag: DiagnosticBag, fallback: Path, grouped: dict[Path, list[Diagnostic]]) -> set[Path]:
    """Sort the findings of one run onto the files they belong to, and say which files those were.

    A finding with no location at all is about the project rather than about a place in it -
    an include that matched nothing, for one - and goes on the file the run started from,
    which is the only file the reader can be sure is open.

    The files are returned because they are the ones this run has now spoken for, which is
    what :func:`collect` needs in order not to speak for any of them twice.

    A finding equal to one already filed for that file is dropped. Every configured build is
    run, and a component linked into two images is in both of them, so one mistake in it was
    published once per image: every squiggle drawn twice and the Problems count doubled, with
    nothing in what the protocol carries to tell the two copies apart. Equal means the same
    check, message, place and severity - where two images differ about how loudly to report
    something, they really are saying two different things and both are kept.
    """
    filed: set[Path] = set()
    already = {(path, _identity(entry)) for path, entries in grouped.items() for entry in entries}
    for finding in bag.sorted:
        for entry in (finding, *_mirrors(finding)):
            path = entry.location.path if entry.location else fallback
            filed.add(path)
            key = (path, _identity(entry))
            if key in already:
                continue
            already.add(key)
            grouped.setdefault(path, []).append(entry)
    return filed


def _identity(finding: Diagnostic) -> tuple[str, Severity, Location | None, str]:
    """What makes two findings the same one, for a reader looking at an underline."""
    return (finding.check, finding.severity, finding.location, finding.message)


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


def _as_lsp(finding: Diagnostic, cache: dict[Path, Document], filed: Path) -> dict[str, Any]:
    """One finding as the protocol carries it; ``filed`` is the file it is published for."""
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
    related = [_related(text, note, cache, filed) for text, note in finding.notes]
    if related:
        # Left out entirely rather than sent empty: this is where the "and here is the other
        # declaration" of a mismatch lands, and an empty list is a clickable nothing.
        published["relatedInformation"] = related
    return published


def _related(text: str, location: Any, cache: dict[Path, Document], filed: Path) -> dict[str, Any]:
    """One note of a finding, as somewhere the reader can jump to.

    A note without a location of its own belongs where its finding is, which the protocol has
    no way to say: every piece of related information carries a location. It is therefore
    given the first line of the file the finding is published for - which is what this
    docstring has always claimed and what an empty uri was not: a client reads ``""`` as
    ``file:///``, so the note was a thing to click that landed nowhere near the project.
    """
    if location is None:
        return {"location": {"uri": filed.as_uri(), "range": _WHOLE_FIRST_LINE}, "message": text}
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
