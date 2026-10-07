#!/usr/bin/env python3
"""Build the address fixtures of ``ddd generate a2l --image``, and the manifest that is their
oracle.

Two steps, each a mode of this script, both run from the repository root:

1. ``python docker/build_address_fixtures.py --generate``, on the host, where DDD is importable,
   writes what ``ddd generate c`` writes for the project in ``tests/fixtures/addresses/project/``
   into ``tests/fixtures/addresses/generated/``; the symbols its a2l carries an ``ECU_ADDRESS``
   for, and its bitfield members, which get none, into ``symbols.json``; and the oracle's
   source, ``oracle.c``.
2. ``docker compose run --rm address-fixtures`` compiles and links that C for five rows of the
   toolbox's matrix (``build_elf_fixtures.py``), into ``tests/fixtures/addresses/<row>.elf``,
   and writes ``manifest.json``.

The images are committed, so that the suite needs neither Docker nor a compiler; and the C they
are built from is committed beside them, so that a test can hold it to what DDD generates today.

The manifest is what each toolchain itself says, never what ddd's reader says, which is what the
tests check against it. A variable's address is what ``nm`` says. A member's offset from its
variable is the compiler's own ``offsetof``, applied to a structure wrapping the variable's type,
so that one spelling serves a structure member, an array element and both at once: ``oracle.c``
compiles one constant per symbol into a section of its own, and ``readelf`` reads them back out
of the image in the row's byte order. Constants rather than addresses stored in the image,
because a static PIE (the ``x86_64`` row) keeps an absolute address as a dynamic relocation whose
bytes in the file are zero.

The Docker mode needs nothing but the standard library and ``build_elf_fixtures.py``. The suite
imports this module too, and must be able to without running anything.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import build_elf_fixtures
from build_elf_fixtures import COMMON, DOCKERFILE, Row, digest, macros, run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "addresses"
PROJECT = OUTPUT / "project" / "project.ddd.json"
GENERATED = OUTPUT / "generated"
SYMBOLS = OUTPUT / "symbols.json"
ORACLE = OUTPUT / "oracle.c"
MANIFEST = OUTPUT / "manifest.json"
TEMPLATES = ROOT / "examples" / "templates"
TOOLBOX = Path(build_elf_fixtures.__file__).resolve()
SECTION = ".address_oracle"
ENTRY = "address_oracle_entry"
_TOOLBOX_ROWS = {row.name: row for row in build_elf_fixtures.ROWS}
ROWS = tuple(_TOOLBOX_ROWS[name] for name in ("armv7m", "powerpc", "i686", "x86_64", "aarch64_be"))
"""Little and big endian, 32 and 64 bit, gcc and clang; and ``i686``, whose ``uint64_t`` aligns to
4, the one row of the matrix that lays the project out otherwise, so that an offset predicted by
one target's rules is wrong on some row."""

_STEP = re.compile(r"[.\[]")
_DUMP = re.compile(r"^\s+0x[0-9a-f]+ (?P<bytes>[0-9a-f ]{35})")
_ORACLE_HEAD = f"""\
/* oracle.c - written by docker/build_address_fixtures.py out of symbols.json; do not edit.
 *
 * The offset of every symbol the a2l of tests/fixtures/addresses/project/ carries an
 * ECU_ADDRESS for, from the variable it belongs to, as this unit's compiler lays the variable
 * out: one constant per symbol, in the order symbols.json lists them. The build reads them back
 * out of each image and adds the variable's address, which nm gives.
 */
#include <stddef.h>
#include <stdint.h>

#include "ddd_globals.h"

__attribute__((used, section("{SECTION}"))) const uint32_t address_oracle[] = {{
"""
_ORACLE_TAIL = f"""\
}};

/* The image's entry point: the images are read, never run. */
void {ENTRY}(void) {{}}
"""


def hashed() -> dict[str, str]:
    """What the images are built from, by path relative to the repository, and its digest."""
    paths = [
        *sorted(GENERATED.iterdir()),
        ORACLE,
        SYMBOLS,
        DOCKERFILE,
        TOOLBOX,
        Path(__file__).resolve(),
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def root_of(symbol: str) -> str:
    """The variable a symbol belongs to: its access path up to the first step."""
    return _STEP.split(symbol, maxsplit=1)[0]


def oracle_source(symbols: Sequence[str]) -> str:
    """``oracle.c``: the offset of each symbol from its variable, in the order given."""
    entries = []
    for symbol in symbols:
        root = root_of(symbol)
        steps = symbol[len(root) :]
        entries.append(f"    offsetof(struct {{ __typeof__({root}) r; }}, r{steps}),\n")
    return _ORACLE_HEAD + "".join(entries) + _ORACLE_TAIL


def generate_c(directory: Path) -> None:
    """Write what ``ddd generate c`` writes for the project, with the repository's templates."""
    from ddd.cli import main

    arguments = ["generate", "c", str(PROJECT), "-o", str(directory), "-t", str(TEMPLATES)]
    if main(arguments) != 0:
        msg = f"ddd {' '.join(arguments)} failed"
        raise SystemExit(msg)


def listed() -> dict[str, Any]:
    """The symbols the project's a2l carries an ``ECU_ADDRESS`` for, its bitfield members, which
    it carries none for, and the DDD that says so."""
    from ddd import DiagnosticBag
    from ddd.analysis import analyze
    from ddd.backends.a2l.model import addressed_symbols
    from ddd.cli import GENERATOR
    from ddd.loading import load_workspace

    bag = DiagnosticBag()
    workspace = load_workspace(PROJECT, bag)
    if workspace is None or bag.has_errors:
        raise SystemExit("\n".join(finding.render() for finding in bag))
    dictionary = analyze(workspace, bag)
    return {
        "generator": GENERATOR,
        "addressed": list(addressed_symbols(dictionary)),
        "bitfields": sorted(leaf.path for leaf in dictionary.leaves if leaf.bits is not None),
    }


def generate() -> None:
    """The host's half: the C, the symbols and the oracle's source, out of the project."""
    generate_c(GENERATED)
    found = listed()
    SYMBOLS.write_text(json.dumps(found, indent=2) + "\n", "utf-8", newline="\n")
    ORACLE.write_text(oracle_source(found["addressed"]), "utf-8", newline="\n")
    print(
        f"wrote {len(found['addressed'])} symbols and {len(found['bitfields'])} bitfields into "
        f"{SYMBOLS.relative_to(ROOT).as_posix()}, and their oracle"
    )


def build(row: Row, work: Path) -> Path:
    """Compile the generated definitions and the oracle for one row and link them; the image
    lands in ``work``."""
    objects: list[str] = []
    for source in ("generated/ddd_globals.c", "oracle.c"):
        target = work / f"{row.name}-{Path(source).stem}.o"
        run(
            [
                *row.compiler,
                *row.target,
                *COMMON,
                *row.dwarf,
                f"-ffile-prefix-map={OUTPUT}=.",
                "-Igenerated",
                "-c",
                source,
                "-o",
                str(target),
            ],
            cwd=OUTPUT,
        )
        objects.append(str(target))
    image = work / f"{row.name}.elf"
    run(
        [
            *row.compiler,
            *row.target,
            *row.dwarf,
            "-nostdlib",
            f"-Wl,-e,{ENTRY}",
            *row.link,
            *objects,
            "-o",
            str(image),
        ],
        cwd=OUTPUT,
    )
    return image


def addresses_of(image: Path) -> dict[str, int]:
    """Every global symbol an image defines, and its address, as ``nm`` reads it."""
    found: dict[str, int] = {}
    for line in run(["nm", "-P", "-g", "--defined-only", str(image)], cwd=OUTPUT).splitlines():
        name, _kind, value, *_size = line.split()
        found[name] = int(value, 16)
    return found


def oracle_of(image: Path, byte_order: Literal["little", "big"]) -> list[int]:
    """The oracle's constants, as ``readelf`` dumps their section out of an image."""
    data = bytearray()
    for line in run(["readelf", "-x", SECTION, str(image)], cwd=OUTPUT).splitlines():
        match = _DUMP.match(line)
        if match is not None:
            data += bytes.fromhex(match["bytes"])
    return [int.from_bytes(data[start : start + 4], byte_order) for start in range(0, len(data), 4)]


def main() -> None:
    """Build every row, then the manifest."""
    found = json.loads(SYMBOLS.read_text(encoding="utf-8"))
    rows: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for row in ROWS:
            image = build(row, work)
            shutil.copyfile(image, OUTPUT / image.name)
            defined = macros(row)
            order: Literal["little", "big"] = (
                "big" if defined["__BYTE_ORDER__"] == "__ORDER_BIG_ENDIAN__" else "little"
            )
            offsets = dict(zip(found["addressed"], oracle_of(image, order), strict=True))
            symbols = addresses_of(image)
            rows[row.name] = {
                "compiler": run([row.compiler[0], "--version"]).splitlines()[0],
                "flags": [*row.compiler[1:], *row.target, *COMMON, *row.dwarf, *row.link],
                "byte_order": order,
                "pointer_size": int(defined["__SIZEOF_POINTER__"]),
                "offsets": offsets,
                "addresses": {
                    symbol: symbols[root_of(symbol)] + offset for symbol, offset in offsets.items()
                },
                "bitfields": found["bitfields"],
            }
    manifest = {"hashes": hashed(), "rows": rows}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    print(f"wrote {len(ROWS)} rows into {OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the address fixtures.")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="write the C, the symbols and the oracle's source, on the host, with DDD",
    )
    if parser.parse_args().generate:
        # This checkout's DDD, as the suite's own pythonpath has it, rather than whichever one
        # the interpreter happens to have installed.
        sys.path.insert(0, str(ROOT / "src"))
        generate()
    else:
        main()
