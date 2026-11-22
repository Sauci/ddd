"""The server half of the benchmark of ``ddd gui`` on a large project.

Times, in order, opening a project through ``POST /api/open``, each of ``GET /api/state``,
``/graph``, ``/units``, ``/types``, ``/shared`` and ``/files``, the Findings tab's first page of
findings and every finding of one component's file, a variable's panel, a unit's panel, the plan
of a variable declared in the largest file, judging a removal on the Files tab, one analysis, an
edit's round trip, planning the rename of the unit stated in the most files and applying that
plan - the server driven in process, over one :class:`~ddd.gui.session.Session` and one
:class:`~ddd.gui.api.Api` (``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md``
§4). Then, over a second session polling at ``ddd gui``'s own interval, three requests each asked
halfway through an analysis, to be answered while it runs: ``GET /api/state``, the plan of the
edit's own change - ``GET /api/settle``, what a variable's panel asks while a reader picks a
unit - and the edit itself. One answered once its analysis had ended is no such figure, and is
written refused, a sentence in its figure's place. Everything a measure needs to choose - the
file, the variable, the unit, the entry to remove, the unit to rename - is read off the project's
own analysed revision, sorted, so the same project measures the same things on every run;
nothing here imports the generator. A measure the spec's §3 gives a budget to is held to it
(:data:`BUDGETS`), and :func:`main` says of each whether it met it.

Every measure but ``open analysed``, ``analysis`` and ``edit analysed`` answers a reply whose
body is timed serialised exactly as the server would send it, ``json.dumps(reply.body,
allow_nan=False)`` inside the timed span, the size being those bytes; each that posts a body
records that body's bytes too, posted as the page posts one. The session analyses on a thread of
its own, as ``ddd gui``'s does: ``open answered`` is timed until the open's reply - the project
named, before its first analysis has landed - and ``open analysed`` from the same moment until
that analysis has landed; ``analysis`` until the analysis it asks for has landed; ``edit
answered`` until the edit's reply - written, before its analysis has landed - and ``edit
analysed`` from the same moment until that analysis has landed. ``rename plan`` is asked once
that analysis has landed, and only plans: ``applied rename`` posts that plan's changes to
``POST /api/edit`` as the page's Apply posts them, timed until the edit's reply, and is undone
once its analysis has landed. ``plan in the largest file`` settles the unit of a variable the
component file declaring the most declares: the plan a panel asks there, which writes nothing.

``measure`` undoes each edit it made and stops each analyser it started before it returns, then
puts back the times of each path it changed, so a second run measures the same bytes, with the
same modification times. Not part of the ``ddd`` package, like
``generate_project.py`` beside it: a tool of the repository's own, run by hand - it is slow on a
large project, and the machine's own (*Global Constraints*) - never in CI, and checked only by
``tests/test_bench_gui.py``'s smoke test on a small generated project.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from ddd.gui.api import Api, Reply
from ddd.gui.session import Revision, Session
from ddd.loading import fingerprint
from ddd.lsp.navigation import Index
from ddd.variables import Declared, declarations_of

NAMES: Final[tuple[str, ...]] = (
    "open answered",
    "open analysed",
    "state",
    "graph",
    "units",
    "types",
    "shared",
    "files",
    "findings page",
    "findings of a file",
    "variable",
    "unit",
    "plan in the largest file",
    "remove judged",
    "analysis",
    "edit answered",
    "edit analysed",
    "rename plan",
    "applied rename",
    "state while analysing",
    "plan while analysing",
    "edit while analysing",
)
"""Every measure :func:`measure` takes, in the order it takes them."""

_TABS_AND_PANELS: Final = (
    "state",
    "graph",
    "units",
    "types",
    "shared",
    "files",
    "findings page",
    "findings of a file",
    "variable",
    "unit",
    "state while analysing",
)
_PLANS: Final = ("plan in the largest file", "rename plan", "plan while analysing")
_APPLIES: Final = ("edit answered", "applied rename", "edit while analysing")

BUDGETS: Final[Mapping[str, int]] = {
    "open answered": 1_000,
    **dict.fromkeys(_TABS_AND_PANELS, 1_000),
    **dict.fromkeys(_PLANS, 1_000),
    **dict.fromkeys(_APPLIES, 500),
}
"""The milliseconds a measure is held to, by its name, where §3 of the spec holds it to a figure.
Those budgets are the page's own, and the server half times what the page waits on: a figure over
its budget says the page cannot meet it, and one under it does not say the page does.

The page answering after a project is opened, under 1 s: ``open answered``. Any tab or panel
drawing once analysed, under 1 s: each tab's and panel's request, idle and while an analysis
runs, and each plan - what a panel draws before it offers its Apply, every plan being bound to
that budget on the Linux development PC (decision 14.5 of the review fixes' plan). An Apply's own
change showing, under 500 ms: each edit. The others are held to no figure of §3: ``open
analysed`` and ``edit analysed`` are budgeted one analysis and a second more, the project's own
time rather than a figure; judging a removal and the analysis itself, §3 budgets not at all."""

_ENDPOINTS: Final[tuple[str, ...]] = ("state", "graph", "units", "types", "shared", "files")
"""The plain ``GET /api/<name>`` measures, asked for with no query."""

_PAGE: Final = {"offset": ["0"], "limit": ["100"]}
"""What ``findings page`` asks of ``GET /api/findings``: the Findings tab's first page, as the
page asks it (``PAGE_SIZE`` in ``gui/src/lib/findingsWindow.ts``)."""

_FORWARD_SECONDS: Final = 3_600
"""How far :func:`_analysis` and :func:`_analysing` move a component file's modification time
forward, each from where it stands: past a filesystem's mtime resolution, so the next poll never
misses it. Put back as the run ends (:class:`_Times`)."""

_POLL_SECONDS: Final = 3_600
"""How often the first session's own poller looks at the disk: never while a run lasts.
``analysis`` polls for itself, and a poller noticing the moved file first would leave that poll
nothing to notice. The second session, the measures under load are taken over, polls at the
session's own default, as ``ddd gui``'s does."""

_BEGUN_SECONDS: Final = 60.0
"""How long :func:`_analysing` waits for the analysis it asks for to begin before ending the run:
a poll noticing the moved file asks for it at once, so only a session that noticed nothing waits
this long."""


_ENDED_FIRST: Final = (
    "answered once its analysis had ended, so no figure of a request answered while one runs"
)
"""What a measure under load is refused with, in its figure's place: asked halfway through its
analysis by the clock, it can still come back once that analysis has ended (Ruling F3)."""


@dataclass(frozen=True, slots=True)
class Measure:
    """One measure taken: how long it ran, and the bytes of its answer where it has one."""

    name: str
    milliseconds: float
    size: int | None
    """Bytes of ``reply.body`` serialised as the server sends it; ``None`` for a measure with no
    reply of its own (``open analysed``, ``analysis``, ``edit analysed``)."""
    refused: str | None = None
    """Why the measure is no figure of what its name says, written in the figure's place
    (:func:`main`): a measure under load answered once its analysis had ended. ``None`` for every
    figure; its time and size are then what :func:`main` writes, and are never written
    otherwise."""
    posted: int | None = None
    """Bytes of the body a measure posts, as the page posts it (:func:`_posted`): ``POST
    /api/open``'s, and each edit's - ``applied rename``'s the largest, every change of a rename
    across the project; ``None`` for a measure posting none."""


class _Watched(Session):
    """A session that says when each of its analyses has begun, and when it has ended: what each
    measure under load is asked at, so that it is answered while an analysis runs rather than
    before one has started, and what it is checked against once answered (:func:`_answered`).
    Polling at the session's own default, as ``ddd gui``'s does."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.begun = threading.Event()
        self.ended = threading.Event()

    def _analysed(self, project: Path) -> Revision:
        self.begun.set()
        try:
            return super()._analysed(project)
        finally:
            self.ended.set()


@dataclass(frozen=True, slots=True)
class _Chosen:
    """What the measures change, read off the project's first revision, sorted: the component
    file whose modification time asks for an analysis, and the edit's own change - the unit of
    the middle variable's first declaration, moved to the next one."""

    target: Path
    variable: str
    first: Declared
    unit: str
    """The unit the edit moves the declaration to: the next unit of the project's own vocabulary
    after its current one, wrapping round - not the generator's own units, so this reads any
    project without importing it."""


class _Times:
    """The access and modification times of each path a run changes, as found before the run
    first changed it, put back as the run ends whichever way it ends - a refusal and an exception
    among them - so that the next run, and anything else reading the project's times, finds them
    as they were: the component file whose time :func:`_analysis` and :func:`_analysing` move
    forward, the file the edits write and their undos write back, and the directory both are
    written in. A file left holding other bytes than it was found with - its edit's undo refused
    - keeps the time it was written at, so that nothing reading times takes it for unchanged."""

    def __init__(self) -> None:
        self._found: dict[Path, tuple[int, int, str | None]] = {}

    def keep(self, *paths: Path) -> None:
        """Note each of ``paths``' times as they are now, and each file's fingerprint, unless
        they are noted already."""
        for path in paths:
            if path not in self._found:
                found = path.stat()
                held = fingerprint(path.read_bytes()) if path.is_file() else None
                self._found[path] = (found.st_atime_ns, found.st_mtime_ns, held)

    def put_back(self) -> None:
        """Every time noted, put back where its path still holds what it was found with."""
        for path, (accessed, modified, held) in self._found.items():
            if held is None or fingerprint(path.read_bytes()) == held:
                os.utime(path, ns=(accessed, modified))


def measure(project: Path) -> list[Measure]:
    """Every measure of §4's server half, each taken once - over a fresh session opened on
    ``project``, then the measures under load over another - left as it was found: each edit this
    makes is undone before this returns, and once both sessions have stopped the times of each
    path it changed are put back (:class:`_Times`), so a second run measures the same project.

    Refused with a ``RuntimeError`` naming the precondition, before any measure but the open's is
    taken: ``project`` needs at least one component file (:func:`_analysis` has one to touch), at
    least two distinct units stated somewhere in it (the edit has another to move to), and its
    middle variable's first declaration must state its own unit rather than leave it to be filled
    some other way (there is otherwise nothing for the edit to read as "current"), as must the
    middle variable of the largest file's own declaration there (:func:`_in_the_largest_file`).
    Every project ``tools/generate_project.py`` makes satisfies all four. An open, a plan or an
    edit the server refuses ends the run with a ``RuntimeError`` as well, once any edit made has
    been undone: a refusal is no plan, nor an edit, and its time would read as one.
    """
    times = _Times()
    try:
        session = Session(project.parent, poll_interval=_POLL_SECONDS)
        session.start()
        try:
            taken, chosen = _measured(session, project, times)
        finally:
            session.stop()
        loaded = _Watched(project.parent)
        loaded.start()
        try:
            # Halfway through an analysis by this run's own measure of one: at 100,000
            # declarations, past reading the files and into analysing them.
            halfway = next(each for each in taken if each.name == "analysis").milliseconds / 2_000
            taken.extend(_under_load(loaded, project, chosen, halfway))
        finally:
            loaded.stop()
    finally:
        # Once both have stopped: a session polling would take a time put back for a change.
        times.put_back()
    return taken


def _measured(session: Session, project: Path, times: _Times) -> tuple[list[Measure], _Chosen]:
    """:func:`measure`'s first session's, over ``session``, whose analyser runs; and what the
    measures change, for the second's - whose times are noted in ``times`` before anything
    changes them."""
    api = Api(session, project, wait_seconds=0.0)
    taken = _opening(api, session, project)

    revision = session.revision
    if revision is None:
        raise RuntimeError(f"{project} did not open")
    built = revision.index
    if built is None:
        raise RuntimeError(f"{project} did not analyse enough to be measured")

    components = sorted(file.path for file in revision.files if file.kind == "component")
    if not components:
        raise RuntimeError(f"{project} has no component file for the benchmark to touch")

    units = sorted(built.units)
    if len(units) < 2:
        raise RuntimeError(
            f"{project} states {len(units)} unit(s); the benchmark needs at least two, so the "
            "edit has another one to move the declaration to"
        )

    variables = sorted(built.declarations)
    variable = variables[len(variables) // 2]
    declared = declarations_of(built, variable, {})
    if not declared:
        raise RuntimeError(f"{variable!r} has no declaration left of {project} to edit")
    if "unit" not in declared[0].stated:
        raise RuntimeError(
            f"{variable!r}'s first declaration in {project} does not state its own unit, "
            "which the benchmark needs to choose the edit's own change"
        )
    current = json.loads(declared[0].stated["unit"])
    chosen = _Chosen(
        components[0], variable, declared[0], units[(units.index(current) + 1) % len(units)]
    )
    edited = declared[0].site.path.resolve()
    times.keep(chosen.target, edited, edited.parent)

    entries: list[dict[str, Any]] = []
    for name in _ENDPOINTS:
        elapsed, reply, size = _get(api, f"/api/{name}")
        taken.append(Measure(name, elapsed, size))
        if name == "files":
            entries = reply.body["entries"]

    elapsed, _, size = _get(api, "/api/findings", _PAGE)
    taken.append(Measure("findings page", elapsed, size))

    # Every finding of one file, as a component's page asks for its own: no limit.
    elapsed, _, size = _get(api, "/api/findings", {"file": [components[0].as_posix()]})
    taken.append(Measure("findings of a file", elapsed, size))

    elapsed, _, size = _get(api, "/api/variable", {"name": [variable]})
    taken.append(Measure("variable", elapsed, size))

    elapsed, _, size = _get(api, "/api/unit", {"name": [units[0]]})
    taken.append(Measure("unit", elapsed, size))

    largest, settled, unit = _in_the_largest_file(built, units)
    asked = {"name": [settled], "key": ["unit"], "raw": [json.dumps(unit)]}
    elapsed, reply, size = _get(api, "/api/settle", asked)
    if reply.status != 200:
        raise RuntimeError(
            f"the benchmark's own plan in the largest file, {largest}, was refused: {reply.body}"
        )
    taken.append(Measure("plan in the largest file", elapsed, size))

    # The root's first entry, never its last: in a generated project the last is the pattern
    # ``components/*.ddd.json``, whose removal judges a project of one file. The first,
    # ``units.ddd.json``, is judged by analysing the whole project without it - one full
    # analysis with the includes changed, the cost this measure is for.
    removed = str(entries[0]["key"])
    elapsed, _, size = _get(api, "/api/files-plan", {"action": ["remove"], "path": [removed]})
    taken.append(Measure("remove judged", elapsed, size))

    taken.append(_analysis(session, chosen.target))

    answered, start = _edit(api, chosen, "edit answered")
    taken.append(answered)
    # Undone whatever follows raises, as a refusal of the rename plan does: the project is left
    # as it was found either way.
    try:
        session.settled(None)
        taken.append(Measure("edit analysed", _elapsed(start), None))
        # Asked once the edit's analysis has landed and before the undo: a plan changing a file
        # an edit wrote is refused until that edit's analysis has landed, and the undo writes
        # one again.
        renamed = _most_stated(built)
        to = _unused(built, renamed)
        asked = {"action": ["rename"], "unit": [renamed], "to": [to]}
        elapsed, reply, size = _get(api, "/api/unit-plan", asked)
        if reply.status != 200:
            raise RuntimeError(f"the benchmark's own rename plan was refused: {reply.body}")
        taken.append(Measure("rename plan", elapsed, size))
        label = f"the rename of '{renamed}' to '{to}'"
        taken.append(_applied(api, session, reply.body, label, times))
    finally:
        _undo(api, session)
    return taken, chosen


def _under_load(session: _Watched, project: Path, chosen: _Chosen, into: float) -> list[Measure]:
    """The measures taken while an analysis runs, the poller at ``ddd gui``'s own interval, over
    ``session``, whose analyser runs: once it has opened ``project``, its state, the plan of the
    edit's own change and the edit itself, each asked ``into`` seconds after an analysis has
    begun (:func:`_analysing`), and the session left to settle before the next one asks its own.

    ``GET /api/state`` is the first request of the newest revision, as the page's long poll is
    the first to hear of one, and so the one that derives it; the version moved when the analysis
    was asked, so its answer is made anew. ``GET /api/settle`` is what a variable's panel asks
    while a reader picks a unit for it, asked of a revision the state has derived already, as the
    page's long poll has by the time a reader picks anything. The edit is the first session's own,
    undone once its analysis has landed.

    Each is checked as its answer comes back (:func:`_answered`): one answered once its analysis
    had ended is kept in its place, refused, rather than reported as a figure of a request
    answered while one runs."""
    api = Api(session, project, wait_seconds=0.0)
    session.open(project)
    session.settled(None)
    taken: list[Measure] = []

    _analysing(session, chosen.target, into)
    elapsed, _, size = _get(api, "/api/state")
    taken.append(_answered(session, Measure("state while analysing", elapsed, size)))
    session.settled(None)

    api.handle("GET", "/api/state", {}, None)
    _analysing(session, chosen.target, into)
    asked = {"name": [chosen.variable], "key": ["unit"], "raw": [json.dumps(chosen.unit)]}
    elapsed, reply, size = _get(api, "/api/settle", asked)
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own plan was refused: {reply.body}")
    taken.append(_answered(session, Measure("plan while analysing", elapsed, size)))
    session.settled(None)

    _analysing(session, chosen.target, into)
    edited = _answered(session, _edit(api, chosen, "edit while analysing")[0])
    taken.append(edited)
    try:
        session.settled(None)
    finally:
        _undo(api, session)
    return taken


def _answered(session: _Watched, taken: Measure) -> Measure:
    """``taken``, a measure under load whose answer has just come back, as a figure while the
    analysis :func:`_analysing` asked it beside still runs, and refused once that analysis has
    ended (:data:`_ENDED_FIRST`). Read just after the answer rather than as it comes, so that an
    analysis ending in between refuses a figure it need not have: never the other way round."""
    if session.ended.is_set():
        return replace(taken, refused=_ENDED_FIRST)
    return taken


def _opening(api: Api, session: Session, project: Path) -> list[Measure]:
    """Opening ``project`` through ``POST /api/open``, in the body the start page posts: until
    its reply, and from the same moment until its first analysis has landed. ``project`` is the
    one ``api`` was given, the project named on the command line, which the server answers before
    any walk for the projects under its start directory: the open of a project the start page
    lists, which may walk, is not one the bench times. A refusal ends the run."""
    body = _posted({"path": project.resolve().as_posix()})
    start = time.perf_counter()
    reply = api.handle("POST", "/api/open", {}, body)
    serialised = json.dumps(reply.body, allow_nan=False)
    answered = _elapsed(start)
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own open was refused: {reply.body}")
    session.settled(None)
    return [
        Measure("open answered", answered, len(serialised.encode("utf-8")), posted=len(body)),
        Measure("open analysed", _elapsed(start), None),
    ]


def _analysis(session: Session, target: Path) -> Measure:
    """``target``'s modification time moved forward, then :meth:`Session.poll` until the
    analysis it asks for has landed. ``target`` is the first, sorted, of the project's own
    component files - chosen by :func:`measure`, which already confirmed there is at least
    one."""
    forward = target.stat().st_mtime + _FORWARD_SECONDS
    os.utime(target, (forward, forward))
    start = time.perf_counter()
    changed = session.poll()
    session.settled(None)
    elapsed = _elapsed(start)
    if not changed:
        raise RuntimeError(f"{target} was moved forward, but the poll after it saw no change")
    return Measure("analysis", elapsed, None)


def _analysing(session: _Watched, target: Path, into: float) -> None:
    """``target``'s modification time moved forward and the session polled, returning ``into``
    seconds after the analysis that asks for has begun: what a measure under load is asked
    beside. Polled here rather than left to the session's own poller, which would notice up to
    its interval later; whichever notices first asks for the one analysis, and the other finds it
    asked or begun.

    Waited for by the clock alone once it has begun, never by anything the session holds a lock
    for, so that the measure is asked at that moment whatever the session is doing then. Asked
    only once the session has settled, so the analysis said to have begun, and then to have
    ended, is this one."""
    session.begun.clear()
    session.ended.clear()
    forward = target.stat().st_mtime + _FORWARD_SECONDS
    os.utime(target, (forward, forward))
    session.poll()
    if not session.begun.wait(_BEGUN_SECONDS):
        raise RuntimeError(f"{target} was moved forward, but no analysis began")
    time.sleep(into)


def _edit(api: Api, chosen: _Chosen, name: str) -> tuple[Measure, float]:
    """``POST /api/edit`` of the chosen change, measured as ``name`` until its reply - written,
    before its analysis has landed - and the moment it was asked at, which ``edit analysed`` is
    timed from too. The body is made before the clock starts, as the page has its own made before
    it asks. A refusal ends the run, nothing written."""
    first = chosen.first
    edited = first.site.path.resolve()
    body = _posted(
        {
            "changes": [
                {
                    "file": edited.as_posix(),
                    "fingerprint": fingerprint(edited.read_bytes()),
                    "operations": [
                        {
                            "op": "set",
                            "pointer": f"{first.site.pointer}.unit",
                            "raw": json.dumps(chosen.unit),
                        }
                    ],
                }
            ],
            "label": f"the unit of {chosen.variable}",
        }
    )
    start = time.perf_counter()
    reply = api.handle("POST", "/api/edit", {}, body)
    serialised = json.dumps(reply.body, allow_nan=False)
    answered = Measure(name, _elapsed(start), len(serialised.encode("utf-8")), posted=len(body))
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own edit was refused: {reply.body}")
    return answered, start


def _applied(
    api: Api, session: Session, plan: Mapping[str, Any], label: str, times: _Times
) -> Measure:
    """``applied rename``: the changes of ``plan``, a plan's reply, posted to ``POST /api/edit``
    as the page's Apply posts them - each file's path, fingerprint and operations, its lines
    left out - under ``label``, the undo's name for it; timed until the edit's reply, and undone
    once its own analysis has landed. The times of each file it writes, and of each directory
    they are written in, are noted in ``times`` first. A refusal ends the run, nothing written.

    Applied in process, through :meth:`Api.handle`, which no limit on a request's body reaches:
    its body's bytes are recorded beside its time, what ``POST /api/edit`` has to take for it."""
    changes = [
        {key: change[key] for key in ("file", "fingerprint", "operations")}
        for change in plan["changes"]
    ]
    written = [Path(change["file"]) for change in changes]
    times.keep(*written, *dict.fromkeys(path.parent for path in written))
    body = _posted({"changes": changes, "label": label})
    start = time.perf_counter()
    reply = api.handle("POST", "/api/edit", {}, body)
    serialised = json.dumps(reply.body, allow_nan=False)
    elapsed = _elapsed(start)
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own applied rename was refused: {reply.body}")
    try:
        session.settled(None)
    finally:
        _undo(api, session)
    session.settled(None)
    return Measure("applied rename", elapsed, len(serialised.encode("utf-8")), posted=len(body))


def _posted(body: Mapping[str, Any]) -> bytes:
    """A request's body as the page posts it: ``JSON.stringify``'s compact json, every character
    as itself, in utf-8."""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _in_the_largest_file(built: Index, units: Sequence[str]) -> tuple[Path, str, str]:
    """The component file holding the most declarations - of files holding as many, the first by
    path - the middle of the variables it declares, by name, and the unit its declaration there
    is settled on: the next of ``units`` after the one it states, wrapping round, as the edit's
    own change is chosen. Refused with a ``RuntimeError`` where that declaration states no unit
    of its own, or is no longer where the analysis found it."""
    held = Counter(site.path for sites in built.declarations.values() for site in sites)
    largest = min(held, key=lambda path: (-held[path], path.as_posix()))
    names = sorted(
        name
        for name, sites in built.declarations.items()
        if any(site.path == largest for site in sites)
    )
    name = names[len(names) // 2]
    there = next((d for d in declarations_of(built, name, {}) if d.site.path == largest), None)
    if there is None or "unit" not in there.stated:
        raise RuntimeError(
            f"{name!r}'s declaration in {largest} does not state its own unit, which the "
            "benchmark needs to choose the plan in the largest file"
        )
    current = json.loads(there.stated["unit"])
    return largest, name, units[(units.index(current) + 1) % len(units)]


def _most_stated(built: Index) -> str:
    """The unit stated in the most files, counting each file once however often it states the
    unit; of units stated in as many files, the first by spelling. :func:`measure` already
    confirmed that some unit is stated."""
    files = {
        unit: len({stated.site.path for stated in sites}) for unit, sites in built.units.items()
    }
    return min(sorted(files), key=lambda unit: -files[unit])


def _unused(built: Index, unit: str) -> str:
    """``unit`` followed by the first number from 2 that spells a unit the project neither states
    nor lists: a name it does not use, as a rename to a new spelling has. Renamed to a unit it
    lists, ``unit``'s own entries would be taken out of the vocabulary rather than renamed in it,
    a plan of another shape."""
    number = 2
    while f"{unit}{number}" in built.units or f"{unit}{number}" in built.vocabulary:
        number += 1
    return f"{unit}{number}"


def _undo(api: Api, session: Session) -> None:
    top = session.undoable
    if top is None:
        raise RuntimeError("the benchmark's own edit left nothing on the undo stack")
    reply = api.handle("POST", "/api/undo", {}, json.dumps({"at": top.at}).encode("utf-8"))
    if reply.status != 200:
        raise RuntimeError(f"putting the benchmark's own edit back was refused: {reply.body}")


def _get(
    api: Api, path: str, query: Mapping[str, Sequence[str]] | None = None
) -> tuple[float, Reply, int]:
    """One ``GET``, timed from the call to its answer serialised as the server sends it - the
    size being those bytes. Answered even where the status is not 200: a judged removal (§4) is
    as real a measure refused as it is allowed."""
    start = time.perf_counter()
    reply = api.handle("GET", path, {} if query is None else query, None)
    serialised = json.dumps(reply.body, allow_nan=False)
    elapsed = _elapsed(start)
    return elapsed, reply, len(serialised.encode("utf-8"))


def _elapsed(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bench_gui.py",
        description="Time the server half of ddd gui's benchmark on one or more projects.",
    )
    parser.add_argument(
        "projects", type=Path, nargs="+", metavar="PROJECT", help="a project.ddd.json to measure"
    )
    parser.add_argument(
        "--json", type=Path, metavar="PATH", help="also write the rows as a list of objects"
    )
    arguments = parser.parse_args(argv)
    rows: list[dict[str, Any]] = []
    print("| project | measure | ms | bytes | posted | budget |")
    print("| --- | --- | --- | --- | --- | --- |")
    for project in arguments.projects:
        label = project.resolve().parent.name
        for taken in measure(project):
            budget = BUDGETS.get(taken.name)
            if taken.refused is not None:
                print(f"| {label} | {taken.name} | {taken.refused} | | | |")
                rows.append(
                    {
                        "project": label,
                        "measure": taken.name,
                        "ms": None,
                        "bytes": None,
                        "posted": None,
                        "budget": budget,
                        "met": None,
                        "refused": taken.refused,
                    }
                )
                continue
            ms = round(taken.milliseconds)
            # "Under" its budget, as §3 words each of them: a figure as long as its budget misses.
            met = None if budget is None else taken.milliseconds < budget
            print(
                f"| {label} | {taken.name} | {ms} | {_cell(taken.size)} | {_cell(taken.posted)} "
                f"| {_verdict(budget, met)} |"
            )
            rows.append(
                {
                    "project": label,
                    "measure": taken.name,
                    "ms": ms,
                    "bytes": taken.size,
                    "posted": taken.posted,
                    "budget": budget,
                    "met": met,
                    "refused": None,
                }
            )
    if arguments.json is not None:
        arguments.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


def _cell(count: int | None) -> str:
    return "" if count is None else str(count)


def _verdict(budget: int | None, met: bool | None) -> str:
    """A budget's cell: the milliseconds a measure is held to and whether it met them, or nothing
    for a measure held to none."""
    if budget is None:
        return ""
    return f"{budget} {'met' if met else 'missed'}"


if __name__ == "__main__":
    raise SystemExit(main())
