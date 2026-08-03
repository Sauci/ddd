"""Jumping between the places a project says the same name.

This is the part of an editor that a json schema cannot approach at all. A schema sees one
file; the interesting jumps all leave it. From a component's ``input`` to the ``output`` that
produces it is a jump into a file the author may not know the name of, and it is the question
they actually have: who writes this, and what did they say it was?

Nothing is analysed here. The loader has already read every file of the project, and every
loaded object knows where it came from - ``LoadedComponent.declaration_location`` gives the
pointer of a declaration, ``LoadedType.location`` that of a structure. All that is missing is
an index from a name to those places, which is what this module builds.

What can be jumped from, and to:

* anywhere inside a declaration goes to the declaration that **produces** the object it is
  about - there is exactly one in a consistent project, and where there is not, the ambiguity
  is worth seeing. A reference key (``axis``, ``x_axis``, ``y_axis``, ``input``) wins over the
  declaration holding it, because that is the object under the pointer;
* the same, asked as "find references", goes to **every** declaration of it;
* a structure name goes to where the structure is declared, and its references to every
  member that nests it;
* an ``includes`` entry and a project's ``naming`` go to the file they name.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from ddd.build_info import BuildInfo
from ddd.diagnostics import DiagnosticBag
from ddd.loading import Workspace, load_workspace
from ddd.lsp.ranges import Document, read
from ddd.models import (
    C_IDENTIFIER_PATTERN,
    IDENTIFIER_MAX_LENGTH,
    EnumConversion,
    is_reserved_identifier,
)

VARIABLE_KEYS: Final = frozenset({"name", "axis", "x_axis", "y_axis", "input"})
"""Keys of a declaration whose value is the name of a data object.

``name`` is in the list on purpose: from the name of an ``input``, the jump the author wants
is to whoever writes it, which is exactly the jump a reference key makes.
"""

_DECLARATION: Final = "component.declarations["
_WITHIN_DECLARATION: Final = re.compile(r"^component\.declarations\[\d+\]")
"""Anywhere inside one declaration, however deep - the prefix names the declaration."""
_TYPES: Final = "types["
_INCLUDES: Final = "project.includes["
_NAMING: Final = "project.naming"


@dataclass(frozen=True, slots=True)
class Site:
    """Somewhere in the project an editor can be sent."""

    path: Path
    pointer: str


@dataclass(frozen=True, slots=True)
class Index:
    """Where a project writes down each of the names it uses."""

    producers: dict[str, list[Site]] = field(default_factory=dict)
    """Name -> the declarations that write it. More than one is an inconsistent project."""

    declarations: dict[str, list[Site]] = field(default_factory=dict)
    """Name -> every declaration of it, whichever way round."""

    types: dict[str, Site] = field(default_factory=dict)
    """Structure name -> where it is declared."""

    type_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Structure name -> every member that nests it."""

    occupied: dict[str, str] = field(default_factory=dict)
    """C identifier -> what already spends it, for identifiers that are not variables.

    Enumerators and enum names, both of which the types header emits and c keeps in the same
    file scope namespace as the variables. The value is the phrase that goes in the refusal,
    because "already taken" without saying by what leaves the author guessing.
    """

    mentions: dict[str, list[Site]] = field(default_factory=dict)
    """Name -> every place the name itself is written.

    Not the same as ``declarations``, which points at the definition objects: these point at
    the strings, and include the ``axis`` of a curve naming this object as well as its own
    ``name``. Renaming has to rewrite all of them or it leaves the project referring to
    something that no longer exists.
    """


def index(workspace: Workspace) -> Index:
    """Read the positions out of an already loaded project."""
    built = Index()
    for loaded in workspace.components:
        for position, declaration in enumerate(loaded.component.declarations):
            location = loaded.declaration_location(position, "definition")
            site = Site(location.path, location.pointer)
            name = declaration.definition.name
            built.declarations.setdefault(name, []).append(site)
            if declaration.scope.is_producer:
                built.producers.setdefault(name, []).append(site)
            built.mentions.setdefault(name, []).append(
                Site(location.path, f"{location.pointer}.name")
            )
            for key, target in declaration.definition.references.items():
                where = loaded.declaration_location(position, f"definition.{key}")
                built.mentions.setdefault(target, []).append(Site(where.path, where.pointer))
            conversion = declaration.definition.conversion
            if isinstance(conversion, EnumConversion):
                built.occupied[conversion.name] = f"the name of enum '{conversion.name}'"
                for enumerator in conversion.enumerators:
                    built.occupied[enumerator.name] = f"an enumerator of enum '{conversion.name}'"
    for entry in workspace.types:
        built.types[entry.name] = Site(entry.path, entry.location().pointer)
        for position, member in enumerate(entry.structure.members):
            if member.type is not None:
                where = entry.location(f"members[{position}].type")
                built.type_uses.setdefault(member.type, []).append(Site(where.path, where.pointer))
    return built


def workspaces(builds: Sequence[BuildInfo], document: Path) -> list[Workspace]:
    """The projects that contain a document, or the document read on its own.

    Loaded per request rather than kept: a jump is something a person asks for, so the cost
    lands on a keypress somebody chose to make, and never on a keystroke they did not.
    """
    found = []
    for info in builds:
        workspace = load_workspace(Path(info.project), DiagnosticBag())
        if workspace is not None and document in workspace.sources():
            found.append(workspace)
    if not found:
        alone = load_workspace(document, DiagnosticBag())
        if alone is not None:
            found.append(alone)
    return found


def variable_at(document: Document, pointer: str) -> str | None:
    """The data object the cursor names outright, if it names one.

    The narrow half of :func:`subject_at`, which is the rule every question actually uses.
    Separate because a reference key has to win over the declaration holding it, and that
    precedence is easier to read as two steps than as one condition.
    """
    value = document.value_at(pointer)
    if not isinstance(value, str):
        return None
    if pointer.startswith(_DECLARATION) and _key(pointer) in VARIABLE_KEYS:
        return value
    return None


def subject_at(document: Document, pointer: str) -> str | None:
    """The object a question asked at this position is about.

    Wider than :func:`variable_at` on purpose, and used by every question an editor asks about
    a position - what is this, where is it written, where else is it used. A declaration is
    *about* one object from its opening brace to its closing one, so resting the pointer on the
    datatype rather than on the name is not a different question, and hunting for the one key
    that answers is not a game worth playing.

    This was narrow for navigation at first, on the reasoning that jumping to another file from
    a datatype would surprise somebody. The opposite turned out to be true: what surprises is a
    hover that says "written by Controller" from a position where "go to definition" then finds
    nothing.

    A reference still wins over the declaration containing it: on the ``axis`` of a curve, the
    thing under the pointer is the axis, and that is what a reader is asking about.
    """
    named = variable_at(document, pointer)
    if named is not None:
        return named
    within = _WITHIN_DECLARATION.match(pointer)
    if within is None:
        return None
    name = document.value_at(f"{within.group()}.definition.name")
    return name if isinstance(name, str) else None


def definition(built: Index, document: Document, path: Path, pointer: str) -> list[Site]:
    """Where the object under the cursor is written.

    The two path-shaped answers need a string under the cursor; the object one does not,
    because a declaration is about its object wherever inside it the pointer rests - including
    on a number, or on the braces of the declaration itself.
    """
    value = document.value_at(pointer)
    if isinstance(value, str):
        if pointer.startswith(_INCLUDES) or pointer == _NAMING:
            return _files(path.parent, value)
        if pointer.startswith(_TYPES):
            found = built.types.get(value)
            return [found] if found is not None else []
    name = subject_at(document, pointer)
    if name is not None:
        return list(built.producers.get(name, ()))
    return []


def references(built: Index, document: Document, pointer: str) -> list[Site]:
    """Everywhere the name under the cursor is used.

    The declaration is always among them. The protocol lets a client ask for the references
    without it, but here the distinction has little to say: every declaration of a variable is
    a use of it, and which one is "the" declaration is the question the jump above answers.
    """
    value = document.value_at(pointer)
    if isinstance(value, str) and pointer.startswith(_TYPES):
        declared = built.types.get(value)
        found = [declared] if declared is not None else []
        return found + list(built.type_uses.get(value, ()))
    name = subject_at(document, pointer)
    if name is not None:
        return list(built.declarations.get(name, ()))
    return []


def rename_problem(built: Index, name: str) -> str | None:
    """Why the project may not be renamed to ``name``, or nothing if it may.

    Checked before a single file is touched. A rename writes into every component that
    mentions the object, so a name that turns out to be unusable would leave a project broken
    across several files at once - and the c compiler, which is where an unusable name is
    otherwise noticed, only sees it a build later.
    """
    if not re.fullmatch(C_IDENTIFIER_PATTERN, name) or len(name) > IDENTIFIER_MAX_LENGTH:
        return f"'{name}' is not a usable c identifier"
    if is_reserved_identifier(name):
        return f"'{name}' is reserved by c or by a header DDD generates"
    if name in built.declarations:
        # Silently merging two objects into one is the worst outcome available here: it
        # compiles, it links, and two components share storage neither of them meant to.
        return f"'{name}' is already declared by this project"
    occupant = built.occupied.get(name)
    if occupant is not None:
        # A variable is not the only thing the generated headers name. Letting the rename
        # through would report the collision as a finding on the next check, which is the
        # right finding in the wrong place: by then it is spread over every file the rename
        # touched, and the author has to undo a rewrite rather than pick another name.
        return f"'{name}' is {occupant}, which shares c's namespace with the variables"
    return None


def rename_edits(
    built: Index, document: Document, pointer: str, name: str, cache: dict[Path, Document]
) -> dict[str, list[dict[str, Any]]]:
    """Every edit that renaming the object under the cursor takes, keyed by file.

    Only the characters between the quotes are replaced, so whatever else is on the line -
    the key, the spacing a project formats its files with - is left exactly as it was.
    """
    subject = variable_at(document, pointer)
    changes: dict[str, list[dict[str, Any]]] = {}
    for site in built.mentions.get(subject or "", ()):
        span = read(site.path, cache).text_range_of(site.pointer)
        if span is not None:
            changes.setdefault(site.path.as_uri(), []).append({"range": span, "newText": name})
    return changes


def locations(sites: Iterable[Site], cache: dict[Path, Document]) -> list[dict[str, Any]]:
    """The sites as the protocol wants them, each one once and in a stable order."""
    unique = {(site.path, site.pointer): site for site in sites}
    return [
        {"uri": site.path.as_uri(), "range": read(site.path, cache).range_of(site.pointer)}
        for site in sorted(unique.values(), key=lambda site: (str(site.path), site.pointer))
    ]


def _files(base: Path, pattern: str) -> list[Site]:
    """The files a path in a description names, relative to the file that names it.

    Expanded rather than resolved, because an ``includes`` entry is a pattern:
    ``components/*.ddd.json`` is the ordinary way to write one, and a jump that worked only
    for the entries somebody had spelled out in full would miss the common case. A plain path
    is a pattern that matches one file, so the two need no telling apart.
    """
    try:
        matches = sorted(base.glob(pattern))
    except (ValueError, NotImplementedError):
        # An absolute pattern, or an empty one. Both are refusals from pathlib rather than
        # answers, and NotImplementedError is not a ValueError, so both have to be named: a
        # description file is somebody's input, and an unrelatable path in one must not take
        # the editor's server down with it. The loader will have something to say about the
        # file; the jump simply has nowhere to go.
        return []
    return [Site(found.resolve(), "") for found in matches if found.is_file()]


def _key(pointer: str) -> str:
    """The last named segment, which is the key whose value the cursor is on."""
    return pointer.rsplit(".", 1)[-1]
