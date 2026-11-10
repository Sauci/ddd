"""What changing one of a project's types takes, planned and never written.

Transport-neutral, like :mod:`ddd.project_types` beside it. A rename is the editor's rename:
:func:`ddd.lsp.navigation.rename_sites` says which strings it has to rewrite - the type's own
``name`` and every ``typename`` reaching it - and :func:`~ddd.lsp.navigation.rename_problem` says
why a name may not be used, in the sentence the editor shows. What is not borrowed is
``rename_edits``, which answers text edits with ranges: the interface plans operations on json
pointers, the way part 4's identity fix does, so that one engine writes every change ``ddd gui``
makes and one undo puts it back.

``rename_edits``'s own ``drifted`` has its counterpart here, the same question asked of the disk
rather than of a buffer (:func:`~ddd.lsp.navigation.drift`): the index is of the files as the last
analysis read them, and a file saved since may have moved the entry or a declaration naming it.
A rename is refused then, and so is setting a key, the entry asked as its panel asks it
(:func:`~ddd.project_types.type_in_place`), rather than planned at places now holding another
type, or none; the fingerprint the edit carries, of the bytes that analysis read, refuses its
Apply as well.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.editing import Operation
from ddd.lsp.navigation import Index, Site, changed_since, drift, rename_problem, rename_sites
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.project_types import kind_of, type_in_place

SETTABLE: Final[Mapping[str, frozenset[str]]] = {
    "scalar": frozenset({"description", "datatype", "unit", "conversion", "limits"}),
    "external": frozenset({"description", "header"}),
    "struct": frozenset({"description"}),
}
"""What each kind of type lets the interface set, by its ``type`` key."""

REQUIRED: Final = frozenset({"datatype", "conversion", "header"})
"""The keys a type may not be left without: the models require them, so a file missing one would
not load. ``unit``, ``limits`` and ``description`` may be left out, and the panel offers it."""


class TypeRefusalError(Exception):
    """A change of a type that cannot be planned, and the code both clients refuse it with."""

    code: Literal["invalid", "not-found", "stale"]
    """``invalid``: the change cannot be made - a key this kind has not, a required key left out,
    a name that may not be used. ``not-found``: the project declares no type of that name.
    ``stale``: a file the change points into no longer names the type where the index found it,
    having changed since the analysis read it."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found", "stale"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class TypePlan:
    """Everything one change of a type takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


def set_key(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> TypePlan:
    """What setting one key of a type takes: one operation, at that type's own entry.

    ``raw`` is the json text the key is set to, or ``None`` to leave the key out - which a key
    the models require refuses rather than writing a file that would not load. A key already
    left out answers no edit at all rather than a removal: there is nothing to remove, and a
    reader who has only selected the row - not typed anything - must not be refused before they
    have done anything.

    Refused ``stale``, before anything is read at the type's entry, while the place the index
    recorded for it no longer names it (:func:`~ddd.project_types.type_in_place`): an entry put
    in above it or taken out moves it, and both the kind that decides which keys may be set and
    the key set would be another type's.
    """
    site = _entry(built, name)
    if not type_in_place(built, name, cache):
        raise TypeRefusalError("stale", changed_since((site.path,), f"'{name}' cannot be changed"))
    document = read(site.path, cache)
    allowed = SETTABLE.get(kind_of(built, name, cache), frozenset())
    if key not in allowed:
        raise TypeRefusalError("invalid", f"a type of this kind has no '{key}' to set")
    if raw is None and key in REQUIRED:
        raise TypeRefusalError("invalid", f"'{key}' is required, so it cannot be left out")
    if raw is None and document.value_at(f"{site.pointer}.{key}") is None:
        return TypePlan(())
    operation = (
        Operation("remove", f"{site.pointer}.{key}")
        if raw is None
        else Operation("set", f"{site.pointer}.{key}", raw)
    )
    return TypePlan((PlannedEdit(site.path, (operation,)),))


def rename_type(built: Index, name: str, to: str, cache: dict[Path, Document]) -> TypePlan:
    """What renaming a type takes: its own ``name`` and every ``typename`` reaching it.

    Refused in the editor's own words for a name that may not be used, before a file is touched -
    a rename writes into every file naming the type, and a name that turns out to be unusable
    would leave the project broken across all of them at once. Refused too while a file no longer
    names the type at a place the index recorded (:func:`~ddd.lsp.navigation.drift`): the
    rename would write the new name over whatever sits there now.
    """
    _entry(built, name)
    problem = rename_problem(built, to, "type")
    if problem is not None:
        raise TypeRefusalError("invalid", problem)
    sites = rename_sites(built, "type", name)
    moved = drift(sites, name, cache)
    if moved:
        raise TypeRefusalError(
            "stale", changed_since(moved, f"renaming '{name}' cannot be planned")
        )
    by_file: dict[Path, list[Operation]] = {}
    for site in sites:
        by_file.setdefault(site.path, []).append(Operation("set", site.pointer, json.dumps(to)))
    return TypePlan(
        tuple(PlannedEdit(path, tuple(operations)) for path, operations in sorted(by_file.items()))
    )


def _entry(built: Index, name: str) -> Site:
    """Where the type is declared, or the refusal a name no type holds gets."""
    site = built.types.get(name)
    if site is None:
        raise TypeRefusalError("not-found", f"this project declares no type called '{name}'")
    return site
