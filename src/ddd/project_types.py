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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.diagnostics import Diagnostic
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

MEMBER_KEYS: Final = ("name", "member", "typename", "datatype", "unit", "bits", "dimensions")
"""What a structure's member is shown with, in the order the panel's columns run."""


@dataclass(frozen=True, slots=True)
class TypeRow:
    """One type as the Types tab lists it."""

    name: str
    kind: str
    """``scalar``, ``external`` or ``struct``; ``""`` for an entry whose file has drifted since
    the analysis read it, which the next revision lists as it now stands."""

    description: str
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
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[TypeRow, ...]:
    """Every type the project declares, by name, with what it is and how much it has to fix."""
    filed = list(findings)
    return tuple(
        TypeRow(
            name=name,
            kind=_string(built, name, "type", cache),
            description=_string(built, name, "description", cache),
            uses=len(built.type_uses.get(name, ())),
            findings=sum(1 for file, found in filed if located_in_type(built, name, file, found)),
        )
        for name in sorted(built.types)
    )


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


def located_in_type(built: Index, name: str, file: Path, finding: Diagnostic) -> bool:
    """Whether a finding shown on ``file`` is filed inside that type's own entry - its own
    ``unknown-unit``, ``type-kind``, ``duplicate-type``, ``init-invalid`` or
    ``limits-out-of-range``, and anything else a check files at a pointer under it."""
    site = built.types.get(name)
    location = finding.location
    if site is None or location is None or site.path.resolve() != file.resolve():
        return False
    return location.pointer == site.pointer or location.pointer.startswith(
        (f"{site.pointer}.", f"{site.pointer}[")
    )


def fixed_by(built: Index, name: str, cache: dict[Path, Document]) -> dict[str, str]:
    """What the type states, as the json text it is written as, per key."""
    site = built.types.get(name)
    if site is None:
        return {}
    document = read(site.path, cache)
    kind = _string(built, name, "type", cache)
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
    """One member as the panel's columns read it, its dimensions rendered as text."""
    shown: dict[str, Any] = {key: entry[key] for key in MEMBER_KEYS if key in entry}
    sized = shown.get("dimensions")
    if isinstance(sized, list):
        # A dimension is an integer or the name of a declared constant; the column shows either.
        shown["dimensions"] = tuple(str(entry) for entry in sized)
    return shown


def _string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """One string of a type's entry, or ``""`` where the entry no longer carries one.

    Both callers already know ``name`` is one of ``built.types`` - :func:`type_rows` iterates
    that mapping's own keys and :func:`fixed_by` has just checked - so unlike the public
    functions of this module this one trusts its caller rather than repeating a guard no test
    could ever make true.
    """
    site = built.types[name]
    value = read(site.path, cache).value_at(f"{site.pointer}.{key}")
    return value if isinstance(value, str) else ""
