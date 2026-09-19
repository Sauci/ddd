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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from ddd import __version__
from ddd.diagnostics import CHECKS
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    UNVERIFIED,
    EditError,
    FileChange,
    Operation,
    parse_raw,
)
from ddd.graph import Module, graph_of
from ddd.gui import contract
from ddd.gui.session import (
    Filed,
    NoProjectError,
    NotInProjectError,
    Revision,
    Session,
    SourceFile,
    find_projects,
)
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
from ddd.project_units import (
    adoptable,
    description_of,
    located_on_unit,
    places_of,
    previewed,
    unit_rows,
)
from ddd.variables import (
    Declared,
    Planned,
    declarations_of,
    located_on,
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
        expected, answer = route
        if method != expected:
            return _error(405, "method-not-allowed", f"{path} takes {expected}")
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
                findings=[_finding(filed) for filed in revision.findings],
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
            revision, written = self.session.edit([_file_change(c) for c in request.changes])
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        return Reply(
            200,
            contract.EditReply(
                revision=revision.number,
                files=[
                    {"path": path.as_posix(), "fingerprint": stamp}
                    for path, stamp in written.items()
                ],
            ).model_dump(mode="json"),
        )

    def _variable(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "variable takes ?name=")
        declared = _declared(revision, name, {})
        if not declared:
            return _undeclared(revision, name)
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
                findings=[
                    _finding(filed)
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
                    _finding(filed)
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
            planned = previewed(plan, stamps)
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
        settlement = settle(built, name, key, raw, {})
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

_ROUTES: Final[dict[str, tuple[str, Answer]]] = {
    "/api/session": ("GET", Api._session),
    "/api/projects": ("GET", Api._projects),
    "/api/open": ("POST", Api._open),
    "/api/state": ("GET", Api._state),
    "/api/file": ("GET", Api._file),
    "/api/dictionary": ("GET", Api._dictionary),
    "/api/graph": ("GET", Api._graph),
    "/api/checks": ("GET", Api._checks),
    "/api/edit": ("POST", Api._edit),
    "/api/variable": ("GET", Api._variable),
    "/api/units": ("GET", Api._units),
    "/api/settle": ("GET", Api._settle),
    "/api/unit": ("GET", Api._unit),
    "/api/unit-plan": ("GET", Api._unit_plan),
}


def _error(status: int, code: str, message: str) -> Reply:
    return Reply(status, {"error": code, "message": message})


def _finding(filed: Filed) -> dict[str, Any]:
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
    ).model_dump(mode="json")


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


def _declared(revision: Revision, name: str, cache: dict[Path, Document]) -> tuple[Declared, ...]:
    return () if revision.index is None else declarations_of(revision.index, name, cache)


def _undeclared(revision: Revision, name: str) -> Reply:
    """The answer about ``name`` when no declaration of it was read.

    That nothing declares it only while every file loaded: a file saved half-edited, as an editor
    saves one being typed into, keeps the names only it declares out of every index until it
    parses again, and a page told they are not declared would close their panels for good
    (spec 5.5) rather than wait for the next save.
    """
    unread = [file.path.name for file in revision.files if not file.loaded]
    if unread:
        return _error(
            409,
            UNREADABLE,
            f"'{name}' is not declared in any file that loaded, "
            f"and {', '.join(unread)} did not load",
        )
    return _error(404, "not-found", f"'{name}' is not declared in the open project")


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


def _single(values: Sequence[str] | None) -> str | None:
    return values[0] if values else None


def _integer(values: Sequence[str] | None) -> int | None:
    text = _single(values)
    return int(text) if text is not None and text.isascii() and text.isdecimal() else None


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
