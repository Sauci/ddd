"""The server half of the benchmark of ``ddd gui`` on a large project.

Times, in order, opening a project, each of ``GET /api/state``, ``/graph``, ``/units``,
``/types``, ``/shared`` and ``/files``, the Findings tab's first page of findings and every
finding of one component's file, a variable's panel, a unit's panel, judging a removal on the
Files tab, one analysis, an edit's round trip, and planning the rename of the unit stated in the
most files - the server driven in process, over one :class:`~ddd.gui.session.Session` and one
:class:`~ddd.gui.api.Api` (``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md``
§4). Then, over a second session polling at ``ddd gui``'s own interval, three requests each asked
halfway through an analysis, to be answered while it runs: ``GET /api/state``, the plan of the
edit's own change - ``GET /api/settle``, what a variable's panel asks while a reader picks a
unit - and the edit itself. One answered once its analysis had ended is no such figure, and is
written refused, a sentence in its figure's place. Everything a measure needs to choose - the
file, the variable, the unit, the entry to remove, the unit to rename - is read off the project's
own analysed revision, sorted, so the same project measures the same things on every run;
nothing here imports the generator.

Every measure but ``open``, ``analysis`` and ``edit analysed`` answers a reply whose body is
timed serialised exactly as the server would send it, ``json.dumps(reply.body, allow_nan=False)``
inside the timed span, the size being those bytes. The session analyses on a thread of its own,
as ``ddd gui``'s does: ``open`` and ``analysis`` are each timed until the analysis they ask for
has landed, ``edit answered`` until the edit's reply - written, before its analysis has
landed - and ``edit analysed`` from the same moment until that analysis has landed. ``rename
plan`` is asked once that analysis has landed, and only plans: it writes nothing.

``measure`` undoes each edit it made and stops each analyser it started before it returns, so a
second run measures the same bytes. Not part of the ``ddd`` package, like
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from ddd.editing import fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Revision, Session
from ddd.lsp.navigation import Index
from ddd.variables import Declared, declarations_of

NAMES: Final[tuple[str, ...]] = (
    "open",
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
    "remove judged",
    "analysis",
    "edit answered",
    "edit analysed",
    "rename plan",
    "state while analysing",
    "plan while analysing",
    "edit while analysing",
)
"""Every measure :func:`measure` takes, in the order it takes them."""

_ENDPOINTS: Final[tuple[str, ...]] = ("state", "graph", "units", "types", "shared", "files")
"""The plain ``GET /api/<name>`` measures, asked for with no query."""

_PAGE: Final = {"offset": ["0"], "limit": ["100"]}
"""What ``findings page`` asks of ``GET /api/findings``: the Findings tab's first page, as the
page asks it (``PAGE_SIZE`` in ``gui/src/lib/findingsWindow.ts``)."""

_FORWARD_SECONDS: Final = 3_600
"""How far :func:`_analysis` moves a component file's modification time forward: past a
filesystem's mtime resolution, so the next poll never misses it."""

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
    reply of its own (``open``, ``analysis``, ``edit analysed``)."""
    refused: str | None = None
    """Why the measure is no figure of what its name says, written in the figure's place
    (:func:`main`): a measure under load answered once its analysis had ended. ``None`` for every
    figure; its time and size are then what :func:`main` writes, and are never written
    otherwise."""


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


def measure(project: Path) -> list[Measure]:
    """Every measure of §4's server half, each taken once - over a fresh session opened on
    ``project``, then the measures under load over another - left as it was found: each edit this
    makes is undone before this returns, so a second run measures the same project.

    Refused with a ``RuntimeError`` naming the precondition, before any measure but ``open`` is
    taken: ``project`` needs at least one component file (:func:`_analysis` has one to touch), at
    least two distinct units stated somewhere in it (the edit has another to move to), and its
    middle variable's first declaration must state its own unit rather than leave it to be filled
    some other way (there is otherwise nothing for the edit to read as "current"). Every project
    ``tools/generate_project.py`` makes satisfies all three. A plan or an edit the server refuses
    ends the run with a ``RuntimeError`` as well, once any edit made has been undone: a refusal is
    no plan, nor an edit, and its time would read as one.
    """
    session = Session(project.parent, poll_interval=_POLL_SECONDS)
    session.start()
    try:
        taken, chosen = _measured(session, project)
    finally:
        session.stop()
    loaded = _Watched(project.parent)
    loaded.start()
    try:
        # Halfway through an analysis by this run's own measure of one: at 100,000 declarations,
        # past reading the files and into analysing them.
        halfway = next(each for each in taken if each.name == "analysis").milliseconds / 2_000
        taken.extend(_under_load(loaded, project, chosen, halfway))
    finally:
        loaded.stop()
    return taken


def _measured(session: Session, project: Path) -> tuple[list[Measure], _Chosen]:
    """:func:`measure`'s first session's, over ``session``, whose analyser runs; and what the
    measures change, for the second's."""
    api = Api(session, project, wait_seconds=0.0)
    taken = [_opening(session, project)]

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
        asked = {"action": ["rename"], "unit": [renamed], "to": [_unused(built, renamed)]}
        elapsed, reply, size = _get(api, "/api/unit-plan", asked)
    finally:
        _undo(api, session)
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own rename plan was refused: {reply.body}")
    taken.append(Measure("rename plan", elapsed, size))
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


def _opening(session: Session, project: Path) -> Measure:
    """Opening ``project``, until its first analysis has landed."""
    start = time.perf_counter()
    session.open(project)
    session.settled(None)
    return Measure("open", _elapsed(start), None)


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
    body = json.dumps(
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
    ).encode("utf-8")
    start = time.perf_counter()
    reply = api.handle("POST", "/api/edit", {}, body)
    serialised = json.dumps(reply.body, allow_nan=False)
    answered = Measure(name, _elapsed(start), len(serialised.encode("utf-8")))
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own edit was refused: {reply.body}")
    return answered, start


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
    print("| project | measure | ms | bytes |")
    print("| --- | --- | --- | --- |")
    for project in arguments.projects:
        label = project.resolve().parent.name
        for taken in measure(project):
            if taken.refused is not None:
                print(f"| {label} | {taken.name} | {taken.refused} | |")
                rows.append(
                    {
                        "project": label,
                        "measure": taken.name,
                        "ms": None,
                        "bytes": None,
                        "refused": taken.refused,
                    }
                )
                continue
            ms = round(taken.milliseconds)
            print(f"| {label} | {taken.name} | {ms} | {'' if taken.size is None else taken.size} |")
            rows.append(
                {
                    "project": label,
                    "measure": taken.name,
                    "ms": ms,
                    "bytes": taken.size,
                    "refused": None,
                }
            )
    if arguments.json is not None:
        arguments.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
