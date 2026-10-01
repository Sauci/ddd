"""DDD's own verdict on what ``ddd tool from-elf`` built (section 5.2 of the design).

The translator states what an image states and nothing of DDD's rules; this module hands the
result to DDD's loader and analysis, under the policy ``ddd check --standalone`` applies, and
relays what they find. A variable one of their errors concerns is left out and the check runs
again, because a load error stops DDD before its analysis: the analysis's own errors only show
once the load errors are gone.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.analysis import analyze
from ddd.diagnostics import (
    STANDALONE_POLICY,
    Diagnostic,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    where,
)
from ddd.elf import Image, Variable
from ddd.loading import load_workspace
from ddd.toolbox.findings import place

POLICY: Final = (*STANDALONE_POLICY, "missing-id=ignore")
"""``ddd check --standalone``'s policy, and ``missing-id`` left out: the tool writes no ``id``
on purpose, says so once in ``elf-not-inferred``, and every producing entry would earn one."""

CHECKED_FILE: Final = "from_elf.ddd.json"
_INTERFACE: Final = re.compile(r"component\.interface\[(\d+)\]")
_TYPES: Final = re.compile(r"component\.types\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class Candidate:
    """One variable's definition, before DDD has had its say."""

    variable: Variable
    definition: dict[str, Any]
    reaches: frozenset[str]


def component_file(
    name: str, types: Sequence[dict[str, Any]], interface: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """A component description holding ``types``, when there are any, and ``interface``."""
    body: dict[str, Any] = {"name": name}
    if types:
        body["types"] = list(types)
    body["interface"] = list(interface)
    return {"component": body}


def checked(
    candidates: Sequence[Candidate],
    types: Callable[[Collection[str]], list[dict[str, Any]]],
    *,
    image: Image,
    scope: str,
    component: str,
    bag: DiagnosticBag,
) -> list[Candidate]:
    """The candidates DDD accepts, every finding it has about them relayed into ``bag``.

    The errors of every pass are relayed, and the warnings and infos of the last pass only,
    so that nothing is reported twice. A finding that concerns no variable is a fault of the
    tool: it is relayed as it is, located at the image, and the passes stop.
    """
    alive = list(candidates)
    last: list[Diagnostic] = []
    names: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / CHECKED_FILE
        while alive:
            entries = types(set().union(*(candidate.reaches for candidate in alive)))
            names = [entry["name"] for entry in entries]
            interface = [{"scope": scope, "definition": c.definition} for c in alive]
            path.write_text(json.dumps(component_file(component, entries, interface)), "utf-8")
            found = DiagnosticBag(SeverityPolicy.from_strings(POLICY, standalone=True))
            workspace = load_workspace(path, found)
            if workspace is not None and not found.has_errors:
                analyze(workspace, found)
            errors = [d for d in found.sorted if d.severity is Severity.ERROR]
            last = [d for d in found.sorted if d.severity is not Severity.ERROR]
            if not errors:
                break
            refused: set[int] = set()
            for diagnostic in errors:
                concerned = _concerned(diagnostic.location, alive, names)
                _relay(diagnostic, concerned, alive, names, image, bag)
                refused.update(concerned)
            if not refused:
                break
            alive = [candidate for index, candidate in enumerate(alive) if index not in refused]
            last = []
    for diagnostic in last:
        _relay(diagnostic, _concerned(diagnostic.location, alive, names), alive, names, image, bag)
    return alive


def _concerned(
    location: Location | None, alive: Sequence[Candidate], names: Sequence[str]
) -> list[int]:
    """The indices of the candidates a finding is about; none for a finding outside them."""
    pointer = location.pointer if location is not None else ""
    match = _INTERFACE.match(pointer)
    if match is not None:
        return [int(match.group(1))]
    match = _TYPES.match(pointer)
    if match is not None:
        name = names[int(match.group(1))]
        return [index for index, candidate in enumerate(alive) if name in candidate.reaches]
    return []


def _relay(
    diagnostic: Diagnostic,
    concerned: Sequence[int],
    alive: Sequence[Candidate],
    names: Sequence[str],
    image: Image,
    bag: DiagnosticBag,
) -> None:
    """Add one of DDD's findings to ``bag``, at the C declaration of what it concerns."""
    if concerned:
        location = place(image, alive[concerned[0]].variable.declared_at)
    else:
        location = where(image.path)
    notes: list[tuple[str, Location | None]] = []
    for text, note_location in diagnostic.notes:
        about = _concerned(note_location, alive, names)
        notes.append((text, place(image, alive[about[0]].variable.declared_at) if about else None))
    if diagnostic.severity is Severity.ERROR:
        notes.extend((f"'{alive[index].variable.name}' is left out", None) for index in concerned)
    bag.add(diagnostic.check, diagnostic.message, location, notes, severity=diagnostic.severity)
