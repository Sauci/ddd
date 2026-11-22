"""A project's types as the Types tab of ``ddd gui`` shows them.

Transport-neutral, like :mod:`ddd.project_units`: nothing here knows about http or the session.
Where a type is declared and which declarations and members name it is the navigation index's own
record (:attr:`ddd.lsp.navigation.Index.types` and :attr:`~ddd.lsp.navigation.Index.type_uses`),
and what a type *says* - its datatype, its unit, the members of a structure - is read from the
document at that entry, the way a unit's description is. Nothing is parsed into the models: a
value travels as the json text it is written as, so ``1.0`` reaches an edit as the three
characters its author typed.

Every function answers empty for a name the index does not hold. The api looks a type up before it
asks, so that arm is only reachable from a test - which is where it is covered.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.diagnostics import Diagnostic
from ddd.findings_by_file import FindingsByFile, Pair, noted_at
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.variables import declarations_of

_MEMBER_TYPENAME: Final = re.compile(
    r"^((?:component\.)?types\[\d+\])\.(members\[\d+\])\.typename$"
)
"""A member's ``typename``, and the two halves of its address: the structure, and the member.

The ``component.`` prefix is optional because a component may declare its own types inline,
alongside its interface, at ``component.types[i]`` rather than a types file's own ``types[i]``
(:mod:`ddd.loading` registers both the same way, under one name). ``ddd.lsp.navigation``'s own
``_MEMBER`` matches the same two homes, for the same reason.
"""

SCALAR_KEYS: Final = ("datatype", "unit", "conversion", "limits")
"""What a scalar type fixes, in the order the panel lists it."""

REPEATED: Final = "duplicate-type"
"""The check the loader files a later entry under that repeats a type's name, in another file - one
file declaring a name twice does not load - filed at that entry, of which the analysis keeps
nothing, with a note naming the first. Of the findings filed where the index records no type, it is
the one that is a type's (:func:`located_in_type`), as
:attr:`ddd.project_shared.Vocabulary.repeated` is a shared entry's."""


@dataclass(frozen=True, slots=True)
class TypeRow:
    """One type as the Types tab lists it."""

    name: str
    kind: str
    """``scalar``, ``external`` or ``struct``; ``""`` for an entry whose file has drifted since
    the analysis read it, which the next revision lists as it now stands: one that no longer says
    its kind, and one whose place the index recorded no longer names it (:func:`type_in_place`)."""

    description: str
    """What its entry says it is; ``""`` where it says nothing, and where its place no longer names
    it, as for :attr:`kind`."""

    uses: int
    """How many declarations and structure members name it."""

    findings: int
    """How many findings are filed inside its own entry."""


@dataclass(frozen=True, slots=True)
class Use:
    """One place a type is named, as its panel lists it."""

    site: Site
    kind: str
    """``variable`` for a declaration's ``typename``, ``member`` for a structure member's."""

    name: str
    """The variable's name, or ``Sensor_t.latest`` for a member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member."""

    role: str | None
    """``produces``, ``reads`` or ``local``; ``None`` for a member."""


def type_rows(
    built: Index, findings: FindingsByFile, cache: dict[Path, Document]
) -> tuple[TypeRow, ...]:
    """Every type the project declares, by name, with what it is and how much it has to fix: each
    row :func:`row_of`'s, so that the table and a panel's own row count a type's findings by the
    one rule, :func:`type_findings`'.

    A row asks the findings of its own entry's file, and of the files of the findings naming its
    record by a note, which :class:`FindingsByFile` resolved once per file, and walks no other:
    O(types + files) resolves instead of O(types x findings) with two each.

    The rows are the index's, a type taken out of its file since the analysis among them until the
    next one lands; what each says of itself is read where the index recorded it (:func:`_said`).
    """
    return tuple(row_of(built, name, findings, cache) for name in sorted(built.types))


def row_of(
    built: Index,
    name: str,
    findings: FindingsByFile,
    cache: dict[Path, Document],
) -> TypeRow:
    """One type's own row: what :func:`type_rows` would answer for ``name`` alone, without
    building every other type's row alongside it - what ``GET /api/type`` pulls one of from its
    whole table today. Trusts ``name`` is one of ``built.types``, as the api checks before it
    asks, the way :func:`type_rows`' own comprehension does by never naming one it did not."""
    kind, description = _said(built, name, cache)
    return TypeRow(
        name=name,
        kind=kind,
        description=description,
        uses=len(built.type_uses.get(name, ())),
        findings=len(type_findings(built, name, findings)),
    )


def _said(built: Index, name: str, cache: dict[Path, Document]) -> tuple[str, str]:
    """What a type's row reads of its own entry, its kind and its description - two empty strings
    where the place the index recorded no longer names it (:func:`type_in_place`).

    An entry above taken out of the file's list, or put back by an undo, leaves another type at
    that place, or none, until the analysis reads the file again: the row keeps its name and shows
    none of another type's keys. Trusts ``name`` is one of ``built.types``, as :func:`type_rows`
    and :func:`row_of` do.
    """
    if not type_in_place(built, name, cache):
        return "", ""
    return kind_of(built, name, cache), _string(built, name, "description", cache)


def type_findings(built: Index, name: str, findings: FindingsByFile) -> list[Pair]:
    """Every finding of ``name``'s own, in the order given: what :func:`located_in_type` keeps of
    every finding, asked only of the findings on the file the entry is in and on the files of the
    findings naming its record by a note (:meth:`~ddd.findings_by_file.FindingsByFile.noting`) -
    a later entry repeating its name is on one of those - which are the only ones it can keep.
    Trusts ``name`` is one of ``built.types``, as :func:`row_of` does."""
    site = built.types[name]
    files = [site.path, *(file for file, _ in findings.noting(site.path, site.pointer))]
    return [
        (file, found)
        for file, found in findings.on_any(files)
        if located_in_type(built, name, file, found, findings.resolve)
    ]


def uses_of(built: Index, name: str, cache: dict[Path, Document]) -> tuple[Use, ...]:
    """Every place the index recorded naming ``name``, in the order it recorded them.

    A declaration comes with its component and its role as :func:`ddd.variables.declarations_of`
    reads them, and one its file no longer declares where the index recorded it is left out, as
    that function leaves it out: the file changed since the analysis, and the next revision lists
    it where it went.
    """
    found: list[Use] = []
    for site in built.type_uses.get(name, ()):
        document = read(site.path, cache)
        within = _MEMBER_TYPENAME.match(site.pointer)
        if within is not None:
            owner = document.value_at(f"{within.group(1)}.name")
            member = document.value_at(f"{within.group(1)}.{within.group(2)}.name")
            if isinstance(owner, str) and isinstance(member, str):
                found.append(Use(site, "member", f"{owner}.{member}", None, None))
            continue
        definition = site.pointer.removesuffix(".typename")
        variable = document.value_at(f"{definition}.name")
        if not isinstance(variable, str):
            continue
        declared = next(
            (
                entry
                for entry in declarations_of(built, variable, cache)
                if entry.site == Site(site.path, definition)
            ),
            None,
        )
        if declared is not None:
            found.append(Use(site, "variable", variable, declared.component, declared.role))
    return tuple(found)


def located_in_type(
    built: Index,
    name: str,
    file: Path,
    finding: Diagnostic,
    resolve: Callable[[Path], Path] = Path.resolve,
) -> bool:
    """Whether a finding shown on ``file`` is that type's own: filed inside its own entry - its own
    ``unknown-unit``, ``type-kind``, ``duplicate-type``, ``init-invalid`` or
    ``limits-out-of-range``, and anything else a check files at a pointer under it - or the
    loader's refusal of a later entry repeating its name (:data:`REPEATED`), filed at that entry
    in another file and naming this one's record by its note. The panel that refusal leads to is
    this type's, the later entry's name being this one's, and it lists the refusal at both places
    it is filed, its note's being this entry's own (14:M8).

    ``resolve`` resolves both paths compared; :func:`type_findings` passes its findings' own
    (:meth:`ddd.findings_by_file.FindingsByFile.resolve`), which resolves no path a revision's
    analysis resolved already."""
    site = built.types.get(name)
    if site is None:
        return False
    if resolve(site.path) == resolve(file) and _within_entry(finding, site):
        return True
    return finding.check == REPEATED and noted_at(finding, site.path, site.pointer, resolve)


def _within_entry(finding: Diagnostic, site: Site) -> bool:
    """Whether a finding's own location lands inside that entry: its own pointer, or a key, a
    member or an enumerator nested under it. ``False`` for a finding with no location at all - a
    check about the project rather than a place in a file."""
    location = finding.location
    return location is not None and (
        location.pointer == site.pointer
        or location.pointer.startswith((f"{site.pointer}.", f"{site.pointer}["))
    )


def kind_of(built: Index, name: str, cache: dict[Path, Document]) -> str:
    """What kind of type this is, as its own entry says it: ``scalar``, ``external`` or ``struct``.

    ``""`` for a name the index does not hold, and where the place the index recorded holds no
    ``type`` now. Read at that place whatever stands there: once an entry above is put in or taken
    out since the analysis read the file, the place holds another type, whose kind this answers -
    so whoever must know the entry is still this one asks :func:`type_in_place` first, as the
    type's panel does and :func:`ddd.type_plans.set_key` does. Public because changing a type
    reads it too - which keys a kind lets the interface set is :data:`ddd.type_plans.SETTABLE`'s
    answer, and a second module spelling out where a kind is written would be a second place to
    keep in step.
    """
    return _string(built, name, "type", cache) if name in built.types else ""


def type_in_place(built: Index, name: str, cache: dict[Path, Document]) -> bool:
    """Whether the entry the index recorded for ``name`` still names it, its file read as it now
    stands: an entry above taken out of the file's list, or put back by an undo, leaves another
    type at that place, or none, until the analysis reads the file again - and every key the panel
    shows is read there. Asked by the type's panel before it reads the entry, as
    :func:`ddd.variables.declarations_of` checks a declaration's name. Trusts ``name`` is one of
    ``built.types``, as the route checks before it asks."""
    return _string(built, name, "name", cache) == name


def fixed_by(built: Index, name: str, cache: dict[Path, Document]) -> dict[str, str]:
    """What the type states, as the json text it is written as, per key."""
    site = built.types.get(name)
    if site is None:
        return {}
    document = read(site.path, cache)
    kind = kind_of(built, name, cache)
    keys = ("description", *SCALAR_KEYS) if kind == "scalar" else ("description", "header")
    stated: dict[str, str] = {}
    for key in keys:
        value = document.value_at(f"{site.pointer}.{key}")
        if value is not None:
            stated[key] = json.dumps(value)
    return stated


def members_of(built: Index, name: str, cache: dict[Path, Document]) -> tuple[dict[str, Any], ...]:
    """Each member of a structure as the panel lists it, in the file's order; empty for a type
    that is not one."""
    site = built.types.get(name)
    if site is None:
        return ()
    document = read(site.path, cache)
    listed = document.value_at(f"{site.pointer}.members")
    if not isinstance(listed, list):
        return ()
    return tuple(_member(entry) for entry in listed if isinstance(entry, dict))


def _member(entry: dict[str, Any]) -> dict[str, Any]:
    """One member as the panel's columns read it, every key of the panel's columns answered.

    Each key is read by what the reply wants of it, as :func:`_string` reads a type's: a save
    that still parses but holds a member without its ``name``, or a ``bits`` that is no integer,
    is answered before the next analysis files its finding, and what the file holds there is not
    an answer. A ``name`` that is no text reads ``""``, a ``member`` that is neither of the two
    reads ``value``, a ``typename``, ``datatype``, ``unit`` or ``bits`` of the wrong kind reads
    ``None`` and ``dimensions`` that is no list reads none; a dimension is an integer or the
    name of a declared constant, and the column shows either as text.
    """
    sized = entry.get("dimensions")
    bits = entry.get("bits")
    return {
        "name": _text(entry.get("name")) or "",
        "member": "bits" if entry.get("member") == "bits" else "value",
        "typename": _text(entry.get("typename")),
        "datatype": _text(entry.get("datatype")),
        "unit": _text(entry.get("unit")),
        "bits": bits if isinstance(bits, int) and not isinstance(bits, bool) else None,
        "dimensions": tuple(str(each) for each in sized) if isinstance(sized, list) else (),
    }


def _text(value: object) -> str | None:
    """``value`` where it is text, else ``None``."""
    return value if isinstance(value, str) else None


def _string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """One string of a type's entry, or ``""`` where the entry no longer carries one.

    Its callers have all established that ``name`` is one of ``built.types`` - :func:`kind_of`
    checks, :func:`fixed_by` has just checked - so unlike the public functions of this module
    this one trusts its caller rather than repeating a guard no test could ever make true.
    """
    site = built.types[name]
    value = read(site.path, cache).value_at(f"{site.pointer}.{key}")
    return value if isinstance(value, str) else ""
