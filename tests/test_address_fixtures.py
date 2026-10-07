"""The committed address fixtures are built from what DDD generates today, as far as a test can
tell without a compiler, and they span what they are there to span.

The images are built in Docker (``docker compose run --rm address-fixtures``) out of C that DDD
generated on the host (``python docker/build_address_fixtures.py --generate``), and all of it is
committed, so the suite runs where Docker cannot. Two things can leave the images stale, and each
has its tests: DDD can come to generate other C, or to carry other symbols, for the project, which
a fresh generation here notices; and what the images were built from can change after they were,
which the hashes notice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from build_address_fixtures import (
    GENERATED,
    MANIFEST,
    ORACLE,
    OUTPUT,
    ROWS,
    SYMBOLS,
    generate_c,
    hashed,
    listed,
    oracle_source,
)

from ddd.cli import GENERATOR

FIXTURES = json.loads(MANIFEST.read_text(encoding="utf-8"))
LISTED = json.loads(SYMBOLS.read_text(encoding="utf-8"))
ROW_NAMES = [row.name for row in ROWS]


def test_the_images_are_built_from_what_is_committed() -> None:
    assert FIXTURES["hashes"] == hashed(), (
        "tests/fixtures/addresses/ was built from other sources than the ones committed: rebuild "
        "it with 'docker compose run --rm address-fixtures' and commit what it writes"
    )


def test_the_committed_c_is_what_ddd_generates_for_the_project(tmp_path: Path) -> None:
    """Every file, the output directory's manifest included. The banner names the DDD that wrote
    the file, and is read as naming the one ``symbols.json`` records: a release changes that line
    in every file, and nothing a compiler reads."""
    generate_c(tmp_path)
    fresh = {
        path.name: path.read_text(encoding="utf-8").replace(GENERATOR, LISTED["generator"])
        for path in tmp_path.iterdir()
    }
    committed = {path.name: path.read_text(encoding="utf-8") for path in GENERATED.iterdir()}
    assert fresh == committed, (
        "DDD no longer generates what tests/fixtures/addresses/generated/ holds: rewrite it with "
        "'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_the_symbols_are_the_ones_the_a2l_carries_and_the_bitfields_it_leaves_out() -> None:
    fresh = listed()
    assert (fresh["addressed"], fresh["bitfields"]) == (LISTED["addressed"], LISTED["bitfields"]), (
        "DDD no longer carries the symbols tests/fixtures/addresses/symbols.json lists: rewrite it "
        "with 'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_the_oracle_is_written_from_the_symbols() -> None:
    assert ORACLE.read_text(encoding="utf-8") == oracle_source(LISTED["addressed"]), (
        "tests/fixtures/addresses/oracle.c is not the oracle of symbols.json: rewrite it with "
        "'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_every_row_is_built_and_described() -> None:
    assert list(FIXTURES["rows"]) == ROW_NAMES
    for row in ROW_NAMES:
        assert (OUTPUT / f"{row}.elf").is_file()


def test_the_rows_span_both_byte_orders_both_widths_and_both_compilers() -> None:
    rows = FIXTURES["rows"].values()
    assert {row["byte_order"] for row in rows} == {"little", "big"}
    assert {row["pointer_size"] for row in rows} == {4, 8}
    assert any("clang" in row["compiler"] for row in rows)
    assert any("gcc" in row["compiler"] for row in rows)


def test_the_rows_lay_the_project_out_in_more_than_one_way() -> None:
    """``i686`` aligns a ``uint64_t`` to 4 where the other rows align it to 8, so ``Mixed.last``
    is at 12 there and at 16 elsewhere. Rows that all agreed could not tell an offset read out of
    the image from one predicted by a single target's rules."""
    layouts = {tuple(sorted(row["offsets"].items())) for row in FIXTURES["rows"].values()}
    assert len(layouts) > 1


@pytest.mark.parametrize("row", ROW_NAMES)
def test_every_carried_symbol_has_an_address_on_every_row(row: str) -> None:
    assert sorted(FIXTURES["rows"][row]["offsets"]) == LISTED["addressed"]
    assert sorted(FIXTURES["rows"][row]["addresses"]) == LISTED["addressed"]


@pytest.mark.parametrize("row", ROW_NAMES)
def test_no_bitfield_member_has_an_address(row: str) -> None:
    bitfields = FIXTURES["rows"][row]["bitfields"]
    assert bitfields == LISTED["bitfields"]
    assert not set(bitfields) & set(FIXTURES["rows"][row]["addresses"])


@pytest.mark.parametrize("row", ROW_NAMES)
def test_the_two_dimensional_array_of_structures_is_laid_out_row_major(row: str) -> None:
    """``Grid[i][j]`` is element ``i * 3 + j`` of the six: ``Grid[1][0]`` is three elements on
    from ``Grid[0][0]``, where a column-major layout would put it one on."""
    offsets = FIXTURES["rows"][row]["offsets"]
    size = offsets["Grid[0][1].raw"] - offsets["Grid[0][0].raw"]
    for i in range(2):
        for j in range(3):
            for member in ("raw", "v"):
                start = offsets[f"Grid[0][0].{member}"]
                assert offsets[f"Grid[{i}][{j}].{member}"] == start + (i * 3 + j) * size
