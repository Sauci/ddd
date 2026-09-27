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

from ddd.editing import DEFAULT_INDENT_UNIT, Operation, lay_out
from ddd.loading import included_files, resolve_path
from ddd.lsp.navigation import Index, Site, rename_problem, rename_sites
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

_DESCRIPTION: Final[TypeAdapter[str]] = TypeAdapter(str)
"""The format's own judge of what a description may hold: any string, and nothing else -
``ConstantDeclaration.description`` is a plain ``str``, so this need only refuse what a string can
never be: a number, a bool, ``null``, an array, an object."""


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
    ``description`` given is checked the same way, against the same consequence: unguarded,
    ``?action=set&key=description&raw=123`` planned ``"description": 123`` - a number where the
    model wants a string - and the file it landed in stopped loading, emptying every tab in the
    page over one keystroke, exactly the failure the ``value`` check exists to prevent. A
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
    _description(raw, name, entry.path)
    return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})


def rename_constant(built: Index, name: str, to: str, cache: dict[Path, Document]) -> SharedPlan:
    """What renaming a constant takes: its own ``name`` and every shape spelling it.

    The editor's rename, asked for rather than reimplemented. :func:`ddd.lsp.navigation.
    rename_sites` knows the three places a shape is written and
    :func:`~ddd.lsp.navigation.rename_problem` knows why a name may not be used - with
    ``Index.occupied`` already holding *the name of the declared constant* - so the tab and the
    editor cannot disagree about what a rename reaches or which names it refuses.

    Refused before a file is touched: a rename writes into every file naming the constant, and a
    name that turned out to be unusable would leave the project broken across all of them at once.
    """
    _entry(built, name)
    problem = rename_problem(built, to, "constant")
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    by_file: dict[Path, list[Operation]] = {}
    for site in rename_sites(built, "constant", name):
        by_file.setdefault(site.path, []).append(Operation("set", site.pointer, _raw(to)))
    return _plan(by_file)


def add_constant(
    built: Index, project: SharedProject, name: str, raw: str, cache: dict[Path, Document]
) -> SharedPlan:
    """``name`` declared with the value ``raw``: appended to the first constants file the project
    includes, or written into a new one beside the project description where it includes none.

    One verb, where the units vocabulary has two. :func:`ddd.lsp.units.adopt_units` harvests the
    units already in use into a new file; the constants in use are exactly the ones
    ``unknown-constant`` complains about, and a value cannot be harvested - nothing in the project
    says what the length of an array is. So this creates the file when there is none, and there is
    nothing to adopt.

    ``raw`` is embedded as the text it was given rather than parsed and reprinted: ``2.0`` declares
    a fractional constant and ``2`` a whole one, and a reader asking for one would otherwise get
    the other.
    """
    problem = rename_problem(built, name, "constant")
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    if not project.constants_files:
        return _created(project, name, raw, cache)
    file = project.constants_files[0]
    if file in project.unread:
        raise SharedRefusalError(
            "unreadable",
            f"{file.name} did not load, so what it declares is unknown and '{name}' cannot be "
            "added to it",
        )
    _value(raw, name, file)
    listed = read(file, cache).value_at("constants")
    position = _appended_at(listed)
    return _plan({file: [Operation("insert", f"constants[{position}]", _entry_text(name, raw))]})


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


def _description(raw: str, name: str, file: Path) -> None:
    """Refuse a description the format would not take, naming the file it would have been
    written to.

    ``value`` has been checked against the format since this module was first written;
    ``description`` was not, and a plan carrying ``"description": 123`` - a number, where
    ``ConstantDeclaration`` wants a string - would write a file that stops loading, emptying
    every tab in the page over one keystroke. The same shape of guard as :func:`_value`, closing
    the asymmetry between the two.
    """
    try:
        _DESCRIPTION.validate_python(json.loads(raw))
    except (ValueError, TypeError) as refused:
        raise SharedRefusalError(
            "invalid",
            f"{raw} is not a description a constant may state, so '{name}' cannot take it in "
            f"{file.name}: a json string",
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


def _created(
    project: SharedProject, name: str, raw: str, cache: dict[Path, Document]
) -> SharedPlan:
    """The constants file a project without one gets, and the ``includes`` entry naming it.

    Follows :func:`ddd.lsp.units.adopt_units`, the only other plan in the repo that creates a
    file: laid out with :func:`ddd.editing.lay_out` so the new file reads like one a person
    wrote, and carried in the same plan as the ``includes`` entry so that a project can never
    list a file that was not written - which is also the only shape of creation
    :func:`ddd.gui.session._confined` allows.
    """
    created = project.project.parent / CONSTANTS_FILE
    if created.exists():
        raise SharedRefusalError(
            "invalid",
            f"declaring '{name}' writes {CONSTANTS_FILE} beside {project.project.name}, and a "
            "file of that name is there already",
        )
    _value(raw, name, created)
    laid_out = lay_out(
        f'{{"constants": [{_entry_text(name, raw)}]}}',
        one_line=False,
        indent="",
        unit=DEFAULT_INDENT_UNIT,
        newline="\n",
    )
    includes = read(project.project, cache).value_at("project.includes")
    position = _appended_at(includes)
    edits = (
        PlannedEdit(created, (Operation("set", "", f"{laid_out}\n"),), creates=True),
        PlannedEdit(
            project.project,
            (Operation("insert", f"project.includes[{position}]", _raw(CONSTANTS_FILE)),),
        ),
    )
    return SharedPlan(tuple(sorted(edits, key=lambda edit: edit.path.as_posix())))


def _appended_at(listed: object) -> int:
    """Where a new entry lands: at the end of a list read off disk, or at the front of a value
    that is not a list at all.

    A project whose ``includes`` is not a list, or a constants file whose ``constants`` is not
    one, is a shape the loader itself refuses - but a plan is built from the raw document, read
    before anything validates it, so a length taken unconditionally would raise while building
    the plan rather than let the caller reach the refusal the next ``ddd check`` already gives.

    A function rather than ``len(listed) if isinstance(listed, list) else 0`` at each call site:
    a conditional expression registers no branch at all with coverage.py, so the arm nobody
    tests could hide behind a green 100 % run, and the assignment ``if``/``else`` ruff would
    accept in its place trips ``SIM108``, which asks for that same ternary right back. An early
    return answers to both.
    """
    if isinstance(listed, list):
        return len(listed)
    return 0


def _entry_text(name: str, raw: str) -> str:
    """One constant entry as json text, with ``raw`` embedded exactly as it was given.

    Built as text rather than dumped from a dict because a dict would carry the value through
    python's number types: ``1e3`` would come back ``1000.0`` and ``2.00`` as ``2.0``. The
    generated outputs normalise a number that way on purpose, but a description file should say
    what its author wrote. ``raw`` has passed :func:`_value`, so what is built here is json.
    """
    return f'{{"name": {_raw(name)}, "value": {raw}, "description": ""}}'
