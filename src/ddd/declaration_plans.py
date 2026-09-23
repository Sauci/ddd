"""What a component may add to its interface, and what each change of one takes.

Transport-neutral, like :mod:`ddd.type_plans` beside it. Nothing here writes a file: a verb
answers a plan of edit-engine operations, and ``POST /api/edit`` is what writes it, so one
engine makes every change ``ddd gui`` makes and part 5's stack puts any of them back.

Nothing here formats json either. ``ddd.editing.insertion`` lays a value out in the layout of
the place it goes - a key per line, a container of literals on one line - which is exactly how
the description files spell a declaration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.models.objects import definition_keys
from ddd.variable_keys import KEY_ORDER, KeyOffer, offer_for

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
                _component_of(produced[0].path, cache)
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


def _statable(kind: str) -> frozenset[str]:
    """What a definition sent here may state: what the form can offer, and nothing else.

    ``definition_keys`` accepts more - ``id``, ``init``, ``a2l``, ``extensions``, ``raster``
    and ``section`` among them. The form offers none of those: ``id`` is this module's to mint,
    and the rest belong to whoever writes the file by hand.
    """
    accepted, _ = definition_keys(kind)
    return frozenset({"name", "kind", "description"}) | (accepted & frozenset(KEY_ORDER))


def _component_of(path: Path, cache: dict[Path, Document]) -> str:
    return str(read(path, cache).value_at("component.name") or "")
