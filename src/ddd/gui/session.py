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
Linux development PC, Python 3.14 - which is why a round holds no lock while it stamps
(:meth:`Session.poll`). A file a wildcard include would match only once it exists is noticed when
something else changes, which is a limit of the preview.

The analysis is the language server's, run the way ``ddd lsp`` runs it: under the severities of
every build record naming the project, or under the defaults when none does.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final

from ddd.build_info import BuildInfo
from ddd.deliveries import Resolved
from ddd.diagnostics import CheckInfo, Diagnostic, Severity
from ddd.editing import (
    INVALID,
    STALE,
    EditError,
    FileChange,
    Written,
    apply_changes,
    edited,
    fingerprint,
    restore,
)
from ddd.ir import DataDictionary
from ddd.loading import included_files, parse_json_text, resolve_path
from ddd.lsp.diagnostics import Run, group_findings, run_build, run_project
from ddd.lsp.discovery import BUILD_DIRECTORY_PATTERNS, discover
from ddd.lsp.navigation import LOAD_CHECKS, Index
from ddd.lsp.ranges import Document

KINDS: Final = ("project", "component", "types", "units", "sections", "constants", "rasters")
"""The top-level keys that say what a description file is, as the loader reads them."""

SEARCH_DEPTH: Final = 4
"""How many directories below the start the search for project descriptions goes."""

UNKNOWN: Final = (-1, -1)
"""The stamp of a file whose modification time and size were not taken before an analysis read
it: a size no file has, so a poll finds the file changed. A revision published with one asks for
the next analysis itself (:meth:`Session._finished`); an analysis that raised leaves every file
it stamped so, and the next poll asks again."""

MAX_UNDO: Final = 50
"""How many edits the stack keeps, the oldest falling off: a session that runs all day does not
grow without bound, and fifty is far past what a reader walks back by hand."""


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
    run that built one, since every run of one project reads the same files."""

    served: tuple[Path, ...]
    """The directories a file of this project may be read from and written to through the
    interface: the one the session was given, and the open project's own where the operator
    named a project from outside it.

    Belonging to the project is not enough, because what a project includes is the project's
    own business - a directory up, which is where a shared vocabulary lives - and an edit may
    add such an entry. A reader of the page could otherwise widen the page's own reach: point
    the includes at a file anywhere and read it back. These cannot be widened that way, being
    what ``ddd gui`` was started in and what it was pointed at. A file outside them still takes
    part in the analysis and is named by the findings on it, the page reporting what
    ``ddd check`` reports; its contents are neither read, written, nor shown in a preview.
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
    for info in discover(base, build_directories, refused):
        images.setdefault(Path(info.project).resolve(), []).append(info.image)
    paths = sorted(set(images) | set(_descriptions(base)))
    projects = tuple(
        FoundProject(path, _name_in(_read_json(path), "project"), tuple(images.get(path, ())))
        for path in paths
    )
    return Found(base, projects, tuple(sorted(refused.items())))


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
    runs. Nothing on disk is touched holding it but the files an edit or an undo writes, so that
    the number it takes, the stack and the files waiting for an analysis move with the write: the
    poll stamps the files without it (:meth:`poll`), an analysis stamps those it is about to read
    without it (:meth:`_next`), and opening reads what a project includes before taking it
    (:meth:`open`). While another thread computes, every system call waits out that thread's
    turn of the interpreter, and a lock held across a project's thousands of files held every
    edit, state and plan behind them: edits asked 0.2 to 3.0 s into an analysis of a generated
    project of 100,000 declarations answered in 2 to 3,363 ms while the poll stamped holding it,
    and in 2 to 129 ms since - one run each, seven edits, on the Linux development PC.
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

        What its own includes name (:func:`_named_by`) is read before the lock is taken, as
        whether it is a project description at all is: the description read and its patterns
        expanded on disk, system calls each of which waits out any busy thread's turn. Sound,
        because what it names is only which files are stamped as the first analysis begins, the
        stamps themselves taken then (:meth:`_next`): a description changed in between names a
        file with no stamp from before, which costs the one analysis more any such file costs
        (:meth:`_finished`).
        """
        path = project.resolve()
        if not _is_project(path):
            raise ValueError(f"{project} is not a project description")
        named = _named_by(path)
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
        """Ask for an analysis if a file of the open project changed on disk since its stamps
        were taken; say whether one did.

        The files are stamped without the lock, which is held only to read the stamps to compare
        with and then to compare and ask: one stat a file, each waiting out any busy thread's
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

    def edit(self, changes: Sequence[FileChange], label: str) -> tuple[int, tuple[Written, ...]]:
        """Make an edit of description files of the open project, ask for its analysis, and
        answer the number it took and what it wrote.

        A change without a fingerprint creates its file, and only the kind of file adopting a
        vocabulary writes: one beside the project description, in an edit whose change of that
        description includes it. Any other is refused before a file is touched.

        ``label`` is what the page calls this edit - "the unit of ValueA" - and is what an undo
        of it offers to put back.
        """
        with self._lock:
            revision = self._required()
            confined = [_confined(revision, pending, changes) for pending in changes]
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
        ignored: dict[Path, str] = {}  # the start page is where a refused record is reported
        builds = tuple(
            info
            for info in discover(self.root, self.build_directories, ignored)
            if Path(info.project).resolve() == project
        )
        runs = _runs(project, builds)
        grouped, covered = _grouped(runs, project)
        registered = {info.identifier: info for run in runs for info in run.bag.registered.values()}
        # The project's own directory as well, where it is not already inside the root: a
        # project named on the command line from elsewhere. Two statements rather than one
        # conditional expression, which coverage.py counts no branch in, so the arm no test
        # took would pass the gate unexercised.
        served: tuple[Path, ...] = (self.root,)
        if not project.parent.is_relative_to(self.root):
            served = (self.root, project.parent)
        files = tuple(_described(path, grouped.get(path, ())) for path in sorted(covered))
        findings = _filed(grouped)
        return Revision(
            # Numbered when it is published (`_finished`): an analysis thrown away takes none.
            number=0,
            project=project,
            builds=builds,
            files=files,
            findings=findings,
            # One run's whole answer, never a field picked from each: the plugins a comparison
            # runs the rules of and the dictionary it compares have to be the same read's, and
            # two `next()` calls over the same list would only agree by coincidence.
            resolved=next((run.resolved for run in runs if run.resolved is not None), None),
            analysed=all(run.resolved is not None for run in runs),
            checks=tuple(registered.values()),
            index=next((run.index for run in runs if run.index is not None), None),
            served=served,
            resolved_paths=_resolved_paths(files, findings),
        )

    def _request(self) -> None:
        """Ask for an analysis of the open project. Holding the lock, with a project open, once
        whatever asked has changed what it changes: the version moves with it."""
        self._asked = self._project
        self._version += 1
        self._changed.notify_all()

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
        revision, its files stamped as they were before it read them - a file with no stamp from
        before :data:`UNKNOWN` - and where it raised instead, ``revision`` being ``None``,
        nothing is published and every file it stamped is stamped unknown, so that the next poll
        asks again.

        Before, never after: stamped after the analysis, a save landing while it ran was already
        in the stamps, so no poll ever saw it and the page kept the findings of bytes no longer
        on disk. A file with no stamp from before - a sub-project's file or a plugin, when the
        project was just opened, or a file the analysis found newly included - is stamped
        :data:`UNKNOWN`, and the revision is published asking for the next analysis: one
        analysis more, which catches a save made to that file while this one ran. Asked here
        rather than left to the next poll, which asked for it up to ``poll_interval`` later, so
        that the session says it is analysing until that analysis lands, rather than that it is
        done and then, a poll later, that it is analysing again.

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
                    file.path: begun.stamps.get(file.path, UNKNOWN) for file in revision.files
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


def _source(revision: Revision, path: Path) -> Path:
    """One path the page gave, resolved and allowed: a description file of the open project,
    inside a directory the session serves.

    Both, not membership alone. ``POST /api/edit`` naming a file a directory up in the project's
    ``includes`` and ``GET /api/file`` reading it back was the page widening its own reach - and
    checked here rather than at that one route, because this is where every route that takes a
    path from the page resolves it, and where an edit resolves the file it writes.
    """
    resolved = path.resolve()
    if not any(file.path == resolved and file.kind != "plugin" for file in revision.files):
        raise NotInProjectError(f"{path.as_posix()} is not a description file of the open project")
    return _served(revision, resolved)


def _served(revision: Revision, resolved: Path) -> Path:
    """One resolved path, allowed where it lies inside a directory the session serves.

    Membership of the open project is not this question and does not answer it: an edit may add
    anything to the project's own ``includes``, so a reader of the page can make a file
    anywhere part of the project and then ask for it. What the session serves cannot be widened
    that way - see :attr:`Revision.served`.
    """
    if not any(resolved.is_relative_to(directory) for directory in revision.served):
        serves = " and ".join(directory.as_posix() for directory in revision.served)
        raise NotInProjectError(
            f"{resolved.as_posix()} is a description file of the open project, but ddd gui "
            f"serves {serves}; "
            "start it in a directory holding this file to reach it here"
        )
    return resolved


def _confined(revision: Revision, pending: FileChange, changes: Sequence[FileChange]) -> FileChange:
    """One change of an edit, its file resolved and allowed: a description file of the open
    project, or a file the edit may create, which takes the access of the project description."""
    if pending.fingerprint is not None:
        return FileChange(_source(revision, pending.path), pending.fingerprint, pending.operations)
    target = pending.path.resolve()
    project = revision.project
    described = next(
        (c for c in changes if c.fingerprint is not None and c.path.resolve() == project), None
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


def _described(path: Path, findings: Iterable[Diagnostic]) -> SourceFile:
    listed = list(findings)
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        # Read as empty, a path the system refuses even to look at - a NUL byte - as much as one
        # that cannot be read: the loader has said why already, and the revision carries it.
        data = b""
    parsed = None if path.suffix == ".py" else _parsed(data)
    kind = kind_of(path, parsed)
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


def kind_of(path: Path, parsed: Any) -> str:
    """What a file is, as ``State.files`` tells the page: ``plugin`` for a file whose name ends
    ``.py``, whatever it holds; otherwise the first of :data:`KINDS` at the top level of
    ``parsed`` - the file read by the loader's own rule, ``None`` where it does not parse - and
    ``unknown`` where none is.

    Public for ``GET /api/files-plan``, which asks it of a file a reader would add to the
    project, so that the Files tab refuses a file by the very rule its rows are shown by."""
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


def _named_by(project: Path) -> set[Path]:
    """The project description and every file its own ``includes`` name now, by the loader's own
    rule: the descriptions the first analysis of a project is about to read, stamped before it
    reads them so that opening a flat project naming no plugin analyses it once. Neither a
    sub-project's ``includes`` nor the project's ``plugins`` are read: those files have no stamp
    from before, and cost opening the one analysis more it always cost, which the first revision
    asks for as it is published.

    Read again after :func:`_is_project` judged the file, so the two conditional expressions
    guard a description changed in between; an ``includes`` that is not a list names nothing,
    the loader refusing it with a ``schema`` error.
    """
    named = {project}
    data = _read_json(project)
    block = data.get("project") if isinstance(data, dict) else None
    listed = block.get("includes") if isinstance(block, dict) else None
    if isinstance(listed, list):
        for entry in listed:
            named.update(included_files(project, entry))
    return named


def _name_in(data: Any, kind: str) -> str | None:
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
