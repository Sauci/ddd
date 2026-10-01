"""The server half of the benchmark of ``ddd gui`` on a large project.

Times, in order, opening a project, one analysis, each of ``GET /api/state``, ``/graph``,
``/units``, ``/types``, ``/shared`` and ``/files``, the Findings tab's first page of findings and
every finding of one component's file, a variable's panel, a unit's panel, judging a removal on
the Files tab, and an edit's round trip - the server driven in process, over one
:class:`~ddd.gui.session.Session` and one :class:`~ddd.gui.api.Api`
(``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md`` §4). Everything a measure
needs to choose - the file, the variable, the unit, the entry to remove - is read off the
project's own analysed revision, sorted, so the same project measures the same things on every
run; nothing here imports the generator.

Every measure but ``open``, ``analysis`` and ``edit analysed`` answers a reply whose body is
timed serialised exactly as the server would send it, ``json.dumps(reply.body, allow_nan=False)``
inside the timed span, the size being those bytes. The session analyses on a thread of its own,
as ``ddd gui``'s does: ``open`` and ``analysis`` are each timed until the analysis they ask for
has landed, ``edit answered`` until the edit's reply - written, before its analysis has
landed - and ``edit analysed`` from the same moment until that analysis has landed.

``measure`` undoes the one edit it made and stops the analyser it started before it returns, so a
second run measures the same bytes. Not part of the ``ddd`` package, like
``generate_project.py`` beside it: a tool of the repository's own, run by hand - it is slow on a
large project, and the machine's own (*Global Constraints*) - never in CI, and checked only by
``tests/test_bench_gui.py``'s smoke test on a small generated project.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.editing import fingerprint
from ddd.gui.api import Api, Reply
from ddd.gui.session import Session
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
"""How often the session's own poller looks at the disk: never while a run lasts. ``analysis``
polls for itself, and a poller noticing the moved file first would leave that poll nothing to
notice."""


@dataclass(frozen=True, slots=True)
class Measure:
    """One measure taken: how long it ran, and the bytes of its answer where it has one."""

    name: str
    milliseconds: float
    size: int | None
    """Bytes of ``reply.body`` serialised as the server sends it; ``None`` for a measure with no
    reply of its own (``open``, ``analysis``, ``edit analysed``)."""


def measure(project: Path) -> list[Measure]:
    """Every measure of §4's server half, taken once over a fresh session opened on ``project``,
    left as it was found: the one edit this makes is undone before this returns, so a second run
    measures the same project.

    Refused with a ``RuntimeError`` naming the precondition, before any measure but ``open`` is
    taken: ``project`` needs at least one component file (:func:`_analysis` has one to touch), at
    least two distinct units stated somewhere in it (the edit has another to move to), and its
    middle variable's first declaration must state its own unit rather than leave it to be filled
    some other way (there is otherwise nothing for the edit to read as "current"). Every project
    ``tools/generate_project.py`` makes satisfies all three.
    """
    session = Session(project.parent, poll_interval=_POLL_SECONDS)
    session.start()
    try:
        return _measured(session, project)
    finally:
        session.stop()


def _measured(session: Session, project: Path) -> list[Measure]:
    """:func:`measure`'s, over ``session``, whose analyser runs."""
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

    taken.append(_analysis(session, components[0]))

    answered, analysed = _edit(api, session, declared[0], units, variable)
    taken.append(answered)
    taken.append(analysed)

    _undo(api, session)
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


def _edit(
    api: Api, session: Session, first: Declared, units: Sequence[str], variable: str
) -> tuple[Measure, Measure]:
    """``POST /api/edit`` of the unit of ``first``, the middle variable's first declaration, to
    the next unit of the project's own vocabulary after its current one, wrapping round - not
    the generator's own units, so this reads any project without importing it. Answered once
    written; analysed once ``session`` has settled."""
    current = json.loads(first.stated["unit"])
    new_unit = units[(units.index(current) + 1) % len(units)]
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
                            "raw": json.dumps(new_unit),
                        }
                    ],
                }
            ],
            "label": f"the unit of {variable}",
        }
    ).encode("utf-8")
    start = time.perf_counter()
    reply = api.handle("POST", "/api/edit", {}, body)
    serialised = json.dumps(reply.body, allow_nan=False)
    answered = Measure("edit answered", _elapsed(start), len(serialised.encode("utf-8")))
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own edit was refused: {reply.body}")
    session.settled(None)
    return answered, Measure("edit analysed", _elapsed(start), None)


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
            ms = round(taken.milliseconds)
            print(f"| {label} | {taken.name} | {ms} | {'' if taken.size is None else taken.size} |")
            rows.append({"project": label, "measure": taken.name, "ms": ms, "bytes": taken.size})
    if arguments.json is not None:
        arguments.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
