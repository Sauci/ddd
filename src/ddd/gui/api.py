"""The JSON API of ``ddd gui``: each request answered from the session, as a status and a body.

Nothing here reads a socket or a header, which is the server's business. A request arrives as
its method, its path, its query and its body, and leaves as a :class:`Reply`, so every answer
the page can get is tested without a network in between. The API is internal - the page and the
server ship in one wheel - and changes with the package.

Every request and response body is a model of :mod:`ddd.gui.contract`: a request is read with
:meth:`~pydantic.BaseModel.model_validate_json`, refusing anything the page's own types would
not have sent, and a response is built as a model and written by :func:`ddd.gui.depth.written` -
never a hand-assembled ``dict`` - so the shape answered here and the shape
``gui/src/generated/api.ts`` declares cannot drift apart, and an answer nested deeper than the
serializer writes is refused, ``409``, rather than failing to be written.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from ddd import __version__
from ddd.declaration_plans import (
    KINDS,
    SCOPES,
    DeclarationPlan,
    DeclarationRefusalError,
    declarable,
    declare_object,
    form_for,
    read_object,
    remove_declaration,
    scopes_for,
)
from ddd.diagnostics import CHECKS
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    UNVERIFIED,
    EditError,
    FileChange,
    Operation,
    fingerprint,
    unchanged,
)
from ddd.file_plans import (
    CREATABLE,
    FileRefusalError,
    add_plan,
    create_plan,
    included_entries,
    new_errors,
    remove_plan,
)
from ddd.finding_fixes import fixes_for
from ddd.finding_routes import Route as FindingRoute
from ddd.finding_routes import route_of
from ddd.findings_by_file import Pair
from ddd.graph import Module, graph_of
from ddd.gui import contract
from ddd.gui.compare import BaselineCache, BaselineRefusedError, compared
from ddd.gui.depth import TooDeepError, block_too_deep, file_too_deep, within_depth, written
from ddd.gui.derived import Derived, derived, key_of
from ddd.gui.queries import (
    AddConstant,
    AddFile,
    AddRaster,
    AddSection,
    AddUnit,
    AdoptUnits,
    CompareQuery,
    ConstantPlanQuery,
    ConstantQuery,
    CreateFile,
    DeclarableQuery,
    DeclarationPlanQuery,
    DeclareObject,
    DescribeUnit,
    FileQuery,
    FilesPlanQuery,
    FindingsQuery,
    FixQuery,
    NoQuery,
    RasterPlanQuery,
    RasterQuery,
    ReadDeclaration,
    RemoveConstant,
    RemoveDeclaration,
    RemoveFile,
    RemoveRaster,
    RemoveSection,
    RemoveUnit,
    RenameConstant,
    RenameRaster,
    RenameSection,
    RenameType,
    RenameUnit,
    SectionPlanQuery,
    SectionQuery,
    Serving,
    SetConstantKey,
    SetRasterKey,
    SetSectionKey,
    SettleQuery,
    SetTypeKey,
    StateQuery,
    TypePlanQuery,
    TypeQuery,
    UnitPlanQuery,
    UnitQuery,
    ValuePlanQuery,
    ValuesPlanQuery,
    ValuesQuery,
    VariableQuery,
    _Query,
    actions_of,
    json_value,
    outside_served,
)
from ddd.gui.routes import Policy, Route, one_value_each
from ddd.gui.session import KINDS as DESCRIPTION_KINDS
from ddd.gui.session import (
    Filed,
    NoProjectError,
    NotAnalysedError,
    NotInProjectError,
    Revision,
    Session,
    Snapshot,
    SourceFile,
    Undoable,
    _name_in,
    _read_json,
    _served,
    _source,
    find_projects,
    findings_with,
    kind_of,
)
from ddd.ir import DataDictionary
from ddd.loading import resolve_path
from ddd.lsp.edits import settle
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import (
    PlannedEdit,
    UnitPlan,
    UnitProject,
    UnitRefusalError,
    add_unit,
    adopt_units,
    describe_unit,
    remove_unit,
    rename_unit,
    unit_project,
)
from ddd.object_values import Grid, ValueRefusalError, grid_of, set_cell, set_values
from ddd.project_shared import (
    CONSTANTS,
    RASTERS,
    SECTIONS,
    Vocabulary,
    entry_findings,
    entry_in_place,
    shared_rows,
    shown,
)
from ddd.project_shared import uses_of as uses_of_entry
from ddd.project_types import (
    SCALAR_KEYS,
    fixed_by,
    members_of,
    row_of,
    type_findings,
    type_in_place,
    type_rows,
    uses_of,
)
from ddd.project_units import (
    adoptable,
    description_of,
    listed_in_place,
    places_of,
    previewed,
    unit_findings,
    unit_rows,
)
from ddd.shared_plans import (
    SharedPlan,
    SharedProject,
    SharedRefusalError,
    add_entry,
    project_of,
    remove_entry,
    rename_entry,
    set_entry,
)
from ddd.type_plans import REQUIRED, TypePlan, TypeRefusalError, rename_type, set_key
from ddd.variable_keys import offer_for, offers
from ddd.variables import (
    Planned,
    declarations_of,
    hunks,
    located_on,
    planned,
    preview,
    refusal,
    units_in_use,
    vocabulary_of,
)

WAIT_SECONDS: Final = 25.0
"""How long a request for a newer state waits before answering with the current one."""

MEMO: Final = 256
"""How many answers the api keeps for the newest revision: the graph, the Types and Shared files
tabs' rows, and the pages of findings a reader scrolls back to. A bound, the oldest dropped first:
without one, every page of a findings-heavy project a reader scrolled through would be kept until
its next analysis."""

ANALYSING: Final = "analysing"
"""The refusal of a request the analysis has not caught up with: asked of the open project before
its first analysis has landed, or a plan changing a file an edit wrote that no analysis has read
yet. Answered 409, and answered differently once the analysis lands."""

REFUSALS: Final = frozenset({STALE, UNREADABLE, INVALID, UNVERIFIED, ANALYSING})
"""The edit refusals a page can act on, answered 409; anything else an edit raises is a 500."""

_NOTHING_LOADED: Final = "the open project did not load, so no interface of it can be changed"

_NOTHING_RESOLVED: Final = "the open project did not resolve, so no object's values can be read"

_NOTHING_COMPARABLE: Final = (
    "the open project did not resolve, so it cannot be compared against a baseline"
)

type Query = Mapping[str, Sequence[str]]

type SharedPlanner[A] = Callable[[A, Index, SharedProject, dict[Path, Document]], SharedPlan]
"""What :meth:`Api._shared_plan` asks for the plan itself: the action asked for, read as its own
model (``A``), the index, the project's own files and the read cache the route shares. One per
vocabulary, since ``add`` is spelled differently for each."""


@dataclass(frozen=True, slots=True)
class Reply:
    """An answer: the HTTP status and the JSON body."""

    status: int
    body: dict[str, Any]


class Api:
    """The requests the page makes, answered from one session."""

    def __init__(
        self, session: Session, project: Path | None = None, *, wait_seconds: float = WAIT_SECONDS
    ) -> None:
        self.session = session
        self.project = None if project is None else project.resolve()
        self.wait_seconds = wait_seconds
        self._compare_cache: BaselineCache = {}
        self._derived: Derived | None = None
        self._deriving = threading.Lock()
        self._memo: OrderedDict[tuple[object, ...], Reply] = OrderedDict()
        # The state's answer and the version it was made at: what `GET /api/state` answers again
        # until the version moves, every request of a page's long poll asking for it.
        self._state_kept: tuple[int, Reply] | None = None

    def handle(self, method: str, path: str, query: Query, body: bytes | None) -> Reply:
        """The answer to one request: its route looked up by path and method, its query read one
        value a key and as its route's model, and a ``POST``'s body as its own - each refused in
        that order, as the first problem it finds - and only then the route's handler asked, with
        the two it read. A path in either is read against the directories served
        (:meth:`_serving`).

        The query is read before anything asks for the open project, on every route, so that a
        malformed one is answered as one whether a project is open or not."""
        routes = [each for each in ROUTES if each.path == path]
        if not routes:
            return _error(404, "not-found", f"{path} is not part of the api")
        route = next((each for each in routes if each.method == method), None)
        if route is None:
            methods = " or ".join(each.method for each in routes)
            return _error(405, "method-not-allowed", f"{path} takes {methods}")
        values = one_value_each(query, route.name)
        if isinstance(values, str):
            return _error(400, "bad-request", values)
        serving = self._serving()
        try:
            typed = route.query.model_validate(values, context=serving)
        except ValidationError as error:
            return _error(400, "bad-request", _query_message(route, error))
        given = None
        if route.body is not None:
            given = _validated(route.body, body, serving)
            if isinstance(given, Reply):
                return given
        try:
            return route.answer(self, typed, given)
        except TooDeepError as error:
            return _error(409, UNREADABLE, str(error))
        except NoProjectError as error:
            return _error(409, "no-project", str(error))
        except NotAnalysedError as error:
            return _error(409, ANALYSING, str(error))
        except NotInProjectError as error:
            return _error(404, "not-found", str(error))

    def _serving(self) -> Serving:
        """What a request's paths are read against: the directory ``ddd gui`` was started in,
        and the directories the open project's newest revision serves - that one alone before
        there is a revision."""
        root = self.session.root.as_posix()
        revision = self.session.revision
        if revision is None:
            return Serving(root, (root,))
        return Serving(root, tuple(directory.as_posix() for directory in revision.served))

    def _session(self, query: NoQuery, body: None) -> Reply:
        return Reply(200, self._session_body())

    def _projects(self, query: NoQuery, body: None) -> Reply:
        found = find_projects(self.session.root, self.session.build_directories)
        return Reply(
            200,
            written(
                contract.Found(
                    root=found.root.as_posix(),
                    projects=[
                        {"path": p.path.as_posix(), "name": p.name, "images": p.images}
                        for p in found.projects
                    ],
                    refused=[
                        {"record": record.as_posix(), "reason": reason}
                        for record, reason in found.refused
                    ],
                )
            ),
        )

    def _open(self, query: NoQuery, body: contract.OpenRequest) -> Reply:
        wanted = resolve_path(Path(body.path))
        found = find_projects(self.session.root, self.session.build_directories)
        allowed = {p.path for p in found.projects} | ({self.project} if self.project else set())
        if wanted not in allowed:
            return _error(404, "not-found", f"{body.path} is not a project found here")
        try:
            self.session.open(wanted)
        except ValueError as error:
            return _error(409, "not-a-project", str(error))
        # Answered at once, the project named: the page follows its first analysis from the
        # state, which says it is being analysed until it lands.
        return Reply(200, self._session_body())

    def _state(self, query: StateQuery, body: None) -> Reply:
        """What the session says: at once, or as soon as its version is past ``?after=``, or
        once the wait runs out.

        Made once a version and kept, every request of a page's long poll asking for it: the
        version moves at every change of what the answer says. Not guarded, unlike
        :meth:`_derive`, which is what the making costs most: two requests of one version that
        both find nothing kept both make it from the one derivation, and one made at an older
        version can be kept over a newer one's, which the newer version's next request makes
        again. Each answer is the one its own version says; only work is repeated."""
        after = query.after
        if after is None:
            snapshot = self.session.snapshot()
        else:
            snapshot = self.session.wait(after, self.wait_seconds)
        if snapshot.project is None:
            raise NoProjectError("no project is open")
        kept = self._state_kept
        if kept is not None and kept[0] == snapshot.version:
            return kept[1]
        reply = self._state_of(snapshot, snapshot.project)
        self._state_kept = (snapshot.version, reply)
        return reply

    def _state_of(self, snapshot: Snapshot, project: Path) -> Reply:
        """The state ``snapshot`` says of ``project``, the one open: revision ``0``, no files and
        every count ``0`` before its first analysis. The findings themselves are
        ``GET /api/findings``'s, a page at a time; this counts them."""
        revision = snapshot.revision
        number = 0
        edits = 0
        files: list[dict[str, Any]] = []
        counts = (0, 0, 0)
        if revision is not None:
            number = revision.number
            edits = revision.edits
            counts = self._derive(revision).counts
            files = [
                {
                    "path": file.path.as_posix(),
                    "kind": file.kind,
                    "name": file.name,
                    "loaded": file.loaded,
                    "fingerprint": file.fingerprint,
                    "findings": {
                        "error": file.errors,
                        "warning": file.warnings,
                        "info": file.infos,
                    },
                }
                for file in revision.files
            ]
        top = snapshot.undoable
        return Reply(
            200,
            written(
                contract.State(
                    revision=number,
                    version=snapshot.version,
                    project=project.as_posix(),
                    files=files,
                    counts={"error": counts[0], "warning": counts[1], "info": counts[2]},
                    undoable=None if top is None else {"at": top.at, "label": top.label},
                    analysing=snapshot.analysing,
                    edits=edits,
                )
            ),
        )

    def _findings(self, query: FindingsQuery, body: None) -> Reply:
        """A page of the newest revision's findings: from ``?offset=`` - ``0`` when none is given -
        at most ``?limit=`` of them, or every one from the offset on when no limit is given, of
        those ``?severity=``, ``?file=`` (a file's path, however spelled) and ``?check=`` leave,
        in the Findings tab's order, each with its key.

        Kept for the revision (:meth:`_memoised`), one answer per page and filters: a reader
        scrolling back to a page finds it made already."""
        revision = self._opened()
        offset, limit, severity = query.offset, query.limit, query.severity
        file, check = query.file, query.check
        return self._memoised(
            revision,
            ("findings", offset, limit, severity, file, check),
            lambda: self._findings_of(revision, offset, limit, severity, file, check),
        )

    def _findings_of(
        self,
        revision: Revision,
        offset: int,
        limit: int | None,
        severity: str | None,
        file: str | None,
        check: str | None,
    ) -> Reply:
        """:meth:`_findings`' answer: the positions the filters leave, in the tab's order - a
        file's read from where its own findings stand, sorted by severity as stably as the whole
        revision's were - and of them the page asked for, each finding listed with where it
        leads, as a panel lists one, and with its key."""
        derived = self._derive(revision)
        findings = revision.findings
        order: Sequence[int] = derived.ranked
        if file is not None:
            order = sorted(
                derived.findings.positions(Path(file)),
                key=lambda position: findings[position].diagnostic.severity.rank,
            )
        if severity is not None:
            order = [at for at in order if findings[at].diagnostic.severity == severity]
        if check is not None:
            order = [at for at in order if findings[at].diagnostic.check == check]
        page = order[offset:]
        if limit is not None:
            page = page[:limit]
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            written(
                contract.FindingsReply(
                    revision=revision.number,
                    total=len(order),
                    offset=offset,
                    findings=[
                        {
                            **_finding(findings[at], derived.sources[at], cache),
                            "key": key_of(findings[at], derived.repeats[at]),
                        }
                        for at in page
                    ],
                )
            ),
        )

    def _file(self, query: FileQuery, body: None) -> Reply:
        """A description file's own json, refused where it nests deeper than its answer carries
        (:func:`~ddd.gui.depth.file_too_deep`), naming the file."""
        content = self.session.read_file(Path(query.path))
        refused = file_too_deep(content.path, content.data)
        if refused is not None:
            return _error(409, UNREADABLE, refused)
        return Reply(
            200,
            written(
                contract.FileContent(
                    path=content.path.as_posix(),
                    fingerprint=content.fingerprint,
                    data=content.data,
                    error=content.error,
                )
            ),
        )

    def _dictionary(self, query: NoQuery, body: None) -> Reply:
        """The dictionary of the newest revision, refused where an extension block it carries
        nests deeper than its answer carries (:func:`~ddd.gui.depth.block_too_deep`), naming the
        file that states it."""
        revision = self._opened()
        dictionary = revision.dictionary
        refused = block_too_deep(revision)
        if refused is not None:
            return _error(409, UNREADABLE, refused)
        return Reply(
            200,
            written(
                contract.DictionaryReply(
                    revision=revision.number,
                    # Dumped here rather than left a model for DictionaryReply to nest: the file
                    # format already publishes this shape under `ddd schema dictionary`, and the
                    # api schema is not the place to publish it a second time.
                    dictionary=None if dictionary is None else written(dictionary),
                )
            ),
        )

    def _graph(self, query: NoQuery, body: None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("graph",), lambda: self._graph_of(revision))

    def _graph_of(self, revision: Revision) -> Reply:
        modules = [_module(file) for file in revision.files if file.kind == "component"]
        findings = [(PurePosixPath(f.file.as_posix()), f.diagnostic) for f in revision.findings]
        built = graph_of(revision.dictionary, modules, findings)
        return Reply(
            200,
            written(
                contract.GraphReply(
                    revision=revision.number,
                    dictionary=revision.dictionary is not None,
                    modules=[
                        {
                            "path": module.path.as_posix(),
                            "name": module.name,
                            "loaded": module.loaded,
                            "findings": {
                                "error": module.errors,
                                "warning": module.warnings,
                                "info": module.infos,
                            },
                        }
                        for module in built.modules
                    ],
                    flows=[
                        {
                            "source": flow.source.as_posix(),
                            "to": flow.target.as_posix(),
                            "objects": flow.objects,
                            "severity": flow.severity,
                            "disagreements": [
                                {
                                    "object": disagreement.object,
                                    "check": disagreement.check,
                                    "severity": disagreement.severity,
                                    "message": disagreement.message,
                                }
                                for disagreement in flow.disagreements
                            ],
                        }
                        for flow in built.flows
                    ],
                ),
                by_alias=True,
            ),
        )

    def _checks(self, query: NoQuery, body: None) -> Reply:
        revision = self.session.revision
        plugins = () if revision is None else revision.checks
        return Reply(
            200,
            written(
                contract.ChecksReply(
                    checks=[
                        {
                            "check": info.identifier,
                            "default_severity": info.default_severity,
                            "description": info.description,
                            "overridable": info.overridable,
                            "needs_every_component": info.needs_every_component,
                            "comparison": info.comparison,
                        }
                        for info in (*CHECKS.values(), *plugins)
                    ]
                )
            ),
        )

    def _edit(self, query: NoQuery, body: contract.Changes) -> Reply:
        try:
            within_depth(body.changes)
            at, wrote = self.session.edit([_file_change(c) for c in body.changes], body.label)
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        # Answered once written, before its analysis: the edit's own number is what says when a
        # revision includes it.
        return Reply(
            200,
            written(
                contract.EditReply(
                    edit=at,
                    files=[
                        {"path": file.path.as_posix(), "fingerprint": file.fingerprint}
                        for file in wrote
                    ],
                )
            ),
        )

    def _undo(self, query: NoQuery, body: None) -> Reply:
        """What putting the last edit back would give each file, read from the disk as it
        stands."""
        revision = self._opened()
        top = self.session.undoable
        if top is None:
            return _error(404, "not-found", "no edit of this session is left to undo")
        try:
            changes = _undone_changes(top)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.UndoPreview(
                    revision=revision.number, at=top.at, label=top.label, changes=changes
                )
            ),
        )

    def _apply_undo(self, query: NoQuery, body: contract.UndoRequest) -> Reply:
        """Put that edit back, and answer the number the undo took, once the files are back -
        before its analysis."""
        try:
            number = self.session.undo(body.at)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(200, written(contract.UndoReply(edit=number)))

    def _variable(self, query: VariableQuery, body: None) -> Reply:
        revision = self._opened()
        name = query.name
        built = revision.index
        cache: dict[Path, Document] = {}
        declared = () if built is None else declarations_of(built, name, cache)
        if built is None or not declared:
            return _undeclared(revision, name)
        derived = self._derive(revision)
        return Reply(
            200,
            written(
                contract.VariableReply(
                    revision=revision.number,
                    name=name,
                    declarations=[
                        {
                            "path": derived.resolve(entry.site.path).as_posix(),
                            "pointer": entry.site.pointer,
                            "component": entry.component,
                            "role": entry.role,
                            "stated": dict(entry.stated),
                            "type": entry.type_name,
                            "fixed": dict(entry.fixed),
                        }
                        for entry in declared
                    ],
                    # The dataclasses of `ddd.variable_keys` are the contract's models field for
                    # field; the contract validates what comes out, so a name that drifts apart
                    # fails here rather than reaching the page.
                    keys=[asdict(offer) for offer in offers(built, declared)],
                    findings=_listed(
                        derived,
                        [
                            (file, found)
                            for file, found in derived.findings.on_any(
                                entry.site.path for entry in declared
                            )
                            if located_on(declared, file, found, derived.resolve)
                        ],
                        cache,
                    ),
                )
            ),
        )

    def _units(self, query: NoQuery, body: None) -> Reply:
        """The vocabulary, the units in use, the Units tab's rows and whether adopting is offered.

        Answered anew each time, never kept (:meth:`_memoised`): the offer reads the disk as it
        stands - the includes expanded to find the units files, and whether ``units.ddd.json``
        is there beside the description - which no revision records: neither a file appearing
        where a pattern matches nor one no include names starts an analysis. Read only where the
        offer can depend on it (:func:`ddd.project_units.adoptable`): a project holding a
        vocabulary already is refused adopting by its index alone, and its includes are not
        expanded at all."""
        revision = self._opened()
        cache: dict[Path, Document] = {}
        vocabulary = vocabulary_of(
            [read(file.path, cache) for file in revision.files if file.kind == "units"]
        )
        built = revision.index
        unread = [file.path for file in revision.files if not file.loaded]

        def project() -> UnitProject:
            # The project `_unit_plan` makes its plans in, built the same way: the offer asks the
            # plan's own guards of it, so an Adopt this answers is one the plan will not refuse.
            return unit_project(revision.project, unread, cache)

        used = () if built is None else units_in_use(built)
        derived = self._derive(revision)
        rows = () if built is None else unit_rows(built, derived.findings, cache)
        return Reply(
            200,
            written(
                contract.UnitsReply(
                    revision=revision.number,
                    vocabulary=None
                    if vocabulary is None
                    else [{"unit": unit, "description": text} for unit, text in vocabulary],
                    used=[{"unit": unit, "variables": count} for unit, count in used],
                    units=[
                        {
                            "unit": row.unit,
                            "description": row.description,
                            "files": [derived.resolve(path).as_posix() for path in row.files],
                            "variables": row.variables,
                            "types": row.types,
                            "members": row.members,
                            "findings": row.findings,
                        }
                        for row in rows
                    ],
                    adoptable=adoptable(built, project),
                )
            ),
        )

    def _unit(self, query: UnitQuery, body: None) -> Reply:
        revision = self._opened()
        unit = query.name
        built = revision.index
        if built is None or (unit not in built.units and unit not in built.vocabulary):
            return _undeclared(revision, unit)
        cache: dict[Path, Document] = {}
        # Its description is read where the index recorded it listed: no neighbour's (`listed_in_
        # place`), answered as a unit no unchanged file declares until the analysis reads it again.
        if not listed_in_place(built, unit, cache):
            return _undeclared(revision, unit)
        derived = self._derive(revision)
        return Reply(
            200,
            written(
                contract.UnitReply(
                    revision=revision.number,
                    unit=unit,
                    description=description_of(built, unit, cache),
                    entries=[
                        {"file": derived.resolve(entry.path).as_posix(), "pointer": entry.pointer}
                        for entry in built.vocabulary.get(unit, ())
                    ],
                    sites=[
                        {
                            "path": derived.resolve(place.stated.site.path).as_posix(),
                            "pointer": place.stated.site.pointer,
                            "kind": place.stated.kind,
                            "name": place.stated.name,
                            "component": place.component,
                            "role": place.role,
                        }
                        for place in places_of(built, unit, cache, _changed_in(derived))
                    ],
                    findings=_listed(derived, unit_findings(built, unit, derived.findings), cache),
                )
            ),
        )

    def _unit_plan(self, query: UnitPlanQuery, body: None) -> Reply:
        revision = self._opened()
        built = revision.index
        if built is None:
            unread = [file.path.name for file in revision.files if not file.loaded]
            return _error(
                409,
                UNREADABLE,
                f"{', '.join(unread) or revision.project.name} did not load, "
                "so no unit of the project can be changed",
            )
        cache: dict[Path, Document] = {}
        project = unit_project(
            revision.project, [file.path for file in revision.files if not file.loaded], cache
        )
        try:
            plan = _unit_plan_of(query.root, built, project, cache)
        except UnitRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _types(self, query: NoQuery, body: None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("types",), lambda: self._types_of(revision))

    def _types_of(self, revision: Revision) -> Reply:
        built = revision.index
        cache: dict[Path, Document] = {}
        rows = () if built is None else type_rows(built, self._derive(revision).findings, cache)
        return Reply(
            200,
            written(
                contract.TypesReply(
                    revision=revision.number,
                    types=[
                        {
                            "name": row.name,
                            "kind": row.kind,
                            "description": row.description,
                            "uses": row.uses,
                            "findings": row.findings,
                        }
                        for row in rows
                    ],
                )
            ),
        )

    def _type(self, query: TypeQuery, body: None) -> Reply:
        revision = self._opened()
        name = query.name
        built = revision.index
        if built is None or name not in built.types:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        # Every key below is read where the index recorded the type: none of a neighbour's
        # (`type_in_place`), answered as a type no unchanged file declares until the analysis
        # reads its file again.
        if not type_in_place(built, name, cache):
            return _undeclared(revision, name)
        site = built.types[name]
        derived = self._derive(revision)
        row = row_of(built, name, derived.findings, cache)
        stated = fixed_by(built, name, cache)
        header = stated.get("header")
        return Reply(
            200,
            written(
                contract.TypeReply(
                    revision=revision.number,
                    name=name,
                    kind=row.kind,
                    file=derived.resolve(site.path).as_posix(),
                    pointer=site.pointer,
                    description=row.description,
                    header=None if header is None else json.loads(header),
                    keys=[
                        asdict(offer_for(built, key, stated.get(key), required=key in REQUIRED))
                        for key in SCALAR_KEYS
                    ]
                    if row.kind == "scalar"
                    else [],
                    uses=[
                        {
                            "path": derived.resolve(use.site.path).as_posix(),
                            "pointer": use.site.pointer,
                            "kind": use.kind,
                            "name": use.name,
                            "component": use.component,
                            "role": use.role,
                        }
                        for use in uses_of(built, name, cache)
                    ],
                    members=[
                        {
                            "name": member["name"],
                            "member": member["member"],
                            "typename": member.get("typename"),
                            "datatype": member.get("datatype"),
                            "unit": member.get("unit"),
                            "bits": member.get("bits"),
                            "dimensions": member.get("dimensions", ()),
                        }
                        for member in members_of(built, name, cache)
                    ],
                    findings=_listed(derived, type_findings(built, name, derived.findings), cache),
                )
            ),
        )

    def _type_plan(self, query: TypePlanQuery, body: None) -> Reply:
        revision = self._opened()
        built = revision.index
        if built is None:
            unread = [file.path.name for file in revision.files if not file.loaded]
            return _error(
                409,
                UNREADABLE,
                f"{', '.join(unread) or revision.project.name} did not load, "
                "so no type of the project can be changed",
            )
        cache: dict[Path, Document] = {}
        try:
            plan = _type_plan_of(query.root, built, cache)
        except TypeRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _shared(self, query: NoQuery, body: None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("shared",), lambda: self._shared_of(revision))

    def _shared_of(self, revision: Revision) -> Reply:
        built = revision.index
        cache: dict[Path, Document] = {}
        rows = () if built is None else shared_rows(built, self._derive(revision).findings, cache)
        return Reply(
            200,
            written(
                contract.SharedReply(
                    revision=revision.number,
                    entries=[
                        {
                            "kind": row.kind,
                            "name": row.name,
                            "states": row.states,
                            "uses": row.uses,
                            "findings": row.findings,
                        }
                        for row in rows
                    ],
                )
            ),
        )

    def _constant(self, query: ConstantQuery, body: None) -> Reply:
        revision = self._opened()
        name = query.name
        built = revision.index
        if built is None or name not in built.constants:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        # Its keys are read where the index recorded the entry: none of a neighbour's
        # (`entry_in_place`), answered as an entry no unchanged file declares until the analysis
        # reads its file again.
        if not entry_in_place(CONSTANTS, built, name, cache):
            return _undeclared(revision, name)
        site = built.constants[name]
        derived = self._derive(revision)
        # The whole entry's display texts in one read, through the descriptor: `value` as the json
        # text its file spells and `description` as the string it holds, which is what
        # `CONSTANTS.strings` says of each. The panel names its keys because the reply does; a
        # vocabulary's own keys are the descriptor's business, not this route's.
        texts = shown(CONSTANTS, built, name, cache)
        return Reply(
            200,
            written(
                contract.ConstantReply(
                    revision=revision.number,
                    name=name,
                    value=texts["value"],
                    description=texts["description"],
                    file=derived.resolve(site.path).as_posix(),
                    pointer=site.pointer,
                    uses=_entry_uses(CONSTANTS, derived, built, name, cache),
                    findings=_entry_findings(CONSTANTS, derived, built, name, cache),
                )
            ),
        )

    def _section(self, query: SectionQuery, body: None) -> Reply:
        revision = self._opened()
        name = query.name
        built = revision.index
        if built is None or name not in built.sections:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        # As a constant's: none of a neighbour's keys under this entry's name.
        if not entry_in_place(SECTIONS, built, name, cache):
            return _undeclared(revision, name)
        site = built.sections[name]
        derived = self._derive(revision)
        texts = shown(SECTIONS, built, name, cache)
        return Reply(
            200,
            written(
                contract.SectionReply(
                    revision=revision.number,
                    name=name,
                    access=texts["access"],
                    alignment=texts["alignment"],
                    description=texts["description"],
                    file=derived.resolve(site.path).as_posix(),
                    pointer=site.pointer,
                    uses=_entry_uses(SECTIONS, derived, built, name, cache),
                    findings=_entry_findings(SECTIONS, derived, built, name, cache),
                )
            ),
        )

    def _raster(self, query: RasterQuery, body: None) -> Reply:
        revision = self._opened()
        name = query.name
        built = revision.index
        if built is None or name not in built.rasters:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        # As a constant's: none of a neighbour's keys under this entry's name.
        if not entry_in_place(RASTERS, built, name, cache):
            return _undeclared(revision, name)
        site = built.rasters[name]
        derived = self._derive(revision)
        texts = shown(RASTERS, built, name, cache)
        return Reply(
            200,
            written(
                contract.RasterReply(
                    revision=revision.number,
                    name=name,
                    event=texts["event"],
                    cycle=texts["cycle"],
                    description=texts["description"],
                    file=derived.resolve(site.path).as_posix(),
                    pointer=site.pointer,
                    uses=_entry_uses(RASTERS, derived, built, name, cache),
                    findings=_entry_findings(RASTERS, derived, built, name, cache),
                )
            ),
        )

    def _files(self, query: NoQuery, body: None) -> Reply:
        """The root's includes, each entry as the loader's own rule reads it, and what each
        brings - the files a row joins ``State.files`` on, and the findings at the entry
        itself, which a row naming nothing has no file to carry.

        Answered anew each time, never kept (:meth:`_memoised`): the includes are expanded on
        disk as it stands, which no revision records - a file appearing where a pattern matches
        starts no analysis. At a cost while an analysis runs: over a generated project of 100,000
        declarations, whose one pattern reaches 1,681 files, the request took 1,872 to 2,602 ms
        asked halfway through an analysis and 24 ms otherwise, 141 ms the first time; listing
        that directory alone took 1,028 to 1,487 ms and under a millisecond - three askings
        each, on the Linux development PC. Kept for a revision and the session's edits instead,
        it would list a file saved where a pattern matches only once something else changed,
        and still be made again after every edit - when the Files tab asks for it again, its
        own Apply written."""
        revision = self._opened()
        at_entry = self._derive(revision).at_entry
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            written(
                contract.FilesReply(
                    revision=revision.number,
                    project=revision.project.as_posix(),
                    entries=[
                        {
                            "index": entry.index,
                            "entry": entry.entry,
                            "names": entry.names,
                            "key": entry.key.as_posix(),
                            "files": [file.as_posix() for file in entry.files],
                            "findings": at_entry.get(entry.index, 0),
                        }
                        for entry in included_entries(revision.project, cache)
                    ],
                    creatable=CREATABLE,
                )
            ),
        )

    def _files_plan(self, query: FilesPlanQuery, body: None) -> Reply:
        """One change of the project's files - creating, adding or removing one - previewed and
        never written, with the errors an add is counted to bring.

        Its query read as :class:`~ddd.gui.queries.FilesPlanQuery` before anything else, a key to
        remove that is not absolute refused there, as a row's never is: read against the server's
        own working directory, a relative one named another file. Past that, each refusal is the
        plan's own or :func:`_addition`'s and :func:`_removal`'s, in the order they ask them,
        ``not-found`` answered 404 and every other 409; a judgement a file saved or come since the
        revision would falsify is refused ``stale``.
        """
        revision = self._opened()
        cache: dict[Path, Document] = {}

        def refuse(paths: Iterable[Path]) -> None:
            self._refuse_unanalysed(revision, paths)

        try:
            plan = _files_plan_of(query.root, revision, cache, refuse)
        except FileRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        derived = self._derive(revision)
        try:
            made = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.FilesPlanReply(
                    revision=revision.number,
                    changes=_planned_changes(revision, derived, made),
                    unjudged=plan.unjudged,
                    brings=[
                        {"file": path.as_posix(), "check": found.check, "message": found.message}
                        for path, found in plan.brings
                    ],
                    kept_by=plan.kept_by,
                )
            ),
        )

    def _constant_plan(self, query: ConstantPlanQuery, body: None) -> Reply:
        return self._shared_plan(CONSTANTS, query.root, _constant_plan_of)

    def _section_plan(self, query: SectionPlanQuery, body: None) -> Reply:
        return self._shared_plan(SECTIONS, query.root, _section_plan_of)

    def _raster_plan(self, query: RasterPlanQuery, body: None) -> Reply:
        return self._shared_plan(RASTERS, query.root, _raster_plan_of)

    def _shared_plan[A](self, vocabulary: Vocabulary, asked: A, plan_of: SharedPlanner[A]) -> Reply:
        """One change of one entry of ``vocabulary``, ``asked`` as its route's query read it,
        previewed and never written.

        Written once for the three endpoints rather than three times: they differ in the actions
        their queries take, the verb each action reaches and the noun a refusal names, all of
        which arrive as arguments - everything else here is about the revision, which a second
        copy would only be able to get wrong differently. Every part that has to be json - a
        ``?raw=``, and each value an ``add`` declares - was read as json text by the query, before
        anything asked for the project: a request that is not json is a mistake about the
        request, not a refusal about the project, so it answers 400 rather than being folded into
        a :class:`~ddd.shared_plans.SharedRefusalError`.
        """
        revision = self._opened()
        built = revision.index
        if built is None:
            unread = [file.path.name for file in revision.files if not file.loaded]
            return _error(
                409,
                UNREADABLE,
                f"{', '.join(unread) or revision.project.name} did not load, "
                f"so no {vocabulary.kind} of the project can be changed",
            )
        cache: dict[Path, Document] = {}
        project = project_of(
            vocabulary,
            revision.project,
            [file.path for file in revision.files if not file.loaded],
            cache,
        )
        try:
            plan = plan_of(asked, built, project, cache)
        except SharedRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            made = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, made)
                )
            ),
        )

    def _settle(self, query: SettleQuery, body: None) -> Reply:
        revision = self._opened()
        # ``raw`` is none where it was left out or given blank: the key goes from every
        # declaration.
        name, key, raw = query.name, query.key, query.raw
        built = revision.index
        if built is None or name not in built.declarations:
            return _undeclared(revision, name)
        # One cache for both reads below, so a declaration `settle` already read for this
        # request is not read from disk a second time to narrow what it comes to.
        cache: dict[Path, Document] = {}
        settlement = settle(built, name, key, raw, cache)
        if settlement.unsettled:
            code, message = refusal(settlement.unsettled[0], name, key)
            return _error(409, code, message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (change.site.path for change in settlement.changes))
            planned = preview(settlement, key, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.SettleReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _fix(self, query: FixQuery, body: None) -> Reply:
        revision = self._opened()
        file, pointer, check = query.file, query.pointer, query.check
        wanted = resolve_path(Path(file))
        derived = self._derive(revision)
        source = next((f for f in revision.files if derived.resolve(f.path) == wanted), None)
        if source is None:
            return _error(404, "not-found", f"{file} is not a file of the open project")
        cache: dict[Path, Document] = {}
        built = revision.index
        if built is None:
            # No index, no declarations - a revision whose project did not load has nothing to
            # reconcile, and answering no fixes is truer than answering an error.
            built = Index()
        offered = []
        for fix in fixes_for(check, source.path, pointer, cache, built):
            try:
                self._refuse_unanalysed(revision, (edit.path for edit in fix.changes))
                made = [planned(edit.path, edit.operations, derived.stamps) for edit in fix.changes]
            except EditError as refused:
                return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
            offered.append(
                {"title": fix.title, "changes": _planned_changes(revision, derived, made)}
            )
        return Reply(
            200,
            written(contract.FixReply(revision=revision.number, fixes=offered)),
        )

    def _declarable(self, query: DeclarableQuery, body: None) -> Reply:
        revision = self._opened()
        try:
            file = _source(revision, Path(query.file))
        except NotInProjectError as outside:
            return _error(404, "not-found", str(outside))
        built = revision.index
        if built is None:
            return _error(409, UNREADABLE, _NOTHING_LOADED)
        if not any(entry.path == file and entry.kind == "component" for entry in revision.files):
            return _error(409, "invalid", f"{file.name} is not a component of the open project")
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            written(
                contract.DeclarableReply(
                    revision=revision.number,
                    file=file.as_posix(),
                    names=tuple(
                        contract.DeclarableName(
                            name=entry.name,
                            kind=entry.kind,
                            producer=entry.producer,
                            scopes=scopes_for(built, entry.name),
                        )
                        for entry in declarable(built, file, cache)
                    ),
                    kinds=tuple(
                        # `asdict`, exactly as `_variable` already converts its offers: the
                        # dataclasses of `ddd.variable_keys` are the contract's models field for
                        # field, and the contract validates what comes out, so a name that drifts
                        # apart fails here rather than reaching the page.
                        contract.KindForm(
                            kind=kind, keys=[asdict(offer) for offer in form_for(built, kind)]
                        )
                        for kind in KINDS
                    ),
                    scopes=SCOPES,
                    constants=tuple(sorted(built.constants)),
                )
            ),
        )

    def _declaration_plan(self, query: DeclarationPlanQuery, body: None) -> Reply:
        asked = query.root
        revision = self._opened()
        try:
            file = _source(revision, Path(asked.file))
        except NotInProjectError as outside:
            return _error(404, "not-found", str(outside))
        built = revision.index
        if built is None:
            return _error(409, UNREADABLE, _NOTHING_LOADED)
        cache: dict[Path, Document] = {}
        try:
            plan = _declaration_plan_of(asked, built, file, cache)
        except DeclarationRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _values(self, query: ValuesQuery, body: None) -> Reply:
        name = query.name
        revision = self._opened()
        built, dictionary = revision.index, revision.dictionary
        if built is None or dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_RESOLVED)
        try:
            grid = grid_of(dictionary, built, name)
        except ValueRefusalError as refused:
            # Both codes are reachable - a name the project has not, and a shape of more
            # dimensions than a grid draws - so both arms need a status and a test reaching
            # them. An `if`/`else` rather than a ternary: a conditional expression registers
            # no branch at all with coverage.py, which is how an untested arm hid here before.
            if refused.code == "not-found":
                return _error(404, refused.code, refused.message)
            return _error(409, refused.code, refused.message)
        derived = self._derive(revision)
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            written(
                contract.ValuesReply(
                    revision=revision.number,
                    name=grid.name,
                    kind=grid.kind,
                    datatype=grid.datatype,
                    unit=grid.unit,
                    conversion=written(grid.conversion),
                    minimum=grid.minimum,
                    maximum=grid.maximum,
                    shape=grid.shape,
                    rows=grid.rows,
                    stated=grid.stated,
                    axes=[
                        {
                            "position": axis.position,
                            "name": axis.name,
                            "unit": axis.unit,
                            "breakpoints": axis.breakpoints,
                            "conversion": written(axis.conversion),
                        }
                        for axis in grid.axes
                    ],
                    owner=grid.owner,
                    file=grid.file,
                    findings=_listed(derived, _grid_findings(derived, grid), cache),
                )
            ),
        )

    def _value_plan(self, query: ValuePlanQuery, body: None) -> Reply:
        revision = self._opened()
        built, dictionary = revision.index, revision.dictionary
        if built is None or dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_RESOLVED)
        try:
            raw = _number(query.raw)
            plan = set_cell(dictionary, built, query.name, query.at, raw, {})
        except ValueRefusalError as refused:
            # Both codes again, as in _values above - a name the project has not, and every
            # other refusal - so both arms need a status and a test reaching them: a ternary
            # here would read the same but hide an untested arm from the coverage gate, the
            # same blind spot that let two earlier defects through.
            if refused.code == "not-found":
                return _error(404, refused.code, refused.message)
            return _error(409, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _values_plan(self, query: ValuesPlanQuery, body: None) -> Reply:
        name = query.name
        revision = self._opened()
        built, dictionary = revision.index, revision.dictionary
        if built is None or dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_RESOLVED)
        try:
            flat = [_number(piece) for piece in query.raw.split(",")]
            plan = set_values(dictionary, built, name, _folded(flat, dictionary, name))
        except ValueRefusalError as refused:
            # Both codes, as `_value_plan` above: a name the project has not, and every other
            # refusal. A statement rather than a ternary, so the gate can see both arms.
            if refused.code == "not-found":
                return _error(404, refused.code, refused.message)
            return _error(409, refused.code, refused.message)
        derived = self._derive(revision)
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, derived.stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            written(
                contract.PlanReply(
                    revision=revision.number, changes=_planned_changes(revision, derived, planned)
                )
            ),
        )

    def _compare(self, query: CompareQuery, body: None) -> Reply:
        revision = self._opened()
        if revision.dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_COMPARABLE)
        try:
            result = compared(
                revision, Path(query.baseline), self.session.root, self._compare_cache
            )
        except BaselineRefusedError as refused:
            return _error(400, "bad-request", str(refused))
        derived = self._derive(revision)
        cache: dict[Path, Document] = {}
        findings = sorted(result.findings, key=lambda filed: filed.file.as_posix())
        baseline_findings = sorted(
            result.baseline_findings, key=lambda filed: filed.file.as_posix()
        )
        return Reply(
            200,
            written(
                contract.CompareReply(
                    revision=revision.number,
                    verdict=result.verdict,
                    findings=[
                        _finding(filed, derived.files.get(derived.resolve(filed.file)), cache)
                        for filed in findings
                    ],
                    # Never a source for one of these, whatever file it resolves to: a baseline
                    # given as a project description can share files, ids and even paths with the
                    # open project, so being carried in this field rather than `findings` is what
                    # marks a finding as the baseline's - not a test of where it happens to sit,
                    # which answered this wrong for a baseline that was also a file of the open
                    # project. Two fields on the wire, mirroring `Compared`'s own two, rather than
                    # one merged list a reader would have to tell apart by matching the
                    # "in the baseline: " a message happens to carry -
                    # `CompareReply.baseline_findings`' own docstring is what that matching would be
                    # re-deriving, unreliably, from text a page does not own.
                    baseline_findings=[_finding(filed, None, cache) for filed in baseline_findings],
                    renames=[
                        {"id": entry["id"], "old": entry["from"], "new": entry["to"]}
                        for entry in result.renames
                    ],
                )
            ),
        )

    def _opened(self) -> Revision:
        """The open project's newest revision, or the refusal :meth:`handle` answers: no project
        open, or none of its analyses landed yet."""
        return self.session.current()

    def _refuse_unanalysed(self, revision: Revision, paths: Iterable[Path]) -> None:
        """Refuse a plan changing a file an edit wrote since ``revision``'s analysis began.

        Computed all the same, it would carry the fingerprint the analysis read that file at, and
        the edit engine would refuse its Apply as stale; and where it points into the file comes
        from an index of bytes no longer on disk. A plan changing only files nobody wrote since is
        made against ``revision`` at once, never waiting for the analysis (spec §5)."""
        waiting = self.session.unanalysed(revision)
        derived = self._derive(revision)
        named: list[str] = []
        for path in paths:
            resolved = derived.resolve(path)
            if resolved in waiting and resolved.name not in named:
                named.append(resolved.name)
        if named:
            raise EditError(
                ANALYSING,
                f"an edit that wrote {', '.join(named)} has not been analysed yet, "
                "so this change can be planned once it has",
            )

    def _derive(self, revision: Revision) -> Derived:
        """What the api derives from ``revision`` (:func:`ddd.gui.derived.derived`): the one kept
        where it is that revision's, else derived now and kept in place of an older revision's,
        the answers :meth:`_memoised` kept beside the last one emptied with it.

        Once per revision: derived behind a lock of its own, never the session's, so that a
        request of a revision another is deriving waits for that derivation and answers from it,
        rather than deriving it again beside it - the page's first requests of a revision each
        derived it, six at once each the slower for the five beside it. A request still holding a
        revision older than the one kept derives its own and keeps nothing, so that the newer
        revision's derivation and kept answers stay. Each answer is made from the revision its
        own request holds."""
        kept = self._derived
        if kept is not None and kept.number == revision.number:
            return kept
        with self._deriving:
            kept = self._derived
            if kept is not None and kept.number == revision.number:
                return kept
            made = derived(revision)
            if kept is None or kept.number < revision.number:
                self._derived = made
                self._memo = OrderedDict()
            return made

    def _memoised(
        self, revision: Revision, key: tuple[object, ...], make: Callable[[], Reply]
    ) -> Reply:
        """The answer ``key`` names - ``("graph",)``, ``("types",)`` - for ``revision``, made by
        ``make`` once and kept beside what :meth:`_derive` keeps for the newest revision, emptied
        with it.

        Kept only where all it reads is the revision and the files the revision read: a save to
        one of those is what the poll notices, making a new revision, so the revision's number
        says when the answer has gone stale. The Files and the Units tabs are not kept for that
        reason: both expand the includes on disk as it stands, which no revision records, and a
        file appearing where a pattern matches starts no analysis.

        Keyed by the edits the session has written as well as by the revision: an edit is written
        at once and answered then, its analysis following, so an answer reading its files as they
        stand - a type's description - changes before the revision does, which the count of
        edits covers, an undo's as well, each taking a number of its own.

        At most :data:`MEMO` answers are kept, the one kept longest dropped first: a reader of a
        findings-heavy project scrolling through its Findings tab asks a page per hundred
        findings, every one of them a new answer.

        Not guarded: requests are answered on threads of their own. Two requests of one revision
        that both find nothing kept both make it, and an answer made for a revision a newer one
        has since replaced can be kept beside the newer revision's - under its own revision's
        number, so it answers for no other, and goes at the next derivation. Each answer stays
        what it would be; only work is repeated, where a lock around the making would hold every
        other request for a kept answer behind the one being made. Dropping is one call no other
        thread interrupts, :meth:`collections.OrderedDict.popitem`: requests dropping at once can
        leave fewer answers kept than the bound, and never fail.
        """
        self._derive(revision)
        keyed = (key, revision.number, self.session.edits)
        kept = self._memo.get(keyed)
        if kept is None:
            kept = make()
            memo = self._memo
            memo[keyed] = kept
            while len(memo) > MEMO:
                memo.popitem(last=False)
        return kept

    def _session_body(self) -> dict[str, Any]:
        """The session's answer: the project open named from its description as it stands, so
        that a project being analysed is named at once; the builds its newest revision ran,
        none before its first.

        One snapshot for both, so that the project and the revision are read at one moment."""
        snapshot = self.session.snapshot()
        project = None
        if snapshot.project is not None:
            name = _name_in(_read_json(snapshot.project), "project")
            project = {"path": snapshot.project.as_posix(), "name": name}
        revision = snapshot.revision
        return written(
            contract.SessionInfo(
                version=__version__,
                preview=True,
                root=self.session.root.as_posix(),
                project=project,
                builds=[]
                if revision is None
                else [
                    {"image": info.image, "strict": info.strict, "severity": info.severity}
                    for info in revision.builds
                ],
            )
        )


ROUTES: Final[tuple[Route, ...]] = (
    Route("/api/session", "GET", NoQuery, None, Api._session),
    Route("/api/projects", "GET", NoQuery, None, Api._projects),
    Route(
        "/api/open",
        "POST",
        NoQuery,
        contract.OpenRequest,
        Api._open,
        Policy(opens=True, runs_plugins=True),
    ),
    Route("/api/state", "GET", StateQuery, None, Api._state, Policy(waits=True)),
    Route("/api/findings", "GET", FindingsQuery, None, Api._findings),
    Route("/api/file", "GET", FileQuery, None, Api._file),
    Route("/api/dictionary", "GET", NoQuery, None, Api._dictionary),
    Route("/api/graph", "GET", NoQuery, None, Api._graph),
    Route("/api/checks", "GET", NoQuery, None, Api._checks),
    Route(
        "/api/edit",
        "POST",
        NoQuery,
        contract.Changes,
        Api._edit,
        Policy(writes=True, runs_plugins=True),
    ),
    Route("/api/undo", "GET", NoQuery, None, Api._undo),
    Route(
        "/api/undo",
        "POST",
        NoQuery,
        contract.UndoRequest,
        Api._apply_undo,
        Policy(writes=True, runs_plugins=True),
    ),
    Route("/api/variable", "GET", VariableQuery, None, Api._variable),
    Route("/api/units", "GET", NoQuery, None, Api._units),
    Route("/api/settle", "GET", SettleQuery, None, Api._settle),
    Route("/api/fix", "GET", FixQuery, None, Api._fix),
    Route("/api/unit", "GET", UnitQuery, None, Api._unit),
    Route("/api/unit-plan", "GET", UnitPlanQuery, None, Api._unit_plan),
    Route("/api/types", "GET", NoQuery, None, Api._types),
    Route("/api/type", "GET", TypeQuery, None, Api._type),
    Route("/api/type-plan", "GET", TypePlanQuery, None, Api._type_plan),
    Route("/api/shared", "GET", NoQuery, None, Api._shared),
    Route("/api/constant", "GET", ConstantQuery, None, Api._constant),
    Route("/api/constant-plan", "GET", ConstantPlanQuery, None, Api._constant_plan),
    Route("/api/section", "GET", SectionQuery, None, Api._section),
    Route("/api/section-plan", "GET", SectionPlanQuery, None, Api._section_plan),
    Route("/api/raster", "GET", RasterQuery, None, Api._raster),
    Route("/api/raster-plan", "GET", RasterPlanQuery, None, Api._raster_plan),
    Route("/api/files", "GET", NoQuery, None, Api._files),
    Route(
        "/api/files-plan", "GET", FilesPlanQuery, None, Api._files_plan, Policy(runs_plugins=True)
    ),
    Route("/api/declarable", "GET", DeclarableQuery, None, Api._declarable),
    Route("/api/declaration-plan", "GET", DeclarationPlanQuery, None, Api._declaration_plan),
    Route("/api/values", "GET", ValuesQuery, None, Api._values),
    Route("/api/value-plan", "GET", ValuePlanQuery, None, Api._value_plan),
    Route("/api/values-plan", "GET", ValuesPlanQuery, None, Api._values_plan),
    Route("/api/compare", "GET", CompareQuery, None, Api._compare, Policy(runs_plugins=True)),
)
"""Every route of the api, in one table: what :meth:`Api.handle` dispatches by, its query read
as the route's own model and its body as its own before its handler is asked."""


def _error(status: int, code: str, message: str) -> Reply:
    return Reply(status, {"error": code, "message": message})


def _finding(
    filed: Filed, source: SourceFile | None, cache: dict[Path, Document]
) -> dict[str, Any]:
    """One finding as the page reads it, with where it leads.

    ``source`` is the analysis's own record of the file the finding is filed on, or ``None``
    for a finding filed on a file the analysis did not list - which leads nowhere, having no
    kind to route by.
    """
    # Kept as a function, unlike the answers _state/_checks/_session_body now build inline:
    # tests/test_gui_api.py imports it directly to check a note with no place is carried
    # without one.
    finding = filed.diagnostic
    return written(
        contract.Finding(
            file=filed.file.as_posix(),
            check=finding.check,
            severity=finding.severity,
            message=finding.message,
            pointer="" if finding.location is None else finding.location.pointer,
            notes=[
                {
                    "message": text,
                    "file": None if note is None else note.path.as_posix(),
                    "pointer": "" if note is None else note.pointer,
                }
                for text, note in finding.notes
            ],
            route=None
            if source is None
            else _route(
                route_of(
                    finding.check,
                    filed.file,
                    "" if finding.location is None else finding.location.pointer,
                    source.kind,
                    source.loaded,
                    cache,
                )
            ),
        )
    )


def _route(route: FindingRoute | None) -> dict[str, Any] | None:
    return None if route is None else {"kind": route.kind, "name": route.name}


def _module(file: SourceFile) -> Module:
    """A file of the revision, as the graph wants it: named by its component, or by the file's
    own stem when it did not load that far."""
    stem = file.path.name.removesuffix(".ddd.json")
    return Module(
        PurePosixPath(file.path.as_posix()),
        file.name if file.loaded and file.name else stem,
        file.loaded,
        file.errors,
        file.warnings,
        file.infos,
    )


def _undeclared(revision: Revision, name: str) -> Reply:
    """The answer about ``name`` when no declaration of it was read.

    That nothing declares it only while every file loaded, and reads now as it did at that
    analysis: a file saved half-edited, as an editor saves one being typed into, keeps the names
    only it declares out of every index until it parses again, and a page told they are not
    declared would close their panels for good (spec 5.5) rather than wait for the next save.

    A file the analysis never loaded and a file it loaded that has since changed on disk - or
    gone missing, which reads the same as changed - are two different statements: this answers
    each file the one that is true of it, never the other.
    """
    unread = [file.path.name for file in revision.files if not file.loaded]
    if unread:
        return _error(
            409,
            UNREADABLE,
            f"'{name}' is not declared in any file that loaded, "
            f"and {', '.join(unread)} did not load",
        )
    changed = [file.path.name for file in revision.files if _changed_since(file)]
    if changed:
        return _error(
            409,
            UNREADABLE,
            f"'{name}' is not declared in any file that has not changed since, "
            f"and {', '.join(changed)} changed since it was read",
        )
    return _error(404, "not-found", f"'{name}' is not declared in the open project")


def _appeared_since(revision: Revision) -> list[str]:
    """The name of every file an entry of the tree reaches now that the revision never read, each
    once: description by description in the order ``revision.files`` has them, which is by path,
    and within one in the order its entries bring them.

    Every description the revision read whose kind is ``project`` - the root, and each
    sub-project - has its entries expanded by the loader's own rule
    (:func:`ddd.file_plans.included_entries`). A file one of them reaches that the revision
    lacks appeared since: saved where a pattern matches it, or moved there. The session's poll
    compares only the files a revision read, so a new file does not start an analysis, and
    judged against a revision that never read it, an error of that file read as the change's.

    Asked beside :func:`_changed_since`, and only where a plan is judged, as that is. Sound
    there: every run of such a revision analysed the project, so every plain entry named a file
    that exists - one naming none is ``file-not-found`` - and no ``include-cycle`` or
    ``include-depth`` stood, all three errors no build lowers; so every file an entry reached
    was read. Where a run was not analysed, a file an entry reaches may never have been read,
    and nothing is judged there anyway.

    Statements in loops rather than a comprehension's filters, which coverage.py counts no branch
    in."""
    read = {file.path for file in revision.files}
    cache: dict[Path, Document] = {}
    appeared: list[str] = []
    for file in revision.files:
        if file.kind != "project":
            continue
        for entry in included_entries(file.path, cache):
            for reached in entry.files:
                if reached in read:
                    continue
                read.add(reached)
                appeared.append(reached.name)
    return appeared


def _changed_in(derived: Derived) -> Callable[[Path], bool]:
    """Whether a file no longer reads as the revision ``derived`` came from read it: one the
    revision did not read at all, or one :func:`_changed_since` finds changed - read afresh and
    fingerprinted, against the revision's own fingerprint of it."""

    def changed(path: Path) -> bool:
        source = derived.files.get(derived.resolve(path))
        return source is None or _changed_since(source)

    return changed


def _changed_since(file: SourceFile) -> bool:
    """Whether ``file`` no longer reads as the analysis found it.

    Read fresh and fingerprinted again, not compared by modification time: the same check an
    edit's own fingerprint makes. A file gone missing since cannot be read at all, which counts
    as changed rather than being guessed at either way.
    """
    try:
        data = file.path.read_bytes()
    except OSError:
        return True
    return fingerprint(data) != file.fingerprint


def _unit_plan_of(
    asked: RenameUnit | AddUnit | DescribeUnit | RemoveUnit | AdoptUnits,
    built: Index,
    project: UnitProject,
    cache: dict[Path, Document],
) -> UnitPlan:
    """The plan ``asked`` names, over the parts its model read."""
    if isinstance(asked, RenameUnit):
        return rename_unit(built, project, asked.unit, asked.to, cache)
    if isinstance(asked, AddUnit):
        return add_unit(built, project, asked.unit, cache)
    if isinstance(asked, DescribeUnit):
        return describe_unit(built, project, asked.unit, asked.description, cache)
    if isinstance(asked, RemoveUnit):
        return remove_unit(built, project, asked.unit, cache)
    return adopt_units(built, project, cache)


def _type_plan_of(
    asked: SetTypeKey | RenameType, built: Index, cache: dict[Path, Document]
) -> TypePlan:
    """The plan ``asked`` names, over the parts its model read."""
    if isinstance(asked, SetTypeKey):
        return set_key(built, asked.name, asked.key, asked.raw, cache)
    return rename_type(built, asked.name, asked.to, cache)


def _constant_plan_of(
    asked: SetConstantKey | RenameConstant | AddConstant | RemoveConstant,
    built: Index,
    project: SharedProject,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``asked`` names, over the parts its model read.

    ``project`` is unused by three of the four: only ``add`` may have to create a constants
    file, which is the one verb that needs to know where the project's constants files are.
    """
    if isinstance(asked, SetConstantKey):
        return set_entry(CONSTANTS, built, asked.name, asked.key, asked.raw, cache)
    if isinstance(asked, RenameConstant):
        return rename_entry(CONSTANTS, built, asked.name, asked.to, cache)
    if isinstance(asked, RemoveConstant):
        return remove_entry(CONSTANTS, built, asked.name, cache)
    # `description` is given too, empty, rather than left out: `add`'s form offers no description
    # and the entry it writes has always stated one, which is the byte a newly declared constant
    # is compared against.
    return add_entry(
        CONSTANTS,
        built,
        project,
        asked.name,
        {"value": asked.raw, "description": '""'},
        cache,
    )


def _section_plan_of(
    asked: SetSectionKey | RenameSection | AddSection | RemoveSection,
    built: Index,
    project: SharedProject,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``asked`` names, over the parts its model read.

    The same four verbs as :func:`_constant_plan_of`, differing only in ``add``: a section is
    declared with one json text per required key rather than a lone ``?raw=``, which is why the
    two dispatchers are written out instead of one taking the descriptor. Sharing them would mean
    either naming a constant's value ``?value=`` on the wire - a url the page already calls - or
    teaching one function which of its parameters each vocabulary spells differently, and that is
    the branch the descriptor exists to remove.
    """
    if isinstance(asked, SetSectionKey):
        return set_entry(SECTIONS, built, asked.name, asked.key, asked.raw, cache)
    if isinstance(asked, RenameSection):
        return rename_entry(SECTIONS, built, asked.name, asked.to, cache)
    if isinstance(asked, RemoveSection):
        return remove_entry(SECTIONS, built, asked.name, cache)
    declared = _declared(SECTIONS, asked.model_dump())
    return add_entry(SECTIONS, built, project, asked.name, declared, cache)


def _raster_plan_of(
    asked: SetRasterKey | RenameRaster | AddRaster | RemoveRaster,
    built: Index,
    project: SharedProject,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``asked`` names, over the parts its model read.

    The same four verbs as :func:`_section_plan_of`, and the same ``add``: one json text per key
    the model gives no default for, read off the descriptor by :func:`_declared` rather than named
    here, so the only word this function spells that its sibling does not is the vocabulary.
    """
    if isinstance(asked, SetRasterKey):
        return set_entry(RASTERS, built, asked.name, asked.key, asked.raw, cache)
    if isinstance(asked, RenameRaster):
        return rename_entry(RASTERS, built, asked.name, asked.to, cache)
    if isinstance(asked, RemoveRaster):
        return remove_entry(RASTERS, built, asked.name, cache)
    declared = _declared(RASTERS, asked.model_dump())
    return add_entry(RASTERS, built, project, asked.name, declared, cache)


def _required_keys(vocabulary: Vocabulary) -> list[str]:
    """``vocabulary``'s required keys, in the order the panel draws them.

    The order matters and is read off the one table that has one.
    :attr:`~ddd.project_shared.Vocabulary.required` is a frozenset, so it has no order of its own -
    it has whatever order the interpreter's hash seed gives it, measured to be ``access, alignment``
    under ``PYTHONHASHSEED=0`` and the reverse under ``PYTHONHASHSEED=1``.
    :attr:`~ddd.project_shared.Vocabulary.keys` is a tuple, ordered by construction and documented
    as "the order the panel draws them", so filtering it answers a question the set cannot: which
    required key comes *first*.

    Filtered rather than intersected. ``set(vocabulary.keys) & vocabulary.required`` is the same
    keys and throws the order away again, which is the whole of what this is for. ``sorted(
    vocabulary.required)`` would also be deterministic, and was what stood here first, but a sort
    exists only to undo the set's arbitrariness: it answers ``access`` before ``alignment`` because
    of the alphabet, where this answers it because that is the field a reader sees first.

    A loop and not a comprehension, for the reason :func:`ddd.project_shared.shown` gives: coverage
    counts no branch in a comprehension's filter, so a key that is *not* required - a
    ``description``, and a raster's ``cycle`` beside it - could stop being skipped and the gate
    would not say so. Nothing bounds how many a vocabulary leaves out: ``keys`` minus ``required``
    is however many the model gives a default for.

    Why the order is visible at all: both :func:`~ddd.shared_plans.add_entry` and
    :func:`~ddd.shared_plans._created` walk ``raws.items()`` and stop at the first key
    :func:`~ddd.shared_plans._judged` refuses; and a query is refused for the first of its parts
    that is not json, in the order its model declares them, which is this one
    (:class:`~ddd.gui.queries.AddSection`). So an ``add`` carrying two bad values answers about
    whichever came first. What it does *not* decide is the file:
    :func:`~ddd.shared_plans._entry_text` composes the entry in ``keys`` order whatever order
    ``raws`` arrives in.
    """
    ordered = []
    for key in vocabulary.keys:
        if key in vocabulary.required:
            ordered.append(key)
    return ordered


def _declared(vocabulary: Vocabulary, given: Mapping[str, str]) -> dict[str, str]:
    """The json text per key an ``add`` of ``vocabulary`` was given, and an empty ``description``
    beside them, in the order :func:`_required_keys` gives.

    ``description`` is appended after them rather than placed among them: it is the one key ``add``
    supplies itself, so no refusal can ever be about it and it has no business being first.
    ``test_a_declared_entry_is_built_in_the_panels_own_order`` is what pins both halves.
    """
    declared = {key: given[key] for key in _required_keys(vocabulary)}
    declared["description"] = '""'
    return declared


def _entry_uses(
    vocabulary: Vocabulary,
    derived: Derived,
    built: Index,
    name: str,
    cache: dict[Path, Document],
) -> list[dict[str, Any]]:
    """Every shape naming that entry of ``vocabulary``, as the page reads one: a constant's
    dimensions and axis sizes, a section's placements, whichever the descriptor reads."""
    return [
        {
            "path": derived.resolve(use.site.path).as_posix(),
            "pointer": use.site.pointer,
            "kind": use.kind,
            "name": use.name,
            "component": use.component,
        }
        for use in uses_of_entry(vocabulary, built, name, cache)
    ]


def _entry_findings(
    vocabulary: Vocabulary,
    derived: Derived,
    built: Index,
    name: str,
    cache: dict[Path, Document],
) -> list[dict[str, Any]]:
    """Every finding of the revision that entry of ``vocabulary`` owns: filed inside its own
    record, or at a shape naming it - a constant's dimension, a section's placement."""
    return _listed(derived, entry_findings(vocabulary, built, name, derived.findings), cache)


def _listed(
    derived: Derived, found: Iterable[Pair], cache: dict[Path, Document]
) -> list[dict[str, Any]]:
    """Findings of the revision as a panel lists them, in the order given, each with where it
    leads: its file's description looked up among the revision's own."""
    return [
        _finding(Filed(file, diagnostic), derived.files.get(derived.resolve(file)), cache)
        for file, diagnostic in found
    ]


def _grid_findings(derived: Derived, grid: Grid) -> list[Pair]:
    """The findings about a grid's own ``init``, filed at its declaration's ``definition.init``:
    asked only of the findings on the file the grid is read from, which is resolved already.
    None for a grid that not exactly one declaration produces, which has no file and no place of
    its own to hold one."""
    if grid.pointer is None or grid.file is None:
        return []
    at = f"{grid.pointer}.definition.init"
    return [
        (file, found)
        for file, found in derived.findings.on(Path(grid.file))
        if found.location is not None and found.location.pointer == at
    ]


@dataclass(frozen=True, slots=True)
class _FilesPlanned:
    """A change of the project's files as ``GET /api/files-plan`` answers it: the edits, and
    what :class:`~ddd.gui.contract.FilesPlanReply` says beside them."""

    edits: tuple[PlannedEdit, ...]
    unjudged: str | None = None
    brings: tuple[Pair, ...] = ()
    kept_by: str | None = None


def _files_plan_of(
    asked: CreateFile | AddFile | RemoveFile,
    revision: Revision,
    cache: dict[Path, Document],
    refuse: Callable[[Iterable[Path]], None],
) -> _FilesPlanned:
    """The plan ``asked`` names, over the parts its model read. A row's key is passed on as it
    arrived: :func:`ddd.file_plans.remove_plan` resolves it to compare, as
    :func:`ddd.file_plans.included_entries` made it, and names it as it was sent. Resolved here
    instead, a key ending in a link would be named by what the link leads to, which may lie
    outside what is served.

    ``refuse`` is asked of the files each plan's edits change, once the plan's own refusals have
    been asked and before anything is judged (:meth:`Api._refuse_unanalysed`): judged, a
    description an edit wrote and no analysis has read yet would be refused ``stale`` instead,
    for the very write the reader made."""
    if isinstance(asked, CreateFile):
        edits = _creation(revision, asked.kind, asked.name, asked.component, cache)
        refuse(edit.path for edit in edits)
        return _FilesPlanned(edits)
    if isinstance(asked, AddFile):
        return _addition(revision, asked.path, cache, refuse)
    return _removal(revision, Path(asked.path), cache, refuse)


def _creation(
    revision: Revision,
    kind: str,
    name: str,
    component: str | None,
    cache: dict[Path, Document],
) -> tuple[PlannedEdit, ...]:
    """A new file, planned with what the revision knows of the whole tree rather than of the
    root's own includes alone.

    ``taken`` is the name of every component of the tree - a sub-project's, and one that did
    not load, whose name is read off its file and clashes the moment it loads - since the
    analysis groups every component the workspace holds. ``checks_units`` is whether any file of
    the tree is a units file, as the loader decides a project is opted in: a project whose one
    units file is a sub-project's is, and a root file listing its units again would fail it with
    a ``duplicate-unit`` for each. Two statements in a loop rather than a comprehension's filter,
    which coverage.py counts no branch in: a component naming itself nothing takes no name."""
    taken: list[str] = []
    for file in revision.files:
        if file.kind != "component":
            continue
        if file.name is None:
            continue
        taken.append(file.name)
    units = unit_project(
        revision.project, [file.path for file in revision.files if not file.loaded], cache
    )
    return create_plan(
        revision.project,
        kind,
        name,
        component,
        taken,
        units,
        revision.index,
        cache,
        checks_units=any(file.kind == "units" for file in revision.files),
    )


def _addition(
    revision: Revision,
    entry: str,
    cache: dict[Path, Document],
    refuse: Callable[[Iterable[Path]], None],
) -> _FilesPlanned:
    """An existing file appended to the includes, and the errors it is counted to bring -
    previewed, never refused for them.

    Refused, in this order: a file outside what the session serves, decided by
    :func:`ddd.gui.session._served` itself so that adding a file and reading it never disagree;
    then :func:`ddd.file_plans.add_plan`'s own, which the disk and the description answer;
    then a file :func:`ddd.gui.session.kind_of` - the rule ``State.files`` shows a kind by -
    finds no kind of description in: a python file, which a project names among its plugins,
    or one the loader could not read as a description of any kind; then by ``refuse``, a
    description an edit wrote that no analysis has read yet.

    Judged where every run of the revision analysed the project, and otherwise answered with
    the sentence saying why it could not be, true of both ways a run stops short: its read
    reporting an error, or a plugin raising.

    Counted as a removal's judgement is, by :func:`ddd.file_plans.new_errors`: the errors the
    project would have more of at their places. So an error the file brings to a place where
    one of its check and severity sits now, which that one leaves, is not listed - measured:
    added, a writer owning a variable, its name sorting first, turns a reader's disagreement
    with the old owner over its unit into one with the new owner over its datatype, and only
    the writers' own conflict and disagreement are listed. The bound holds as it does for a
    removal: a project with no errors is never answered that an add bringing one brings none."""
    added = resolve_path(revision.project.parent / entry)
    try:
        _served(revision, added)
    except NotInProjectError:
        serves = (directory.as_posix() for directory in revision.served)
        raise FileRefusalError("invalid", outside_served(entry, serves)) from None
    plan = add_plan(revision.project, entry, cache)
    kind = kind_of(added, _read_json(added))
    if kind == "plugin":
        raise FileRefusalError(
            "invalid",
            f"{entry} is a python file, which a project names among its plugins rather than its "
            "includes",
        )
    if kind == "unknown":
        raise FileRefusalError(
            "invalid",
            f"{entry} is no kind of file a project includes: it cannot be read as json, or its "
            f"top level holds none of {', '.join(DESCRIPTION_KINDS[:-1])} and "
            f"{DESCRIPTION_KINDS[-1]}",
        )
    refuse(edit.path for edit in plan.edits)
    if not revision.analysed:
        return _FilesPlanned(
            plan.edits,
            unjudged=f"not every analysis of this project ran to its end, so what adding {entry} "
            "brings cannot be judged",
        )
    return _FilesPlanned(plan.edits, brings=_judged(revision, plan.includes))


def _removal(
    revision: Revision,
    path: Path,
    cache: dict[Path, Document],
    refuse: Callable[[Iterable[Path]], None],
) -> _FilesPlanned:
    """Every entry whose key ``path`` resolves to taken out, refused where the project without
    them would have an error more than it has now at its place.

    :func:`ddd.file_plans.remove_plan`'s own refusals first, then ``refuse``'s, a description an
    edit wrote that no analysis has read yet. Then judged only where every run of the revision
    analysed the project: a project any run of which stopped at its read, or at a
    plugin raising, has no complete "now" to compare with, and judged, removing the very file
    that stopped it would be refused for errors of an analysis the reader never saw. It is
    allowed then, with the sentence saying why it was not judged, true of both ways a run stops
    short.

    The refusal counts what :func:`ddd.file_plans.new_errors` counts, and says so: errors the
    project would have more of than it has now, at the places they are - a whole file's, and
    one's placed nowhere, told apart by their words as well. Not a total: measured, a project with
    four errors, whose removed writer reads a variable nothing writes, has five once it is gone -
    the writer's own error leaving with it - where the count is two. The first of them is quoted
    without being called new: where a place that had one error of a check would have two, the one
    quoted can be the old one, re-worded.

    Named by the entry taken out as the description writes it - the first, where several spell
    one file - and not by the key it was asked by, which names where the entry leads: through a
    link to a directory, a path no entry spells."""
    plan = remove_plan(revision.project, path, cache)
    removing = plan.removed[0]
    refuse(edit.path for edit in plan.edits)
    if not revision.analysed:
        return _FilesPlanned(
            plan.edits,
            unjudged=f"not every analysis of this project ran to its end, so what removing "
            f"{removing} leaves cannot be judged",
            kept_by=plan.kept_by,
        )
    errors = _judged(revision, plan.includes)
    if errors:
        where, first = errors[0]
        if len(errors) == 1:
            raise FileRefusalError(
                "invalid",
                f"removing {removing} would leave one error more than the project has now at "
                f"its place, in {where.name}: {first.message}",
            )
        raise FileRefusalError(
            "invalid",
            f"removing {removing} would leave {len(errors)} errors more than the project has "
            f"now at their places, the first in {where.name}: {first.message}",
        )
    return _FilesPlanned(plan.edits, kept_by=plan.kept_by)


def _judged(revision: Revision, includes: Sequence[str]) -> tuple[Pair, ...]:
    """The errors the project would have more of with its root's includes replaced by
    ``includes``, by :func:`ddd.file_plans.new_errors`: the revision's findings against its own
    runs made again with the list changed, the revision the plan was computed from and never a
    fresher one.

    Refused ``stale`` where any file of the revision no longer reads as it did - read afresh and
    fingerprinted, as an edit's own check is. The revision's findings were made from those
    bytes, and :func:`ddd.gui.session.findings_with` reads every file again: a description saved
    since reads the root's findings through a list they were not made from, and a component
    saved just before the next poll would make an error that save brought read as the
    change's.

    Refused ``stale`` too where an entry of the tree reaches a file the revision never read
    (:func:`_appeared_since`): judged, an error of that file read as the change's.

    Asked only where there is a judgement to spoil, never of a plan answered unjudged: a file
    the revision could not read - the one a plain entry naming no file puts among its files -
    reads as changed every time it is asked, and would refuse removing that very entry for
    good. Its project is never analysed, ``file-not-found`` being an error no build lowers."""
    saved = [file.path.name for file in revision.files if _changed_since(file)]
    if saved:
        raise EditError(
            STALE,
            f"{', '.join(saved)} changed since the project was analysed, so the change cannot "
            "be judged until the project is analysed again",
        )
    appeared = _appeared_since(revision)
    if appeared:
        raise EditError(
            STALE,
            f"{', '.join(appeared)} appeared since the project was analysed, so the change cannot "
            "be judged until the project is analysed again",
        )
    now = [(filed.file, filed.diagnostic) for filed in revision.findings]
    after = [(filed.file, filed.diagnostic) for filed in findings_with(revision, includes)]
    return new_errors(now, after)


def _declaration_plan_of(
    asked: ReadDeclaration | DeclareObject | RemoveDeclaration,
    built: Index,
    file: Path,
    cache: dict[Path, Document],
) -> DeclarationPlan:
    """The plan ``asked`` names, over the parts its model read.

    A definition is read here, rather than by the query, as json text is read everywhere else in
    a query (:func:`~ddd.gui.queries.json_value`): its depth counted before anything parses it,
    by the loader's rule, its numbers finite. Text that is not such json, or not one json object,
    is refused ``invalid``, 409, in the one sentence it always was - the declare panel shows it
    as its offer's refusal (ruling 5 of the security review's plan)."""
    if isinstance(asked, ReadDeclaration):
        return read_object(built, file, asked.name, asked.scope, cache)
    if isinstance(asked, RemoveDeclaration):
        return remove_declaration(built, file, asked.name, cache)
    try:
        definition = json_value(asked.definition)
    except EditError as malformed:
        raise DeclarationRefusalError("invalid", "the definition is not json") from malformed
    if not isinstance(definition, dict):
        raise DeclarationRefusalError("invalid", "the definition is not json")
    return declare_object(built, file, asked.scope, definition, cache)


def _planned_changes(
    revision: Revision, derived: Derived, planned: Sequence[Planned]
) -> list[dict[str, Any]]:
    """A preview's files as the page reads them: the edit of each - posted to ``POST /api/edit``
    as it stands - beside the lines it changes.

    Refused whole where one of those files lies outside what the session serves. A preview
    carries the very lines it would change, so offering one would show a file the page may not
    read, and the edit it offers would be refused on arrival. The routes that reach a file by
    name rather than by path - settling a key on every declaration of a variable, a finding's
    own fix - are the ones that can reach such a file at all, an ``includes`` entry above the
    root having made it part of the project.

    An undo's own preview needs no such check: opening a project empties the stack, and no edit
    made since can have written a file outside, being resolved through :func:`_source`.
    """
    for entry in planned:
        _served(revision, derived.resolve(entry.path))
    return [
        {
            "file": derived.resolve(entry.path).as_posix(),
            "fingerprint": entry.fingerprint,
            "operations": [
                {"op": o.op, "pointer": o.pointer, "raw": o.raw} for o in entry.operations
            ],
            "hunks": [{"line": h.line, "before": h.before, "after": h.after} for h in entry.hunks],
        }
        for entry in planned
    ]


def _undone_changes(entry: Undoable) -> list[dict[str, Any]]:
    """The files an undo puts back and the lines each would get, read from the disk as it
    stands.

    A file whose bytes are not the ones that edit left refuses the whole preview rather than
    being left out of it: an undo is all-or-nothing, and offering the rest would be offering to
    throw away half of what somebody wrote in their own editor.
    """
    changes: list[dict[str, Any]] = []
    for file in entry.files:
        try:
            current = unchanged(file).decode("utf-8-sig")
        except EditError as refused:
            # The page shows this sentence as it stands, and every other sentence it shows names a
            # file by its own name rather than by the path the engine refuses with.
            raise EditError(
                refused.code, str(refused).replace(str(file.path), file.path.name, 1)
            ) from None
        previous = "" if file.before is None else file.before.decode("utf-8-sig")
        changes.append(
            {
                "file": file.path.as_posix(),
                "gone": file.before is None,
                "hunks": [
                    {"line": h.line, "before": h.before, "after": h.after}
                    for h in hunks(current, previous)
                ],
            }
        )
    return changes


def _number(text: str) -> float:
    """A raw count as the query spells it: a whole number where it is one, else a float.

    ``json.loads`` rather than ``float``, so that ``750`` stays an ``int`` and is written back
    as ``750`` rather than ``750.0`` - the file's own spelling, and the one the integer check
    weighs.

    Refused as anything else that is not a number is, with the same sentence: text holding a
    bracket before anything parses it - no number holds one, and parsed, an array nested deep
    enough exhausts the stack; and a whole number of more digits than ``int()`` reads, which
    ``json.loads`` raises a plain ``ValueError`` for, not a ``JSONDecodeError``.
    """
    if "[" in text or "{" in text:
        raise ValueRefusalError("invalid", f"'{text}' is not a number")
    try:
        value = json.loads(text)
    except ValueError as malformed:
        raise ValueRefusalError("invalid", f"'{text}' is not a number") from malformed
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueRefusalError("invalid", f"'{text}' is not a number")
    return value


def _folded(flat: Sequence[float], dictionary: DataDictionary, name: str) -> list[list[float]]:
    """A row-major list laid back into rows by the shape the project already states.

    A list whose length is not the shape's is laid out as one row, so that ``set_values``'s own
    refusal says what was wanted against what came - one sentence for a wrong length, rather than
    one here and a different one there.
    """
    resolved = dictionary.by_name.get(name)
    shape = tuple(resolved.shape) if resolved is not None else ()
    if len(shape) != 2 or len(flat) != shape[0] * shape[1]:
        return [list(flat)]
    return [list(flat[row * shape[1] : (row + 1) * shape[1]]) for row in range(shape[0])]


def _validated[T: BaseModel](
    model: type[T], body: bytes | None, serving: Serving | None = None
) -> T | Reply:
    """``body`` read as ``model``, or the 400 reply about the first way it is not one; a path
    in it read against ``serving`` (:class:`~ddd.gui.queries.Serving`).

    Strict and closed, per the model's own configuration: an unknown key, a string where an
    index belongs or a boolean where an integer belongs never reaches a handler.
    """
    try:
        return model.model_validate_json(body or b"", context=serving)
    except ValidationError as error:
        return _error(400, "bad-request", _message(error))


def _message(error: ValidationError) -> str:
    """The first problem ``error`` describes, as one sentence naming where it is.

    Pydantic's own text is several lines - "N validation errors for Model", one block per
    field, a link to its documentation - written for a terminal, not for a banner next to a
    field. The first problem is the one worth showing: a request a page built from its own
    types fails for one reason at a time, and that reason already reads as a full sentence.
    """
    first = error.errors(include_url=False)[0]
    where = ""
    for part in first["loc"]:
        where += f"[{part}]" if isinstance(part, int) else f".{part}" if where else str(part)
    return f"{where}: {first['msg']}" if where else first["msg"]


def _query_message(route: Route, error: ValidationError) -> str:
    """The first problem ``error`` found with a query of ``route``, as the one sentence the route
    answers it with: for a key it does not take, that it takes no such key; for a key it requires,
    left out or given blank, its ``missing``; for anything else, the sentence of the value's own
    type - or of a check the model makes of the query as a whole, before reading any key.

    A query read as one model per action has its problem placed under the action given, which
    pydantic puts first in the problem's location: that action's model is the one whose ``missing``
    is answered, and the action names the key it does not take."""
    first = error.errors(include_url=False)[0]
    where, named, model = first["loc"], route.name, route.query
    actions = actions_of(model)
    if where and where[0] in actions:
        named = str(where[0])
        model, where = actions[named], where[1:]
    if first["type"] == "extra_forbidden":
        return f"{named} takes no ?{where[0]}="
    if where and issubclass(model, _Query) and _left_out(model, str(where[0]), first):
        return model.missing
    return first["msg"]


def _left_out(model: type[_Query], key: str, problem: ErrorDetails) -> bool:
    """Whether ``problem`` is a key ``model`` requires being left out or given blank."""
    if problem["type"] == "missing":
        return True
    return problem["input"] == "" and model.model_fields[key].is_required()


def _file_change(change: contract.Change) -> FileChange:
    """A validated change, as the session's edit engine takes it: a ``null`` fingerprint stays
    ``None``, the change that creates its file."""
    operations = tuple(Operation(o.op, o.pointer, o.raw, o.to) for o in change.operations)
    return FileChange(Path(change.file), change.fingerprint, operations)
