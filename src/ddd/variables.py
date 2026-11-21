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
from bisect import bisect_right
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path
from typing import Any, Final

from ddd.diagnostics import Diagnostic
from ddd.difflib_lock import ONE_THREAD_IN_DIFFLIB
from ddd.editing import UNREADABLE, EditError, Operation, TextEdit, edit_spans
from ddd.lsp.edits import PROPAGATED_KEYS, Settlement, Unsettled, loading_problem
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.models.objects import FIXED_BY_A_TYPE, TypeConversions

ROLES: Final = (("output", "produces"), ("input", "reads"), ("local", "local"))
"""What a declaration's scope says its component does with the variable."""

SETTLE_CODES: Final = {
    "unreachable": "unreadable",
    "type": "fixed-by-type",
    "kind": "invalid",
    "storage": "invalid",
    "load": "invalid",
    "unproduced": "invalid",
}
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
    """The json text of each key of :data:`ddd.models.objects.FIXED_BY_A_TYPE` the type states."""


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
                component=component_of(document, site.path),
                role=role_of(document.value_at(f"{_entry(site)}.scope")),
                stated=_stated(document, site.pointer, ("kind", *sorted(PROPAGATED_KEYS))),
                type_name=type_name,
                fixed=_fixed(built, type_name, cache),
            )
        )
    return tuple(found)


def located_on(
    declared: Sequence[Declared],
    file: Path,
    diagnostic: Diagnostic,
    resolve: Callable[[Path], Path] = Path.resolve,
) -> bool:
    """Whether a finding shown on ``file`` is located on one of these declarations: on its entry
    of the interface or anywhere under it, which is how the page puts a finding on a row.

    ``resolve`` resolves both paths compared: ``ddd gui`` passes one answering from what its
    revision's analysis resolved already (:meth:`ddd.gui.derived.Derived.resolve`), so that
    asking this of every finding on a declaration's files resolves none of them again."""
    location = diagnostic.location
    if location is None:
        return False
    shown = resolve(file)
    return any(
        shown == resolve(entry.site.path) and _within(location.pointer, _entry(entry.site))
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


def operations_for(
    settlement: Settlement, key: str
) -> tuple[tuple[Path, tuple[Operation, ...]], ...]:
    """What a settlement writes, file by file, in path order.

    Shared by the preview a variable's panel draws and the fix a finding carries, so that one
    settlement spells the same operations in the same order whichever of the two asked for it.
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
        (path, tuple(made))
        for path, made in sorted(operations.items(), key=lambda entry: entry[0].as_posix())
    )


def preview(
    settlement: Settlement,
    key: str,
    fingerprints: Mapping[Path, str],
    cache: Mapping[Path, Document] | None = None,
) -> tuple[Planned, ...]:
    """The edit a settlement comes to, file by file, and the lines it changes in each - made by
    the edit engine in memory and never written.

    Each file carries the fingerprint the analysis read it at, from ``fingerprints`` (keyed by
    resolved path), so that applying the preview after the file changed on disk is refused as
    stale rather than made to text nobody previewed. ``cache`` is the one the settlement was
    decided on, whose documents :func:`planned` makes each edit from.
    """
    return tuple(
        planned(path, operations, fingerprints, cache)
        for path, operations in operations_for(settlement, key)
    )


def planned(
    path: Path,
    operations: tuple[Operation, ...],
    fingerprints: Mapping[Path, str],
    cache: Mapping[Path, Document] | None = None,
) -> Planned:
    """The edit of one file the analysis read, and the lines it changes, made in memory.

    The file carries the fingerprint the analysis read it at, from ``fingerprints`` (keyed by
    resolved path): a file the analysis did not read, or that can no longer be read as utf-8,
    is refused as unreadable rather than previewed from bytes nobody analysed.

    Looked up as it is spelled first, and resolved only where that finds nothing: a path spelled
    as a key is that resolved path already, as every path of an analysis's own index is, and a
    plan renaming a unit stated in every file of a large project resolved every one of them
    again.

    The lines it changes are read off the spans the engine's edit replaced
    (:func:`lines_replaced`), never found by comparing the file before and after it. The edit is
    made from the document ``cache`` - the plan's own - holds for the file, where the file reads
    as that document still (:func:`ddd.editing.edit_spans`): whoever planned the operations read
    the file already, to find where they go or that it still holds what they point at.
    """
    stamp = fingerprints.get(path)
    if stamp is None:
        stamp = fingerprints.get(path.resolve())
    if stamp is None:
        raise EditError(UNREADABLE, f"{path} is not a file the last analysis read")
    try:
        text = path.read_bytes().removeprefix(codecs.BOM_UTF8).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise EditError(UNREADABLE, f"{path} can no longer be read as utf-8") from None
    edited = edit_spans(text, operations, None if cache is None else cache.get(path))
    return Planned(path, stamp, operations, lines_replaced(text, edited.replaced))


def lines_replaced(before: str, replaced: Sequence[TextEdit]) -> tuple[Hunk, ...]:
    """The lines a change replaces in ``before``, each run of them numbered as the text stood,
    read off the spans of it the change replaced - in order and none overlapping, as
    :attr:`ddd.editing.Edited.replaced` holds them: a plan's lines.

    A span lies on the lines from the one it begins on to the one it ends on, and spans lying on
    one line are one run. A span beginning a line that a carriage return alone ends the line
    before lies on that line too: a line feed written there makes one line break of the two.
    Of a run's lines, those reading the same before and after at either end are no part of it,
    the last ones first: an entry taken out ends where the next one begins, so the line it
    reaches into reads as it did once the entry is gone - that line is the next entry's, and the
    lines taken out are the entry's own. Runs that then meet, no line left as it was between
    them, are one. A text's lines are what ``str.splitlines`` reads, as :func:`hunks` reads them.

    Only the lines a span lies on are compared (:func:`_alike_at_the_ends`), however long the
    file. :func:`hunks` compares every line of it, by difflib where a line the change writes is
    held elsewhere in the file, as it is wherever a unit is stated twice: over the 48,350 lines of
    the largest component of a generated project of 100,000 declarations, one unit set in it, it
    took 6.8 s, and the plan of that variable, declared there and in a component as large, 13.4 s
    (Linux development PC).
    """
    if not replaced:
        return ()
    kept = before.splitlines(keepends=True)
    starts = [0, *accumulate(map(len, kept))]
    # Past a line break that ends the text, a last line holding nothing, where an edit there goes.
    last = len(kept) if not kept or kept[-1].splitlines() != [kept[-1]] else len(kept) - 1

    def line_of(offset: int) -> int:
        return min(bisect_right(starts, offset) - 1, last)

    def first_line_of(edit: TextEdit) -> int:
        line = line_of(edit.start)
        if line and starts[line] == edit.start and before[edit.start - 1] == "\r":
            return line - 1
        return line

    runs: list[tuple[int, int, list[TextEdit]]] = []
    for edit in replaced:
        first, final = first_line_of(edit), line_of(edit.end)
        if runs and first <= runs[-1][1]:
            runs[-1] = (runs[-1][0], max(final, runs[-1][1]), [*runs[-1][2], edit])
        else:
            runs.append((first, final, [edit]))
    found: list[Hunk] = []
    for first, final, edits in runs:
        start = starts[first]
        end = starts[final + 1] if final + 1 < len(starts) else len(before)
        pieces: list[str] = []
        reached = start
        for edit in edits:
            pieces += (before[reached : edit.start], edit.text)
            reached = edit.end
        pieces.append(before[reached:end])
        hunk = _changed(first + 1, before[start:end].splitlines(), "".join(pieces).splitlines())
        if hunk is not None and found and found[-1].line + len(found[-1].before) == hunk.line:
            met = found.pop()
            hunk = _changed(met.line, met.before + hunk.before, met.after + hunk.after)
        if hunk is not None:
            found.append(hunk)
    return tuple(found)


def _changed(line: int, before: Sequence[str], after: Sequence[str]) -> Hunk | None:
    """The hunk of ``before``, its first line numbered ``line``, replaced by ``after``, less the
    lines that read alike at either end (:func:`_alike_at_the_ends`); ``None`` where every line
    does, and nothing changed."""
    head, tail = _alike_at_the_ends(before, after)
    if head + tail == len(before) == len(after):
        return None
    return Hunk(
        line + head,
        tuple(before[head : len(before) - tail]),
        tuple(after[head : len(after) - tail]),
    )


def _alike_at_the_ends(before: Sequence[str], after: Sequence[str]) -> tuple[int, int]:
    """How many lines the two read alike at their start, and then at their end, none of them
    counted twice: the end first, as :func:`lines_replaced` reads a run."""
    shortest = min(len(before), len(after))
    tail = 0
    while tail < shortest and before[-1 - tail] == after[-1 - tail]:
        tail += 1
    head = 0
    while head < shortest - tail and before[head] == after[head]:
        head += 1
    return head, tail


def hunks(before: str, after: str) -> tuple[Hunk, ...]:
    """The lines a change replaces in a text, each run of them numbered as the text stood: what
    ``difflib.SequenceMatcher`` answers over the lines of the two texts - for an undo's preview,
    which holds the text a file stands at and the one it is put back to, and no operation. A
    plan's lines are read off the spans its operations replace instead (:func:`lines_replaced`).

    Answered without difflib for a change made in place (:func:`_replaced_in_place`): putting back
    a unit renamed to a spelling nothing used makes such a change of every file the rename
    touched, all 1,167, in a generated project of 35,000 declarations. Any other change goes to
    difflib over both texts whole: matching the lines the two share at their start and at their
    end first would number some of them otherwise. Where the lines taken out are spelled like the
    lines beside them, which of those difflib names depends on the text all around - taking the
    first of six declarations out of a component, it answers lines 5 to 17, where the head
    matched first would answer lines 8 to 20 (``tests/test_variables.py``). That one call into
    difflib holds :data:`ddd.difflib_lock.ONE_THREAD_IN_DIFFLIB`, for this file alone.
    """
    old, new = before.splitlines(), after.splitlines()
    in_place = _replaced_in_place(old, new)
    if in_place is not None:
        return in_place
    with ONE_THREAD_IN_DIFFLIB:
        opcodes = difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes()
    return tuple(
        Hunk(first + 1, tuple(old[first:last]), tuple(new[start:end]))
        for tag, first, last, start, end in opcodes
        if tag != "equal"
    )


def _replaced_in_place(old: list[str], new: list[str]) -> tuple[Hunk, ...] | None:
    """The hunks of a change made in place, or ``None`` for any other: the two texts as long as
    each other, and each line that differs replaced by a line the old text holds nowhere, itself
    held nowhere in the new text.

    What difflib answers then, found by comparing the lines at each place. No changed line has an
    equal in the other text, so every block of equal lines difflib can match is of unchanged
    lines on both sides, and an unchanged line stands at the same place in both texts. Of the
    longest blocks, difflib takes the one earliest in the old text and then in the new, and that
    one is at the same place in both: a block at place i of the old text and j of the new is of
    unchanged lines at both places, so the lines at i, and those at j, form a block as long at
    the same place in both - and one of those two comes before it. The block taken is then a
    whole run of unchanged lines, no run being longer than the longest block, and difflib goes on
    alike on each side of it, taking every run whole. Between two runs lies a run of changed
    lines, replaced by the new text's.
    """
    if len(old) != len(new):
        return None
    changed = [index for index, (was, now) in enumerate(zip(old, new, strict=True)) if was != now]
    held, holding = set(old), set(new)
    for index in changed:
        if old[index] in holding or new[index] in held:
            return None
    runs: list[list[int]] = []
    for index in changed:
        if runs and runs[-1][1] == index:
            runs[-1][1] = index + 1
        else:
            runs.append([index, index + 1])
    return tuple(
        Hunk(first + 1, tuple(old[first:last]), tuple(new[first:last])) for first, last in runs
    )


def refusal(unsettled: Unsettled, name: str, key: str) -> tuple[str, str]:
    """The code and the sentence ``ddd gui`` refuses a settlement with, naming the declaration -
    or the variable, where every declaration of it reads it and none is the one to state a key a
    reader leaves to its producer (``unproduced``)."""
    where = f"the declaration of '{name}' in {unsettled.site.path.name}"
    if unsettled.reason == "type":
        sentence = f"{where} names the type '{unsettled.type_name}', which fixes its {key}"
    elif unsettled.reason == "kind":
        sentence = f"{where} is of a kind that does not allow that {key}"
    elif unsettled.reason == "storage":
        # The loader's own two sentences, quoted: the declaration would not load afterwards, and
        # which of the pair is at fault depends on which way the change went.
        sentence = (
            f"{where} would not load with that {key}: storage is named exactly once, and a "
            f"'datatype' comes with a 'conversion'"
        )
    elif unsettled.reason == "load":
        sentence = _would_not_load(unsettled.site, name, key, unsettled.problem)
    elif unsettled.reason == "unproduced":
        sentence = (
            f"no declaration of '{name}' produces it, and a declaration reading it leaves its "
            f"{key} to the one that does"
        )
    else:
        sentence = f"{where} is no longer where the last analysis found it"
    return SETTLE_CODES[unsettled.reason], sentence


def unloadable(
    settlement: Settlement,
    name: str,
    key: str,
    cache: dict[Path, Document],
    *,
    types: TypeConversions | None = None,
) -> tuple[str, ...]:
    """One sentence for each declaration the settlement would leave unable to load, by file.

    What the plan of a value its reader chose says, where a button offering the same value is
    withheld (:func:`ddd.lsp.edits.settled_at`): the reader may still apply it, and the next
    analysis reports the file as ``schema``, but the plan says first which file would stop loading
    and why, in the sentence ``ddd check`` files it in (:func:`ddd.models.definition_problem`).
    Asked of the definition each change leaves (:func:`ddd.lsp.edits.loading_problem`), from the
    documents the settlement was decided on - ``cache`` is the one it was given - so that no file
    is read again, and ordered by file as the settlement's preview is. ``types`` is what the
    project's types fix (:func:`ddd.lsp.edits.type_conversions`), which a declaration naming a
    string type is asked beside; without it nothing is asked of a type.
    """
    said: list[tuple[str, str]] = []
    for change in settlement.changes:
        document = read(change.site.path, cache)
        problem = loading_problem(document, change.site.pointer, key, change.raw, types=types)
        if problem is not None:
            said.append(
                (change.site.path.as_posix(), _would_not_load(change.site, name, key, problem))
            )
    return tuple(sentence for _, sentence in sorted(said))


def _would_not_load(site: Site, name: str, key: str, problem: str | None) -> str:
    """The sentence of a declaration that would not load with a key written, as the models or the
    analysis say it: the one words for the refusal of a settlement and for what a plan tells its
    reader."""
    return (
        f"the declaration of '{name}' in {site.path.name} would not load with that {key}: {problem}"
    )


def _entry(site: Site) -> str:
    """The declaration's entry of the interface, the definition's parent."""
    return site.pointer.removesuffix(".definition")


def _within(pointer: str, entry: str) -> bool:
    return pointer == entry or pointer.startswith((f"{entry}.", f"{entry}["))


def component_of(document: Document, path: Path) -> str:
    """The component's name, or ``path``'s own name when the file never states one."""
    named = document.value_at("component.name")
    return named if isinstance(named, str) else path.name.removesuffix(".ddd.json")


def role_of(scope: Any) -> str:
    """What a declaration's scope says its component does with the variable, by :data:`ROLES`:
    ``produces``, ``reads`` or ``local``, and ``reads`` for a scope it does not name."""
    return next((role for spelled, role in ROLES if spelled == scope), "reads")


def _stated(document: Document, pointer: str, keys: Iterable[str]) -> dict[str, str]:
    """The json text of each of ``keys`` the document states there, the ones holding nothing left
    out.

    A key written ``null`` states nothing: that is how a file says so, and the loader reads it as
    absent - ``ddd check`` accepts an explicit ``"typename": null`` beside a real datatype. Counted
    as stated, the variable panel offered to strip the storage a declaration actually uses and
    withheld the one holding nothing, backwards from what the loader believes, and taking that
    offer would have written a file the loader refuses.
    """
    return {
        key: raw
        for key in keys
        if (raw := document.raw_at(f"{pointer}.{key}")) is not None and raw != "null"
    }


def _fixed(built: Index, type_name: str | None, cache: dict[Path, Document]) -> dict[str, str]:
    site = None if type_name is None else built.types.get(type_name)
    if site is None:
        return {}
    return _stated(read(site.path, cache), site.pointer, FIXED_BY_A_TYPE)
