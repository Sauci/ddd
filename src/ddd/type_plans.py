"""What changing one of a project's types takes, planned and never written.

Transport-neutral, like :mod:`ddd.project_types` beside it. A rename is the editor's rename:
:func:`ddd.lsp.navigation.rename_sites` says which strings it has to rewrite - the type's own
``name`` and every ``typename`` reaching it - :func:`~ddd.lsp.navigation.named_by_a_header` why
an external type is not renamed at all, and :func:`~ddd.lsp.navigation.rename_problem` why a
name may not be used, each in the sentence the editor shows. What is not borrowed is
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

What a key is set to is asked of the models as the entry would be left
(:func:`ddd.models.type_problem`), the question a variable's settlement asks of a definition
(:func:`ddd.lsp.edits.loading_problem`), and of the entry as it stands: a value bringing the entry
a refusal it did not carry is refused before it is planned, in the models' words, rather than
written into a types file that would then take every type it declares with it.

Each change answers a :class:`~ddd.plans.Plan`, one edit per file, sorted by path, or raises a
:class:`~ddd.plans.PlanRefusalError`: ``invalid`` where the change cannot be made - a key this
kind has not, a required key left out, a value the entry would not load with, a name that may not
be used; ``not-found`` where the project declares no type of that name; ``stale`` where a file the
change points into no longer names the type where the index found it, having changed since the
analysis read it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ddd.editing import Operation
from ddd.loading import parse_json_text
from ddd.lsp.navigation import (
    Index,
    Site,
    changed_since,
    drift,
    named_by_a_header,
    rename_problem,
    rename_sites,
)
from ddd.lsp.ranges import Document, read
from ddd.models import type_problem
from ddd.plans import Plan, PlannedEdit, PlanRefusalError
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


def set_key(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Plan:
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

    Refused ``invalid`` where the change brings the entry a refusal it did not carry: where the
    project refuses the entry as the change would leave it (:func:`_loading_problem`) and the
    entry as it stands not at all, or in another sentence - a datatype that is none, a range whose
    maximum is below its minimum, a conversion that cannot be undone, limits derived past the
    largest float - in the sentence ``ddd check`` files it in, naming the type and its file. The
    entry is asked of :func:`ddd.models.type_problem` before the change and after. A type the
    analysis refuses already - a ``float64`` scaled past the largest float loads, and is refused
    at its conversion - is planned a change leaving that refusal as it was, its unit, its
    description, or the value a row holds, which the Types tab asks the moment the row is
    selected; and a change mending it. The refusal is the entry's, and the sentence would blame
    whichever key the reader chose.
    """
    site = _entry(built, name)
    if not type_in_place(built, name, cache):
        raise PlanRefusalError("stale", changed_since((site.path,), f"'{name}' cannot be changed"))
    document = read(site.path, cache)
    allowed = SETTABLE.get(kind_of(built, name, cache), frozenset())
    if key not in allowed:
        raise PlanRefusalError("invalid", f"a type of this kind has no '{key}' to set")
    if raw is None and key in REQUIRED:
        raise PlanRefusalError("invalid", f"'{key}' is required, so it cannot be left out")
    if raw is None and document.value_at(f"{site.pointer}.{key}") is None:
        return Plan(())
    problem = _loading_problem(document, site.pointer, key, raw)
    if problem is not None and problem != type_problem(document.value_at(site.pointer)):
        raise PlanRefusalError(
            "invalid",
            f"the type '{name}' in {site.path.name} would not load with that {key}: {problem}",
        )
    operation = (
        Operation("remove", f"{site.pointer}.{key}")
        if raw is None
        else Operation("set", f"{site.pointer}.{key}", raw)
    )
    return Plan((PlannedEdit(site.path, (operation,)),))


def _loading_problem(document: Document, entry: str, key: str, raw: str | None) -> str | None:
    """What the project would refuse of the type's entry at ``entry`` once ``key`` states ``raw`` -
    or states nothing, for ``None`` - or ``None`` where it still loads.

    The entry as the key would leave it, asked of :func:`ddd.models.type_problem` as
    :func:`ddd.lsp.edits.loading_problem` asks a definition of the models: a copy of its members,
    so that the document asked of is left as it was. ``raw`` read as json the loader does not take
    - a key written twice - is that problem, in the loader's words, and not raised.
    ``set_key`` asks it only of an entry still in place (:func:`~ddd.project_types.type_in_place`),
    which is an object.
    """
    left = {member: value for member, value in document.value_at(entry).items() if member != key}
    if raw is not None:
        try:
            left[key] = parse_json_text(raw)
        except ValueError as refused:
            return str(refused)
    return type_problem(left)


def rename_type(built: Index, name: str, to: str, cache: dict[Path, Document]) -> Plan:
    """What renaming a type takes: its own ``name`` and every ``typename`` reaching it.

    Refused in the editor's own words for an external type, whose name is the one its header
    defines (:func:`~ddd.lsp.navigation.named_by_a_header`), and for a name that may not be used,
    before a file is touched - a rename writes into every file naming the type, and a name that
    turns out to be unusable would leave the project broken across all of them at once. Refused
    too while a file no longer names the type at a place the index recorded
    (:func:`~ddd.lsp.navigation.drift`): the rename would write the new name over whatever sits
    there now.
    """
    _entry(built, name)
    problem = named_by_a_header(built, "type", name) or rename_problem(built, to, "type")
    if problem is not None:
        raise PlanRefusalError("invalid", problem)
    sites = rename_sites(built, "type", name)
    moved = drift(sites, name, cache)
    if moved:
        raise PlanRefusalError(
            "stale", changed_since(moved, f"renaming '{name}' cannot be planned")
        )
    by_file: dict[Path, list[Operation]] = {}
    for site in sites:
        by_file.setdefault(site.path, []).append(Operation("set", site.pointer, json.dumps(to)))
    return Plan(
        tuple(PlannedEdit(path, tuple(operations)) for path, operations in sorted(by_file.items()))
    )


def _entry(built: Index, name: str) -> Site:
    """Where the type is declared, or the refusal a name no type holds gets."""
    site = built.types.get(name)
    if site is None:
        raise PlanRefusalError("not-found", f"this project declares no type called '{name}'")
    return site
