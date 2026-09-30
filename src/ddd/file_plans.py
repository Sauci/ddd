"""The root project's ``includes``: its entries as the loader reads them, the plans creating,
adding and removing a file of it, and what a change of the list would break, as the analysis
itself says.

Transport-neutral, like :mod:`ddd.shared_plans`: nothing here knows about http or the session,
and nothing here imports :mod:`ddd.gui`. It is for the gui to call and never calls the gui, so
findings arrive as ``(path, diagnostic)`` pairs - the shape
:func:`ddd.project_shared.shared_rows` takes for the same reason - rather than as the session's
own ``Filed``.

The entries are read by the loader's own rule, :func:`ddd.loading.included_files`, so that the
list a reader is shown and the files a run checks cannot come to two answers. A plan is the
operations of :mod:`ddd.editing` each file takes, made and never written: a file is created by
:func:`ddd.lsp.units.created_beside`, the one recipe every plan creates a file by, and an entry
is added or removed by one edit of the description.

No rule here says which kinds of file a project may do without. :func:`new_errors` counts the
errors of two analyses of one project, the second with the root's list changed, place by place,
and what the second has more of is what the change would break. It counts a finding where
``ddd check`` reports it, not again at each place an editor is shown a mirror of it, as far as
:func:`_as_reported` can tell the two apart.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import TypeAdapter, ValidationError

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.editing import Operation
from ddd.loading import included_files, resolve_path
from ddd.lsp.diagnostics import finding_identity
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit, UnitProject, created_beside, entry_appended
from ddd.models.common import Identifier
from ddd.models.reserved import is_reserved_identifier

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on, as :func:`ddd.project_shared.shared_rows` takes them."""


def new_errors(before: Sequence[Pair], after: Sequence[Pair]) -> tuple[Pair, ...]:
    """The errors ``after`` has more of than ``before``, in ``after``'s order: what a change of
    the root's ``includes`` would break, ``before`` being what the project reports now and
    ``after`` what it would report with the list changed.

    Errors only, after each run's severity policy: the line ``ddd check`` draws between a
    project that passes and one that fails. A warning a change brings is for the reader to see
    once it is made, not a reason to call the change breaking.

    Of what each side lists, what it reports is counted - what :func:`_as_reported` leaves, which
    for ddd's own checks is each finding where ``ddd check`` reports it, and not again at each
    place a note of it points to, where an editor is shown a mirror of it. Where a note points
    at a declaration ddd picks by an order a removal can change - the owner, the first
    declaration read, the name sorting first - the mirrors move with it, and counted, they read
    as new errors where the findings stayed where they were.

    Counted, not matched, in two passes over the errors ``after`` reports. First each one
    ``before`` reports word for word - :func:`~ddd.lsp.diagnostics.finding_identity` - uses that
    one up; then each one left uses up one ``before`` reports, still unused, under the same
    :func:`_key` - its check, severity and place - and one with none left to use up is new. Word
    for word first, so that where a place that had one error has two, the error reported is the
    one the project does not have: taken by key alone in ``after``'s order, a new error listed
    first used up the old one's key, and the old one was quoted as new.

    Per place costs something both ways. ddd reports some findings on declarations it picks by
    an order a removal can change - the owner, the order it reads the project in, the first
    declaration read of a name, the first local, the first copy of an enum met - and a harmless
    removal that moves one is refused wherever the move raises the count of its check and
    severity at a place, quoting the error the project has, reworded where its words name that
    order. Measured, so is a removal that relabels an error - a local gone, its other writers'
    ``local-conflict`` reported as ``multiple-producers`` - or re-counts one against a new
    reference, each quoting an error the project would really have. The other way, a new error
    is hidden only where an error of its check and severity leaves the same place - with the
    same message, where the place is a whole file or none - or where it has the shape of a
    mirror (see :func:`_as_reported`). A check filing every finding at one place, as a plugin's
    may, hides there up to as many new errors as leave. ddd's own ``definition-mismatch`` reaches
    the first way under the default severities, measured. A removal can take out the declaration
    a comparison is made against - the owner, where several components write a variable, or the
    first declaration read, where none does - and a declaration that disagreed with it on one
    field, and disagrees on another with the one compared against next, keeps its check and its
    place, so the count there does not move: ``W1`` writes ``X`` as ``uint16`` in ``rpm`` and
    owns it, its name sorting first, ``W2`` writes it as ``uint32`` in ``Nm``, and ``R`` reads
    it as ``uint32`` in ``rpm``; removing ``W1`` turns ``R``'s disagreement with ``W1`` over its
    datatype into one with ``W2`` over its unit, and is allowed. A build lowering
    ``duplicate-component`` or ``duplicate-type`` reaches it too, measured: removing the first
    declaration lets in the one the loader dropped, and a reader's disagreement at its
    declaration changes what it is about while its place stays. So does a build raising
    ``storage-mismatch`` to an error, measured: that check compares the same two declarations,
    and with the owner gone a reader's storage disagreement moves from one field to another at
    its place. What holds is a bound: a change bringing a new error is answered with none only
    where the project has an error of that error's check and severity now - at its place, or,
    for one with a mirror's shape, at the place of the finding it copies - so a project with no
    errors is never made to fail this way.

    What is reported is never a mirror :func:`_as_reported` tells, and never, word for word, an
    error ``before`` reports: a revision never lists one identity twice,
    :func:`~ddd.lsp.diagnostics.group_findings` filing each once, and the first pass sets each
    of those aside - given one twice where ``before`` reports it once, the second is reported.
    It can have the words of a mirror ``before`` lists, which is not counted: measured, an
    enum's first copy met, read later and differing from the copy met first now, is reported in
    the words of the mirror it was shown.

    Of ``before``, warnings are counted too: every key carries its finding's severity, so only
    an error the project has now can be used up by an error of ``after``. The filters are
    statements in loops rather than comprehensions', which coverage.py counts no branch in.
    """
    had = _as_reported(before)
    identities = Counter(finding_identity(diagnostic) for _, diagnostic in had)
    keys = Counter(_key(diagnostic) for _, diagnostic in had)
    unmatched: list[Pair] = []
    for found in _as_reported(after):
        _, diagnostic = found
        if diagnostic.severity is not Severity.ERROR:
            continue
        identity = finding_identity(diagnostic)
        if identities[identity] > 0:
            identities[identity] -= 1
            keys[_key(diagnostic)] -= 1
            continue
        unmatched.append(found)
    fresh: list[Pair] = []
    for found in unmatched:
        key = _key(found[1])
        if keys[key] > 0:
            keys[key] -= 1
            continue
        fresh.append(found)
    return tuple(fresh)


def _as_reported(pairs: Sequence[Pair]) -> list[Pair]:
    """``pairs`` less what is shaped like a mirror :func:`~ddd.lsp.diagnostics.group_findings`
    adds of a finding, so that an editor marks both sides of a clash: the finding again, without
    notes, at each other place a note of it points to.

    A mirror is told by its shape, as :func:`~ddd.lsp.diagnostics._mirrors` makes one: no notes,
    at the place a note of a finding of its check, severity and message points to - a note with
    a place other than that finding's own, of a finding with a place.

    The shape is a mirror's alone where no finding a run reports has the check, severity,
    message and place of another's mirror, which holds of ddd's own checks: each note they make
    that has a place points at another place its finding is about - the owner, the first read,
    the first copy met - and none of them reports a finding of that check and message there. A
    plugin's check can, and then ``group_findings``, filing one identity once, files the finding
    and a mirror as one: the finding can go uncounted, and mirrors of it be counted in its stead.
    """
    copied: set[tuple[str, Severity, str, Location]] = set()
    for _, diagnostic in pairs:
        placed = diagnostic.location
        if placed is None:
            continue
        for _, noted in diagnostic.notes:
            if noted is None:
                continue
            if noted == placed:
                continue
            copied.add((diagnostic.check, diagnostic.severity, diagnostic.message, noted))
    reported: list[Pair] = []
    for found in pairs:
        diagnostic = found[1]
        if diagnostic.notes:
            reported.append(found)
            continue
        shape = (diagnostic.check, diagnostic.severity, diagnostic.message, diagnostic.location)
        if shape in copied:
            continue
        reported.append(found)
    return reported


def _key(diagnostic: Diagnostic) -> tuple[object, ...]:
    """What an error no error of ``before`` matches word for word is counted as: its check, its
    severity and its place, but never its wording where it has a place of its own.

    A message may name what else the project holds: the writers of a variable, in an order the
    reading sets, or a constant spelled nearly like the one a shape names. Once a file is gone
    the same error at the same place can read differently - the near miss is no longer
    suggested - and keyed by its message, as the editor keys a finding, it would read as new.

    Counted per place, a check cannot see an error whose meaning changes while its place stays:
    one gone and another come at one pointer read as the one the project had.
    """
    return (diagnostic.check, diagnostic.severity, _place(diagnostic))


def _place(diagnostic: Diagnostic) -> tuple[object, ...]:
    """Where an error is: the file and pointer of a placed finding; and for one on a whole file,
    or on no place at all, its message as well, since nothing narrower tells two of those apart.
    The three are of three lengths, so that none can ever be taken for another.

    A finding at one of the root's own ``includes`` entries is placed by its position like any
    other, although removing an entry moves every later one up. ddd files there only while it
    reads the project, and a run whose read reports an error is never analysed, so where every
    run of ``before`` was analysed no error of ddd's own sits at an entry, and one there after the
    change is new whichever way it is keyed. A plugin's check is not told the list a run was
    given, only able to read the one in the file, which the change leaves as it was: keyed by
    the entry the changed list has at that position, its unchanged finding would read as new.
    """
    location = diagnostic.location
    if location is None:
        return (diagnostic.message,)
    if not location.pointer:
        return (location.path, location.pointer, diagnostic.message)
    return (location.path, location.pointer)


CREATABLE: Final = ("component", "types", "units", "constants", "sections", "rasters")
"""The kinds :func:`create_plan` makes a file of, in the order a reader is to be offered them.
Not ``project``: a sub-project's own includes belong to opening it, and are out of the Files
tab's reach (spec §6)."""

FILE_NAME: Final = re.compile(r"[A-Za-z0-9_-]+")
"""A name a new file may take, before ``.ddd.json`` is added: one or more of the letters ``a``
to ``z`` and ``A`` to ``Z``, the digits ``0`` to ``9``, ``_`` and ``-`` - ascii's, so ``é`` or
``٣`` is refused though it is a letter or a digit. No separator, so a file can only ever be
created beside the description, and no dot, so the suffix is always the one every project
committed to this repository uses."""

_SUFFIX: Final = ".ddd.json"
"""What :func:`create_plan` adds to a name :data:`FILE_NAME` takes."""

_COMPONENT_NAME: Final[TypeAdapter[str]] = TypeAdapter(Identifier)
"""The model's own judge of a component's name - :class:`~ddd.models.component.Component` takes
an :data:`~ddd.models.common.Identifier` - so that a name it refuses is exactly one whose file
would not load, and no second spelling of the rule can drift from the first. The first check
:func:`_component_name` asks of a name. Built once: a :class:`~pydantic.TypeAdapter` compiles a
core schema from the annotation."""


class FileRefusalError(Exception):
    """A change of the project's files that is not made, and why - as the other plan modules'
    refusals."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``not-found``: the file to add is not there, or no entry has the path to remove.
    ``invalid``: the change cannot be made - a kind or a name a new file may not take, a file
    of that name there already, a file the project has already, a file only a pattern brings
    in. ``unreadable``: a first units file cannot list every unit, a file of the project not
    having loaded."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class IncludedEntry:
    """One entry of the root's ``includes``, as the loader's own rule reads it."""

    index: int
    """Where it is in the list: a finding filed at the entry is at ``project.includes[index]``."""

    entry: str
    """The entry as it is written."""

    names: bool
    """Whether the entry names an existing file, and so is that file whatever it spells: the
    loader tries an entry as a file before it reads it as a pattern. One naming none is a plain
    path naming no file - one that is not there, or a directory, each reported
    ``file-not-found`` by ``ddd check`` - or one holding a wildcard, a pattern that may match
    nothing, reported ``include-empty`` where it does."""

    key: Path
    """The description's directory joined with the entry and resolved, as the loader joins an
    entry to read it as a file: the file, for an entry naming one, and otherwise the path or the
    pattern the entry spells. What a row of it is selected by."""

    files: tuple[Path, ...]
    """The files the entry brings that exist, resolved: its own, for an entry naming one; a
    pattern's matches, in the loader's order, the project description never among them; none,
    for a path naming no file and for a pattern matching none."""


@dataclass(frozen=True, slots=True)
class FilePlan:
    """What adding or removing an entry takes: the edit of the description, the root's
    ``includes`` as the edit leaves them - the entries that are strings, in order - and, for a
    removal, the pattern that keeps the file in the project all the same, where one does, and the
    entries taken out.

    One decision, read twice. ``includes`` is the list to hand
    :func:`ddd.gui.session.findings_with`, which analyses the project with the root's list
    replaced; made here beside the edit rather than again from the disk, it cannot come to
    another answer than the edit it goes with - an entry listed twice is taken out everywhere,
    for one."""

    edits: tuple[PlannedEdit, ...]
    includes: tuple[str, ...]
    kept_by: str | None = None
    """For a removal, the first entry of ``includes`` that still brings the file in, each read
    as the loader reads it (:func:`ddd.loading.included_files`): a pattern, every entry naming
    the file being taken out. The file stays in the project then, and a reader is to be told so
    by this answer rather than by the page working it out. ``None`` where no entry left brings
    it in, and always for an addition."""

    removed: tuple[str, ...] = ()
    """For a removal, every entry taken out, each as the description writes it, in the order
    the list has them: what a sentence about the removal names it by - the key it was asked by
    names where the entry leads, which a link on the way can make a path no entry spells. Empty
    for an addition."""


def included_entries(project: Path, cache: dict[Path, Document]) -> tuple[IncludedEntry, ...]:
    """The root's ``includes``, each entry in order: read off the description when asked, not
    recorded by a run, and by the loader's own rule, :func:`ddd.loading.included_files` - which
    exists so that nothing asking which files a project includes comes to another answer than
    the run that checks it.

    The description is resolved first: ``included_files`` leaves its ``source`` out of a
    pattern's matches, which are resolved paths, so a ``*.ddd.json`` beside a description
    spelled any other way would match the description too.

    An ``includes`` that is not a list has no entries here, and an entry that is not a string is
    no row, the loader refusing both with a ``schema`` error; the entries that are strings keep
    the index they have in the list. The filter on ``files`` is a statement in a loop rather
    than a comprehension's, which coverage.py counts no branch in.
    """
    described = resolve_path(project)
    listed = read(described, cache).value_at("project.includes")
    if not isinstance(listed, list):
        return ()
    found: list[IncludedEntry] = []
    for index, entry in enumerate(listed):
        if not isinstance(entry, str):
            continue
        key = resolve_path(described.parent / entry)
        files: list[Path] = []
        for file in included_files(described, entry):
            if file.is_file():
                files.append(file)
        found.append(IncludedEntry(index, entry, key.is_file(), key, tuple(files)))
    return tuple(found)


def create_plan(
    project: Path,
    kind: str,
    name: str,
    component: str | None,
    taken: Collection[str],
    units: UnitProject,
    built: Index | None,
    cache: dict[Path, Document],
    *,
    checks_units: bool,
) -> tuple[PlannedEdit, ...]:
    """A new file of ``kind``, called ``name`` and ``.ddd.json``, beside the description and
    appended to its ``includes`` in one plan: created by :func:`ddd.lsp.units.created_beside`,
    in the one shape :func:`ddd.gui.session._confined` lets a file be created in. One edit per
    file, sorted by path, as the recipe's other two callers sort them.

    The entry appended is the file's own name, whatever else reaches it already: ``_confined``
    lets a file be created only where an entry of the edited ``includes`` names it as a file -
    a pattern is never expanded - and the description is changed in the same edit. The cost: a
    pattern matching the new name, or an entry naming the file while it is missing, leaves it
    listed twice. Measured with a component created both ways, the loader reads it once and
    ``ddd check`` passes.

    Refused ``invalid``, in this order, before anything is built: a kind not in
    :data:`CREATABLE`; a name :data:`FILE_NAME` does not take; a file of that name beside the
    description already; and for a component, no name for it, or a name a check of the project
    would reject - one the model's own :data:`~ddd.models.common.Identifier` does not take, one
    reserved, or one of ``taken``, the names the project's components have, or of them but for
    its case (:func:`_component_name`).

    A vocabulary file declares nothing, and a component has its name and an empty
    ``interface``. A units file is the exception: where ``checks_units`` is false, it lists
    every unit the project states, each with an empty description. A units file opts the whole
    project into the unit check whatever it declares, and one created empty would have every
    stated unit reported ``unknown-unit`` at once - the one click making a passing project fail.
    The list is refused ``unreadable`` where a file of the project did not load, or no index of
    the project was built to list it from, since it could not then be complete - refused as
    :func:`ddd.lsp.units.adoption` refuses adopting.

    ``checks_units`` says whether a file of the project's tree is a units file already, and
    :attr:`~ddd.lsp.units.UnitProject.units_files` cannot: it is read out of the description's
    own ``includes``, where what opts a project in is a units file anywhere in its tree, a
    sub-project's included (:attr:`ddd.loading.Workspace.units_files`). A project whose one
    units file is a sub-project's is opted in already, and a root units file listing its units
    again fails it with a ``duplicate-unit`` for each: measured on ``examples/vocabulary``
    included as a sub-project by a root with no units file of its own, three units stated made
    three errors, where the file created empty adds one ``empty-vocabulary`` at INFO. Only a
    caller holding every file of the tree can say which it is.
    """
    described = resolve_path(project)
    if kind not in CREATABLE:
        raise FileRefusalError(
            "invalid",
            f"no file of kind '{kind}' can be created here; the kinds that can are "
            f"{', '.join(CREATABLE[:-1])} and {CREATABLE[-1]}",
        )
    if FILE_NAME.fullmatch(name) is None:
        raise FileRefusalError(
            "invalid",
            f"'{name}' cannot name a new file: a name is one or more of the letters a to z and "
            f"A to Z, the digits 0 to 9, '_' and '-', and {_SUFFIX} is added to it",
        )
    filename = f"{name}{_SUFFIX}"
    if (described.parent / filename).exists():
        raise FileRefusalError("invalid", f"{filename} is there already, beside {described.name}")
    content = _content(described, kind, component, taken, units, built, checks_units=checks_units)
    edits = created_beside(described, filename, json.dumps(content, ensure_ascii=False), cache)
    return tuple(sorted(edits, key=lambda edit: edit.path.as_posix()))


def _content(
    described: Path,
    kind: str,
    component: str | None,
    taken: Collection[str],
    units: UnitProject,
    built: Index | None,
    *,
    checks_units: bool,
) -> dict[str, Any]:
    """What a new file of ``kind`` holds, or the refusal its component's name or its units meet.

    Each arm its own statement rather than an ``and`` or an ``or`` in one ``if``, which
    coverage.py counts as one branch whichever operand decided it.
    """
    if kind == "component":
        return {"component": {"name": _component_name(component, taken), "interface": []}}
    if kind != "units":
        return {kind: []}
    if checks_units:
        return {"units": []}
    return {
        "units": [
            {"unit": unit, "description": ""} for unit in _stated_units(described, units, built)
        ]
    }


def _component_name(component: str | None, taken: Collection[str]) -> str:
    """A new component's name, or the refusal it meets.

    Past the name's absence, each refusal is a check a project holding the component would
    fail, asked the way that check asks it, in this order:

    * the model's :data:`~ddd.models.common.Identifier`, through :data:`_COMPONENT_NAME`: the
      component's file would not load, its ``schema`` error;
    * :func:`~ddd.models.reserved.is_reserved_identifier`, the judge of the ``reserved-identifier``
      the analysis files on a component's name, and the one
      :func:`ddd.lsp.navigation.rename_problem` asks of a name too;
    * a name of ``taken``: the loader's ``duplicate-component``;
    * a name differing from one of ``taken`` only in upper and lower case: the analysis's
      ``name-collision``, which :meth:`ddd.analysis._Analysis._check_component_names` finds by
      grouping components under :meth:`str.lower`, as this compares them. The sentence names
      the component already there, whose name the reader did not type.

    So a name refused is exactly one those checks reject - read with ``taken`` the name of every
    component the project loads, and under the default severities, where each of those checks is
    an error; a build lowering ``reserved-identifier`` or ``name-collision`` still has such a name
    refused here, which is the safe way. ``taken`` is read in sorted order, so that of two names
    differing only in case - a project failing ``name-collision`` already - the one named is the
    same on every run.
    """
    if component is None:
        raise FileRefusalError("invalid", "a new component needs a name, besides its file's")
    try:
        _COMPONENT_NAME.validate_python(component)
    except ValidationError as refused:
        raise FileRefusalError(
            "invalid", f"'{component}' cannot name a component, not being a usable c identifier"
        ) from refused
    if is_reserved_identifier(component):
        raise FileRefusalError(
            "invalid",
            f"'{component}' cannot name a component, being reserved by c or by a header DDD "
            "generates",
        )
    if component in taken:
        raise FileRefusalError(
            "invalid", f"this project has a component called '{component}' already"
        )
    for other in sorted(taken):
        if other.lower() == component.lower():
            raise FileRefusalError(
                "invalid",
                f"this project has a component called '{other}' already, and '{component}' "
                "differs from it only in upper and lower case, so the two would ask for the same "
                "generated header",
            )
    return component


def _stated_units(described: Path, units: UnitProject, built: Index | None) -> list[str]:
    """Every unit the project states, by code point, as :func:`ddd.lsp.units.adoption` lists
    them - or the refusal where the list could not be complete."""
    if units.unread:
        raise FileRefusalError(
            "unreadable",
            f"{', '.join(file.name for file in units.unread)} did not load, so a first units "
            "file could not list every unit in use",
        )
    if built is None:
        raise FileRefusalError(
            "unreadable",
            f"{described.name} did not load, so a first units file could not list every unit "
            "in use",
        )
    return sorted(built.units)


def add_plan(project: Path, entry: str, cache: dict[Path, Document]) -> FilePlan:
    """``entry`` - a path to an existing file, relative to the description, as the reader wrote
    it - appended to the root's ``includes`` as written. Always a literal: the loader reads an
    entry naming a file as that file, whatever it spells.

    Refused, in this order, by what the description and the files on disk can answer: ``entry``
    naming no file, ``not-found``, a file that is not there being created rather than added;
    naming the description itself, ``invalid``; naming a file the project has already - named by
    an entry, or matched by a pattern, which the refusal names - ``invalid``. Whether the file
    lies where the caller may read it, and whether it is a kind of file the loader recognises,
    are the caller's to ask: the first needs the directories the session serves, and the second
    the kind rule :func:`ddd.gui.session.kind_of` holds, which this module, importing nothing of
    :mod:`ddd.gui`, cannot ask.

    Added by :func:`ddd.lsp.units.entry_appended`, the rule a created file's entry is added by
    too: at the end of the list; or, where the description has no ``includes``, as a list of its
    own; or at the front of an ``includes`` that is there and is no list, for the edit engine to
    refuse.
    """
    described = resolve_path(project)
    added = resolve_path(described.parent / entry)
    if not added.is_file():
        raise FileRefusalError(
            "not-found", f"{entry} names no file; a file not there yet is created, not added"
        )
    if added == described:
        raise FileRefusalError(
            "invalid", f"{entry} is this project's own description, which it cannot include"
        )
    entries = included_entries(described, cache)
    for included in entries:
        if added not in included.files:
            continue
        if included.names:
            raise FileRefusalError(
                "invalid",
                f"{entry} is part of this project already, as the entry '{included.entry}'",
            )
        raise FileRefusalError(
            "invalid",
            f"{entry} is part of this project already: the pattern '{included.entry}' brings it in",
        )
    return FilePlan(
        (PlannedEdit(described, (entry_appended(described, entry, cache),)),),
        (*(included.entry for included in entries), entry),
    )


def remove_plan(project: Path, path: Path, cache: dict[Path, Document]) -> FilePlan:
    """Every entry of the root's ``includes`` whose key is ``path`` taken out - ``path`` being a
    row's key as :func:`included_entries` answers it. A pattern's key takes the pattern out
    whole. The files stay on disk.

    Every one, where two spellings of one file are one key: removing a row is to take its file
    out of the project, and an entry left naming it would keep it in. The last goes first, since
    the edit engine makes a file's operations in turn and taking an entry out moves every later
    one up. A pattern left that matches the file keeps it in all the same - taking the pattern
    out would take out every other file it matches - and :attr:`FilePlan.kept_by` names it.

    Refused ``invalid`` where no entry has that key and a pattern matches it, naming the
    pattern, which goes only whole; ``not-found`` where neither holds. Both are read off one
    answer, :func:`_brought_by`'s over the entries a removal leaves: where no entry has the key,
    that is every entry, and the pattern bringing the file in is the one refused.
    """
    described = resolve_path(project)
    removed: list[IncludedEntry] = []
    kept: list[IncludedEntry] = []
    for included in included_entries(described, cache):
        if included.key == path:
            removed.append(included)
        else:
            kept.append(included)
    brought_by = _brought_by(kept, path)
    if removed:
        operations = tuple(
            Operation("remove", f"project.includes[{gone.index}]") for gone in reversed(removed)
        )
        return FilePlan(
            (PlannedEdit(described, operations),),
            tuple(left.entry for left in kept),
            kept_by=brought_by,
            removed=tuple(gone.entry for gone in removed),
        )
    if brought_by is not None:
        raise FileRefusalError(
            "invalid",
            f"{path.name} has no entry of its own: the pattern '{brought_by}' brings it in, and "
            "only the whole pattern can be removed",
        )
    raise FileRefusalError(
        "not-found",
        f"no entry of {described.name}'s includes names {path.name}, and none of its patterns "
        "matches it",
    )


def _brought_by(entries: Sequence[IncludedEntry], path: Path) -> str | None:
    """The first of ``entries`` bringing the file ``path`` in, as the loader reads each, or
    ``None`` where none does.

    Asked of entries whose key is not ``path``, which makes what it answers a pattern: an entry
    naming a file brings in that file alone, and its key is that file. The loader reads each
    entry by itself, so what one brings in does not change with the entries around it, and the
    answer is the loader's after the change as well as before it.
    """
    for included in entries:
        if path in included.files:
            return included.entry
    return None
