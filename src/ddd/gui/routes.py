"""The routes of the ddd gui api: what each takes and does, in one table the dispatcher reads.

The table itself, :data:`ddd.gui.api.ROUTES`, is filled where :class:`~ddd.gui.api.Api` is
defined, each route's answer being one of its methods; what a route is, and how a query is read
off a request before its model reads it, are here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from ddd.gui.api import Api, Reply


@dataclass(frozen=True, slots=True)
class Policy:
    """What a route does besides answering: whether it writes, opens a project, runs plugins or
    waits."""

    writes: bool = False
    """It writes files of the open project: an edit, or one put back."""

    opens: bool = False
    """It opens a project, which the session then analyses."""

    runs_plugins: bool = False
    """Its answer, or the analysis it asks for, may run a plugin's code: a project it opens, an
    edit or an undo the session then analyses, a baseline it compares, and a plan judged by
    analysing the project with its includes changed."""

    waits: bool = False
    """It may hold its answer until something changes: the state's long poll."""


@dataclass(frozen=True, slots=True)
class Route:
    """One route of the api: a path and a method, what it takes, and what answers it."""

    path: str
    method: str

    query: type[BaseModel]
    """The model its query is read as: one of :mod:`ddd.gui.queries`, or a ``RootModel`` over a
    union of them, one model per action, discriminated by ``action``."""

    body: type[BaseModel] | None
    """The model a ``POST``'s body is read as; ``None`` for a route that takes no body."""

    answer: Callable[[Api, Any, Any], Reply]
    """The handler: an :class:`~ddd.gui.api.Api` method taking the query its own ``query``
    model read and the body its ``body`` model read, each validated before it is called."""

    policy: Policy = Policy()

    @property
    def name(self) -> str:
        """How the route's sentences call it: its path's last segment."""
        return self.path.rsplit("/", 1)[1]


def one_value_each(query: Mapping[str, Sequence[str]], route: str) -> dict[str, str] | str:
    """The query's values, one a key, or the sentence refusing the first key given twice."""
    values: dict[str, str] = {}
    for key, given in query.items():
        if len(given) != 1:
            return f"{route} takes ?{key}= once"
        values[key] = given[0]
    return values
