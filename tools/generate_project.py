"""Generate a project of a chosen size and shape, to measure ``ddd gui`` on.

The benchmark of the browser interface (``tools/bench_gui.py``, ``gui/bench/``) runs on projects of
10,000, 35,000 and 100,000 declarations, and real projects mix many small components with a few
large ones (``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md`` §4). Nothing in
``examples/`` comes near those sizes, so this writes them - the same bytes for the same arguments,
on every machine.

Every declaration is written as a finished project writes one: an id on every output, a unit its
vocabulary lists, a reader for every output, each reader stating what its producer states. A
project generated with the defaults therefore has no finding at all, as a real one can;
``--missing-ids`` and ``--unread`` give it the findings of a project half-way through a migration,
at the density asked for.

Not part of the ``ddd`` package: a tool of the repository's own, as ``dev_version.py`` is, run by
hand, by the benchmark and by the journeys, and checked by ``tests/test_generate_project.py``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH

SHAPES: Final = ("many", "large", "mixed")
"""Many small components; a few large ones sharing every declaration; or half of each."""

SMALL: Final = 30
"""The declarations of a component of the "many" shape - the size the spec's §2 measured."""

LARGE: Final = 30
"""How many components the "large" shape shares its declarations between; the "mixed" shape has
half as many large ones, beside its small ones."""

LAYER: Final = 30
"""How many components on a reader's output sits, in the "many" shape: the canvas then lays the
project out in layers about this many components across, rather than as one chain as deep as the
project is long, which ``@dagrejs/dagre`` 3.1.1 runs out of stack on past about 1,500
components."""

FEWEST: Final = 120
"""The smallest project generated: fewer declarations leave the "many" shape a component or two,
between which no reader can sit ``LAYER`` components away."""

UNITS: Final = ("rpm", "Nm", "kPa", "degC", "V", "A", "ms", "Hz")
"""The vocabulary every generated project lists, and the units its outputs state in turn."""

MULTIPLIER: Final = 2_654_435_761
"""Scatters the ids: odd, so multiplying by it is a bijection on the 2**60 ids of
``OBJECT_ID_LENGTH`` characters of the 32-letter ``OBJECT_ID_ALPHABET``, and neighbouring
declarations do not read alike."""


@dataclass(frozen=True, slots=True)
class Generated:
    """What :func:`generate` wrote."""

    project: Path
    components: int
    declarations: int
    unnamed: int
    """Outputs written without an id: a ``missing-id`` each."""

    unread: int
    """Outputs nobody reads: an ``unused-output`` each."""


def generate(
    directory: Path,
    declarations: int,
    shape: str,
    *,
    missing_ids: float = 0.0,
    unread: float = 0.0,
) -> Generated:
    """Write a project of ``declarations`` declarations, rounded down to even components, into
    ``directory``, which must not exist yet."""
    if shape not in SHAPES:
        raise ValueError(f"a shape is one of many, large or mixed, not {shape!r}")
    if declarations < FEWEST:
        raise ValueError(
            f"a generated project has at least {FEWEST} declarations, not {declarations}"
        )
    if directory.exists():
        raise FileExistsError(f"{directory} exists already; generate into a new directory")
    halves = [size // 2 for size in _sizes(declarations, shape)]
    owners = [component for component, half in enumerate(halves) for _ in range(half)]
    starts = [sum(halves[:component]) for component in range(len(halves))]
    total = len(owners)
    widest = max(halves)
    shift = min(max(widest, LAYER * (SMALL // 2)), total - widest)
    interfaces: list[list[dict[str, Any]]] = [[] for _ in halves]
    names: list[str] = []
    unnamed = 0
    for number, owner in enumerate(owners):
        name = f"C{owner:05d}_O{number - starts[owner]:04d}"
        names.append(name)
        entry = _output(name, number, named=not _chosen(number, missing_ids))
        if "id" not in entry["definition"]:
            unnamed += 1
        interfaces[owner].append(entry)
    read = [False] * total
    converted = 0
    for slot, owner in enumerate(owners):
        if _chosen(slot, unread):
            number = total + slot
            name = f"C{owner:05d}_X{slot - starts[owner]:04d}"
            entry = _output(name, number, named=not _chosen(number, missing_ids))
            if "id" not in entry["definition"]:
                unnamed += 1
            interfaces[owner].append(entry)
            converted += 1
            continue
        source = (slot + shift) % total
        read[source] = True
        interfaces[owner].append(
            {"scope": "input", "definition": _definition(names[source], source)}
        )
    _write(directory, interfaces)
    return Generated(
        project=directory / "project.ddd.json",
        components=len(halves),
        declarations=2 * total,
        unnamed=unnamed,
        unread=read.count(False) + converted,
    )


def _sizes(declarations: int, shape: str) -> list[int]:
    """Each component's declarations, in component order."""
    if shape == "many":
        return _even(declarations, declarations // SMALL)
    if shape == "large":
        return _even(declarations, LARGE)
    half = declarations // 2
    return _even(half, LARGE // 2) + _even(declarations - half, (declarations - half) // SMALL)


def _even(total: int, parts: int) -> list[int]:
    """``total`` over ``parts`` components as evenly as even sizes allow - an even size being as
    many outputs as inputs - the first components taking two more where some are left over."""
    base = total // parts // 2 * 2
    sizes = [base] * parts
    for index in range((total - base * parts) // 2):
        sizes[index] += 2
    return sizes


def _chosen(number: int, density: float) -> bool:
    """Whether the ``number``-th item is among a ``density`` of them, spread evenly: of ``count``
    items, exactly ``floor(count * density)`` are chosen, never bunched at the start."""
    return math.floor((number + 1) * density) > math.floor(number * density)


def _definition(name: str, number: int) -> dict[str, Any]:
    """What a producer states of its output, and what its reader states back."""
    return {
        "name": name,
        "kind": "measurement",
        "description": f"generated measurement {number}",
        "datatype": "uint16",
        "unit": UNITS[number % len(UNITS)],
        "conversion": {"kind": "identity"},
        "volatile": False,
    }


def _output(name: str, number: int, *, named: bool) -> dict[str, Any]:
    definition = _definition(name, number)
    if named:
        definition = {"name": name, "id": _id(number), **definition}
    return {"scope": "output", "definition": definition}


def _id(number: int) -> str:
    """The ``number``-th id: distinct for distinct numbers, spelled in ``OBJECT_ID_ALPHABET``."""
    size = len(OBJECT_ID_ALPHABET)
    value = (number * MULTIPLIER) % size**OBJECT_ID_LENGTH
    digits = []
    for _ in range(OBJECT_ID_LENGTH):
        value, digit = divmod(value, size)
        digits.append(OBJECT_ID_ALPHABET[digit])
    return "".join(digits)


def _write(directory: Path, interfaces: Sequence[Sequence[dict[str, Any]]]) -> None:
    components = directory / "components"
    components.mkdir(parents=True)
    _dump(
        directory / "project.ddd.json",
        {"project": {"name": "Generated", "includes": ["units.ddd.json", "components/*.ddd.json"]}},
    )
    _dump(
        directory / "units.ddd.json",
        {"units": [{"unit": unit, "description": f"generated unit {unit}"} for unit in UNITS]},
    )
    for index, interface in enumerate(interfaces):
        _dump(
            components / f"c{index:05d}.ddd.json",
            {"component": {"name": f"C{index:05d}", "interface": list(interface)}},
        )


def _dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _density(text: str) -> float:
    value = float(text)
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"a density is a fraction from 0 to 1, not {text}")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_project.py",
        description="Write a project of N declarations to measure ddd gui on.",
    )
    parser.add_argument("directory", type=Path, help="where to write it; must not exist yet")
    parser.add_argument("--declarations", type=int, required=True, metavar="N")
    parser.add_argument("--shape", choices=SHAPES, default="many")
    parser.add_argument("--missing-ids", type=_density, default=0.0, metavar="FRACTION")
    parser.add_argument("--unread", type=_density, default=0.0, metavar="FRACTION")
    arguments = parser.parse_args(argv)
    try:
        made = generate(
            arguments.directory,
            arguments.declarations,
            arguments.shape,
            missing_ids=arguments.missing_ids,
            unread=arguments.unread,
        )
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(
        f"{made.project}: {made.components} components, {made.declarations} declarations, "
        f"{made.unnamed} outputs without an id, {made.unread} outputs nobody reads"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
