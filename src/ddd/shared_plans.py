"""What changing one of a project's constants takes, planned and never written.

Transport-neutral, like :mod:`ddd.project_shared` beside it: nothing here knows about http or the
session. A rename is the editor's rename - :func:`ddd.lsp.navigation.rename_sites` says which
strings it has to rewrite, :func:`~ddd.lsp.navigation.rename_problem` says why a name may not be
used - for the reason :mod:`ddd.type_plans` borrows them both: two clients that renamed a constant
differently would disagree about what a project means, and the one reaching fewer files would
leave it broken across several at once.

Every value travels as the json text its author wrote. :data:`ddd.models.constants.ConstantValue`
is strict on both arms and refuses a whole number in the fractional one, so ``2`` and ``2.0`` are
two different constants; a plan that parsed a value and wrote it back would retype one nobody
asked it to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.loading import included_files, resolve_path
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit

CONSTANTS_FILE: Final = "constants.ddd.json"
"""The constants file ``add_constant`` writes for a project that has none, beside its description.

Named as :data:`ddd.lsp.units.ADOPTED` names the units file adoption writes, and for the same
reason: whoever opens the checkout afterwards should be able to tell what the file is from its
name.
"""

SETTABLE: Final = frozenset({"value", "description"})
"""What the interface may set on a constant's entry. ``name`` is not one of them: changing a name
is a rename, which has to rewrite every shape naming it in the same edit."""


@dataclass(frozen=True, slots=True)
class SharedProject:
    """What a plan has to know of the project besides its index: where its constants are kept,
    and which of its files did not load."""

    project: Path
    """The project description, resolved."""

    constants_files: tuple[Path, ...]
    """Its constants files, in the order its ``project.includes`` lists them, each listed once:
    the first is where a new constant goes, so that it lands in the file a run of ``ddd check``
    reads first."""

    unread: tuple[Path, ...]
    """The project's files that did not load, resolved and sorted."""


@dataclass(frozen=True, slots=True)
class SharedPlan:
    """Everything one change of a constant takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class SharedRefusalError(Exception):
    """A change of a constant that cannot be planned, and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``unreadable``: a file the change has to see did not load. ``invalid``: the change cannot
    be made - a key a constant has not, a name that may not be used, a constant a shape still
    names. ``not-found``: no file of the project declares a constant of that name."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def shared_project(
    project: Path, unread: Sequence[Path], cache: dict[Path, Document]
) -> SharedProject:
    """The project a constant's plans are made in: its description, its constants files and the
    files of it that did not load.

    The constants files come out of the description's own ``includes``, each entry expanded by the
    loader's rule, so that the first of them is the first a run of ``ddd check`` reads. A
    constants file is a document with ``constants`` at its top, which is how the loader tells one;
    a file that does not parse is none, since what it is cannot be told - and a new entry must not
    be appended to a file nobody could read.
    """
    path = resolve_path(project)
    listed = read(path, cache).value_at("project.includes")
    found: list[Path] = []
    for entry in listed if isinstance(listed, list) else ():
        for file in included_files(path, entry):
            document = read(file, cache).data
            if file not in found and isinstance(document, dict) and "constants" in document:
                found.append(file)
    return SharedProject(
        path,
        tuple(found),
        tuple(sorted({resolve_path(file) for file in unread}, key=Path.as_posix)),
    )
