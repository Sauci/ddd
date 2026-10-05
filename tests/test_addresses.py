"""A build's addresses: the map a build writes after the link, and the range the a2l holds the
addresses it states to."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddd.addresses import load_address_map
from ddd.backends.a2l.options import weigh_addresses


def refusal(path: Path) -> str:
    with pytest.raises(ValueError) as refused:
        load_address_map(path)
    return str(refused.value)


class TestTheMap:
    """The reader of the map, moved here from the a2l backend's tests. Each refusal is the
    sentence the reader printed before the move, read off it then and asserted whole."""

    def test_address_map_accepts_hex_and_decimal(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text('{"A": "0x1000", "B": 32, "C": "40"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x1000, "B": 32, "C": 40}

    @pytest.mark.parametrize(
        ("value", "said"),
        [
            ('"ff"', "is not an integer written in decimal or with a '0x' prefix: 'ff'"),
            ("true", "is not an integer: True"),
            ("null", "is not an integer: None"),
            ("[1]", "is not an integer: [1]"),
        ],
    )
    def test_address_map_rejects_anything_else(self, tree: Path, value: str, said: str) -> None:
        path = tree / "addresses.json"
        path.write_text(f'{{"A": {value}}}', encoding="utf-8")
        assert refusal(path) == f"{path.as_posix()}: address of 'A' {said}"

    def test_address_map_still_ignores_the_space_around_a_value(self, tree: Path) -> None:
        """The grammar holds the stripped text: a map is machine written, and a stray space
        around a number it got right is not what the strictness is for."""
        path = tree / "addresses.json"
        path.write_text('{"A": " 0x10 ", "B": "\\t32"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x10, "B": 32}

    @pytest.mark.parametrize("value", ["0x1_0000", "+5", "١٢", "-5", "-0x10", "0b11", "0x"])
    def test_address_map_holds_a_spelled_address_to_the_two_documented_forms(
        self, tree: Path, value: str
    ) -> None:
        """``int()`` took every spelling python accepts, none of which section 6 offers.

        ``0x1_0000`` reached the a2l as ``0x00010000``, ``+5`` as ``0x00000005`` and the
        Arabic-Indic ``١٢`` as ``0x0000000C`` - from a file a linker script or a patch tool
        wrote, which is the argument for a strict grammar rather than a lenient one.
        """
        path = tree / "addresses.json"
        path.write_text(json.dumps({"A": value}), encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: address of 'A' is not an integer written in decimal or with a "
            f"'0x' prefix: {value!r}"
        )

    def test_address_map_refuses_a_symbol_stated_twice(self, tree: Path) -> None:
        """Python's json reader keeps the last of two equal keys, so the first address was
        dropped in silence - the loader refuses a repeated key for the same reason."""
        path = tree / "addresses.json"
        path.write_text('{"A": "0x10", "B": "0x20", "A": "0x30"}', encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: the address map names 'A' twice, with two addresses"
        )

    def test_address_map_reads_a_byte_order_mark(self, tree: Path) -> None:
        """Every other file the tool reads is read ``utf-8-sig``; a map written by a Windows
        tool or by Notepad was a json syntax error with python's advice to a programmer."""
        path = tree / "addresses.json"
        path.write_text('﻿{"A": "0x10"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x10}

    def test_address_map_must_be_an_object(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text("[1, 2]", encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: expected a json object mapping symbol names to addresses"
        )

    def test_an_address_map_that_is_not_json_names_the_file(self, tree: Path) -> None:
        """The words after the colon are json's own, read off it here rather than out of this
        test, as they may change between pythons."""
        path = tree / "addresses.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError) as decoded:
            json.loads("{ not json")
        assert refusal(path) == (
            f"the address map '{path.as_posix()}' is not valid json: {decoded.value}"
        )

    def test_an_address_map_that_cannot_be_read_names_it(self, tree: Path) -> None:
        path = tree / "nosuch.json"
        with pytest.raises(OSError) as refused:
            load_address_map(path)
        assert str(refused.value) == (
            f"cannot read the address map '{path.as_posix()}': No such file or directory"
        )

    @pytest.mark.parametrize("content", ["[1, 2]", '{"A": "nowhere"}', '{"A": 1, "A": 2}'])
    def test_every_complaint_about_a_map_spells_the_path_forward_slashed(
        self, tree: Path, content: str
    ) -> None:
        """As every other path this tool prints is spelled, and as the same messages about a
        description file already are; on Windows these carried backslashes. The fourth
        complaint, an address no ``ECU_ADDRESS`` holds, is the a2l backend's since the move,
        and ``tests/test_cli.py`` holds its path to the same spelling."""
        path = tree / "sub" / "addresses.json"
        path.parent.mkdir()
        path.write_text(content, encoding="utf-8")
        said = refusal(path)
        assert path.as_posix() in said
        assert "\\" not in said

    def test_every_entry_is_kept_whatever_its_value(self, tree: Path) -> None:
        """Ruling 1: the reader checks how an address is written, never what it is; which
        addresses the a2l can state is ``weigh_addresses``' question, for the symbols it
        carries."""
        path = tree / "addresses.json"
        path.write_text('{"X": -16, "Y": "0x1FFFFFFFF"}', encoding="utf-8")
        assert load_address_map(path) == {"X": -16, "Y": 0x1_FFFF_FFFF}


class TestTheRange:
    """What an ``ECU_ADDRESS`` holds, weighed for the symbols the a2l carries alone."""

    @pytest.mark.parametrize("address", [-16, 0x1_FFFF_FFFF])
    def test_an_address_the_field_cannot_hold_is_refused_naming_the_symbol_and_where(
        self, address: int
    ) -> None:
        """A negative value renders as ``0x-0000010`` and a wider one as a 33 bit literal,
        either of which makes the whole a2l unreadable."""
        with pytest.raises(ValueError) as refused:
            weigh_addresses({"X": address}, ("X",), "build/addresses.json")
        assert str(refused.value) == (
            f"build/addresses.json: address of 'X' is {address}, outside the range "
            f"0 .. 0xFFFFFFFF that an a2l address can hold"
        )

    def test_both_ends_of_the_field_are_addresses(self) -> None:
        weigh_addresses({"Low": 0, "High": 0xFFFF_FFFF}, ("Low", "High"), "addresses.json")

    def test_an_address_the_a2l_never_states_is_not_weighed(self) -> None:
        """The documented recipe extracts every defined symbol of the image, which on a 64 bit
        host puts a hundred entries of the c runtime above 4 GB."""
        weigh_addresses({"X": 0x1000, "___crt_xc_end__": 0x1_4000_9018}, ("X",), "map.json")

    def test_the_first_address_out_of_range_is_named_in_the_order_of_the_map(self) -> None:
        with pytest.raises(ValueError) as refused:
            weigh_addresses({"Z": -1, "A": 0x1_0000_0000}, ("A", "Z"), "map.json")
        assert str(refused.value) == (
            "map.json: address of 'Z' is -1, outside the range 0 .. 0xFFFFFFFF that an a2l "
            "address can hold"
        )
