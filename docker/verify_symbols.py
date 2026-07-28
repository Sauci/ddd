#!/usr/bin/env python3
"""Compare what DDD promised with what really ended up in the object file.

Usage: verify_symbols.py variables.json symbols.txt

``variables.json`` is the output of ``ddd list --format json``, ``symbols.txt`` the
externally visible symbols defined by the generated definition file.  Variables with
a preprocessor condition may legitimately be absent, everything else must be there
exactly once, and nothing else may be defined.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    variables = json.loads(Path(argv[1]).read_text(encoding="utf-8"))["variables"]
    symbols = Path(argv[2]).read_text(encoding="utf-8").splitlines()
    defined = {line.strip() for line in symbols if line.strip()}

    declared = {variable["name"] for variable in variables}
    conditional = {variable["name"] for variable in variables if variable["condition"]}
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
