"""The committed ELF fixtures are the ones their committed sources build, as far as a test can
tell without a compiler, and they span what they are there to span.

The images are built in Docker (``docker compose run --rm elf-fixtures``) and committed, so
the suite runs where Docker cannot. What the suite cannot do is rebuild them; what it can do is
notice that what they were built from has changed since, which is what the hashes are for.
"""

from __future__ import annotations

import json

import pytest
from build_elf_fixtures import (
    EXAMPLE,
    EXAMPLE_ROW,
    NEGATIVES,
    OUTPUT,
    ROWS,
    STRIPPED_ROW,
    hashed,
)

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
FACTS = {"elf_type", "dwarf_versions", "unit_types", "debug_sections", "compressed"}


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
