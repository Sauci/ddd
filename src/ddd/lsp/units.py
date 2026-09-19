"""Changing a unit everywhere a project states it, and the vocabulary that lists it.

A unit is free text wherever it is written, so one quantity drifts into two spellings - ``rpm``
in one component, ``RPM`` in the next - and a vocabulary is what holds a project to one. This
module plans each change to that: renaming a unit everywhere, which merges two spellings when the
new one is listed already; adding a unit to the vocabulary, describing it and taking it out; and
adopting a vocabulary where there is none. A plan is the operations of :mod:`ddd.editing` each
file takes, on json pointers, made once for both clients: the language server renders it as the
text edits of Rename Symbol and of its quick fixes, and ``ddd gui`` previews it and posts it to
its edit endpoint. Where a unit is stated is the navigation index's to say; nothing here decides
it again.

A plan refuses before it reads a file it would not write. A file that did not load may state the
unit, and a rename that cannot see it leaves the old spelling there, in a project the rename
said it had rewritten.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from ddd.editing import (
    DEFAULT_INDENT_UNIT,
    INVALID,
    EditError,
    Operation,
    TextEdit,
    insertion,
    lay_out,
    member_addition,
    removal,
    replacement,
)
from ddd.loading import expand_include, resolve_path
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.pointers import parent_pointer

ADOPTED: Final = "units.ddd.json"
"""The units file adopting a vocabulary writes, beside the project description."""


@dataclass(frozen=True, slots=True)
class UnitProject:
    """What a plan has to know of the project besides its index: where its vocabulary is kept,
    and which of its files did not load."""

    project: Path
    """The project description, resolved."""

    units_files: tuple[Path, ...]
    """Its units files, in the order its ``project.includes`` lists them: the first is where a
    unit added to the vocabulary goes."""

    unread: tuple[Path, ...]
    """The project's files that did not load, resolved and sorted."""


@dataclass(frozen=True, slots=True)
class PlannedEdit:
    """The operations one file takes, in the order they are made."""

    path: Path
    operations: tuple[Operation, ...]
    creates: bool = False
    """The plan creates this file: ``operations`` is one ``set`` at the root, carrying it whole."""


@dataclass(frozen=True, slots=True)
class UnitPlan:
    """Everything one change of a unit takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class UnitRefusalError(Exception):
    """A change of a unit that cannot be planned, and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``unreadable``: a file the change has to see did not load. ``invalid``: the change cannot
    be made - a spelling no unit has, a unit something still states, a vocabulary the project
    has already. ``not-found``: the project neither states the unit nor lists it."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def unit_project(project: Path, unread: Sequence[Path], cache: dict[Path, Document]) -> UnitProject:
    """The project a unit's plans are made in: its description, its units files and the files of
    it that did not load.

    The units files are read out of the description's own ``includes``, each entry expanded by
    the loader's rule, so that the first of them is the first a run of ``ddd check`` reads. A
    units file is a document with ``units`` at its top, which is how the loader tells one; a file
    that does not parse is none, since what it is cannot be told.
    """
    path = resolve_path(project)
    listed = read(path, cache).value_at("project.includes")
    found: list[Path] = []
    for entry in listed if isinstance(listed, list) else ():
        for file in _included(path, entry):
            document = read(file, cache).data
            if file not in found and isinstance(document, dict) and "units" in document:
                found.append(file)
    return UnitProject(
        path,
        tuple(found),
        tuple(sorted({resolve_path(file) for file in unread}, key=Path.as_posix)),
    )


def rename_unit(
    built: Index, project: UnitProject, old: str, new: str, cache: dict[Path, Document]
) -> UnitPlan:
    """Every place ``old`` is stated spelled ``new``, and the vocabulary brought along.

    Only the spelling changes: a value, its limits and its conversion stay as they are, because
    ``ms`` to ``s`` is a conversion and not a spelling. In the vocabulary, each entry listing
    ``old`` is renamed, keeping its description, where no entry lists ``new``; where one does,
    the rename is a merge, and the entries listing ``old`` are taken out, leaving the entry of
    ``new`` with its own description. A unit listed twice has every entry treated so.
    """
    _spelling(new)
    if new == old:
        raise UnitRefusalError("invalid", f"'{old}' is spelled that way already")
    if project.unread:
        raise UnitRefusalError(
            "unreadable",
            f"{_names(project.unread)} did not load, so renaming '{old}' could not reach every "
            "place it is stated",
        )
    _known(built, old)
    raw = _raw(new)
    operations: dict[Path, list[Operation]] = {}
    for stated in built.units.get(old, ()):
        operations.setdefault(stated.site.path, []).append(
            Operation("set", stated.site.pointer, raw)
        )
    entries = built.vocabulary.get(old, [])
    if new in built.vocabulary:
        for file, removals in _taken_out(entries, old, cache).items():
            operations.setdefault(file, []).extend(removals)
    else:
        for entry in entries:
            spelled = entry.pointer
            if isinstance(read(entry.path, cache).value_at(entry.pointer), dict):
                spelled = f"{entry.pointer}.unit"
            operations.setdefault(entry.path, []).append(Operation("set", spelled, raw))
    return _plan(operations)


def add_unit(
    built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]
) -> UnitPlan:
    """``unit`` appended to the first units file the project description includes, in the form
    that file's entries take: the spelling alone where every entry is one, and an object with an
    empty description where any entry is written as an object."""
    _spelling(unit)
    if not project.units_files:
        raise UnitRefusalError(
            "invalid", f"{project.project.name} includes no units file to add '{unit}' to"
        )
    file = project.units_files[0]
    if file in project.unread:
        raise UnitRefusalError(
            "unreadable", f"{file.name} did not load, so '{unit}' cannot be added to it"
        )
    if unit in built.vocabulary:
        raise UnitRefusalError(
            "invalid",
            f"'{unit}' is in the vocabulary already, in {_names(_paths(built.vocabulary[unit]))}",
        )
    listed = read(file, cache).value_at("units") or []
    plain = all(isinstance(entry, str) for entry in listed)
    written = _raw(unit if plain else {"unit": unit, "description": ""})
    return _plan({file: [Operation("insert", f"units[{len(listed)}]", written)]})


def describe_unit(
    built: Index, project: UnitProject, unit: str, description: str, cache: dict[Path, Document]
) -> UnitPlan:
    """The vocabulary's description of ``unit`` set to ``description``: an object entry's
    ``description``, added where it has none, and an entry that is the spelling alone turned into
    an object that holds one. A unit listed twice has every entry described."""
    _vocabulary_loaded(built, project, unit, "its description cannot be set there")
    _known(built, unit)
    entries = built.vocabulary.get(unit)
    if entries is None:
        raise UnitRefusalError(
            "invalid", f"'{unit}' is not in the vocabulary, so it has no description to set"
        )
    operations: dict[Path, list[Operation]] = {}
    for entry in entries:
        if isinstance(read(entry.path, cache).value_at(entry.pointer), dict):
            made = Operation("set", f"{entry.pointer}.description", _raw(description))
        else:
            whole = _raw({"unit": unit, "description": description})
            made = Operation("set", entry.pointer, whole)
        operations.setdefault(entry.path, []).append(made)
    return _plan(operations)


def remove_unit(
    built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]
) -> UnitPlan:
    """Every entry listing ``unit`` taken out of the vocabulary, each with exactly one comma.

    Only a unit nothing states: taking out one that is stated would turn every place stating it
    into an ``unknown-unit`` finding.
    """
    _vocabulary_loaded(built, project, unit, "it cannot be taken out of it")
    stated = built.units.get(unit)
    if stated is not None:
        places = f"{len(stated)} place{'s' if len(stated) != 1 else ''}"
        raise UnitRefusalError(
            "invalid",
            f"'{unit}' is still stated in {places}; only a unit nothing states is taken out of "
            "the vocabulary",
        )
    entries = built.vocabulary.get(unit)
    if entries is None:
        raise UnitRefusalError("not-found", f"no file of this project states or lists '{unit}'")
    return _plan(_taken_out(entries, unit, cache))


def adopt_units(built: Index, project: UnitProject, cache: dict[Path, Document]) -> UnitPlan:
    """A vocabulary for a project without one: :data:`ADOPTED`, written beside the description
    and listing every unit in use alphabetically with an empty description, and its name
    appended to the description's ``includes``, in one edit.

    Every unit in use, drifted spellings included, so that adopting reports nothing that was not
    reported before; two spellings of one unit are merged by renaming one of them afterwards.
    The file is laid out by the edit engine the way a units file is written by hand, one entry
    to a line, so that the first edit anybody makes to it reads as a one-line change.
    """
    entries = [entry for listed in built.vocabulary.values() for entry in listed]
    held = sorted({*project.units_files, *_paths(entries)}, key=Path.as_posix)
    if held:
        raise UnitRefusalError("invalid", f"this project has a vocabulary already: {_names(held)}")
    if project.unread:
        raise UnitRefusalError(
            "unreadable",
            f"{_names(project.unread)} did not load, so adopting could not list every unit in use",
        )
    if not built.units:
        raise UnitRefusalError(
            "invalid", "this project states no unit, and a units file lists at least one"
        )
    created = project.project.parent / ADOPTED
    if created.exists():
        raise UnitRefusalError(
            "invalid",
            f"adopting writes {ADOPTED} beside {project.project.name}, and a file of that name "
            "is there already",
        )
    document = {"units": [{"unit": unit, "description": ""} for unit in sorted(built.units)]}
    laid_out = lay_out(
        _raw(document), one_line=False, indent="", unit=DEFAULT_INDENT_UNIT, newline="\n"
    )
    whole = f"{laid_out}\n"
    includes = read(project.project, cache).value_at("project.includes") or []
    included = Operation("insert", f"project.includes[{len(includes)}]", _raw(ADOPTED))
    edits = (
        PlannedEdit(created, (Operation("set", "", whole),), creates=True),
        PlannedEdit(project.project, (included,)),
    )
    return UnitPlan(tuple(sorted(edits, key=lambda edit: edit.path.as_posix())))


def _spelling(unit: str) -> None:
    """Refuse a spelling no unit is written with: the empty unit is no unit, and spaces around
    one are a slip of the keyboard rather than part of its spelling."""
    if not unit:
        raise UnitRefusalError("invalid", "the empty unit is no unit")
    if unit != unit.strip():
        raise UnitRefusalError("invalid", f"'{unit}' has spaces around it")


def _known(built: Index, unit: str) -> None:
    """Refuse a unit the project neither states nor lists: there is nothing of it to change."""
    if unit not in built.units and unit not in built.vocabulary:
        raise UnitRefusalError("not-found", f"no file of this project states or lists '{unit}'")


def _vocabulary_loaded(built: Index, project: UnitProject, unit: str, consequence: str) -> None:
    """Refuse to change the entries listing ``unit`` while a units file holding one did not load
    - or, for a unit no entry that loaded lists, while any units file did not, since that may be
    the one listing it. A component that did not load is no concern of the vocabulary's."""
    entries = built.vocabulary.get(unit)
    files = _paths(entries) if entries is not None else project.units_files
    unread = [file for file in files if file in project.unread]
    if unread:
        raise UnitRefusalError("unreadable", f"{_names(unread)} did not load, so {consequence}")


def _taken_out(
    entries: Sequence[Site], unit: str, cache: dict[Path, Document]
) -> dict[Path, list[Operation]]:
    """The removals taking every entry of ``unit`` out of the vocabulary, file by file.

    The entry furthest down a file goes first: the edit engine makes a file's operations one
    after another, and taking out ``units[1]`` makes ``units[3]`` the new ``units[2]``. Refused
    where the file would be left listing no unit at all, which a units file may not do - emptied,
    it would no longer load.
    """
    for file, taken in Counter(entry.path for entry in entries).items():
        listed = read(file, cache).value_at("units")
        if isinstance(listed, list) and taken >= len(listed):
            raise UnitRefusalError(
                "invalid",
                f"'{unit}' is all {file.name} lists, and a units file lists at least one unit",
            )
    operations: dict[Path, list[Operation]] = {}
    for entry in sorted(entries, key=lambda entry: (entry.path.as_posix(), -_position(entry))):
        operations.setdefault(entry.path, []).append(Operation("remove", entry.pointer))
    return operations


def _included(project: Path, entry: Any) -> list[Path]:
    """The files one ``includes`` entry names, or none for an entry the loader cannot expand -
    one that is not a string, or a pattern pathlib refuses - which it has reported already."""
    if not isinstance(entry, str):
        return []
    try:
        return expand_include(project, entry, {project})
    except (OSError, ValueError, NotImplementedError):
        return []


def _position(entry: Site) -> int:
    """Where a vocabulary entry sits in its file's ``units``, read off its pointer ``units[i]``."""
    return int(entry.pointer.removeprefix("units[").removesuffix("]"))


def _plan(operations: Mapping[Path, Sequence[Operation]]) -> UnitPlan:
    """One edit per file, sorted by path, each file's operations in the order they were planned."""
    return UnitPlan(
        tuple(
            PlannedEdit(path, tuple(made))
            for path, made in sorted(operations.items(), key=lambda item: item[0].as_posix())
        )
    )


def _raw(value: Any) -> str:
    """A value as the json text an operation carries, every character as written: a unit such as
    ``°C`` arrives in the file as ``°C``, where json's default would write ``\\u00b0C``."""
    return json.dumps(value, ensure_ascii=False)


def _paths(entries: Iterable[Site]) -> list[Path]:
    return sorted({entry.path for entry in entries}, key=Path.as_posix)


def _names(files: Iterable[Path]) -> str:
    return ", ".join(file.name for file in files)


def text_edits(plan: UnitPlan, cache: dict[Path, Document]) -> dict[str, list[dict[str, Any]]]:
    """A plan as a language client applies it: the protocol's text edits, by file uri.

    Each operation is made by the edit engine's own :func:`~ddd.editing.replacement`,
    :func:`~ddd.editing.member_addition`, :func:`~ddd.editing.removal` or
    :func:`~ddd.editing.insertion`, on the text the operations before it left - the way
    ``POST /api/edit`` makes them, so an editor and ``ddd gui`` write the same bytes. A client
    applies a file's edits all at once, to the text as it stands, and refuses two that overlap,
    so the edits are restated against that text, and edits that meet become one: two
    neighbouring vocabulary entries taken out would otherwise both claim the comma between them.

    Each file is read through ``cache``, which holds the buffers an editor has open, because
    the edit is applied to what is on screen. A plan that creates a file - an adoption, which
    only ``ddd gui`` plans - is refused rather than rendered: a text edit changes a file that
    is there.
    """
    changes: dict[str, list[dict[str, Any]]] = {}
    for planned in plan.edits:
        if planned.creates:
            raise EditError(
                INVALID, f"{planned.path.name} is created by this plan, which no text edit can do"
            )
        document = read(planned.path, cache)
        changes[planned.path.as_uri()] = [
            _protocol_edit(document, edit) for edit in _simultaneous(document, planned.operations)
        ]
    return changes


def unit_drift(built: Index, unit: str, cache: dict[Path, Document]) -> tuple[Path, ...]:
    """The files whose text no longer holds ``unit`` where the index found it, sorted.

    The index is read off the disk, and a buffer an editor has open may have moved or respelled
    what it recorded since. A plan's pointers are the index's, so made in that buffer they would
    respell whatever sits there now: the language server refuses the rename instead, naming
    these files, and offers none as a quick fix.
    """
    stated = [
        found.site.path
        for found in built.units.get(unit, ())
        if read(found.site.path, cache).value_at(found.site.pointer) != unit
    ]
    listed = [
        entry.path
        for entry in built.vocabulary.get(unit, ())
        if read(entry.path, cache).value_at(entry.pointer) != unit
        and read(entry.path, cache).value_at(f"{entry.pointer}.unit") != unit
    ]
    return tuple(sorted({*stated, *listed}, key=Path.as_posix))


def _simultaneous(document: Document, operations: Sequence[Operation]) -> list[TextEdit]:
    """The operations' edits of ``document`` as its text stands, in order and none overlapping.

    Made one after another, as the engine makes them, with every character of the result
    remembered by where it came from: an offset of the text as it stands, or none for a
    character an edit wrote. Whatever lies between two characters kept from that text is one
    edit of it, however many operations it took.
    """
    current = document
    origins: list[int | None] = list(range(len(document.text)))
    for operation in operations:
        edit = _engine_edit(current, operation)
        origins[edit.start : edit.end] = [None] * len(edit.text)
        text = current.text
        current = Document(f"{text[: edit.start]}{edit.text}{text[edit.end :]}")
    edits: list[TextEdit] = []
    kept = 0
    written: list[str] = []
    # A last character kept past the end, so that an edit running to the end of the text is
    # closed like any other.
    ends = ("", len(document.text))
    for character, origin in [*zip(current.text, origins, strict=True), ends]:
        if origin is None:
            written.append(character)
            continue
        if origin != kept or written:
            edits.append(TextEdit(kept, origin, "".join(written)))
            written = []
        kept = origin + 1
    return edits


def _engine_edit(document: Document, operation: Operation) -> TextEdit:
    """The edit the engine makes for one operation, as :func:`ddd.editing.edit_text` makes it:
    an entry taken out with one comma, an element inserted into an array, a value replaced, or
    a member added to an object that has none of that name. A plan makes no ``move``."""
    if operation.op == "remove":
        return removal(document, operation.pointer)
    # Every other operation of a plan writes a value, carried as json text.
    assert operation.raw is not None
    if operation.op == "insert":
        return insertion(document, operation.pointer, operation.raw)
    if document.raw_at(operation.pointer) is not None:
        return replacement(document, operation.pointer, operation.raw)
    parent = parent_pointer(operation.pointer)
    key = operation.pointer[len(parent) + 1 :] if parent else operation.pointer
    return member_addition(document, parent, key, operation.raw)


def _protocol_edit(document: Document, edit: TextEdit) -> dict[str, Any]:
    """An edit the engine computed as offsets, as the protocol carries it - the rendering
    :mod:`ddd.lsp.edits` gives its quick fixes."""
    return {
        "range": {"start": document.position(edit.start), "end": document.position(edit.end)},
        "newText": edit.text,
    }
