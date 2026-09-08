#!/usr/bin/env python3
"""Compare what DDD promised with what really ended up in the object file.

Usage: verify_symbols.py dictionary.json symbols.txt

``dictionary.json`` is the output of ``ddd dump --format json``, ``symbols.txt`` the
externally visible symbols defined by the generated definition file.  Variables with
a preprocessor condition may legitimately be absent, everything else must be there
exactly once, and nothing else may be defined.

The dictionary is read rather than ``ddd list``, because the two answer different
questions.  ``ddd list`` reports what can be *described* - the leaves of a structured
variable, and none at all for a member DDD only carries - while the definition file
defines one symbol per plain object and one per structured instance, whether or not
anything inside it can be described.  A structure whose members are all external types
is exactly that case: real storage, no leaf, and a symbol the linker sees.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def defines(dictionary: dict) -> list[dict]:
    """Every declaration the definition file turns into one symbol.

    A plain object is defined under its own name and a structured one under the name of its
    instance; both carry ``name`` and ``condition``, so nothing here has to tell them apart.
    """
    return [*dictionary["objects"], *dictionary["instances"]]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    declarations = defines(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    symbols = Path(argv[2]).read_text(encoding="utf-8").splitlines()
    defined = {line.strip() for line in symbols if line.strip()}

    declared = {entry["name"] for entry in declarations}
    conditional = {entry["name"] for entry in declarations if entry["condition"]}
    unconditional = declared - conditional

    missing = sorted(unconditional - defined)
    stray = sorted(defined - declared)
    present_conditional = sorted(defined & conditional)
    absent_conditional = sorted(conditional - defined)

    print(f"{len(defined)} of {len(declared)} declared variables are defined")
    for name in present_conditional:
        print(f"  conditional, present: {name}")
    for name in absent_conditional:
        print(f"  conditional, absent : {name}")

    for name in missing:
        print(f"error: '{name}' is declared by DDD but not defined in the object file")
    for name in stray:
        print(f"error: '{name}' is defined but was never declared by DDD")

    return 1 if missing or stray else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
