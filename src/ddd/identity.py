"""Making an identity, and writing one into a description file without reformatting it.

The insertion is textual rather than a json round trip on purpose. Rewriting the whole
document to add one key would produce a diff in which every line moved, and a diff nobody can
read is exactly what makes a tool that edits hand-authored sources dangerous. What justifies
this command is that the project is in git - the tool proposes, the diff is reviewed, a
checkout undoes it - and that justification only holds while the diff is one line per object.

The text positions come from :mod:`ddd.lsp.ranges`, which is a json-pointer-to-text utility
that happens to live under the language server; the command reuses it rather than growing a
second scanner that would drift from it.
"""

from __future__ import annotations

import codecs
import secrets
from pathlib import Path

from ddd.lsp.ranges import Document, read
from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH
from ddd.models.component import Scope

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


def new_id() -> str:
    """A fresh identity: twelve characters of the unambiguous lowercase base32 alphabet."""
    return "".join(secrets.choice(OBJECT_ID_ALPHABET) for _ in range(OBJECT_ID_LENGTH))


def _pointers_needing_an_id(document: Document) -> list[str]:
    """The ``...definition.name`` pointer of every producing declaration that has no id.

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
        if not isinstance(definition, dict) or "id" in definition or "name" not in definition:
            continue
        wanted.append(f"component.interface[{index}].definition.name")
    return wanted


def _indent_of_line_at(text: str, offset: int) -> str:
    """The leading whitespace of the line ``offset`` sits on, so the new key lines up.

    Whatever the file is indented with: a project writing tabs gets a tab, and one writing
    four spaces gets four. The command has no opinion about how a description is formatted.
    """
    start = text.rfind("\n", 0, offset) + 1
    return text[start : len(text) - len(text[start:].lstrip())]


def assign(path: Path) -> int:
    """Write an id into every producing declaration of ``path`` that lacks one.

    Returns how many were written, or :data:`UNREADABLE` for a file that is not json. A file
    that reads but declares no data objects is left exactly as it was and reports zero: the
    loader is what has something to say about a description, and this command must not
    rewrite one it could not read.
    """
    document = read(path, {})
    if document.data is None:
        return UNREADABLE
    pointers = _pointers_needing_an_id(document)
    if not pointers:
        return 0
    text = document.text
    written = 0
    # Back to front, so an insertion never moves the offset of the one before it.
    for pointer in reversed(pointers):
        span = document.value_span_of(pointer)
        if span is None:
            continue
        at = span[1]
        indent = _indent_of_line_at(text, at)
        text = f'{text[:at]},\n{indent}"id": "{new_id()}"{text[at:]}'
        written += 1
    # What the file was encoded and ended with, which ``read`` has already normalised away:
    # it decodes with utf-8-sig and with universal newlines, so by the time the text is here
    # a byte order mark is gone and every line ends in "\n". Writing the defaults back would
    # drop the mark and rewrite every line ending - turning a one line diff into a whole file
    # one, which is the only thing making a command that edits hand-authored sources safe.
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(codecs.BOM_UTF8) else "utf-8"
    path.write_text(text, encoding=encoding, newline="\r\n" if b"\r\n" in raw else "\n")
    return written
