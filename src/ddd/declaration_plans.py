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

from pydantic import TypeAdapter, ValidationError

from ddd.analysis import _PRODUCER_KEYS
from ddd.editing import Operation
from ddd.identity import new_id
from ddd.lsp.navigation import Index, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.component import Scope
from ddd.models.objects import AnyDataObject, definition_keys
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

CARRIED_BY_A_READER: Final = frozenset(key for key, _, _ in _PRODUCER_KEYS)
"""What a reader does not copy from the producer it reads.

Derived from :data:`ddd.analysis._PRODUCER_KEYS` rather than restated beside it: that tuple is
where the project decides which keys only a producing declaration may state - ``init``,
``section``, ``raster``, ``id`` and ``extensions`` - and it names, per key, the check a
consumer stating one earns. Copying any of them into an ``input`` would write the finding this
verb exists to avoid, and reading the rule where it is decided means a sixth key added there
is dropped here the moment it exists. The same reasoning :func:`definition_keys` already uses
about the models, applied to the analysis.

Read through a name private to :mod:`ddd.analysis` because nothing outside it had needed the
set before. A copy is what let a reader carry ``section`` and ``raster`` into an ``input``,
which no measurement across the examples could show: every producer there stating one is
``local``, and a local is never declarable elsewhere.
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
    not, a required key left out, a scope this name may not take, a value the models themselves
    refuse. ``not-found``: the file declares no interface, or no declaration of that name."""

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

    That repair is what a :data:`PRODUCING_SCOPES` scope means here - ``scopes_for`` offers
    ``output`` exactly while nothing produces the name - so the declaration written is stamped,
    as :func:`declare_object` stamps one. Without it the verb would trade a ``missing-producer``
    for a ``missing-id``, which is not a repair.
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
    if scope in PRODUCING_SCOPES:
        definition = _stamped(name, definition)
    return _appended(here, entries, scope, definition)


_DEFINITION: Final[TypeAdapter[AnyDataObject]] = TypeAdapter(AnyDataObject)
"""Built once: compiling a discriminated union's schema is not free, and :func:`declare_object`
asks it once per call.

The same union :class:`~ddd.models.component.Declaration` validates a file's own ``definition``
against - asked here, before a definition is planned, rather than only once the file it was
written into is read back.
"""


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

    Stamped, the definition is asked of :data:`_DEFINITION` - a rule crossing two keys, a
    ``datatype`` wanting a ``conversion`` among them, is not something a key-by-key check above
    can see, and is refused in the model's own sentence rather than left for the file it is
    written into to refuse back.
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
    try:
        _DEFINITION.validate_python(stated)
    except ValidationError as error:
        raise DeclarationRefusalError("invalid", _model_problem(error)) from error
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


def _model_problem(error: ValidationError) -> str:
    """One sentence naming the first way the models refuse a definition the checks above did not.

    A rule crossing two keys - :func:`~ddd.models.objects.check_conversion_stated` and its
    neighbours - already raises one english sentence, which is what a page can act on; pydantic
    wraps it as ``"Value error, <that sentence>"``, so it is unwrapped here rather than shown
    wrapped. A key's value of the wrong shape - nothing above checks that ``datatype`` names a
    real one, or that ``volatile`` is a boolean - has no such sentence to unwrap, and is shown
    as pydantic states it.
    """
    first = error.errors(include_url=False)[0]
    cause = first.get("ctx", {}).get("error")
    return str(cause) if isinstance(cause, Exception) else first["msg"]


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
