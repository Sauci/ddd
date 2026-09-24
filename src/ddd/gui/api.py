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
from collections.abc import Callable, Mapping, Sequence
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
from ddd.finding_fixes import fixes_for
from ddd.finding_routes import Route, route_of
from ddd.graph import Module, graph_of
from ddd.gui import contract
from ddd.gui.session import (
    Filed,
    NoProjectError,
    NotInProjectError,
    Revision,
    Session,
    SourceFile,
    Undoable,
    _source,
    find_projects,
)
from ddd.ir import DataDictionary
from ddd.lsp.edits import PROPAGATED_KEYS, settle
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import (
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
from ddd.object_values import ValueRefusalError, grid_of, set_cell, set_values
from ddd.project_types import (
    SCALAR_KEYS,
    fixed_by,
    located_in_type,
    members_of,
    row_of,
    type_rows,
    uses_of,
)
from ddd.project_units import (
    adoptable,
    description_of,
    located_on_unit,
    places_of,
    previewed,
    unit_rows,
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
"""How long a request for a newer revision waits before answering with the current one."""

REFUSALS: Final = frozenset({STALE, UNREADABLE, INVALID, UNVERIFIED})
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

DECLARATION_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "read": ("file", "name", "scope"),
    "declare": ("file", "scope", "definition"),
    "remove": ("file", "name"),
}
"""Which query parameters each action of ``GET /api/declaration-plan`` takes."""

_NOTHING_LOADED: Final = "the open project did not load, so no interface of it can be changed"

_NOTHING_RESOLVED: Final = "the open project did not resolve, so no object's values can be read"

type Query = Mapping[str, Sequence[str]]


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
        return Reply(200, self._session_body())

    def _state(self, query: Query, body: bytes | None) -> Reply:
        after = _integer(query.get("after"))
        if after is None:
            revision = self.session.revision
        else:
            revision = self.session.wait(after, self.wait_seconds)
        if revision is None:
            raise NoProjectError("no project is open")
        top = self.session.undoable
        sources = {file.path.resolve(): file for file in revision.files}
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            contract.State(
                revision=revision.number,
                project=revision.project.as_posix(),
                files=[
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
                ],
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                ],
                undoable=None if top is None else {"at": top.at, "label": top.label},
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
        revision = self.session.revision
        if revision is None:
            raise NoProjectError("no project is open")
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
        revision = self.session.revision
        if revision is None:
            raise NoProjectError("no project is open")
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
            revision, written = self.session.edit(
                [_file_change(c) for c in request.changes], request.label
            )
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        return Reply(
            200,
            contract.EditReply(
                revision=revision.number,
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
        """Put that edit back, and answer the revision it produced."""
        request = _validated(contract.UndoRequest, body)
        if isinstance(request, Reply):
            return request
        try:
            revision = self.session.undo(request.at)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(200, contract.UndoReply(revision=revision.number).model_dump(mode="json"))

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
        sources = {file.path.resolve(): file for file in revision.files}
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
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                    if located_on(declared, filed.file, filed.diagnostic)
                ],
            ).model_dump(mode="json"),
        )

    def _units(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        cache: dict[Path, Document] = {}
        vocabulary = vocabulary_of(
            [read(file.path, cache) for file in revision.files if file.kind == "units"]
        )
        built = revision.index
        used = () if built is None else units_in_use(built)
        rows = (
            ()
            if built is None
            else unit_rows(built, [(f.file, f.diagnostic) for f in revision.findings], cache)
        )
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
                adoptable=adoptable(built, vocabulary is not None),
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
        sources = {file.path.resolve(): file for file in revision.files}
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
                    for place in places_of(built, unit, cache)
                ],
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                    if located_on_unit(built, unit, filed.file, filed.diagnostic)
                ],
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
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
            ).model_dump(mode="json"),
        )

    def _types(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        built = revision.index
        cache: dict[Path, Document] = {}
        rows = (
            ()
            if built is None
            else type_rows(built, [(f.file, f.diagnostic) for f in revision.findings], cache)
        )
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
        row = row_of(built, name, [(f.file, f.diagnostic) for f in revision.findings], cache)
        stated = fixed_by(built, name, cache)
        header = stated.get("header")
        sources = {file.path.resolve(): file for file in revision.files}
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
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                    if located_in_type(built, name, filed.file, filed.diagnostic)
                ],
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
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
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
            planned = preview(settlement, key, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.SettleReply(
                revision=revision.number, changes=_planned_changes(planned)
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
        offered = []
        for fix in fixes_for(check, source.path, pointer, cache):
            try:
                made = planned(fix.path, fix.operations, stamps)
            except EditError as refused:
                return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
            offered.append({"title": fix.title, "changes": _planned_changes([made])})
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
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
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
        sources = {file.path.resolve(): file for file in revision.files}
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
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                    if grid.pointer is not None
                    and filed.file.resolve().as_posix() == grid.file
                    and filed.diagnostic.location is not None
                    and filed.diagnostic.location.pointer == f"{grid.pointer}.definition.init"
                ],
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
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
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
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
            ).model_dump(mode="json"),
        )

    def _opened(self) -> Revision:
        revision = self.session.revision
        if revision is None:
            raise NoProjectError("no project is open")
        return revision

    def _session_body(self) -> dict[str, Any]:
        revision = self.session.revision
        project = None
        if revision is not None:
            name = next((f.name for f in revision.files if f.path == revision.project), None)
            project = {"path": revision.project.as_posix(), "name": name}
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
    "/api/declarable": {"GET": Api._declarable},
    "/api/declaration-plan": {"GET": Api._declaration_plan},
    "/api/values": {"GET": Api._values},
    "/api/value-plan": {"GET": Api._value_plan},
    "/api/values-plan": {"GET": Api._values_plan},
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


def _planned_changes(planned: Sequence[Planned]) -> list[dict[str, Any]]:
    """A preview's files as the page reads them: the edit of each - posted to ``POST /api/edit``
    as it stands - beside the lines it changes."""
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
