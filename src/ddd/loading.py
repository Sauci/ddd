"""Reading a project/component tree from disk into the pydantic contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import DICTIONARY_FORMAT, DataDictionary
from ddd.models import (
    AnyDataObject,
    AnyType,
    Component,
    ComponentFile,
    Conversion,
    NamingConvention,
    NamingFile,
    Project,
    ProjectFile,
    StructType,
    TypesFile,
    discriminator_tags,
)

DDD_SUFFIX = ".ddd.json"
"""Every project and component description file carries this extension.

In a large repository a plain ``*.json`` says nothing about who owns the file; the
double extension makes a DDD description recognisable at a glance and lets build
scripts and editors match them with a single pattern.
"""

_GLOB_CHARACTERS = frozenset("*?[")

FILE_KINDS = ("project", "component", "types")
"""Top level keys that identify a description file, in the order they are offered.

A naming convention is not among them: it is pointed at by the ``naming`` key of a project
rather than included, and is reported separately when it turns up in ``includes``.
"""

_UNION_TAGS = discriminator_tags(AnyDataObject, Conversion)
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
    """Position in the ``types`` list of its file, which is what the location points at."""

    declared: AnyType
    """The entry itself: a structure or a scalar type."""

    @property
    def name(self) -> str:
        return self.declared.name

    @property
    def structure(self) -> StructType | None:
        """The entry as a structure, or nothing if it names a scalar."""
        return self.declared if isinstance(self.declared, StructType) else None

    def location(self, suffix: str = "") -> Location:
        pointer = f"types[{self.index}]"
        if suffix:
            pointer = f"{pointer}.{suffix}"
        return Location(self.path, pointer)


@dataclass(frozen=True, slots=True)
class Workspace:
    """Everything DDD knows after reading the file tree."""

    root: Path
    name: str
    description: str
    components: tuple[LoadedComponent, ...]
    projects: tuple[LoadedProject, ...]
    types: tuple[LoadedType, ...] = ()
    """The structured datatypes the project declares, sorted by name.

    Sorted rather than in include order so that a project produces the same output whichever
    way its ``includes`` happen to expand; the order of *members* inside a structure is the
    author's and is preserved, because that one decides the layout.
    """

    naming: NamingConvention | None = None
    """The convention the root project points at, if it points at one."""

    naming_path: Path | None = None
    """Where that convention was read from; part of what the project is built out of."""

    read_paths: tuple[Path, ...] = ()
    """Every file the loader opened, whatever came of it.

    Deliberately not derived from ``components`` and ``projects``: a file that was read and
    then rejected - a duplicate component name, a schema error - is still a file this project
    is built out of, and editing it has to make the build run DDD again. Leaving it out is how
    a build system ends up never noticing the fix.
    """

    def sources(self) -> tuple[Path, ...]:
        """Every file that was read to build this workspace, sorted and without duplicates.

        What a build system needs in order to know when to run DDD again: the root file
        alone is not enough, because a project pulls its components in through ``includes``.
        """
        paths = {self.root, *self.read_paths}
        if self.naming_path is not None:
            paths.add(self.naming_path)
        return tuple(sorted(paths))


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
        self._seen_paths: set[Path] = set()
        self._read_paths: set[Path] = set()

    def load(self, path: Path) -> Workspace | None:
        root = _resolve(path)
        data = self._read_json(root, origin=None)
        if data is None:
            return None
        self._check_extension(root)
        kind = self._detect_kind(root, data)
        if kind is None:
            return None

        if kind == "types":
            # Same reasoning as a naming convention handed in directly: a structure is not a
            # project, so there is nothing to resolve or generate from it on its own. Validating
            # it against the published schema is what an editor is for.
            self._bag.add(
                "file-kind",
                "this is a structured datatype description; list it in the 'includes' of the "
                "project that uses it instead of analysing it on its own",
                Location(root),
            )
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
                read_paths=tuple(sorted(self._read_paths)),
            )

        project = self._load_project(root, data, parents=(), stack=())
        if project is None:
            return None
        naming_path = self._naming_path(project)
        return Workspace(
            root=root,
            name=project.name,
            description=project.project.description,
            components=tuple(self._components),
            projects=tuple(self._projects),
            types=tuple(sorted(self._types_by_name.values(), key=lambda entry: entry.name)),
            naming=load_convention(naming_path, self._bag) if naming_path else None,
            naming_path=naming_path,
            read_paths=tuple(sorted(self._read_paths)),
        )

    def _naming_path(self, project: LoadedProject) -> Path | None:
        """The convention of the root project; a sub-project cannot impose one on its parent."""
        if project.project.naming is None:
            return None
        return _resolve(project.path.parent / project.project.naming)

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
        if "naming" in data:
            self._bag.add(
                "file-kind",
                "this is a naming convention; point the 'naming' key of the project at it "
                "instead of listing it in 'includes'",
                Location(path),
            )
            return None
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
                f"component '{loaded.name}' is declared twice",
                loaded.location(),
                notes=[("first declared here", previous.location())],
            )
            return None
        self._components_by_name[loaded.name] = loaded
        self._components.append(loaded)
        return loaded

    def _load_types(self, path: Path, data: dict[str, Any]) -> None:
        """Read a type description and register what it declares.

        A type is registered under its name, so the second file to declare ``Engine_t`` is
        refused rather than quietly winning or losing: which of two layouts the generated c
        would get is not something an include order should decide.
        """
        try:
            model = TypesFile.model_validate(data)
        except ValidationError as error:
            self._report_validation_error(path, error)
            return

        for index, declared in enumerate(model.types):
            loaded = LoadedType(path=path, index=index, declared=declared)
            previous = self._types_by_name.get(loaded.name)
            if previous is not None:
                self._bag.add(
                    "duplicate-type",
                    f"type '{loaded.name}' is declared twice",
                    loaded.location(),
                    notes=[("first declared here", previous.location())],
                )
                continue
            self._types_by_name[loaded.name] = loaded

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
        # A wildcard next to the project file also matches the convention that project points
        # at. It is not an include, and the layout the manual shows puts it exactly there, so
        # it is skipped rather than reported as a file of the wrong kind.
        naming = model.project.naming
        excluded = {path} | ({_resolve(path.parent / naming)} if naming else set())
        for index, pattern in enumerate(model.project.includes):
            origin = Location(path, f"project.includes[{index}]")
            for included in self._expand(path, pattern, origin, excluded):
                self._load_include(included, origin, child_parents, child_stack)
        return loaded

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


def _report_validation_error(path: Path, error: ValidationError, bag: DiagnosticBag) -> None:
    for item in _one_per_place(_meaningful(error.errors(include_url=False))):
        message = item["msg"]
        if item["type"] != "missing":
            message = f"{message} (got: {_short(item.get('input'))})"
        bag.add("schema", message, Location(path, _pointer(item["loc"])))


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


def _is_branch_tag(item: int | str) -> bool:
    """Whether a path segment names a union branch rather than a key of the document.

    pydantic spells those as ``str-enum[Datatype]`` or ``constrained-str``, neither of which
    can be a key: a key is an identifier, and these are not. Recognised by shape rather than
    by a list of names, so a new branch needs nothing added here.
    """
    return isinstance(item, str) and not item.replace("_", "").replace("$", "").isalnum()


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
