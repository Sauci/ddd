"""Where a finding leads.

``ddd gui`` lists what the analysis reported and, until now, left the reader to work out where
to go: a sentence about a variable's declarations says nothing about which screen settles them.
This answers what the page can open for one finding - the variable whose declaration it is
about, the unit it names, the type its entry declares, the section it places data in, or the
component it is filed on - and answers nothing where the page has nothing to open, so that a
row can say why instead of leading somewhere useless.

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

UNIT_CHECKS: Final = frozenset({"unknown-unit", "duplicate-unit"})
"""The checks filed where a unit is written, whose finding leads to that unit's own panel.

``unknown-unit`` is filed where a definition states one; ``duplicate-unit`` at the vocabulary entry
that repeats it - measured, ``u.ddd.json#units[1]``. The panel lists both kinds of place, so both
lead there, and a units file stopped being somewhere the page had nothing to open.
"""

CONSTANT_CHECKS: Final = frozenset({"unknown-constant", "dimension-value"})
"""The checks filed where a shape names a constant, whose finding leads to that constant.

``unknown-constant`` names one no file declares, and the route carries the name anyway: the page
opens its add form with it filled in. ``dimension-value`` names one whose value is no array length,
and the value is the thing to change.
"""

SECTION_CHECKS: Final = frozenset({"unknown-section"})
"""The checks filed where a definition places its data, whose finding leads to that section.

``unknown-section`` names one no file declares, and the route carries the name anyway, exactly as
``unknown-constant`` does: the page opens the add form with it filled in, which is what a reader
who placed data in a section nobody declared has come to the tab to do.

The other two checks filed at that same key - ``section-access`` and ``section-alignment`` - are
deliberately not here. Each says something about the *variable* ("'X' is a measurement, which the
software writes, but '.calib' is read-only"), and the declaration's own panel is where its ``kind``
and its ``section`` are changed, so both keep the variable route :data:`WITHIN_DECLARATION` already
gives them.
"""

COMPONENT_KIND: Final = "component"
"""The one file kind the page has a screen for; rasters are what is left of milestone 6."""

WITHIN_TYPE: Final = re.compile(r"^(?:component\.)?types\[\d+\]")
"""The entry a pointer inside a type lies in: the type itself, one of its keys, or a member of
it, all of which the same panel shows - whether the type was declared in a types file
(``types[i]``) or inline by a component (``component.types[i]``)."""

WITHIN_CONSTANT: Final = re.compile(r"^(?:component\.)?constants\[\d+\]")
"""The entry a pointer inside a constant lies in - whether the constant was declared in a constants
file (``constants[i]``) or inline by a component (``component.constants[i]``), which
:mod:`ddd.loading` registers the same way."""

WITHIN_SECTION: Final = re.compile(r"^sections\[\d+\]")
"""The entry a pointer inside a section lies in: the entry itself, its name, its ``access``, its
``alignment`` or its ``description``, all of which the one panel shows.

No ``component.`` alternative, where :data:`WITHIN_CONSTANT` has one: a section is a project wide
vocabulary with no home inside a component, which :attr:`ddd.project_shared.SECTIONS.containers`
is the authority for - one container, ``sections``, where a constant has two.
"""

WITHIN_INIT: Final = re.compile(r"^(component\.interface\[\d+\])\.definition\.init\b")
"""A pointer inside a declaration's ``init``: the values grid is what opens on it.

Measured: ``init-invalid`` is filed at ``component.interface[0].definition.init`` - the whole
init, with no element index, because the check folds every value wrong in the same way into
one finding. So the route names the object and the grid opens; which cell is wrong is not
something the finding says.
"""


@dataclass(frozen=True, slots=True)
class Route:
    """Where a finding leads."""

    kind: str
    """``variable``, ``unit``, ``component``, ``type``, ``values``, ``constant`` or ``section``."""

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
        if isinstance(stated, dict):
            # A vocabulary entry is a spelling on its own or an object carrying a description,
            # and `ddd.lsp.units` writes back whichever the file already uses. Read whole, the
            # object is no string and `duplicate-unit` would lead nowhere.
            stated = stated.get("unit")
        return Route("unit", stated) if isinstance(stated, str) and stated else None
    if check in CONSTANT_CHECKS:
        # Before WITHIN_TYPE below, exactly as UNIT_CHECKS is and for the same reason: a structure
        # member's dimension is inside `types[i]`, so tried after it an unknown-constant on a
        # member would open the type rather than the constant the finding is about.
        named = read(path, cache).value_at(pointer)
        return Route("constant", named) if isinstance(named, str) and named else None
    if check in SECTION_CHECKS:
        # Beside CONSTANT_CHECKS above and read the same way - the value at the pointer is the
        # name - and, like it, ahead of the kind check below: the pointer is inside a component,
        # so WITHIN_DECLARATION would otherwise claim it and open the variable instead.
        #
        # Written as statements rather than the conditional expression the constant branch uses:
        # coverage.py counts no branch in one, so the arm that answers nothing would pass the
        # gate without a test ever asking for it.
        named = read(path, cache).value_at(pointer)
        if isinstance(named, str) and named:
            return Route("section", named)
        return None
    within_constant = WITHIN_CONSTANT.match(pointer)
    if within_constant is not None:
        # Before the kind check below, as WITHIN_TYPE is: a constants file's kind is `constants`,
        # and a component may declare a constant inline at `component.constants[i]`.
        name = read(path, cache).value_at(f"{within_constant.group()}.name")
        return Route("constant", name) if isinstance(name, str) else None
    within_section = WITHIN_SECTION.match(pointer)
    if within_section is not None:
        # Before the kind check below, as WITHIN_CONSTANT is, and for the sharper version of the
        # same reason: a sections file's kind is `sections`, and a section has no second home
        # inside a component, so every pointer this matches comes from a file the gate stops.
        #
        # The name is read from the entry's own `section` key, which is what SECTIONS calls its
        # name - a constant's is `name` - so the two branches differ in that one word and in
        # nothing else.
        name = read(path, cache).value_at(f"{within_section.group()}.section")
        if isinstance(name, str):
            return Route("section", name)
        return None
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
    within_init = WITHIN_INIT.match(pointer)
    if within_init is not None:
        # Tried ahead of WITHIN_DECLARATION below, which a pointer inside an ``init`` also
        # matches, being broader: caught here first or the values grid would never open.
        name = read(path, cache).value_at(f"{within_init.group(1)}.definition.name")
        return Route("values", name) if isinstance(name, str) else None
    within = WITHIN_DECLARATION.match(pointer)
    if within is None:
        # Somewhere else in a component: its own page is what there is to open.
        return Route("component", None) if pointer else None
    declaration = within.group()
    name = read(path, cache).value_at(f"{declaration}.definition.name")
    # The pointer is where the analysis found the declaration; the file may have moved on since.
    return Route("variable", name) if isinstance(name, str) else None
