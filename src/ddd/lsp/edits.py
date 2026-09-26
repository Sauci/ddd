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

import contextlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal

from ddd.analysis import close_units
from ddd.editing import EditError, TextEdit, member_addition, removal
from ddd.identity import insertions
from ddd.lsp.navigation import Index, Site, renameable_at
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import (
    UnitProject,
    UnitRefusalError,
    add_unit,
    rename_unit,
    text_edits,
    unit_drift,
)
from ddd.models import definition_keys
from ddd.models.objects import FIXED_BY_A_TYPE, STORAGE_NAMES, storage_keys
from ddd.value_identity import same_value

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

DEFERRED_KEYS: Final = frozenset({"limits"})
"""Keys a declaration may leave to whoever states them, which the checker counts as agreement.

The one exception to silence being a value: ``definition-mismatch`` compares limits only where
both sides state them, and a consumer that leaves them out defers to the producer. Offering to
spread a range into a declaration that deferred, or to strip the one range anybody stated,
would be a fix on a declaration the checker calls clean - and taking it would change the range
the a2l publishes without a finding before or after. Two stated ranges that differ are still
reconciled both ways.
"""

QUICK_FIX: Final = "quickfix"

RECONCILED: Final = frozenset({"definition-mismatch"})
"""The finding these actions settle, so an editor can show them as its fix.

An action carrying the diagnostic it resolves is the one a client puts a lightbulb on, right
at the squiggle. Left unattached it is still offered, but only to somebody who already thought
to ask - which is the wrong way round for a fix. ``storage-mismatch`` is not here: it is about
the a2l presentation keys, which none of these actions carries, and an action claiming to
settle a finding it leaves in place is worse than one that stays quiet about it.
"""


UNIDENTIFIED: Final = frozenset({"missing-id"})
"""The finding the identity action settles, so a client can put its lightbulb on the squiggle.

Its own set rather than a member of :data:`RECONCILED`, because it settles a different kind of
thing: those actions carry one declaration's answer to another, while this one invents a value
no declaration has. Sharing the set would offer every reconcile action as a fix for a missing
id, and this one as a fix for a disagreement it does nothing about.
"""


UNKNOWN_UNIT: Final = frozenset({"unknown-unit"})
"""The finding the vocabulary actions settle, so a client can put its lightbulb on the squiggle.

Its own set for the reason :data:`UNIDENTIFIED` has one: these actions change the vocabulary, or
every place a unit is stated, rather than one declaration to agree with another.
"""


WITHIN_DEFINITION: Final = re.compile(r"^component\.interface\[\d+\]\.definition")
"""Anywhere inside one definition, however deep - the prefix names the definition."""


WITHIN_DECLARATION: Final = re.compile(r"^component\.interface\[\d+\]")
"""Anywhere inside one declaration, definition or not - the prefix names the declaration.

:data:`WITHIN_DEFINITION` names the definition a key belongs to; this names the declaration a
finding is about, which is broader by exactly the keys a declaration carries beside its
definition - ``scope`` and ``condition``. ``missing-producer`` and ``local-conflict`` are filed
on the declaration itself, and a ``condition-mismatch`` on the condition or, stating none, on
the declaration too - none of them under ``definition``, so :data:`WITHIN_DEFINITION` would miss
every one.
"""


def _keys_of(document: Document, definition: str) -> tuple[frozenset[str], frozenset[str]]:
    """What the definition at that pointer accepts and must state, by its own ``kind``.

    Read from the file rather than from the object being reconciled, because the two
    declarations need not agree - a disagreement about ``kind`` is precisely one of the things
    being reported. Each side is measured against its own kind.
    """
    kind = document.value_at(f"{definition}.kind")
    return definition_keys(kind) if isinstance(kind, str) else (frozenset(), frozenset())


def _give_an_identity(
    path: Path, document: Document, definition: str, name: str
) -> dict[str, Any] | None:
    """Offer this declaration an identity, when it produces the object and states none.

    The same answer ``ddd id --assign`` would give, decided in the same place: which
    declarations want one, and where the key goes, are :mod:`ddd.identity`'s to say, so the
    editor and the command cannot drift about it. Only the applying differs - the command
    rewrites the file, this returns an edit and lets the client do it.
    """
    wanted = next(
        (
            entry
            for entry in insertions(document)
            if entry.pointer in (f"{definition}.name", f"{definition}.id")
        ),
        None,
    )
    if wanted is None:
        return None
    # Both readings come from the same recorded spans, and `insertions` only yields a pointer
    # whose span it already found - so this one is there. Asserted rather than guarded, the way
    # `DataObject.storage` narrows a union it knows: a branch that cannot be taken is a branch
    # no test can cover and no reader can trust.
    span = document.value_range_of(wanted.pointer)
    assert span is not None
    # A zero width range at the end of the name's value, so that the key is inserted after
    # it and nothing already written is replaced - or the value of a stated ``null``, which is.
    at = span["end"]
    replaced = {"start": span["start"] if wanted.length else at, "end": at}
    return {
        "title": f"Give '{name}' an id",
        "kind": QUICK_FIX,
        "edit": {"changes": {path.as_uri(): [{"range": replaced, "newText": wanted.text}]}},
    }


def actions(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]] = (),
    project: UnitProject | None = None,
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

    The reconcile actions are offered whether or not the client sent a finding with its
    request; the identity one is not. It is offered only where ``missing-id`` was actually
    reported, which is what keeps it inside the project's own severity policy: a project that
    has silenced the check with ``-W missing-id=ignore`` has said it is not adopting ids yet,
    and an editor that goes on offering them anyway is arguing with a decision already made.

    The vocabulary actions are offered only where ``unknown-unit`` was reported, for the same
    reason, and on whatever states the unit - a scalar type or a structure member as much as a
    declaration. They are planned in the project ``project`` names; without one, none is.
    """
    # After the declaration's own actions, so that neither inherits the other's findings, and
    # a fix the reader asked for about the declaration keeps the preferred slot.
    return [
        *_on_the_declaration(built, path, document, pointer, cache, reported),
        *_vocabulary_actions(built, document, pointer, cache, reported, project),
    ]


def _on_the_declaration(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The actions on the declaration around the cursor: its keys brought into agreement with
    the other declarations of its object, and an identity where ``missing-id`` was reported."""
    within = WITHIN_DEFINITION.match(pointer)
    if within is None:
        return []
    definition = within.group()
    name = document.value_at(f"{definition}.name")
    if not isinstance(name, str):
        return []

    offered = [
        _protocol_action(action, cache)
        for action in reconciliations(built, path, document, pointer, cache)
    ]
    settles = [entry for entry in reported if entry.get("code") in RECONCILED]
    if settles and offered:
        for action in offered:
            action["diagnostics"] = settles
        offered[0]["isPreferred"] = True

    # Appended rather than folded into the loop above: it settles its own finding and answers
    # a different question, so it must not inherit the reconcile actions' diagnostics or take
    # the preferred slot from a fix the reader actually asked for.
    unstamped = [entry for entry in reported if entry.get("code") in UNIDENTIFIED]
    if unstamped:
        identity = _give_an_identity(path, document, definition, name)
        if identity is not None:
            identity["diagnostics"] = unstamped
            offered.append(identity)
    return offered


def reconciliations(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    *,
    owned: bool = False,
) -> list[Reconciliation]:
    """Every way to settle the declaration at ``pointer``, in the order to offer them.

    On a key that can be propagated, that key; anywhere else inside the declaration, every key
    that differs from the other declarations. Two ways at most per key - somebody else's answer
    brought here, and this one's answer sent out - ordered by which side owns the variable.

    ``owned=True`` keeps only the first of each key's pair - the direction the ownership rule
    wants for this declaration - or nothing when that direction does not exist, and nothing at
    all, for every key, when the variable has no single producer: two components writing it, or
    none, leaves no side to take without the tool choosing a winner it has no standing to choose.
    The editor calls without it, offering both (and whatever else two or no producers still
    leaves reachable) and letting the reader pick; ``ddd gui`` calls with it, because a button
    whose direction the reader has to work out is not the one press it exists to be, and falling
    through to the *other* direction when the wanted one is missing would have a consumer rewrite
    its producers, a producer adopt its consumers' consensus, or - with no producer to prefer at
    all - one disagreeing declaration overwrite another in a dispute neither of them owns.

    Kept taking is also widened to every declaration of the variable, not left at the one it was
    computed for: the editor's own actions reach where the cursor is, which is right for a
    cursor and wrong for a finding, where pressing the button means the disagreement over
    everywhere, not moved along to the next file that still carries it. Giving needs no such
    widening - it is built from :func:`settle` already, which never reached only one file.

    Taking is narrower too, under ``owned=True``: adopting what the other readers agree on is
    offered to the editor, never to the page. It only ever arises with a silent producer - the
    one case ``_from_producer`` cannot answer for - and a silent owner is not standing in for
    its readers' consensus, whatever they happen to agree on among themselves.
    """
    within = WITHIN_DEFINITION.match(pointer)
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
    if owned and len(built.producers.get(name, ())) != 1:
        # No single owner, so no direction for a fix to flow in. Two components writing one
        # variable - or none writing it - is its own finding, and settling the disagreement
        # between them would be choosing a winner this has no standing to choose.
        return []
    offered: list[Reconciliation] = []
    for candidate in wanted:
        # Two ways to settle a key, and at most one of each. Taking is somebody else's answer
        # brought here - the producer's for preference, the one the rest agree on otherwise,
        # or their silence. Giving is this declaration's answer sent out, value or silence.
        taken = _from_producer(built, here, document, name, candidate, cache) or _remove_here(
            built, here, document, name, candidate, cache
        )
        if not owned:
            # The editor offers a consensus among the other declarations where the producer is
            # silent. The page does not: with one owner guaranteed above, a silent owner means
            # there is no owner's answer to take, and what the other readers happen to agree on
            # is not one.
            taken = taken or _adopt(built, here, document, name, candidate, cache)
        given = _propagate(built, here, document, name, candidate, cache) or _remove_elsewhere(
            built, here, document, name, candidate, cache
        )
        # A consumer is offered the producer's value first; the producer is offered its own,
        # outward. Which side owns the variable is not a matter of taste here - it is the rule
        # the whole tool is built on, and the fix that reads naturally is the one that follows
        # it rather than the one that quietly redefines somebody else's data.
        ordered = [given, taken] if produces else [taken, given]
        if owned:
            first = ordered[0]
            if first is not None and not produces:
                first = _across(built, name, first, cache)
            ordered = [first]
        offered.extend(action for action in ordered if action is not None)
    return offered


def _across(
    built: Index, name: str, action: Reconciliation, cache: dict[Path, Document]
) -> Reconciliation:
    """One declaration's settlement widened to every declaration of the variable.

    The editor changes what the cursor is in, which is the right reach for a cursor and the
    wrong one for a finding: a reader pressing a finding's button means the disagreement to be
    over, not to move to the next file that still carries it.
    """
    (change,) = action.settlement.changes
    return Reconciliation(
        action.title, action.key, settle(built, name, action.key, change.raw, cache)
    )


def _vocabulary_actions(
    built: Index,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]],
    project: UnitProject | None,
) -> list[dict[str, Any]]:
    """Put the unit under the cursor into the vocabulary, or respell it everywhere as a unit the
    vocabulary lists.

    Both are the plans of :mod:`ddd.lsp.units`, the ones ``ddd gui`` makes, so an editor and the
    page write the same edit. The spellings offered are the finding's own suggestions -
    :func:`ddd.analysis.close_units` over the same vocabulary - so the lightbulb never proposes
    a unit the message did not name, and a unit nothing is close to is offered no rename at
    all. A plan that is refused is not offered.
    """
    unknown = [entry for entry in reported if entry.get("code") in UNKNOWN_UNIT]
    subject = renameable_at(document, pointer)
    if project is None or not unknown or subject is None or subject[0] != "unit":
        return []
    unit = subject[1]
    if unit in built.vocabulary:
        # The finding is older than the vocabulary, which lists the unit now.
        return []
    plans = [(f"Add '{unit}' to the vocabulary", partial(add_unit, built, project, unit, cache))]
    # A rename's pointers are the disk's, and made in a buffer that has moved one of them it
    # would respell whatever sits there now: none is offered until that buffer is saved.
    if not unit_drift(built, unit, cache):
        plans.extend(
            (
                f"Rename '{unit}' to '{close}' everywhere",
                partial(rename_unit, built, project, unit, close, cache),
            )
            for close in close_units(unit, sorted(built.vocabulary))
        )
    offered: list[dict[str, Any]] = []
    for title, plan in plans:
        # Refused, or not an edit the engine can make in the buffer as it stands - a units file
        # caught halfway through an edit: either way there is nothing to offer.
        with contextlib.suppress(UnitRefusalError, EditError):
            changes = text_edits(plan(), cache)
            offered.append(
                {
                    "title": title,
                    "kind": QUICK_FIX,
                    "edit": {"changes": changes},
                    "diagnostics": unknown,
                }
            )
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


@dataclass(frozen=True, slots=True)
class Settled:
    """One declaration a settlement changes, and what it states from then on."""

    site: Site
    raw: str | None
    """The json text the declaration is to state, or ``None`` to stop stating the key at all."""


@dataclass(frozen=True, slots=True)
class Unsettled:
    """One declaration a settlement cannot change, and why not."""

    site: Site
    reason: Literal["unreachable", "kind", "type", "storage"]
    """``unreachable``: its file no longer names the variable at that pointer, or no longer
    reads as json. ``kind``: its kind has no such key, or requires the one being taken out.
    ``type``: it names a declared type that fixes the key to another value. ``storage``: the
    key is the storage it named, or would name it a second way - what
    :func:`ddd.models.objects.storage_keys` answers."""

    type_name: str | None = None
    """The declared type that fixes the key, when ``reason`` is ``type``."""


@dataclass(frozen=True, slots=True)
class Settlement:
    """What making every declaration of one variable state one value for one key takes."""

    changes: tuple[Settled, ...]
    unsettled: tuple[Unsettled, ...]


def settled_at(
    built: Index, site: Site, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settled | Unsettled | None:
    """What one declaration does about ``raw`` for ``key``: take it, refuse it, or nothing.

    ``None`` where there is nothing to do - the declaration already means that value, or it is
    leaving a deferred key to whoever states it. The body of :func:`settle`'s own loop, lifted
    so that an action changing one declaration asks it the same question a whole settlement
    asks of each: the two must not drift into two readings of "can this declaration take it".

    A declaration naming a declared type takes none of the keys the type fixes - every key of
    :data:`ddd.models.objects.FIXED_BY_A_TYPE`, the ``datatype`` as much as what it means: it
    agrees when the type states ``raw``, and refuses otherwise - stating the key beside the type
    is an error the loader reports, not an override. Read from what the declaration *resolves
    to*, in other words, which is what ``definition-mismatch`` compares and what makes a
    ``typename`` carrying the answer something other than silence.

    Nor does a declaration give up the storage it named, or name it a second way. That is
    :func:`ddd.models.objects.storage_keys`', the same reading the variable's panel hides its
    "state nothing" by, and the loader refuses a file either would write: a ``datatype`` taken
    out, or a ``typename`` written beside one, leaves storage named twice or not at all.
    """
    document = _at_site(site, name, cache)
    if document is None:
        return Unsettled(site, "unreachable")
    typename = document.value_at(f"{site.pointer}.typename")
    if key in FIXED_BY_A_TYPE and isinstance(typename, str):
        if _fixed_by(built, typename, key, cache) != raw:
            return Unsettled(site, "type", typename)
        return None
    stated = document.raw_at(f"{site.pointer}.{key}")
    if _already(key, stated, raw) or (key in DEFERRED_KEYS and stated is None):
        return None
    storage, another = storage_keys(
        [named for named in STORAGE_NAMES if document.raw_at(f"{site.pointer}.{named}") is not None]
    )
    if (raw is None and key in storage) or (raw is not None and key in another):
        return Unsettled(site, "storage")
    accepted, required = _keys_of(document, site.pointer)
    if (raw is None and key in required) or (raw is not None and key not in accepted):
        return Unsettled(site, "kind")
    return Settled(site, raw)


def settle(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settlement:
    """Which declarations of ``name`` change for every one of them to state ``raw`` as ``key``,
    and which of them cannot.

    One rule for two callers. The language server's "Apply this unit to N other declarations"
    leaves out what cannot change and offers the rest; ``ddd gui`` refuses the whole change
    instead, because its reader chose a value for the variable and a change that reaches only
    some of its declarations is not the one they chose. Deciding here, once, is what keeps the
    editor and the page from disagreeing about what a change touches.
    """
    changes: list[Settled] = []
    unsettled: list[Unsettled] = []
    for site in built.declarations.get(name, ()):
        decided = settled_at(built, site, name, key, raw, cache)
        if isinstance(decided, Settled):
            changes.append(decided)
        elif decided is not None:
            unsettled.append(decided)
    return Settlement(tuple(changes), tuple(unsettled))


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """One way to settle one key of one variable: decided, and not yet spelled.

    What the two clients share. The decision is which declarations come to state what, which is
    a question about the project; how that arrives in a file is a question about text, and the
    two have no business being one function. :mod:`ddd.finding_fixes` spells this as operations
    on json pointers, this module as edits with ranges.
    """

    title: str
    key: str
    settlement: Settlement


def _protocol_action(reconciliation: Reconciliation, cache: dict[Path, Document]) -> dict[str, Any]:
    """A decision as the protocol carries it: a titled quick fix over one or more files.

    ``_assign`` and ``_erase`` answer ``None`` for a change the decision already ruled out, so
    nothing here is expected to skip; the guard is the only-child refusal of :func:`_erase`,
    which stays a question about a file's own style rather than about the data.
    """
    changes: dict[str, list[dict[str, Any]]] = {}
    for change in reconciliation.settlement.changes:
        document = read(change.site.path, cache)
        edit = (
            _erase(document, change.site.pointer, reconciliation.key)
            if change.raw is None
            else _assign(document, change.site.pointer, reconciliation.key, change.raw)
        )
        if edit is not None:
            changes.setdefault(change.site.path.as_uri(), []).append(edit)
    return {"title": reconciliation.title, "kind": QUICK_FIX, "edit": {"changes": changes}}


def _fixed_by(built: Index, typename: str, key: str, cache: dict[Path, Document]) -> str | None:
    """The json text a declared type states for ``key``, or ``None`` when it states none - a
    structure, which has no room for a unit, or a name no type of the project declares."""
    site = built.types.get(typename)
    return None if site is None else read(site.path, cache).raw_at(f"{site.pointer}.{key}")


def _already(key: str, stated: str | None, raw: str | None) -> bool:
    """Whether the declaration already says what the settlement would write.

    By what the value means rather than by its json text. The text is the file's own layout,
    and an edit writes a value in the *target* file's layout: comparing text would call a
    declaration changed for spelling a conversion over four lines where the value came from a
    file that writes it on one, and would go on asking for that change after every apply.
    Removing a key compares as it always did - ``None`` against ``None`` is nothing to remove,
    and a stated key has something to take out whatever it says.
    """
    if stated is None or raw is None:
        return stated == raw
    return same_value(key, stated) == same_value(key, raw)


def _at_site(site: Site, name: str, cache: dict[Path, Document]) -> Document | None:
    """The document a site lies in, provided the site still names the object there.

    The index is built from the files on disk and a site's pointer describes them; an open
    buffer may have a declaration inserted above, after which the same pointer names a
    different object. Reading a value from there, or inserting one, would reconcile the
    wrong declaration - so a site that has drifted is treated as absent.
    """
    document = read(site.path, cache)
    return document if document.value_at(f"{site.pointer}.name") == name else None


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
        target = _at_site(site, name, cache)
        if target is None:
            continue
        absent.update(interface_keys(target.value_at(site.pointer)))
    # A key this declaration may defer on is not missing from it.
    return sorted(absent - mine - DEFERRED_KEYS)


def _adopt(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """Take a value the others state and this declaration does not.

    Only when they agree with each other about it - by what the value means, the rule
    ``definition-mismatch`` compares by, so two declarations spelling one conversion
    differently are one answer rather than two. Two different answers is a question about which
    one is right, and picking one silently is exactly the kind of help nobody asked for.

    Written through :func:`_assign` rather than straight into the text, so that this direction
    is refused for a key the target's own kind does not have on the same terms as every other.
    """
    if key in DEFERRED_KEYS or document.raw_at(f"{here.pointer}.{key}") is not None:
        return None
    others = [site for site in built.declarations.get(name, ()) if site != here]
    targets: list[Document] = []
    for site in others:
        target = _at_site(site, name, cache)
        if target is None:
            # The title claims the other declarations state this value - a claim only
            # available having actually read every one of them. A declaration drifted out of
            # reach is not the same as one that agrees, so a single reading among several
            # readable others is not the unanimity the title would assert; withhold instead.
            return None
        targets.append(target)
    spelled = [
        raw
        for site, target in zip(others, targets, strict=True)
        if (raw := target.raw_at(f"{site.pointer}.{key}")) is not None
    ]
    # Counted by what each value means rather than by its json text: two files writing one
    # conversion differently state one value, which is why the checker files nothing between
    # them, and counting their spellings would withhold this action from declarations it calls
    # settled. The text carried is the first spelling of the one value - they say the same
    # thing, and it travels verbatim as every value here does.
    stated: dict[str, str] = {}
    for raw in spelled:
        stated.setdefault(same_value(key, raw), raw)
    if len(stated) != 1:
        return None
    decided = settled_at(built, here, name, key, next(iter(stated.values())), cache)
    if not isinstance(decided, Settled):
        return None
    return Reconciliation(
        f"Take the {key} the other declarations of '{name}' state",
        key,
        Settlement((decided,), ()),
    )


def _from_producer(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
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
    target = _at_site(producer, name, cache)
    raw = None if target is None else target.raw_at(f"{producer.pointer}.{key}")
    if raw is None:
        return None
    decided = settled_at(built, here, name, key, raw, cache)
    if not isinstance(decided, Settled):
        return None
    owner = producer.path.stem.removesuffix(".ddd")
    return Reconciliation(f"Use the {key} declared in {owner}", key, Settlement((decided,), ()))


def _remove_here(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """Take a key out, when this declaration is the only one that states it.

    The other half of adopting somebody else's answer: a key nobody else mentions is
    reconciled by removing it just as much as by spreading it, and which of the two an author
    wants is not something to decide for them. Only offered when no other declaration has one,
    because otherwise removing it settles nothing.
    """
    if key in DEFERRED_KEYS or document.raw_at(f"{here.pointer}.{key}") is None:
        return None
    others = [site for site in built.declarations.get(name, ()) if site != here]
    # Nobody to disagree with is not the same as everybody agreeing: a variable one component
    # declares on its own has nothing to reconcile, and offering to strip its unit would be a
    # suggestion to lose information for no reason at all.
    if not others:
        return None
    targets: list[Document] = []
    for site in others:
        target = _at_site(site, name, cache)
        if target is None:
            # The title below claims no other declaration has this key - a claim only
            # available having actually read every one of them. A declaration drifted out of
            # reach is not the same as one that agrees, so it must not be counted out of the
            # "other declarations" the title speaks for; withhold the offer instead.
            return None
        targets.append(target)
    if any(
        target.raw_at(f"{site.pointer}.{key}") is not None
        for site, target in zip(others, targets, strict=True)
    ):
        return None
    decided = settled_at(built, here, name, key, None, cache)
    if not isinstance(decided, Settled):
        return None
    producers = [site for site in built.producers.get(name, ()) if site != here]
    where = (
        f"which {producers[0].path.stem.removesuffix('.ddd')} does not declare"
        if len(producers) == 1
        else f"which no other declaration of '{name}' has"
    )
    return Reconciliation(f"Remove this {key}, {where}", key, Settlement((decided,), ()))


def _remove_elsewhere(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """Take the key out of the other declarations, when this one does not state it.

    The mirror of spreading a value, and the direction that was missing: a declaration with no
    ``unit`` could take one from the others but never say "none of you should have one
    either". Both are ways of agreeing, and which one is meant is the author's to choose.

    Which declarations it reaches is :func:`settle`'s to say, as it is for :func:`_propagate`,
    and it carries what cannot lose the key as well: an editor offers the reachable part, and a
    page that refuses a partial settlement needs to be told there is one. This declaration is
    among the ones asked and answers nothing, since silence is what it already states - except
    where a type it names states the key for it, which is a declaration that cannot lose it
    either and is exactly how a removal that settles nothing used to be offered.
    """
    if key in DEFERRED_KEYS or document.raw_at(f"{here.pointer}.{key}") is not None:
        return None
    settlement = settle(built, name, key, None, cache)
    elsewhere = len(settlement.changes)
    if elsewhere == 0:
        return None
    return Reconciliation(
        f"Remove the {key} from {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        key,
        settlement,
    )


def _erase(document: Document, definition: str, key: str) -> dict[str, Any] | None:
    """Cut a member out of an object, taking exactly one comma with it.

    Which comma is the whole difficulty, and it depends on where the member sits. A member
    with one after it is removed up to the start of that one, which takes its own comma and
    leaves the next where this began. The last member is removed from the *end of the one
    before it*, which takes the comma that used to join them and leaves no trailing one. The
    cutting itself is :func:`ddd.editing.removal`'s, which the GUI's edits share; the refusal
    of an only child stays here, a decision about what a quick fix offers.

    An only child is refused: what to leave between the braces is a judgement about the file's
    style rather than about the data. It cannot arise for these keys anyway - every definition
    has a ``name`` beside them.
    """
    members = document.value_at(definition)
    if not isinstance(members, dict) or key not in members or len(members) == 1:
        return None
    return _protocol_edit(document, removal(document, f"{definition}.{key}"))


def _propagate(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """One action, or nothing when every other declaration already says the same.

    Which declarations it reaches is :func:`settle`'s to say, as it is for ``ddd gui``. One that
    cannot take the value is left out of the action rather than refusing it: the others can
    still be reconciled from here, and an editor offers what it can.
    """
    raw = document.raw_at(f"{here.pointer}.{key}")
    if raw is None:
        return None
    settlement = settle(built, name, key, raw, cache)
    elsewhere = len(settlement.changes)
    if elsewhere == 0:
        return None
    return Reconciliation(
        f"Apply this {key} to {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        key,
        settlement,
    )


def _assign(document: Document, definition: str, key: str, raw: str) -> dict[str, Any] | None:
    """The edit that makes one declaration say ``key: raw``, or nothing if it already does.

    Refused for a key the target's own kind does not have. Two declarations of one object
    disagreeing about ``kind`` is a finding of its own, and while it stands, writing a curve's
    ``axis`` into the measurement somebody else declared would only add a file that no longer
    loads to a project that already has something to fix.

    Refused as well for a key a named type fixes - what it means and the storage under it alike,
    :data:`ddd.models.objects.FIXED_BY_A_TYPE` - for the same reason: the declaration already
    gets this key from its ``typename``, and stating it again beside that is an error the loader
    reports, not an override. The same set :func:`settled_at` decides by, which asks first: these
    are two spellings of one rule and must not come to two answers.
    """
    if key not in _keys_of(document, definition)[0]:
        return None
    if key in FIXED_BY_A_TYPE and isinstance(document.value_at(f"{definition}.typename"), str):
        # The type it names fixes this key; stated beside it, the loader refuses the file. An
        # explicit ``null`` names no type - the same reading ``settle`` gives it, so a plain
        # declaration that happens to state ``"typename": null`` beside its ``datatype`` is not
        # caught here.
        return None
    existing = document.raw_at(f"{definition}.{key}")
    if existing is not None:
        # The same question :func:`settle` asks of every declaration it reaches, asked through
        # the same function: a value already meaning what would be written is nothing to write,
        # and the two must not drift into two readings of "already says it".
        if _already(key, existing, raw):
            return None
        return {"range": document.value_range_of(f"{definition}.{key}"), "newText": raw}
    return _insert(document, definition, key, raw)


def _insert(document: Document, definition: str, key: str, raw: str) -> dict[str, Any] | None:
    """Add a key an object does not have, next to the one written last.

    After the last member rather than at the front, because that is where a person adding a key
    by hand puts it, and because the first member of a definition is its ``name`` - which is
    what somebody reading the file scans for. Where the key goes and how it is separated is
    :func:`ddd.editing.member_addition`'s; the value travels verbatim, as the author of the
    other declaration wrote it.
    """
    members = document.value_at(definition)
    if not isinstance(members, dict) or not members:
        return None
    return _protocol_edit(document, member_addition(document, definition, key, raw, verbatim=True))


def _protocol_edit(document: Document, edit: TextEdit) -> dict[str, Any]:
    """An edit the engine computed as offsets, as the protocol carries it: a range and a text."""
    return {
        "range": {"start": document.position(edit.start), "end": document.position(edit.end)},
        "newText": edit.text,
    }
