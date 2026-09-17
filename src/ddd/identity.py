"""Making an identity, and writing one into a description file without reformatting it.

The insertion is textual rather than a json round trip on purpose. Rewriting the whole
document to add one key would produce a diff in which every line moved, and a diff nobody can
read is exactly what makes a tool that edits hand-authored sources dangerous. What justifies
this command is that the project is in git - the tool proposes, the diff is reviewed, a
checkout undoes it - and that justification only holds while the diff is one line per object.

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

import codecs
import contextlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ddd.editing import indent_of_line_at, newline_at
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
"""What :func:`assign` returns for a file it could not read as json, which is not zero.

``ranges.read`` answers an unreadable or half-written file with an empty document rather than
an exception, so "nothing to do" and "could not read it" arrive here looking identical. The
command exits non-zero on the second and says nothing about the first.
"""

UNWRITABLE = -2
"""What :func:`assign` returns for a file it read, had ids for, and could not write back.

A read-only file in a checkout, or one an editor is holding: the command is given a list of
files and stamps what it can, so a write that fails is reported like a read that failed and
the files after it are still stamped. Collapsed into one answer the way :data:`UNREADABLE`
collapses the several reasons a file cannot be read: what the caller does about either is to
look at that one file.
"""

STAGING_SUFFIX = ".ddd-staging"
"""What :func:`assign` appends to a description's name to stage its new bytes beside it.

The same spelling the artefact writer stages under, and for the same reason it gives: a name
no project gives a file of its own, so a leftover of a run that died is ours by construction
and overwriting it is right. Spelled here rather than imported from
:mod:`ddd.backends.base`, which would put jinja2 and every backend behind ``ddd id``; a test
pins the two together.
"""


def new_id() -> str:
    """A fresh identity: twelve characters of the unambiguous lowercase base32 alphabet."""
    return "".join(secrets.choice(OBJECT_ID_ALPHABET) for _ in range(OBJECT_ID_LENGTH))


def _unstamped(document: Document) -> list[tuple[str, bool]]:
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
    """Where an id belongs in a description's text, and what to write there.

    Two callers need this answer and must not disagree about it: :func:`assign` rewrites the
    file, and the language server offers the same edit on one declaration. Both read it from
    here rather than each working out where the key goes - the reasoning this module already
    applies to reusing one scanner rather than growing a second of its own.
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
    for definition, stated_null in _unstamped(document):
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


def assign(path: Path) -> int:
    """Write an id into every producing declaration of ``path`` that lacks one.

    Returns how many were written, :data:`UNREADABLE` for a file that is not json, or
    :data:`UNWRITABLE` for one that could not be written back. A file that reads but declares
    no data objects is left exactly as it was and reports zero: the loader is what has
    something to say about a description, and this command must not rewrite one it could not
    read.
    """
    from ddd.lsp.ranges import Document

    # The bytes as they are, not the text ``read`` would normalise them into: the document is
    # scanned with every line ending as written, so an edit lands between the same bytes it
    # was computed against, and writing the rest back unchanged is what turns a command that
    # edits hand-authored sources into a one line diff per object.
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return UNREADABLE
    document = Document(text)
    if document.data is None:
        return UNREADABLE
    wanted = insertions(document)
    if not wanted:
        return 0
    # Back to front, so an insertion never moves the offset of the one before it.
    for entry in reversed(wanted):
        text = f"{text[: entry.offset]}{entry.text}{text[entry.offset + entry.length :]}"
    mark = codecs.BOM_UTF8 if raw.startswith(codecs.BOM_UTF8) else b""
    # Staged beside the file and renamed onto it, the way every artefact DDD writes is. What
    # this command edits is hand-authored and under review rather than regenerated, so a
    # write that dies partway through - a full disk, a kill between the truncation and the
    # write - has nothing to put back: the one copy of those bytes was the file itself.
    staging = path.with_name(path.name + STAGING_SUFFIX)
    try:
        staging.write_bytes(mark + text.encode("utf-8"))
        staging.replace(path)
    except OSError:
        # The command is handed a list of files and stamps what it can: a file it may not
        # write - read-only in the checkout, held open by an editor - is one file to report,
        # not a reason to leave the rest of the list untouched and print no total.
        with contextlib.suppress(OSError):
            staging.unlink()
        return UNWRITABLE
    return len(wanted)
