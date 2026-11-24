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
* an ``includes`` entry goes to the file it names.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from ddd.build_info import BuildInfo
from ddd.diagnostics import DiagnosticBag, Location, Severity
from ddd.loading import Workspace, included_files, load_workspace
from ddd.lsp.ranges import Document, read
from ddd.models import (
    C_IDENTIFIER_PATTERN,
    IDENTIFIER_MAX_LENGTH,
    Conversion,
    Datatype,
    EnumConversion,
    ScalarType,
    is_reserved_identifier,
    spelled_dimensions,
)
from ddd.models.common import RASTER_NAME_LENGTH, RASTER_NAME_PATTERN, SECTION_NAME_PATTERN
from ddd.plugins import PluginError

_WITHIN_DECLARATION: Final = re.compile(r"^component\.interface\[\d+\]")
"""Anywhere inside one declaration, however deep - the prefix names the declaration."""
_TYPE_ENTRIES: Final = re.compile(r"^(?:component\.)?types\[")
"""Inside a type entry, in either of its homes: a types file, or a component's own list."""
_TYPE_ENTRY: Final = re.compile(r"^(?:component\.)?types\[\d+\]")
"""One type entry, the prefix naming it; what a question about the whole entry starts from."""
_CONSTANT_ENTRIES: Final = re.compile(r"^(?:component\.)?constants\[")
"""Inside a constant entry, in a constants file or in a component's own list."""
_INCLUDES: Final = "project.includes["

_DEFINITION_KEY: Final = re.compile(
    r"^component\.interface\[\d+\]\.definition\.(?:name|axis|x_axis|y_axis|input)$"
)
"""One of the keys naming a data object, *directly* under a definition.

``name`` is among them on purpose: from the name of an ``input``, the jump the author wants is
to whoever writes it, which is exactly the jump a reference key makes.

Anchored rather than matched on the last segment of the pointer, which is how F2 on an enum's
name or on one of its enumerators - ``definition.conversion.name``,
``definition.conversion.enumerators[0].name`` - used to pass as the object's own name. So did
any key an ``extensions`` block happens to spell that way, and a plugin may spell anything.
"""

_MEMBER: Final = r"(?:component\.)?types\[\d+\]\.members\[\d+\]"
_DIMENSION_KEY: Final = re.compile(
    rf"^(?:component\.interface\[\d+\]\.definition\.(?:dimensions\[\d+\]|size)"
    rf"|{_MEMBER}\.dimensions\[\d+\])$"
)
"""Where a shape is written, and therefore where a constant name may be spelled."""

_TYPENAME_KEY: Final = re.compile(
    rf"^(?:component\.interface\[\d+\]\.definition|{_MEMBER})\.typename$"
)
"""The two homes of a ``typename``: a declaration, and a structure member."""

_TYPE_NAME: Final = re.compile(r"^(?:component\.)?types\[\d+\]\.name$")
_CONSTANT_NAME: Final = re.compile(r"^(?:component\.)?constants\[\d+\]\.name$")

_SECTION_NAME: Final = re.compile(r"^sections\[\d+\]\.section$")
_SECTION_KEY: Final = re.compile(r"^component\.interface\[\d+\]\.definition\.section$")
"""The one place a definition places its data: a section is a project wide vocabulary, with
no home inside a component the way a type or a constant may have one."""

_RASTER_NAME: Final = re.compile(r"^rasters\[\d+\]\.raster$")
_RASTER_KEY: Final = re.compile(
    r"^(?:component\.raster|component\.interface\[\d+\]\.definition\.raster)$"
)
"""Where a raster is spelled: a definition's own, or the component's default for everything
it produces - the one use written outside any definition at all."""

_UNIT_KEY: Final = re.compile(
    rf"^(?:(?:component\.interface\[\d+\]\.definition|(?:component\.)?types\[\d+\]|{_MEMBER}"
    rf"|units\[\d+\])\.unit|units\[\d+\])$"
)
"""Where a unit is spelled: a declaration's ``unit``; a scalar type's or a structure member's, in
a types file or in a component's own list; and an entry of a units file - the spelling on its
own, or the ``unit`` of an object. The places ``unknown-unit`` checks, and the vocabulary it
checks them against."""

_BASE_DATATYPES: Final = frozenset(member.value for member in Datatype)
"""The keys whose string value names a constant: one dimension entry, or an axis size."""

_WORD: Final = re.compile(r"[\w$\u0300-\u036f\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]+")
"""One word of a condition: a run of the characters an identifier holds there, as long as it goes -
a letter or a digit of any script, the underscore, the dollar sign gcc and clang take in an
identifier, and the combining marks C11's Annex D allows in one after its first character, from
U+0300 to U+036F, U+1DC0 to U+1DFF, U+20D0 to U+20FF and U+FE20 to U+FE2F. ``CELLS`` is a word of
``CELLS > 2`` and of ``defined(CELLS)``, and no word of ``MAX_CELLS``, ``CELLS2``, ``CELLS$1`` or
``CELLS`` and a combining accent, each of which is a longer identifier holding it."""

_JSON_CHARACTER: Final = re.compile(
    r"\\u[dD][89abAB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\.|[^\\]"
)
"""One character of a json string as it is written between the quotes: an escape - the two of a
surrogate pair, which json writes for a character beyond the basic plane, four hex digits, or the
one character after the backslash - or the character itself. The pair is tried first: read half
by half, a letter beyond the basic plane was two characters no identifier holds, and ``CELLS``
after one read as a word."""

LOAD_CHECKS: Final = frozenset({"file-not-found", "json-syntax", "file-kind", "schema"})
"""The checks whose error on a file means that file did not load.

One notion for both clients: ``ddd gui`` shows such a file as not loaded, and a plan of
:mod:`ddd.lsp.units` made in the language server refuses to reach round one.
"""

_UNREAD_AT_THE_ENTRY: Final = frozenset({"file-not-found", "json-syntax"})
"""The checks the loader reports at the include entry naming a file it could not read - one that
is not there, or holds no text - rather than in the file, which has no place to point into."""

_INCLUDE_ENTRY: Final = re.compile(r"project\.includes\[\d+\]")
"""Where it reports them: one entry of a project description's ``includes``."""


@dataclass(frozen=True, slots=True)
class Site:
    """Somewhere in the project an editor can be sent."""

    path: Path
    pointer: str


@dataclass(frozen=True, slots=True)
class UnitSite:
    """One place a unit is stated: its string, and what states it."""

    site: Site
    """The unit's string itself: ``….definition.unit``, a scalar type's ``unit``, a member's."""

    kind: Literal["variable", "type", "member"]
    name: str
    """The variable's name, the type's, or ``Type.member`` for a structure member."""


@dataclass(frozen=True, slots=True)
class Index:
    """Where a project writes down each of the names it uses."""

    producers: dict[str, list[Site]] = field(default_factory=dict)
    """Name -> the declarations that write it. More than one is an inconsistent project."""

    declarations: dict[str, list[Site]] = field(default_factory=dict)
    """Name -> every declaration of it, whichever way round."""

    types: dict[str, Site] = field(default_factory=dict)
    """Type name -> where it is declared: a structure, a scalar type or an external type."""

    externals: dict[str, str] = field(default_factory=dict)
    """External type name -> the header that defines it, spelled as its entry spells it: the types
    whose name is that header's rather than the project's, which no rename of a description may
    change (:func:`named_by_a_header`)."""

    type_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Structure name -> every member that nests it."""

    constants: dict[str, Site] = field(default_factory=dict)
    """Constant name -> where the constants file declares it."""

    constant_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Constant name -> every dimension entry and axis size that spells it."""

    condition_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Constant name -> every declaration whose ``condition`` spells it as a word (:data:`_WORD`),
    at that ``condition``, in the order the project lists its components.

    Apart from :attr:`constant_uses` on purpose. A shape's string is the constant's name and
    nothing else, so a rename writes the new name over the whole of it, and a panel reads the
    variable it shapes; a condition is an expression, of which a rename rewrites the word alone
    (:func:`word_spans`). A word is a constant only where the project declares one of that name -
    the shipped templates define each constant as a macro in the types header, which ``#if``
    reads - and any other word of a condition is a macro the build defines, or none.
    """

    sections: dict[str, Site] = field(default_factory=dict)
    """Section name -> where the sections file declares it."""

    section_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Section name -> every definition placing data in it."""

    rasters: dict[str, Site] = field(default_factory=dict)
    """Raster name -> where the rasters file declares it."""

    raster_uses: dict[str, list[Site]] = field(default_factory=dict)
    """Raster name -> every definition naming it, and every component naming it as the
    default raster for what it produces."""

    kinds: dict[str, str] = field(default_factory=dict)
    """Name -> the kind its first declaration states, in the order the project lists its
    components.

    What a chooser naming an object reads: the ``axis`` of a curve is one of the project's
    axes, the ``input`` of an axis one of its measurements. One kind per name rather than one
    per declaration, because declarations disagreeing about their kind are two objects under
    one name - which ``definition-mismatch`` reports and no chooser can settle, ``kind`` being
    the one shared key an edit may not carry from one declaration to another (see
    :data:`ddd.lsp.edits.PROPAGATED_KEYS`).
    """

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

    units: dict[str, list[UnitSite]] = field(default_factory=dict)
    """Unit -> every place it is stated: a declaration's ``unit``, a scalar type's and a
    structure member's, which are the places ``unknown-unit`` checks - the declarations first,
    in the order the project lists its components, then the types by name.

    Keyed by the exact spelling, so ``rpm`` and ``RPM`` are two units, which is the drift a
    rename exists to merge. A declaration repeated in one component is here each time, though
    the check reads it once: a rename that left the repeat alone would leave the old spelling
    in the file. The empty unit is not here - a dimensionless value states no unit rather than a
    spelling of one.
    """

    vocabulary: dict[str, list[Site]] = field(default_factory=dict)
    """Unit -> every entry of the units files listing it, at ``units[i]``, whether the entry is
    the spelling on its own or an object naming it. Two entries are a unit listed twice."""

    scopes: dict[Site, str] = field(default_factory=dict)
    """Declaration -> the scope it states, ``input``, ``output`` or ``local``, as the analysis
    loaded it: keyed by its ``definition``, as :attr:`declarations` records it.

    With :attr:`components`, what a unit's panel names a variable by where its file still reads
    as the analysis read it, rather than parse every file stating the unit again for two strings
    of each."""

    components: dict[Path, str] = field(default_factory=dict)
    """Component file -> the name of the component it declares, as the analysis loaded it."""


def index(workspace: Workspace) -> Index:
    """Read the positions out of an already loaded project."""
    built = Index()
    conditions: list[tuple[Site, str]] = []
    for loaded in workspace.components:
        built.components[loaded.path] = loaded.component.name
        # A plain `None` check: a component need not name a default raster, and the model has
        # already validated this field to `str | None` - there is no drifted third shape here
        # for an `isinstance` to be guarding against.
        if loaded.component.raster is not None:
            where = loaded.location("component.raster")
            built.raster_uses.setdefault(loaded.component.raster, []).append(
                Site(where.path, where.pointer)
            )
        for position, declaration in enumerate(loaded.component.interface):
            location = loaded.declaration_location(position, "definition")
            site = Site(location.path, location.pointer)
            name = declaration.definition.name
            built.declarations.setdefault(name, []).append(site)
            built.scopes[site] = declaration.scope.value
            built.kinds.setdefault(name, declaration.definition.kind.value)
            if declaration.scope.is_producer:
                built.producers.setdefault(name, []).append(site)
            built.mentions.setdefault(name, []).append(
                Site(location.path, f"{location.pointer}.name")
            )
            for key, target in declaration.definition.references.items():
                where = loaded.declaration_location(position, f"definition.{key}")
                built.mentions.setdefault(target, []).append(Site(where.path, where.pointer))
            for named_size, suffix in spelled_dimensions(declaration.definition):
                where = loaded.declaration_location(position, f"definition.{suffix}")
                built.constant_uses.setdefault(named_size, []).append(
                    Site(where.path, where.pointer)
                )
            named = declaration.definition.declared_type
            if named is not None:
                where = loaded.declaration_location(position, "definition.typename")
                built.type_uses.setdefault(named, []).append(Site(where.path, where.pointer))
            # The same plain `None` check: a definition need not place its data in a section,
            # nor state its own raster when the component's default already does.
            if declaration.definition.section is not None:
                where = loaded.declaration_location(position, "definition.section")
                built.section_uses.setdefault(declaration.definition.section, []).append(
                    Site(where.path, where.pointer)
                )
            if declaration.definition.raster is not None:
                where = loaded.declaration_location(position, "definition.raster")
                built.raster_uses.setdefault(declaration.definition.raster, []).append(
                    Site(where.path, where.pointer)
                )
            if declaration.condition is not None:
                where = loaded.declaration_location(position, "condition")
                conditions.append((Site(where.path, where.pointer), declaration.condition))
            _occupy(built, declaration.definition.conversion)
            _unit_stated(
                built,
                declaration.definition.unit,
                loaded.declaration_location(position, "definition.unit"),
                "variable",
                name,
            )
    for entry in workspace.types:
        built.types[entry.name] = Site(entry.path, entry.location().pointer)
        built.occupied[entry.name] = f"the name of the type '{entry.name}'"
        if entry.external is not None:
            built.externals[entry.name] = entry.external.header
        declared = entry.declared
        if isinstance(declared, ScalarType):
            _occupy(built, declared.conversion)
            _unit_stated(built, declared.unit, entry.location("unit"), "type", entry.name)
        structure = entry.structure
        if structure is None:
            continue
        for position, member in enumerate(structure.members):
            _occupy(built, member.conversion)
            _unit_stated(
                built,
                member.unit,
                entry.location(f"members[{position}].unit"),
                "member",
                f"{entry.name}.{member.name}",
            )
            # A member naming a base datatype names no type; the two keys keep them apart.
            if member.typename is not None:
                where = entry.location(f"members[{position}].typename")
                built.type_uses.setdefault(member.typename, []).append(
                    Site(where.path, where.pointer)
                )
            for index, dimension in enumerate(member.dimensions):
                if isinstance(dimension, str):
                    where = entry.location(f"members[{position}].dimensions[{index}]")
                    built.constant_uses.setdefault(dimension, []).append(
                        Site(where.path, where.pointer)
                    )
    for constant in workspace.constants:
        built.constants[constant.name] = Site(constant.path, constant.location().pointer)
        built.occupied[constant.name] = f"the name of the declared constant '{constant.name}'"
    # Once every constant is known, since a word of a condition is a constant's only where one is
    # declared; each word once a condition, which spelling it twice is still one use of.
    for site, condition in conditions:
        for word in dict.fromkeys(_WORD.findall(condition)):
            if word in built.constants:
                built.condition_uses.setdefault(word, []).append(site)
    # Neither a section nor a raster joins `occupied`. A constant's name reaches generated code
    # as a c identifier, so a collision there is two objects sharing storage; a section's name
    # is a linker string and a raster's an a2l short name, and neither is ever spelled into the
    # generated header, so neither shares that namespace.
    for section in workspace.sections:
        built.sections[section.section] = Site(section.path, section.location().pointer)
    for raster in workspace.rasters:
        built.rasters[raster.raster] = Site(raster.path, raster.location().pointer)
    for listed in workspace.unit_entries:
        where = listed.location()
        built.vocabulary.setdefault(listed.unit, []).append(Site(where.path, where.pointer))
    return built


def _unit_stated(
    built: Index,
    unit: str,
    where: Location,
    kind: Literal["variable", "type", "member"],
    name: str,
) -> None:
    """Note one place a unit is stated, unless it states the empty unit, which is no unit:
    ``unknown-unit`` never checks it, so a rename or an adoption has nothing to do with it."""
    if unit:
        built.units.setdefault(unit, []).append(
            UnitSite(Site(where.path, where.pointer), kind, name)
        )


def _occupy(built: Index, conversion: Conversion | None) -> None:
    """Note what an enum spends of c's namespace, wherever the enum was written.

    A declaration's own conversion, a scalar type's, and a structure member's: all three end
    up as one ``enum`` in the shared types header, so all three take their name and every one
    of their enumerators out of the namespace the variables share. Only the first was noted,
    so a rename onto ``MODE_IDLE`` - an enumerator of a type file's ``SensorMode_t`` - was
    accepted, every file rewritten, and the collision reported by the next check.
    """
    if not isinstance(conversion, EnumConversion):
        return
    built.occupied[conversion.name] = f"the name of enum '{conversion.name}'"
    for enumerator in conversion.enumerators:
        built.occupied[enumerator.name] = f"an enumerator of enum '{conversion.name}'"


@dataclass(frozen=True, slots=True)
class Loaded:
    """A project read for a question about it, and what reading it had to say.

    The bag is kept rather than thrown away because an edit needs it. A project is indexed
    from what loaded, so a file a ``schema`` error dropped is a file whose declarations are
    simply absent from the index - and a rename computed over that index rewrites every other
    file of the project and leaves that one holding the old name. An ordinary mid-edit state
    has to refuse the rename, not half-perform it.

    It is also what keeps a refresh from reading one project twice. The search below loads
    every candidate to ask whether it includes the document, so the answer is already in
    hand; handing back the read, rather than the path it was read from, is what lets the
    caller analyse it instead of loading it again.
    """

    path: Path
    """The description this was read from, which is what a finding about the read names."""

    workspace: Workspace
    bag: DiagnosticBag
    """What the read reported, for a caller that publishes those findings as well."""

    unreadable: tuple[Path, ...]
    """The files the read reported an error on, sorted; empty when it reported none. A file an
    include names that could not be read is among them, rather than the description reporting it
    (:func:`_unread`).

    Settled when the read finished rather than derived on demand: a caller that goes on to
    analyse this workspace reports into the same bag, and what an edit may not rewrite is a
    file that did not *load*.
    """

    unloaded: tuple[Path, ...] = ()
    """The files of ``unreadable`` that did not load at all, sorted: an error of one of
    :data:`LOAD_CHECKS`, as ``ddd gui`` counts a file that did not load.

    Narrower on purpose, for the plans of :mod:`ddd.lsp.units`. A file that loaded with an error
    is in the index all the same: a units file listing a unit twice is reported as
    ``duplicate-unit``, and a rename of that unit has to reach both of its entries, which a
    refusal would not let it do.
    """


@dataclass(frozen=True, slots=True)
class Containing:
    """What the search for a document's project found, including what it could not read."""

    projects: tuple[Loaded, ...] = ()
    """The descriptions of the outermost directory that include the document, as read."""

    failed: dict[Path, str] = field(default_factory=dict)
    """Candidate -> why reading it stopped, for the candidates a plugin defect stopped.

    Carried out of the search rather than dropped inside it, because a candidate that cannot
    be read is the one case where the search has nothing to say and something to report: as
    far as anybody knows it contains the document, and a caller told only that no project
    contains it would answer from the file alone, with nothing anywhere naming the plugin
    that is broken.
    """


class Descriptions(dict[Path, Loaded | None]):
    """Every description one question has read, by the path it resolves to: what it read as, or
    ``None`` where it could not be read."""

    def __init__(self) -> None:
        super().__init__()
        self.failed: dict[Path, str] = {}
        """Why each description a plugin defect stopped could not be read, by the path it
        resolves to: what a rename that depends on a description it cannot read says."""


def workspaces(
    builds: Sequence[BuildInfo],
    document: Path,
    root: Path | None = None,
    descriptions: Descriptions | None = None,
) -> list[Loaded]:
    """The projects that contain a document, or the document read on its own.

    Loaded per request rather than kept: a jump is something a person asks for, so the cost
    lands on a keypress somebody chose to make, and never on a keystroke they did not.

    Three answers are tried in order of how much they know. A build that named this file knows
    most, because it knows which components are linked together. Failing that, a project file
    lying above the document that turns out to include it knows nearly as much - and finding it
    is what lets an editor answer at all in a tree nobody has configured a build for. Only when
    neither exists is the file read on its own, which is a real answer but a thin one: a
    component alone has no producers for its inputs, no readers for its outputs, and no types
    or constants beyond the ones it declares inline.

    ``descriptions`` is what the question asking has read already, and takes what this reads of
    the builds and of the descriptions above the document: a rename asks this of the document it
    starts from, and goes on to the projects holding the files it rewrites without reading any
    description twice (:class:`Reach`).
    """
    if descriptions is None:
        descriptions = Descriptions()
    # What stopped a read is collected and then dropped: a hover or a jump is a question a
    # person asked and wants an answer to, and the squiggles are where a broken plugin is
    # named. Reporting it twice, once as a finding and once instead of a jump, helps nobody.
    unreadable: dict[Path, str] = {}
    found = []
    for info in builds:
        loaded = _read_once(Path(info.project), unreadable, descriptions)
        if loaded is not None and document.resolve() in loaded.workspace.sources():
            found.append(loaded)
    if not found:
        # Already read, by the search that found them: asking for them again is the second of
        # the two reads per project this used to cost, and the pair is what made the first
        # hover after a save take three times what checking the whole project takes.
        found.extend(resolve_projects(document, root, descriptions).projects)
    if not found:
        alone = _loaded(document, unreadable)
        if alone is not None:
            found.append(alone)
    return found


def _read_once(path: Path, failed: dict[Path, str], descriptions: Descriptions) -> Loaded | None:
    """:func:`_loaded`, unless the question has read ``path`` already: ``descriptions`` holds what
    it has read, by resolved path, ``None`` standing for a description that could not be read -
    whose reason is in the ``failed`` of the search that met it first, and in
    ``descriptions.failed`` for whoever asks later."""
    key = path.resolve()
    if key not in descriptions:
        descriptions[key] = _loaded(path, failed)
        if path in failed:
            descriptions.failed[key] = failed[path]
    return descriptions[key]


def read_project(path: Path) -> Loaded | None:
    """One project description read afresh, as the search reads each candidate, or nothing where
    it cannot be read: for a caller that keeps what it learnt of a project between two questions,
    and settles it again whenever the files may have changed."""
    return _loaded(path, {})


def _loaded(path: Path, failed: dict[Path, str]) -> Loaded | None:
    """One project read for a question about it, or nothing when it cannot be read.

    Reading a project runs the models its plugins declare, over every ``extensions`` block in
    it, and a model that raises is reported as a ``PluginError`` the way a hook that raises
    is. Nothing here can draw a squiggle, so what stopped the read is written into ``failed``
    for the caller to do with as its own answer allows: the diagnostics report it at the
    project file, and a jump discards it, because a jump that answers nothing beats a server
    that exits and the findings of the same save already name the plugin.

    The bag the read reported through is kept, not discarded: which files did not load is what
    an edit over this project has to know before it rewrites any of them.
    """
    bag = DiagnosticBag()
    try:
        workspace = load_workspace(path, bag)
    except PluginError as error:
        failed[path] = str(error)
        return None
    if workspace is None:
        return None
    return Loaded(path, workspace, bag, *_unread(bag))


def _unread(bag: DiagnosticBag) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """What :class:`Loaded` holds of the read's errors: every file one is about, and of those the
    files that did not load, an error of one of :data:`LOAD_CHECKS` - each sorted, each file once.

    An error is about the file it sits in, but for one the loader reports at the include entry
    naming a file it could not read, which is about that file: the description holding the entry
    read, and naming it sent the reader to a file that loaded, while the one an include names
    and is not there went unnamed. An entry naming several files does not say which of them could
    not be read, and the error stays the description's, as one it has and not one that stopped it
    loading.
    """
    about: set[Path] = set()
    unloaded: set[Path] = set()
    for finding in bag.sorted:
        location = finding.location
        if finding.severity is not Severity.ERROR or location is None:
            continue
        path, unread = location.path, finding.check in LOAD_CHECKS
        named = named_at(finding.check, location)
        if named is not None and len(named) == 1:
            path = named[0]
        elif named is not None:
            unread = False
        about.add(path)
        if unread:
            unloaded.add(path)
    return tuple(sorted(about)), tuple(sorted(unloaded))


def named_at(check: str, location: Location) -> list[Path] | None:
    """The files the include entry at ``location`` names, by the loader's own reading of it,
    where ``check`` is one it reports there for a file it could not read; ``None`` for any other
    error, which is about the file it sits in."""
    if check not in _UNREAD_AT_THE_ENTRY or not _INCLUDE_ENTRY.fullmatch(location.pointer):
        return None
    return included_files(location.path, read(location.path, {}).value_at(location.pointer))


def told_apart(files: Iterable[Path]) -> list[str]:
    """Each file as a sentence names it, in order: by its name alone, as a refusal always named a
    file, unless another of ``files`` has that name too - then by its path from the first directory
    up that the two do not share, and in full where nothing short of the root tells them apart.

    Named by their names alone, a units file in each of two images' folders was
    ``units.ddd.json`` twice, and a reader sent to fix it opened whichever one came first.

    Walked over the segments of each path's posix spelling, so that its anchor - nothing before
    the first slash for a root, a drive, a share's double slash - is one segment like any other,
    and all of them together spell the path in full.
    """
    listed = [(file, file.as_posix().split("/")) for file in files]
    # Counted rather than compared pair by pair: a project of thousands of files, named all at
    # once for a filter over its findings, took seconds to compare each with every other.
    ending: Counter[tuple[str, ...]] = Counter()
    for _, segments in listed:
        for depth in range(1, len(segments) + 1):
            ending[tuple(segments[-depth:])] += 1
    listing = Counter(file for file, _ in listed)
    named = []
    for file, segments in listed:
        # The last segment is the name, so a file of another name stops the walk at once. Those
        # equal to the file are the file itself, set aside.
        depth = 1
        while depth < len(segments) and ending[tuple(segments[-depth:])] > listing[file]:
            depth += 1
        named.append("/".join(segments[-depth:]))
    return named


def resolve_projects(
    document: Path, root: Path | None = None, descriptions: Descriptions | None = None
) -> Containing:
    """Descriptions lying at or above the document that turn out to include it, as they read.

    A search rather than a guess: every candidate is loaded and asked whether this file is one
    of its sources, so one that does not include the document is discarded however close it
    sits. What it buys is the case an editor meets constantly - a description opened in a tree
    where no build has been configured - in which the alternative is a component cut off from
    the shared vocabularies, whose declarations of shared types resolve to nothing at all.

    The outermost directory holding a description that includes the document answers, so a
    component of a sub-project is checked under the project that holds the sub-project, as
    ``ddd check`` of that project checks it. The walk therefore goes to the root even after a
    hit, and a description nearer the document is dropped.

    The read itself is handed back, which is what makes this the one place a project above a
    document is loaded: the findings go to the diagnostics, the workspace answers the hovers
    and the jumps, and neither has to read the file a second time to have it.

    A candidate that could not be read answers neither way: the walk carries on past it, and
    it is named in ``failed`` so that the caller can say so - where this search is the first of
    its question to meet it: a candidate ``descriptions`` holds already is not read again, as
    :func:`workspaces` says.

    The document is resolved once, above the walk, because that is what the candidates are:
    they come from a resolved directory and every ``sources()`` is resolved too. Compared with
    the client's own spelling - through a junction, a ``subst`` drive or a symlink - the
    document never equalled itself, so it was taken as a project containing itself and
    analysed a second time as a project of one, whose inputs nobody writes.

    Bounded by the editor's own root, so the walk cannot wander up into a home directory.
    """
    if descriptions is None:
        descriptions = Descriptions()
    resolved = document.resolve()
    failed: dict[Path, str] = {}
    outermost: list[Loaded] = []
    for directory in _walked(document, root):
        found = []
        for candidate in sorted(directory.glob("*.ddd.json")):
            if candidate == resolved:
                continue
            loaded = _read_once(candidate, failed, descriptions)
            if loaded is not None and resolved in loaded.workspace.sources():
                found.append(loaded)
        if found:
            # Every level is walked, and the last one that included the document answers: a
            # description nearer the document is a sub-project of the one further up, and the
            # sub-project alone does not know what its siblings produce. Answering from both
            # would say everything twice, so the nearer one is dropped.
            outermost = found
    return Containing(tuple(outermost), failed)


def _walked(document: Path, root: Path | None) -> list[Path]:
    """The directories the search above ``document`` walks, resolved, the nearest first: from the
    one holding it up to ``root``, the editor's own, or the one holding it alone without one."""
    stop = root.resolve() if root is not None else document.parent.resolve()
    directories = []
    current = document.parent.resolve()
    while True:
        directories.append(current)
        if current == stop or current.parent == current or stop not in current.parents:
            return directories
        current = current.parent


def _held_above(
    files: Iterable[Path], root_for: Callable[[Path], Path], descriptions: Descriptions
) -> list[Loaded]:
    """The descriptions of the outermost directory above each of ``files`` that include it, as
    :func:`resolve_projects` answers for each file alone, file after file, in the order given.

    The same candidates are read as each file's own search reads - every description of a
    directory one of the files' walks reaches, but for the file itself - and each directory is
    listed, and each candidate asked which of the files it holds, once for them all. Asked file by
    file, a fix sent from a writer to two hundred readers of one flat directory listed it two
    hundred times, and resolved and sorted every candidate's sources as often, at every move of
    the caret.
    """
    walks: dict[Path, list[Path]] = {}
    asking: dict[Path, set[Path]] = {}
    for file in files:
        resolved = file.resolve()
        walks[resolved] = _walked(file, root_for(file))
        for directory in walks[resolved]:
            asking.setdefault(directory, set()).add(resolved)
    failed: dict[Path, str] = {}
    holding: dict[tuple[Path, Path], list[Loaded]] = {}
    for directory, asked in asking.items():
        for candidate in sorted(directory.glob("*.ddd.json")):
            if asked == {candidate}:
                # The one file whose walk reaches here is this candidate, which is not asked
                # whether it holds itself.
                continue
            loaded = _read_once(candidate, failed, descriptions)
            if loaded is None:
                continue
            for held in asked.intersection(loaded.workspace.sources()) - {candidate}:
                holding.setdefault((directory, held), []).append(loaded)
    found: list[Loaded] = []
    for resolved, walk in walks.items():
        outermost: list[Loaded] = []
        for directory in walk:
            # Every level is walked, and the last one holding a description that includes the
            # file answers, as :func:`resolve_projects` answers.
            outermost = holding.get((directory, resolved), outermost)
        found.extend(outermost)
    return found


class Reach:
    """Every project a rename reaches: the ones holding the document it starts from, then every
    project holding a file a reached project's edits touch, until none is new.

    The projects of the document alone made a rename's reach depend on where it started. A
    writer linked into two images, read by a reader in each: started from the writer, the
    rename rewrote all three; started from image one's reader, it rewrote that reader and the
    writer, and left image two's reader naming an object that is gone. Reaching every project
    that holds a file the rename rewrites, and every project holding a file those rewrite in
    turn, makes it the same rename from either reader as from the writer.

    The projects holding a file are the ones :func:`workspaces` answers for it - the builds
    holding it, and, for a file no build holds, the descriptions of the outermost directory above
    it that include it - found without reading any description twice: the projects read already
    are asked which of the new files they hold, and a description is read only where nothing has
    read it for this rename yet. Asked of :func:`workspaces` file by file, the search would read
    every build's project once for each file the rename touches. A file no project holds is not
    read on its own: a project reached already holds it, since its edits touch it. A description
    that cannot be read reaches nothing, as :func:`workspaces` answers.

    Iterated while it grows: :meth:`touch` adds the projects holding what a reached project's
    edits touch, and the iteration goes on to them.
    """

    def __init__(
        self,
        builds: Sequence[BuildInfo],
        start: Sequence[Loaded],
        root_for: Callable[[Path], Path],
        descriptions: Descriptions,
    ) -> None:
        self.projects: list[Loaded] = []
        """The projects reached so far, in the order they were reached, the document's first."""
        self._builds = builds
        self._root_for = root_for
        """The workspace folder bounding the search above a file, as the server answers it."""
        self._descriptions = descriptions
        self._reached: set[Path] = set()
        self._touched: set[Path] = set()
        for loaded in start:
            # The document's projects may have been read for an earlier request, and kept: the
            # rename goes on from that read rather than reading them again.
            descriptions.setdefault(loaded.path.resolve(), loaded)
            self._add(loaded)
        self._own = frozenset(self._reached)
        """The descriptions holding the document the rename started from: the reader's own."""

    def __iter__(self) -> Iterator[Loaded]:
        """Every project reached, those :meth:`touch` adds while this runs included."""
        position = 0
        while position < len(self.projects):
            yield self.projects[position]
            position += 1

    def touch(self, files: Iterable[Path]) -> None:
        """Reach every project holding one of ``files``, which a reached project's edits touch.

        Nothing is asked where no file is new: a build's project the rename has not needed yet
        would be read for nothing, to say which of no files it holds."""
        new = set(files) - self._touched
        if not new:
            return
        self._touched |= new
        held: set[Path] = set()
        for info in self._builds:
            # Why a build's project could not be read is not this question's to report, as in
            # :func:`workspaces`: the findings of the same refresh name it.
            loaded = _read_once(Path(info.project), {}, self._descriptions)
            if loaded is not None and (holds := new.intersection(loaded.workspace.sources())):
                held |= holds
                self._add(loaded)
        for loaded in _held_above(sorted(new - held), self._root_for, self._descriptions):
            self._add(loaded)

    @property
    def unread(self) -> dict[Path, str]:
        """Every description the search has met and could not read, with why, by the path it
        resolves to: the ones a plugin defect stopped, whether a build record names them or the
        search above a file found them. What a rename must not go on without, since the files
        such a description holds are rewritten for no image."""
        return self._descriptions.failed

    def image(self, loaded: Loaded) -> str | None:
        """What a refusal from ``loaded`` names it by: the image of the build naming its
        description; where no build names one, the description, by its path in its workspace
        folder - two images' descriptions often share a file name, and in a folder each - or in
        full where it lies in none; and nothing for a project holding the document the rename
        started from, which is the reader's own."""
        if loaded.path.resolve() in self._own:
            return None
        return self.described(loaded)

    def described(self, loaded: Loaded) -> str:
        """What a sentence calls ``loaded`` where it names two projects, the reader's own among
        them as readily as another: as :meth:`image` names one that is not the reader's."""
        key = loaded.path.resolve()
        return self._record_image(key) or self._in_folder(key)

    def named(self, description: Path) -> str:
        """What a refusal about a description that could not be read calls it: its path in its
        workspace folder, and the image of the build naming it where one does."""
        key = description.resolve()
        image = self._record_image(key)
        return self._in_folder(key) + (f" of the image {image}" if image else "")

    def _record_image(self, key: Path) -> str | None:
        for info in self._builds:
            if info.image and Path(info.project).resolve() == key:
                return info.image
        return None

    def _in_folder(self, key: Path) -> str:
        folder = self._root_for(key).resolve()
        if key.is_relative_to(folder):
            return key.relative_to(folder).as_posix()
        return key.as_posix()

    def _add(self, loaded: Loaded) -> None:
        key = loaded.path.resolve()
        if key not in self._reached:
            self._reached.add(key)
            self.projects.append(loaded)


def variable_at(document: Document, pointer: str) -> str | None:
    """The data object the cursor names outright, if it names one.

    The narrow half of :func:`subject_at`, which is the rule every question actually uses.
    Separate because a reference key has to win over the declaration holding it, and that
    precedence is easier to read as two steps than as one condition.
    """
    value = document.value_at(pointer)
    if not isinstance(value, str):
        return None
    if _DEFINITION_KEY.match(pointer):
        return value
    return None


def constant_at(document: Document, pointer: str) -> str | None:
    """The declared constant the cursor names outright, if it names one.

    A dimension entry or an axis ``size`` spelling a name rather than a number, or a value
    inside a constants file - the places where the string under the cursor *is* a constant.
    Whether the name is actually declared is the caller's question; an undeclared one simply
    resolves to nothing, the way an unknown type does.
    """
    value = document.value_at(pointer)
    if not isinstance(value, str):
        return None
    if _DIMENSION_KEY.match(pointer) or _CONSTANT_ENTRIES.match(pointer):
        return value
    return None


def type_at(document: Document, pointer: str) -> str | None:
    """The declared type the cursor is about, if it is about one.

    Two positions answer: a ``typename`` value, wherever it is written - on a declaration or
    on a structure member - and anywhere inside a type entry, which is about the type it
    declares from its opening brace on, exactly as a declaration is about its object. Whether
    the name is actually declared is the caller's question; an unknown one simply resolves to
    nothing, the way an unknown constant does.
    """
    value = document.value_at(pointer)
    if isinstance(value, str) and _TYPENAME_KEY.match(pointer):
        return value
    entry = _TYPE_ENTRY.match(pointer)
    if entry is None:
        return None
    name = document.value_at(f"{entry.group()}.name")
    return name if isinstance(name, str) else None


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
        if pointer.startswith(_INCLUDES):
            return _files(path.parent, value)
        # A dimension spelled as a name goes to the constant it names, wherever the
        # constants file lives - the constant is what is under the pointer. A name nobody
        # declares goes nowhere; the unknown-constant finding is already saying why.
        if constant_at(document, pointer) is not None:
            declared = built.constants.get(value)
            return [declared] if declared is not None else []
        # A datatype that names a declared type goes to that type, wherever it is written -
        # the type is what is under the pointer. A base datatype names no file, so it falls
        # through to the declaration jump, which is what somebody resting there expects.
        found = built.types.get(value)
        if found is not None and (_TYPE_ENTRIES.match(pointer) or _TYPENAME_KEY.match(pointer)):
            return [found]
        if _TYPE_ENTRIES.match(pointer):
            return []
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
    named = constant_at(document, pointer)
    if named is not None:
        found = built.constants.get(named)
        return [found, *built.constant_uses.get(named, ())] if found is not None else []
    value = document.value_at(pointer)
    if isinstance(value, str) and (_TYPE_ENTRIES.match(pointer) or _TYPENAME_KEY.match(pointer)):
        declared = built.types.get(value)
        if declared is not None:
            return [declared, *built.type_uses.get(value, ())]
        if _TYPE_ENTRIES.match(pointer):
            return []
    name = subject_at(document, pointer)
    if name is not None:
        return list(built.declarations.get(name, ()))
    return []


def is_alone(document: Path, projects: Sequence[Loaded], builds: Sequence[BuildInfo]) -> bool:
    """Whether ``projects``, which :func:`workspaces` answered for ``document``, are no project
    at all: the document read on its own, a component that no record claims, that no description
    above includes, and that declares no project itself.

    The third answer of :func:`workspaces` is also the whole project of a project file opened
    alone, which is a project known; and a component whose description above could not be read
    is read alone too, which is not what is wrong with it (:attr:`Reach.unread`). A build record
    naming the component as its description is a claim, so a project of its own, however thin.
    """
    if len(projects) != 1 or projects[0].workspace.projects:
        return False
    return all(Path(info.project).resolve() != document.resolve() for info in builds)


def is_local(built: Index, name: str) -> bool:
    """Whether every declaration of ``name`` states it ``local``: spelled in the file declaring
    it and nowhere else, which is why its rename is the one that needs no project."""
    sites = built.declarations.get(name, ())
    return bool(sites) and all(built.scopes[site] == "local" for site in sites)


def renameable_at(document: Document, pointer: str) -> tuple[str, str] | None:
    """What a rename may start from at this position: its kind and its name, or nothing.

    A variable, from its name or from a reference naming it; a declared type, from the
    ``name`` of its entry or from any ``typename`` spelling it; a declared constant, from the
    ``name`` of its entry or from any dimension or axis ``size`` spelling it; a section or a
    raster, from its own entry or from any definition placing data in it or naming it - a
    raster's uses also include a component's own default, the one use written outside any
    definition at all; a unit, from any place it is stated or from its entry in a units file.
    Narrow on purpose, like :func:`variable_at`: the editor opens its box over the range this
    names.

    A unit is renamed by :func:`ddd.lsp.units.rename_unit` rather than by :func:`rename_edits`:
    its rename rewrites the vocabulary too, and merges two spellings where a name would collide.
    """
    value = document.value_at(pointer)
    if not isinstance(value, str):
        return None
    variable = variable_at(document, pointer)
    if variable is not None:
        return ("variable", variable)
    if _TYPENAME_KEY.match(pointer) or _TYPE_NAME.match(pointer):
        return ("type", value)
    if _DIMENSION_KEY.match(pointer) or _CONSTANT_NAME.match(pointer):
        return ("constant", value)
    if _SECTION_KEY.match(pointer) or _SECTION_NAME.match(pointer):
        return ("section", value)
    if _RASTER_KEY.match(pointer) or _RASTER_NAME.match(pointer):
        return ("raster", value)
    # The empty unit is no unit - a dimensionless value states none - so there is nothing
    # spelled there to rename.
    if value and _UNIT_KEY.match(pointer):
        return ("unit", value)
    return None


def rename_sites(built: Index, kind: str, name: str) -> list[Site]:
    """Every string a rename of this kind writes the new name over whole, the declaration
    included: a condition, of which a constant's rename rewrites a word alone, is
    :func:`conditions_spelling`'s.

    A variable's mentions are indexed as strings already. A type or a constant is indexed by
    its entry and by the places spelling it, so its own ``name`` is added here; a name nothing
    declares - a ``typename`` the loader has already reported - renames its uses alone. A
    section or a raster is the same, its own entry added under its own key rather than
    ``name``.
    """
    if kind == "variable":
        return list(built.mentions.get(name, ()))
    if kind == "section":
        section = built.sections.get(name)
        uses = built.section_uses.get(name, ())
        if section is None:
            return list(uses)
        return [Site(section.path, f"{section.pointer}.section"), *uses]
    if kind == "raster":
        raster = built.rasters.get(name)
        uses = built.raster_uses.get(name, ())
        if raster is None:
            return list(uses)
        return [Site(raster.path, f"{raster.pointer}.raster"), *uses]
    declared = (built.types if kind == "type" else built.constants).get(name)
    uses = (built.type_uses if kind == "type" else built.constant_uses).get(name, ())
    if declared is None:
        return list(uses)
    return [Site(declared.path, f"{declared.pointer}.name"), *uses]


def conditions_spelling(built: Index, kind: str, name: str) -> list[Site]:
    """Every condition spelling ``name`` as a word, where a name of this kind is one a condition
    may spell: a constant's, at :attr:`Index.condition_uses`; for any other kind, none.

    A section's name is a linker string and a raster's an a2l short name, neither ever written into
    the generated c, so no condition spells one, whatever constant shares its spelling; and neither
    a variable nor a type is a macro ``#if`` could read. What a rename of the name rewrites a word
    of, beside :func:`rename_sites`, and what the Shared files tab counts beside the shapes, and
    refuses a removal for.
    """
    if kind != "constant":
        return []
    return list(built.condition_uses.get(name, ()))


def word_spans(document: Document, pointer: str, word: str) -> list[tuple[int, int]]:
    """Where the string at ``pointer`` spells ``word`` as a word (:data:`_WORD`), as offsets into
    the document's text: each time it does, in order, and none where no string is written there.

    Found in the string as json reads it and placed in the text as it is written. An escape is one
    character of the string and several of the text, so ``CELLS`` after a ``\\t`` or a ``\\"`` sits
    further along in the file than in the condition, and ``C\\u0045LLS`` is the word too, its span
    taking the escape with it.
    """
    span = document.text_span_of(pointer)
    if span is None:
        return []
    written = list(_JSON_CHARACTER.finditer(document.text, *span))
    read_as = "".join(_character(found.group()) for found in written)
    return [
        (written[found.start()].start(), written[found.end() - 1].end())
        for found in _WORD.finditer(read_as)
        if found.group() == word
    ]


def _character(written: str) -> str:
    """The character one :data:`_JSON_CHARACTER` reads as: the escape decoded, as json reads it,
    or the character itself."""
    if written.startswith("\\"):
        decoded: str = json.loads(f'"{written}"')
        return decoded
    return written


def drift(
    sites: Iterable[Site],
    name: str,
    cache: dict[Path, Document],
    conditions: Iterable[Site] = (),
) -> tuple[Path, ...]:
    """The files whose text no longer holds ``name`` at one of ``sites``, or no longer spells it as
    a word in the condition at one of ``conditions``, each once, sorted.

    The index points into each file as the analysis read it. A declaration or an entry put in
    above the one it recorded - or taken out, or put back by an undo - leaves another, or none, at
    that place, and a plan made at the recorded pointer changes whatever sits there now: what a
    panel's route asks before it reads an entry (:func:`ddd.project_types.type_in_place`,
    :func:`ddd.project_shared.entry_in_place`), and what :func:`rename_edits` asks of a buffer,
    asked of every place a plan points at. A condition is asked whether it still spells the name,
    which is all a plan rewriting its word needs of it.
    """
    moved = {site.path for site in sites if read(site.path, cache).value_at(site.pointer) != name}
    moved.update(
        site.path
        for site in conditions
        if not word_spans(read(site.path, cache), site.pointer, name)
    )
    return tuple(sorted(moved, key=Path.as_posix))


def changed_since(files: Iterable[Path], consequence: str) -> str:
    """Why a plan pointing by the index is refused while ``files`` no longer hold what it recorded
    there, ``consequence`` saying what cannot be done: one sentence for every such plan, naming
    each file, and the wait that clears it - the next analysis, which reads them again."""
    names = ", ".join(file.name for file in files)
    return (
        f"{names} changed since the project was analysed, so {consequence} until the project is "
        "analysed again"
    )


def named_by_a_header(built: Index, kind: str, name: str) -> str | None:
    """Why what is of this ``kind`` and called ``name`` may not be renamed at all, whatever it
    would be renamed onto: an external type's name is the one the header beside it defines. Nothing
    for anything else.

    DDD generates no typedef for an external type, only the include of its header, so the name
    its entry spells is the vendor's: a rename of the descriptions left the header defining the
    old name and the generated types header spelling the new one, ``ddd check`` said nothing, and
    the build stopped at the first compile. The one check both clients ask, the editor's ``F2`` of
    every project it reaches (:meth:`ddd.lsp.server.Server._name_rename`) and the page's Types tab
    (:func:`ddd.type_plans.rename_type`), so that the two cannot disagree about it; asked before
    :func:`rename_problem`, which judges the new name, since no new name would do.

    A variable, a constant or anything else spelled as an external type is the project's own, and
    renaming it is how the collision of the two is mended. Two early returns rather than one
    ``or``, which coverage.py counts as a single branch whichever operand decided it.
    """
    if kind != "type":
        return None
    header = built.externals.get(name)
    if header is None:
        return None
    return (
        f"'{name}' is an external type whose name {header} defines, so a rename here would leave "
        "that header defining the old one"
    )


def rename_problem(built: Index, name: str, kind: str = "variable") -> str | None:
    """Why the project may not be renamed to ``name``, or nothing if it may.

    Checked before a single file is touched. A rename writes into every component that
    mentions the object, so a name that turns out to be unusable would leave a project broken
    across several files at once - and the c compiler, which is where an unusable name is
    otherwise noticed, only sees it a build later.

    A section is judged by its own rule and leaves before the first check below: every one of
    them is about a c identifier, and a section's name is a linker string. Answered here rather
    than in :mod:`ddd.project_shared`, which is where the Shared files tab would otherwise have
    written the rule a second time: that module imports this one - :class:`Index` is this
    module's - so the tab reaches this function through its descriptor's ``taken`` and the
    editor's F2 reaches it through :meth:`ddd.lsp.server.Server._rename`, and the two cannot come
    to different answers about a name.

    A raster is judged by its own rule too, and leaves beside the section's: its name is the
    short name of an a2l ``EVENT``, not a c identifier, and none of the checks below apply to
    it. Before this arm existed it fell through to them and answered wrong - ``10ms`` is no c
    identifier and is a perfectly usable a2l short name. That wrong answer was latent before
    part 14's third task and reachable after it: :func:`renameable_at` had no raster arm before
    then, so it never answered ``("raster", …)`` and :meth:`ddd.lsp.server.Server._rename` could
    not hand this function that kind at all. Teaching the index to see rasters is what made F2 on
    one arrive here, so the rasters part owed this its arm beside the section's.
    """
    if kind == "section":
        return _section_problem(built, name)
    if kind == "raster":
        return _raster_problem(built, name)
    if not re.fullmatch(C_IDENTIFIER_PATTERN, name) or len(name) > IDENTIFIER_MAX_LENGTH:
        return f"'{name}' is not a usable c identifier"
    if kind == "type" and name.lower() in _BASE_DATATYPES:
        # The loader refuses a declared type wearing the name of storage it is not; the rename
        # has to refuse it first, or the files it rewrote would not load.
        return f"'{name}' spells a base datatype, which a declared type may not be called"
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


def _section_problem(built: Index, name: str) -> str | None:
    """Why the project may not have a section called ``name``, or nothing if it may.

    Two checks, and none of the five :func:`rename_problem` applies to the other kinds. The c
    identifier rule and the reserved word rule would refuse ``.calib`` outright, a leading dot
    being an ordinary linker name; ``declarations`` and ``occupied`` guard c's file scope
    namespace, which a section's name never joins - it is spliced into a ``section`` attribute
    and never emitted as an identifier, which is what
    ``test_a_section_may_share_a_spelling_with_a_variable`` pins. No length limit either:
    :data:`~ddd.models.common.IDENTIFIER_MAX_LENGTH` bounds a c identifier, and the model sets a
    section's name no length at all.

    :data:`~ddd.models.common.SECTION_NAME_PATTERN` is the rule rather than a restatement of it:
    :class:`ddd.models.sections.SectionDeclaration` constrains its own ``section`` to that same
    constant, so a name refused here is exactly a name whose file would not load - and its
    ``min_length=1`` is what the pattern's ``+`` already says.

    A name the vocabulary already declares is refused although the file would still load:
    ``duplicate-section`` is a check and not a schema error, so the format permits two sections
    under one name - but each carries its own ``access`` and ``alignment``, and a rename that
    merged them would silently move data into memory with different properties. The reader can
    see the name is taken and pick another, which is the line part 14's design draws between what
    the interface refuses and what it lets a check report.
    """
    if not re.fullmatch(SECTION_NAME_PATTERN, name):
        return f"'{name}' is not a usable linker section name"
    if name in built.sections:
        return f"'{name}' is already a section this project declares"
    return None


def _raster_problem(built: Index, name: str) -> str | None:
    """Why the project may not have a raster called ``name``, or nothing if it may.

    Judged by :data:`~ddd.models.common.RASTER_NAME_PATTERN` and, unlike a section,
    :data:`~ddd.models.common.RASTER_NAME_LENGTH` too - rather than by the c identifier rule the
    other kinds answer to: a raster's name is the short name of its XCP event, which ``10ms``
    spells and no c identifier may. The length is the model's own, not
    :data:`~ddd.models.common.IDENTIFIER_MAX_LENGTH`, which bounds a c identifier and is a
    different number for a different reason. It joins no namespace ``occupied`` guards, for the
    reason :func:`_section_problem` gives about a section's.

    A name the vocabulary already declares is refused although the file would still load, exactly
    as a section's is: ``duplicate-raster`` is a check, not a schema error, so two rasters may share
    a name - and each carries its own event and cycle, so merging two would silently sample one
    signal on another's channel.
    """
    if not re.fullmatch(RASTER_NAME_PATTERN, name) or len(name) > RASTER_NAME_LENGTH:
        return f"'{name}' is not a usable raster name"
    if name in built.rasters:
        return f"'{name}' is already a raster this project declares"
    return None


@dataclass(frozen=True, slots=True)
class RenameEdits:
    """What a rename takes: the edits it makes, and the sites a drifted buffer kept out of them."""

    changes: dict[str, list[dict[str, Any]]]
    drifted: tuple[Path, ...]
    """Every site skipped because its buffer no longer names the subject there, sorted.

    Reported rather than silently dropped: the caller is the one in a position to decide
    whether an edit that could not reach every site should be applied at all.
    """


def rename_edits(
    built: Index, document: Document, pointer: str, name: str, cache: dict[Path, Document]
) -> RenameEdits:
    """Every edit that renaming the object under the cursor takes, keyed by file - and the
    sites a drifted buffer kept out of them.

    Only the characters between the quotes are replaced, so whatever else is on the line -
    the key, the spacing a project formats its files with - is left exactly as it was; and of a
    condition spelling a constant, only that word (:func:`conditions_spelling`), every other
    word and every longer identifier holding it left as they were. The new name is written as
    json spells it between the quotes: a raster's name may hold a quote or a backslash, and
    written raw, a quote ended the string, so that no file the rename rewrote parsed, and a
    backslash began an escape, so that the name read back was another.

    A site whose buffer no longer names the subject at the index's pointer - or a condition that
    no longer spells it - is reported in ``drifted`` instead of silently left out of ``changes``:
    a rename that rewrites some files and not others leaves the project half renamed, and the
    caller has to know which file that would have been.
    """
    subject = renameable_at(document, pointer)
    if subject is None:
        return RenameEdits(changes={}, drifted=())
    kind, old = subject
    written = json.dumps(name, ensure_ascii=False)[1:-1]
    changes: dict[str, list[dict[str, Any]]] = {}
    drifted: list[Path] = []
    for site in rename_sites(built, kind, old):
        target = read(site.path, cache)
        if target.value_at(site.pointer) != old:
            # The index describes the disk; an open buffer may have moved the declaration.
            # Editing at the old pointer would rename whatever now sits there.
            drifted.append(site.path)
            continue
        # `text_range_of` and the `value_at` above are read off the same scan of `target`, so
        # a pointer just confirmed to hold `old` there always has a text span too.
        span = target.text_range_of(site.pointer)
        assert span is not None
        changes.setdefault(site.path.as_uri(), []).append({"range": span, "newText": written})
    for site in conditions_spelling(built, kind, old):
        target = read(site.path, cache)
        spans = word_spans(target, site.pointer, old)
        if not spans:
            drifted.append(site.path)
            continue
        changes.setdefault(site.path.as_uri(), []).extend(
            {
                "range": {"start": target.position(start), "end": target.position(end)},
                "newText": written,
            }
            for start, end in spans
        )
    return RenameEdits(changes=changes, drifted=tuple(sorted(drifted)))


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
