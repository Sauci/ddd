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
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from ddd import __version__
from ddd.diagnostics import CHECKS, CheckInfo
from ddd.editing import INVALID, STALE, UNREADABLE, UNVERIFIED, EditError, FileChange, Operation
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

WAIT_SECONDS: Final = 25.0
"""How long a request for a newer revision waits before answering with the current one."""

REFUSALS: Final = frozenset({STALE, UNREADABLE, INVALID, UNVERIFIED})
"""The edit refusals a page can act on, answered 409; anything else an edit raises is a 500."""

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
                files=[_file(file) for file in revision.files],
                findings=[_finding(filed) for filed in revision.findings],
            ).model_dump(mode="json"),
        )

    def _file(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("path"))
        if path is None:
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
        return Reply(
            200,
            contract.DictionaryReply(
                revision=revision.number, dictionary=revision.dictionary
            ).model_dump(mode="json"),
        )

    def _checks(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        plugins = () if revision is None else revision.checks
        return Reply(
            200,
            contract.ChecksReply(
                checks=[_check(info) for info in (*CHECKS.values(), *plugins)]
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

    def _session_body(self) -> dict[str, Any]:
        revision = self.session.revision
        return contract.SessionInfo(
            version=__version__,
            preview=True,
            root=self.session.root.as_posix(),
            project=None if revision is None else _project(revision),
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
    "/api/checks": ("GET", Api._checks),
    "/api/edit": ("POST", Api._edit),
}


def _error(status: int, code: str, message: str) -> Reply:
    return Reply(status, {"error": code, "message": message})


def _project(revision: Revision) -> dict[str, Any]:
    name = next((f.name for f in revision.files if f.path == revision.project), None)
    return contract.OpenProject(path=revision.project.as_posix(), name=name).model_dump(mode="json")


def _file(file: SourceFile) -> dict[str, Any]:
    return contract.SourceFile(
        path=file.path.as_posix(),
        kind=file.kind,
        name=file.name,
        loaded=file.loaded,
        fingerprint=file.fingerprint,
        findings={"error": file.errors, "warning": file.warnings, "info": file.infos},
    ).model_dump(mode="json")


def _finding(filed: Filed) -> dict[str, Any]:
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


def _check(info: CheckInfo) -> dict[str, Any]:
    return contract.CheckInfo(
        check=info.identifier,
        default_severity=info.default_severity,
        description=info.description,
        overridable=info.overridable,
        needs_every_component=info.needs_every_component,
        comparison=info.comparison,
    ).model_dump(mode="json")


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
    """A validated change, as the session's edit engine takes it."""
    operations = tuple(Operation(o.op, o.pointer, o.raw, o.to) for o in change.operations)
    return FileChange(Path(change.file), change.fingerprint, operations)
