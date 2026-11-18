"""``SYMBOL_LINK``: the linker symbol a record names, and the offset of the record from it.

Finding 1:I9. ASAP2 1.6.1 (3.5.123) defines the first parameter as the name of the symbol in the
linker map and the second as the offset from that symbol's address, so a member is the variable's
name and the member's offset, and not the access path, which no map holds. Only the linked image
states an offset: a map gives a symbol's address and nothing of its members', and a build with no
address source knows no layout, so there a member keeps the path it was always written with.

The offsets of the address fixtures are the compiler's own (``offsetof``, in the manifest), so no
test here works one out.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import component, declare, project, run_analysis
from ddd.addresses import addresses_from_image
from ddd.backends import A2lBackend, A2lOptions, render
from ddd.cli import EXIT_OK, main
from ddd.elf import Array, Member, Struct, Typedef, Variable
from test_addresses import U16, image, stored
from test_cli import ADDRESS_FIXTURES, ADDRESS_PROJECT, ADDRESS_ROWS

RECORD = re.compile(r"/begin (?:MEASUREMENT|CHARACTERISTIC|AXIS_PTS) (\S+) ")
LINK = re.compile(r'SYMBOL_LINK "([^"]+)" (\d+)')


def links(text: str) -> dict[str, tuple[str, int]]:
    """Every record of an a2l and the ``SYMBOL_LINK`` it states."""
    found: dict[str, tuple[str, int]] = {}
    record: str | None = None
    for line in text.splitlines():
        opened = RECORD.search(line)
        if opened:
            record = opened.group(1)
        stated = LINK.search(line)
        if stated and record is not None:
            found[record] = (stated.group(1), int(stated.group(2)))
            record = None
    return found


def generate(
    tmp_path: Path, *extra: str, source: Path = ADDRESS_PROJECT
) -> dict[str, tuple[str, int]]:
    output = tmp_path / "gen"
    assert main(["generate", "a2l", str(source), "-o", str(output), *extra]) == EXIT_OK
    return links((output / "AddressFixture.a2l").read_text(encoding="utf-8"))


def root_of(symbol: str) -> str:
    return re.match(r"\w+", symbol).group()  # type: ignore[union-attr]


class TestAnImageNamesTheLinkerSymbolAndTheOffset:
    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_every_member_names_its_variable_at_the_compilers_offset(
        self, tmp_path: Path, row: str
    ) -> None:
        stated = generate(tmp_path, "--image", str(ADDRESS_FIXTURES / f"{row}.elf"))
        offsets = ADDRESS_ROWS[row]["offsets"]
        symbols = json.loads((ADDRESS_FIXTURES / "symbols.json").read_text(encoding="utf-8"))
        assert symbols["addressed"], "the fixture lists what the a2l addresses"
        for symbol in symbols["addressed"]:
            assert stated[symbol] == (root_of(symbol), offsets[symbol]), symbol

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_measurement_member_in_an_element_of_an_array_of_structures(
        self, tmp_path: Path, row: str
    ) -> None:
        stated = generate(tmp_path, "--image", str(ADDRESS_FIXTURES / f"{row}.elf"))
        assert stated["Inlet.cells[1].v"] == ("Inlet", 26)
        assert stated["Inlet.latest.value"] == ("Inlet", 0)
        assert stated["Inlet.history"] == ("Inlet", 8)

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_calibratable_member_names_its_variable_too(self, tmp_path: Path, row: str) -> None:
        stated = generate(tmp_path, "--image", str(ADDRESS_FIXTURES / f"{row}.elf"))
        assert stated["Tuning.shift"] == ("Tuning", 4)
        assert stated["Tuning.timeout"] == ("Tuning", 8)

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_variable_that_is_no_member_keeps_its_name_at_zero(
        self, tmp_path: Path, row: str
    ) -> None:
        stated = generate(tmp_path, "--image", str(ADDRESS_FIXTURES / f"{row}.elf"))
        assert stated["Speed"] == ("Speed", 0)
        assert stated["Table"] == ("Table", 0)

    def test_the_demo_s_diagnosis_faults_follows_the_vendor_s_own_type(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``Diagnosis.faults`` lies after ``driver``, a type DDD does not describe, so only the
        image knows where: here a vendor structure of 12 bytes, which puts it at 12."""
        from conftest import DEMO

        driver = Struct("DriverState_s", 12, (Member("raw", Array(U16, (6,)), 0),))
        diagnosis = Struct(
            "SensorDiagnosis_s",
            16,
            (Member("driver", Typedef("DriverState_t", driver), 0), Member("faults", U16, 96)),
        )
        hand = image(stored("Diagnosis", Typedef("SensorDiagnosis_t", diagnosis), address=0x2000))
        monkeypatch.setattr("ddd.cli._image_reader", lambda: lambda _path: hand)
        output = tmp_path / "gen"
        main(["generate", "a2l", str(DEMO), "-o", str(output), "--image", "hand.elf"])
        stated = links((output / "DemoDevice.a2l").read_text(encoding="utf-8"))
        assert stated["Diagnosis.faults"] == ("Diagnosis", 12)


class TestWhatPlacementFound:
    def test_the_offset_is_the_one_the_walk_added(self) -> None:
        cell = Struct("Cell_s", 8, (Member("raw", U16, 0), Member("v", U16, 32)))
        hand = image(stored("Cells", Array(cell, (3,)), address=0x700))
        placed = addresses_from_image(hand, ["Cells[2].v", "Cells"])
        assert placed.links == {"Cells[2].v": ("Cells", 20), "Cells": ("Cells", 0)}

    def test_a_symbol_the_image_does_not_place_has_no_link(self) -> None:
        hand = image(Variable("Gone", "u.c", U16, None, None, "removed", True))
        assert addresses_from_image(hand, ["Gone.x"]).links == {}


class TestWithNoImageTheMemberKeepsItsPath:
    def test_with_an_address_map(self, tmp_path: Path) -> None:
        addresses = tmp_path / "map.json"
        addresses.write_text(json.dumps({"Inlet": "0x20000000"}), encoding="utf-8")
        stated = generate(tmp_path, "--address-map", str(addresses))
        assert stated["Inlet.latest.value"] == ("Inlet.latest.value", 0)
        assert stated["Inlet.cells[1].v"] == ("Inlet.cells[1].v", 0)
        assert stated["Speed"] == ("Speed", 0)

    def test_before_the_link(self, tmp_path: Path) -> None:
        stated = generate(tmp_path)
        assert stated["Inlet.latest.value"] == ("Inlet.latest.value", 0)
        assert stated["Tuning.shift"] == ("Tuning.shift", 0)


class TestEveryRecordKindReadsItsLink:
    """An axis cannot be a member, so no image gives it an offset today, and a characteristic object
    is the variable itself; each record still writes what the options hold for it."""

    def test_an_axis_and_a_characteristic_name_what_the_options_hold(self, tmp_path: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component(
                "A",
                declare("local", "Speed", "uint16"),
                declare("local", "Ax", "uint16", kind="axis", size=2, input="Speed"),
                declare("local", "Cal", "uint16", kind="parameter"),
            ),
        }
        dictionary, bag = run_analysis(tmp_path, files)
        assert dictionary is not None, [d.render() for d in bag]
        options = A2lOptions(
            links={"Ax": ("Holder", 12), "Speed": ("Holder", 4), "Cal": ("Holder", 20)}
        )
        rendered = render(dictionary, [A2lBackend(options)], tmp_path / "gen")
        stated = links(next(f.content for f in rendered if f.path.name == "Device.a2l"))
        assert stated["Ax"] == ("Holder", 12)
        assert stated["Speed"] == ("Holder", 4)
        assert stated["Cal"] == ("Holder", 20)
