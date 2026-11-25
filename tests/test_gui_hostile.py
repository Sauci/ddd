"""Every parameter of every route, and every string field of a POST body, sent every hostile
value spec section 5 names: none of them is answered 500.

For a plain route, the keys are its query model's own :attr:`~pydantic.BaseModel.model_fields`.
For an action route - a query of one model per action (ruling P18-3) - every member's own
:attr:`~pydantic.BaseModel.model_fields` is walked, the ``action`` given its member's own value
while another key is the one under test, so that each key reaches the model that reads it. A
route whose query takes no key at all (:class:`~ddd.gui.queries.NoQuery`) gets one stray key
instead, since there is no key of its own to mutate.

Every case sends the one key under test a hostile value, with every other key the route or
action requires given a well-formed value - a real file of the open project, or one of its
objects, wherever the handler reads a value this walk gives rather than only its model - so a
500 the walk finds is about the key under test, not about a baseline this walk got wrong.

A ``POST``'s body is walked the same way, over and above its query (ruling P18-6): every field
of :class:`~ddd.gui.contract.OpenRequest`, :class:`~ddd.gui.contract.Changes`,
:class:`~ddd.gui.contract.Change`, :class:`~ddd.gui.contract.Operation` and
:class:`~ddd.gui.contract.UndoRequest` whose own annotation admits a string
(:func:`_admits_string`) - read off each model's own ``model_fields``, as the query walk reads
a query model's, rather than named by hand, so a field these models gain later is swept in
without this file changing. ``Operation.op`` is a ``Literal`` of four strings and so is one of
them, beside the plain ``str`` fields; ``Operation.to`` and :class:`~ddd.gui.contract.UndoRequest`'s
only field, ``at``, are both ``int`` and admit none - :class:`~ddd.gui.contract.UndoRequest`
contributes no case, which is named and asserted, not left to be noticed by its absence.

Every body case starts from the demo exactly as the walk found it (ruling P18-23): each file a
case wrote is given back the bytes it held, and a session opened afresh over them, so that the
fingerprint the well-formed edit carries - taken once, from the file as found - is always the
file's own. The walk this replaced carried each case on from the last: its hostile ``pointer``
``""``, which names the whole file, left the demo's project description a single json string,
and from then on every edit whose value was json met that string, not the description it was
written to replace, before its value was laid out - so that a value nested 3,000 deep, which the
engine's layout failed on, never reached it. So every model's well-formed body is first shown to
be answered as a good request is - a project opened, an edit applied, that edit undone - and each
case then differs from that request in its one field alone; and no case is answered the
fingerprint's own refusal but a case of ``fingerprint`` itself, which is what a case meeting a file
other than the one found would be answered. A lone surrogate reaches no field at all: json carries
one only as an escape, ``\\ud800``, which the body's own reader refuses, ``400``, before any field
is read. And a hostile number goes into a pointer's array index as well as into its own field,
spelled as the index of the well-formed edit's element (:data:`INDEXED`): sent whole, a value
never reaches a grammar inside another, where a 4,301-digit index once reached ``int()``.

The walk asserts no answer is 500 - never one of 400, 404 or 409 (ruling P18-7). The state
route's ``?after=`` is lenient: none of these values is a whole number, so it is answered at
once every time, and the walk's ``wait_seconds=0`` (as ``tests/test_gui_api.py``'s own fixtures
construct the api) means nothing here could wait regardless.

Both walks run with the working directory at the demo's root, as ``ddd gui`` serves from the
directory it was started in, so that a relative path lands where a real run's would (12:M1). The
query walk runs twice: resolving every path as the system the suite runs on resolves it, and as
Windows resolves it (:func:`_resolving_as_windows_does`), so that every system the suite runs on
asks what a run on Windows is asked.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import threading
import time
import types
import typing
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final, Literal

import pytest
from pydantic import BaseModel

from conftest import EXAMPLES, project, write_tree
from ddd.editing import fingerprint
from ddd.gui import queries as queries_module
from ddd.gui.api import ROUTES, Api, Reply
from ddd.gui.contract import Change, Changes, OpenRequest, Operation, UndoRequest
from ddd.gui.queries import actions_of
from ddd.gui.server import GuiServer
from ddd.gui.session import Session

HOSTILE: tuple[str, ...] = (
    "\x00",
    "a\x00b",
    "\ud800",
    "1" * 4301,
    "[" * 3000 + "]" * 3000,
    "1e999",
    "\\\\server\\share\\a.ddd.json",
    "//server/share/a.ddd.json",
    "//server/share/p/../../x.ddd.json",
    "",
    "x" * 65536,
)
"""Every value spec section 5 names, with one more: a network path holding dot segments
(``//server/share/p/../../x.ddd.json``), which Task 4's ``_under`` refuses in its own words
before anything resolves it - a rule spec section 5 predates, and so a value beyond its list
that this walk owes the same hostility the rest get."""


NUMBERS: Final = tuple(
    value for value in HOSTILE if re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", value)
)
"""Each hostile value that spells a number, which the body walk sends in its own field and spells
as well into a pointer's array index: ``int()`` refuses 4,301 digits with a plain ``ValueError``,
which a pointer's grammar met before anything refused the index."""

INDEXED: Final = "project.includes[0]"
"""A well-formed pointer naming an array's element: the demo's first include, which the walk's
indexed edit writes back as it is."""

WRITTEN: Final = json.dumps("Described by the hostile walk")
"""The description the walk's well-formed edit writes, as json text: one the demo does not hold
already, so that the edit's own control sees the file change."""


def _admits_string(annotation: object) -> bool:
    """Whether a body field's own annotation can hold a string: ``str`` itself, ``Any``, ``str``
    made optional (``str | None``, as :class:`~ddd.gui.contract.Change`'s ``fingerprint`` and
    :class:`~ddd.gui.contract.Operation`'s ``raw`` are), or a ``Literal`` with a string among its
    values (:class:`~ddd.gui.contract.Operation`'s ``op``, four strings), optional or not. Anything
    else - ``int``, ``int | None``, a ``Literal`` of numbers alone, a tuple of another model -
    admits none."""
    if annotation in (str, Any):
        return True
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return any(isinstance(value, str) for value in typing.get_args(annotation))
    if origin is typing.Union or origin is types.UnionType:
        return any(_admits_string(part) for part in typing.get_args(annotation))
    return False


@pytest.mark.parametrize(
    ("annotation", "admits"),
    [
        (str, True),
        (Any, True),
        (str | None, True),
        (Literal["set", "remove"], True),
        (Literal["set", 1], True),
        (Literal["set"] | None, True),
        (int, False),
        (int | None, False),
        (Literal[1, 2], False),
        (tuple[Operation, ...], False),
    ],
)
def test_a_field_is_walked_where_its_annotation_admits_a_string(annotation, admits) -> None:
    """``Any`` holds a string, and so does a ``Literal`` with one string among numbers: a field of
    either kind is walked, as a plain ``str`` is, where a field holding none is not."""
    assert _admits_string(annotation) is admits


def _string_fields(model: type[BaseModel]) -> tuple[str, ...]:
    """Every field of ``model`` whose own annotation admits a string, in the order
    ``model_fields`` gives them - a field's kind decides whether it is walked, not a name typed
    by hand, so a string field added to ``model`` later is swept in without this file changing."""
    return tuple(
        name for name, field in model.model_fields.items() if _admits_string(field.annotation)
    )


def opened(root: Path) -> Api:
    """``ddd gui``'s api over the demo project at ``root``, opened and analysed afresh.
    ``wait_seconds=0``, as the api's own tests construct it, so ``GET /api/state`` can never
    hold this walk up."""
    session = Session(root)
    session.open(root / "demo.ddd.json")
    return Api(session, root / "demo.ddd.json", wait_seconds=0)


def demo_api(tmp_path: Path) -> tuple[Api, Path]:
    """``ddd gui``'s api over a copy of examples/demo, analysed: the session
    ``tests/test_gui_api.py``'s own hostile-value tests (``TestNoMalformedValueIsA500``,
    ``TestNoPlanValueIsA500``) already read their fixtures from, copied fresh so the walk's own
    edits never touch the shipped example."""
    root = tmp_path / "demo"
    shutil.copytree(EXAMPLES / "demo", root)
    return opened(root), root


def _files(root: Path) -> dict[Path, bytes]:
    """Every file under ``root``, with the bytes it holds."""
    return {path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _well_formed(
    root: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    """A well-formed query for every plain route, and for every action of every action route,
    over the demo project at ``root``: real values where a handler reads one this walk supplies
    - ``ValueA``, which both ``components/controller.ddd.json`` and
    ``components/sensor_hub.ddd.json`` declare, and ``CurveA``, the one object demo gives a grid
    of values - and otherwise-plausible ones a route's own tests already use, for a name demo
    declares none of: the handler then refuses it in its own words, never a crash, exactly as
    ``tests/test_gui_queries.py``'s refusal tables are built."""
    controller = (root / "components" / "controller.ddd.json").resolve().as_posix()
    demo_json = (root / "demo.ddd.json").resolve().as_posix()
    plain: dict[str, dict[str, str]] = {
        "/api/state": {},
        "/api/findings": {},
        "/api/file": {"path": demo_json},
        "/api/undo": {"at": "1"},
        "/api/variable": {"name": "ValueA"},
        "/api/names": {"text": "Value"},
        "/api/unit": {"name": "rpm"},
        "/api/settle": {"name": "ValueA", "key": "unit"},
        "/api/fix": {
            "file": controller,
            "pointer": "component.interface[0].definition",
            "check": "missing-id",
        },
        "/api/type": {"name": "X"},
        "/api/constant": {"name": "X"},
        "/api/section": {"name": "X"},
        "/api/raster": {"name": "X"},
        "/api/declarable": {"file": controller},
        "/api/values": {"name": "CurveA"},
        "/api/description-plan": {"file": controller, "name": "ParameterA", "description": "d"},
        "/api/value-plan": {"name": "CurveA", "at": "[2]", "raw": "750"},
        "/api/cells-plan": {"name": "CurveA", "at": "[0],[2]", "raw": "1300,750"},
        "/api/values-plan": {"name": "CurveA", "raw": "1,2,3,4,5,6"},
        "/api/compare": {"baseline": demo_json},
    }
    actions: dict[str, dict[str, dict[str, str]]] = {
        "/api/unit-plan": {
            "rename": {"action": "rename", "unit": "rpm", "to": "Hz"},
            "add": {"action": "add", "unit": "bar"},
            "describe": {"action": "describe", "unit": "rpm", "description": "d"},
            "remove": {"action": "remove", "unit": "rpm"},
            "adopt": {"action": "adopt"},
        },
        "/api/type-plan": {
            "set": {"action": "set", "name": "X", "key": "description", "raw": "1"},
            "rename": {"action": "rename", "name": "X", "to": "Y"},
        },
        "/api/constant-plan": {
            "set": {"action": "set", "name": "X", "key": "description", "raw": "1"},
            "rename": {"action": "rename", "name": "X", "to": "Y"},
            "add": {"action": "add", "name": "X", "raw": "1"},
            "remove": {"action": "remove", "name": "X"},
        },
        "/api/section-plan": {
            "set": {"action": "set", "name": "X", "key": "description", "raw": "1"},
            "rename": {"action": "rename", "name": "X", "to": "Y"},
            "add": {"action": "add", "name": "X", "access": '"read-write"', "alignment": "4"},
            "remove": {"action": "remove", "name": "X"},
        },
        "/api/raster-plan": {
            "set": {"action": "set", "name": "X", "key": "description", "raw": "1"},
            "rename": {"action": "rename", "name": "X", "to": "Y"},
            "add": {"action": "add", "name": "X", "event": "1"},
            "remove": {"action": "remove", "name": "X"},
        },
        "/api/files-plan": {
            "create": {"action": "create", "kind": "types", "name": "sizes"},
            "add": {"action": "add", "path": "components/extra.ddd.json"},
            "remove": {"action": "remove", "path": controller},
        },
        "/api/declaration-plan": {
            "read": {"action": "read", "file": controller, "name": "ValueA", "scope": "input"},
            "declare": {
                "action": "declare",
                "file": controller,
                "scope": "output",
                "definition": "{}",
            },
            "remove": {"action": "remove", "file": controller, "name": "ValueA"},
        },
    }
    return plain, actions


def _resolving_as_windows_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Path.resolve`` as Windows resolves a path it cannot look up, from python 3.13 on: made
    absolute against the working directory and normalised, or refused with an ``OSError`` where
    ``strict``, as ``ntpath.realpath`` does. Every other path resolves as it does on the system
    this runs on."""
    real = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        try:
            return real(self, strict)
        except ValueError as error:
            if strict:
                raise OSError(str(error)) from None
            return Path(os.path.normpath(Path.cwd() / self))

    monkeypatch.setattr(Path, "resolve", resolve)


@pytest.mark.parametrize("windows", [False, True], ids=["as-this-system-resolves", "as-windows"])
def test_every_key_of_every_route_s_query_is_never_answered_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows: bool
) -> None:
    api, root = demo_api(tmp_path)
    monkeypatch.chdir(root)
    if windows:
        _resolving_as_windows_does(monkeypatch)
    plain, actions = _well_formed(root)
    cases = 0
    for route in ROUTES:
        members = actions_of(route.query)
        if members:
            for action, member in members.items():
                baseline = actions[route.path][action]
                assert baseline["action"] == action, (route.path, action)
                for key in member.model_fields:
                    for value in HOSTILE:
                        cases += 1
                        query = {**baseline, key: value}
                        reply = api.handle(
                            route.method, route.path, {k: [v] for k, v in query.items()}, None
                        )
                        assert reply.status != 500, (route.path, key, value[:20], reply.body)
        elif route.query.model_fields:
            baseline = plain[route.path]
            for key in route.query.model_fields:
                for value in HOSTILE:
                    cases += 1
                    query = {**baseline, key: value}
                    reply = api.handle(
                        route.method, route.path, {k: [v] for k, v in query.items()}, None
                    )
                    assert reply.status != 500, (route.path, key, value[:20], reply.body)
        else:
            # A route with no query (NoQuery): one stray key, since it has none of its own.
            body = b"{}" if route.method == "POST" else None
            for value in HOSTILE:
                cases += 1
                reply = api.handle(route.method, route.path, {"zzz": [value]}, body)
                assert reply.status != 500, (route.path, "zzz", value[:20], reply.body)
    assert cases == 1342, "every route's query, every key, every hostile value: once each"


def test_every_string_field_of_a_post_body_is_never_answered_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling P18-6: every field of :class:`~ddd.gui.contract.OpenRequest`,
    :class:`~ddd.gui.contract.Changes`, :class:`~ddd.gui.contract.Change`,
    :class:`~ddd.gui.contract.Operation` and :class:`~ddd.gui.contract.UndoRequest` that
    :func:`_string_fields` finds, each sent every hostile value in an otherwise well-formed
    body - the fields found, not a list typed by hand, are what fixes this test to the models
    rather than to this file's own memory of them.

    Ruling P18-23: every case asked of the demo as the walk found it, after a control of every
    model, and none answered the fingerprint's own refusal but a case of ``fingerprint``. Every
    case is asked before any is judged, and anything the api raises is answered ``500``, as the
    server answers it, so that one run names every case that fails."""
    _, root = demo_api(tmp_path)
    monkeypatch.chdir(root)
    found = _files(root)
    target = root / "demo.ddd.json"
    demo_json = target.resolve().as_posix()

    def as_found() -> Api:
        """The demo as the walk found it: every file a case wrote given back the bytes it held,
        and a session opened afresh over them, so that no case meets what another left behind,
        in a file or in a session's history."""
        assert _files(root).keys() == found.keys(), "a case added or took away a file"
        for path, data in found.items():
            if path.read_bytes() != data:
                path.write_bytes(data)
        return opened(root)

    def edit() -> dict[str, Any]:
        # The fingerprint of the file as the walk found it, taken once: as_found() is what keeps
        # it the file's own, case after case.
        return {
            "changes": [
                {
                    "file": demo_json,
                    "fingerprint": fingerprint(found[target]),
                    "operations": [{"op": "set", "pointer": "project.description", "raw": WRITTEN}],
                }
            ],
            "label": "the description",
        }

    def indexed() -> dict[str, Any]:
        # The same edit at an array's element, what a hostile number is spelled into as an index.
        body = edit()
        operation = body["changes"][0]["operations"][0]
        operation["pointer"] = INDEXED
        operation["raw"] = json.dumps("components/*.ddd.json")
        return body

    def posted(api: Api, path: str, body: object) -> Reply:
        """What ``POST path`` is answered with ``body``; anything the api raises answered
        ``500``, as the server's own ``_answer`` answers it."""
        try:
            return api.handle("POST", path, {}, json.dumps(body).encode("utf-8"))
        except Exception as error:
            return Reply(500, {"raised": f"{type(error).__name__}: {error}"})

    # A control of each model: its well-formed body, answered as its route answers a good
    # request. Changes, Change and Operation are three levels of the one body POST /api/edit
    # takes, whose control is an edit applied; UndoRequest's is that edit put back.
    opening = posted(as_found(), "/api/open", {"path": demo_json})
    assert (opening.status, opening.body["project"]) == (
        200,
        {"path": demo_json, "name": "DemoDevice"},
    )
    api = as_found()
    written = posted(api, "/api/edit", edit())
    assert written == Reply(
        200,
        {
            "edit": 1,
            "files": [{"path": demo_json, "fingerprint": fingerprint(target.read_bytes())}],
        },
    )
    assert target.read_bytes() != found[target]
    assert json.loads(target.read_bytes())["project"]["description"] == json.loads(WRITTEN)
    assert posted(api, "/api/undo", {"at": 1}) == Reply(200, {"edit": 2})
    assert target.read_bytes() == found[target]
    # And the indexed edit, the request every case of a number spelled as an index differs from.
    assert posted(as_found(), "/api/edit", indexed()).status == 200
    # UndoRequest.at is int, the model's only field, so _string_fields finds none of it - named
    # and asserted here rather than left to be noticed by nothing below ever mentioning it.
    assert _string_fields(UndoRequest) == (), "UndoRequest has no string field: at is int"

    # The fingerprint's own refusal, as the route answers it: what a case would be answered that
    # met any file but the one found, before its own value was read.
    stale = edit()
    stale["changes"][0]["fingerprint"] = fingerprint(b"")
    refusal = posted(as_found(), "/api/edit", stale)
    assert refusal == Reply(
        409, {"error": "stale", "message": f"{target.resolve()} changed on disk since it was read"}
    )

    # Each model with a string field: the route that reads it, its well-formed body, and where in
    # that body the model's own fields sit. Operation.op is a Literal of four strings, found
    # beside pointer and raw: the gap a review of this walk's first commit found - op hardcoded
    # out of a by-hand field list - which reading the fields off each model closes by
    # construction.
    walked = (
        (OpenRequest, "/api/open", lambda: {"path": demo_json}, lambda body: body),
        (Changes, "/api/edit", edit, lambda body: body),
        (Change, "/api/edit", edit, lambda body: body["changes"][0]),
        (Operation, "/api/edit", edit, lambda body: body["changes"][0]["operations"][0]),
    )
    assert {model: _string_fields(model) for model, *_ in walked} == {
        OpenRequest: ("path",),
        Changes: ("label",),
        Change: ("file", "fingerprint"),
        Operation: ("op", "pointer", "raw"),
    }
    cases = 0
    failed: list[tuple[str, str, str]] = []
    preempted: list[tuple[str, str]] = []
    for model, path, well_formed, fields_of in walked:
        for field in _string_fields(model):
            for value in HOSTILE:
                cases += 1
                body = well_formed()
                fields_of(body)[field] = value
                reply = posted(as_found(), path, body)
                case = (f"{model.__name__}.{field}", value[:20])
                if reply.status == 500:
                    failed.append((*case, str(reply.body)[:200]))
                if reply == refusal and (model, field) != (Change, "fingerprint"):
                    preempted.append(case)
    assert NUMBERS == ("1" * 4301, "1e999")
    for value in NUMBERS:
        cases += 1
        body = indexed()
        body["changes"][0]["operations"][0]["pointer"] = INDEXED.replace("[0]", f"[{value}]")
        reply = posted(as_found(), "/api/edit", body)
        case = ("Operation.pointer, as its index", value[:20])
        if reply.status == 500:
            failed.append((*case, str(reply.body)[:200]))
        if reply == refusal:
            preempted.append(case)
    assert failed == [], "each case answered 500, or raising"
    assert preempted == [], "each case refused for the file's fingerprint before its own value"
    assert cases == 79, (
        "the seven string fields these five models hold, eleven values each, and the two "
        "numbers spelled as an index"
    )


UNOPENABLE_BASELINES: Final = ("%00", "a%00b", "base%00.ddd.json")
"""Baselines as a query spells them, each a path no file can bear."""


@pytest.mark.parametrize("windows", [False, True], ids=["as-this-system-resolves", "as-windows"])
@pytest.mark.parametrize("spelled", UNOPENABLE_BASELINES, ids=range(len(UNOPENABLE_BASELINES)))
def test_a_baseline_no_file_can_bear_is_refused_400_from_the_directory_served(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    spelled: str,
    windows: bool,
) -> None:
    """``GET /api/compare`` over the wire, with the working directory at the project's root, as
    ``run`` serves from it, and the session's root that directory: refused ``400``, saying the
    baseline is unreadable, and nothing printed on the terminal (12:M1)."""
    root = tmp_path / "demo"
    shutil.copytree(EXAMPLES / "demo", root)
    monkeypatch.chdir(root)
    session = Session(Path.cwd())
    session.open(root / "demo.ddd.json")
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "index.html").write_text("stand-in", encoding="utf-8")
    server = GuiServer(Api(session, root / "demo.ddd.json", wait_seconds=0.05), pages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if windows:
            _resolving_as_windows_does(monkeypatch)
        status, body = _ask(server, "GET", f"/api/compare?baseline={spelled}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert (status, body["error"]) == (400, "bad-request"), body
    assert body["message"].startswith("the baseline '"), body
    assert body["message"].endswith("' is unreadable"), body
    assert capsys.readouterr().err == ""


# What the start page reads of a build record (12:I4): a record's project is read under the rule a
# request's path meets, and only a description's name, whatever the record writes.


def _start_page(root: Path) -> Iterator[tuple[GuiServer, Path]]:
    """``ddd gui`` started over ``root`` with no project open, on loopback alone."""
    pages = root.parent / "pages"
    pages.mkdir(exist_ok=True)
    (pages / "index.html").write_text("stand-in", encoding="utf-8")
    server = GuiServer(Api(Session(root), None, wait_seconds=0.05), pages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, root
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def start_page(tmp_path: Path) -> Iterator[tuple[GuiServer, Path]]:
    root = tmp_path / "clone"
    write_tree(root, {"mine.ddd.json": project("Mine"), "other.json": project("Other")})
    yield from _start_page(root)


def _ask(server: GuiServer, method: str, path: str, body: object = None) -> tuple[int, Any]:
    """One request, with a client timeout so that a regression fails and never hangs."""
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    headers = {"Host": f"127.0.0.1:{server.port}", "Authorization": f"Bearer {server.token}"}
    sent = None
    if body is not None:
        sent = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Origin"] = f"http://127.0.0.1:{server.port}"
    try:
        connection.request(method, path, body=sent, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _record(root: Path, named: object) -> None:
    """A build record under ``root`` naming ``named`` as its project."""
    write_tree(root, {"build/ddd-build.json": {"format": 1, "project": named}})


def _touched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every path a read, a resolve, a stat or an open is asked for from now on."""
    asked: list[str] = []
    for name in (
        "read_bytes",
        "read_text",
        "resolve",
        "stat",
        "lstat",
        "open",
        "exists",
        "is_file",
    ):
        monkeypatch.setattr(Path, name, _watching(getattr(Path, name), asked))
    return asked


def _watching(real: Callable[..., Any], asked: list[str]) -> Callable[..., Any]:
    def spy(self: Path, *arguments: Any, **keywords: Any) -> Any:
        asked.append(self.as_posix())
        return real(self, *arguments, **keywords)

    return spy


REFUSED_RECORD_PROJECTS: Final = (
    "\\\\127.0.0.1\\share\\far.ddd.json",
    "//127.0.0.1/share/far.ddd.json",
    "//127.0.0.1/share/p/../../far.ddd.json",
    "",
    "far.ddd.json",
    "/tmp/a\x00b.ddd.json",
    "/tmp/" + "x" * 5000 + ".ddd.json",
    "C:/dir/CON.ddd.json",
    "/dir/not-a-description.json",
    "C:/dir/other.ini",
    "C:/dir",
    7,
)
"""What a record's ``project`` may be, none of which the start page reads or offers."""


REFUSED_MARKERS: Final = ("far.ddd.json", "a\x00b", "xxxx", "CON.ddd.json", "C:/dir", "/dir/not-a")
"""What no path a refused record names may appear in, as read, resolved, stat'd or opened."""


def _nothing_at_a_refused_path(asked: list[str]) -> None:
    assert not [path for path in asked if any(marker in path for marker in REFUSED_MARKERS)]


@pytest.mark.parametrize("named", REFUSED_RECORD_PROJECTS, ids=range(len(REFUSED_RECORD_PROJECTS)))
def test_a_record_naming_what_a_request_s_path_is_refused_is_read_as_no_record(
    start_page: tuple[GuiServer, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    named: object,
) -> None:
    server, root = start_page
    monkeypatch.setattr(queries_module, "_OPENS_DEVICES", True)
    _record(root, named)
    asked = _touched(monkeypatch)
    status, listed = _ask(server, "GET", "/api/projects")
    assert status == 200
    assert [p["path"] for p in listed["projects"]] == [
        (root.resolve() / "mine.ddd.json").as_posix()
    ]
    mine = f"{root.resolve().as_posix()}/mine.ddd.json"
    status, opened_ = _ask(server, "POST", "/api/open", {"path": mine})
    assert status == 200, opened_
    assert opened_["project"]["name"] == "Mine"
    assert [path for path in asked if path.endswith("ddd-build.json")], "the record was read"
    _nothing_at_a_refused_path(asked)
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("named", REFUSED_RECORD_PROJECTS, ids=range(len(REFUSED_RECORD_PROJECTS)))
def test_a_record_beside_an_opened_project_naming_what_a_request_s_path_is_refused_names_nothing(
    start_page: tuple[GuiServer, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    named: object,
) -> None:
    server, root = start_page
    monkeypatch.setattr(queries_module, "_OPENS_DEVICES", True)
    write_tree(root, {"ddd-build.json": {"format": 1, "project": named}})
    asked = _touched(monkeypatch)
    mine = f"{root.resolve().as_posix()}/mine.ddd.json"
    status, opened_ = _ask(server, "POST", "/api/open", {"path": mine})
    assert status == 200, opened_
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        _, state = _ask(server, "GET", "/api/state")
        if state["revision"] >= 1 and not state["analysing"]:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the project was never analysed")
    assert [path for path in asked if path.endswith("/ddd-build.json")], "the record was read"
    _nothing_at_a_refused_path(asked)
    assert "Traceback" not in capsys.readouterr().err


def test_a_record_naming_a_file_not_named_as_a_description_is_not_read_or_offered(
    start_page: tuple[GuiServer, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, root = start_page
    _record(root, (root / "other.json").as_posix())
    asked = _touched(monkeypatch)
    status, listed = _ask(server, "GET", "/api/projects")
    assert status == 200
    assert [p["name"] for p in listed["projects"]] == ["Mine"]
    assert not [path for path in asked if path.endswith("other.json")]


def test_a_record_naming_an_ordinary_description_still_offers_it(
    start_page: tuple[GuiServer, Path],
) -> None:
    server, root = start_page
    write_tree(root, {"build/p.ddd.json": project("Built")})
    _record(root, (root / "build" / "p.ddd.json").as_posix())
    status, listed = _ask(server, "GET", "/api/projects")
    assert status == 200
    assert {p["name"] for p in listed["projects"]} == {"Mine", "Built"}
