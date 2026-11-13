"""What a component may add to its interface, and what each change of one takes.

Transport-neutral, like :mod:`ddd.type_plans` beside it. Nothing here writes a file: a verb
answers a plan of edit-engine operations, and ``POST /api/edit`` is what writes it, so one
engine makes every change ``ddd gui`` makes and part 5's stack puts any of them back.

Nothing here formats json either. ``ddd.editing.insertion`` lays a value out in the layout of
the place it goes - a key per line, a container of literals on one line - which is exactly how
the description files spell a declaration.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.analysis import PRODUCER_KEYS
from ddd.editing import Operation
from ddd.identity import new_id
from ddd.lsp.edits import type_conversions
from ddd.lsp.navigation import Index, changed_since, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.component import Scope
from ddd.models.objects import definition_keys, definition_problem
from ddd.variable_keys import KEY_ORDER, KeyOffer, offer_for
from ddd.variables import component_of

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
    """The component producing it; ``None`` when nothing does."""


def declarable(built: Index, file: Path, cache: dict[Path, Document]) -> tuple[Declarable, ...]:
    """Every name the project declares that ``file`` does not and a scope may take there, sorted
    by name.

    A name some component declares ``local`` is left out: :func:`scopes_for` answers it no scope,
    and the name field is not offered a name the form has no scope to write it with.
    """
    here = file.resolve()
    return tuple(
        Declarable(
            name=name,
            kind=built.kinds.get(name, ""),
            producer=(
                component_of(read(produced[0].path, cache), produced[0].path)
                if (produced := built.producers.get(name) or [])
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


def form_for(built: Index, kind: str) -> tuple[KeyOffer, ...]:
    """What a new declaration of that kind asks for: one offer per key of ``KEY_ORDER`` the
    kind accepts, each with no value in play and ``required`` as the models have it.

    A kind nothing declares answers empty rather than raising: ``definition_keys`` answers two
    empty sets for one, and the endpoint refuses before reaching here.
    """
    accepted, required = definition_keys(kind)
    return tuple(
        offer_for(built, key, None, required=key in required)
        for key in KEY_ORDER
        if key in accepted
    )


@dataclass(frozen=True, slots=True)
class DeclarationPlan:
    """Everything one change of an interface takes: one edit per file, sorted by path.

    One file, always, as it happens - a declaration is written into the component that makes
    it, and nothing else moves - but the shape is :class:`~ddd.type_plans.TypePlan`'s so that
    :func:`ddd.project_units.previewed` previews all three tabs' plans.
    """

    edits: tuple[PlannedEdit, ...]


class DeclarationRefusalError(Exception):
    """A change of an interface that cannot be planned, and the code both clients refuse with."""

    code: Literal["invalid", "not-found", "stale"]
    """``invalid``: the change cannot be made - a name that may not be used, a key the kind has
    not, a required key left out, a scope this name may not take, a value the models themselves
    refuse. ``not-found``: the file declares no interface, or no declaration of that name.
    ``stale``: the declaration read from holds another object where the index found it, its file
    having changed since the analysis read it."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found", "stale"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def read_object(
    built: Index, file: Path, name: str, scope: str, cache: dict[Path, Document]
) -> DeclarationPlan:
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
    place holds another object's - a declaration put in above it, or taken out, since the analysis
    read the file - rather than carried under this name: the question
    :func:`ddd.variables.declarations_of` asks before it reads a declaration. The write goes to
    ``file`` alone, so no fingerprint the edit carries is of the file read from.
    """
    here, entries = _interface(file, cache)
    sites = built.declarations.get(name)
    if not sites:
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    if any(site.path == here for site in sites):
        raise DeclarationRefusalError("invalid", f"this component already declares '{name}'")
    if (keeper := _kept_by(built, name)) is not None:
        raise DeclarationRefusalError(
            "invalid",
            f"'{name}' is local to component '{keeper}', so no other component may declare it",
        )
    if scope not in scopes_for(built, name):
        raise DeclarationRefusalError("invalid", f"'{name}' may not be declared '{scope}' here")
    owner = (built.producers.get(name) or sites)[0]
    stated = read(owner.path, cache).value_at(owner.pointer)
    if not isinstance(stated, dict):
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    if stated.get("name") != name:
        raise DeclarationRefusalError(
            "stale", changed_since((owner.path,), f"'{name}' cannot be declared here")
        )
    definition = {key: value for key, value in stated.items() if key not in CARRIED_BY_A_READER}
    if scope in PRODUCING_SCOPES:
        definition = _stamped(name, definition)
    return _appended(here, entries, scope, definition)


def declare_object(
    built: Index,
    file: Path,
    scope: str,
    definition: Mapping[str, object],
    cache: dict[Path, Document],
) -> DeclarationPlan:
    """What declaring a new object takes: one ``insert`` appending the definition given.

    Refused before a file is touched for a name the project may not use, in
    :func:`~ddd.lsp.navigation.rename_problem`'s own sentence - a new declaration lands in the
    namespace a rename guards, so it gets the same answers rather than a second set derived
    here. A declaration whose scope is one of :data:`PRODUCING_SCOPES` is stamped with a fresh
    id, after its ``name``, where every stamped declaration of the examples carries one.

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
        raise DeclarationRefusalError("invalid", "a definition states a 'name' and a 'kind'")
    if kind not in KINDS:
        raise DeclarationRefusalError("invalid", f"'{kind}' is not a kind: {', '.join(KINDS)}")
    if scope not in SCOPES:
        raise DeclarationRefusalError("invalid", f"'{scope}' is not a scope: {', '.join(SCOPES)}")
    problem = rename_problem(built, name)
    if problem is not None:
        raise DeclarationRefusalError("invalid", problem)
    if "id" in definition:
        raise DeclarationRefusalError("invalid", "an id is this server's to mint, not the page's")
    if extra := sorted(set(definition) - _statable(kind)):
        raise DeclarationRefusalError("invalid", f"a {kind} has no '{extra[0]}' to state")
    _, required = definition_keys(kind)
    if missing := sorted(required - set(definition)):
        raise DeclarationRefusalError("invalid", f"a {kind} must state '{missing[0]}'")
    stated = dict(definition)
    if scope in PRODUCING_SCOPES:
        stated = _stamped(name, stated)
    problem = definition_problem(stated, type_conversions(built, cache))
    if problem is not None:
        raise DeclarationRefusalError("invalid", problem)
    return _appended(here, entries, scope, stated)


def remove_declaration(
    built: Index, file: Path, name: str, cache: dict[Path, Document]
) -> DeclarationPlan:
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
            return DeclarationPlan((PlannedEdit(here, (operation,)),))
    raise DeclarationRefusalError("not-found", f"{here.name} declares no '{name}'")


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
        raise DeclarationRefusalError("not-found", f"{here.name} declares no interface")
    return here, entries


def _appended(
    here: Path, entries: list[object], scope: str, definition: Mapping[str, object]
) -> DeclarationPlan:
    """The plan that appends one declaration: an ``insert`` at the end of the interface."""
    raw = json.dumps({"scope": scope, "definition": definition})
    operation = Operation("insert", f"{INTERFACE}[{len(entries)}]", raw)
    return DeclarationPlan((PlannedEdit(here, (operation,)),))
