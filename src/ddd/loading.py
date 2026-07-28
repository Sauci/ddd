"""Reading a project/component tree from disk into the pydantic contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import DataDictionary
from ddd.models import (
    AnyDataObject,
    Component,
    ComponentFile,
    Conversion,
    NamingConvention,
    NamingFile,
    Project,
    ProjectFile,
    discriminator_tags,
)

DDD_SUFFIX = ".ddd.json"
"""Every project and component description file carries this extension.

In a large repository a plain ``*.json`` says nothing about who owns the file; the
double extension makes a DDD description recognisable at a glance and lets build
scripts and editors match them with a single pattern.
"""

_GLOB_CHARACTERS = frozenset("*?[")

_UNION_TAGS = discriminator_tags(AnyDataObject, Conversion)
"""Discriminator values pydantic inserts into the error location of a tagged union."""


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
        pointer = f"component.declarations[{index}]"
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
class Workspace:
    """Everything DDD knows after reading the file tree."""

    root: Path
    name: str
    description: str
    components: tuple[LoadedComponent, ...]
    projects: tuple[LoadedProject, ...]
    naming: NamingConvention | None = None
    """The convention the root project points at, if it points at one."""


def load_convention(path: Path, bag: DiagnosticBag) -> NamingConvention | None:
    """Read a naming convention description."""
    text = _read_text(path, bag, None)
    if text is None:
        return None
    try:
        return NamingFile.model_validate_json(text).naming
    except ValidationError as error:
        _report_validation_error(path, error, bag)
        return None


def load_dictionary(path: Path, bag: DiagnosticBag) -> DataDictionary | None:
    """Read a data dictionary that ``ddd dump`` wrote earlier.

    The counterpart of :func:`load_workspace`: it takes the resolved form rather than the
    description files, which is what makes a published dictionary usable as a baseline long
    after the sources of that delivery have moved on.
    """
    text = _read_text(path, bag, None)
    if text is None:
        return None
    try:
        return DataDictionary.model_validate_json(text)
    except ValidationError as error:
        _report_validation_error(path, error, bag)
        return None


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
        self._seen_paths: set[Path] = set()

    # -- entry point --------------------------------------------------------

    def load(self, path: Path) -> Workspace | None:
        root = _resolve(path)
        data = self._read_json(root, origin=None)
        if data is None:
            return None
        self._check_extension(root)
        kind = self._detect_kind(root, data)
        if kind is None:
            return None

        if kind == "component":
            component = self._load_component(root, data, parents=())
            if component is None:
                return None
            return Workspace(
                root=root,
                name=component.name,
                description=component.component.description,
                components=tuple(self._components),
                projects=(),
            )

        project = self._load_project(root, data, parents=(), stack=())
        if project is None:
            return None
        return Workspace(
            root=root,
            name=project.name,
            description=project.project.description,
            components=tuple(self._components),
            projects=tuple(self._projects),
            naming=self._load_naming(project),
        )

    def _load_naming(self, project: LoadedProject) -> NamingConvention | None:
        """The convention of the root project; a sub-project cannot impose one on its parent."""
        if project.project.naming is None:
            return None
        path = project.path.parent / project.project.naming
        return load_convention(_resolve(path), self._bag)

    # -- file handling ------------------------------------------------------

    def _read_json(self, path: Path, origin: Location | None) -> dict[str, Any] | None:
        text = _read_text(path, self._bag, origin)
        if text is None:
            return None

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            self._bag.add(
                "json-syntax",
                error.msg,
                Location(path, line=error.lineno, column=error.colno),
            )
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
        has_project = "project" in data
        has_component = "component" in data
        if has_project and has_component:
            self._bag.add(
                "file-kind",
                "file has both a 'project' and a 'component' key; it must have exactly one",
                Location(path),
            )
            return None
        if has_project:
            return "project"
        if has_component:
            return "component"
        if "naming" in data:
            self._bag.add(
                "file-kind",
                "this is a naming convention; point the 'naming' key of the project at it "
                "instead of listing it in 'includes'",
                Location(path),
            )
            return None
        keys = ", ".join(sorted(data)) or "none"
        self._bag.add(
            "file-kind",
            f"missing top level key 'project' or 'component' (found: {keys})",
            Location(path),
        )
        return None

    # -- components ---------------------------------------------------------

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
                f"component '{loaded.name}' is declared twice",
                loaded.location(),
                notes=[("first declared here", previous.location())],
            )
            return None
        self._components_by_name[loaded.name] = loaded
        self._components.append(loaded)
        return loaded

    # -- projects -----------------------------------------------------------

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

        child_parents = (*parents, loaded.name)
        child_stack = (*stack, path)
        for index, pattern in enumerate(model.project.includes):
            origin = Location(path, f"project.includes[{index}]")
            for included in self._expand(path, pattern, origin):
                self._load_include(included, origin, child_parents, child_stack)
        return loaded

    def _expand(self, source: Path, pattern: str, origin: Location) -> list[Path]:
        """Resolve one include entry into a list of existing files."""
        raw = Path(pattern)
        if not any(character in pattern for character in _GLOB_CHARACTERS):
            candidate = raw if raw.is_absolute() else source.parent / raw
            return [_resolve(candidate)]

        base = Path(raw.anchor) if raw.is_absolute() else source.parent
        relative = raw.relative_to(raw.anchor) if raw.is_absolute() else raw
        matches = sorted(
            _resolve(match)
            for match in base.glob(relative.as_posix())
            if match.is_file() and _resolve(match) != source
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

    # -- error reporting ----------------------------------------------------

    def _report_validation_error(self, path: Path, error: ValidationError) -> None:
        _report_validation_error(path, error, self._bag)


def _read_text(path: Path, bag: DiagnosticBag, origin: Location | None) -> str | None:
    """Read a file, reporting anything the filesystem refuses instead of raising."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        bag.add(
            "file-not-found", f"file '{path.as_posix()}' does not exist", origin or Location(path)
        )
    except OSError as error:
        bag.add(
            "file-not-found",
            f"cannot read '{path.as_posix()}': {error.strerror or error}",
            origin or Location(path),
        )
    return None


def _report_validation_error(path: Path, error: ValidationError, bag: DiagnosticBag) -> None:
    for item in error.errors(include_url=False):
        message = item["msg"]
        if item["type"] != "missing":
            message = f"{message} (got: {_short(item.get('input'))})"
        bag.add("schema", message, Location(path, _pointer(item["loc"])))


def _resolve(path: Path) -> Path:
    """Absolute, symlink free path; works for files that do not exist yet."""
    return Path(path).expanduser().resolve()


def _pointer(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    for item in loc:
        if item in _UNION_TAGS:
            # pydantic reports the selected variant of a tagged union as a path segment;
            # 'definition.measurement.datatype' would only confuse the reader.
            continue
        if isinstance(item, int):
            parts.append(f"[{item}]")
        elif parts:
            parts.append(f".{item}")
        else:
            parts.append(str(item))
    return "".join(parts)


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
