"""The server half of the benchmark of ``ddd gui`` on a large project.

Times, in order, opening a project, one analysis, each of ``GET /api/state``, ``/graph``,
``/units``, ``/types``, ``/shared`` and ``/files``, a variable's panel, a unit's panel, judging a
removal on the Files tab, and an edit's round trip - the server driven in process, over one
:class:`~ddd.gui.session.Session` and one :class:`~ddd.gui.api.Api`
(``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md`` §4). Everything a measure
needs to choose - the variable, the unit, the entry to remove - is read off the project's own
analysed revision, sorted, so the same project measures the same things on every run; nothing
here imports the generator.

Every measure but ``open``, ``analysis`` and ``edit analysed`` answers a reply whose body is
timed serialised exactly as the server would send it, ``json.dumps(reply.body, allow_nan=False)``
inside the timed span, the size being those bytes. Before Task 5 of this part, ``Session.edit``
still analyses inside the call it writes in, so ``edit answered`` and ``edit analysed`` time and
measure the same span; later tasks give the second its own wait and update this module in the
same commit, keeping every measure's name and meaning.

Left running on the project it opened: ``measure`` undoes the one edit it made before it returns,
so a second run measures the same bytes. Not part of the ``ddd`` package, like
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
from ddd.gui.session import Revision, Session
from ddd.variables import Declared, declarations_of

NAMES: Final[tuple[str, ...]] = (
    "open",
    "state",
    "graph",
    "units",
    "types",
    "shared",
    "files",
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

_FORWARD_SECONDS: Final = 3_600
"""How far :func:`_analysis` moves a component file's modification time forward: past a
filesystem's mtime resolution, so the next poll never misses it."""


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
    measures the same project."""
    session = Session(project.parent)
    api = Api(session, project, wait_seconds=0.0)
    taken = [_opening(session, project)]

    entries: list[dict[str, Any]] = []
    for name in _ENDPOINTS:
        elapsed, reply, size = _get(api, f"/api/{name}")
        taken.append(Measure(name, elapsed, size))
        if name == "files":
            entries = reply.body["entries"]

    revision = session.revision
    if revision is None:
        raise RuntimeError(f"{project} did not open")
    built = revision.index
    if built is None:
        raise RuntimeError(f"{project} did not analyse enough to be measured")

    variables = sorted(built.declarations)
    variable = variables[len(variables) // 2]
    elapsed, _, size = _get(api, "/api/variable", {"name": [variable]})
    taken.append(Measure("variable", elapsed, size))

    units = sorted(built.units)
    elapsed, _, size = _get(api, "/api/unit", {"name": [units[0]]})
    taken.append(Measure("unit", elapsed, size))

    # The root's first entry, never its last: in a generated project the last is the pattern
    # ``components/*.ddd.json``, whose removal judges a project of one file. The first,
    # ``units.ddd.json``, is judged by analysing the whole project without it - one full
    # analysis with the includes changed, the cost this measure is for.
    removed = str(entries[0]["key"])
    elapsed, _, size = _get(api, "/api/files-plan", {"action": ["remove"], "path": [removed]})
    taken.append(Measure("remove judged", elapsed, size))

    taken.append(_analysis(session, revision))

    declared = declarations_of(built, variable, {})
    if not declared:
        raise RuntimeError(f"{variable!r} has no declaration left of {project} to edit")
    answered, analysed = _edit(api, declared[0], units, variable)
    taken.append(answered)
    taken.append(analysed)

    _undo(api, session)
    return taken


def _opening(session: Session, project: Path) -> Measure:
    start = time.perf_counter()
    session.open(project)
    return Measure("open", _elapsed(start), None)


def _analysis(session: Session, revision: Revision) -> Measure:
    """One component file's modification time moved forward, then :meth:`Session.poll` until it
    has analysed."""
    components = sorted(file.path for file in revision.files if file.kind == "component")
    target = components[0]
    forward = target.stat().st_mtime + _FORWARD_SECONDS
    os.utime(target, (forward, forward))
    start = time.perf_counter()
    changed = session.poll()
    elapsed = _elapsed(start)
    if not changed:
        raise RuntimeError(f"{target} was moved forward, but the poll after it saw no change")
    return Measure("analysis", elapsed, None)


def _edit(
    api: Api, first: Declared, units: Sequence[str], variable: str
) -> tuple[Measure, Measure]:
    """``POST /api/edit`` of the unit of ``first``, the middle variable's first declaration, to
    the next unit of the project's own vocabulary after its current one, wrapping round - not
    the generator's own units, so this reads any project without importing it."""
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
    elapsed = _elapsed(start)
    if reply.status != 200:
        raise RuntimeError(f"the benchmark's own edit was refused: {reply.body}")
    answered = Measure("edit answered", elapsed, len(serialised.encode("utf-8")))
    # Before Task 5, `Session.edit` analyses inside the call it writes in, so the revision it
    # answers with already includes it: the same span is both figures, as the plan says.
    analysed = Measure("edit analysed", elapsed, None)
    return answered, analysed


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
