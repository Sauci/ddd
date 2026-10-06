"""How deep json may nest in ``ddd gui``: the serializer's own limit, measured on the system the
suite runs on, every bound read against it, and the net every answer is written through."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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

ANYTHING = TypeAdapter(Any)


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


def test_every_answer_of_the_api_is_written_through_the_net() -> None:
    """No route dumps an answer of its own: each is written by :func:`~ddd.gui.depth.written`,
    which counts it first, so that a route added later is covered without a test of its own. The
    two dumps left read a plan's own query, not an answer."""
    api = (Path(__file__).parents[1] / "src" / "ddd" / "gui" / "api.py").read_text(encoding="utf-8")
    assert re.findall(r"(\w+)\.model_dump\(", api) == ["asked", "asked"]
