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

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import TypeAdapter

from ddd.editing import Operation
from ddd.loading import included_files, resolve_path
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.constants import ConstantValue

CONSTANTS_FILE: Final = "constants.ddd.json"
"""The constants file ``add_constant`` writes for a project that has none, beside its description.

Named as :data:`ddd.lsp.units.ADOPTED` names the units file adoption writes, and for the same
reason: whoever opens the checkout afterwards should be able to tell what the file is from its
name.
"""

SETTABLE: Final = frozenset({"value", "description"})
"""What the interface may set on a constant's entry. ``name`` is not one of them: changing a name
is a rename, which has to rewrite every shape naming it in the same edit."""

_VALUE: Final[TypeAdapter[ConstantValue]] = TypeAdapter(ConstantValue)
"""The format's own judge of what a constant may hold, so that the interface and the loader cannot
come to different answers. Strict on both arms, which is what keeps ``2`` a whole constant and
``2.0`` a fractional one."""


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


def set_constant(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> SharedPlan:
    """``key`` of that constant's entry set to the json text ``raw``, or taken away where ``raw``
    is ``None``.

    ``raw`` is trusted to be json: the api parses it with :func:`ddd.editing.parse_raw` and answers
    ``bad-request`` for text that is not, the way ``GET /api/settle`` already does - a malformed
    request is not a refusal about the project.

    A ``value`` may not be taken away, and one the format would refuse is refused here: written,
    the file would stop loading and every tab would empty because of one keystroke in this one. A
    ``description`` already left out answers no edit at all rather than a removal, as
    :func:`ddd.type_plans.set_key` also does for a type: there is nothing to remove, and a reader
    who has only selected the row - not typed anything - must not be refused before they have.
    """
    entry = _entry(built, name)
    if key not in SETTABLE:
        raise SharedRefusalError(
            "invalid",
            f"a constant has no '{key}' to set in {entry.path.name}: it states "
            f"{' and '.join(sorted(SETTABLE))}",
        )
    if key == "value":
        if raw is None:
            raise SharedRefusalError(
                "invalid",
                f"a constant states a value, so '{name}' cannot be left without one in "
                f"{entry.path.name}",
            )
        _value(raw, name, entry.path)
        return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})
    if raw is None:
        if read(entry.path, cache).value_at(f"{entry.pointer}.{key}") is None:
            return SharedPlan(())
        return _plan({entry.path: [Operation("remove", f"{entry.pointer}.{key}")]})
    return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})


def remove_constant(built: Index, name: str, cache: dict[Path, Document]) -> SharedPlan:
    """That constant's entry taken out of the list holding it.

    Refused while any shape names it. Removed, each of those shapes would name nothing, which is
    an ``unknown-constant`` apiece in files the reader was not looking at - a worse answer than
    saying no. What is in use is asked of the index, never of a file's text: reading text to answer
    a question about meaning is the mistake part 11 filed against ``variable_keys._storage_of``.
    """
    entry = _entry(built, name)
    used = built.constant_uses.get(name, ())
    if used:
        raise SharedRefusalError(
            "invalid",
            f"'{name}' is named by {_plural(len(used), 'shape')}, the first in "
            f"{used[0].path.name}; nothing may name it before it goes",
        )
    return _plan({entry.path: [Operation("remove", entry.pointer)]})


def _entry(built: Index, name: str) -> Site:
    """Where that constant is declared, or a refusal saying nothing declares it."""
    entry = built.constants.get(name)
    if entry is None:
        raise SharedRefusalError(
            "not-found", f"no file of this project declares a constant called '{name}'"
        )
    return entry


def _value(raw: str, name: str, file: Path) -> None:
    """Refuse a value the format would not take, naming the file it would have been written to."""
    try:
        _VALUE.validate_python(json.loads(raw))
    except (ValueError, TypeError) as refused:
        raise SharedRefusalError(
            "invalid",
            f"{raw} is not a value a constant may state, so '{name}' cannot take it in "
            f"{file.name}: a whole number a 64 bit target holds, of either sign, or a finite "
            f"fractional one",
        ) from refused


def _plan(operations: Mapping[Path, Sequence[Operation]]) -> SharedPlan:
    """One edit per file, sorted by path, as :class:`SharedPlan` promises and the interface applies
    them."""
    return SharedPlan(
        tuple(
            PlannedEdit(path, tuple(operations[path]))
            for path in sorted(operations, key=Path.as_posix)
        )
    )


def _plural(count: int, noun: str) -> str:
    """ "1 shape", "2 shapes" - the wording `remove_constant` names a blocking use's count with."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _raw(value: Any) -> str:
    """A value as the json text an operation carries, every character as written: a description
    holding a degree sign arrives in the file as one, where json's default would write an
    escape."""
    return json.dumps(value, ensure_ascii=False)
