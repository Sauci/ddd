"""The committed ELF fixtures are the ones their committed sources build, as far as a test can
tell without a compiler, and they span what they are there to span.

The images are built in Docker (``docker compose run --rm elf-fixtures``) and committed, so
the suite runs where Docker cannot. What the suite cannot do is rebuild them; what it can do is
notice that what they were built from has changed since, which is what the hashes are for.
"""

from __future__ import annotations

import json
import re

import pytest
from build_elf_fixtures import (
    COMPANION,
    COMPANION_ROW,
    EXAMPLE,
    EXAMPLE_ROW,
    NEGATIVES,
    OUTPUT,
    ROWS,
    STRIPPED_ROW,
    hashed,
)

from conftest import placement

MANIFEST = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
TRAITS = {
    "byte_order",
    "char_unsigned",
    "sizeof_long",
    "sizeof_long_double",
    "pointer_size",
    "sizeof_enum",
    "uint64_alignment",
    "alignment_attribute",
}
FACTS = {"elf_type", "machine", "dwarf_versions", "unit_types", "debug_sections", "compressed"}


def test_the_images_are_built_from_what_is_committed() -> None:
    assert MANIFEST["hashes"] == hashed(), (
        "tests/fixtures/elf/ was built from other sources than the ones committed: rebuild it "
        "with 'docker compose run --rm elf-fixtures' and commit what it writes"
    )


def test_every_row_is_built_and_described() -> None:
    assert sorted(MANIFEST["rows"]) == sorted(row.name for row in ROWS)
    for row in ROWS:
        assert (OUTPUT / f"{row.name}.elf").is_file()


@pytest.mark.parametrize("row", sorted(MANIFEST["rows"]))
def test_every_row_states_the_traits_the_tests_read(row: str) -> None:
    assert set(MANIFEST["rows"][row]["traits"]) == TRAITS


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        *(("rows", row) for row in sorted(MANIFEST["rows"])),
        *(("negatives", negative) for negative in sorted(MANIFEST["negatives"])),
    ],
)
def test_every_image_states_what_readelf_says_of_it(kind: str, name: str) -> None:
    assert set(MANIFEST[kind][name]["image"]) == FACTS


def test_the_matrix_spans_both_byte_orders_both_widths_and_both_compilers() -> None:
    rows = MANIFEST["rows"].values()
    assert {row["traits"]["byte_order"] for row in rows} == {"little", "big"}
    assert {row["traits"]["pointer_size"] for row in rows} == {4, 8}
    assert any("clang" in row["compiler"] for row in rows)
    assert any("gcc" in row["compiler"] for row in rows)


def test_the_matrix_spans_dwarf_2_to_5_compressed_sections_and_both_kinds_of_linked_image() -> None:
    images = [row["image"] for row in MANIFEST["rows"].values()]
    assert set().union(*(image["dwarf_versions"] for image in images)) == {2, 3, 4, 5}
    assert {image["compressed"] for image in images} == {True, False}
    assert {image["elf_type"] for image in images} == {"EXEC", "DYN"}


def test_the_example_image_is_the_row_it_copies() -> None:
    assert EXAMPLE.read_bytes() == (OUTPUT / f"{EXAMPLE_ROW}.elf").read_bytes()


def test_the_negative_inputs_are_there() -> None:
    assert (OUTPUT / "stripped.elf").is_file()
    assert (OUTPUT / "main.o").is_file()
    assert STRIPPED_ROW in MANIFEST["rows"]
    assert sorted(MANIFEST["negatives"]) == sorted(negative.name for negative in NEGATIVES)
    for negative in NEGATIVES:
        assert (OUTPUT / f"{negative.name}.elf").is_file()


def test_each_negative_input_carries_what_it_is_named_for() -> None:
    """Type units in a .debug_types section at DWARF 4 and as units of .debug_info at DWARF 5,
    gcc's link-time optimisation, and a variable the linker discarded: readelf's symbol table
    holds the variable it kept and not the other."""
    negatives = MANIFEST["negatives"]
    assert ".debug_types" in negatives["type-units-dwarf4"]["image"]["debug_sections"]
    assert "DW_UT_type" in negatives["type-units-dwarf5"]["image"]["unit_types"]
    assert "-flto" in negatives["gcc-lto"]["flags"]
    assert [record["name"] for record in negatives["gc-sections"]["variables"]] == ["Cal_Kept"]
    for linked in ("gold-gc-sections", "bfd-gc-sections"):
        assert "-Wl,--gc-sections" in negatives[linked]["flags"]
        assert "-fdata-sections" not in negatives[linked]["flags"]
        assert [record["name"] for record in negatives[linked]["variables"]] == [
            "Gold_Kept",
            "Gold_Static",
        ]
    assert "DW_UT_skeleton" in negatives["split-dwarf"]["image"]["unit_types"]
    assert negatives["split-dwarf-4"]["image"]["dwarf_versions"] == [4]
    assert "-gsplit-dwarf" in negatives["split-dwarf-4"]["flags"]
    assert "-g1" in negatives["debug-level-1"]["flags"]
    assert negatives["gold-gc-sections"]["linker"].startswith("GNU gold")
    assert negatives["bfd-gc-sections"]["linker"].startswith("GNU ld")


LINKERS = (
    (re.compile(r"^GNU ld .* (\d+\.\d+)$"), "GNU ld"),
    (re.compile(r"^GNU gold \(GNU Binutils for Debian (\d+\.\d+)\)"), "gold"),
    (re.compile(r"LLD (\d+)\."), "lld"),
)
"""What a linker says of itself on its first line, and how SPEC names it with its version."""


def named(said: str) -> str:
    for pattern, name in LINKERS:
        found = pattern.search(said)
        if found is not None:
            return f"{name} {found[1]}"
    raise AssertionError(said)


def test_spec_names_the_linkers_the_fixtures_are_linked_by() -> None:
    """Decision 11.5: the sentence of section 6 naming the linkers holds each one the manifest
    records, with its version, and no other."""
    linked = {
        *(row["linker"] for row in MANIFEST["rows"].values()),
        *(negative["linker"] for negative in MANIFEST["negatives"].values()),
    }
    spec = (OUTPUT.parents[2] / "SPEC.md").read_text(encoding="utf-8")
    match = re.search(r"The linkers this is tested with are (.+?),\s+the ones", spec, re.S)
    assert match is not None
    stated = re.split(r", | and ", " ".join(match[1].split()))
    assert sorted(stated) == sorted({named(said) for said in linked})


def test_spec_says_what_each_linker_leaves_of_a_discarded_unit() -> None:
    """Gold keeps the unit's debug information at offsets, and GNU ld drops it, as the two
    fixtures of the same sources show."""
    spec = " ".join((OUTPUT.parents[2] / "SPEC.md").read_text(encoding="utf-8").split())
    assert (
        "gold keeps the debug information of the unit and leaves each variable at its offset in "
        "the section it dropped; GNU ld drops it, and the reader holds no variable of that name"
    ) in spec


def test_the_debug_only_companion_is_the_row_it_was_split_from() -> None:
    assert (OUTPUT / COMPANION).is_file()
    assert COMPANION_ROW in MANIFEST["rows"]
    assert MANIFEST["companions"][COMPANION] == {
        "from": COMPANION_ROW,
        "command": "objcopy --only-keep-debug",
        "sections": {
            ".bss": "NOBITS",
            ".data": "NOBITS",
            ".rodata": "NOBITS",
            ".text": "NOBITS",
        },
    }


@pytest.mark.parametrize("row", sorted(MANIFEST["rows"]))
def test_a_const_volatile_object_lies_where_the_plain_const_one_of_its_size_does(row: str) -> None:
    """``Cal_Tunable`` is ``const volatile`` and ``Cal_Gain`` is ``const``, both small: they lie
    in the same section on every row, ``.rodata`` and not writable on every row but ``powerpc``,
    where both are in ``.sdata``, which is. The larger ``Cal_Table`` is in ``.rodata`` on all."""
    image = OUTPUT / f"{row}.elf"
    small = (".sdata", True) if row == "powerpc" else (".rodata", False)
    assert placement(image, "Cal_Tunable") == small
    assert placement(image, "Cal_Gain") == small
    assert placement(image, "Cal_Table") == (".rodata", False)
