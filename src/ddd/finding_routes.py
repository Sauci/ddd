"""Where a finding leads.

``ddd gui`` lists what the analysis reported and, until now, left the reader to work out where
to go: a sentence about a variable's declarations says nothing about which screen settles them.
This answers what the page can open for one finding - the variable whose declaration it is
about, the unit it names, the type its entry declares, or the component it is filed on - and
answers nothing where the page has nothing to open, so that a row can say why instead of
leading somewhere useless.

Pure: no GUI and no HTTP. :mod:`ddd.gui.api` turns a route into the shape ``GET /api/state``
answers, and nothing else reads them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.lsp.edits import WITHIN_DECLARATION
from ddd.lsp.ranges import Document, read

UNIT_CHECKS: Final = frozenset({"unknown-unit"})
"""The checks filed where a unit is stated, whose finding leads to that unit's own panel."""

COMPONENT_KIND: Final = "component"
"""The one file kind the page has a screen for; the rest are milestone 6's."""

TYPES_KIND: Final = "types"
"""The second file kind the page has a screen for, as of part 6."""

WITHIN_TYPE: Final = re.compile(r"^(?:component\.)?types\[\d+\]")
"""The entry a pointer inside a type lies in: the type itself, one of its keys, or a member of
it, all of which the same panel shows - whether the type was declared in a types file
(``types[i]``) or inline by a component (``component.types[i]``)."""


@dataclass(frozen=True, slots=True)
class Route:
    """Where a finding leads."""

    kind: str
    """``variable``, ``unit``, ``component`` or ``type``."""

    name: str | None
    """The variable's name, the unit's spelling or the type's name; ``None`` for a component,
    which the finding's own file already names."""


def route_of(
    check: str,
    path: Path,
    pointer: str,
    kind: str,
    loaded: bool,
    cache: dict[Path, Document],
) -> Route | None:
    """What the page can open for a finding filed on ``path`` at ``pointer``.

    ``kind`` and ``loaded`` are the file's own, as the analysis recorded them. Nothing is
    answered for a file that did not load - the pointer describes a document nobody parsed -
    and nothing for a finding that names no place at all, which is how a check about the
    project rather than a line in a file reports itself.
    """
    if not loaded:
        return None
    if check in UNIT_CHECKS:
        # A unit is stated in a component, in a scalar type and in a structure member, and part
        # 2's panel lists all three: the one route that does not care which file it was on.
        stated = read(path, cache).value_at(pointer)
        return Route("unit", stated) if isinstance(stated, str) and stated else None
    within_type = WITHIN_TYPE.match(pointer)
    if within_type is not None:
        # A pointer anywhere inside an entry - its own keys, a member's, an enumerator's - is
        # about the type that entry declares, which is what the panel opens on. Tried ahead of
        # the kind check below and the component branch it guards: a component may declare a
        # type inline, at `component.types[i]`, and that pointer cannot collide with one of its
        # own declarations, which always starts `component.interface[`.
        name = read(path, cache).value_at(f"{within_type.group()}.name")
        return Route("type", name) if isinstance(name, str) else None
    if kind != COMPONENT_KIND:
        return None
    within = WITHIN_DECLARATION.match(pointer)
    if within is None:
        # Somewhere else in a component: its own page is what there is to open.
        return Route("component", None) if pointer else None
    declaration = within.group()
    name = read(path, cache).value_at(f"{declaration}.definition.name")
    # The pointer is where the analysis found the declaration; the file may have moved on since.
    return Route("variable", name) if isinstance(name, str) else None
