"""The fixes a finding of ``ddd gui`` carries.

Most checks have none: they name what is wrong, and the panel that owns the key is where a
reader settles it. One has a fix with nowhere else to go - ``missing-id``, an identity for a
producing declaration that states none - and this plans it as operations on json pointers, the
form ``POST /api/edit`` applies.

The language server offers the same fix as a text edit with a range, computed by
:mod:`ddd.identity` from the same walk this reads: which declarations want an id is decided in
one place, and only how the edit is spelled differs between the two clients.

A list of fixes rather than one, so that the second check to grow a fix needs no new shape.
One file per fix, because that is what a fix is: a change reaching several files is a plan, and
:mod:`ddd.lsp.units` already shows what those look like.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.editing import Operation
from ddd.identity import new_id, unstamped
from ddd.lsp.edits import WITHIN_DEFINITION
from ddd.lsp.ranges import Document, read

MISSING_ID: Final = "missing-id"
"""The one check whose fix the page has nowhere else to offer."""


@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries."""

    title: str
    """What the button says, naming the thing it changes."""

    path: Path
    """The file it writes in."""

    operations: tuple[Operation, ...]
    """What it writes there, for the edit engine."""


def fixes_for(check: str, path: Path, pointer: str, cache: dict[Path, Document]) -> tuple[Fix, ...]:
    """The fixes the finding filed at ``pointer`` of ``path`` carries, in the order to offer
    them.

    Empty for every check but one, and empty for that one wherever the declaration it names has
    moved on since the analysis: a file is read here as it stands now, and a fix planned against
    something that is no longer there would be refused by the engine anyway - with a sentence
    about fingerprints rather than about the declaration.
    """
    if check != MISSING_ID:
        return ()
    document = read(path, cache)
    within = WITHIN_DEFINITION.match(pointer)
    if within is None:
        return ()
    definition = within.group()
    if definition not in {found for found, _ in unstamped(document)}:
        return ()
    name = document.value_at(f"{definition}.name")
    if not isinstance(name, str):
        return ()
    # A fresh id per call: the page applies the preview it was given, never one asked for twice.
    return (
        Fix(
            title=f"Give '{name}' an id",
            path=path,
            operations=(Operation("set", f"{definition}.id", json.dumps(new_id())),),
        ),
    )
