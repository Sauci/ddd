"""Applying one declaration's value to the others that describe the same object.

Two components sharing a variable have to agree about it, and until now the editor could only
say so. This is the other half: put the cursor on a ``unit`` and the editor offers to make
every other declaration of that object say the same thing.

The protocol has no notion of an edit that propagates - nothing says "when this changes, change
that too" - so this is a code action, offered where the cursor is rather than applied behind
one. That is the better shape anyway: a client shows a multi-file code action in a preview
first, so nobody's files change without being seen.

Three rules keep the writing safe:

* **The value is copied as source text, never re-serialised.** ``{ "kind": "linear", "factor":
  0.5 }`` arrives in the other file looking the way its author wrote it. Round-tripping it
  through a json library would arrive as four differently indented lines and turn a one line
  change into a reformatting of the file.
* **A value is only ever written, never removed.** The action acts on the key under the
  cursor, so the source always has one; the awkward case - deleting a key from the others,
  with the comma juggling that needs - therefore cannot arise.
* **A key the target lacks is inserted next to its neighbours**, taking the indentation of the
  member above it, on its own line or beside it depending on how that object is written.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read

PROPAGATED_KEYS: Final = frozenset(
    {
        "datatype",
        "unit",
        "conversion",
        "limits",
        "dimensions",
        "size",
        "volatile",
        "kind",
        "axis",
        "x_axis",
        "y_axis",
        "input",
    }
)
"""Keys every declaration of one object has to agree on, and may therefore be given.

The interface, in other words - what ``definition-mismatch`` is about. ``name`` is not here
because changing it is a rename, ``description`` because two components may describe the same
variable in their own words, and ``init`` because only a producer may state one at all.
"""

QUICK_FIX: Final = "quickfix"

RECONCILED: Final = frozenset({"definition-mismatch", "storage-mismatch"})
"""The findings this action settles, so an editor can show it as their fix.

An action carrying the diagnostic it resolves is the one a client puts a lightbulb on, right
at the squiggle. Left unattached it is still offered, but only to somebody who already thought
to ask - which is the wrong way round for a fix.
"""


def actions(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """What an editor may offer at this position.

    One action, and only when there is something to change: a key whose value already matches
    everywhere would offer a fix that does nothing, which teaches a reader to stop reading the
    lightbulb.
    """
    key = pointer.rsplit(".", 1)[-1]
    definition, _, _ = pointer.rpartition(f".{key}")
    if key not in PROPAGATED_KEYS or not definition.endswith(".definition"):
        return []
    name = document.value_at(f"{definition}.name")
    raw = document.raw_at(pointer)
    if not isinstance(name, str) or raw is None:
        return []

    changes: dict[str, list[dict[str, Any]]] = {}
    for site in built.declarations.get(name, ()):
        if site.path == path and site.pointer == definition:
            continue
        edit = _assign(read(site.path, cache), site.pointer, key, raw)
        if edit is not None:
            changes.setdefault(site.path.as_uri(), []).append(edit)
    if not changes:
        return []

    elsewhere = sum(len(edits) for edits in changes.values())
    offered: dict[str, Any] = {
        "title": f"Apply this {key} to {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        "kind": QUICK_FIX,
        "edit": {"changes": changes},
    }
    settles = [entry for entry in reported if entry.get("code") in RECONCILED]
    if settles:
        offered["diagnostics"] = settles
    return [offered]


def _assign(document: Document, definition: str, key: str, raw: str) -> dict[str, Any] | None:
    """The edit that makes one declaration say ``key: raw``, or nothing if it already does."""
    existing = document.raw_at(f"{definition}.{key}")
    if existing is not None:
        if existing == raw:
            return None
        return {"range": document.value_range_of(f"{definition}.{key}"), "newText": raw}
    return _insert(document, definition, key, raw)


def _insert(document: Document, definition: str, key: str, raw: str) -> dict[str, Any] | None:
    """Add a key an object does not have, next to the one written last.

    After the last member rather than at the front, because that is where a person adding a key
    by hand puts it, and because the first member of a definition is its ``name`` - which is
    what somebody reading the file scans for.
    """
    members = document.value_at(definition)
    if not isinstance(members, dict) or not members:
        return None
    end = document.range_of(f"{definition}.{next(reversed(members))}")["end"]
    if end["line"] == document.range_of(definition)["start"]["line"]:
        # Written on one line, and a fix is no reason for it to stop being.
        separator = ", "
    else:
        line = document.text.splitlines()[end["line"]]
        separator = ",\n" + line[: len(line) - len(line.lstrip())]
    return {"range": {"start": end, "end": end}, "newText": f'{separator}"{key}": {raw}'}
