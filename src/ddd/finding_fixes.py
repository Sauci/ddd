"""The fixes a finding of ``ddd gui`` carries.

Most checks have none: they name what is wrong, and the panel that owns the key is where a
reader settles it. One has a fix with nowhere else to go - ``missing-id``, an identity for a
producing declaration that states none - and this plans it as operations on json pointers, the
form ``POST /api/edit`` applies.

The language server offers the same fix as a text edit with a range, computed by
:mod:`ddd.identity` from the same walk this reads: which declarations want an id is decided in
one place, and only how the edit is spelled differs between the two clients.

A list of fixes rather than one, so that the second check to grow a fix needs no new shape. A
fix carries whatever files its decision names, and the page previews each before anything is
written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.editing import Operation
from ddd.identity import new_id, unstamped
from ddd.lsp.edits import WITHIN_DEFINITION, reconciliations
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.variables import operations_for

MISSING_ID: Final = "missing-id"
"""The one check whose fix the page has nowhere else to offer."""

MISMATCH: Final = "definition-mismatch"
"""Two components describing one variable differently - the finding this tool exists to file,
and until now the one it could only describe."""


@dataclass(frozen=True, slots=True)
class FileEdit:
    """What one fix writes in one file."""

    path: Path
    operations: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries."""

    title: str
    """What the button says, naming the thing it changes."""

    changes: tuple[FileEdit, ...]
    """One per file, in the order the settlement names them. An identity has exactly one; a
    reconciliation has as many as the variable has declarations that must move."""


def fixes_for(
    check: str, path: Path, pointer: str, cache: dict[Path, Document], built: Index
) -> tuple[Fix, ...]:
    """The fixes the finding filed at ``pointer`` of ``path`` carries, in the order to offer
    them.

    Empty for every check but two, and empty for those wherever the declaration they name has
    moved on since the analysis: a file is read here as it stands now, and a fix planned against
    something that is no longer there would be refused by the engine anyway - with a sentence
    about fingerprints rather than about the declaration.
    """
    if check == MISSING_ID:
        return _an_identity(path, pointer, cache)
    if check == MISMATCH:
        return _reconciled(built, path, pointer, cache)
    return ()


def _an_identity(path: Path, pointer: str, cache: dict[Path, Document]) -> tuple[Fix, ...]:
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
    operation = Operation("set", f"{definition}.id", json.dumps(new_id()))
    return (Fix(f"Give '{name}' an id", (FileEdit(path, (operation,)),)),)


def _reconciled(
    built: Index, path: Path, pointer: str, cache: dict[Path, Document]
) -> tuple[Fix, ...]:
    """One fix per key the declaration disagrees on: the direction the owning component decides.

    Asks ``reconciliations`` for ``owned=True``, which already keeps only the direction the
    ownership rule wants for this declaration - a consumer takes the producer's value, the
    producer sends its own out - or nothing when that direction does not exist, rather than
    falling through to the other one: a button whose direction the reader has to work out is not
    the one press this exists to be. The other way is a click away, in the variable's own panel,
    which settles any value the reader chooses.

    A settlement that cannot reach every declaration is dropped rather than offered. The page
    refuses a partial settlement, so the button would do nothing but explain itself, and a fix
    that does nothing teaches a reader to stop reading the fixes.
    """
    document = read(path, cache)
    fixes: list[Fix] = []
    for decision in reconciliations(built, path, document, pointer, cache, owned=True):
        if decision.settlement.unsettled:
            continue
        changes = tuple(
            FileEdit(edit_path, operations)
            for edit_path, operations in operations_for(decision.settlement, decision.key)
        )
        fixes.append(Fix(decision.title, changes))
    return tuple(fixes)
