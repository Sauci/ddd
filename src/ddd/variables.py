"""One variable of a project as the unit panel of ``ddd gui`` shows it, and what changing it takes.

Transport-neutral, like :mod:`ddd.graph`: nothing here knows about http or the session. It reads
the files the language server's navigation index points into, as hover and the quick fixes do,
and it decides nothing about whether a declaration may take a change at all - that is
:func:`ddd.lsp.edits.settle`'s, so that the page and the editor cannot disagree about it. What it
adds is what a page needs around ``settle``'s rule: every declaration of one variable as its file
states it now, the units a project uses and declares, and the edit a settlement comes to with the
lines it changes, computed without writing anything.
"""

from __future__ import annotations

import codecs
import difflib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.diagnostics import Diagnostic
from ddd.editing import UNREADABLE, EditError, Operation, edit_text
from ddd.lsp.edits import PROPAGATED_KEYS, Settlement, Unsettled
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.models.objects import MEANING_KEYS

ROLES: Final = (("output", "produces"), ("input", "reads"), ("local", "local"))
"""What a declaration's scope says its component does with the variable."""

FIXED_BY_A_TYPE: Final = ("datatype", *MEANING_KEYS)
"""What a scalar type states once, for every declaration naming it."""

SETTLE_CODES: Final = {"unreachable": "unreadable", "type": "fixed-by-type", "kind": "invalid"}
"""The code ``ddd gui`` refuses a settlement with, for each reason a declaration cannot take it."""


@dataclass(frozen=True, slots=True)
class Declared:
    """One declaration of a variable, as its file states it now."""

    site: Site
    component: str
    role: str
    """``produces``, ``reads`` or ``local``, by the declaration's scope."""

    stated: Mapping[str, str]
    """The json text of ``kind`` and of every key of ``PROPAGATED_KEYS`` it states."""

    type_name: str | None
    fixed: Mapping[str, str]
    """The json text of each key of :data:`FIXED_BY_A_TYPE` the named type states."""


@dataclass(frozen=True, slots=True)
class Hunk:
    """Lines of one file a change replaces, numbered as the file stands before it."""

    line: int
    before: tuple[str, ...]
    after: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Planned:
    """The edit of one file a preview comes to, and the lines it changes."""

    path: Path
    fingerprint: str | None
    """What the analysis read the file at, which the edit is checked against; ``None`` for a
    file the change creates."""

    operations: tuple[Operation, ...]
    hunks: tuple[Hunk, ...]


def declarations_of(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Declared, ...]:
    """Every declaration of ``name`` the index recorded that its file still holds, in the index's
    order, which is the order the project lists its components in.

    A declaration its file no longer holds at the recorded place is left out rather than guessed
    at: the file changed since the analysis, and the next revision lists it where it went.
    """
    found: list[Declared] = []
    for site in built.declarations.get(name, ()):
        document = read(site.path, cache)
        if document.value_at(f"{site.pointer}.name") != name:
            continue
        typename = document.value_at(f"{site.pointer}.typename")
        type_name = typename if isinstance(typename, str) else None
        found.append(
            Declared(
                site=site,
                component=_component_of(document, site.path),
                role=_role_of(document.value_at(f"{_entry(site)}.scope")),
                stated=_stated(document, site.pointer, ("kind", *sorted(PROPAGATED_KEYS))),
                type_name=type_name,
                fixed=_fixed(built, type_name, cache),
            )
        )
    return tuple(found)


def located_on(declared: Sequence[Declared], file: Path, diagnostic: Diagnostic) -> bool:
    """Whether a finding shown on ``file`` is located on one of these declarations: on its entry
    of the interface or anywhere under it, which is how the page puts a finding on a row."""
    location = diagnostic.location
    if location is None:
        return False
    shown = file.resolve()
    return any(
        shown == entry.site.path.resolve() and _within(location.pointer, _entry(entry.site))
        for entry in declared
    )


def units_in_use(built: Index) -> tuple[tuple[str, int], ...]:
    """Every unit a declaration states, with how many variables state it: most used first, then
    by spelling. A variable several components declare counts once; no unit is not a unit.

    Counted from the index's record of units, which the Units tab counts from too, so the picker
    and the tab cannot disagree about how many variables state a unit. A unit only types and
    structure members state is used by no variable, and is not one of these.
    """
    counted = {
        unit: len({stated.name for stated in sites if stated.kind == "variable"})
        for unit, sites in built.units.items()
    }
    return tuple(
        sorted(
            ((unit, count) for unit, count in counted.items() if count),
            key=lambda pair: (-pair[1], pair[0]),
        )
    )


def vocabulary_of(documents: Sequence[Document]) -> tuple[tuple[str, str | None], ...] | None:
    """The units the project's units files declare, each with its description, in the order they
    are written - or ``None`` when it has no units file, which keeps its units free.

    Read from the files rather than from the analysis, and tolerantly: an entry that is neither a
    spelling nor an object naming one is skipped, since the loader already reports it.
    """
    if not documents:
        return None
    declared: list[tuple[str, str | None]] = []
    for document in documents:
        entries = document.value_at("units")
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, str):
                declared.append((entry, None))
            elif isinstance(entry, dict) and isinstance(entry.get("unit"), str):
                described = entry.get("description")
                declared.append((entry["unit"], described if isinstance(described, str) else None))
    return tuple(declared)


def preview(
    settlement: Settlement, key: str, fingerprints: Mapping[Path, str]
) -> tuple[Planned, ...]:
    """The edit a settlement comes to, file by file, and the lines it changes in each - made by
    the edit engine in memory and never written.

    Each file carries the fingerprint the analysis read it at, from ``fingerprints`` (keyed by
    resolved path), so that applying the preview after the file changed on disk is refused as
    stale rather than made to text nobody previewed.
    """
    operations: dict[Path, list[Operation]] = {}
    for change in settlement.changes:
        pointer = f"{change.site.pointer}.{key}"
        made = (
            Operation("remove", pointer)
            if change.raw is None
            else Operation("set", pointer, change.raw)
        )
        operations.setdefault(change.site.path, []).append(made)
    return tuple(
        planned(path, tuple(made), fingerprints)
        for path, made in sorted(operations.items(), key=lambda entry: entry[0].as_posix())
    )


def planned(
    path: Path, operations: tuple[Operation, ...], fingerprints: Mapping[Path, str]
) -> Planned:
    """The edit of one file the analysis read, and the lines it changes, made in memory.

    The file carries the fingerprint the analysis read it at, from ``fingerprints`` (keyed by
    resolved path): a file the analysis did not read, or that can no longer be read as utf-8,
    is refused as unreadable rather than previewed from bytes nobody analysed.
    """
    stamp = fingerprints.get(path.resolve())
    if stamp is None:
        raise EditError(UNREADABLE, f"{path} is not a file the last analysis read")
    try:
        text = path.read_bytes().removeprefix(codecs.BOM_UTF8).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise EditError(UNREADABLE, f"{path} can no longer be read as utf-8") from None
    return Planned(path, stamp, operations, hunks(text, edit_text(text, operations)))


def hunks(before: str, after: str) -> tuple[Hunk, ...]:
    """The lines a change replaces in a text, each run of them numbered as the text stood."""
    old, new = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return tuple(
        Hunk(first + 1, tuple(old[first:last]), tuple(new[start:end]))
        for tag, first, last, start, end in matcher.get_opcodes()
        if tag != "equal"
    )


def refusal(unsettled: Unsettled, name: str, key: str) -> tuple[str, str]:
    """The code and the sentence ``ddd gui`` refuses a settlement with, naming the declaration."""
    where = f"the declaration of '{name}' in {unsettled.site.path.name}"
    if unsettled.reason == "type":
        sentence = f"{where} names the type '{unsettled.type_name}', which fixes its {key}"
    elif unsettled.reason == "kind":
        sentence = f"{where} is of a kind that does not allow that {key}"
    else:
        sentence = f"{where} is no longer where the last analysis found it"
    return SETTLE_CODES[unsettled.reason], sentence


def _entry(site: Site) -> str:
    """The declaration's entry of the interface, the definition's parent."""
    return site.pointer.removesuffix(".definition")


def _within(pointer: str, entry: str) -> bool:
    return pointer == entry or pointer.startswith((f"{entry}.", f"{entry}["))


def _component_of(document: Document, path: Path) -> str:
    named = document.value_at("component.name")
    return named if isinstance(named, str) else path.name.removesuffix(".ddd.json")


def _role_of(scope: Any) -> str:
    return next((role for spelled, role in ROLES if spelled == scope), "reads")


def _stated(document: Document, pointer: str, keys: Iterable[str]) -> dict[str, str]:
    return {key: raw for key in keys if (raw := document.raw_at(f"{pointer}.{key}")) is not None}


def _fixed(built: Index, type_name: str | None, cache: dict[Path, Document]) -> dict[str, str]:
    site = None if type_name is None else built.types.get(type_name)
    if site is None:
        return {}
    return _stated(read(site.path, cache), site.pointer, FIXED_BY_A_TYPE)
