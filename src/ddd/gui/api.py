"""The JSON API of ``ddd gui``: each request answered from the session, as a status and a body.

Nothing here reads a socket or a header, which is the server's business. A request arrives as
its method, its path, its query and its body, and leaves as a :class:`Reply`, so every answer
the page can get is tested without a network in between. The API is internal - the page and the
server ship in one wheel - and changes with the package.

Every request and response body is a model of :mod:`ddd.gui.contract`: a request is read with
:meth:`~pydantic.BaseModel.model_validate_json`, refusing anything the page's own types would
not have sent, and a response is built as a model and left as ``model_dump(mode="json")`` -
never a hand-assembled ``dict`` - so the shape answered here and the shape
``gui/src/generated/api.ts`` declares cannot drift apart.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import BaseModel, ValidationError

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
    parse_raw,
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
from ddd.finding_routes import Route, route_of
from ddd.findings_by_file import Pair
from ddd.graph import Module, graph_of
from ddd.gui import contract
from ddd.gui.compare import BaselineCache, BaselineRefusedError, compared
from ddd.gui.derived import Derived, derived
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
from ddd.lsp.edits import PROPAGATED_KEYS, settle
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
    type_rows,
    uses_of,
)
from ddd.project_units import (
    adoptable,
    description_of,
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

ANALYSING: Final = "analysing"
"""The refusal of a request the analysis has not caught up with: asked of the open project before
its first analysis has landed, or a plan changing a file an edit wrote that no analysis has read
yet. Answered 409, and answered differently once the analysis lands."""

REFUSALS: Final = frozenset({STALE, UNREADABLE, INVALID, UNVERIFIED, ANALYSING})
"""The edit refusals a page can act on, answered 409; anything else an edit raises is a 500."""

UNIT_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "rename": ("unit", "to"),
    "add": ("unit",),
    "describe": ("unit", "description"),
    "remove": ("unit",),
    "adopt": (),
}
"""The changes ``GET /api/unit-plan`` previews, each with the parameters it takes besides
``action``."""

TYPE_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "set": ("name", "key"),
    "rename": ("name", "to"),
}
"""What each change of a type takes, beside the action itself. ``set`` takes ``raw`` too, which
may be absent: leaving a key out is what its absence means."""

CONSTANT_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "set": ("name", "key"),
    "rename": ("name", "to"),
    "add": ("name", "raw"),
    "remove": ("name",),
}
"""What each change of a constant takes, beside the action itself. ``set`` takes ``raw`` too,
which may be absent: leaving it out is what taking the key away means. ``add`` takes ``raw`` as
one of its required parameters instead: a constant declared with no value is not what ``add``
means, unlike ``set``, which a reader may ask of a row without having typed anything yet."""

SECTION_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "set": ("name", "key"),
    "rename": ("name", "to"),
    "add": ("name", "access", "alignment"),
    "remove": ("name",),
}
"""What each change of a section takes, beside the action itself.

``set``, ``rename`` and ``remove`` are the constants table's own, spelled again rather than shared:
these are the query parameters of one url, and a table two urls read from would tie a change of
either endpoint to the other.

``add`` is where the two differ, and where the descriptor decides: one parameter per key of
:attr:`ddd.project_shared.SECTIONS.required`, in the order :func:`_required_keys` reads them off
:attr:`~ddd.project_shared.Vocabulary.keys`, because a section the model gives no default for
``access`` or ``alignment`` is one whose file would not load the moment it was written -
``?raw=`` alone, which is all a constant's one required key needs, could not say either. Each
carries json text, judged as ``set``'s ``raw`` is:
``?access="read-only"&alignment=4``. ``description`` is not among them, having a default, and is
set from the panel afterwards.
"""

RASTER_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "set": ("name", "key"),
    "rename": ("name", "to"),
    "add": ("name", "event"),
    "remove": ("name",),
}
"""What each change of a raster takes, beside the action itself.

The third table of the same four verbs, spelled again rather than shared for the reason
:data:`SECTION_PLANS` gives: these are one url's query parameters, and a table two urls read from
would tie a change of either to the other.

``add`` is one parameter per key of :attr:`ddd.project_shared.RASTERS.required`, which is ``event``
alone - a raster's ``cycle`` is ``str | None`` and its ``description`` defaults, so neither is the
request's to supply and both are set from the panel afterwards. One required key, as a constant
has, and still named for the key rather than carried as ``?raw=``: a section is not the only
vocabulary whose ``add`` says which key it is declaring, and a url reading ``?event=1`` is what
lets :func:`_declared` build the entry off the descriptor instead of off this route's memory of
which key a vocabulary happens to require.
"""

FILE_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "create": ("kind", "name"),
    "add": ("path",),
    "remove": ("path",),
}
"""What each change of the project's files takes, beside the action itself: ``create`` the kind
and the name of the new file, ``add`` a path relative to the description or absolute, as the
reader typed it, and ``remove`` the key of a row of ``GET /api/files``.

``create`` takes ``component`` as well, a new component's name, and may go without it: absent
or empty, it reaches :func:`ddd.file_plans.create_plan` as ``None``, which refuses a component
without a name in words of its own, and ignores it for every other kind."""

DECLARATION_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "read": ("file", "name", "scope"),
    "declare": ("file", "scope", "definition"),
    "remove": ("file", "name"),
}
"""Which query parameters each action of ``GET /api/declaration-plan`` takes."""

_NOTHING_LOADED: Final = "the open project did not load, so no interface of it can be changed"

_NOTHING_RESOLVED: Final = "the open project did not resolve, so no object's values can be read"

_NOTHING_COMPARABLE: Final = (
    "the open project did not resolve, so it cannot be compared against a baseline"
)

type Query = Mapping[str, Sequence[str]]

type SharedPlanner = Callable[
    [str, Index, SharedProject, Mapping[str, str], str | None, dict[Path, Document]], SharedPlan
]
"""What :meth:`Api._shared_plan` asks for the plan itself: the action, the index, the project's own
files, the parameters the action takes, ``?raw=`` where the request carried one, and the read cache
the route shares. One per vocabulary, since ``add`` is spelled differently for each."""


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
        self._memo: dict[tuple[object, ...], Reply] = {}
        # The state's answer and the version it was made at: what `GET /api/state` answers again
        # until the version moves, every request of a page's long poll asking for it.
        self._state_kept: tuple[int, Reply] | None = None

    def handle(self, method: str, path: str, query: Query, body: bytes | None) -> Reply:
        route = _ROUTES.get(path)
        if route is None:
            return _error(404, "not-found", f"{path} is not part of the api")
        answer = route.get(method)
        if answer is None:
            return _error(405, "method-not-allowed", f"{path} takes {' or '.join(route)}")
        try:
            return answer(self, query, body)
        except NoProjectError as error:
            return _error(409, "no-project", str(error))
        except NotAnalysedError as error:
            return _error(409, ANALYSING, str(error))
        except NotInProjectError as error:
            return _error(404, "not-found", str(error))

    def _session(self, query: Query, body: bytes | None) -> Reply:
        return Reply(200, self._session_body())

    def _projects(self, query: Query, body: bytes | None) -> Reply:
        found = find_projects(self.session.root, self.session.build_directories)
        return Reply(
            200,
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
            ).model_dump(mode="json"),
        )

    def _open(self, query: Query, body: bytes | None) -> Reply:
        request = _validated(contract.OpenRequest, body)
        if isinstance(request, Reply):
            return request
        wanted = Path(request.path).resolve()
        found = find_projects(self.session.root, self.session.build_directories)
        allowed = {p.path for p in found.projects} | ({self.project} if self.project else set())
        if wanted not in allowed:
            return _error(404, "not-found", f"{request.path} is not a project found here")
        try:
            self.session.open(wanted)
        except ValueError as error:
            return _error(409, "not-a-project", str(error))
        # Answered at once, the project named: the page follows its first analysis from the
        # state, which says it is being analysed until it lands.
        return Reply(200, self._session_body())

    def _state(self, query: Query, body: bytes | None) -> Reply:
        """What the session says: at once, or as soon as its version is past ``?after=``, or
        once the wait runs out.

        Made once a version and kept, every request of a page's long poll asking for it: the
        version moves at every change of what the answer says. Not guarded, as :meth:`_derive`
        is not: two requests of one version that both find nothing kept both make it, and one
        made at an older version can be kept over a newer one's, which the newer version's next
        request makes again. Each answer is the one its own version says; only work is
        repeated."""
        after = _integer(query.get("after"))
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
        no findings before its first analysis."""
        revision = snapshot.revision
        number = 0
        edits = 0
        files: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        if revision is not None:
            number = revision.number
            edits = revision.edits
            derived = self._derive(revision)
            cache: dict[Path, Document] = {}
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
            findings = [
                _finding(filed, source, cache)
                for filed, source in zip(revision.findings, derived.sources, strict=True)
            ]
        top = snapshot.undoable
        return Reply(
            200,
            contract.State(
                revision=number,
                version=snapshot.version,
                project=project.as_posix(),
                files=files,
                findings=findings,
                undoable=None if top is None else {"at": top.at, "label": top.label},
                analysing=snapshot.analysing,
                edits=edits,
            ).model_dump(mode="json"),
        )

    def _file(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("path"))
        if not path:
            return _error(400, "bad-request", "file takes ?path=")
        content = self.session.read_file(Path(path))
        return Reply(
            200,
            contract.FileContent(
                path=content.path.as_posix(),
                fingerprint=content.fingerprint,
                data=content.data,
                error=content.error,
            ).model_dump(mode="json"),
        )

    def _dictionary(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        dictionary = revision.dictionary
        return Reply(
            200,
            contract.DictionaryReply(
                revision=revision.number,
                # Dumped here rather than left a model for DictionaryReply to nest: the file
                # format already publishes this shape under `ddd schema dictionary`, and the
                # api schema is not the place to publish it a second time.
                dictionary=None if dictionary is None else dictionary.model_dump(mode="json"),
            ).model_dump(mode="json"),
        )

    def _graph(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("graph",), lambda: self._graph_of(revision))

    def _graph_of(self, revision: Revision) -> Reply:
        modules = [_module(file) for file in revision.files if file.kind == "component"]
        findings = [(PurePosixPath(f.file.as_posix()), f.diagnostic) for f in revision.findings]
        built = graph_of(revision.dictionary, modules, findings)
        return Reply(
            200,
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
            ).model_dump(mode="json", by_alias=True),
        )

    def _checks(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        plugins = () if revision is None else revision.checks
        return Reply(
            200,
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
            ).model_dump(mode="json"),
        )

    def _edit(self, query: Query, body: bytes | None) -> Reply:
        request = _validated(contract.Changes, body)
        if isinstance(request, Reply):
            return request
        try:
            at, written = self.session.edit(
                [_file_change(c) for c in request.changes], request.label
            )
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        # Answered once written, before its analysis: the edit's own number is what says when a
        # revision includes it.
        return Reply(
            200,
            contract.EditReply(
                edit=at,
                files=[
                    {"path": file.path.as_posix(), "fingerprint": file.fingerprint}
                    for file in written
                ],
            ).model_dump(mode="json"),
        )

    def _undo(self, query: Query, body: bytes | None) -> Reply:
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
            contract.UndoPreview(
                revision=revision.number, at=top.at, label=top.label, changes=changes
            ).model_dump(mode="json"),
        )

    def _apply_undo(self, query: Query, body: bytes | None) -> Reply:
        """Put that edit back, and answer the number the undo took, once the files are back -
        before its analysis."""
        request = _validated(contract.UndoRequest, body)
        if isinstance(request, Reply):
            return request
        try:
            number = self.session.undo(request.at)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(200, contract.UndoReply(edit=number).model_dump(mode="json"))

    def _variable(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "variable takes ?name=")
        built = revision.index
        cache: dict[Path, Document] = {}
        declared = () if built is None else declarations_of(built, name, cache)
        if built is None or not declared:
            return _undeclared(revision, name)
        derived = self._derive(revision)
        return Reply(
            200,
            contract.VariableReply(
                revision=revision.number,
                name=name,
                declarations=[
                    {
                        "path": entry.site.path.resolve().as_posix(),
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
                        if located_on(declared, file, found)
                    ],
                    cache,
                ),
            ).model_dump(mode="json"),
        )

    def _units(self, query: Query, body: bytes | None) -> Reply:
        """The vocabulary, the units in use, the Units tab's rows and whether adopting is offered.

        Answered anew each time, never kept (:meth:`_memoised`): the offer reads the disk as it
        stands - the includes expanded to find the units files, and whether ``units.ddd.json``
        is there beside the description - which no revision records: neither a file appearing
        where a pattern matches nor one no include names starts an analysis."""
        revision = self._opened()
        cache: dict[Path, Document] = {}
        vocabulary = vocabulary_of(
            [read(file.path, cache) for file in revision.files if file.kind == "units"]
        )
        built = revision.index
        # The project `_unit_plan` makes its plans in, built the same way: the offer asks the
        # plan's own guards of it, so an Adopt this answers is one the plan will not refuse.
        project = unit_project(
            revision.project, [file.path for file in revision.files if not file.loaded], cache
        )
        used = () if built is None else units_in_use(built)
        rows = () if built is None else unit_rows(built, self._derive(revision).findings, cache)
        return Reply(
            200,
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
                        "files": [path.resolve().as_posix() for path in row.files],
                        "variables": row.variables,
                        "types": row.types,
                        "members": row.members,
                        "findings": row.findings,
                    }
                    for row in rows
                ],
                adoptable=adoptable(built, project),
            ).model_dump(mode="json"),
        )

    def _unit(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        unit = _single(query.get("name"))
        if not unit:
            return _error(400, "bad-request", "unit takes ?name=")
        built = revision.index
        if built is None or (unit not in built.units and unit not in built.vocabulary):
            return _undeclared(revision, unit)
        cache: dict[Path, Document] = {}
        derived = self._derive(revision)
        return Reply(
            200,
            contract.UnitReply(
                revision=revision.number,
                unit=unit,
                description=description_of(built, unit, cache),
                entries=[
                    {"file": entry.path.resolve().as_posix(), "pointer": entry.pointer}
                    for entry in built.vocabulary.get(unit, ())
                ],
                sites=[
                    {
                        "path": place.stated.site.path.resolve().as_posix(),
                        "pointer": place.stated.site.pointer,
                        "kind": place.stated.kind,
                        "name": place.stated.name,
                        "component": place.component,
                        "role": place.role,
                    }
                    for place in places_of(built, unit, cache, _changed_in(derived))
                ],
                findings=_listed(derived, unit_findings(built, unit, derived.findings), cache),
            ).model_dump(mode="json"),
        )

    def _unit_plan(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        action = _single(query.get("action")) or ""
        takes = UNIT_PLANS.get(action)
        if takes is None:
            return _error(
                400, "bad-request", f"unit-plan takes ?action= one of {', '.join(UNIT_PLANS)}"
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes) or given.get("unit") == "":
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
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
            plan = _unit_plan_of(action, built, project, given, cache)
        except UnitRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _types(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("types",), lambda: self._types_of(revision))

    def _types_of(self, revision: Revision) -> Reply:
        built = revision.index
        cache: dict[Path, Document] = {}
        rows = () if built is None else type_rows(built, self._derive(revision).findings, cache)
        return Reply(
            200,
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
            ).model_dump(mode="json"),
        )

    def _type(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "type takes ?name=")
        built = revision.index
        if built is None or name not in built.types:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        site = built.types[name]
        derived = self._derive(revision)
        row = row_of(built, name, derived.findings, cache)
        stated = fixed_by(built, name, cache)
        header = stated.get("header")
        return Reply(
            200,
            contract.TypeReply(
                revision=revision.number,
                name=name,
                kind=row.kind,
                file=site.path.resolve().as_posix(),
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
                        "path": use.site.path.resolve().as_posix(),
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
            ).model_dump(mode="json"),
        )

    def _type_plan(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        action = _single(query.get("action")) or ""
        takes = TYPE_PLANS.get(action)
        if takes is None:
            return _error(
                400, "bad-request", f"type-plan takes ?action= one of {', '.join(TYPE_PLANS)}"
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes) or given.get("name") == "":
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
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
        raw = _single(query.get("raw")) or None
        try:
            plan = _type_plan_of(action, built, given, raw, cache)
        except TypeRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _shared(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        return self._memoised(revision, ("shared",), lambda: self._shared_of(revision))

    def _shared_of(self, revision: Revision) -> Reply:
        built = revision.index
        cache: dict[Path, Document] = {}
        rows = () if built is None else shared_rows(built, self._derive(revision).findings, cache)
        return Reply(
            200,
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
            ).model_dump(mode="json"),
        )

    def _constant(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "constant takes ?name=")
        built = revision.index
        if built is None or name not in built.constants:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        site = built.constants[name]
        # The whole entry's display texts in one read, through the descriptor: `value` as the json
        # text its file spells and `description` as the string it holds, which is what
        # `CONSTANTS.strings` says of each. The panel names its keys because the reply does; a
        # vocabulary's own keys are the descriptor's business, not this route's.
        texts = shown(CONSTANTS, built, name, cache)
        return Reply(
            200,
            contract.ConstantReply(
                revision=revision.number,
                name=name,
                value=texts["value"],
                description=texts["description"],
                file=site.path.resolve().as_posix(),
                pointer=site.pointer,
                uses=_entry_uses(CONSTANTS, built, name, cache),
                findings=_entry_findings(CONSTANTS, self._derive(revision), built, name, cache),
            ).model_dump(mode="json"),
        )

    def _section(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "section takes ?name=")
        built = revision.index
        if built is None or name not in built.sections:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        site = built.sections[name]
        texts = shown(SECTIONS, built, name, cache)
        return Reply(
            200,
            contract.SectionReply(
                revision=revision.number,
                name=name,
                access=texts["access"],
                alignment=texts["alignment"],
                description=texts["description"],
                file=site.path.resolve().as_posix(),
                pointer=site.pointer,
                uses=_entry_uses(SECTIONS, built, name, cache),
                findings=_entry_findings(SECTIONS, self._derive(revision), built, name, cache),
            ).model_dump(mode="json"),
        )

    def _raster(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "raster takes ?name=")
        built = revision.index
        if built is None or name not in built.rasters:
            return _undeclared(revision, name)
        cache: dict[Path, Document] = {}
        site = built.rasters[name]
        texts = shown(RASTERS, built, name, cache)
        return Reply(
            200,
            contract.RasterReply(
                revision=revision.number,
                name=name,
                event=texts["event"],
                cycle=texts["cycle"],
                description=texts["description"],
                file=site.path.resolve().as_posix(),
                pointer=site.pointer,
                uses=_entry_uses(RASTERS, built, name, cache),
                findings=_entry_findings(RASTERS, self._derive(revision), built, name, cache),
            ).model_dump(mode="json"),
        )

    def _files(self, query: Query, body: bytes | None) -> Reply:
        """The root's includes, each entry as the loader's own rule reads it, and what each
        brings - the files a row joins ``State.files`` on, and the findings at the entry
        itself, which a row naming nothing has no file to carry.

        Answered anew each time, never kept (:meth:`_memoised`): the includes are expanded on
        disk as it stands, which no revision records - a file appearing where a pattern matches
        starts no analysis."""
        revision = self._opened()
        at_entry = self._derive(revision).at_entry
        cache: dict[Path, Document] = {}
        return Reply(
            200,
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
            ).model_dump(mode="json"),
        )

    def _files_plan(self, query: Query, body: bytes | None) -> Reply:
        """One change of the project's files - creating, adding or removing one - previewed and
        never written, with the errors an add is counted to bring.

        A parameter :data:`FILE_PLANS` names that is missing or empty is a bad request, and so
        is a key to remove that is not absolute, as a row's never is: read against the server's
        own working directory, a relative one named another file. Past that, each refusal is the
        plan's own or :func:`_addition`'s and :func:`_removal`'s, in the order they ask them,
        ``not-found`` answered 404 and every other 409; a judgement a file saved or come since the
        revision would falsify is refused ``stale``.
        """
        revision = self._opened()
        action = _single(query.get("action")) or ""
        takes = FILE_PLANS.get(action)
        if takes is None:
            return _error(
                400, "bad-request", f"files-plan takes ?action= one of {', '.join(FILE_PLANS)}"
            )
        given: dict[str, str] = {}
        for part in takes:
            value = _single(query.get(part))
            if not value:
                wanted = " and ".join(f"?{taken}=" for taken in takes)
                return _error(400, "bad-request", f"{action} takes {wanted}")
            given[part] = value
        if action == "remove" and not Path(given["path"]).is_absolute():
            return _error(
                400,
                "bad-request",
                f"remove takes ?path= as a row's key, which is absolute, and '{given['path']}' "
                "is not",
            )
        component = _single(query.get("component")) or None
        cache: dict[Path, Document] = {}

        def refuse(paths: Iterable[Path]) -> None:
            self._refuse_unanalysed(revision, paths)

        try:
            plan = _files_plan_of(action, revision, given, component, cache, refuse)
        except FileRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            made = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.FilesPlanReply(
                revision=revision.number,
                changes=_planned_changes(revision, made),
                unjudged=plan.unjudged,
                brings=[
                    {"file": path.as_posix(), "check": found.check, "message": found.message}
                    for path, found in plan.brings
                ],
                kept_by=plan.kept_by,
            ).model_dump(mode="json"),
        )

    def _constant_plan(self, query: Query, body: bytes | None) -> Reply:
        return self._shared_plan(CONSTANTS, CONSTANT_PLANS, _constant_plan_of, query)

    def _section_plan(self, query: Query, body: bytes | None) -> Reply:
        return self._shared_plan(SECTIONS, SECTION_PLANS, _section_plan_of, query)

    def _raster_plan(self, query: Query, body: bytes | None) -> Reply:
        return self._shared_plan(RASTERS, RASTER_PLANS, _raster_plan_of, query)

    def _shared_plan(
        self,
        vocabulary: Vocabulary,
        plans: Mapping[str, tuple[str, ...]],
        plan_of: SharedPlanner,
        query: Query,
    ) -> Reply:
        """One change of one entry of ``vocabulary``, previewed and never written.

        Written once for both endpoints rather than twice: the two differ in their table of
        actions, the verb each action reaches and the noun a refusal names, all three of which
        arrive as arguments - everything else here is about the request and the revision, which a
        second copy would only be able to get wrong differently.
        """
        revision = self._opened()
        action = _single(query.get("action")) or ""
        takes = plans.get(action)
        if takes is None:
            return _error(
                400,
                "bad-request",
                f"{vocabulary.kind}-plan takes ?action= one of {', '.join(plans)}",
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes) or given.get("name") == "" or given.get("raw") == "":
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
        # Validated before any plan is asked for, as `_settle` already validates its own `raw`:
        # a request that is not json is a mistake about the request, not a refusal about the
        # project, so it answers 400 rather than being folded into a `SharedRefusalError`.
        raw = _single(query.get("raw")) or None
        for text in _json_texts(vocabulary, given, raw):
            try:
                parse_raw(text)
            except EditError as refused:
                return _error(400, "bad-request", str(refused))
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
            plan = plan_of(action, built, project, given, raw, cache)
        except SharedRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            made = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, made)
            ).model_dump(mode="json"),
        )

    def _settle(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name, key = (_single(query.get(part)) for part in ("name", "key"))
        # A blank ``raw`` is none, as a missing one: the key goes from every declaration.
        raw = _single(query.get("raw")) or None
        if not name or not key:
            return _error(
                400, "bad-request", "settle takes ?name= and ?key=, and ?raw= unless the key goes"
            )
        if key not in PROPAGATED_KEYS:
            return _error(
                400, "bad-request", f"'{key}' is not a key the declarations of a variable share"
            )
        if raw is not None:
            try:
                parse_raw(raw)
            except EditError as refused:
                return _error(400, "bad-request", str(refused))
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
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            self._refuse_unanalysed(revision, (change.site.path for change in settlement.changes))
            planned = preview(settlement, key, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.SettleReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _fix(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        file, check = (_single(query.get(part)) for part in ("file", "check"))
        pointer = _single(query.get("pointer"))
        if not file or not check or pointer is None:
            return _error(400, "bad-request", "fix takes ?file=, ?pointer= and ?check=")
        wanted = Path(file).resolve()
        source = next((f for f in revision.files if f.path.resolve() == wanted), None)
        if source is None:
            return _error(404, "not-found", f"{file} is not a file of the open project")
        cache: dict[Path, Document] = {}
        stamps = {f.path.resolve(): f.fingerprint for f in revision.files}
        built = revision.index
        if built is None:
            # No index, no declarations - a revision whose project did not load has nothing to
            # reconcile, and answering no fixes is truer than answering an error.
            built = Index()
        offered = []
        for fix in fixes_for(check, source.path, pointer, cache, built):
            try:
                self._refuse_unanalysed(revision, (edit.path for edit in fix.changes))
                made = [planned(edit.path, edit.operations, stamps) for edit in fix.changes]
            except EditError as refused:
                return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
            offered.append({"title": fix.title, "changes": _planned_changes(revision, made)})
        return Reply(
            200,
            contract.FixReply(revision=revision.number, fixes=offered).model_dump(mode="json"),
        )

    def _declarable(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("file"))
        if not path:
            return _error(400, "bad-request", "declarable takes ?file=")
        revision = self._opened()
        try:
            file = _source(revision, Path(path))
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
            ).model_dump(mode="json"),
        )

    def _declaration_plan(self, query: Query, body: bytes | None) -> Reply:
        action = _single(query.get("action")) or ""
        takes = DECLARATION_PLANS.get(action)
        if takes is None:
            return _error(
                400,
                "bad-request",
                f"declaration-plan takes ?action= one of {', '.join(DECLARATION_PLANS)}",
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes):
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
        revision = self._opened()
        try:
            file = _source(revision, Path(given["file"]))
        except NotInProjectError as outside:
            return _error(404, "not-found", str(outside))
        built = revision.index
        if built is None:
            return _error(409, UNREADABLE, _NOTHING_LOADED)
        cache: dict[Path, Document] = {}
        try:
            plan = _declaration_plan_of(action, built, file, given, cache)
        except DeclarationRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {entry.path.resolve(): entry.fingerprint for entry in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _values(self, query: Query, body: bytes | None) -> Reply:
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "values takes ?name=")
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
            contract.ValuesReply(
                revision=revision.number,
                name=grid.name,
                kind=grid.kind,
                datatype=grid.datatype,
                unit=grid.unit,
                conversion=grid.conversion.model_dump(mode="json"),
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
                        "conversion": axis.conversion.model_dump(mode="json"),
                    }
                    for axis in grid.axes
                ],
                owner=grid.owner,
                file=grid.file,
                findings=_listed(derived, _grid_findings(derived, grid), cache),
            ).model_dump(mode="json"),
        )

    def _value_plan(self, query: Query, body: bytes | None) -> Reply:
        name = _single(query.get("name"))
        at = _single(query.get("at"))
        raw_text = _single(query.get("raw"))
        if not name or not at or not raw_text:
            return _error(400, "bad-request", "value-plan takes ?name= and ?at= and ?raw=")
        revision = self._opened()
        built, dictionary = revision.index, revision.dictionary
        if built is None or dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_RESOLVED)
        try:
            raw = _number(raw_text)
            plan = set_cell(dictionary, built, name, at, raw, {})
        except ValueRefusalError as refused:
            # Both codes again, as in _values above - a name the project has not, and every
            # other refusal - so both arms need a status and a test reaching them: a ternary
            # here would read the same but hide an untested arm from the coverage gate, the
            # same blind spot that let two earlier defects through.
            if refused.code == "not-found":
                return _error(404, refused.code, refused.message)
            return _error(409, refused.code, refused.message)
        stamps = {entry.path.resolve(): entry.fingerprint for entry in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _values_plan(self, query: Query, body: bytes | None) -> Reply:
        name = _single(query.get("name"))
        counts = _single(query.get("raw"))
        if not name or not counts:
            return _error(400, "bad-request", "values-plan takes ?name= and ?raw=")
        revision = self._opened()
        built, dictionary = revision.index, revision.dictionary
        if built is None or dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_RESOLVED)
        try:
            flat = [_number(piece) for piece in counts.split(",")]
            plan = set_values(dictionary, built, name, _folded(flat, dictionary, name))
        except ValueRefusalError as refused:
            # Both codes, as `_value_plan` above: a name the project has not, and every other
            # refusal. A statement rather than a ternary, so the gate can see both arms.
            if refused.code == "not-found":
                return _error(404, refused.code, refused.message)
            return _error(409, refused.code, refused.message)
        stamps = {entry.path.resolve(): entry.fingerprint for entry in revision.files}
        try:
            self._refuse_unanalysed(revision, (edit.path for edit in plan.edits))
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(revision, planned)
            ).model_dump(mode="json"),
        )

    def _compare(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        path = _single(query.get("baseline"))
        if not path:
            return _error(400, "bad-request", "compare takes ?baseline=")
        if revision.dictionary is None:
            return _error(409, UNREADABLE, _NOTHING_COMPARABLE)
        try:
            result = compared(revision, Path(path), self.session.root, self._compare_cache)
        except BaselineRefusedError as refused:
            return _error(400, "bad-request", str(refused))
        sources = {file.path.resolve(): file for file in revision.files}
        cache: dict[Path, Document] = {}
        findings = sorted(result.findings, key=lambda filed: filed.file.as_posix())
        baseline_findings = sorted(
            result.baseline_findings, key=lambda filed: filed.file.as_posix()
        )
        return Reply(
            200,
            contract.CompareReply(
                revision=revision.number,
                verdict=result.verdict,
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache) for filed in findings
                ],
                # Never a source for one of these, whatever file it resolves to: a baseline given
                # as a project description can share files, ids and even paths with the open
                # project, so being carried in this field rather than `findings` is what marks a
                # finding as the baseline's - not a test of where it happens to sit, which
                # answered this wrong for a baseline that was also a file of the open project. Two
                # fields on the wire, mirroring `Compared`'s own two, rather than one merged list
                # a reader would have to tell apart by matching the "in the baseline: " a message
                # happens to carry - `CompareReply.baseline_findings`' own docstring is what that
                # matching would be re-deriving, unreliably, from text a page does not own.
                baseline_findings=[_finding(filed, None, cache) for filed in baseline_findings],
                renames=[
                    {"id": entry["id"], "old": entry["from"], "new": entry["to"]}
                    for entry in result.renames
                ],
            ).model_dump(mode="json"),
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
        named: list[str] = []
        for path in paths:
            resolved = path.resolve()
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
        where it is that revision's, else derived now and kept in its place, the answers
        :meth:`_memoised` kept beside the last one emptied with it.

        Once per revision while its requests come one at a time, and not guarded: requests are
        answered on threads of their own, so two first requests of one revision can both derive
        it, and a request still holding an older revision derives that one again, replacing the
        newer derivation and emptying the newer revision's kept answers, which the newer
        revision's next request makes again. Each answer is made from the revision its own
        request holds, so each stays what it would be; only work is repeated."""
        kept = self._derived
        if kept is not None and kept.number == revision.number:
            return kept
        made = derived(revision)
        self._derived = made
        self._memo = {}
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

        Not guarded: requests are answered on threads of their own. Two requests of one revision
        that both find nothing kept both make it, and an answer made for a revision a newer one
        has since replaced can be kept beside the newer revision's - under its own revision's
        number, so it answers for no other, and goes at the next derivation. Each answer stays
        what it would be; only work is repeated, where a lock around the making would hold every
        other request for a kept answer behind the one being made.
        """
        self._derive(revision)
        keyed = (key, revision.number, self.session.edits)
        kept = self._memo.get(keyed)
        if kept is None:
            kept = make()
            self._memo[keyed] = kept
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
        return contract.SessionInfo(
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
        ).model_dump(mode="json")


type Answer = Callable[[Api, Query, bytes | None], Reply]

_ROUTES: Final[dict[str, dict[str, Answer]]] = {
    "/api/session": {"GET": Api._session},
    "/api/projects": {"GET": Api._projects},
    "/api/open": {"POST": Api._open},
    "/api/state": {"GET": Api._state},
    "/api/file": {"GET": Api._file},
    "/api/dictionary": {"GET": Api._dictionary},
    "/api/graph": {"GET": Api._graph},
    "/api/checks": {"GET": Api._checks},
    "/api/edit": {"POST": Api._edit},
    "/api/undo": {"GET": Api._undo, "POST": Api._apply_undo},
    "/api/variable": {"GET": Api._variable},
    "/api/units": {"GET": Api._units},
    "/api/settle": {"GET": Api._settle},
    "/api/fix": {"GET": Api._fix},
    "/api/unit": {"GET": Api._unit},
    "/api/unit-plan": {"GET": Api._unit_plan},
    "/api/types": {"GET": Api._types},
    "/api/type": {"GET": Api._type},
    "/api/type-plan": {"GET": Api._type_plan},
    "/api/shared": {"GET": Api._shared},
    "/api/constant": {"GET": Api._constant},
    "/api/constant-plan": {"GET": Api._constant_plan},
    "/api/section": {"GET": Api._section},
    "/api/section-plan": {"GET": Api._section_plan},
    "/api/raster": {"GET": Api._raster},
    "/api/raster-plan": {"GET": Api._raster_plan},
    "/api/files": {"GET": Api._files},
    "/api/files-plan": {"GET": Api._files_plan},
    "/api/declarable": {"GET": Api._declarable},
    "/api/declaration-plan": {"GET": Api._declaration_plan},
    "/api/values": {"GET": Api._values},
    "/api/value-plan": {"GET": Api._value_plan},
    "/api/values-plan": {"GET": Api._values_plan},
    "/api/compare": {"GET": Api._compare},
}


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
    return contract.Finding(
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
    ).model_dump(mode="json")


def _route(route: Route | None) -> dict[str, Any] | None:
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
        source = derived.files.get(path.resolve())
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
    action: str,
    built: Index,
    project: UnitProject,
    given: Mapping[str, str],
    cache: dict[Path, Document],
) -> UnitPlan:
    """The plan ``action`` names, over the parameters :data:`UNIT_PLANS` says it takes."""
    if action == "rename":
        return rename_unit(built, project, given["unit"], given["to"], cache)
    if action == "add":
        return add_unit(built, project, given["unit"], cache)
    if action == "describe":
        return describe_unit(built, project, given["unit"], given["description"], cache)
    if action == "remove":
        return remove_unit(built, project, given["unit"], cache)
    return adopt_units(built, project, cache)


def _type_plan_of(
    action: str,
    built: Index,
    given: Mapping[str, str],
    raw: str | None,
    cache: dict[Path, Document],
) -> TypePlan:
    """The plan ``action`` names, over the parameters :data:`TYPE_PLANS` says it takes."""
    if action == "set":
        return set_key(built, given["name"], given["key"], raw, cache)
    return rename_type(built, given["name"], given["to"], cache)


def _constant_plan_of(
    action: str,
    built: Index,
    project: SharedProject,
    given: Mapping[str, str],
    raw: str | None,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``action`` names, over the parameters :data:`CONSTANT_PLANS` says it takes.

    ``project`` is unused by three of the four: only ``add`` may have to create a constants
    file, which is the one verb that needs to know where the project's constants files are.
    """
    if action == "set":
        return set_entry(CONSTANTS, built, given["name"], given["key"], raw, cache)
    if action == "rename":
        return rename_entry(CONSTANTS, built, given["name"], given["to"], cache)
    if action == "remove":
        return remove_entry(CONSTANTS, built, given["name"], cache)
    # `description` is given too, empty, rather than left out: `add`'s form offers no description
    # and the entry it writes has always stated one, which is the byte a newly declared constant
    # is compared against.
    return add_entry(
        CONSTANTS,
        built,
        project,
        given["name"],
        {"value": given["raw"], "description": '""'},
        cache,
    )


def _section_plan_of(
    action: str,
    built: Index,
    project: SharedProject,
    given: Mapping[str, str],
    raw: str | None,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``action`` names, over the parameters :data:`SECTION_PLANS` says it takes.

    The same four verbs as :func:`_constant_plan_of`, over the same three parameters, differing
    only in ``add``: a section is declared with one json text per required key rather than a lone
    ``?raw=``, which is why the two dispatchers are written out instead of one taking the
    descriptor. Sharing them would mean either naming a constant's value ``?value=`` on the wire -
    a url the page already calls - or teaching one function which of its parameters each
    vocabulary spells differently, and that is the branch the descriptor exists to remove.
    """
    if action == "set":
        return set_entry(SECTIONS, built, given["name"], given["key"], raw, cache)
    if action == "rename":
        return rename_entry(SECTIONS, built, given["name"], given["to"], cache)
    if action == "remove":
        return remove_entry(SECTIONS, built, given["name"], cache)
    return add_entry(SECTIONS, built, project, given["name"], _declared(SECTIONS, given), cache)


def _raster_plan_of(
    action: str,
    built: Index,
    project: SharedProject,
    given: Mapping[str, str],
    raw: str | None,
    cache: dict[Path, Document],
) -> SharedPlan:
    """The plan ``action`` names, over the parameters :data:`RASTER_PLANS` says it takes.

    The same four verbs over the same three parameters as :func:`_section_plan_of`, and the same
    ``add``: one json text per key the model gives no default for, read off the descriptor by
    :func:`_declared` rather than named here, so the only word this function spells that its
    sibling does not is the vocabulary.
    """
    if action == "set":
        return set_entry(RASTERS, built, given["name"], given["key"], raw, cache)
    if action == "rename":
        return rename_entry(RASTERS, built, given["name"], given["to"], cache)
    if action == "remove":
        return remove_entry(RASTERS, built, given["name"], cache)
    return add_entry(RASTERS, built, project, given["name"], _declared(RASTERS, given), cache)


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
    :func:`~ddd.shared_plans._judged` refuses, and :func:`_json_texts`'s caller stops at the first
    text that is not json. So an ``add`` carrying two bad values answers about whichever came
    first. What it does *not* decide is the file: :func:`~ddd.shared_plans._entry_text` composes
    the entry in ``keys`` order whatever order ``raws`` arrives in.
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


def _json_texts(vocabulary: Vocabulary, given: Mapping[str, str], raw: str | None) -> list[str]:
    """Every part of a shared plan request that has to be json, in the order a refusal should
    name them.

    ``?raw=`` where there is one, and the value of each required key an ``add`` carries, through
    :func:`_required_keys`. Both are embedded into a file verbatim, so both are the request's
    business to get right: read as text a reader who typed ``read-only`` where ``"read-only"`` was
    wanted would otherwise meet *"read-only is not an access a section may state ... : read-write
    or read-only"*, a sentence naming the value it refuses among the ones it allows.

    ``name``, ``to`` and ``key`` are not here: each is a plain string the verb quotes itself.

    Two statements rather than two conditional expressions, for the reason
    :func:`_required_keys` gives: neither the request without a ``?raw=`` nor the action that
    carries no required key would register a branch of its own.
    """
    texts = []
    if raw is not None:
        texts.append(raw)
    for key in _required_keys(vocabulary):
        if key in given:
            texts.append(given[key])
    return texts


def _entry_uses(
    vocabulary: Vocabulary, built: Index, name: str, cache: dict[Path, Document]
) -> list[dict[str, Any]]:
    """Every shape naming that entry of ``vocabulary``, as the page reads one: a constant's
    dimensions and axis sizes, a section's placements, whichever the descriptor reads."""
    return [
        {
            "path": use.site.path.resolve().as_posix(),
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
        _finding(Filed(file, diagnostic), derived.files.get(file.resolve()), cache)
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
    action: str,
    revision: Revision,
    given: Mapping[str, str],
    component: str | None,
    cache: dict[Path, Document],
    refuse: Callable[[Iterable[Path]], None],
) -> _FilesPlanned:
    """The plan ``action`` names, over the parameters :data:`FILE_PLANS` says it takes. A row's
    key is passed on as it arrived: :func:`ddd.file_plans.remove_plan` resolves it to compare, as
    :func:`ddd.file_plans.included_entries` made it, and names it as it was sent. Resolved here
    instead, a key ending in a link would be named by what the link leads to, which may lie
    outside what is served.

    ``refuse`` is asked of the files each plan's edits change, once the plan's own refusals have
    been asked and before anything is judged (:meth:`Api._refuse_unanalysed`): judged, a
    description an edit wrote and no analysis has read yet would be refused ``stale`` instead,
    for the very write the reader made."""
    if action == "create":
        edits = _creation(revision, given["kind"], given["name"], component, cache)
        refuse(edit.path for edit in edits)
        return _FilesPlanned(edits)
    if action == "add":
        return _addition(revision, given["path"], cache, refuse)
    return _removal(revision, Path(given["path"]), cache, refuse)


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
        serves = " and ".join(directory.as_posix() for directory in revision.served)
        raise FileRefusalError(
            "invalid",
            f"{entry} lies outside what ddd gui serves, {serves}; start it in a directory "
            "holding this file to add it here",
        ) from None
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
    action: str,
    built: Index,
    file: Path,
    given: Mapping[str, str],
    cache: dict[Path, Document],
) -> DeclarationPlan:
    """The plan ``action`` names, over the parameters :data:`DECLARATION_PLANS` says it takes."""
    if action == "read":
        return read_object(built, file, given["name"], given["scope"], cache)
    if action == "remove":
        return remove_declaration(built, file, given["name"], cache)
    try:
        definition = json.loads(given["definition"])
    except json.JSONDecodeError as malformed:
        raise DeclarationRefusalError("invalid", "the definition is not json") from malformed
    if not isinstance(definition, dict):
        raise DeclarationRefusalError("invalid", "the definition is not json")
    return declare_object(built, file, given["scope"], definition, cache)


def _planned_changes(revision: Revision, planned: Sequence[Planned]) -> list[dict[str, Any]]:
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
        _served(revision, entry.path.resolve())
    return [
        {
            "file": entry.path.resolve().as_posix(),
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


def _single(values: Sequence[str] | None) -> str | None:
    return values[0] if values else None


def _integer(values: Sequence[str] | None) -> int | None:
    text = _single(values)
    return int(text) if text is not None and text.isascii() and text.isdecimal() else None


def _number(text: str) -> float:
    """A raw count as the query spells it: a whole number where it is one, else a float.

    ``json.loads`` rather than ``float``, so that ``750`` stays an ``int`` and is written back
    as ``750`` rather than ``750.0`` - the file's own spelling, and the one the integer check
    weighs.
    """
    try:
        value = json.loads(text)
    except json.JSONDecodeError as malformed:
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


def _validated[T: BaseModel](model: type[T], body: bytes | None) -> T | Reply:
    """``body`` read as ``model``, or the 400 reply about the first way it is not one.

    Strict and closed, per the model's own configuration: an unknown key, a string where an
    index belongs or a boolean where an integer belongs never reaches a handler.
    """
    try:
        return model.model_validate_json(body or b"")
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


def _file_change(change: contract.Change) -> FileChange:
    """A validated change, as the session's edit engine takes it: a ``null`` fingerprint stays
    ``None``, the change that creates its file."""
    operations = tuple(Operation(o.op, o.pointer, o.raw, o.to) for o in change.operations)
    return FileChange(Path(change.file), change.fingerprint, operations)
