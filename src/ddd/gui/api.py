"""The JSON API of ``ddd gui``: each request answered from the session, as a status and a body.

Nothing here reads a socket or a header, which is the server's business. A request arrives as
its method, its path, its query and its body, and leaves as a :class:`Reply`, so every answer
the page can get is tested without a network in between. The API is internal - the page and the
server ship in one wheel - and changes with the package.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd import __version__
from ddd.diagnostics import CHECKS, CheckInfo
from ddd.editing import INVALID, STALE, UNREADABLE, UNVERIFIED, EditError, FileChange, Operation
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

OPERATIONS: Final = frozenset({"set", "remove", "insert", "move"})

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
            {
                "root": found.root.as_posix(),
                "projects": [
                    {"path": p.path.as_posix(), "name": p.name, "images": list(p.images)}
                    for p in found.projects
                ],
                "refused": [
                    {"record": record.as_posix(), "reason": reason}
                    for record, reason in found.refused
                ],
            },
        )

    def _open(self, query: Query, body: bytes | None) -> Reply:
        request = _json_object(body)
        given = None if request is None else request.get("path")
        if not isinstance(given, str):
            return _error(400, "bad-request", 'open takes {"path": ...}')
        wanted = Path(given).resolve()
        found = find_projects(self.session.root, self.session.build_directories)
        allowed = {p.path for p in found.projects} | ({self.project} if self.project else set())
        if wanted not in allowed:
            return _error(404, "not-found", f"{given} is not a project found here")
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
            {
                "revision": revision.number,
                "project": revision.project.as_posix(),
                "files": [_file(file) for file in revision.files],
                "findings": [_finding(filed) for filed in revision.findings],
            },
        )

    def _file(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("path"))
        if path is None:
            return _error(400, "bad-request", "file takes ?path=")
        content = self.session.read_file(Path(path))
        return Reply(
            200,
            {
                "path": content.path.as_posix(),
                "fingerprint": content.fingerprint,
                "data": content.data,
                "error": content.error,
            },
        )

    def _dictionary(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        if revision is None:
            raise NoProjectError("no project is open")
        dictionary = revision.dictionary
        return Reply(
            200,
            {
                "revision": revision.number,
                "dictionary": None if dictionary is None else dictionary.model_dump(mode="json"),
            },
        )

    def _checks(self, query: Query, body: bytes | None) -> Reply:
        revision = self.session.revision
        plugins = () if revision is None else revision.checks
        return Reply(200, {"checks": [_check(info) for info in (*CHECKS.values(), *plugins)]})

    def _edit(self, query: Query, body: bytes | None) -> Reply:
        changes = _changes(_json_object(body))
        if changes is None:
            return _error(
                400,
                "bad-request",
                'edit takes {"changes": [{"file", "fingerprint", "operations": [...]}]}',
            )
        try:
            revision, written = self.session.edit(changes)
        except EditError as refusal:
            return _error(409 if refusal.code in REFUSALS else 500, refusal.code, str(refusal))
        return Reply(
            200,
            {
                "revision": revision.number,
                "files": [
                    {"path": path.as_posix(), "fingerprint": stamp}
                    for path, stamp in written.items()
                ],
            },
        )

    def _session_body(self) -> dict[str, Any]:
        revision = self.session.revision
        return {
            "version": __version__,
            "preview": True,
            "root": self.session.root.as_posix(),
            "project": None if revision is None else _project(revision),
            "builds": []
            if revision is None
            else [
                {"image": info.image, "strict": info.strict, "severity": list(info.severity)}
                for info in revision.builds
            ],
        }


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
    return {"path": revision.project.as_posix(), "name": name}


def _file(file: SourceFile) -> dict[str, Any]:
    return {
        "path": file.path.as_posix(),
        "kind": file.kind,
        "name": file.name,
        "loaded": file.loaded,
        "fingerprint": file.fingerprint,
        "findings": {"error": file.errors, "warning": file.warnings, "info": file.infos},
    }


def _finding(filed: Filed) -> dict[str, Any]:
    finding = filed.diagnostic
    return {
        "file": filed.file.as_posix(),
        "check": finding.check,
        "severity": finding.severity.value,
        "message": finding.message,
        "pointer": "" if finding.location is None else finding.location.pointer,
        "notes": [
            {
                "message": text,
                "file": None if note is None else note.path.as_posix(),
                "pointer": "" if note is None else note.pointer,
            }
            for text, note in finding.notes
        ],
    }


def _check(info: CheckInfo) -> dict[str, Any]:
    return {
        "check": info.identifier,
        "default_severity": info.default_severity.value,
        "description": info.description,
        "overridable": info.overridable,
        "needs_every_component": info.needs_every_component,
        "comparison": info.comparison,
    }


def _json_object(body: bytes | None) -> dict[str, Any] | None:
    try:
        parsed = json.loads(body or b"")
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _single(values: Sequence[str] | None) -> str | None:
    return values[0] if values else None


def _integer(values: Sequence[str] | None) -> int | None:
    text = _single(values)
    return int(text) if text is not None and text.isascii() and text.isdecimal() else None


def _changes(request: dict[str, Any] | None) -> list[FileChange] | None:
    entries = None if request is None else request.get("changes")
    if not isinstance(entries, list) or not entries:
        return None
    changes = []
    for entry in entries:
        change = _change(entry)
        if change is None:
            return None
        changes.append(change)
    return changes


def _change(entry: object) -> FileChange | None:
    if not isinstance(entry, dict):
        return None
    file, stamp, operations = entry.get("file"), entry.get("fingerprint"), entry.get("operations")
    if not (isinstance(file, str) and isinstance(stamp, str) and isinstance(operations, list)):
        return None
    parsed = [_operation(item) for item in operations]
    valid = [operation for operation in parsed if operation is not None]
    if not operations or len(valid) != len(operations):
        return None
    return FileChange(Path(file), stamp, tuple(valid))


def _operation(item: object) -> Operation | None:
    if not isinstance(item, dict):
        return None
    op, pointer, raw, to = item.get("op"), item.get("pointer"), item.get("raw"), item.get("to")
    if op not in OPERATIONS or not isinstance(pointer, str):
        return None
    if raw is not None and not isinstance(raw, str):
        return None
    if to is not None and (not isinstance(to, int) or isinstance(to, bool)):
        return None
    return Operation(op, pointer, raw, to)
