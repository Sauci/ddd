"""Applying one declaration's value to the others that describe the same object.

Two components sharing a variable have to agree about it, and until now the editor could only
say so. This is the other half: ask for a fix anywhere in a declaration and the editor offers
to make every other declaration of that object say the same thing.

The protocol has no notion of an edit that propagates - nothing says "when this changes, change
that too" - so this is a code action, offered where the cursor is rather than applied behind
one. That is the better shape anyway: a client shows a multi-file code action in a preview
first, so nobody's files change without being seen.

Three rules keep the writing safe:

* **The value is copied as source text, never re-serialised.** ``{ "kind": "linear", "factor":
  0.5 }`` arrives in the other file looking the way its author wrote it. Round-tripping it
  through a json library would arrive as four differently indented lines and turn a one line
  change into a reformatting of the file.
* **A key the target lacks is inserted next to its neighbours**, taking the indentation of the
  member above it, on its own line or beside it depending on how that object is written.
* **Silence is a value too, and travels both ways.** Two declarations disagree just as much
  when one of them says nothing, so a key can be removed from here to match the others, or
  removed from the others to match here. Removing takes exactly one comma with it - the one
  after the member, or the one before it when the member is last - which is the fiddly part
  and the reason this came last.

Every key is offered at most two ways: somebody else's answer brought here, and this one's
answer sent out. Either may be a value or its absence. They are ordered by which component owns
the variable - a consumer is shown the producer's answer first, the producer its own - and
nothing here decides which is right, because nothing here can.

One action per key rather than one that settles the whole declaration, because two keys the
other declaration lacks would be two insertions anchored at the same position - which is not a
pair of edits any client can apply. Applying one and asking again is the way round it, and the
editor re-asks after every fix anyway.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.models import definition_keys

PROPAGATED_KEYS: Final = frozenset(
    {
        "datatype",
        "typename",
        "unit",
        "conversion",
        "limits",
        "dimensions",
        "size",
        "volatile",
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

``kind`` is left out although the declarations do have to agree on it, and it is the one key
here whose value decides which *other* keys the definition may carry: a value block has
``dimensions``, a curve has ``axis``, an axis has ``size``. Writing one declaration's ``kind``
into another therefore leaves keys behind that the new kind does not allow and keys missing
that it requires, and the file stops loading at all - a schema error, which is the one class of
finding no severity setting can turn down. A disagreement about ``kind`` is two components
describing different objects under one name, and the edit that settles it is not a key at a
time.
"""

QUICK_FIX: Final = "quickfix"

RECONCILED: Final = frozenset({"definition-mismatch", "storage-mismatch"})
"""The findings this action settles, so an editor can show it as their fix.

An action carrying the diagnostic it resolves is the one a client puts a lightbulb on, right
at the squiggle. Left unattached it is still offered, but only to somebody who already thought
to ask - which is the wrong way round for a fix.
"""


_WITHIN_DEFINITION: Final = re.compile(r"^component\.interface\[\d+\]\.definition")
"""Anywhere inside one definition, however deep - the prefix names the definition."""


def _keys_of(document: Document, definition: str) -> tuple[frozenset[str], frozenset[str]]:
    """What the definition at that pointer accepts and must state, by its own ``kind``.

    Read from the file rather than from the object being reconciled, because the two
    declarations need not agree - a disagreement about ``kind`` is precisely one of the things
    being reported. Each side is measured against its own kind.
    """
    kind = document.value_at(f"{definition}.kind")
    return definition_keys(kind) if isinstance(kind, str) else (frozenset(), frozenset())


def actions(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """What an editor may offer at this position.

    On a key that can be propagated, that key. Anywhere else inside the declaration - on the
    ``"definition"`` line, on a nested ``limits.min``, on a selection covering the lot - every
    key that differs from the other declarations, one action each.

    The wide answer is the one that matters in practice. The finding is drawn over the whole
    declaration, so that is where the pointer lands when somebody asks for a fix; requiring
    them to have first found the offending key is asking them to do the diagnosis the fix is
    for.

    Nothing at all when there is nothing to change: a fix that does nothing teaches a reader
    to stop reading the lightbulb.
    """
    within = _WITHIN_DEFINITION.match(pointer)
    if within is None:
        return []
    definition = within.group()
    name = document.value_at(f"{definition}.name")
    if not isinstance(name, str):
        return []

    key = pointer.rsplit(".", 1)[-1]
    if pointer == f"{definition}.{key}" and key in PROPAGATED_KEYS:
        wanted = [key]
    else:
        wanted = interface_keys(document.value_at(definition)) + _missing(
            built, path, document, name, definition, cache
        )
    here = Site(path, definition)
    produces = here in built.producers.get(name, ())
    offered: list[dict[str, Any]] = []
    for candidate in wanted:
        # Two ways to settle a key, and at most one of each. Taking is somebody else's answer
        # brought here - the producer's for preference, the one the rest agree on otherwise,
        # or their silence. Giving is this declaration's answer sent out, value or silence.
        taken = (
            _from_producer(built, here, document, name, candidate, cache)
            or _remove_here(built, here, document, name, candidate, cache)
            or _adopt(built, here, document, name, candidate, cache)
        )
        given = _propagate(built, here, document, name, candidate, cache) or _remove_elsewhere(
            built, here, document, name, candidate, cache
        )
        # A consumer is offered the producer's value first; the producer is offered its own,
        # outward. Which side owns the variable is not a matter of taste here - it is the rule
        # the whole tool is built on, and the fix that reads naturally is the one that follows
        # it rather than the one that quietly redefines somebody else's data.
        ordered = [given, taken] if produces else [taken, given]
        offered.extend(action for action in ordered if action is not None)
    settles = [entry for entry in reported if entry.get("code") in RECONCILED]
    if settles and offered:
        for action in offered:
            action["diagnostics"] = settles
        offered[0]["isPreferred"] = True
    return offered


def interface_keys(members: Any) -> list[str]:
    """The propagatable keys an object states, in the order they are written.

    Tolerant of being handed something that is not an object at all: a definition is one in
    every file that loaded, but these are read from disk a moment after the loader saw them,
    and a file rewritten in between should not take the server down.
    """
    if not isinstance(members, dict):
        return []
    return [key for key in members if key in PROPAGATED_KEYS]


def _missing(
    built: Index,
    path: Path,
    document: Document,
    name: str,
    definition: str,
    cache: dict[Path, Document],
) -> list[str]:
    """Keys the other declarations state and this one does not.

    The other direction, and the one the first version could not do anything about: a
    declaration missing a ``unit`` the rest agree on cannot *give* one, so without this the
    only file offering a fix was one of the files that was already right.

    Keys this declaration already has are left out, or every shared key would be considered
    twice and offered twice.
    """
    mine = set(interface_keys(document.value_at(definition)))
    absent: set[str] = set()
    for site in built.declarations.get(name, ()):
        if site.path == path and site.pointer == definition:
            continue
        absent.update(interface_keys(read(site.path, cache).value_at(site.pointer)))
    return sorted(absent - mine)


def _adopt(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> dict[str, Any] | None:
    """Take a value the others state and this declaration does not.

    Only when they agree with each other about it. Two different answers is a question about
    which one is right, and picking one silently is exactly the kind of help nobody asked for.

    Written through :func:`_assign` rather than straight into the text, so that this direction
    is refused for a key the target's own kind does not have on the same terms as every other.
    """
    if document.raw_at(f"{here.pointer}.{key}") is not None:
        return None
    stated = {
        raw
        for site in built.declarations.get(name, ())
        if site != here
        and (raw := read(site.path, cache).raw_at(f"{site.pointer}.{key}")) is not None
    }
    if len(stated) != 1:
        return None
    edit = _assign(document, here.pointer, key, next(iter(stated)))
    if edit is None:
        return None
    return {
        "title": f"Take the {key} the other declarations of '{name}' state",
        "kind": QUICK_FIX,
        "edit": {"changes": {here.path.as_uri(): [edit]}},
    }


def _from_producer(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> dict[str, Any] | None:
    """Take the value the producing component states, into the declaration asked at.

    The direction that reads naturally from a consumer. A component that reads a variable is
    describing what it expects to find, and the component that writes it is the one that
    decides - so "use what the producer says" is a fix, where "make the producer say what I
    say" is a consumer redefining data it does not own.
    """
    producers = [site for site in built.producers.get(name, ()) if site != here]
    if len(producers) != 1:
        # No producer, or several - which is its own finding, and not one to guess through.
        return None
    producer = producers[0]
    raw = read(producer.path, cache).raw_at(f"{producer.pointer}.{key}")
    if raw is None or raw == document.raw_at(f"{here.pointer}.{key}"):
        return None
    edit = _assign(document, here.pointer, key, raw)
    if edit is None:
        return None
    owner = producer.path.stem.removesuffix(".ddd")
    return {
        "title": f"Use the {key} declared in {owner}",
        "kind": QUICK_FIX,
        "edit": {"changes": {here.path.as_uri(): [edit]}},
    }


def _remove_here(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> dict[str, Any] | None:
    """Take a key out, when this declaration is the only one that states it.

    The other half of adopting somebody else's answer: a key nobody else mentions is
    reconciled by removing it just as much as by spreading it, and which of the two an author
    wants is not something to decide for them. Only offered when no other declaration has one,
    because otherwise removing it settles nothing.
    """
    if document.raw_at(f"{here.pointer}.{key}") is None:
        return None
    if key in _keys_of(document, here.pointer)[1]:
        # Offering to remove a key the kind requires is offering to break the file: it would
        # not load at all afterwards, which is a worse state than the disagreement it settles.
        return None
    others = [site for site in built.declarations.get(name, ()) if site != here]
    # Nobody to disagree with is not the same as everybody agreeing: a variable one component
    # declares on its own has nothing to reconcile, and offering to strip its unit would be a
    # suggestion to lose information for no reason at all.
    if not others:
        return None
    if any(read(site.path, cache).raw_at(f"{site.pointer}.{key}") is not None for site in others):
        return None
    edit = _erase(document, here.pointer, key)
    if edit is None:
        return None
    producers = [site for site in built.producers.get(name, ()) if site != here]
    where = (
        f"which {producers[0].path.stem.removesuffix('.ddd')} does not declare"
        if len(producers) == 1
        else f"which no other declaration of '{name}' has"
    )
    return {
        "title": f"Remove this {key}, {where}",
        "kind": QUICK_FIX,
        "edit": {"changes": {here.path.as_uri(): [edit]}},
    }


def _remove_elsewhere(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> dict[str, Any] | None:
    """Take the key out of the other declarations, when this one does not state it.

    The mirror of spreading a value, and the direction that was missing: a declaration with no
    ``unit`` could take one from the others but never say "none of you should have one
    either". Both are ways of agreeing, and which one is meant is the author's to choose.
    """
    if document.raw_at(f"{here.pointer}.{key}") is not None:
        return None
    changes: dict[str, list[dict[str, Any]]] = {}
    for site in built.declarations.get(name, ()):
        if site == here:
            continue
        target = read(site.path, cache)
        edit = (
            None
            if target.raw_at(f"{site.pointer}.{key}") is None
            or key in _keys_of(target, site.pointer)[1]
            else _erase(target, site.pointer, key)
        )
        if edit is not None:
            changes.setdefault(site.path.as_uri(), []).append(edit)
    if not changes:
        return None
    elsewhere = sum(len(edits) for edits in changes.values())
    return {
        "title": f"Remove the {key} from {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        "kind": QUICK_FIX,
        "edit": {"changes": changes},
    }


def _erase(document: Document, definition: str, key: str) -> dict[str, Any] | None:
    """Cut a member out of an object, taking exactly one comma with it.

    Which comma is the whole difficulty, and it depends on where the member sits. A member
    with one after it is removed up to the start of that one, which takes its own comma and
    leaves the next where this began. The last member is removed from the *end of the one
    before it*, which takes the comma that used to join them and leaves no trailing one.

    An only child is refused: what to leave between the braces is a judgement about the file's
    style rather than about the data. It cannot arise for these keys anyway - every definition
    has a ``name`` beside them.
    """
    members = document.value_at(definition)
    if not isinstance(members, dict) or key not in members or len(members) == 1:
        return None
    keys = list(members)
    position = keys.index(key)
    mine = document.range_of(f"{definition}.{key}")
    if position < len(keys) - 1:
        following = document.range_of(f"{definition}.{keys[position + 1]}")
        cut = {"start": mine["start"], "end": following["start"]}
    else:
        previous = document.range_of(f"{definition}.{keys[position - 1]}")
        cut = {"start": previous["end"], "end": mine["end"]}
    return {"range": cut, "newText": ""}


def _propagate(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> dict[str, Any] | None:
    """One action, or nothing when every other declaration already says the same."""
    raw = document.raw_at(f"{here.pointer}.{key}")
    if raw is None:
        return None
    changes: dict[str, list[dict[str, Any]]] = {}
    for site in built.declarations.get(name, ()):
        if site == here:
            continue
        edit = _assign(read(site.path, cache), site.pointer, key, raw)
        if edit is not None:
            changes.setdefault(site.path.as_uri(), []).append(edit)
    if not changes:
        return None
    elsewhere = sum(len(edits) for edits in changes.values())
    return {
        "title": f"Apply this {key} to {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        "kind": QUICK_FIX,
        "edit": {"changes": changes},
    }


def _assign(document: Document, definition: str, key: str, raw: str) -> dict[str, Any] | None:
    """The edit that makes one declaration say ``key: raw``, or nothing if it already does.

    Refused for a key the target's own kind does not have. Two declarations of one object
    disagreeing about ``kind`` is a finding of its own, and while it stands, writing a curve's
    ``axis`` into the measurement somebody else declared would only add a file that no longer
    loads to a project that already has something to fix.
    """
    if key not in _keys_of(document, definition)[0]:
        return None
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
