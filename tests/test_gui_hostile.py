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

The walk asserts no answer is 500 - never one of 400, 404 or 409 (ruling P18-7). The state
route's ``?after=`` is lenient: none of these values is a whole number, so it is answered at
once every time, and the walk's ``wait_seconds=0`` (as ``tests/test_gui_api.py``'s own fixtures
construct the api) means nothing here could wait regardless.
"""

from __future__ import annotations

import json
import shutil
import types
import typing
from pathlib import Path

from pydantic import BaseModel

from conftest import EXAMPLES
from ddd.editing import fingerprint
from ddd.gui.api import ROUTES, Api
from ddd.gui.contract import Change, Changes, OpenRequest, Operation, UndoRequest
from ddd.gui.queries import actions_of
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


def _admits_string(annotation: object) -> bool:
    """Whether a body field's own annotation can hold a string: ``str`` itself, ``str`` made
    optional (``str | None``, as :class:`~ddd.gui.contract.Change`'s ``fingerprint`` and
    :class:`~ddd.gui.contract.Operation`'s ``raw`` are), or a ``Literal`` of strings
    (:class:`~ddd.gui.contract.Operation`'s ``op``), optional or not. Anything else - ``int``,
    ``int | None``, a tuple of another model - admits none."""
    if annotation is str:
        return True
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return all(isinstance(value, str) for value in typing.get_args(annotation))
    if origin is typing.Union or origin is types.UnionType:
        return any(_admits_string(part) for part in typing.get_args(annotation))
    return False


def _string_fields(model: type[BaseModel]) -> tuple[str, ...]:
    """Every field of ``model`` whose own annotation admits a string, in the order
    ``model_fields`` gives them - a field's kind decides whether it is walked, not a name typed
    by hand, so a string field added to ``model`` later is swept in without this file changing."""
    return tuple(
        name for name, field in model.model_fields.items() if _admits_string(field.annotation)
    )


def demo_api(tmp_path: Path) -> tuple[Api, Path]:
    """``ddd gui``'s api over a copy of examples/demo, analysed: the session
    ``tests/test_gui_api.py``'s own hostile-value tests (``TestNoMalformedValueIsA500``,
    ``TestNoPlanValueIsA500``) already read their fixtures from, copied fresh so the walk's own
    edits never touch the shipped example. ``wait_seconds=0``, as the api's own tests construct
    it, so ``GET /api/state`` can never hold this walk up."""
    root = tmp_path / "demo"
    shutil.copytree(EXAMPLES / "demo", root)
    session = Session(root)
    session.open(root / "demo.ddd.json")
    return Api(session, root / "demo.ddd.json", wait_seconds=0), root


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
        "/api/variable": {"name": "ValueA"},
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
        "/api/value-plan": {"name": "CurveA", "at": "[2]", "raw": "750"},
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


def test_every_key_of_every_route_s_query_is_never_answered_500(tmp_path: Path) -> None:
    api, root = demo_api(tmp_path)
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
    assert cases == 1254, "every route's query, every key, every hostile value: once each"


def test_every_string_field_of_a_post_body_is_never_answered_500(tmp_path: Path) -> None:
    """Ruling P18-6: every field of :class:`~ddd.gui.contract.OpenRequest`,
    :class:`~ddd.gui.contract.Changes`, :class:`~ddd.gui.contract.Change`,
    :class:`~ddd.gui.contract.Operation` and :class:`~ddd.gui.contract.UndoRequest` that
    :func:`_string_fields` finds, each sent every hostile value in an otherwise well-formed
    body - the fields found, not a list typed by hand, are what fixes this test to the models
    rather than to this file's own memory of them."""
    api, root = demo_api(tmp_path)
    demo_json = (root / "demo.ddd.json").resolve().as_posix()
    target = root / "demo.ddd.json"
    description = json.dumps("Demonstration project showing every kind of data object")

    def well_formed_edit() -> dict[str, object]:
        # The fingerprint is re-read fresh every call: an earlier case in this same walk may
        # already have written it (a label, a pointer or a raw the engine accepts changes it),
        # and one read once up front would then be stale for every case after the first - a
        # 409, never a 500, but not the field under test either.
        return {
            "changes": [
                {
                    "file": demo_json,
                    "fingerprint": fingerprint(target.read_bytes()),
                    "operations": [
                        {"op": "set", "pointer": "project.description", "raw": description}
                    ],
                }
            ],
            "label": "x",
        }

    # UndoRequest.at is int, the model's only field, so _string_fields finds none of it - named
    # and asserted here rather than left to be noticed by nothing below ever mentioning it.
    assert _string_fields(UndoRequest) == (), "UndoRequest has no string field: at is int"

    cases = 0
    open_fields = _string_fields(OpenRequest)
    assert open_fields == ("path",)
    for field in open_fields:
        for value in HOSTILE:
            cases += 1
            body = json.dumps({field: value}).encode("utf-8")
            reply = api.handle("POST", "/api/open", {}, body)
            assert reply.status != 500, (f"OpenRequest.{field}", value[:20], reply.body)

    changes_fields = _string_fields(Changes)
    assert changes_fields == ("label",)
    for field in changes_fields:
        for value in HOSTILE:
            cases += 1
            body = well_formed_edit()
            body[field] = value
            reply = api.handle("POST", "/api/edit", {}, json.dumps(body).encode("utf-8"))
            assert reply.status != 500, (f"Changes.{field}", value[:20], reply.body)

    change_fields = _string_fields(Change)
    assert change_fields == ("file", "fingerprint")
    for field in change_fields:
        for value in HOSTILE:
            cases += 1
            body = well_formed_edit()
            body["changes"][0][field] = value
            reply = api.handle("POST", "/api/edit", {}, json.dumps(body).encode("utf-8"))
            assert reply.status != 500, (f"Change.{field}", value[:20], reply.body)

    # Operation.op is a Literal of four strings, found beside pointer and raw: the gap a review
    # of this walk's first commit found - op hardcoded out of a by-hand field list - which
    # reading the field off the model, as every other field here now is, closes by construction.
    operation_fields = _string_fields(Operation)
    assert operation_fields == ("op", "pointer", "raw")
    for field in operation_fields:
        for value in HOSTILE:
            cases += 1
            body = well_formed_edit()
            body["changes"][0]["operations"][0][field] = value
            reply = api.handle("POST", "/api/edit", {}, json.dumps(body).encode("utf-8"))
            assert reply.status != 500, (f"Operation.{field}", value[:20], reply.body)

    assert cases == 77, "the seven string fields these five models hold, once each"
