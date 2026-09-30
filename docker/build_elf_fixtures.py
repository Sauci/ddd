#!/usr/bin/env python3
"""Build the ELF fixtures of ``ddd tool from-elf``, and the manifest the tests read them with.

Usage, from the repository root: ``docker compose run --rm elf-fixtures``

Each row of :data:`ROWS` compiles ``tests/fixtures/elf/src/`` with one toolchain and links it
into ``tests/fixtures/elf/<row>.elf``, beside a stripped copy of one row, a relocatable object,
and a copy of the ``armv7m`` row at ``examples/firmware/firmware.elf`` for the documentation's
re-run transcripts. The images are committed, so that the suite needs neither Docker nor a
compiler.

The manifest records what each toolchain itself says about its target - never what ddd's
reader says, which is what the tests check against it - and a hash of everything the images
were built from, so that a test can tell when they are stale. GNU readelf is the one tool used
for every row: it reads the headers, the symbols and the DWARF of any target's ELF, where nm
and objdump are built for one.

It runs inside the image of ``docker/elf-fixtures.Dockerfile`` and needs nothing but the
standard library there. The suite imports it too, for :func:`hashed`, and must be able to
without running anything.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "elf" / "src"
OUTPUT = ROOT / "tests" / "fixtures" / "elf"
DOCKERFILE = ROOT / "docker" / "elf-fixtures.Dockerfile"
EXAMPLE = ROOT / "examples" / "firmware" / "firmware.elf"
EXAMPLE_ROW = "armv7m"
STRIPPED_ROW = "x86_64"
UNITS = ("main", "unit_a", "unit_b")
UNDEBUGGED = "nodebug"
ENTRY = "fixture_entry"
COMMON = ("-O2", "-std=gnu11", "-ffreestanding", "-fno-common")
TLS = "FIXTURE_TLS"
FOLDED = "FIXTURE_FOLDED"


@dataclass(frozen=True)
class Row:
    """One image: its compiler, the flags naming its target, its DWARF, and how it links."""

    name: str
    compiler: tuple[str, ...]
    target: tuple[str, ...]
    dwarf: tuple[str, ...]
    link: tuple[str, ...]
    cases: tuple[str, ...] = (TLS, FOLDED)
    """The optional cases of ``main.c`` this row builds. ``FOLDED`` is gcc's alone: clang may
    drop the entry of a folded static rather than give it a ``DW_AT_const_value``."""


GNU_LINK = ("-static", "-no-pie")
CORTEX_M4 = ("-mcpu=cortex-m4", "-mthumb")
ROWS = (
    Row("x86_64", ("x86_64-linux-gnu-gcc",), ("-fPIE",), ("-gdwarf-5",), ("-static-pie",)),
    Row("i686", ("i686-linux-gnu-gcc",), (), ("-gdwarf-4",), GNU_LINK),
    Row("armv7m", ("arm-none-eabi-gcc",), CORTEX_M4, ("-gdwarf-4",), ()),
    Row("armv7m-dwarf2", ("arm-none-eabi-gcc",), CORTEX_M4, ("-gdwarf-2", "-gstrict-dwarf"), ()),
    Row(
        "armeb",
        ("arm-none-eabi-gcc",),
        ("-mcpu=cortex-r5", "-marm", "-mbig-endian"),
        ("-gdwarf-4",),
        (),
    ),
    Row("aarch64", ("aarch64-linux-gnu-gcc",), (), ("-gdwarf-5",), GNU_LINK),
    Row("powerpc", ("powerpc-linux-gnu-gcc",), (), ("-gdwarf-3",), GNU_LINK),
    Row("s390x", ("s390x-linux-gnu-gcc",), (), ("-gdwarf-5", "-gz=zlib"), GNU_LINK),
    Row(
        "riscv32",
        ("clang", "--target=riscv32-unknown-elf", "-march=rv32imac", "-mabi=ilp32"),
        (),
        ("-gdwarf-5",),
        ("-fuse-ld=lld",),
        cases=(TLS,),
    ),
    Row(
        "aarch64_be",
        ("clang", "--target=aarch64_be-none-elf"),
        (),
        ("-gdwarf-4",),
        ("-fuse-ld=lld",),
        cases=(TLS,),
    ),
)

_SYMBOL = re.compile(
    r"^\s*\d+:\s+[0-9a-f]+\s+(?P<size>0x[0-9a-f]+|\d+)\s+(?P<type>\w+)\s+\w+\s+\w+\s+"
    r"(?P<index>\S+)\s+(?P<name>\S+)$"
)
_SECTION = re.compile(r"^\s*\[\s*(?P<index>\d+)\]\s+(?P<name>\S+)\s+(?P<type>\S+)\s")


def digest(path: Path) -> str:
    """The SHA-256 of a text file with its line endings normalised, so that a checkout that
    converts them - git on Windows does, by default - is not read as a change."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def hashed() -> dict[str, str]:
    """What the images are built from, by path relative to the repository, and its digest."""
    paths = [*sorted(SOURCE.iterdir()), DOCKERFILE, Path(__file__).resolve()]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def run(command: list[str], cwd: Path = SOURCE) -> str:
    """Run a command, failing loudly with its output when it fails."""
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        msg = f"{' '.join(command)} failed:\n{done.stdout}{done.stderr}"
        raise SystemExit(msg)
    return done.stdout


def build(row: Row, work: Path) -> Path:
    """Compile and link one row; the image lands in ``work``."""
    defines = [f"-D{case}" for case in row.cases]
    prefix = f"-ffile-prefix-map={SOURCE}=."
    objects: list[str] = []
    for unit in UNITS:
        target = work / f"{row.name}-{unit}.o"
        run(
            [
                *row.compiler,
                *row.target,
                *COMMON,
                *row.dwarf,
                *defines,
                prefix,
                "-c",
                f"{unit}.c",
                "-o",
                str(target),
            ]
        )
        objects.append(str(target))
    target = work / f"{row.name}-{UNDEBUGGED}.o"
    run([*row.compiler, *row.target, *COMMON, "-c", f"{UNDEBUGGED}.c", "-o", str(target)])
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
        ]
    )
    return image


def macros(row: Row) -> dict[str, str]:
    """The macros the row's compiler predefines, by name."""
    text = run([*row.compiler, *row.target, "-dM", "-E", "-x", "c", "/dev/null"])
    found: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 2 and parts[0] == "#define":
            found[parts[1]] = parts[2] if len(parts) == 3 else ""
    return found


def sections(image: Path) -> dict[str, tuple[str, str]]:
    """Every section of an image, by index: its name and its type."""
    found: dict[str, tuple[str, str]] = {}
    for line in run(["readelf", "-S", "-W", str(image)]).splitlines():
        match = _SECTION.match(line)
        if match is not None:
            found[match["index"]] = (match["name"], match["type"])
    return found


def variables(image: Path) -> list[dict[str, object]]:
    """Every object and thread-local symbol of an image: its section, whether that has
    contents, its size. A thread-local variable's symbol is of type TLS rather than OBJECT, and
    the tests read its section to hold the reader to leaving that section out."""
    table = sections(image)
    found: list[dict[str, object]] = []
    for line in run(["readelf", "-s", "-W", str(image)]).splitlines():
        match = _SYMBOL.match(line)
        if match is None or match["type"] not in ("OBJECT", "TLS") or match["index"] not in table:
            continue
        name, kind = table[match["index"]]
        found.append(
            {
                "name": match["name"],
                "section": name,
                "contents": kind != "NOBITS",
                "size": int(match["size"], 0),
            }
        )
    return sorted(found, key=lambda entry: (str(entry["name"]), str(entry["section"])))


def traits(row: Row, image: Path, found: list[dict[str, object]]) -> dict[str, object]:
    """What the row's toolchain says about its target, the answers the tests hold ddd to."""
    defined = macros(row)
    sizes = {str(entry["name"]): int(str(entry["size"])) for entry in found}
    order = defined["__BYTE_ORDER__"]
    dump = run(["readelf", "--debug-dump=info", str(image)])
    return {
        "byte_order": "big" if order == "__ORDER_BIG_ENDIAN__" else "little",
        "char_unsigned": "__CHAR_UNSIGNED__" in defined,
        "sizeof_long": int(defined["__SIZEOF_LONG__"]),
        "sizeof_long_double": int(defined["__SIZEOF_LONG_DOUBLE__"]),
        "pointer_size": int(defined["__SIZEOF_POINTER__"]),
        "sizeof_enum": sizes["Probe_Enum"],
        "uint64_alignment": sizes["Probe_Align"] - 8,
        "alignment_attribute": "DW_AT_alignment" in dump,
    }


def main() -> None:
    """Build every row, the two negative inputs and the example copy, then the manifest."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for row in ROWS:
            image = build(row, work)
            shutil.copyfile(image, OUTPUT / image.name)
            found = variables(image)
            rows[row.name] = {
                "compiler": run([row.compiler[0], "--version"]).splitlines()[0],
                "flags": [*row.compiler[1:], *row.target, *COMMON, *row.dwarf, *row.link],
                "cases": list(row.cases),
                "traits": traits(row, image, found),
                "variables": found,
            }
        run(
            [
                "x86_64-linux-gnu-strip",
                "--strip-debug",
                "-o",
                str(OUTPUT / "stripped.elf"),
                str(OUTPUT / f"{STRIPPED_ROW}.elf"),
            ]
        )
        # strip gives what it writes an executable's mode; a fixture is read, never run, and the
        # images beside it are copies without that mode.
        (OUTPUT / "stripped.elf").chmod(0o644)
        run(
            [
                "x86_64-linux-gnu-gcc",
                *COMMON,
                "-gdwarf-5",
                f"-ffile-prefix-map={SOURCE}=.",
                "-c",
                "main.c",
                "-o",
                str(OUTPUT / "main.o"),
            ]
        )
    EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUTPUT / f"{EXAMPLE_ROW}.elf", EXAMPLE)
    manifest = {"hashes": hashed(), "rows": rows}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    print(f"wrote {len(ROWS)} rows into {OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
