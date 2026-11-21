"""What a plan is: the operations a change of the project takes, file by file, and the refusal of
a change that cannot be planned.

Transport-neutral, like the modules that plan each change, and planning nothing itself. A unit's
change is planned by :mod:`ddd.lsp.units`, a type's by :mod:`ddd.type_plans`, an entry's of the
Shared files tab by :mod:`ddd.shared_plans`, a declaration's by :mod:`ddd.declaration_plans` and
a value's by :mod:`ddd.object_values`: each answers a :class:`Plan` or raises a
:class:`PlanRefusalError`, and which code it refuses with, and when, its own module says.
:mod:`ddd.file_plans` writes a change of the project's own ``includes`` in the same edits, and
answers more beside them.

One plan and one refusal for every family of plans, rather than a plan and a refusal of one shape
apiece in each module: ``ddd gui`` previews and answers each family alike, and a new family copied
the shapes of the one beside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ddd.editing import Operation


@dataclass(frozen=True, slots=True)
class PlannedEdit:
    """The operations one file takes, in the order they are made."""

    path: Path
    operations: tuple[Operation, ...]
    creates: bool = False
    """The plan creates this file: ``operations`` is one ``set`` at the root, carrying it whole."""


@dataclass(frozen=True, slots=True)
class Plan:
    """Everything one change takes: one edit per file, sorted by path - so that one function
    previews every family's plan (:func:`ddd.project_units.previewed`), and the language server
    renders a unit's as the text edits of a rename (:func:`ddd.lsp.units.text_edits`)."""

    edits: tuple[PlannedEdit, ...]


class PlanRefusalError(Exception):
    """A change that cannot be planned - or, for an object's values, a grid that cannot be shown -
    and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found", "stale"]
    """``unreadable``: a file the change has to see did not load, so what it holds is unknown.
    ``invalid``: the change cannot be made - a key, a value or a name it may not take, or a project
    it cannot be made in. ``not-found``: what the change is of is not there to change - a name the
    project does not declare, a file to add that is not there. ``stale``: a file the change points
    into no longer holds what the index found there, having changed since the analysis read it."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns where there is one."""

    def __init__(
        self, code: Literal["unreadable", "invalid", "not-found", "stale"], message: str
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
