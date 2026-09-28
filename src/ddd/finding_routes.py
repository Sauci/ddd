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

PLACEMENT_KEY: Final = re.compile(r"^component\.interface\[\d+\]\.definition\.section$")
"""A definition's own ``section`` key: the one shape outside a sections file that names a section,
and the second half of spec 4.6's section route - "a pointer a definition's ``section`` key
matches".

**Pointer shaped, where a unit's and a constant's routes are check-id shaped**
(:data:`UNIT_CHECKS`, :data:`CONSTANT_CHECKS`), and the asymmetry is not an accident. A check id
set exists to *override* the pointer, and is needed wherever the pointer's shape belongs to
something else as well: a constant is named at a declaration's ``dimensions[i]`` and at its axis
``size``, pointers that ``limits-out-of-range`` and the rest of the declaration's checks sit
inside, so only the id can say which findings there are about the constant rather than about the
variable. Nothing else is written at ``definition.section``, so the pointer carries the route and
a placement check added to the analysis tomorrow leads here without this module being told - which
is the whole benefit, and the reason this is not simply a list of three ids.

What the pointer does not settle on its own is *what the finding is about*, and that is
:data:`ABOUT_THE_DECLARATION`'s business. Three of the four checks filed here are about the
placement - ``unknown-section``, ``section-access``, ``section-alignment``, all from one ``where``
in :meth:`ddd.analysis.Analysis._check_sections` - and the section's panel is the right screen for
each: it holds the ``access`` and the ``alignment`` two of them name, and it lists every definition
placing data there, so the variable a finding is *also* about is one click away with the rest of
the section's tenants visible beside it. That is what a reader deciding between "change this
variable" and "change this section" has to see.
"""

ABOUT_THE_DECLARATION: Final = frozenset({"consumer-storage"})
"""The checks filed at a definition's ``section`` key that are not about the section, and so are
left to the declaration's own route.

One, today. ``consumer-storage`` comes from :data:`ddd.analysis.PRODUCER_KEYS` rather than from
the section checks, and it says a *consumer* stated a key only the producing component may state.
The section it names is innocent and may well be the right one; what is wrong is the declaration
having the key at all. The check's own filing site says as much - "reported where the claim is
written rather than where it is overruled: the producer may be in a file this author has never
opened, **and the fix is here**" - so routing it to the section would send the reader away from
the place the analysis chose on purpose.

Its sibling agrees. ``PRODUCER_KEYS`` gives this one check five keys, and the copy filed at
``definition.init`` is already claimed by :data:`WITHIN_INIT`, which opens the values grid - the
variable's own screen. So ``consumer-storage`` leads to the variable today by two routes, and a
third destination for the ``section`` key would break a pattern that is currently whole.

An exclusion with a reason, then, not a carve-out: the pointer says *where* the finding sits, this
says *whose* it is.
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
    if check not in ABOUT_THE_DECLARATION and PLACEMENT_KEY.match(pointer) is not None:
        # The value at the pointer is the name, as it is for a unit and a constant above. What
        # differs is that the id is asked only whether the finding is the *declaration's* -
        # `consumer-storage` alone - rather than which of the section's checks it is: the pointer
        # carries the route, for the reason PLACEMENT_KEY gives, and a check the id set does not
        # name falls through to the declaration's own route below.
        #
        # Ahead of WITHIN_DECLARATION, which matches this pointer too, being broader: caught
        # there first, every finding about where a variable's data sits would open the variable.
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
