"""The project ``ddd gui`` has open, and what its last analysis said about it.

The GUI holds no data of its own: the description files are the project, and a revision is one
analysis of them - the findings, the files it read with a fingerprint of each, and the
dictionary it resolved to. A new revision is made after every edit and undo and whenever a file
of the project changes on disk, by one analysis at a time on a thread of its own: an edit is
written at once and answered as soon as it is, its analysis following, and the edits landing
while one analysis runs are all analysed by the one after it. What the session says - the newest
revision, whether an analysis is asked for or running, the undo entry - is read whole as a
:class:`Snapshot`, numbered by a version that moves at every change of it, which is what a page
waits past. A change on disk is noticed by another thread, comparing each file's modification
time and size once a second: the standard library has no file watcher. Re-checking the 1,683 files
of a generated project of 100,000 declarations (``--shape mixed --missing-ids 1 --unread 0.5``)
took 2 to 6 ms a round with nothing else running, and 2.8 to 3.4 s a round while an analysis ran,
every stat waiting out the analysis's turn of the interpreter - one run of four analyses on the
Linux development PC, Python 3.14 at its default switch interval, which ``ddd gui`` keeps - which
is why a round holds no lock while it stamps (:meth:`Session.poll`). Beside the files, a round
stamps what can change the analysis though none of them changed (:attr:`Revision.watched`): the
directory each wildcard include expands in, since creating or removing a file moves its time;
every file a ``plugins`` list names by its path, loaded or not; and every build record the search
finds, a refused one among them, with the one beside the project description wherever it lies.
So a component saved where a pattern matches, a plugin created or mended and a build record
rewritten each make a new revision, as a file saved does. So does a plugin named by its path and
edited once this process imported it, whose analysis runs the module of its old bytes, a module
being imported once per process: the revision carries ``plugin-changed`` on the plugin's file, an
error by default, until ``ddd gui`` is restarted or the file holds the bytes it was imported from
again (:func:`_tell_changed_plugins`). A build record written where none was, elsewhere than beside
the project description - a new build tree's, or a new image's - and a plugin named as a module and
installed since are noticed when something else changes, and an edit of a plugin named as a
module, or of a module a plugin imports, is told by nothing, which are limits of the preview.

The analysis is the language server's, run the way ``ddd lsp`` runs it: under the severities of
every build record naming the project, or under the defaults when none does.

A project a build generates is the exception to the description files being the project.
``ddd_generate`` without ``PROJECT`` writes the description into its output directory, beside the
build record naming it, out of what ``ddd_add_component`` registers on what the image links, and
writes it again at every configure: which files belong to it is the build's. A revision of one
says so, and which tree the build owns (:attr:`Revision.generated`), and nothing under that tree
is written - the description, a file created beside it, any file the tree holds - each such
change refused :data:`GENERATED`, in a sentence saying where membership is decided
(:func:`generated_refusal`). A record beside a description that does not read as one, a write of
it cut short among them, is taken for the build's until it reads. The components it collects from
the source tree are edited as in any other project.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final

from ddd.build_info import BUILD_INFO_FILENAME, BuildInfo
from ddd.deliveries import Resolved
from ddd.diagnostics import CheckInfo, Diagnostic, Location, Severity
from ddd.editing import (
    INVALID,
    STALE,
    EditError,
    FileChange,
    Written,
    apply_changes,
    edited,
    restore,
)
from ddd.file_names import uncreatable
from ddd.gui.queries import is_a_path
from ddd.ir import DataDictionary
from ddd.loading import (
    DDD_SUFFIX,
    FILE_KINDS,
    FileRead,
    fingerprint,
    included_files,
    parse_json_text,
    resolve_path,
    top_level_kind,
)
from ddd.lsp.diagnostics import Run, finding_identity, group_findings, run_build, run_project
from ddd.lsp.discovery import BUILD_DIRECTORY_PATTERNS, build_files, discover, load_builds
from ddd.lsp.navigation import LOAD_CHECKS, Index
from ddd.lsp.ranges import Document
from ddd.plugins import changed_since_imported, plugin_files

KINDS: Final = FILE_KINDS
"""The top-level keys that say what a description file is, as the loader reads them: the
loader's own, which :func:`kind_of` tells a file's kind by."""

SEARCH_DEPTH: Final = 4
"""How many directories below the start the search for project descriptions goes."""

DESCRIPTION_SUFFIX: Final = ".ddd.json"
"""How the name of a project description ends: the walk's finds, and the only files a build record
may name as its project for the start page to read."""

UNKNOWN: Final = (-1, -1)
"""The stamp of a path whose modification time and size were not taken before an analysis read
it - a file, or what it watches (:attr:`Revision.watched`): a size nothing has, so a poll finds
the path changed. A revision published with one asks for the next analysis itself
(:meth:`Session._finished`); an analysis that raised leaves every path it stamped so, and the
next poll asks again."""

MAX_UNDO: Final = 50
"""How many edits the stack keeps, the oldest falling off: a session that runs all day does not
grow without bound, and fifty is far past what a reader walks back by hand."""

GENERATED: Final = "generated"
"""The refusal of a change writing under the build tree a build generates the open project in
(:func:`generated_refusal`): its description, a file created beside it, or any other file the
tree holds, every one the build's. Answered 409, and refused again for as long as the build record
beside the description names it, or does not read as one (:attr:`Generated.unread`)."""

PLUGINS: Final = "plugins"
"""The refusal of an edit after which the project's descriptions would name plugins other than
they name now (:func:`refuse_plugins`): a change of a description's ``plugins`` list, a created
file whose document names plugins, or a change of ``includes`` that brings in or drops a
description naming plugins. Answered 409. ``ddd gui`` runs what a project names, as ``make`` runs
what a Makefile names, so the token names no code the descriptions do not name already (decision
M7); each shape says what the reader changes in a text editor instead."""

_PLUGINS_SAID: Final = "ddd gui does not change which plugins the project's descriptions name; "
"""What every :data:`PLUGINS` refusal opens with: ``ddd gui`` names no plugin the project's
descriptions do not name already. Each shape then says what the reader changes by hand instead."""

_PLUGINS_LIST: Final = f"{_PLUGINS_SAID}change the plugins list in a text editor"
"""A change of a description's ``plugins`` list, the project's or a sub-project's - a document
rewritten to name plugins among them."""

_PLUGINS_CREATED: Final = f"{_PLUGINS_SAID}create a file that names plugins in a text editor"
"""A file an edit creates whose document names plugins."""

_PLUGINS_INCLUDES: Final = f"{_PLUGINS_SAID}change the includes in a text editor"
"""A change of a description's ``includes`` that brings in or drops a description naming
plugins: the reader touched no plugins list, and the includes are what names it."""

_CMAKE_CACHE: Final = "CMakeCache.txt"
"""The file CMake writes at the top of every build tree it configures: what says where a build
tree begins (:func:`_build_tree`)."""

_CMAKE_LISTS: Final = "CMakeLists.txt"
"""The file a CMake source directory is configured from: the one a ``ddd_add_component`` call
registering a new description goes into (:func:`_instead`), or an existing one
(:func:`_registered`)."""

_REPLACING: Final = "replacing <target> with your component's target"
"""What a sentence offering a ``ddd_add_component`` call says of its ``<target>``, which stays for
the reader to replace with their component's target: no file DDD reads names it."""

_HOME_DIRECTORY: Final = "CMAKE_HOME_DIRECTORY:INTERNAL="
"""The entry of a CMake cache naming the source tree it was configured from, as CMake spells it:
the one entry :func:`_source_tree` reads."""

_WILDCARDS: Final = frozenset("*?[")
"""The characters that make an ``includes`` entry a pattern, as the loader reads one
(:func:`ddd.loading.expand_include`): an entry holding none names a file."""


@dataclass(frozen=True, slots=True)
class Generated:
    """How a build generates the open project, as the build record beside its description says
    (:func:`_generated`)."""

    image: str
    """The image the record names, empty where it names none."""

    tree: Path
    """Resolved: the build tree the description is generated in, every file under which is the
    build's (:func:`_build_tree`) - the description's own directory, where no CMake build tree is
    known to hold it apart from the source tree."""

    unread: Path | None = None
    """The record beside the description, where it does not read as one: whether a build writes
    the description cannot be told then, and it is taken for the build's, the refusal naming the
    record (:func:`generated_refusal`), until the record reads. ``None`` for a record that reads,
    the build it names being the one :attr:`image` names."""


@dataclass(frozen=True, slots=True)
class FoundProject:
    """A project the start page offers."""

    path: Path
    name: str | None
    images: tuple[str, ...]
    """The build images a build record names this project for, each once and in the order of the
    records; empty for a file found alone, and for one whose records name no image."""


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
    """Of the bytes the analysis read (:class:`~ddd.loading.FileRead`) - those the revision's
    index was built from, where several runs read the file (:func:`_files_read`) - never of the
    disk once it is over: what every plan made from the revision carries, so that an Apply after
    the file changed - while the analysis ran, too - is refused as stale. A file no run's read
    parsed, a plugin, is fingerprinted as it stands once the analysis is over."""

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
    statements: tuple[int, int, int]
    """How many errors, warnings and informational findings the analysis made: each once, as
    ``ddd check`` counts them (decision 14.3), however many files :attr:`findings` files it on -
    a disagreement on each of the files it concerns - and however many runs made it."""

    resolved: Resolved | None
    """What the analysis resolved the project to, or ``None`` when it did not get that far.

    The whole of it - the dictionary, the project's plugins and where it writes each name - and
    not the dictionary alone, because those are what a reader of a revision needs to do to it
    anything ``ddd check`` or ``ddd compare`` does to a project of their own: the comparison in
    :mod:`ddd.gui.compare` has a plugin's comparison rules to run only because they are here.
    """

    analysed: bool
    """Whether every run the revision was made from resolved the project, where
    :attr:`resolved` is the first run that did.

    The first is enough for a reader of the dictionary, and not for comparing ``findings`` with
    another analysis's. A run whose read reported an error is never analysed, so none of its
    analysis's errors are in ``findings``, and another build's run that was analysed does not
    speak for it, each run grading the checks by its own severities. Compared all the same, a
    change can surface as new an error the stopped run simply never checked, or break what it
    would check while it stays stopped at the read.
    """

    checks: tuple[CheckInfo, ...]
    """The plugin checks the analysis registered, beside the built-in ones every run has."""

    index: Index | None
    """Where the project writes down each name it uses, from the analysis's own read: the first
    run that built one, since every run of one project reads the same files, and the run whose
    read :attr:`files` are described by."""

    served: tuple[Path, ...]
    """The directories a file the page names by its path may be read, written or previewed in:
    the one the session was given, and the open project's own where it lies outside it - a
    project named on the command line from elsewhere, or one a build record names there, opened
    from the start page.

    What they guard is ``GET /api/file``'s reads, and the files an edit writes and a plan
    previews, each named by its path (:func:`source_path`, :func:`served_path`): a description
    file of the project outside them is refused, ``404``, saying where ``ddd gui`` would have to
    be started to reach it (12:M2). They are no boundary around what the project's analysis reads.
    What a project includes is the project's own business - a directory up is where a shared
    vocabulary lives - and an edit may add any file to its ``includes``: the analysis then reads
    that file wherever it lies, as ``ddd check`` does, and every route answering from the
    analysis - the dictionary, its types, units and values, a variable, the graph, the findings,
    which may quote what the file holds - answers what it states. What bounds an edit is
    elsewhere: it cannot change which plugins the project's descriptions name
    (:func:`refuse_plugins`); a file it creates is a description named ``*.ddd.json``, beside
    the project description and included by the same edit (:func:`_confined`,
    :func:`_refuse_created_kind`); and a build
    record's ``project`` is read only under the rule a request's path meets
    (:func:`_readable_project`).
    """

    edits: int = 0
    """The last edit or undo on disk when this revision's analysis began: every one numbered up
    to it was written before the analysis read a file. ``0`` where the session has written
    none."""

    resolved_paths: Mapping[Path, Path] = field(default_factory=dict)
    """Each path this revision names - each file's and each finding's - and what it resolves to
    by the loader's own rule (:func:`ddd.loading.resolve_path`), resolved once, by the analysis
    that made it: a request about the revision looks a path up here rather than resolving it
    again, a system call for each directory of the path, each of which waits out any busy
    thread's turn of the interpreter. Empty for a revision made any other way - a test's - whose
    paths are resolved when they are first asked about (:func:`ddd.gui.derived.derived`)."""

    generated: Generated | None = None
    """How a build generates the project, where a build record beside its description names it
    (:func:`_generated`): ``ddd_generate`` collecting it out of an image's link closure, and
    nothing under the build tree it is generated in written (:func:`generated_refusal`). Read
    whether or not this version could apply that record's severities, which are another question.
    ``None`` for a project somebody wrote, its record, where a build has one, lying in a build
    tree it is not in."""

    watched: tuple[Path, ...] = ()
    """What the poll stamps beside :attr:`files`, sorted (:func:`_watched`): what can change the
    analysis though no file it read changed. The directory each wildcard include of the project's
    descriptions expands in, every directory a ``**`` walks among them - creating or removing an
    entry moves a directory's modification time, so a component saved on a pattern is noticed by
    that time; every file a ``plugins`` list names by its path, loaded or not, so a plugin created
    or mended is noticed whatever the run read of it; every build record the search found, a
    refused one among them, whose rewrite changes the severities; and the record beside the
    project description, there or not, which says whether a build generates it
    (:attr:`generated`). Empty for a revision made any other way - a test's."""

    @property
    def dictionary(self) -> DataDictionary | None:
        """What the analysis resolved to, or ``None`` when it did not get that far."""
        return None if self.resolved is None else self.resolved.dictionary


@dataclass(frozen=True, slots=True)
class Undoable:
    """One edit the interface made, as it would be put back."""

    at: int
    """What the session counted this edit as, and what an undo names: never reused, so an undo
    asked for from one window cannot put back an edit another window made in between."""

    label: str
    """What the page said this edit was, e.g. ``"the unit of ValueA"``."""

    files: tuple[Written, ...]
    """Every file it wrote, as :func:`ddd.editing.restore` takes them."""


@dataclass(frozen=True, slots=True)
class FileContent:
    """A description file as the page reads it: parsed, or the reason it cannot be."""

    path: Path
    fingerprint: str
    data: Any
    error: str | None


def _readable_project(project: str, *served: Path) -> bool:
    """Whether a build record's ``project`` may be read at all: a path a request may name
    (:func:`~ddd.gui.queries.is_a_path`) - judged as text, before anything resolves it, which a
    network or device spelling would have the system open - and named ``*.ddd.json``. The one
    rule every reader of a record's ``project`` goes through, a network path allowed only under a
    directory of ``served``, which each reader gives. The start page's listing
    (:func:`find_projects`), which an open asks as well, reads records through :func:`_offering`
    under the start directory alone - narrower than the directories a request is served,
    deliberately: a record never names more than the start page needs. The builds that feed the
    open project's analysis (:meth:`Session._analysed`) read records under every directory a
    request is served (:attr:`Revision.served`), the open project's own directory among them, and
    so does the record beside the open project's description that says how it is generated
    (:func:`_generated`): a project whose build records name it by a network path in its own
    directory is fed by the builds those records describe, as a request may name a path there."""
    directories = tuple(directory.as_posix() for directory in served)
    return project.endswith(DESCRIPTION_SUFFIX) and is_a_path(project, directories)


def _offering(records: Iterable[BuildInfo], *served: Path) -> list[BuildInfo]:
    """The build records whose ``project`` is readable under the directories ``served``
    (:func:`_readable_project`). A record naming anything else reads as no record, and nothing is
    read at the path it names."""
    return [info for info in records if _readable_project(info.project, *served)]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What the session says at one moment, every part of it read at once: what
    ``GET /api/state`` answers."""

    version: int
    """Counts up at every change of anything else here - an analysis asked for, one published
    or failed, an edit or an undo written: what a long poll waits past."""

    project: Path | None
    revision: Revision | None
    analysing: bool
    """Whether an analysis is asked for or running: the findings may be about to change."""

    undoable: Undoable | None


class NoProjectError(RuntimeError):
    """Asked about the open project while none is open."""


class NotAnalysedError(RuntimeError):
    """Asked about the open project before any analysis of it has finished."""


class NotInProjectError(LookupError):
    """Asked about a file this session does not serve: one that is not a description file of
    the open project, or one outside the directories it serves."""


def find_projects(root: Path, build_directories: Sequence[Path] = ()) -> Found:
    """The projects under ``root``: those a build record names, and the project descriptions a
    bounded walk finds, hidden directories, ``node_modules`` and build trees left out."""
    base = root.resolve()
    refused: dict[Path, str] = {}
    images: dict[Path, list[str]] = {}
    for info in _offering(discover(base, build_directories, refused), base):
        named = images.setdefault(Path(info.project).resolve(), [])
        # A record offers its project whatever it names: one written without an image names
        # none, and two build trees of one image name it twice.
        if info.image and info.image not in named:
            named.append(info.image)
    paths = sorted(set(images) | set(_descriptions(base)))
    projects = tuple(
        FoundProject(path, name_in(read_json(path), "project"), tuple(images.get(path, ())))
        for path in paths
    )
    return Found(base, projects, tuple(sorted(refused.items())))


def walk_finds(root: Path, path: Path) -> bool:
    """Whether the walk :func:`find_projects` makes finds ``path``, resolved, among the project
    descriptions under ``root``, asked of that one path rather than walked for: it lies under
    ``root`` by directories the walk goes into - real ones, neither a symbolic link nor a
    junction, that it can list, ``root`` among them, none of them left out, no deeper than
    :data:`SEARCH_DEPTH` - it is named ``*.ddd.json``, and it is a project description as it
    stands now. A project a build record offers is not asked
    about: the walk finds it by reading the records, and one outside ``root`` only a record
    offers.

    What ``POST /api/open`` asks of a path it holds already - the open project, or one the last
    listing found - before it walks (:meth:`ddd.gui.api.Api._open`), the walk parsing every
    description under ``root`` to tell the projects among them."""
    base = root.resolve()
    if not path.is_relative_to(base):
        return False
    *directories, name = path.relative_to(base).parts or ("",)
    if not name.endswith(DESCRIPTION_SUFFIX) or len(directories) > SEARCH_DEPTH:
        return False
    if any(_skipped(directory) for directory in directories):
        return False
    on_the_way = [base]
    for directory in directories:
        on_the_way.append(on_the_way[-1] / directory)
    if any(
        place.is_symlink() or place.is_junction() or not _listable(place) for place in on_the_way
    ):
        return False
    return _is_project(path)


def _listable(directory: Path) -> bool:
    """Whether the walk lists ``directory``: it opens it to list it, and passes over what it
    cannot open so - a file, or a directory this process may go through and not list, whose
    descriptions a path through it reads all the same (``Path.walk``)."""
    try:
        with os.scandir(directory):
            return True
    except OSError:
        return False


@dataclass(frozen=True, slots=True)
class _Begun:
    """An analysis begun: the project it reads, the stamps its revision is published with -
    taken before it read a file - and the last edit already on disk."""

    project: Path
    stamps: dict[Path, tuple[int, int] | None]
    edits: int


class Session:
    """One open project at a time, analysed into numbered revisions by one analysis at a time.

    Everything that asks for an analysis - opening a project, an edit, an undo, the poll noticing
    that a file changed, a revision that read a file it had no stamp for - asks it the same way,
    and one asked for while another runs is merged with any other: one analysis follows, of the
    disk as it then stands, never a queue. Once :meth:`start` has started the analyser, it runs
    them on a thread of its own and whatever asked answers at once; where nothing started it -
    every test not about it, and a session nobody started - whatever asked makes the analysis
    itself before it answers, and the one its revision asks for in turn, and a failure of either
    is raised to it.

    One lock guards the project, its newest revision, the undo stack, the counters, the request,
    the stamps and the files written since an analysis began, and every write of them is made
    holding it. An analysis runs without it, which is what lets an edit be written while one
    runs. Nothing on disk is touched holding it but the files an edit or an undo writes, and the
    descriptions an edit's change of ``includes`` brings in or drops, read for the plugins they
    name (:func:`refuse_plugins`), so that the number it takes, the stack and the files waiting
    for an analysis move with the write: the poll stamps the files without it (:meth:`poll`), an
    analysis stamps those it is about to read without it (:meth:`_next`), and opening reads what a
    project includes, and searches for its build records, before taking it (:meth:`open`). While
    another thread computes, every system call waits out that thread's turn of the interpreter,
    and a lock held across a project's thousands of files held every edit, state and plan behind
    them: edits asked 0.2 to 3.0 s into an analysis of a generated project of 100,000 declarations
    answered in 2 to 3,363 ms while the poll stamped holding it, and in 2 to 129 ms since - one run
    each, seven edits, on the Linux development PC.
    """

    def __init__(
        self, root: Path, build_directories: Sequence[Path] = (), *, poll_interval: float = 1.0
    ) -> None:
        self.root = root.resolve()
        self.build_directories = tuple(build_directories)
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._project: Path | None = None
        self._revision: Revision | None = None
        self._numbered = 0
        self._version = 0
        self._stack: list[Undoable] = []
        self._edits = 0
        # Each edit and undo by its number, with the files it wrote: what no analysis has read
        # yet, until a published revision's `edits` reaches that number.
        self._written: list[tuple[int, frozenset[Path]]] = []
        self._signature: dict[Path, tuple[int, int] | None] = {}
        self._fresh: set[Path] = set()
        self._asked: Path | None = None
        self._running = False
        self._stopping = threading.Event()
        self._poller: threading.Thread | None = None
        self._analyser: threading.Thread | None = None

    @property
    def project(self) -> Path | None:
        """The project open, analysed yet or not; ``None`` while none is."""
        return self._project

    @property
    def revision(self) -> Revision | None:
        """The open project's newest revision, or ``None`` while it has none yet."""
        return self._revision

    @property
    def edits(self) -> int:
        """How many edits and undos this session has written: the number the last of them took,
        an edit's being what an undo names it by. One refused before anything was written counts
        none."""
        with self._lock:
            return self._edits

    def open(self, project: Path) -> None:
        """Open a project description, replacing the project open before it, and ask for its
        first analysis.

        What its own includes name (:func:`named_by`) is read before the lock is taken, as
        whether it is a project description at all is: the description read and its patterns
        expanded on disk, system calls each of which waits out any busy thread's turn. So are the
        directories its own patterns expand in and the build records the search finds, which its
        revision watches (:attr:`Revision.watched`): stamped as well, they cost a project with a
        pattern or a build no second analysis. Sound, because what it names is only which paths
        are stamped as the first analysis begins, the stamps themselves taken then
        (:meth:`_next`): a description changed in between names a path with no stamp from before,
        which costs the one analysis more any such path costs (:meth:`_finished`).
        """
        path = project.resolve()
        if not _is_project(path):
            raise ValueError(f"{project} is not a project description")
        named = named_by(path) | _expanded_by(path, read_json(path))
        named.update(build_files(self.root, self.build_directories))
        named.add(path.parent / BUILD_INFO_FILENAME)
        with self._lock:
            self._project = path
            self._revision = None
            self._stack = []
            self._written = []
            self._signature = {}
            self._fresh = named
            self._request()
        self._analyse_here()

    def settled(self, timeout: float | None) -> Revision | None:
        """The newest revision once no analysis is asked for or running, or once ``timeout``
        seconds have passed; ``None`` waits as long as that takes."""
        with self._changed:
            self._changed.wait_for(lambda: self._asked is None and not self._running, timeout)
            return self._revision

    def snapshot(self) -> Snapshot:
        """What the session says now, every part of it read at once."""
        with self._lock:
            return self._snapshot()

    def wait(self, after: int, timeout: float) -> Snapshot:
        """What the session says as soon as its version is past ``after``, or after
        ``timeout``."""
        with self._changed:
            self._changed.wait_for(lambda: self._version > after, timeout)
            return self._snapshot()

    def current(self) -> Revision:
        """The open project's newest revision, refusing where there is none: no project open, or
        no analysis of it finished yet."""
        with self._lock:
            return self._required()

    def unanalysed(self, revision: Revision) -> frozenset[Path]:
        """Every file an edit or an undo wrote after ``revision``'s analysis began: numbered past
        its ``edits``. A revision older than the newest may miss some the newest already
        includes; the engine's own fingerprint check still refuses a plan made against it."""
        with self._lock:
            waiting: set[Path] = set()
            for number, paths in self._written:
                if number > revision.edits:
                    waiting |= paths
            return frozenset(waiting)

    def poll(self) -> bool:
        """Ask for an analysis if a file of the open project, or what its revision watches
        (:attr:`Revision.watched`), changed on disk since its stamps were taken; say whether one
        did.

        The paths are stamped without the lock, which is held only to read the stamps to compare
        with and then to compare and ask: one stat a path, each waiting out any busy thread's
        turn, held every edit, state and plan behind a round of them for seconds. Stamps replaced
        in between - an analysis begun or published, a project opened, each of which rebinds them
        whole and never changes them in place - make this reading moot, and the round passes
        asking for nothing: whatever replaced them took stamps of its own, from before its
        analysis reads a file, and the next round compares with those. Two statements rather than
        one condition, so that coverage counts a branch for each.
        """
        with self._lock:
            if self._project is None:
                return False
            signature = self._signature
        now = stamped(signature)
        with self._lock:
            if self._signature is not signature:
                return False
            if now == signature:
                return False
            self._request()
        self._analyse_here()
        return True

    def start(self) -> None:
        """Analyse on a thread of its own from now on, and poll on another, until :meth:`stop`."""
        if self._analyser is None:
            self._analyser = threading.Thread(
                target=self._analyse_until_stopped, name="ddd-gui-analyse", daemon=True
            )
            self._analyser.start()
        self.start_polling()

    def start_polling(self) -> None:
        """Poll every ``poll_interval`` seconds on a thread of its own, until :meth:`stop`."""
        if self._poller is None:
            self._poller = threading.Thread(
                target=self._poll_until_stopped, name="ddd-gui-poll", daemon=True
            )
            self._poller.start()

    def stop(self) -> None:
        """End the analyser and the poller, each once its current round is done."""
        self._stopping.set()
        with self._changed:
            self._changed.notify_all()
        for thread in (self._poller, self._analyser):
            if thread is not None:
                thread.join()

    def read_file(self, path: Path) -> FileContent:
        """A description file of the open project, parsed, with the fingerprint it was read at.

        Parsed by the loader's rule, like every file the session reads: python's own reader
        takes ``NaN``, which went to the page as a value no browser's parser reads, and a key
        spelled twice, which showed the page a file ``ddd check`` refuses as though it loaded.
        """
        target = source_path(self._required(), path)
        try:
            data = target.read_bytes()
        except OSError as error:
            return FileContent(target, fingerprint(b""), None, f"{target} cannot be read: {error}")
        try:
            parsed = parse_json_text(data.decode("utf-8-sig"))
        except ValueError as error:
            return FileContent(target, fingerprint(data), None, f"{target} is not json: {error}")
        return FileContent(target, fingerprint(data), parsed, None)

    def edit(self, changes: Sequence[FileChange], label: str) -> tuple[int, tuple[Written, ...]]:
        """Make an edit of description files of the open project, ask for its analysis, and
        answer the number it took and what it wrote.

        A change without a fingerprint creates its file, and only a project description file
        ``ddd gui`` creates (:func:`kind_of`): one beside the project description, in an edit
        whose change of that description includes it, and no plugin and no file of another kind.
        Any other is refused before a file is touched (:func:`_creatable`, :func:`_confined`,
        :func:`_refuse_created_kind`).

        ``ddd gui`` does not change which plugins the project's descriptions name
        (:func:`refuse_plugins`): an edit that would change a ``plugins`` list, create a file
        whose document names plugins, or bring in or drop a description naming plugins through a
        change of ``includes`` is refused before a file is touched, so the reader makes such a
        change in a text editor, never through the page. ``ddd gui`` runs what a project names,
        as ``make`` runs what a Makefile names (decision M7), and a description that does not
        load runs none of the plugins it names, whichever way an edit leaves it. Each change is
        judged whole before the next, read once as it would leave its file: a file it creates for
        what it is, then for the plugins it names.

        Nothing is written under the build tree a description a build generates is in
        (:attr:`Revision.generated`): an edit changing that description, creating a file beside
        it or changing any other file of the tree is refused :data:`GENERATED`, before a file is
        touched (:func:`generated_refusal`). A file this process may not write - one kept
        read-only, on any system - is refused ``unwritable`` as well, before any file of the
        edit is written or staged (:func:`ddd.editing.apply_changes`).

        ``label`` is what the page calls this edit - "the unit of ValueA" - and is what an undo
        of it offers to put back.
        """
        try:
            return self._edited(changes, label)
        except EditError as refused:
            self._refused(refused)
            raise

    def _edited(self, changes: Sequence[FileChange], label: str) -> tuple[int, tuple[Written, ...]]:
        with self._lock:
            revision = self._required()
            _creatable(changes)
            _refuse_generated(revision, changes)
            confined = [_confined(revision, pending, changes) for pending in changes]
            for change in confined:
                before, after = _as_edited(change)
                _refuse_created_kind(change, after)
                _refuse_plugin_change(change, before, after)
            written = apply_changes(confined)
            self._edits += 1
            self._stack.append(Undoable(self._edits, label, written))
            del self._stack[:-MAX_UNDO]
            self._written.append((self._edits, frozenset(file.path for file in written)))
            # Stamped when its analysis begins, after this write, so that the poll does not take
            # the write for somebody else's. A file of the last revision is stamped again then
            # in any case; a file this edit created is not, having no stamp yet, but for this.
            self._fresh |= {file.path for file in written}
            self._request()
            at = self._edits
        self._analyse_here()
        return at, written

    def undo(self, at: int) -> int:
        """Put the edit numbered ``at`` back, pop it, ask for an analysis, and answer the number
        the undo took.

        Only the top of the stack: an ``at`` that is not it is refused as stale, which is what
        keeps a second window from putting back an edit this one never saw. A refusal - a file
        changed since, or one that could not be written - leaves the stack as it is, so the
        reader may put that file back and ask again.
        """
        try:
            return self._undone(at)
        except EditError as refused:
            self._refused(refused)
            raise

    def _undone(self, at: int) -> int:
        with self._lock:
            self._required()
            top = self._stack[-1] if self._stack else None
            if top is None or top.at != at:
                raise EditError(STALE, f"edit {at} is not the one to undo any more")
            restore(top.files)
            # Popped only once the files are back: a refused restore leaves the entry where it
            # was.
            self._stack.pop()
            self._edits += 1
            self._written.append((self._edits, frozenset(file.path for file in top.files)))
            self._fresh |= {file.path for file in top.files}
            self._request()
            number = self._edits
        self._analyse_here()
        return number

    @property
    def undoable(self) -> Undoable | None:
        """The edit an undo would put back: the top of the stack, or ``None`` when it is
        empty."""
        with self._lock:
            # Locked, unlike `revision`: `_revision` is only ever rebound whole, so one read of
            # it is atomic, but `undo` mutates `_stack` in place with `.pop()` - an unlocked
            # check-then-index here could see it emptied between the two.
            return self._stack[-1] if self._stack else None

    def _poll_until_stopped(self) -> None:
        while not self._stopping.wait(self.poll_interval):
            try:
                self.poll()
            except Exception as error:
                # A thread that dies here leaves a page that never updates again, and nothing
                # says why: the one line is that reason, and the next poll tries again.
                print(f"ddd gui: checking the project again failed: {error}", file=sys.stderr)

    def _snapshot(self) -> Snapshot:
        """What the session says, read holding the lock."""
        return Snapshot(
            self._version,
            self._project,
            self._revision,
            self._asked is not None or self._running,
            self._stack[-1] if self._stack else None,
        )

    def _required(self) -> Revision:
        if self._project is None:
            raise NoProjectError("no project is open")
        if self._revision is None:
            raise NotAnalysedError("the open project has not been analysed yet")
        return self._revision

    def _analysed(self, project: Path) -> Revision:
        # The project's own directory as well, where it is not already inside the root: a
        # project named on the command line from elsewhere, or one a build record names there,
        # opened from the start page (`Revision.served` says what that guards). Two statements
        # rather than one conditional expression, which coverage.py counts no branch in, so the
        # arm no test took would pass the gate unexercised.
        served: tuple[Path, ...] = (self.root,)
        if not project.parent.is_relative_to(self.root):
            served = (self.root, project.parent)
        ignored: dict[Path, str] = {}  # the start page is where a refused record is reported
        # Every record found, apart from reading them: the revision watches each, the refused
        # among them (`Revision.watched`). Read under every directory served, a request's rule
        # (`_readable_project`).
        found = build_files(self.root, self.build_directories)
        builds = tuple(
            info
            for info in _offering(load_builds(found, ignored), *served)
            if Path(info.project).resolve() == project
        )
        runs = _runs(project, builds)
        # The run the index comes from, chosen once: its read is the one the files are described
        # by (`_files_read`).
        indexed = next((run for run in runs if run.index is not None), None)
        read = _files_read(runs, indexed)
        # Each project description the analysis read, the project's own among them, whatever
        # the runs went on to cover: a plugin's model raising ends the read, and a run so ended
        # covers the project description alone.
        descriptions = [path for path, file in read.items() if file.kind == "project"]
        # The record beside the description too, there or not, wherever the search looked: it
        # says whether a build generates the project.
        watched, plugins = _watched(descriptions, (*found, project.parent / BUILD_INFO_FILENAME))
        # Before the findings are sorted onto their files, so that a plugin's file counts its own.
        _tell_changed_plugins(runs, plugins)
        grouped, covered = _grouped(runs, project)
        registered = {info.identifier: info for run in runs for info in run.bag.registered.values()}
        files = tuple(
            _described(path, grouped.get(path, ()), read.get(path)) for path in sorted(covered)
        )
        findings = _filed(grouped)
        return Revision(
            # Numbered when it is published (`_finished`): an analysis thrown away takes none.
            number=0,
            project=project,
            builds=builds,
            files=files,
            findings=findings,
            statements=_statements(runs),
            # One run's whole answer, never a field picked from each: the plugins a comparison
            # runs the rules of and the dictionary it compares have to be the same read's, and
            # two `next()` calls over the same list would only agree by coincidence.
            resolved=next((run.resolved for run in runs if run.resolved is not None), None),
            analysed=all(run.resolved is not None for run in runs),
            checks=tuple(registered.values()),
            index=None if indexed is None else indexed.index,
            served=served,
            resolved_paths=_resolved_paths(files, findings),
            generated=_generated(project, self.root),
            watched=watched,
        )

    def _request(self) -> None:
        """Ask for an analysis of the open project. Holding the lock, with a project open, once
        whatever asked has changed what it changes: the version moves with it."""
        self._asked = self._project
        self._version += 1
        self._changed.notify_all()

    def _refused(self, refused: EditError) -> None:
        """Ask for an analysis, and make it, when a write was refused ``stale``, then let the
        refusal stand. A file changed in a way the poll cannot see - the same size and modification
        time - keeps every plan carrying the fingerprint of the bytes read before, which would be
        refused for good; the analysis reads what is on disk and its revision fingerprints that.
        Called without the lock.

        The refusal is the answer whatever the analysis does: one that raises - the change may
        have left the project unanalysable - is printed as the analyser prints its own, and its
        files stay stamped unknown (:meth:`_finished`), so that the next poll asks again.
        """
        if refused.code == STALE:
            with self._lock:
                self._request()
            try:
                self._analyse_here()
            except Exception as error:
                print(f"ddd gui: analysing the project failed: {error}", file=sys.stderr)

    def _analyse_here(self) -> None:
        """Make the analyses asked for on this thread, where no analyser was started."""
        if self._analyser is not None:
            return
        begun = self._next(wait=False)
        while begun is not None:
            self._run(begun, raising=True)
            begun = self._next(wait=False)

    def _analyse_until_stopped(self) -> None:
        while not self._stopping.is_set():
            begun = self._next(wait=True)
            if begun is not None:
                # Nothing raised outside the analysis may end this thread, which would leave
                # every page waiting for an analysis that never comes. `_run` publishes and prints
                # a failure of the analysis itself; what can still raise is that print, on a
                # stderr nothing can be written to, and the line is lost with it.
                with contextlib.suppress(Exception):
                    self._run(begun, raising=False)

    def _next(self, *, wait: bool) -> _Begun | None:
        """The analysis to make next, begun - its stamps taken before it reads a file - or
        ``None`` where there is none to make; after waiting for one, where asked to, until the
        session stops.

        Taken up holding the lock - the request, the files to stamp and the edits already on
        disk, every one of which this analysis reads - and stamped without it, as :meth:`poll`
        stamps. An edit written while the files are stamped is numbered past the edits taken up,
        so it is the next analysis's, which its own request asks for, however this one's stamps
        caught its write: stamped after it, the write is what this analysis reads; stamped
        before, the poll after this revision finds the file changed, and asks for the analysis
        that edit asked for already.

        While they are stamped the stamps stand empty, so that a poll compares nothing then: an
        edit's own write, made before this analysis took its request up, is not a change it
        missed, being about to be read. Put in place once taken, unless something replaced the
        empty ones meanwhile: only opening a project can, whose own stamps they then are.
        """
        with self._changed:
            if wait:
                self._changed.wait_for(
                    lambda: (
                        self._stopping.is_set() or (self._asked is not None and not self._running)
                    )
                )
            project = self._asked
            if project is None or self._running or self._stopping.is_set():
                return None
            self._asked = None
            self._running = True
            paths = set(self._signature) | self._fresh
            self._fresh = set()
            edits = self._edits
            stamping: dict[Path, tuple[int, int] | None] = {}
            self._signature = stamping
        # Raising nothing: `stamped` stamps a path the system refuses even to look at as one that
        # is not there, and an exception here would leave `_running` set for good.
        stamps = stamped(paths)
        with self._changed:
            # Standing in for the last revision's while this one runs, so that the poll does not
            # take an edit's own write, stamped here, for a change this analysis missed.
            if self._signature is stamping:
                self._signature = dict(stamps)
        return _Begun(project, stamps, edits)

    def _run(self, begun: _Begun, *, raising: bool) -> None:
        """Make the analysis ``begun`` and publish what it made; one that raises is raised to
        the caller where ``raising``, and printed otherwise."""
        revision: Revision | None = None
        try:
            revision = self._analysed(begun.project)
        except Exception as error:
            if raising:
                raise
            # A thread that dies here leaves a page that never updates again, and nothing says
            # why: the one line is that reason, and the next poll asks again. Printed before the
            # failure is published, so that whatever waits for it finds the line written.
            print(f"ddd gui: analysing the project failed: {error}", file=sys.stderr)
        finally:
            with self._changed:
                self._finished(begun, revision)

    def _finished(self, begun: _Begun, revision: Revision | None) -> None:
        """What an analysis leaves once it has ended, made holding the lock: nothing, where the
        project it read is no longer the one open. Otherwise what it made becomes the newest
        revision, its files and what it watches (:attr:`Revision.watched`) stamped as they were
        before it read them - a path with no stamp from before :data:`UNKNOWN` - and where it
        raised instead, ``revision`` being ``None``, nothing is published and every path it
        stamped is stamped unknown, so that the next poll asks again.

        Before, never after: stamped after the analysis, a save landing while it ran was already in
        the stamps, so no poll ever saw it and the page kept the findings of bytes no longer on
        disk. The revision's fingerprints are of what its analysis read for the same reason
        (:func:`_described`), never of the disk once it is over. A path with no stamp from before -
        a sub-project's file, a plugin or the directory a sub-project's pattern expands in, when
        the project was just opened, or a file the analysis found newly included - is stamped
        :data:`UNKNOWN`, and the revision is published asking for the next analysis: one analysis
        more, which catches a save made to that file while this one ran. Asked here rather than
        left to the next poll, which asked for it up to ``poll_interval`` later, so that the
        session says it is analysing until that analysis lands, rather than that it is done and
        then, a poll later, that it is analysing again.

        A revision published lets go of the files every edit it includes wrote: none of them is
        waiting for an analysis any more. Whatever it leaves, the version moves, since what the
        session says may have changed with it: the newest revision, where one is published, and
        ``analysing``, which turns false unless another analysis is asked for by then - the one
        this revision asks for, or one asked while this analysis ran.
        """
        self._running = False
        if begun.project == self._project:
            if revision is None:
                self._signature = dict.fromkeys(begun.stamps, UNKNOWN)
            else:
                self._numbered += 1
                self._revision = replace(revision, number=self._numbered, edits=begun.edits)
                self._signature = {
                    path: begun.stamps.get(path, UNKNOWN)
                    for path in (*(file.path for file in revision.files), *revision.watched)
                }
                waiting: list[tuple[int, frozenset[Path]]] = []
                for number, paths in self._written:
                    if number > begun.edits:
                        waiting.append((number, paths))
                self._written = waiting
                if UNKNOWN in self._signature.values():
                    self._request()
        self._version += 1
        self._changed.notify_all()


def findings_with(revision: Revision, includes: Sequence[str]) -> tuple[Filed, ...]:
    """The findings ``revision``'s project would have with its root's ``includes`` replaced,
    from exactly the runs that revision was made from - each build's, with that build's own
    severity flags, or the project's alone - so that the runs differ in the list and nothing
    else. Every file is read from disk again. Nothing is written and nothing is published.

    Given the revision rather than reading the newest: a plan is computed against one, and a
    save landing between the plan and this would otherwise make them two.

    Cost, measured in one process as the median of seven calls with the list unchanged, so that
    every file is read and analysed: 0.6 ms over each of the three projects of
    ``examples/pressure`` (four files and three components apiece), 1.8 ms over
    ``examples/demo``, the example with the most components (six files, 23 variables in four
    components), and 17 ms over a generated flat project of two hundred components, each listed
    by an entry of its own and reading the variable the one before it writes, the first the
    last's. Each call measured returned what ``ddd check`` reports on that project.
    """
    runs = _runs(revision.project, revision.builds, includes=includes)
    grouped, _ = _grouped(runs, revision.project)
    return _filed(grouped)


def _runs(
    project: Path, builds: Sequence[BuildInfo], *, includes: Sequence[str] | None = None
) -> list[Run]:
    """The runs a revision of ``project`` is made from: one per build record naming it, each
    under that build's own severity flags, or the project's alone under the defaults where no
    record does. ``includes`` replaces the root's list in every one of them.

    One function for a revision and for :func:`findings_with`, so that the latter re-runs what
    the revision it is given was made of and cannot drift from it. A statement rather than
    ``[...] or [...]``, which coverage.py counts no branch in.
    """
    runs = [run_build(info, includes=includes) for info in builds]
    if not runs:
        runs = [run_project(project, includes=includes)]
    return runs


def _grouped(runs: Sequence[Run], project: Path) -> tuple[dict[Path, list[Diagnostic]], set[Path]]:
    """The findings of ``runs`` sorted onto the files they are shown on, as
    :func:`~ddd.lsp.diagnostics.group_findings` sorts them, and every file the runs covered or
    filed one on. A finding with no place goes on ``project``, the one file the reader is sure
    to have open.

    One function for a revision and for :func:`findings_with`, so that the two show every
    finding on the same file.
    """
    grouped: dict[Path, list[Diagnostic]] = {}
    covered: set[Path] = set()
    for run in runs:
        covered |= run.covered | group_findings(run.bag, project, grouped)
    return grouped, covered


def _statements(runs: Sequence[Run]) -> tuple[int, int, int]:
    """:attr:`Revision.statements` of ``runs``: their findings counted before :func:`_grouped`
    files each on every file it concerns, and each once however many of the runs made it - the
    same check, severity, place and words, as :func:`~ddd.lsp.diagnostics.group_findings` keeps
    one of them (:func:`~ddd.lsp.diagnostics.finding_identity`). A finding two builds grade apart
    is two, one under each severity, as the rows are.

    Measured on the Linux development PC over the 125,000 findings of a generated project of
    100,000 declarations (``--shape mixed --missing-ids 1 --unread 0.5``): 50 to 55 ms, beside the
    193 to 204 ms the grouping of the same run takes - three runs each."""
    made = {finding_identity(finding) for run in runs for finding in run.bag}
    counted = Counter(severity for _, severity, _, _ in made)
    return (counted[Severity.ERROR], counted[Severity.WARNING], counted[Severity.INFO])


def _resolved_paths(files: Iterable[SourceFile], findings: Iterable[Filed]) -> dict[Path, Path]:
    """Each path ``files`` and ``findings`` name, resolved once each by the loader's own rule:
    :attr:`Revision.resolved_paths`. That rule hands back as it is a path the system refuses even
    to look at, where :meth:`pathlib.Path.resolve` raised for it, and the state of a project
    including one answered a server error."""
    resolved: dict[Path, Path] = {}
    for path in (*(file.path for file in files), *(filed.file for filed in findings)):
        if path not in resolved:
            resolved[path] = resolve_path(path)
    return resolved


def _filed(grouped: Mapping[Path, Sequence[Diagnostic]]) -> tuple[Filed, ...]:
    """The findings of some runs, as :func:`~ddd.lsp.diagnostics.group_findings` sorted them onto
    files: file by file in path order, each file's in the order they were grouped. A revision's
    order, and so the order :func:`findings_with` answers in."""
    return tuple(Filed(path, found) for path in sorted(grouped) for found in grouped[path])


def source_path(revision: Revision, path: Path) -> Path:
    """One path the page gave, resolved and allowed: a description file of the open project,
    inside a directory the session serves.

    Both, not membership alone: an edit may add a file a directory up to the project's
    ``includes``, and membership alone would then have ``GET /api/file`` read it back and an
    edit write it. Checked here rather than at that one route, because this is where every route
    that takes a path from the page resolves it, and where an edit resolves the file it writes.
    What this does not bound, what the analysis reads of such a file, :attr:`Revision.served`
    says.

    Resolved as the loader resolves a path (:func:`ddd.loading.resolve_path`), which hands one it
    cannot resolve back as given, to be no file of the project: on python 3.12 a loop of links
    made ``Path.resolve`` raise, which answered the request ``500``.
    """
    resolved = resolve_path(path)
    if not any(file.path == resolved and file.kind != "plugin" for file in revision.files):
        raise NotInProjectError(f"{path.as_posix()} is not a description file of the open project")
    return served_path(revision, resolved)


def served_path(revision: Revision, resolved: Path) -> Path:
    """One resolved path, allowed where it lies inside a directory the session serves.

    Membership of the open project is not this question and does not answer it: an edit may add
    anything to the project's own ``includes``, so a reader of the page can make a file
    anywhere part of the project and then name it by its path, which this refuses outside the
    directories served. That is all it bounds: what the analysis reads of such a file, and what
    the routes answering from the analysis say of it, :attr:`Revision.served` says.
    """
    if not any(resolved.is_relative_to(directory) for directory in revision.served):
        serves = " and ".join(directory.as_posix() for directory in revision.served)
        raise NotInProjectError(
            f"{resolved.as_posix()} is a description file of the open project, but ddd gui "
            f"serves {serves}; "
            "start it in a directory holding this file to reach it here"
        )
    return resolved


def _creatable(changes: Sequence[FileChange]) -> None:
    """Refuse an edit creating a file under a name no file can be created under
    (:func:`ddd.file_names.uncreatable`), before any change of it is confined: a name Windows keeps
    for a device, one holding a character it keeps out of a name or ending in a dot or a space,
    or one too long to stage, is refused on every system alike, whatever an operating system
    would answer about it - Windows' answer about a name too long for NTFS is not one
    ``Path.resolve`` is sure to walk past.

    Every one before any is confined: confining a file to be created looks up each name the
    project description's includes give (:func:`_included`), another created file's among them,
    and on Windows looking up a device's name opens the device."""
    for pending in changes:
        if pending.fingerprint is None:
            refused = uncreatable(pending.path.name)
            if refused is not None:
                raise EditError(INVALID, f"{pending.path} cannot be created: {refused}")


def generated_refusal(
    revision: Revision,
    written: Iterable[Path],
    created: Iterable[Path] = (),
    added: Iterable[Path] = (),
) -> str | None:
    """Why a change writing the files ``written`` - each resolved, ``created`` the ones of them it
    creates, ``added`` the existing descriptions it brings into the project's includes - cannot
    be made, where ``revision``'s project is one a build generates (:attr:`Revision.generated`)
    and one of them lies under the build tree it is generated in; ``None`` otherwise, which is
    every change of a project somebody wrote.

    Every file under that tree is the build's. The description is written again at every
    configure out of what ``ddd_add_component`` registers, so an entry added or taken out here
    does not outlive that configure, and no other change of it does either; a file created beside
    it is in no ``ddd_add_component`` call, so the project no longer includes it after that
    configure, and it is deleted with the build tree, as is every other file the tree holds - one
    a custom command generates there, the build writing it again. The sentence says so, naming the
    tree, and the description where the change writes it or creates a file - membership being what
    both are about - and otherwise the first file it writes under the tree, which the reader asked
    to change. Where it creates one, it offers the file in the source tree instead
    (:func:`_instead`); where it brings an existing one in, the line that registers it, in the
    CMakeLists.txt beside it (:func:`_registered`) - one under the tree passed over, as
    :func:`_instead` passes over a description there, since it goes with the tree. Only the Files
    tab's add knows the file it brings in: an edit posted with an entry written by hand is told
    the build's membership alone.

    Where the record beside the description does not read as one (:attr:`Generated.unread`),
    whether the build writes it is not known: every such change is refused in one sentence naming
    the record and the tree, and offering nothing, until the record reads.
    """
    generated = revision.generated
    if generated is None:
        return None
    there: list[Path] = []
    for path in written:
        if path.is_relative_to(generated.tree):
            there.append(path)
    if not there:
        return None
    name = revision.project.name
    tree = generated.tree.as_posix()
    if generated.unread is not None:
        return (
            f"{name} may be generated by a build: the build record beside it, "
            f"{generated.unread.as_posix()}, does not read as one, so nothing under {tree} is "
            "written from here until it does"
        )
    # Two statements rather than a conditional expression, which coverage.py counts no branch in:
    # a record written without --image names no image.
    build = "the build"
    if generated.image:
        build = f"the build of {generated.image}"
    membership = "which files belong to it is ddd_add_component's to say"
    said = (
        f"{name} is generated by {build} at every configure, so {membership}, and nothing under "
        f"{tree} is written from here"
    )
    new = next(iter(created), None)
    if new is not None:
        return f"{said}{_instead(revision, generated.tree, new.name)}"
    if revision.project in there:
        brought = next(iter(added), None)
        if brought is not None and not brought.is_relative_to(generated.tree):
            return f"{said}{_registered(brought)}"
        return said
    return (
        f"{min(there).name} lies under {tree}, where {name} is generated by {build} at every "
        f"configure: {membership}, and nothing there is written from here"
    )


def _component_line(filename: str) -> str:
    """The ``ddd_add_component`` call registering the description ``filename``, as a CMakeLists.txt
    of its own directory writes it: by its name, which the call reads against the directory it is
    made in."""
    return f"ddd_add_component(<target> JSON {filename})"


def _registered(described: Path) -> str:
    """How the existing description ``described`` joins a project a build generates, rather than
    by an entry of the includes the build writes again: by the line a new file is offered with
    (:func:`_instead`), in the CMakeLists.txt beside it."""
    return (
        f"; add {_component_line(described.name)} to the CMakeLists.txt beside "
        f"{described.as_posix()} instead, {_REPLACING}"
    )


def _instead(revision: Revision, tree: Path, filename: str) -> str:
    """Where a new file ``filename`` goes rather than beside a description a build generates under
    ``tree``: beside the first description of ``revision`` the build collects from the source
    tree, and into a ``ddd_add_component`` call of the CMakeLists.txt beside it, by its name,
    which the call reads against the directory it is made in. Passed over, so that no sentence
    sends the reader where the file would not stay or the line could not go:

    * a plugin, which is no description: ``ddd_generate`` names it with ``PLUGINS``;
    * a description under ``tree`` - one a custom command writes there, or a dependency fetched
      into it - which would go with the tree;
    * one outside every directory the session serves, an installed package or a checkout beside
      this one, which is not where the reader works;
    * one with no CMakeLists.txt beside it, where "the CMakeLists.txt there" would name nothing.

    A project collecting no such description is pointed at the source tree alone. ``<target>``
    stays for the reader to replace (:data:`_REPLACING`)."""
    line = _component_line(filename)
    for file in revision.files:
        if file.kind == "plugin":
            continue
        path = resolve_path(file.path)
        if path.is_relative_to(tree):
            continue
        if not any(path.is_relative_to(directory) for directory in revision.served):
            continue
        if not os.path.isfile(path.parent / _CMAKE_LISTS):  # noqa: PTH113
            continue
        return (
            f"; create {filename} beside {path.as_posix()} instead, and add {line} to the "
            f"CMakeLists.txt there, {_REPLACING}"
        )
    return (
        f"; create {filename} in the source tree instead, and add {line} to the CMakeLists.txt "
        f"beside it, {_REPLACING}"
    )


def _refuse_generated(revision: Revision, changes: Sequence[FileChange]) -> None:
    """Refuse an edit writing under the build tree a build generates the open project in
    (:func:`generated_refusal`), each change's file resolved as the loader resolves one.

    Before any change of it is confined: :func:`_confined` refuses a file created beside the
    description that the same edit does not include, saying it is created only by an edit
    including it there - which, under the build tree of a description the build writes, is a
    change refused too."""
    refused = generated_refusal(
        revision,
        (resolve_path(change.path) for change in changes),
        (resolve_path(change.path) for change in changes if change.fingerprint is None),
    )
    if refused is not None:
        raise EditError(GENERATED, refused)


def refuse_plugins(revision: Revision, changes: Sequence[FileChange]) -> None:
    """Refuse an edit after which the open project would name plugins other than it names now,
    before any file is touched (decision M7): a change of a description's ``plugins`` list, the
    project's or a sub-project's; a created file whose document names plugins; or a change of
    ``includes`` that brings in or drops a description naming plugins. So the token names no code
    the descriptions do not name already - ``ddd gui`` runs what a project names, as ``make`` runs
    what a Makefile names.

    The rule an edit is held to change by change (:meth:`Session.edit`), each file it creates
    judged a description first (:func:`_refuse_created_kind`); asked here of a plan's edits whole,
    by ``GET /api/files-plan``, for the refusal its Apply would meet.

    Each change is read as it would leave its file (:func:`_as_edited`), in memory, from the
    confined changes so a file beyond what the session serves was refused already. Every
    existing description the edit changes is compared before and after, whatever kind it is now:
    a document rewritten from any other kind into a project naming plugins, or into one that
    includes a description naming plugins, names other plugins the next analysis would load, and
    its kind before the edit is not what the next analysis reads it as. :func:`_listed` answers
    ``()`` for a document that is no project, so a change touching neither list is passed over
    all the same. A description brought in or dropped is read for the plugins it names and those
    its own includes bring, by the loader's reading of json alone and never by importing one
    (:func:`_subtree_names_plugins`): each file as the next analysis would read it, the walk
    going further than that analysis goes."""
    for change in changes:
        _refuse_plugin_change(change, *_as_edited(change))


def _as_edited(change: FileChange) -> tuple[Any, Any]:
    """The document ``change``'s file holds, and the one the change would leave it holding, each
    read as the loader reads json and made in memory by the edit engine
    (:func:`ddd.editing.edited`), refused as it refuses the change: ``None`` before for a file the
    change creates, which held nothing, as for a document that does not parse."""
    original, new = edited(change)
    if original is None:
        return None, _parsed(new)
    return _parsed(original), _parsed(new)


def _refuse_plugin_change(change: FileChange, before: Any, after: Any) -> None:
    """Refuse where the description ``change`` edits would name plugins other than it names now,
    its document ``before`` the change and ``after`` it: its ``plugins`` list changed, in order
    so a reorder of the hooks counts; a file the change creates whose document names plugins; or
    a change of its ``includes`` bringing in or dropping a description that names plugins
    (:data:`PLUGINS`). ``before`` is ``None`` for a file the change creates, which named none
    before, and the refusal says which of the two it is, so each says what the reader changes by
    hand."""
    described = change.path
    if _listed(before, "plugins") != _listed(after, "plugins"):
        created = change.fingerprint is None
        raise EditError(PLUGINS, _PLUGINS_CREATED if created else _PLUGINS_LIST)
    # Seeded with the edited description, so a tree that leads back to it is not read for the
    # plugins it already names, which this edit of its includes does not change.
    seen = {described}
    for entry in set(_listed(before, "includes")) ^ set(_listed(after, "includes")):
        for included in included_files(described, entry):
            if _subtree_names_plugins(resolve_path(included), seen):
                raise EditError(PLUGINS, _PLUGINS_INCLUDES)


def _listed(data: Any, key: str) -> tuple[str, ...]:
    """What a description's document lists under ``project.<key>`` - its ``plugins``, the code
    it runs, or its ``includes`` - the strings of it in the order it lists them. Empty where it
    lists none, or the document is no project: a list the loader refuses with a ``schema`` error,
    one that is no list, names nothing, and neither does an entry that is no string.

    The one reading of those lists the session makes, so that its walks cannot come to two
    answers about one description: the plugins guard (:func:`_refuse_plugin_change`,
    :func:`_subtree_names_plugins`), what a revision watches (:func:`_watched`,
    :func:`_expanded_by`), and the files a project's own includes name (:func:`named_by`).

    Ordered, so that a reorder of ``plugins`` - which reorders the hooks that run - is a change.
    Order is held within one list alone: a reorder of ``includes`` is allowed, bringing in and
    dropping nothing, though it reorders the plugins the included descriptions name."""
    block = data.get("project") if isinstance(data, dict) else None
    listed = block.get(key) if isinstance(block, dict) else None
    if not isinstance(listed, list):
        return ()
    return tuple(entry for entry in listed if isinstance(entry, str))


def _subtree_names_plugins(project: Path, seen: set[Path]) -> bool:
    """Whether the description ``project`` names any plugin, or includes one that does, by the
    loader's reading of json alone - never importing a plugin to find out, which is the very
    thing the refusal is before. ``seen`` holds every description already read, so a tree that
    includes itself is walked once and the walk ends; a path already in it is passed over.

    Each file is read as the next analysis would read it (:func:`read_json`), but the walk goes
    further than that analysis: nothing caps how deep the includes lead, where the loader reads
    64 levels and files ``include-depth`` for what lies below. So a change of ``includes`` that
    brings in or drops a description naming plugins only below that depth is refused, though the
    analysis would load none of them; and a chain deep enough to raise ``RecursionError`` here,
    or a tree too large to hold, ``MemoryError``, is answered ``500``, the edit refused with
    nothing written. Both fail closed."""
    if project in seen:
        return False
    seen.add(project)
    data = read_json(project)
    if _listed(data, "plugins"):
        return True
    for entry in _listed(data, "includes"):
        for included in included_files(project, entry):
            if _subtree_names_plugins(resolve_path(included), seen):
                return True
    return False


def _confined(revision: Revision, pending: FileChange, changes: Sequence[FileChange]) -> FileChange:
    """One change of an edit, its file resolved and allowed: a description file of the open
    project, or a file the edit may create, which takes the access of the project description.

    A file to be created has had its name judged already, as every one of the edit has
    (:func:`_creatable`). Its path is resolved as the loader resolves one
    (:func:`ddd.loading.resolve_path`), and so is each other change's, to find the project
    description among them: a path the system will not resolve is handed back as given rather
    than raised on."""
    if pending.fingerprint is not None:
        return FileChange(
            source_path(revision, pending.path), pending.fingerprint, pending.operations
        )
    target = resolve_path(pending.path)
    project = revision.project
    described = next(
        (c for c in changes if c.fingerprint is not None and resolve_path(c.path) == project), None
    )
    if (
        target.parent != project.parent
        or described is None
        or target not in _included(project, described)
    ):
        raise EditError(
            INVALID,
            f"{pending.path} can be created only beside {project.name}, "
            "by an edit that adds it to the includes there",
        )
    return FileChange(target, None, pending.operations, like=project)


def _refuse_created_kind(change: FileChange, after: Any) -> None:
    """Refuse a file an edit creates that is no description ``ddd gui`` creates: ``after``, its
    document as the edit would leave it, no kind of description (:func:`kind_of`), or its name
    not a description's. A file that is there is passed over.

    The third rule a created file is held to, after its name is judged one a file can be created
    under (:func:`_creatable`) and its place beside the project description (:func:`_confined`):
    asked of each change in turn as the edit judges it, before the plugins that change would
    name (:func:`_refuse_plugin_change`), so that an edit is refused for the first fault of its
    first change at fault. Nothing a plan creates is refused here, every one of them a
    description named as one."""
    if change.fingerprint is not None:
        return
    if kind_of(change.path, after) not in KINDS:
        raise EditError(
            INVALID,
            f"{change.path.as_posix()} cannot be created: ddd gui creates a project's "
            "description files, and this is not one",
        )
    # Besides its content: a description is named *.ddd.json, the one name every create flow
    # writes (:data:`ddd.loading.DDD_SUFFIX`). kind_of reads a name that is not a plugin's by its
    # content alone, so this is what keeps a valid description from being written under any other
    # name.
    if not change.path.name.lower().endswith(DDD_SUFFIX):
        raise EditError(
            INVALID,
            f"{change.path.as_posix()} cannot be created: ddd gui names a description it "
            f"creates '*{DDD_SUFFIX}'",
        )


def _included(project: Path, change: FileChange) -> frozenset[Path]:
    """The files the project description's ``includes`` name once ``change`` is made to it, each
    entry resolved as the loader resolves one naming a file.

    Made in memory by the edit engine itself, so a description that changed on disk since the
    change was computed is refused as stale here, as the engine would refuse it. A pattern is
    not expanded: the file it would have to match does not exist yet.
    """
    _, new = edited(FileChange(project, change.fingerprint, change.operations))
    entries = Document(new.decode("utf-8-sig")).value_at("project.includes")
    return frozenset(
        resolve_path(project.parent / entry)
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, str)
    )


def _files_read(runs: Sequence[Run], indexed: Run | None) -> dict[Path, FileRead]:
    """What each file the runs read was read as: by ``indexed``, the run the revision's index
    comes from (:attr:`Revision.index`), and a file it did not read by the first run reading it.

    Every run of one project reads the same files, and reads the same bytes of each unless a save
    lands between two of them. The index is the first run's that built one - a later run's, where
    the first read no further than the project description - so a file is fingerprinted as the
    bytes the index was built from: a plan made from the index, changing a file a save has reached
    since, is refused as stale rather than applied to bytes the index does not describe. Taken
    from the first run instead, a description that run read no further, saved between two runs and
    put back after, carried the fingerprint of the bytes put back, and a plan made from the index
    of the others passed the stale check."""
    read: dict[Path, FileRead] = {} if indexed is None else dict(indexed.files_read)
    for run in runs:
        for path, file in run.files_read.items():
            read.setdefault(path, file)
    return read


def _described(path: Path, findings: Iterable[Diagnostic], read: FileRead | None) -> SourceFile:
    """One file of a revision, as its analysis read it (``read``) and never as the disk holds it
    once the analysis is over: a save landing in between holds other bytes than the ones the
    findings and the index are of. A file no run's read parsed has no such record and is read as
    it stands (:func:`_as_it_stands`)."""
    listed = list(findings)
    if read is None:
        read = _as_it_stands(path)
    return SourceFile(
        path=path,
        kind=_kind_shown(path, read.kind),
        name=read.name,
        loaded=not any(f.check in LOAD_CHECKS and f.severity is Severity.ERROR for f in listed),
        fingerprint=read.fingerprint,
        errors=sum(1 for f in listed if f.severity is Severity.ERROR),
        warnings=sum(1 for f in listed if f.severity is Severity.WARNING),
        infos=sum(1 for f in listed if f.severity is Severity.INFO),
    )


def _as_it_stands(path: Path) -> FileRead:
    """A file no run's read parsed, as it stands: a plugin, which the loader imports and never
    parses, so its bytes alone; or a file only a finding names."""
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        # Read as empty, a path the system refuses even to look at - a NUL byte - as much as one
        # that cannot be read: the run has said why already, and the revision carries it.
        data = b""
    if path.suffix == ".py":
        return FileRead.of(data, None)
    return FileRead.of(data, _parsed(data))


def kind_of(path: Path, parsed: Any) -> str:
    """What a file is, as ``State.files`` tells the page: ``plugin`` for a file whose name ends
    ``.py``, whatever it holds; otherwise the first of :data:`KINDS` at the top level of
    ``parsed`` (:func:`~ddd.loading.top_level_kind`) - the file read by the loader's own rule,
    ``None`` where it does not parse - and ``unknown`` where none is.

    Public for ``GET /api/files-plan``, which asks it of a file a reader would add to the
    project, so that the Files tab refuses a file by the very rule its rows are shown by: a
    revision's files are shown by the kind their analysis read (:func:`_described`), told by the
    same rule."""
    return _kind_shown(path, top_level_kind(parsed))


def _kind_shown(path: Path, stated: str | None) -> str:
    """What :func:`kind_of` shows a file as, its top level stating ``stated``."""
    if path.suffix == ".py":
        return "plugin"
    if stated is None:
        return "unknown"
    return stated


def _descriptions(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, subdirectories, files in root.walk():
        depth = len(directory.relative_to(root).parts)
        # A junction is passed over as a symbolic link is: ``Path.walk`` does so itself from
        # 3.13, and on 3.12 it would go into one, so the rule is stated here for every Python
        # the project admits, and :func:`walk_finds` asks the same of each directory.
        subdirectories[:] = [
            name
            for name in subdirectories
            if depth < SEARCH_DEPTH and not _skipped(name) and not (directory / name).is_junction()
        ]
        found.extend(
            directory / name
            for name in files
            if name.endswith(DESCRIPTION_SUFFIX) and _is_project(directory / name)
        )
    return found


def _skipped(name: str) -> bool:
    return (
        name.startswith(".")
        or name == "node_modules"
        or any(fnmatch(name, pattern) for pattern in BUILD_DIRECTORY_PATTERNS)
    )


def read_json(path: Path) -> Any:
    """The document ``path`` holds, read as the loader reads json (:func:`_parsed`), or ``None``
    where the file cannot be read or does not parse. Public for the api, which names the open
    project by its description as it stands (:func:`name_in`) and tells what a file a reader would
    add to the project is (:func:`kind_of`) by it."""
    try:
        return _parsed(path.read_bytes())
    except (OSError, ValueError):
        # ValueError as much as OSError: a path holding a NUL byte makes `read_bytes` raise, as
        # the loader's own read of a file (`ddd.loading._read_bytes`) and `resolve_path` both
        # catch it and go on, so a file is read here as the next analysis would read it, or is
        # not read at all. The walk for plugins reading through this goes further than that
        # analysis goes, which `_subtree_names_plugins` says.
        return None


def _parsed(data: bytes) -> Any:
    try:
        return parse_json_text(data.decode("utf-8-sig"))
    except ValueError:
        return None


def _is_project(path: Path) -> bool:
    data = read_json(path)
    return isinstance(data, dict) and isinstance(data.get("project"), dict)


def named_by(project: Path) -> set[Path]:
    """The project description and every file its own ``includes`` name now, by the loader's own
    rule: the descriptions the first analysis of a project is about to read, stamped before it
    reads them so that opening a flat project naming no plugin analyses it once. Neither a
    sub-project's ``includes`` nor the project's ``plugins`` are read: those files have no stamp
    from before, and cost opening the one analysis more it always cost, which the first revision
    asks for as it is published.

    Read again after :func:`_is_project` judged the file, by the one reading of a description's
    lists (:func:`_listed`), so that a description changed in between to no project, or to an
    ``includes`` that is no list, names nothing more than itself - the loader refusing such a
    list with a ``schema`` error.
    """
    named = {project}
    for entry in _listed(read_json(project), "includes"):
        named.update(included_files(project, entry))
    return named


def _watched(
    descriptions: Iterable[Path], records: Iterable[Path]
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """What a revision watches (:attr:`Revision.watched`), and the plugin files among it, each
    sorted: every build record of ``records``, and for each project description of
    ``descriptions`` - each one its analysis read, the project's own among them - where its
    wildcard includes expand (:func:`_expanded_by`) and every file its ``plugins`` list names by
    its path, loaded or not (:func:`ddd.plugins.plugin_files`), which are the plugin files.

    Each description is read again for its lists, by the loader's reading of json: a run keeps no
    list it read, and a description saved since its run read it is a file the revision stamps
    already, whose change makes the next analysis. A plugin named as a module is no path, and is
    passed over: finding its file can import its parents, running code no analysis ran - a
    description that does not validate loads none of the plugins it names."""
    watched = set(records)
    plugins: set[Path] = set()
    for described in descriptions:
        data = read_json(described)
        watched |= _expanded_by(described, data)
        for spelling in _listed(data, "plugins"):
            if spelling.endswith(".py"):
                plugins.update(plugin_files(spelling, described.parent))
    return tuple(sorted(watched | plugins)), tuple(sorted(plugins))


def _tell_changed_plugins(runs: Sequence[Run], plugins: Iterable[Path]) -> None:
    """File ``plugin-changed`` on each of ``plugins`` whose file changed since this process imported
    it (:func:`ddd.plugins.changed_since_imported`), into each of ``runs``, which grades it under
    its build's severities as it grades every other finding: a module is imported once per
    process, so ``ddd gui`` runs the old code until it is restarted, and every finding of the
    analysis is that code's. Several builds grading it alike file it once, as they file any
    finding (:func:`~ddd.lsp.diagnostics.group_findings`).

    ``plugins`` are the plugin files the revision watches (:func:`_watched`), every file a
    ``plugins`` list names by its path, loaded or not, rather than the files the runs covered: a
    run its plugin's model ended covers the project description alone, and that plugin is the one
    most in need of telling, its mended model never having run. Nothing else the revision watches
    is asked: no module is run from a directory a pattern walks or from a build record, and their
    names need not even be text - a directory named in Latin-1, as an old archive leaves one, is
    spelled with a lone surrogate. A plugin named as a module is passed over with them, the
    environment importing it as it imports any other."""
    changed = [path for path in plugins if changed_since_imported(path)]
    for run in runs:
        for path in changed:
            run.bag.add(
                "plugin-changed",
                f"'{path.name}' changed since ddd gui imported it: a module is imported once per "
                "process, so ddd gui runs the old code until it is restarted",
                Location(path),
            )


def _expanded_by(described: Path, data: Any) -> set[Path]:
    """Where every wildcard include of the description ``described``, its document ``data``,
    expands (:func:`_expanded_in`); nothing where it is no project."""
    expanded: set[Path] = set()
    for entry in _listed(data, "includes"):
        expanded |= _expanded_in(described, entry)
    return expanded


def _expanded_in(source: Path, entry: str) -> set[Path]:
    """Where the ``includes`` entry ``entry`` of the description ``source`` expands, as the loader
    expands it (:func:`ddd.loading.expand_include`): what the poll stamps so that a file a pattern
    comes to match, or stops matching, makes a new revision - creating or removing an entry moves
    its directory's modification time, one stat where expanding the pattern again at every poll
    would walk it.

    For a pattern, each directory a wildcard of it is matched in, every directory a ``**`` walks
    among them, hidden ones too, as the loader's walk goes into them - where a name that is no
    wildcard leads to one, the path it names there or not, so that its being made is noticed too -
    and, where its last name is no wildcard, each path that name is looked up at. A directory a
    name is only passed through on the way to another is not listed, and is not watched:
    ``src/components/*.ddd.json`` lists ``src/components``, and a file saved in ``src``, or beside
    the description including it - an editor's swap file - is no change of that project, while
    ``src/components`` itself, stamped there or not, notices its being made all the same; and
    ``../shared/*.ddd.json`` leaves the directory holding the project's checkout unwatched, a
    sibling clone made there no change either. Nothing for an entry naming a file,
    wildcard characters and all, which the loader reads before it reads the entry as a pattern
    and the revision stamps as one of its files; nothing either for a pattern pathlib refuses,
    which the analysis reports as ``include-empty``. Each directory is spelled as the loader's
    walk finds it, under the directory the walk starts in, so that two analyses stamp one
    spelling."""
    if not any(character in entry for character in _WILDCARDS):
        return set()
    raw = Path(entry)
    # The loader's own reading of the entry: tried as a file first, and a pattern's walk starting
    # at its own anchor joined onto the description's directory (`ddd.loading._pattern_anchor`).
    candidate = raw if raw.is_absolute() else source.parent / raw
    if os.path.isfile(candidate):  # noqa: PTH113
        return set()
    base = source.parent / raw.anchor if raw.anchor else source.parent
    parts = (raw.relative_to(raw.anchor) if raw.anchor else raw).parts
    expanded: set[Path] = set()
    # The paths the name at each depth is matched in, or looked up at.
    level = [base]
    try:
        for depth, part in enumerate(parts):
            prefix = "/".join(parts[: depth + 1])
            if part == "**":
                # Every directory it walks, the ones it starts in among them, as pathlib walks.
                level = [found for found in base.glob(prefix) if found.is_dir()]
                expanded.update(level)
            elif any(character in part for character in _WILDCARDS):
                expanded.update(level)
                # Listed for the directories it matches only where a name follows: a wildcard in
                # the last name, as in ``comps/*.ddd.json``, lists nothing here, which the loader's
                # own expansion lists.
                if depth < len(parts) - 1:
                    level = [found for found in base.glob(prefix) if found.is_dir()]
            else:
                level = [directory / part for directory in level]
                # Watched where a wildcard is matched in it next - a ``**`` among them, whose walk
                # yields nothing while it is not there - or where it is the path a match ends at:
                # a directory a name is only passed through on the way to another is no listing.
                last = depth == len(parts) - 1
                if last or any(character in parts[depth + 1] for character in _WILDCARDS):
                    expanded.update(level)
    except (OSError, ValueError, NotImplementedError):
        return set()
    return expanded


def _generated(project: Path, root: Path) -> Generated | None:
    """How a build generates the project description ``project``, where the build record beside
    it names it; ``None`` otherwise.

    What ``ddd_generate`` leaves where it collects a project out of an image's link closure: the
    description and the record of that build, written into one directory, its output directory.
    A project somebody wrote has the record beside it too where its output directory is the
    description's own, and that record says so: its ``origin`` is ``given``, the description given
    to the build as ``PROJECT``, which the build does not write - ``None``. A record without the
    key, as every record is that a build wrote before it and every one of a collected description,
    or saying anything else, is the build's: reading it as given would open each build made before
    to edits the next configure undoes, and a project given with such a record beside it stays
    refused until the build is configured again. Looked for beside the description whatever build
    directories the session was given, which are where it finds the builds whose severities
    apply: a build tree under any other name is the build's all the same.

    Read for what it names alone - the project, whether it was given, and the image for the
    sentence - by the loader's reading of json, and not as :func:`ddd.lsp.discovery.load_builds`
    reads a record. That reader asks whether this version can apply the record's severities, and
    declines one written by a newer DDD, in a format past its own, or naming a check it has not
    got; the description beside such a record, unless it says it was given, is written again at
    every configure all the same. A record naming no project by a path names nothing here.

    A record there that does not read as one - not json, a write of it cut short among them, or
    no object - cannot say whether the build writes the description, and the refusal fails
    closed: the description is taken for the build's, naming the record (:attr:`Generated.unread`),
    until it reads, which its revision watches for (:attr:`Revision.watched`). Read as no record,
    a write that died left a generated description open to edits the next configure undoes."""
    beside = project.parent / BUILD_INFO_FILENAME
    record = read_json(beside)
    if not isinstance(record, dict):
        # Asked with os.path.isfile, which answers false for a path it cannot look at.
        if not os.path.isfile(beside):  # noqa: PTH113
            return None
        return Generated("", _build_tree(project.parent), unread=beside)
    named = record.get("project")
    if not isinstance(named, str) or not _readable_project(named, root, project.parent):
        return None
    if resolve_path(Path(named)) != project:
        return None
    # Only a record saying the description was given to the build, as PROJECT, leaves it to the
    # person who wrote it. One without the key - every record a build wrote before the key, and
    # every record of a collected description - or saying anything else is the build's.
    if record.get("origin") == "given":
        return None
    image = record.get("image")
    if not isinstance(image, str):
        image = ""
    return Generated(image, _build_tree(project.parent))


def _build_tree(directory: Path) -> Path:
    """The build tree a build record in ``directory`` belongs to, every file under which the build
    writes: the nearest directory at or above ``directory`` holding a ``CMakeCache.txt``, unless
    the source tree that cache was configured from lies at or under it - an in-source build, or a
    source tree inside its build tree - where refusing the tree would refuse every component, and
    ``directory`` alone is the build's. So it is where no cache is found, the record written by
    another build system or into an output directory outside the build tree, and where the cache
    does not say which source tree it was configured from (:func:`_source_tree`).

    Asked with :func:`os.path.isfile`, which answers false for a path it cannot look at, where
    ``Path.is_file`` raises for some on python 3.12."""
    for candidate in (directory, *directory.parents):
        cache = candidate / _CMAKE_CACHE
        if not os.path.isfile(cache):  # noqa: PTH113
            continue
        source = _source_tree(cache)
        if source is None:
            return directory
        if source.is_relative_to(candidate):
            return directory
        return candidate
    return directory


def _source_tree(cache: Path) -> Path | None:
    """The source tree the CMake cache ``cache`` was configured from - its
    ``CMAKE_HOME_DIRECTORY``, resolved - or ``None`` where the cache cannot be read or does not
    say, an entry spelling nothing among them."""
    try:
        text = cache.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith(_HOME_DIRECTORY):
            named = line.removeprefix(_HOME_DIRECTORY)
            # An entry spelling nothing says nothing: read as a path, it was the directory the
            # process was started in.
            if not named:
                return None
            return resolve_path(Path(named))
    return None


def name_in(data: Any, kind: str) -> str | None:
    """The ``name`` the ``kind`` block of the document ``data`` states, or ``None`` where it holds
    no such block, or the block names nothing as a string: what the start page lists a project as,
    and the api names the open one by."""
    block = data.get(kind) if isinstance(data, dict) else None
    name = block.get("name") if isinstance(block, dict) else None
    return name if isinstance(name, str) else None


def stamped(paths: Iterable[Path]) -> dict[Path, tuple[int, int] | None]:
    """The modification time and size of each path, ``None`` for one that is not there - or that
    the system refuses even to look at: one holding a NUL byte, on every system, or one holding a
    character the encoding of a path to bytes cannot write, where paths are so encoded, as on
    Linux - U+D800 is one. No analysis can read either.

    How this session decides a file has changed, without a file watcher the standard library
    does not have: taken again and compared with what was taken before. Shared with
    :mod:`ddd.gui.compare`, which asks the same question of a baseline's own files, rather than
    read a second way there - a baseline may perfectly well *be* the open project's description
    (spec 2026-09-26-gui-compare-design.md §3), and two readings of "has this file changed"
    disagreeing about one file is exactly the answer nobody could explain.
    """
    signature: dict[Path, tuple[int, int] | None] = {}
    for path in paths:
        try:
            status = path.stat()
        except (OSError, ValueError):
            signature[path] = None
        else:
            signature[path] = (status.st_mtime_ns, status.st_size)
    return signature
