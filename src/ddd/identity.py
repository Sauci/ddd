"""Making an identity, and writing one into a description file without reformatting it.

The insertion is textual rather than a json round trip on purpose. Rewriting the whole
document to add one key would produce a diff in which every line moved, and a diff nobody can
read is exactly what makes a tool that edits hand-authored sources dangerous. What justifies
this command is that the project is in git - the tool proposes, the diff is reviewed, a
checkout undoes it - and that justification only holds while the diff is one line per object.

The writing is the edit engine's (:mod:`ddd.editing`), the one every description ``ddd gui``
changes is written by: :func:`assign` hands it one operation for each declaration that wants an
id (:func:`stamp`), and gets a file that keeps its mode, written through a link to the file the
link names, staged under a name of its own and looked at once more right before it is renamed
into place - and one the loader refuses, a key spelled twice or ``NaN``, left as it is. The
engine writes the key right after the declaration's ``name``.

The text positions come from :mod:`ddd.lsp.ranges`, which is a json-pointer-to-text utility
that happens to live under the language server; the command reuses it rather than growing a
second scanner that would drift from it.

That import is deferred into :func:`assign` rather than made at the top, for two reasons that
point the same way. Importing ``ddd.lsp.ranges`` runs the package's ``__init__``, which brings
up the whole language server - a cost ``ddd id`` has no use for and a dependency a command
line tool should not have on an editor service. And the server's own quick fix reads
:func:`insertions` from here, so a module level import would close a cycle. Only :func:`assign`
touches the filesystem; everything above it works on a document it is handed.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ddd.editing import (
    EditError,
    FileChange,
    Operation,
    apply_changes,
    indent_of_line_at,
    newline_at,
)
from ddd.loading import fingerprint, parse_json_text, resolve_path
from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH
from ddd.models.component import Scope

if TYPE_CHECKING:
    from ddd.lsp.ranges import Document

_PRODUCING = (Scope.OUTPUT.value, Scope.LOCAL.value)
"""Spelled as the raw strings a description carries, not as ``Scope`` itself.

This module reads a file's json directly, before the loader has had a chance to say
whether it is well formed - so a declaration's ``scope`` is whatever the author typed, not
yet a validated :class:`Scope`. Comparing against the enum's own values keeps this from
drifting from what ``Scope`` calls a producer, without asking pydantic to construct one
from a string that has not been checked, which would turn an unrelated malformed value into
an exception this module has no business raising.
"""

UNREADABLE = -1
"""What :func:`assign` returns for a file DDD does not read as json, which is not zero.

That is a file that is not json at all, and one the loader refuses although python's parser
reads it - a key spelled twice in one object, ``NaN`` - which ``ddd check`` reports as
``json-syntax``. ``ranges.read`` answers an unreadable or half-written file with an empty
document rather than an exception, so "nothing to do" and "could not read it" arrive here
looking identical. The command exits non-zero on the second and says nothing about the first.
"""

UNWRITABLE = -2
"""What :func:`assign` returns for a file it read, had ids for, and the edit engine would not
write back, or could not.

A read-only file in a checkout, or one an editor is holding; one saved while the command was at
it, which the engine refuses rather than write over; a full disk. The command is given a list of
files and stamps what it can, so a write that fails is reported like a read that failed and the
files after it are still stamped. Collapsed into one answer the way :data:`UNREADABLE` collapses
the several reasons a file cannot be read: what the caller does about either is to look at that
one file.
"""


def new_id() -> str:
    """A fresh identity: twelve characters of the unambiguous lowercase base32 alphabet."""
    return "".join(secrets.choice(OBJECT_ID_ALPHABET) for _ in range(OBJECT_ID_LENGTH))


def unstamped(document: Document) -> list[tuple[str, bool]]:
    """Every producing declaration without an id: its ``...definition`` pointer, and whether
    it states the key as ``null`` - which the dump writes for an unstamped object, and which
    ``missing-id`` reports exactly as it reports the key's absence.

    A component file is the only kind that declares data objects, so a file of any other kind
    yields nothing and is left untouched rather than reported: ``ddd id`` is pointed at a
    directory of description files as readily as at one component.
    """
    parsed = document.data
    if not isinstance(parsed, dict):
        return []
    component = parsed.get("component")
    if not isinstance(component, dict):
        return []
    interface = component.get("interface")
    if not isinstance(interface, list):
        return []
    wanted = []
    for index, entry in enumerate(interface):
        if not isinstance(entry, dict) or entry.get("scope") not in _PRODUCING:
            continue
        definition = entry.get("definition")
        if not isinstance(definition, dict) or "name" not in definition:
            continue
        if "id" in definition and definition["id"] is not None:
            continue
        wanted.append((f"component.interface[{index}].definition", "id" in definition))
    return wanted


@dataclass(frozen=True, slots=True)
class Insertion:
    """Where an id belongs in a description's text, and what to write there: the language
    server's quick fix, which offers the edit on one declaration as a text edit with a range.

    The command and the page's fix state the same edit as an operation for the edit engine
    (:func:`stamp`), which writes the key in the same place, right after the name, and in the
    same layout where the object is written one member to a line; a test holds the two to one
    text.
    """

    pointer: str
    """The ``...definition.name`` pointer the new key follows, or the ``...definition.id``
    pointer of the ``null`` the new value replaces."""

    offset: int
    """Where it goes in the document's text, for a caller rewriting the whole file."""

    text: str
    """The key itself, with the comma and the indent of the line it joins - or, replacing a
    ``null``, the quoted id alone."""

    length: int = 0
    """How many characters at ``offset`` the text replaces: the ``null``, or nothing."""


def insertions(document: Document) -> list[Insertion]:
    """Every identity this document is missing, in the order its declarations are written.

    Each carries a freshly generated id, so asking twice proposes two different sets - which
    is why a caller applies the answer it was given rather than asking again.
    """
    found = []
    for definition, stated_null in unstamped(document):
        target = f"{definition}.id" if stated_null else f"{definition}.name"
        # The walk above reads the parsed document and the spans come from a scan of the same
        # text, under pointers built from the same decoded keys - and every segment of this
        # one is a fixed identifier, so no spelling can split differently. A document that
        # parsed therefore has a span here. Asserted rather than guarded, the way the quick
        # fix that reads this list asserts the same span: a declaration skipped in silence is
        # what this used to do, and it did it whenever a key carried a json escape.
        span = document.value_span_of(target)
        assert span is not None
        if stated_null:
            found.append(Insertion(target, span[0], f'"{new_id()}"', span[1] - span[0]))
        else:
            indent = indent_of_line_at(document.text, span[1])
            newline = newline_at(document.text, span[1])
            found.append(Insertion(target, span[1], f',{newline}{indent}"id": "{new_id()}"'))
    return found


def stamp(definition: str) -> Operation:
    """The operation giving the declaration at the pointer ``definition`` a fresh identity.

    What the command and the page's fix for ``missing-id`` each hand the edit engine, which
    writes the ``id`` right after the declaration's ``name`` - or, where the declaration states
    one as ``null``, in place of that ``null`` - in the layout of the file around it
    (:func:`ddd.editing.member_addition`). Spelled once, here, so that the two cannot ask for
    one edit in two ways; a fresh id per call, so a caller applies the answer it was given
    rather than asking again.
    """
    return Operation("set", f"{definition}.id", json.dumps(new_id()))


def assign(path: Path) -> int:
    """Write an id into every producing declaration of ``path`` that lacks one.

    Returns how many were written, :data:`UNREADABLE` for a file DDD does not read as json, or
    :data:`UNWRITABLE` for one the edit engine refused or could not write back. A file that
    reads but declares no data objects is left exactly as it was and reports zero: the loader is
    what has something to say about a description, and this command must not rewrite one it
    could not read.

    The file is the one ``path`` names, followed through a symbolic link: the engine stages the
    new bytes beside the file it writes and renames them onto it, which on the link's own name
    replaces the link with a copy and leaves the file the link names as it was - a description
    shared between projects, forked in silence. Resolved as the loader and ``ddd gui`` resolve
    a path (:func:`ddd.loading.resolve_path`).
    """
    from ddd.lsp.ranges import Document

    path = resolve_path(path)
    # The bytes as they are: their fingerprint is what the engine checks the edit against, and
    # a byte order mark is the engine's to keep. Read as the loader reads a description, not as
    # python's parser does - which takes a key spelled twice and ``NaN`` - because what the
    # loader refuses this command must not rewrite, and the engine would refuse to edit it.
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        parse_json_text(text)
    except (OSError, ValueError):  # a decoding error is one
        return UNREADABLE
    document = Document(text)
    if document.data is None:
        return UNREADABLE
    wanted = unstamped(document)
    if not wanted:
        return 0
    try:
        apply_changes(
            [FileChange(path, fingerprint(raw), tuple(stamp(found) for found, _ in wanted))]
        )
    except EditError:
        # The command is handed a list of files and stamps what it can: a file it may not
        # write - read-only in the checkout, held open by an editor, saved while it worked - is
        # one file to report, not a reason to leave the rest of the list untouched and print
        # no total.
        return UNWRITABLE
    return len(wanted)
