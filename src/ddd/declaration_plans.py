"""What a component may add to its interface, and what each change of one takes.

Transport-neutral, like :mod:`ddd.type_plans` beside it. Nothing here writes a file: a verb
answers a plan of edit-engine operations, and ``POST /api/edit`` is what writes it, so one
engine makes every change ``ddd gui`` makes and part 5's stack puts any of them back.

Nothing here formats json either. ``ddd.editing.insertion`` lays a value out in the layout of
the place it goes - a key per line, a container of literals on one line - which is exactly how
the description files spell a declaration.

Each verb answers a :class:`~ddd.plans.Plan` - of one file always, as it happens: a declaration is
written into the component that makes it, and nothing else moves - or raises a
:class:`~ddd.plans.PlanRefusalError`: ``invalid`` where the change cannot be made - a name that
may not be used, a key the kind has not, a required key left out, a scope this name may not take,
a value the models themselves refuse; ``not-found`` where the file declares no interface, or no
declaration of that name; ``stale`` where the declaration read from holds another object where
the index found it, its file having changed since the analysis read it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.analysis import PRODUCER_KEYS
from ddd.editing import Operation
from ddd.identity import new_id
from ddd.lsp.edits import type_conversions
from ddd.lsp.navigation import Index, Site, changed_since, drift, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.models.component import Scope
from ddd.models.objects import definition_keys, definition_problem
from ddd.plans import Plan, PlannedEdit, PlanRefusalError
from ddd.pointers import parent_pointer
from ddd.variable_keys import KEY_ORDER, KeyOffer, offer_for

KINDS: Final = ("measurement", "parameter", "value_block", "curve", "map", "axis")
"""The six kinds a declaration may be, in the order the form offers them."""

SCOPES: Final = ("output", "input", "local")
"""``ddd.models.component.Scope``'s three values, in the order the form offers them."""

PRODUCING_SCOPES: Final = frozenset(scope.value for scope in Scope if scope.is_producer)
"""The scopes that own what they declare, and whose declaration is therefore stamped.

:attr:`ddd.models.component.Scope.is_producer` decides it - ``output`` and ``local`` - rather
than a comparison against ``"output"`` alone: a local owns its object exclusively, so
``missing-id`` fires on an unstamped local exactly as it does on an unstamped output, and
:data:`ddd.identity._PRODUCING` names the same pair. Spelled as the raw strings a description
carries, the way :mod:`ddd.identity` spells them, because a scope arrives here as the text a
page sent and is checked against :data:`SCOPES` rather than parsed into a :class:`Scope`.
"""

CARRIED_BY_A_READER: Final = frozenset(key for key, _, _ in PRODUCER_KEYS)
"""What a reader does not copy from the producer it reads.

Derived from :data:`ddd.analysis.PRODUCER_KEYS` rather than restated beside it: that tuple is
where the project decides which keys only a producing declaration may state - ``init``,
``section``, ``raster``, ``id`` and ``extensions`` - and it names, per key, the check a
consumer stating one earns. Copying any of them into an ``input`` would write the finding this
verb exists to avoid, and reading the rule where it is decided means a sixth key added there
is dropped here the moment it exists. The same reasoning :func:`definition_keys` already uses
about the models, applied to the analysis.

One concept named once, the way :func:`ddd.variables.component_of` is: a copy is what let a
reader carry ``section`` and ``raster`` into an ``input``, which no measurement across the
examples could show - every producer there stating one is ``local``, and a local is never
declarable elsewhere.
"""

INTERFACE: Final = "component.interface"
"""Where a component's declarations live, which is the array a verb inserts into."""


@dataclass(frozen=True, slots=True)
class Declarable:
    """One variable this component could read, as the name field offers it."""

    name: str
    kind: str
    """``measurement`` … ``axis``, or ``""`` when no declaration of it states one."""

    producer: str | None
    """The component producing it, as the analysis loaded it; ``None`` when nothing does."""


def declarable(built: Index, file: Path) -> tuple[Declarable, ...]:
    """Every name the project declares that ``file`` does not and a scope may take there, sorted
    by name, each with the component producing it.

    A name some component declares ``local`` is left out: :func:`scopes_for` answers it no scope,
    and the name field is not offered a name the form has no scope to write it with. A producer is
    named as the analysis loaded its component, which the index holds
    (:attr:`~ddd.lsp.navigation.Index.components`), and no file is read: read off each producer's
    file instead, every one of them parsed, the panel of the largest component of a generated
    project of 100,000 declarations, offering 46,666 names, took 1.60 to 1.96 s to answer, and
    takes 0.35 to 0.49 s (Linux development PC, three askings each).
    """
    here = file.resolve()
    return tuple(
        Declarable(
            name=name,
            kind=built.kinds.get(name, ""),
            producer=(
                built.components[produced[0].path]
                if (produced := built.producers.get(name))
                else None
            ),
        )
        for name, sites in sorted(built.declarations.items())
        if all(site.path != here for site in sites) and scopes_for(built, name)
    )


def scopes_for(built: Index, name: str) -> tuple[str, ...]:
    """Which of :data:`SCOPES` this name may be declared with, in that order.

    ``input`` while no component keeps the name ``local``. ``output`` only while nothing
    produces the name, so the menu cannot make a ``multiple-producers`` - and when something is
    missing a producer, this is the repair. ``local`` only for a name nothing declares at all,
    because ``local-conflict`` is exactly a local beside another declaration.

    No scope at all where a component declares the name ``local``: it owns the object
    exclusively, so a declaration of it anywhere else is a ``local-conflict`` whatever its scope -
    an ``input`` no less than a second producer, and one more where the project holds one already.
    The index lists a local among the producers of a name, which the editor jumps by and the grid
    reads values from (:attr:`ddd.lsp.navigation.Index.producers`), so this is not read off them:
    it is asked of the scope each declaration states.
    """
    if name not in built.declarations:
        return SCOPES
    if _kept_by(built, name) is not None:
        return ()
    return ("input",) if built.producers.get(name) else ("output", "input")


def _kept_by(built: Index, name: str) -> str | None:
    """The name of the component that declares ``name`` ``local``, as the analysis loaded it, or
    ``None`` where none does.

    The first, in the order the project lists its components: the one ``local-conflict`` names
    when it files each declaration of the name beside it.
    """
    for site in built.declarations.get(name, ()):
        if built.scopes[site] == Scope.LOCAL.value:
            return built.components[site.path]
    return None


def _refuse_kept(built: Index, name: str) -> None:
    """Refuse declaring ``name`` in a component other than the one that keeps it ``local``
    (:func:`_kept_by`), naming that one: a declaration of it anywhere else, in any scope, is a
    ``local-conflict``. One sentence for a read of it and for a new object of its name alike:
    the chooser offers it to no other component, so it is said only to a name asked for all the
    same."""
    if (keeper := _kept_by(built, name)) is not None:
        raise PlanRefusalError(
            "invalid",
            f"'{name}' is local to component '{keeper}', so no other component may declare it",
        )


def form_for(built: Index, kind: str, file: Path) -> tuple[KeyOffer, ...]:
    """What a new declaration of that kind asks for: one offer per key of ``KEY_ORDER`` the
    kind accepts, each with no value in play and ``required`` as the models have it.

    The choosers offer what a declaration in ``file`` may name, which leaves out another
    component's locals.

    A kind nothing declares answers empty rather than raising: ``definition_keys`` answers two
    empty sets for one, and the endpoint refuses before reaching here.
    """
    accepted, required = definition_keys(kind)
    return tuple(
        offer_for(built, key, None, required=key in required, files={file.resolve()})
        for key in KEY_ORDER
        if key in accepted
    )


def read_object(
    built: Index, file: Path, name: str, scope: str, cache: dict[Path, Document]
) -> Plan:
    """What reading an object the project already has takes.

    One ``insert`` appending a declaration that carries the producer's own definition, less
    :data:`CARRIED_BY_A_READER` - which is what makes the new reader agree with its producer by
    construction rather than by a later check. A name nothing produces is read from the one
    declaration there is: there is no owner's definition to copy, and the alternative is
    refusing the very repair the reader came for.

    A name a component declares ``local`` is refused in every scope, saying whose it is rather than
    only that the scope asked is none it may take: the declaration would be a ``local-conflict``,
    which is why :func:`scopes_for` answers it no scope and :func:`declarable` leaves it out.

    That repair is what a :data:`PRODUCING_SCOPES` scope means here - ``scopes_for`` offers
    ``output`` exactly while nothing produces the name - so the declaration written is stamped,
    as :func:`declare_object` stamps one. Without it the verb would trade a ``missing-producer``
    for a ``missing-id``, which is not a repair.

    The definition carried is read where the index recorded it, and refused ``stale`` where that
    place holds another object's, or no object at all - a declaration put in above it, or taken
    out, since the analysis read the file - rather than carried under this name, or answered as a
    name the project does not declare, which the index the reader took it from still names: the
    question :func:`ddd.variables.declarations_of` asks before it reads a declaration. The
    producer's entry states what the declaration is compiled under as well - its ``condition``,
    which is no part of the definition - and the reader carries it, the analysis comparing the two
    (``condition-mismatch``). The write goes to ``file`` alone, so no fingerprint the edit
    carries is of the file read from.
    """
    here, entries = _interface(file, cache)
    sites = built.declarations.get(name)
    if not sites:
        raise PlanRefusalError("not-found", f"the project declares no '{name}'")
    if any(site.path == here for site in sites):
        raise PlanRefusalError("invalid", f"this component already declares '{name}'")
    _refuse_kept(built, name)
    if scope not in scopes_for(built, name):
        raise PlanRefusalError("invalid", f"'{name}' may not be declared '{scope}' here")
    owner = (built.producers.get(name) or sites)[0]
    stated = read(owner.path, cache).value_at(owner.pointer)
    if not isinstance(stated, dict) or stated.get("name") != name:
        raise PlanRefusalError(
            "stale", changed_since((owner.path,), f"'{name}' cannot be declared here")
        )
    definition = {key: value for key, value in stated.items() if key not in CARRIED_BY_A_READER}
    if scope in PRODUCING_SCOPES:
        definition = _stamped(name, definition)
    condition = read(owner.path, cache).value_at(f"{parent_pointer(owner.pointer)}.condition")
    return _appended(
        here, entries, scope, definition, condition if isinstance(condition, str) else None
    )


def declare_object(
    built: Index,
    file: Path,
    scope: str,
    definition: Mapping[str, object],
    cache: dict[Path, Document],
) -> Plan:
    """What declaring a new object takes: one ``insert`` appending the definition given.

    Refused before a file is touched for a name the project may not use, in
    :func:`~ddd.lsp.navigation.rename_problem`'s own sentence - a new declaration lands in the
    namespace a rename guards, so it gets the same answers rather than a second set derived
    here - but a name another component keeps ``local`` first, naming that component as a read
    of it is refused (:func:`_refuse_kept`): no chooser offers it, and that the project declares
    it already does not say where, nor that no scope would do. A local of this file's own is
    the project's name like any other. A declaration whose scope is one of
    :data:`PRODUCING_SCOPES` is stamped with a fresh id, after its ``name``, where every stamped
    declaration of the examples carries one.

    Stamped, the definition is asked of the models (:func:`~ddd.models.definition_problem`) - a
    rule crossing two keys, a ``datatype`` wanting a ``conversion`` among them, is not something
    a key-by-key check above can see, and is refused in the model's own sentence rather than
    left for the file it is written into to refuse back. The same question asks the rules of the
    analysis that need no more of the project than the declaration and the type it names - limits
    that run past the largest float, a shape past the caps, a string type named with none or with
    two dimensions - and refuses them in the analysis's own sentence.
    """
    here, entries = _interface(file, cache)
    name, kind = definition.get("name"), definition.get("kind")
    if not isinstance(name, str) or not isinstance(kind, str):
        raise PlanRefusalError("invalid", "a definition states a 'name' and a 'kind'")
    if kind not in KINDS:
        raise PlanRefusalError("invalid", f"'{kind}' is not a kind: {', '.join(KINDS)}")
    if scope not in SCOPES:
        raise PlanRefusalError("invalid", f"'{scope}' is not a scope: {', '.join(SCOPES)}")
    if all(site.path != here for site in built.declarations.get(name, ())):
        _refuse_kept(built, name)
    problem = rename_problem(built, name)
    if problem is not None:
        raise PlanRefusalError("invalid", problem)
    if "id" in definition:
        raise PlanRefusalError("invalid", "an id is this server's to mint, not the page's")
    if extra := sorted(set(definition) - _statable(kind)):
        raise PlanRefusalError("invalid", f"a {kind} has no '{extra[0]}' to state")
    _, required = definition_keys(kind)
    if missing := sorted(required - set(definition)):
        raise PlanRefusalError("invalid", f"a {kind} must state '{missing[0]}'")
    stated = dict(definition)
    if scope in PRODUCING_SCOPES:
        stated = _stamped(name, stated)
    problem = definition_problem(stated, type_conversions(built, cache))
    if problem is not None:
        raise PlanRefusalError("invalid", problem)
    return _appended(here, entries, scope, stated)


def remove_declaration(built: Index, file: Path, name: str, cache: dict[Path, Document]) -> Plan:
    """What removing a declaration takes: one ``remove`` at its index in the interface.

    ``built`` is unread - the index says which components declare a name, and this needs the
    index *of this file*, which its own text is. It is taken all the same so that the three
    verbs are called the same way, and so that a later rule about the project can be added here
    without changing every caller.
    """
    here, entries = _interface(file, cache)
    document = read(here, cache)
    for position in range(len(entries)):
        if document.value_at(f"{INTERFACE}[{position}].definition.name") == name:
            operation = Operation("remove", f"{INTERFACE}[{position}]")
            return Plan((PlannedEdit(here, (operation,)),))
    raise PlanRefusalError("not-found", f"{here.name} declares no '{name}'")


def describe_declaration(
    built: Index, file: Path, name: str, description: str, cache: dict[Path, Document]
) -> Plan:
    """What describing a declaration takes: one ``set`` at its own ``description``, or one
    ``remove`` of that key where ``description`` is the empty text, which is the model's default.

    The declaration is the one ``file`` holds: ``description`` is no key the declarations of a
    variable share (:data:`ddd.lsp.edits.PROPAGATED_KEYS`), because two components may describe
    one variable in their own words, and this changes no other component's. Found where the
    index recorded it, and refused ``stale`` where that place no longer holds the name - a
    declaration put in above it, or taken out, since the analysis read the file
    (:func:`ddd.lsp.navigation.drift`) - rather than described under another's name. A file the
    index records no declaration of the name in, whether it declares none or did not load, is
    ``not-found``.

    The empty text asks for a description to go, which there is none to take away from a
    declaration that states none: refused, rather than planned as a ``remove`` of a key that is
    not there.
    """
    here = file.resolve()
    sites = [site for site in built.declarations.get(name, ()) if site.path.resolve() == here]
    if not sites:
        raise PlanRefusalError("not-found", f"{here.name} declares no '{name}'")
    site = sites[0]
    if drift((Site(site.path, f"{site.pointer}.name"),), name, cache):
        raise PlanRefusalError(
            "stale", changed_since((here,), f"the description of '{name}' cannot be set")
        )
    pointer = f"{site.pointer}.description"
    if not _writable(description):
        raise PlanRefusalError(
            "invalid", "a description holds a character that no file can hold, a lone surrogate"
        )
    if description:
        # Every character as written, as the plans of units and shared entries spell theirs: a
        # description holding a degree sign arrives in the file as one, where json's default
        # would write an escape.
        operation = Operation("set", pointer, json.dumps(description, ensure_ascii=False))
    elif read(here, cache).value_at(pointer) is None:
        raise PlanRefusalError(
            "invalid", f"{here.name} states no description of '{name}', so there is none to remove"
        )
    else:
        operation = Operation("remove", pointer)
    return Plan((PlannedEdit(here, (operation,)),))


def _writable(text: str) -> bool:
    """Whether ``text`` can be written to a file as utf-8: a lone surrogate, which a query can
    carry, cannot, and written as it stands it would reach no file the page could apply."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _stamped(name: str, definition: Mapping[str, object]) -> dict[str, object]:
    """That definition with a fresh identity after its ``name``, where the examples spell one.

    The name is passed rather than read out of the definition, because both callers already
    hold it as a checked string - ``declare_object`` from the page's own json, ``read_object``
    as the name it was asked for - while what the definition holds is whatever text the file
    has now, which may have moved on since the index was built.
    """
    rest = {key: value for key, value in definition.items() if key != "name"}
    return {"name": name, "id": new_id(), **rest}


def _statable(kind: str) -> frozenset[str]:
    """What a definition sent here may state: what the form can offer, and nothing else.

    ``definition_keys`` accepts more - ``id``, ``init``, ``a2l``, ``extensions``, ``raster``
    and ``section`` among them. The form offers none of those: ``id`` is this module's to mint,
    and the rest belong to whoever writes the file by hand.
    """
    accepted, _ = definition_keys(kind)
    return frozenset({"name", "kind", "description"}) | (accepted & frozenset(KEY_ORDER))


def _interface(file: Path, cache: dict[Path, Document]) -> tuple[Path, list[object]]:
    """The file resolved, and the declarations it holds."""
    here = file.resolve()
    entries = read(here, cache).value_at(INTERFACE)
    if not isinstance(entries, list):
        raise PlanRefusalError("not-found", f"{here.name} declares no interface")
    return here, entries


def _appended(
    here: Path,
    entries: list[object],
    scope: str,
    definition: Mapping[str, object],
    condition: str | None = None,
) -> Plan:
    """The plan that appends one declaration: an ``insert`` at the end of the interface, its
    ``condition`` - where it has one - between its scope and its definition, as the model orders
    them."""
    entry: dict[str, object] = {"scope": scope}
    if condition is not None:
        entry["condition"] = condition
    entry["definition"] = definition
    raw = json.dumps(entry)
    operation = Operation("insert", f"{INTERFACE}[{len(entries)}]", raw)
    return Plan((PlannedEdit(here, (operation,)),))
