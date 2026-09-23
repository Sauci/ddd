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

from ddd.editing import Operation
from ddd.identity import new_id
from ddd.lsp.navigation import Index, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.objects import definition_keys
from ddd.variable_keys import KEY_ORDER, KeyOffer, offer_for
from ddd.variables import component_of

KINDS: Final = ("measurement", "parameter", "value_block", "curve", "map", "axis")
"""The six kinds a declaration may be, in the order the form offers them."""

SCOPES: Final = ("output", "input", "local")
"""``ddd.models.component.Scope``'s three values, in the order the form offers them."""

CARRIED_BY_A_READER: Final = frozenset({"id", "init"})
"""What a reader does not copy from the producer it reads.

Measured across examples/demo, examples/structures and examples/vocabulary: for every variable
more than one component declares, a reader's definition is the producer's without these two,
and with nothing of its own. ``id`` is the producer's identity - :mod:`ddd.identity` stamps
only a producing declaration - and ``init`` is the owner's initial value.
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
    """Every name the project declares that ``file`` does not, sorted by name."""
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
        if all(site.path != here for site in sites)
    )


def scopes_for(built: Index, name: str) -> tuple[str, ...]:
    """Which of :data:`SCOPES` this name may be declared with, in that order.

    ``input`` always. ``output`` only while nothing produces the name, so the menu cannot make
    a ``multiple-producers`` - and when something is missing a producer, this is the repair.
    ``local`` only for a name nothing declares at all, because ``local-conflict`` is exactly a
    local beside another declaration.
    """
    if name not in built.declarations:
        return SCOPES
    return ("input",) if built.producers.get(name) else ("output", "input")


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

    code: Literal["invalid", "not-found"]
    """``invalid``: the change cannot be made - a name that may not be used, a key the kind has
    not, a required key left out, a scope this name may not take. ``not-found``: the file
    declares no interface, or no declaration of that name."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found"], message: str) -> None:
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
    """
    here, entries = _interface(file, cache)
    sites = built.declarations.get(name)
    if not sites:
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    if any(site.path == here for site in sites):
        raise DeclarationRefusalError("invalid", f"this component already declares '{name}'")
    if scope not in scopes_for(built, name):
        raise DeclarationRefusalError("invalid", f"'{name}' may not be declared '{scope}' here")
    owner = (built.producers.get(name) or sites)[0]
    stated = read(owner.path, cache).value_at(owner.pointer)
    if not isinstance(stated, dict):
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    definition = {key: value for key, value in stated.items() if key not in CARRIED_BY_A_READER}
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
    here. A producing declaration is stamped with a fresh id, after its ``name``, where every
    stamped declaration of the examples carries one.
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
    if scope == "output":
        stated = {"name": stated.pop("name"), "id": new_id(), **stated}
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
