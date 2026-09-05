"""Reading a project/component tree from disk into the pydantic contracts."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import DICTIONARY_FORMAT, DataDictionary
from ddd.models import (
    AnyDataObject,
    AnyType,
    Component,
    ComponentFile,
    ConstantDeclaration,
    ConstantsFile,
    Conversion,
    ExternalType,
    Project,
    ProjectFile,
    RasterDeclaration,
    RastersFile,
    SectionDeclaration,
    SectionsFile,
    StructType,
    TypesFile,
    UnitDeclaration,
    UnitsFile,
    discriminator_tags,
)
from ddd.plugins import Plugin, PluginInvalidError, PluginNotFoundError, load_plugin

DDD_SUFFIX = ".ddd.json"
"""Every project and component description file carries this extension.

In a large repository a plain ``*.json`` says nothing about who owns the file; the
double extension makes a DDD description recognisable at a glance and lets build
scripts and editors match them with a single pattern.
"""

_GLOB_CHARACTERS = frozenset("*?[")

FILE_KINDS = ("project", "component", "types", "units", "sections", "constants", "rasters")
"""Top level keys that identify a description file, in the order they are offered."""

_INCLUDE_ONLY_KINDS = {
    "types": "this is a structured datatype description; list it in the 'includes' of the "
    "project that uses it instead of analysing it on its own",
    "units": "this is a unit vocabulary; list it in the 'includes' of the project whose "
    "units it declares instead of analysing it on its own",
    "sections": "this is a memory section description; list it in the 'includes' of the "
    "project that places data in them instead of analysing it on its own",
    "constants": "this is a constant vocabulary; list it in the 'includes' of the project "
    "whose sizes it names instead of analysing it on its own",
    "rasters": "this is a measurement raster description; list it in the 'includes' of the "
    "project whose measurements name them instead of analysing it on its own",
}
"""Why a vocabulary file is refused as the root, by kind.

None of these is a project, so there is nothing to resolve or generate from one on its
own. Validating one against the published schema is what an editor is for.
"""

_UNION_TAGS = discriminator_tags(AnyDataObject, Conversion, AnyType)
"""Discriminator values pydantic inserts into the error location of a tagged union."""


def _reject_constant(name: str) -> float:
    """Refuse ``NaN``, ``Infinity`` and ``-Infinity``, which python's json reader accepts.

    They are not json, and none of them is a value DDD can carry through to its outputs: a
    limit of NaN compares false against everything, so every range check silently passes,
    and the a2l would end up with a token no calibration tool can parse.
    """
    msg = f"'{name}' is not valid json; DDD has no representation for it"
    raise ValueError(msg)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse an object that spells the same key twice, which json itself allows.

    Parsers resolve the duplication silently - the last spelling wins - so the value the
    author reads first is not the value the tool would use, and in a grown description
    file that is a debugging session. Refusing it turns the guess into a finding.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = (
                f"key '{key}' appears twice in one object; json would silently keep the "
                f"last spelling, so decide which one stays"
            )
            raise ValueError(msg)
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class LoadedComponent:
    """A component description together with where it came from."""

    path: Path
    component: Component
    parents: tuple[str, ...]
    """Names of the projects that led to this component, outermost first."""

    @property
    def name(self) -> str:
        return self.component.name

    def location(self, pointer: str = "component") -> Location:
        return Location(self.path, pointer)

    def declaration_location(self, index: int, suffix: str = "") -> Location:
        pointer = f"component.interface[{index}]"
        if suffix:
            pointer = f"{pointer}.{suffix}"
        return Location(self.path, pointer)


@dataclass(frozen=True, slots=True)
class LoadedProject:
    """A project description together with where it came from."""

    path: Path
    project: Project
    parents: tuple[str, ...]

    @property
    def name(self) -> str:
        return self.project.name


@dataclass(frozen=True, slots=True)
class LoadedType:
    """One declared type together with where it was declared.

    One per type rather than one per file, because everything downstream refers to a type by
    name and a finding about it has to point at the entry that declared it.
    """

    path: Path
    index: int
    """Position in the list of its file, which is what the location points at."""

    declared: AnyType
    """The entry itself: a structure or a scalar type."""

    container: str = "types"
    """Pointer of the list holding the entry: ``types`` in a types file, ``component.types``
    for a type a component declares inline. Only the location differs; a declared type is
    the same thing in either home."""

    @property
    def name(self) -> str:
        return self.declared.name

    @property
    def structure(self) -> StructType | None:
        """The entry as a structure, or nothing if it names a scalar or an external type."""
        return self.declared if isinstance(self.declared, StructType) else None

    @property
    def external(self) -> ExternalType | None:
        """The entry as an external type, or nothing if DDD declares this type itself."""
        return self.declared if isinstance(self.declared, ExternalType) else None

    def location(self, suffix: str = "") -> Location:
        pointer = f"{self.container}[{self.index}]"
        if suffix:
            pointer = f"{pointer}.{suffix}"
        return Location(self.path, pointer)


@dataclass(frozen=True, slots=True)
class LoadedUnit:
    """One declared unit together with where it was declared.

    One per unit rather than one per file, for the reason :class:`LoadedType` gives: a
    finding about a unit has to point at the entry that declared it.
    """

    path: Path
    index: int
    """Position in the ``units`` list of its file, which is what the location points at."""

    declared: UnitDeclaration

    @property
    def unit(self) -> str:
        return self.declared.unit

    def location(self) -> Location:
        return Location(self.path, f"units[{self.index}]")


@dataclass(frozen=True, slots=True)
class LoadedSection:
    """One declared section together with where it was declared."""

    path: Path
    index: int
    """Position in the ``sections`` list of its file, which is what the location points at."""

    declared: SectionDeclaration

    @property
    def section(self) -> str:
        return self.declared.section

    def location(self) -> Location:
        return Location(self.path, f"sections[{self.index}]")


@dataclass(frozen=True, slots=True)
class LoadedRaster:
    """One declared raster together with where it was declared."""

    path: Path
    index: int
    """Position in the ``rasters`` list of its file, which is what the location points at."""

    declared: RasterDeclaration

    @property
    def raster(self) -> str:
        return self.declared.raster

    def location(self) -> Location:
        return Location(self.path, f"rasters[{self.index}]")


@dataclass(frozen=True, slots=True)
class LoadedConstant:
    """One declared constant together with where it was declared.

    One per constant rather than one per file, for the reason :class:`LoadedType` gives: a
    finding about a constant has to point at the entry that declared it.
    """

    path: Path
    index: int
    """Position in the list of its file, which is what the location points at."""

    declared: ConstantDeclaration

    container: str = "constants"
    """Pointer of the list holding the entry: ``constants`` in a constants file,
    ``component.constants`` for a constant a component declares inline."""

    @property
    def name(self) -> str:
        return self.declared.name

    @property
    def value(self) -> int:
        return self.declared.value

    def location(self, suffix: str = "") -> Location:
        pointer = f"{self.container}[{self.index}]"
        if suffix:
            pointer = f"{pointer}.{suffix}"
        return Location(self.path, pointer)


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """A plugin together with where the project named it, for the note on a clash."""

    plugin: Plugin
    spelling: str
    origin: Location


@dataclass(frozen=True, slots=True)
class Workspace:
    """Everything DDD knows after reading the file tree."""

    root: Path
    name: str
    description: str
    components: tuple[LoadedComponent, ...]
    projects: tuple[LoadedProject, ...]
    types: tuple[LoadedType, ...] = ()
    """The declared types of the project, from its types files and its components alike,
    sorted by name.

    One registry whichever home declared an entry: a type a component declares inline is the
    same project wide name a types file would have given it. Sorted rather than in include
    order so that a project produces the same output whichever way its ``includes`` happen
    to expand; the order of *members* inside a structure is the author's and is preserved,
    because that one decides the layout.
    """

    units: tuple[LoadedUnit, ...] = ()
    """The unit vocabulary the project declares, sorted by spelling; empty means unchecked.

    An empty vocabulary is the opt-out: no units file, no constraint. Once any file declares
    one, every stated unit is checked against the union of what every units file declares.
    """

    sections: tuple[LoadedSection, ...] = ()
    """The memory sections the project declares, sorted by name.

    Unlike a unit, a section is a reference rather than a spelling: a definition naming one
    that no file declares is ``unknown-section``, whether or not any sections file exists -
    a section without declared properties would be a name the checks can say nothing about.
    """

    rasters: tuple[LoadedRaster, ...] = ()
    """The measurement rasters the project declares, sorted by name.

    A reference the way a section is: a definition naming one that no file declares is
    ``unknown-raster``, whether or not any rasters file exists, because an event nothing
    describes is a name the a2l could only write as a number nobody chose.
    """

    constants: tuple[LoadedConstant, ...] = ()
    """The named constants the project declares, from its constants files and its
    components alike, sorted by name.

    A constant is a reference the way a section is: a shape naming one that nothing declares
    is ``unknown-constant``, whether or not any constants file exists, because a name
    without a value is a dimension nothing can resolve.
    """

    read_paths: tuple[Path, ...] = ()
    """Every file the loader opened, whatever came of it.

    Deliberately not derived from ``components`` and ``projects``: a file that was read and
    then rejected - a duplicate component name, a schema error - is still a file this project
    is built out of, and editing it has to make the build run DDD again. Leaving it out is how
    a build system ends up never noticing the fix.
    """

    plugins: tuple[Plugin, ...] = ()
    """The plugins the project files name, in project order, each once.

    Empty for a component read on its own: only a project names plugins, which is why a
    block in such a run is reported by ``unknown-extension``, a check the editor's
    standalone mode holds back for exactly that reason.
    """

    project_extensions: dict[str, dict[str, Any]] = field(default_factory=dict)
    """The settings block of each plugin, as the project files wrote it, by plugin name."""

    def sources(self) -> tuple[Path, ...]:
        """Every file that was read to build this workspace, sorted and without duplicates.

        What a build system needs in order to know when to run DDD again: the root file
        alone is not enough, because a project pulls its components in through ``includes``.
        """
        return tuple(sorted({self.root, *self.read_paths}))

    def locate(self, name: str) -> Location | None:
        """Where a plugin's finding about the object ``name`` belongs.

        The declaration that produces it, and failing that the first one naming it: a
        consumer's declaration is still where a reader looks for the object. ``None`` when no
        component names it - a leaf, or a name the plugin made up.
        """
        fallback: Location | None = None
        for loaded in self.components:
            for index, declaration in enumerate(loaded.component.interface):
                if declaration.definition.name != name:
                    continue
                location = loaded.declaration_location(index)
                if declaration.scope.is_producer:
                    return location
                fallback = fallback or location
        return fallback


def load_dictionary(path: Path, bag: DiagnosticBag) -> DataDictionary | None:
    """Read a data dictionary that ``ddd dump`` wrote earlier.

    The counterpart of :func:`load_workspace`: it takes the resolved form rather than the
    description files, which is what makes a published dictionary usable as a baseline long
    after the sources of that delivery have moved on.
    """
    text = _read_text(path, bag, None)
    if text is None:
        return None

    # The version is read before the document is validated, not after. A dictionary from a
    # later DDD is precisely one that carries fields this version does not know, and the
    # contract forbids unknown fields - so validating first would answer "extra inputs are
    # not permitted", which tells the reader nothing about what actually happened. Reading it
    # anyway is not an option either: the parts this version does understand would compare
    # clean and the rest would silently count as unchanged.
    if not _dictionary_format_is_supported(text, path, bag):
        return None

    try:
        return DataDictionary.model_validate_json(text)
    except ValidationError as error:
        _report_validation_error(path, error, bag)
        return None


def _dictionary_format_is_supported(text: str, path: Path, bag: DiagnosticBag) -> bool:
    """Whether the ``format`` of a dumped dictionary is one this version can read.

    Tolerant about everything except the version itself: a document that is not json, or not
    an object, or carries no ``format``, is left to the real validation to report properly.
    """
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return True
    if not isinstance(data, dict):
        return True
    found = data.get("format", DICTIONARY_FORMAT)
    if not isinstance(found, int) or isinstance(found, bool) or found <= DICTIONARY_FORMAT:
        return True
    bag.add(
        "schema",
        f"this dictionary is in format {found}, and this DDD understands up to "
        f"{DICTIONARY_FORMAT}; use a newer DDD to read it",
        Location(path, "format"),
    )
    return False


def load_workspace(path: Path, bag: DiagnosticBag) -> Workspace | None:
    """Load ``path`` (a project or a single component file) and everything it includes.

    Returns ``None`` only when the root file itself is unusable; every other problem
    is reported through ``bag`` so that as many findings as possible are collected
    in one run.
    """
    return _Loader(bag).load(path)


class _Loader:
    def __init__(self, bag: DiagnosticBag) -> None:
        self._bag = bag
        self._components: list[LoadedComponent] = []
        self._projects: list[LoadedProject] = []
        self._components_by_name: dict[str, LoadedComponent] = {}
        self._types_by_name: dict[str, LoadedType] = {}
        self._units_by_name: dict[str, LoadedUnit] = {}
        self._sections_by_name: dict[str, LoadedSection] = {}
        self._rasters_by_name: dict[str, LoadedRaster] = {}
        self._constants_by_name: dict[str, LoadedConstant] = {}
        self._seen_paths: set[Path] = set()
        self._read_paths: set[Path] = set()
        self._plugins: list[Plugin] = []
        self._plugins_by_name: dict[str, LoadedPlugin] = {}
        self._project_blocks: dict[str, tuple[dict[str, Any], Location]] = {}

    def load(self, path: Path) -> Workspace | None:
        root = _resolve(path)
        data = self._read_json(root, origin=None)
        if data is None:
            return None
        self._check_extension(root)
        kind = self._detect_kind(root, data)
        if kind is None:
            return None

        refusal = _INCLUDE_ONLY_KINDS.get(kind)
        if refusal is not None:
            self._bag.add("file-kind", refusal, Location(root))
            return None

        if kind == "component":
            component = self._load_component(root, data, parents=())
            if component is None:
                return None
            # The types and constants the component declares inline resolve in a run on the
            # component alone, which is what makes a self-contained library file listable
            # and checkable by itself. Standalone vocabularies cannot reach such a run - only
            # a project lists them - so those registries are left at their empty defaults.
            self._validate_blocks(root)
            return Workspace(
                root=root,
                name=component.name,
                description=component.component.description,
                components=tuple(self._components),
                projects=(),
                types=tuple(sorted(self._types_by_name.values(), key=lambda entry: entry.name)),
                constants=tuple(
                    sorted(self._constants_by_name.values(), key=lambda entry: entry.name)
                ),
                read_paths=tuple(sorted(self._read_paths)),
                plugins=tuple(self._plugins),
                project_extensions={
                    name: block for name, (block, _) in self._project_blocks.items()
                },
            )

        project = self._load_project(root, data, parents=(), stack=())
        if project is None:
            return None
        self._validate_blocks(root)
        return Workspace(
            root=root,
            name=project.name,
            description=project.project.description,
            components=tuple(self._components),
            projects=tuple(self._projects),
            types=tuple(sorted(self._types_by_name.values(), key=lambda entry: entry.name)),
            units=tuple(sorted(self._units_by_name.values(), key=lambda entry: entry.unit)),
            sections=tuple(
                sorted(self._sections_by_name.values(), key=lambda entry: entry.section)
            ),
            rasters=tuple(sorted(self._rasters_by_name.values(), key=lambda entry: entry.raster)),
            constants=tuple(sorted(self._constants_by_name.values(), key=lambda entry: entry.name)),
            read_paths=tuple(sorted(self._read_paths)),
            plugins=tuple(self._plugins),
            project_extensions={name: block for name, (block, _) in self._project_blocks.items()},
        )

    def _read_json(self, path: Path, origin: Location | None) -> dict[str, Any] | None:
        # Recorded before anything can go wrong with it: a file that turns out to be
        # unreadable, malformed or rejected is still one this project is built out of, and a
        # build system has to run DDD again when it changes - especially then.
        self._read_paths.add(path)
        text = _read_text(path, self._bag, origin)
        if text is None:
            return None

        try:
            data = json.loads(
                text,
                parse_constant=_reject_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except json.JSONDecodeError as error:
            self._bag.add(
                "json-syntax",
                error.msg,
                Location(path, line=error.lineno, column=error.colno),
            )
            return None
        except RecursionError:
            # A document nested thousands of levels deep. Python gives up on it, and it has
            # to give up as a finding rather than as a traceback.
            self._bag.add("json-syntax", "the json is nested too deeply to read", Location(path))
            return None
        except ValueError as error:
            self._bag.add("json-syntax", str(error), Location(path))
            return None

        if not isinstance(data, dict):
            self._bag.add(
                "file-kind",
                f"expected a json object at the top level, found {type(data).__name__}",
                Location(path),
            )
            return None
        return data

    def _check_extension(self, path: Path) -> None:
        if not path.name.lower().endswith(DDD_SUFFIX):
            self._bag.add(
                "file-extension",
                f"'{path.name}' is a DDD description file and has to be named '*{DDD_SUFFIX}'",
                Location(path),
            )

    def _detect_kind(self, path: Path, data: dict[str, Any]) -> str | None:
        present = [key for key in FILE_KINDS if key in data]
        if len(present) > 1:
            listed = " and ".join(f"'{key}'" for key in present)
            self._bag.add(
                "file-kind",
                f"file has {listed} at the top level; it must have exactly one",
                Location(path),
            )
            return None
        if present:
            return present[0]
        keys = ", ".join(sorted(data)) or "none"
        offered = ", ".join(f"'{kind}'" for kind in FILE_KINDS)
        self._bag.add(
            "file-kind",
            f"missing top level key, one of {offered} (found: {keys})",
            Location(path),
        )
        return None

    def _load_component(
        self, path: Path, data: dict[str, Any], parents: tuple[str, ...]
    ) -> LoadedComponent | None:
        try:
            model = ComponentFile.model_validate(data)
        except ValidationError as error:
            self._report_validation_error(path, error)
            return None

        loaded = LoadedComponent(path=path, component=model.component, parents=parents)
        previous = self._components_by_name.get(loaded.name)
        if previous is not None:
            self._bag.add(
                "duplicate-component",
                f"component '{loaded.name}' is already declared",
                loaded.location(),
                notes=[("first declared here", previous.location())],
            )
            return None
        self._components_by_name[loaded.name] = loaded
        self._components.append(loaded)
        self._register_embedded(loaded)
        return loaded

    def _register_embedded(self, loaded: LoadedComponent) -> None:
        """Register the types and constants a component declares inline.

        Into the same registries the standalone files feed, at the moment the component
        loads, so that declaring a name twice is refused with a note at whichever home
        declared it first - embedded against embedded, embedded against standalone, and the
        other way around, all through the one duplicate rule. Only the location differs:
        ``component.types[0]`` instead of ``types[0]``.
        """
        component = loaded.component
        for index, declared_type in enumerate(component.types or ()):
            self._register(
                LoadedType(loaded.path, index, declared_type, container="component.types"),
                key=lambda entry: entry.name,
                location=lambda entry: entry.location(),
                registry=self._types_by_name,
                noun="type",
            )
        for index, declared_constant in enumerate(component.constants or ()):
            self._register(
                LoadedConstant(
                    loaded.path, index, declared_constant, container="component.constants"
                ),
                key=lambda entry: entry.name,
                location=lambda entry: entry.location(),
                registry=self._constants_by_name,
                noun="constant",
            )

    def _load_vocabulary[ModelT: BaseModel, EntryT, LoadedT](
        self,
        path: Path,
        data: dict[str, Any],
        *,
        file_model: type[ModelT],
        entries: Callable[[ModelT], tuple[EntryT, ...]],
        wrap: Callable[[Path, int, EntryT], LoadedT],
        key: Callable[[LoadedT], str],
        location: Callable[[LoadedT], Location],
        registry: dict[str, LoadedT],
        noun: str,
    ) -> None:
        """Read one vocabulary file and register each entry it declares under its key.

        The one shape behind the vocabulary loaders below: validate the file, wrap every entry
        together with where it was declared, and refuse the second declaration of a key as
        ``duplicate-<noun>`` - with a note at the first - rather than letting one of them
        quietly win.
        """
        try:
            model = file_model.model_validate(data)
        except ValidationError as error:
            self._report_validation_error(path, error)
            return

        for index, declared in enumerate(entries(model)):
            self._register(
                wrap(path, index, declared),
                key=key,
                location=location,
                registry=registry,
                noun=noun,
            )

    def _register[LoadedT](
        self,
        loaded: LoadedT,
        *,
        key: Callable[[LoadedT], str],
        location: Callable[[LoadedT], Location],
        registry: dict[str, LoadedT],
        noun: str,
    ) -> None:
        """Register one declared entry under its key, or refuse the second declaration.

        The registries are shared by the standalone files and the entries a component
        declares inline, so the ``duplicate-<noun>`` rule - refused with a note at the
        first - holds across the homes without either knowing about the other.
        """
        previous = registry.get(key(loaded))
        if previous is not None:
            self._bag.add(
                f"duplicate-{noun}",
                f"{noun} '{key(loaded)}' is already declared",
                location(loaded),
                notes=[("first declared here", location(previous))],
            )
            return
        registry[key(loaded)] = loaded

    def _load_types(self, path: Path, data: dict[str, Any]) -> None:
        """Read a type description and register what it declares.

        A type is registered under its name, so the second file to declare ``Engine_t`` is
        refused rather than quietly winning or losing: which of two layouts the generated c
        would get is not something an include order should decide.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=TypesFile,
            entries=lambda model: model.types,
            wrap=LoadedType,
            key=lambda loaded: loaded.name,
            location=lambda loaded: loaded.location(),
            registry=self._types_by_name,
            noun="type",
        )

    def _load_units(self, path: Path, data: dict[str, Any]) -> None:
        """Read a unit vocabulary and register what it declares.

        A unit is registered under its spelling, so the second file to declare ``Nm`` is
        refused rather than merged: two files declaring one unit is either a copy that will
        drift or a disagreement about its description, and neither is worth keeping quiet.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=UnitsFile,
            entries=lambda model: model.units,
            wrap=LoadedUnit,
            key=lambda loaded: loaded.unit,
            location=lambda loaded: loaded.location(),
            registry=self._units_by_name,
            noun="unit",
        )

    def _load_sections(self, path: Path, data: dict[str, Any]) -> None:
        """Read a section description and register what it declares.

        A section is registered under its name; the second file to declare ``.calib`` is
        refused rather than merged: two files declaring one section is either a copy that
        will drift or a disagreement about its properties, and neither is worth keeping
        quiet.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=SectionsFile,
            entries=lambda model: model.sections,
            wrap=LoadedSection,
            key=lambda loaded: loaded.section,
            location=lambda loaded: loaded.location(),
            registry=self._sections_by_name,
            noun="section",
        )

    def _load_rasters(self, path: Path, data: dict[str, Any]) -> None:
        """Read a raster description and register what it declares.

        A raster is registered under its name; the second file to declare ``10ms`` is refused
        rather than merged, because the two would carry different event numbers and the one
        that won would depend on which file loaded first.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=RastersFile,
            entries=lambda model: model.rasters,
            wrap=LoadedRaster,
            key=lambda loaded: loaded.raster,
            location=lambda loaded: loaded.location(),
            registry=self._rasters_by_name,
            noun="raster",
        )

    def _load_constants(self, path: Path, data: dict[str, Any]) -> None:
        """Read a constant vocabulary and register what it declares.

        A constant is registered under its name; the second file to declare
        ``PRESSURE_CELLS`` is refused rather than merged: two files declaring one constant
        is either a copy that will drift or a disagreement about its value, and a size that
        depends on which file loads first is exactly what the vocabulary exists to prevent.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=ConstantsFile,
            entries=lambda model: model.constants,
            wrap=LoadedConstant,
            key=lambda loaded: loaded.name,
            location=lambda loaded: loaded.location(),
            registry=self._constants_by_name,
            noun="constant",
        )

    def _load_project(
        self,
        path: Path,
        data: dict[str, Any],
        parents: tuple[str, ...],
        stack: tuple[Path, ...],
    ) -> LoadedProject | None:
        try:
            model = ProjectFile.model_validate(data)
        except ValidationError as error:
            self._report_validation_error(path, error)
            return None

        loaded = LoadedProject(path=path, project=model.project, parents=parents)
        self._projects.append(loaded)

        for index, spelling in enumerate(model.project.plugins):
            self._load_plugin(spelling, Location(path, f"project.plugins[{index}]"), path.parent)
        for name, block in model.project.extensions.items():
            self._register_settings(name, block, Location(path, f"project.extensions.{name}"))

        child_parents = (*parents, loaded.name)
        child_stack = (*stack, path)
        for index, pattern in enumerate(model.project.includes):
            origin = Location(path, f"project.includes[{index}]")
            for included in self._expand(path, pattern, origin, {path}):
                self._load_include(included, origin, child_parents, child_stack)
        return loaded

    def _load_plugin(self, spelling: str, origin: Location, base: Path) -> None:
        """Import one plugin the project names, or report why it could not be.

        Both failures have a fixed severity, like ``file-not-found`` and ``schema``: a project
        cannot be interpreted without the plugins it names, so there is nothing to relax.
        """
        try:
            plugin = load_plugin(spelling, base)
        except PluginNotFoundError as error:
            self._bag.add("plugin-not-found", str(error), origin)
            return
        except PluginInvalidError as error:
            self._bag.add("plugin-invalid", str(error), origin)
            return
        previous = self._plugins_by_name.get(plugin.name)
        if previous is not None:
            # The same module named twice loads to one object and is nothing; a different
            # module claiming a name in use is the second of two plugins, refused.
            if previous.plugin is not plugin:
                self._bag.add(
                    "plugin-invalid",
                    f"plugin '{plugin.name}' is already provided by '{previous.spelling}'",
                    origin,
                    notes=[("first named here", previous.origin)],
                )
            return
        self._plugins_by_name[plugin.name] = LoadedPlugin(plugin, spelling, origin)
        self._plugins.append(plugin)
        self._bag.register(plugin.checks)

    def _register_settings(self, name: str, block: dict[str, Any], location: Location) -> None:
        previous = self._project_blocks.get(name)
        if previous is not None:
            self._bag.add(
                "schema",
                f"the settings of plugin '{name}' are already stated",
                location,
                notes=[("first stated here", previous[1])],
            )
            return
        self._project_blocks[name] = (block, location)

    def _validate_blocks(self, root: Path) -> None:
        """Every extension block against the model of the plugin that owns it.

        One pass at the end rather than at each file, because a component included before
        the sub-project that names its plugin would otherwise be refused for a block that is
        about to become valid. A block on a consumer is validated too: whose claim it is comes
        later, in the analysis, and a typo is a typo either way.
        """
        plugins = {name: loaded.plugin for name, loaded in self._plugins_by_name.items()}
        for name, (block, location) in sorted(self._project_blocks.items()):
            self._validate_block(plugins.get(name), name, block, location, on_project=True)
        for plugin in self._plugins:
            # A plugin whose settings have a required field, in a project stating none: the
            # finding belongs where the block would be written.
            if plugin.project_model is not None and plugin.name not in self._project_blocks:
                location = Location(root, f"project.extensions.{plugin.name}")
                self._validate_block(plugin, plugin.name, {}, location, on_project=True)
        for loaded in self._components:
            for index, declaration in enumerate(loaded.component.interface):
                for name, block in declaration.definition.extensions.items():
                    suffix = f"definition.extensions.{name}"
                    location = loaded.declaration_location(index, suffix)
                    self._validate_block(plugins.get(name), name, block, location, on_project=False)

    def _validate_block(
        self,
        plugin: Plugin | None,
        name: str,
        block: dict[str, Any],
        location: Location,
        *,
        on_project: bool,
    ) -> None:
        if plugin is None:
            self._bag.add(
                "unknown-extension",
                f"'{name}' names no plugin this project loads; a block only means something "
                f"to the plugin that owns it",
                location,
            )
            return
        model = plugin.project_model if on_project else plugin.object_model
        if model is None:
            where = "the project" if on_project else "a definition"
            self._bag.add(
                "schema", f"plugin '{name}' takes no 'extensions' block on {where}", location
            )
            return
        try:
            model.model_validate(block)
        except ValidationError as error:
            _report_validation_error(location.path, error, self._bag, prefix=location.pointer)

    def _expand(
        self, source: Path, pattern: str, origin: Location, excluded: set[Path]
    ) -> list[Path]:
        """Resolve one include entry into a list of existing files."""
        raw = Path(pattern)
        if not any(character in pattern for character in _GLOB_CHARACTERS):
            candidate = raw if raw.is_absolute() else source.parent / raw
            return [_resolve(candidate)]

        # The anchor decides where a pattern starts, not is_absolute(): on Windows both the
        # rooted '/shared/*.ddd.json' and the drive relative 'C:*.ddd.json' carry an anchor
        # while reporting is_absolute() as false, and handing either to Path.glob unchanged
        # makes pathlib refuse a non-relative pattern.
        anchor = raw.anchor
        base = Path(anchor) if anchor else source.parent
        relative = raw.relative_to(anchor) if anchor else raw
        try:
            found = list(base.glob(relative.as_posix()))
        except (OSError, ValueError, NotImplementedError) as error:
            self._bag.add("include-empty", f"cannot expand pattern '{pattern}': {error}", origin)
            return []
        matches = sorted(
            resolved
            for match in found
            if match.is_file() and (resolved := _resolve(match)) not in excluded
        )
        if not matches:
            self._bag.add("include-empty", f"pattern '{pattern}' matches no file", origin)
        return matches

    def _load_include(
        self,
        path: Path,
        origin: Location,
        parents: tuple[str, ...],
        stack: tuple[Path, ...],
    ) -> None:
        if path in stack:
            chain = " -> ".join(item.name for item in (*stack, path))
            self._bag.add("include-cycle", f"include cycle: {chain}", origin)
            return
        if path in self._seen_paths:
            # Diamond shaped include graphs are fine, the file is simply used once.
            return
        self._seen_paths.add(path)

        data = self._read_json(path, origin)
        if data is None:
            return
        self._check_extension(path)
        kind = self._detect_kind(path, data)
        if kind == "component":
            self._load_component(path, data, parents)
        elif kind == "project":
            self._load_project(path, data, parents, stack)
        elif kind == "types":
            self._load_types(path, data)
        elif kind == "units":
            self._load_units(path, data)
        elif kind == "sections":
            self._load_sections(path, data)
        elif kind == "rasters":
            self._load_rasters(path, data)
        elif kind == "constants":
            self._load_constants(path, data)

    def _report_validation_error(self, path: Path, error: ValidationError) -> None:
        _report_validation_error(path, error, self._bag)


def _read_text(path: Path, bag: DiagnosticBag, origin: Location | None) -> str | None:
    """Read a file, reporting anything that stops it instead of raising.

    Every failure has to come back as a located finding: the loader's promise is that one
    run reports as much as it can, and an exception escaping from here would end the run
    with a bare python message and throw away everything already collected.

    ``utf-8-sig`` rather than ``utf-8``: a byte order mark is what several Windows editors
    and PowerShell redirection put in front of a file, and refusing those would be pedantry
    about a file that is otherwise perfectly good json.
    """
    where = origin or Location(path)
    try:
        if path.is_dir():
            bag.add(
                "file-not-found",
                f"'{path.as_posix()}' is a directory, not a description file",
                where,
            )
            return None
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        bag.add("file-not-found", f"file '{path.as_posix()}' does not exist", where)
    except UnicodeDecodeError as error:
        bag.add(
            "json-syntax",
            f"'{path.as_posix()}' is not valid utf-8 (byte {error.start}): DDD description "
            f"files are utf-8, so save it in that encoding",
            where,
        )
    except OSError as error:
        bag.add(
            "file-not-found",
            f"cannot read '{path.as_posix()}': {error.strerror or error}",
            where,
        )
    except ValueError as error:
        # A path the operating system cannot even represent, e.g. one with a NUL byte in it.
        bag.add("file-not-found", f"cannot read '{path.as_posix()}': {error}", where)
    return None


def _report_validation_error(
    path: Path, error: ValidationError, bag: DiagnosticBag, prefix: str = ""
) -> None:
    """One ``schema`` finding per place; ``prefix`` is the pointer of a nested document."""
    for item in _one_per_place(_meaningful(error.errors(include_url=False))):
        message = item["msg"]
        if item["type"] != "missing":
            message = f"{message} (got: {_short(item.get('input'))})"
        pointer = ".".join(part for part in (prefix, _pointer(item["loc"])) if part)
        bag.add("schema", message, Location(path, pointer))


def _one_per_place(items: list[Any]) -> list[Any]:
    """One finding per place, however many ways the value failed to be what was wanted.

    A union that is not discriminated fails once per branch, so a mistyped ``datatype`` arrives
    as two errors about one key: it is not one of the eleven base datatypes, *and* it does not
    look like a type name. Both are true and the reader needs neither of them twice.

    The first is kept, because pydantic reports the branches in the order they are declared and
    that order is chosen to put the likely reading first - for ``datatype``, "one of these
    eleven" says far more than a regular expression does.
    """
    kept: dict[str, Any] = {}
    for item in items:
        kept.setdefault(_pointer(item["loc"]), item)
    return list(kept.values())


def _meaningful(items: list[Any]) -> list[Any]:
    """Drop the findings that are only consequences of another finding in the same run.

    A list whose single entry fails validation is dropped by pydantic and then reported as
    too short as well, so one mistake arrives as two errors: the useful one about the entry,
    and 'Tuple should have at least 1 item after validation, not 0' about the list holding
    it. Reporting both invites the reader to go looking for a second problem that is not
    there.
    """
    locations = {tuple(item["loc"]) for item in items}

    def explained_by_a_deeper_finding(location: tuple[Any, ...]) -> bool:
        # Strictly deeper: a list that is empty because it was written empty has no finding
        # under it, and has to keep reporting itself.
        return any(
            len(other) > len(location) and other[: len(location)] == location for other in locations
        )

    return [
        item
        for item in items
        if item["type"] != "too_short" or not explained_by_a_deeper_finding(tuple(item["loc"]))
    ]


def _resolve(path: Path) -> Path:
    """Absolute, symlink free path; works for files that do not exist yet.

    A path the operating system refuses to even look at - one with a NUL byte in it, say -
    is handed back unresolved rather than raising. Where that refusal surfaces is otherwise
    a property of the platform: linux rejects such a path in ``resolve()`` while Windows
    carries it as far as the read. Degrading here puts every one of them through the same
    handler in :func:`_read_text`, so the run ends with one located finding on both.
    """
    try:
        return Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return Path(path)


def _pointer(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    for item in loc:
        if item in _UNION_TAGS or _is_branch_tag(item):
            # pydantic reports the selected variant of a tagged union as a path segment, and
            # the tried branch of a plain one the same way; 'definition.measurement.datatype'
            # and 'datatype.str-enum[Datatype]' would both only confuse the reader.
            continue
        if isinstance(item, int):
            parts.append(f"[{item}]")
        elif parts:
            parts.append(f".{item}")
        else:
            parts.append(str(item))
    return "".join(parts)


_BARE_TYPE_TAGS = frozenset({"bool", "int", "float", "str", "none", "bytes"})
"""How pydantic names the branch of a union that is a plain python type.

The branches of an ``init`` value are spelled ``bool``, ``int`` and ``float``, which look like
keys and are not: no key of any file format is called that, while a finding located at
``init.bool`` names a place the document does not have.
"""


def _is_branch_tag(item: int | str) -> bool:
    """Whether a path segment names a union branch rather than a key of the document.

    pydantic spells most of those as ``str-enum[Datatype]`` or ``constrained-str``, neither of
    which can be a key: a key is an identifier, and these are not. Recognised by shape rather
    than by a list of names, so a new branch needs nothing added here - except a branch that
    is a bare python type, which is spelled as one word and listed above.
    """
    if not isinstance(item, str):
        return False
    return item in _BARE_TYPE_TAGS or not item.replace("_", "").replace("$", "").isalnum()


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
