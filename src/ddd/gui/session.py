"""The project ``ddd gui`` has open, and what its last analysis said about it.

The GUI holds no data of its own: the description files are the project, and a revision is one
analysis of them - the findings, the files it read with a fingerprint of each, and the
dictionary it resolved to. A new revision is made after every edit and whenever a file of the
project changes on disk, which a thread notices by comparing each file's modification time and
size once a second: the standard library has no file watcher, and re-checking a project of
thousands of declarations takes well under a second. A file a wildcard include would match only
once it exists is noticed when something else changes, which is a limit of the preview.

The analysis is the language server's, run the way ``ddd lsp`` runs it: under the severities of
every build record naming the project, or under the defaults when none does.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final

from ddd.build_info import BuildInfo
from ddd.diagnostics import CheckInfo, Diagnostic, Severity
from ddd.editing import FileChange, apply_changes, fingerprint
from ddd.ir import DataDictionary
from ddd.loading import parse_json_text
from ddd.lsp.diagnostics import Run, group_findings, run_build, run_project
from ddd.lsp.discovery import BUILD_DIRECTORY_PATTERNS, discover

KINDS: Final = ("project", "component", "types", "units", "sections", "constants", "rasters")
"""The top-level keys that say what a description file is, as the loader reads them."""

LOAD_CHECKS: Final = frozenset({"file-not-found", "json-syntax", "file-kind", "schema"})
"""The checks whose error on a file means that file did not load."""

SEARCH_DEPTH: Final = 4
"""How many directories below the start the search for project descriptions goes."""

UNKNOWN: Final = (-1, -1)
"""The stamp of a file whose modification time and size were not taken before an analysis read
it: a size no file has, so the next poll finds the file changed and analyses once more."""


@dataclass(frozen=True, slots=True)
class FoundProject:
    """A project the start page offers."""

    path: Path
    name: str | None
    images: tuple[str, ...]
    """The build images a build record names this project for; empty for a file found alone."""


@dataclass(frozen=True, slots=True)
class Found:
    """Every project found under a directory, and the build records that could not be used."""

    root: Path
    projects: tuple[FoundProject, ...]
    refused: tuple[tuple[Path, str], ...]


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One file an analysis read: what it is, whether it loaded, and how much it has to fix."""

    path: Path
    kind: str
    name: str | None
    loaded: bool
    fingerprint: str
    errors: int
    warnings: int
    infos: int


@dataclass(frozen=True, slots=True)
class Filed:
    """A finding and the file it is shown on: both sides of a disagreement are filed."""

    file: Path
    diagnostic: Diagnostic


@dataclass(frozen=True, slots=True)
class Revision:
    """One analysis of the open project."""

    number: int
    project: Path
    builds: tuple[BuildInfo, ...]
    files: tuple[SourceFile, ...]
    findings: tuple[Filed, ...]
    dictionary: DataDictionary | None
    checks: tuple[CheckInfo, ...]
    """The plugin checks the analysis registered, beside the built-in ones every run has."""


@dataclass(frozen=True, slots=True)
class FileContent:
    """A description file as the page reads it: parsed, or the reason it cannot be."""

    path: Path
    fingerprint: str
    data: Any
    error: str | None


class NoProjectError(RuntimeError):
    """Asked about the open project while none is open."""


class NotInProjectError(LookupError):
    """Asked about a file that is not a description file of the open project."""


def find_projects(root: Path, build_directories: Sequence[Path] = ()) -> Found:
    """The projects under ``root``: those a build record names, and the project descriptions a
    bounded walk finds, hidden directories, ``node_modules`` and build trees left out."""
    base = root.resolve()
    refused: dict[Path, str] = {}
    images: dict[Path, list[str]] = {}
    for info in discover(base, build_directories, refused):
        images.setdefault(Path(info.project).resolve(), []).append(info.image)
    paths = sorted(set(images) | set(_descriptions(base)))
    projects = tuple(
        FoundProject(path, _name_in(_read_json(path), "project"), tuple(images.get(path, ())))
        for path in paths
    )
    return Found(base, projects, tuple(sorted(refused.items())))


class Session:
    """One open project at a time, analysed into numbered revisions."""

    def __init__(
        self, root: Path, build_directories: Sequence[Path] = (), *, poll_interval: float = 1.0
    ) -> None:
        self.root = root.resolve()
        self.build_directories = tuple(build_directories)
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._published = threading.Condition()
        self._revision: Revision | None = None
        self._signature: dict[Path, tuple[int, int] | None] = {}
        self._stopping = threading.Event()
        self._poller: threading.Thread | None = None

    @property
    def revision(self) -> Revision | None:
        """The newest revision, or ``None`` while no project is open."""
        return self._revision

    def open(self, project: Path) -> Revision:
        """Open a project description, replacing the project open before it."""
        path = project.resolve()
        if not _is_project(path):
            raise ValueError(f"{project} is not a project description")
        with self._lock:
            return self._publish(self._analysed(path), {})

    def wait(self, after: int, timeout: float) -> Revision | None:
        """The newest revision as soon as it is newer than ``after``, or after ``timeout``."""
        with self._published:
            self._published.wait_for(
                lambda: self._revision is not None and self._revision.number > after, timeout
            )
            return self._revision

    def poll(self) -> bool:
        """Analyse the open project again if a file of it changed on disk; say whether one did."""
        with self._lock:
            revision = self._revision
            stamps = _signature(self._signature)
            if revision is None or stamps == self._signature:
                return False
            self._publish(self._analysed(revision.project), stamps)
            return True

    def start_polling(self) -> None:
        """Poll every ``poll_interval`` seconds on a thread of its own, until :meth:`stop`."""
        if self._poller is None:
            self._poller = threading.Thread(
                target=self._poll_until_stopped, name="ddd-gui-poll", daemon=True
            )
            self._poller.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._poller is not None:
            self._poller.join()

    def read_file(self, path: Path) -> FileContent:
        """A description file of the open project, parsed, with the fingerprint it was read at.

        Parsed by the loader's rule, like every file the session reads: python's own reader
        takes ``NaN``, which went to the page as a value no browser's parser reads, and a key
        spelled twice, which showed the page a file ``ddd check`` refuses as though it loaded.
        """
        target = _source(self._required(), path)
        try:
            data = target.read_bytes()
        except OSError as error:
            return FileContent(target, fingerprint(b""), None, f"{target} cannot be read: {error}")
        try:
            parsed = parse_json_text(data.decode("utf-8-sig"))
        except ValueError as error:
            return FileContent(target, fingerprint(data), None, f"{target} is not json: {error}")
        return FileContent(target, fingerprint(data), parsed, None)

    def edit(self, changes: Sequence[FileChange]) -> tuple[Revision, dict[Path, str]]:
        """Make an edit of description files of the open project, then analyse it again."""
        with self._lock:
            revision = self._required()
            confined = [
                FileChange(_source(revision, pending.path), pending.fingerprint, pending.operations)
                for pending in changes
            ]
            written = apply_changes(confined)
            # After the edit's own write, so the next poll does not take it for somebody else's,
            # and before the analysis, so a save landing while that runs is not taken for seen.
            stamps = _signature(self._signature)
            return self._publish(self._analysed(revision.project), stamps), written

    def _poll_until_stopped(self) -> None:
        while not self._stopping.wait(self.poll_interval):
            try:
                self.poll()
            except Exception as error:
                # A thread that dies here leaves a page that never updates again, and nothing
                # says why: the one line is that reason, and the next poll tries again.
                print(f"ddd gui: checking the project again failed: {error}", file=sys.stderr)

    def _required(self) -> Revision:
        if self._revision is None:
            raise NoProjectError("no project is open")
        return self._revision

    def _analysed(self, project: Path) -> Revision:
        ignored: dict[Path, str] = {}  # the start page is where a refused record is reported
        builds = tuple(
            info
            for info in discover(self.root, self.build_directories, ignored)
            if Path(info.project).resolve() == project
        )
        runs: list[Run] = [run_build(info) for info in builds] or [run_project(project)]
        grouped: dict[Path, list[Diagnostic]] = {}
        covered: set[Path] = set()
        for run in runs:
            covered |= run.covered | group_findings(run.bag, project, grouped)
        registered = {info.identifier: info for run in runs for info in run.bag.registered.values()}
        return Revision(
            number=1 if self._revision is None else self._revision.number + 1,
            project=project,
            builds=builds,
            files=tuple(_described(path, grouped.get(path, ())) for path in sorted(covered)),
            findings=tuple(
                Filed(path, found) for path in sorted(grouped) for found in grouped[path]
            ),
            dictionary=next((run.dictionary for run in runs if run.dictionary is not None), None),
            checks=tuple(registered.values()),
        )

    def _publish(
        self, revision: Revision, stamps: Mapping[Path, tuple[int, int] | None]
    ) -> Revision:
        """Make ``revision`` the newest, its files stamped as they were before it read them.

        Before, never after: stamped after the analysis, a save landing while it ran was already
        in the stamps, so no poll ever saw it and the page kept the findings of bytes no longer
        on disk. A file with no stamp from before - every file of a project just opened, a file
        the analysis found newly included - is stamped :data:`UNKNOWN`, which costs one analysis
        more and catches a save made to that file while this one ran.
        """
        with self._published:
            self._revision = revision
            self._signature = {file.path: stamps.get(file.path, UNKNOWN) for file in revision.files}
            self._published.notify_all()
        return revision


def _source(revision: Revision, path: Path) -> Path:
    resolved = path.resolve()
    if not any(file.path == resolved and file.kind != "plugin" for file in revision.files):
        raise NotInProjectError(f"{path} is not a description file of the open project")
    return resolved


def _described(path: Path, findings: Iterable[Diagnostic]) -> SourceFile:
    listed = list(findings)
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    parsed = None if path.suffix == ".py" else _parsed(data)
    kind = _kind(path, parsed)
    return SourceFile(
        path=path,
        kind=kind,
        name=_name_in(parsed, kind),
        loaded=not any(f.check in LOAD_CHECKS and f.severity is Severity.ERROR for f in listed),
        fingerprint=fingerprint(data),
        errors=sum(1 for f in listed if f.severity is Severity.ERROR),
        warnings=sum(1 for f in listed if f.severity is Severity.WARNING),
        infos=sum(1 for f in listed if f.severity is Severity.INFO),
    )


def _kind(path: Path, parsed: Any) -> str:
    if path.suffix == ".py":
        return "plugin"
    if isinstance(parsed, dict):
        return next((key for key in KINDS if key in parsed), "unknown")
    return "unknown"


def _descriptions(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, subdirectories, files in root.walk():
        depth = len(directory.relative_to(root).parts)
        subdirectories[:] = [
            name for name in subdirectories if depth < SEARCH_DEPTH and not _skipped(name)
        ]
        found.extend(
            directory / name
            for name in files
            if name.endswith(".ddd.json") and _is_project(directory / name)
        )
    return found


def _skipped(name: str) -> bool:
    return (
        name.startswith(".")
        or name == "node_modules"
        or any(fnmatch(name, pattern) for pattern in BUILD_DIRECTORY_PATTERNS)
    )


def _read_json(path: Path) -> Any:
    try:
        return _parsed(path.read_bytes())
    except OSError:
        return None


def _parsed(data: bytes) -> Any:
    try:
        return parse_json_text(data.decode("utf-8-sig"))
    except ValueError:
        return None


def _is_project(path: Path) -> bool:
    data = _read_json(path)
    return isinstance(data, dict) and isinstance(data.get("project"), dict)


def _name_in(data: Any, kind: str) -> str | None:
    block = data.get(kind) if isinstance(data, dict) else None
    name = block.get("name") if isinstance(block, dict) else None
    return name if isinstance(name, str) else None


def _signature(paths: Iterable[Path]) -> dict[Path, tuple[int, int] | None]:
    signature: dict[Path, tuple[int, int] | None] = {}
    for path in paths:
        try:
            status = path.stat()
        except OSError:
            signature[path] = None
        else:
            signature[path] = (status.st_mtime_ns, status.st_size)
    return signature
