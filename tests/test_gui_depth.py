"""How deep json may nest in ``ddd gui``: the serializer's own limit, measured on the system the
suite runs on, every bound read against it, and the net every answer is written through."""

from __future__ import annotations

import ast
import inspect
import re
import typing
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ddd.gui import contract
from ddd.gui.depth import (
    FILE_DEPTH,
    OBJECT_BLOCK_DEPTH,
    PROJECT_BLOCK_DEPTH,
    SERIALIZED_DEPTH,
    TooDeepError,
    counted,
    nesting,
    written,
)
from ddd.ir import DataDictionary
from ddd.models.conversion import Conversion

ANYTHING = TypeAdapter(Any)

API: Final = Path(__file__).parents[1] / "src" / "ddd" / "gui" / "api.py"

DUMPS: Final = ("model_dump", "model_dump_json", "dump_python", "dump_json")
"""The dumps of pydantic's own models and adapters - a model's ``model_dump`` and
``model_dump_json``, an adapter's ``dump_python`` and ``dump_json`` - each running the serializer
the net counts for: read in api.py wherever they are named, an attribute called or not, a name,
or a string."""

RETIRED: Final = ("dict", "json")
"""pydantic 1's dumps, which a model of pydantic 2 still answers: read as an attribute alone. As a
name or a string each is python's own as well - its type and its module, and the json mode of
every dump - and is not read."""

PLAN_READS: Final = [
    ("_raster_plan_of", "asked.model_dump"),
    ("_section_plan_of", "asked.model_dump"),
]
"""The two dumps api.py makes that are no answer: each reads a plan's own query, a model of a few
strings, as the keys an ``add`` was given."""


def around(depth: int) -> Any:
    """A number under lists, ``depth`` levels deep as pydantic-core counts them - the number at the
    bottom one of them: ``0`` is one level, ``[0]`` two."""
    value: Any = 0
    for _ in range(depth - 1):
        value = [value]
    return value


def deepest_written() -> int:
    """The most levels the running pydantic-core writes in an untyped field: a number under lists,
    bisected in at most nine dumps."""
    low, high = 1, 511
    while low < high:
        middle = (low + high + 1) // 2
        try:
            ANYTHING.dump_python(around(middle), mode="json")
        except ValueError:
            high = middle - 1
        else:
            low = middle
    return low


def test_the_running_serializer_writes_every_bound_with_its_envelope() -> None:
    """The premise every bound rests on, measured on the system the suite runs on: 99 levels on
    CI's windows legs, 255 on the others. Each bound fits it with the levels its reply wraps
    around what it bounds - none around a file, the dictionary's ``extensions`` around the
    project's settings, its ``objects``, the object and its ``extensions`` around an object's
    block - and each reply at its bound is written."""
    measured = deepest_written()
    assert measured >= SERIALIZED_DEPTH
    assert measured >= FILE_DEPTH + 0
    assert measured >= PROJECT_BLOCK_DEPTH + 1
    assert measured >= OBJECT_BLOCK_DEPTH + 3
    contract.FileContent(
        path="/p.ddd.json", fingerprint="0", data=around(FILE_DEPTH), error=None
    ).model_dump(mode="json")
    settings = {"deep": {"v": around(PROJECT_BLOCK_DEPTH - 1)}}
    contract.DictionaryReply(revision=1, dictionary={"extensions": settings}).model_dump(
        mode="json"
    )
    stamped = {"deep": {"v": around(OBJECT_BLOCK_DEPTH - 1)}}
    contract.DictionaryReply(
        revision=1, dictionary={"objects": [{"extensions": stamped}]}
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    "value",
    [0, "x", None, [], {}, [0], {"a": 0}, {"a": {"b": None}}, [[], [0]], ({"k": [1]},)],
    ids=[
        "number",
        "string",
        "none",
        "list",
        "object",
        "a-number-in-a-list",
        "a-number-under-a-key",
        "none-under-two-keys",
        "the-deeper-of-two",
        "a-tuple",
    ],
)
def test_a_value_is_counted_as_the_serializer_counts_it(value: Any) -> None:
    """Every value counts, a number, a string or ``None`` as much as a list, and a key does not:
    wrapped in lists to exactly the most levels the running serializer writes, by this count, a
    value is written, and a list more is not."""
    limit = deepest_written()
    wrapped = value
    for _ in range(limit - nesting(value)):
        wrapped = [wrapped]
    ANYTHING.dump_python(wrapped, mode="json")
    with pytest.raises(ValueError, match=re.escape("Circular reference detected")):
        ANYTHING.dump_python([wrapped], mode="json")


class Inner(BaseModel):
    data: Any


class Outer(BaseModel):
    once: Inner
    many: tuple[Inner, ...] = ()
    named: dict[str, Any] | None = None
    text: str = ""


class Paired(BaseModel):
    pair: tuple[int, Any]


@pytest.mark.parametrize(
    ("reply", "levels"),
    [
        (contract.FileContent(path="/p", fingerprint="0", data=around(7), error=None), 7),
        (contract.DictionaryReply(revision=1, dictionary={"a": around(7)}), 7),
        (contract.DictionaryReply(revision=1, dictionary=None), 0),
        (Outer(once=Inner(data=around(7))), 8),
        (Outer(once=Inner(data=0), many=(Inner(data=around(7)),)), 8),
        (Outer(once=Inner(data=0), named={"k": around(7)}), 7),
        (Paired(pair=(1, around(7))), 7),
    ],
    ids=[
        "untyped",
        "a-typed-mapping-of-untyped",
        "none",
        "a-model",
        "models-in-a-tuple",
        "mixed",
        "a-tuple-of-fixed-length",
    ],
)
def test_the_net_counts_every_level_the_serializer_counts(reply: BaseModel, levels: int) -> None:
    """An untyped value as the serializer counts it, every value along the way; a typed mapping
    or tuple not at all, as the serializer does not count one; a model nested in another one
    level more - which the serializer counts where it reaches the model through a definition
    it shares with another field, and so may - and the answer itself not at all."""
    assert counted(reply) == levels


@pytest.mark.parametrize(
    "make",
    [
        lambda depth: contract.FileContent(
            path="/p.ddd.json", fingerprint="0", data=around(depth), error=None
        ),
        lambda depth: contract.DictionaryReply(revision=1, dictionary={"a": around(depth)}),
        lambda depth: Outer(once=Inner(data=0), many=(Inner(data=around(depth - 1)),)),
    ],
    ids=["a-file", "the-dictionary", "a-nested-model"],
)
def test_the_net_writes_an_answer_at_its_bound_and_refuses_one_a_level_deeper(make) -> None:
    """At the bound, on every system - Windows' 99 among them, which CI's windows legs run this
    on - the answer is written; a level deeper, it is refused before anything writes it."""
    assert written(make(SERIALIZED_DEPTH)) == make(SERIALIZED_DEPTH).model_dump(mode="json")
    with pytest.raises(TooDeepError) as refused:
        written(make(SERIALIZED_DEPTH + 1))
    assert str(refused.value) == (
        "this answer is nested more than 99 levels deep, deeper than ddd gui can show"
    )


class Aliased(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    written_as: int = Field(0, alias="writtenAs")


def test_the_net_passes_what_it_is_given_to_the_dump() -> None:
    """``GET /api/graph`` is written by its fields' aliases."""
    assert written(Aliased(written_as=1), by_alias=True) == {"writtenAs": 1}


class _Reader(ast.NodeVisitor):
    """What :func:`unwritten` finds, read off one syntax tree, each with the function it lies in."""

    def __init__(self) -> None:
        self.function = ""
        self.found: list[tuple[str, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        outer, self.function = self.function, node.name
        self.generic_visit(node)
        self.function = outer

    def visit_Return(self, node: ast.Return) -> None:
        if self.function == "_session_body" and not _through_the_net(node.value):
            self.found.append((self.function, f"return {_shown(node.value)}"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "Reply":
            body = node.args[1]
            if not self._answered(body):
                self.found.append((self.function, f"Reply body {_shown(body)}"))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in (*DUMPS, *RETIRED):
            self.found.append((self.function, ast.unparse(node)))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in DUMPS:
            self.found.append((self.function, node.id))

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value in DUMPS:
            self.found.append((self.function, repr(node.value)))

    def _answered(self, body: ast.expr) -> bool:
        """Whether a ``Reply``'s body is one the net wrote: a ``written(...)`` call, the session's
        own answer, or - in ``_error`` alone - its dict of two strings."""
        if _through_the_net(body):
            return True
        if ast.unparse(body) == "self._session_body()":
            return True
        return self.function == "_error" and ast.unparse(body) == (
            "{'error': code, 'message': message}"
        )


def _through_the_net(node: ast.expr | None) -> bool:
    """Whether ``node`` is a call of the net itself, ``written(...)``."""
    return (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "written"
    )


def _shown(node: ast.expr | None) -> str:
    """A body as a finding names it: a call by what it calls."""
    if isinstance(node, ast.Call):
        return f"{ast.unparse(node.func)}(...)"
    return "nothing" if node is None else ast.unparse(node)


def unwritten(source: str) -> list[tuple[str, str]]:
    """Every place ``source`` - api.py's text - answers, or dumps, other than through the net,
    each with the function it lies in, sorted: a ``Reply`` whose body is not a ``written(...)``
    call, the session's own answer or ``_error``'s own dict; a return of the session's own
    answer that is not a ``written(...)`` call; and every naming of a dump - an attribute of
    :data:`DUMPS` or :data:`RETIRED`, whatever it is an attribute of and whether it is called or
    not, and a name or a string of :data:`DUMPS` - wherever it lies, inside a ``written(...)``
    call's argument as much as anywhere, since a dump there runs before the net counts anything.
    Not read: pydantic-core's own functions, a model's ``__pydantic_serializer__``,
    :data:`RETIRED` asked for as a string, and a dump's name put together at run time."""
    reader = _Reader()
    reader.visit(ast.parse(source))
    return sorted(reader.found)


def test_every_answer_of_the_api_is_written_through_the_net() -> None:
    """Every ``Reply`` of api.py answers a body :func:`~ddd.gui.depth.written` wrote, which
    counts an answer before writing it - a ``written(...)`` call, the session's own answer,
    itself one, or ``_error``'s dict of two strings - and no dump of :data:`DUMPS` or
    :data:`RETIRED` is named there but the two reading a plan's own query (:data:`PLAN_READS`).
    Read off api.py's syntax tree, so that a route added later is held to the net as every route
    there is, in whichever of these ways it would dump its answer
    (:func:`test_an_answer_written_any_other_way_is_found`)."""
    assert unwritten(API.read_text(encoding="utf-8")) == PLAN_READS


UNDO: Final = "return Reply(200, written(contract.UndoReply(edit=number)))"
"""How ``_apply_undo`` answers: the route most spellings below are tried in."""

INNER: Final = "dictionary=None if dictionary is None else written(dictionary),"
"""How ``_dictionary`` writes the dictionary it answers, inside the answer's own ``written(...)``:
the place a dump runs before the net counts anything, where the rest are tried."""

READ: Final = "        dictionary = revision.dictionary\n"
"""Where ``_dictionary`` reads the dictionary, for a spelling that names something first."""


@pytest.mark.parametrize(
    ("swaps", "found"),
    [
        pytest.param(
            [(UNDO, 'return Reply(200, contract.UndoReply(edit=number).model_dump(mode="json"))')],
            [
                ("_apply_undo", "Reply body contract.UndoReply(edit=number).model_dump(...)"),
                ("_apply_undo", "contract.UndoReply(edit=number).model_dump"),
            ],
            id="the-old-spelling",
        ),
        pytest.param(
            [
                (
                    UNDO,
                    "return Reply(200, json.loads(contract.UndoReply(edit=number)"
                    ".model_dump_json()))",
                )
            ],
            [
                ("_apply_undo", "Reply body json.loads(...)"),
                ("_apply_undo", "contract.UndoReply(edit=number).model_dump_json"),
            ],
            id="as-json-text",
        ),
        pytest.param(
            [
                (
                    UNDO,
                    "return Reply(200, UNDONE.dump_python(contract.UndoReply(edit=number), "
                    'mode="json"))',
                )
            ],
            [
                ("_apply_undo", "Reply body UNDONE.dump_python(...)"),
                ("_apply_undo", "UNDONE.dump_python"),
            ],
            id="through-an-adapter",
        ),
        pytest.param(
            [
                (
                    UNDO,
                    "return Reply(200, json.loads(UNDONE.dump_json("
                    "contract.UndoReply(edit=number))))",
                )
            ],
            [
                ("_apply_undo", "Reply body json.loads(...)"),
                ("_apply_undo", "UNDONE.dump_json"),
            ],
            id="through-an-adapter-as-json-text",
        ),
        pytest.param(
            [(UNDO, 'return Reply(200, {"edit": number})')],
            [("_apply_undo", "Reply body {'edit': number}")],
            id="a-body-of-its-own",
        ),
        pytest.param(
            [
                (
                    INNER,
                    "dictionary=None if dictionary is None else "
                    'dictionary.model_dump(mode="json"),',
                )
            ],
            [("_dictionary", "dictionary.model_dump")],
            id="a-dump-inside-the-net",
        ),
        pytest.param(
            [
                (
                    INNER,
                    "dictionary=None if dictionary is None else "
                    'getattr(dictionary, "model_dump")(mode="json"),',
                )
            ],
            [("_dictionary", "'model_dump'")],
            id="a-dump-asked-for-by-its-name",
        ),
        pytest.param(
            [
                (READ, f"{READ}        dump = dictionary.model_dump if dictionary else None\n"),
                (INNER, 'dictionary=None if dump is None else dump(mode="json"),'),
            ],
            [("_dictionary", "dictionary.model_dump")],
            id="a-bound-method-named-first",
        ),
        pytest.param(
            [(INNER, "dictionary=None if dictionary is None else model_dump(dictionary),")],
            [("_dictionary", "model_dump")],
            id="a-dump-by-a-name-of-its-own",
        ),
        pytest.param(
            [(INNER, "dictionary=None if dictionary is None else dictionary.dict(),")],
            [("_dictionary", "dictionary.dict")],
            id="pydantic-1-s-dict",
        ),
        pytest.param(
            [(INNER, "dictionary=None if dictionary is None else json.loads(dictionary.json()),")],
            [("_dictionary", "dictionary.json")],
            id="pydantic-1-s-json",
        ),
        pytest.param(
            [
                (
                    "        return written(\n            contract.SessionInfo(",
                    "        return dict(\n            contract.SessionInfo(",
                )
            ],
            [("_session_body", "return dict(...)")],
            id="the-session-s-own-answer",
        ),
        pytest.param(
            [
                (
                    'return Reply(status, {"error": code, "message": message})',
                    'return Reply(status, {"error": code, "message": message, "at": where})',
                )
            ],
            [("_error", "Reply body {'error': code, 'message': message, 'at': where}")],
            id="an-error-carrying-more",
        ),
        pytest.param(
            [(UNDO, 'return Reply(409, {"error": code, "message": message})')],
            [("_apply_undo", "Reply body {'error': code, 'message': message}")],
            id="an-error-of-its-own",
        ),
    ],
)
def test_an_answer_written_any_other_way_is_found(
    swaps: list[tuple[str, str]], found: list[tuple[str, str]]
) -> None:
    """api.py with one answer written another way - the first as every answer was written before
    the net, ``.model_dump(`` after a call - is found wherever it differs from the net, with the
    function it lies in: a dump called, named first, or asked for by its name as a string, as an
    answer or inside one. ``UNDONE`` would be a ``TypeAdapter``, ``model_dump`` a function of
    that name, ``where`` anything at all."""
    source = API.read_text(encoding="utf-8")
    for answered, spelled in swaps:
        assert source.count(answered) == 1
        source = source.replace(answered, spelled)
    assert unwritten(source) == sorted([*PLAN_READS, *found])


def shared(model: type[BaseModel]) -> set[str]:
    """Each definition ``model``'s serializer shares between the places using it that is not a
    model, by its qualified name - which the serializer counts a level at each place, and
    :func:`~ddd.gui.depth.counted` never does. Read off the core schema's own ``definitions``,
    where pydantic gathers every definition a model's schema shares."""
    schema = model.__pydantic_core_schema__
    if schema["type"] != "definitions":
        return set()
    return {
        definition["ref"].split(":")[0]
        for definition in schema["definitions"]
        if definition["type"] != "model"
    }


def test_no_answer_shares_a_definition_the_net_does_not_count_but_the_two_inits() -> None:
    """:func:`~ddd.gui.depth.counted`'s premise: the serializer counts a level for each shared
    definition it passes through, a model or not, and the net counts every nested model and
    no other definition - so it is a bound only while every other definition an answer shares
    is one it reads as untyped, every value under it counted. Two are, ``InitElement`` and
    ``InitScalar``, an object's ``init``; another, in any model an answer is written from - the
    contract's, the dictionary's or a conversion's - fails this test, which then wants the net
    shown to count it."""
    models = [
        model
        for _, model in inspect.getmembers(contract, inspect.isclass)
        if issubclass(model, BaseModel) and model.__module__ == contract.__name__
    ]
    conversions = typing.get_args(typing.get_args(Conversion)[0])
    answered = [*models, DataDictionary, *conversions]
    assert set().union(*(shared(model) for model in answered)) == {
        "ddd.models.objects.InitElement",
        "ddd.models.objects.InitScalar",
    }
