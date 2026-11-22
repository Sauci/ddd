"""The graph of one revision: its modules, the flows between them, and what disagrees.

Transport neutral, and the only place that decides what counts as a disagreement between two
components: everything before this module is a dictionary, the index of where the project writes
each name, and the diagnostics, and everything after it is a page or an endpoint drawing what this
returns. Task 2 is the only caller; it turns a revision's files into :class:`Module` and pairs
each finding with the file it is filed on, so that this module never has to import ``ddd.gui`` to
do its own job.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.ir import DataDictionary, ResolvedInstance, ResolvedObject
from ddd.lsp.navigation import Index, Site
from ddd.pointers import segments

type _ModulePair = tuple[PurePosixPath, PurePosixPath]


@dataclass(frozen=True, slots=True)
class Module:
    """One component of the project, as the canvas shows it."""

    path: PurePosixPath
    name: str
    loaded: bool
    errors: int
    warnings: int
    infos: int


@dataclass(frozen=True, slots=True)
class Disagreement:
    """One finding that says two modules describe the same object differently."""

    object: str | None
    check: str
    severity: Severity
    message: str


@dataclass(frozen=True, slots=True)
class Flow:
    """Everything one module produces for another."""

    source: PurePosixPath
    target: PurePosixPath
    objects: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]

    @property
    def severity(self) -> Severity | None:
        """The worst disagreement on this flow, or nothing when the two agree."""
        if not self.disagreements:
            return None
        return min((d.severity for d in self.disagreements), key=lambda severity: severity.rank)


@dataclass(frozen=True, slots=True)
class Graph:
    """The modules of one revision and what flows between them."""

    modules: tuple[Module, ...]
    flows: tuple[Flow, ...]


def graph_of(
    dictionary: DataDictionary | None,
    modules: Iterable[Module],
    findings: Iterable[tuple[PurePosixPath, Diagnostic]],
    *,
    index: Index | None = None,
) -> Graph:
    """The graph of one revision: its modules, and a flow per producing-consuming pair.

    ``index`` is where the project writes each name, the revision's own
    (:attr:`ddd.gui.session.Revision.index`): what names the object a disagreement is about, by
    the declaration its finding points into. Without one, every disagreement is drawn unnamed.
    """
    sorted_modules = tuple(sorted(modules, key=lambda module: module.path))
    if dictionary is None:
        return Graph(sorted_modules, ())

    # Assumes distinct names among loaded modules; two sharing one would collapse here, the
    # later one in path order silently winning.
    paths_by_component = {module.name: module.path for module in sorted_modules if module.loaded}
    objects_by_pair = _objects_by_pair(
        (*dictionary.objects, *dictionary.instances), paths_by_component
    )
    declared = (
        {}
        if index is None
        else {site: name for name, sites in index.declarations.items() for site in sites}
    )
    disagreements_by_pair = _disagreements_by_pair(objects_by_pair, findings, declared)

    flows = tuple(
        sorted(
            (
                _flow(pair, names, disagreements_by_pair.get(pair, []))
                for pair, names in objects_by_pair.items()
            ),
            key=lambda flow: (flow.source, flow.target),
        )
    )
    return Graph(sorted_modules, flows)


def _objects_by_pair(
    objects: tuple[ResolvedObject | ResolvedInstance, ...],
    paths_by_component: dict[str, PurePosixPath],
) -> dict[_ModulePair, set[str]]:
    """Every producing-consuming pair one of ``objects`` puts a flow between, and their names.

    ``objects`` are the dictionary's objects and its instances alike: a structured variable
    carries the same ``owner``, ``consumers`` and ``local`` as a scalar one.

    A local object contributes to no pair whatever its own ``consumers`` says: a component
    declaring a local object as ``input`` is the ``local-conflict`` the analysis reports for
    it, and that finding does not drop the declaration - it stays in ``consumers`` beside
    ``local=True``, so this is checked on its own rather than assumed from ``consumers`` being
    empty. An object with no owner, an owner or a consumer no module has, or a consumer that
    is its own owner, likewise contributes nothing to that pair.
    """
    pairs: dict[_ModulePair, set[str]] = {}
    for data_object in objects:
        if data_object.local:
            continue
        if data_object.owner is None:
            continue
        source = paths_by_component.get(data_object.owner)
        if source is None:
            continue
        for consumer in data_object.consumers:
            if consumer == data_object.owner:
                continue
            target = paths_by_component.get(consumer)
            if target is None:
                continue
            pairs.setdefault((source, target), set()).add(data_object.name)
    return pairs


def _disagreements_by_pair(
    objects_by_pair: dict[_ModulePair, set[str]],
    findings: Iterable[tuple[PurePosixPath, Diagnostic]],
    declared: Mapping[Site, str],
) -> dict[_ModulePair, list[Disagreement]]:
    """Every disagreement a finding carries, attached to the flow(s) its object puts it on: the
    object ``declared`` names at the declaration the finding points into."""
    found: dict[_ModulePair, list[Disagreement]] = {}
    for file, diagnostic in findings:
        # Assumes at most one of a diagnostic's notes locates another module; several would
        # each add their own disagreement, since no check today files more than one.
        for _, note in diagnostic.notes:
            if note is None:
                continue
            other = PurePosixPath(note.path.as_posix())
            pairs = [pair for pair in ((file, other), (other, file)) if pair in objects_by_pair]
            if not pairs:
                continue
            name = _declared_object(declared, diagnostic.location)
            disagreement = Disagreement(
                name, diagnostic.check, diagnostic.severity, diagnostic.message
            )
            targets = pairs if name is None else [p for p in pairs if name in objects_by_pair[p]]
            for pair in targets:
                found.setdefault(pair, []).append(disagreement)
    return found


def _declared_object(declared: Mapping[Site, str], location: Location | None) -> str | None:
    """The object of the declaration ``location``'s ``component.interface[<index>]...`` pointer
    points into: the name ``declared`` - the index's record, by site - says the file writes there.

    Read by its place, never by its position among the declarations the analysis kept: those
    leave out every one it drops - a repeated name, an unknown type, a curve over a dropped
    axis - so that past the first dropped, a position names the declaration after the one meant,
    or one that flows nowhere, and the disagreement leaves the arrow it is about (14:M2).

    ``None`` when the finding has no place, when the pointer does not have that shape, or when
    the index records no declaration there: the disagreement is still built, only unable to say
    which object of the flow it is about.
    """
    if location is None:
        return None
    parts = segments(location.pointer)
    index = parts[2] if len(parts) >= 3 and parts[:2] == ["component", "interface"] else None
    if not isinstance(index, int):
        return None
    return declared.get(Site(location.path, f"component.interface[{index}].definition"))


def _flow(pair: _ModulePair, objects: set[str], disagreements: list[Disagreement]) -> Flow:
    return Flow(
        source=pair[0],
        target=pair[1],
        objects=tuple(sorted(objects)),
        disagreements=tuple(sorted(disagreements, key=_disagreement_order)),
    )


def _disagreement_order(disagreement: Disagreement) -> tuple[str, str, str]:
    return (disagreement.object or "", disagreement.check, disagreement.message)
