"""A build's addresses: the map a build writes after the link, the range the a2l holds the
addresses it states to, and the symbols an image places, over images built by hand."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

import ddd.addresses
from ddd.addresses import Placed, addresses_from_image, load_address_map
from ddd.backends.a2l.options import weigh_addresses
from ddd.elf import (
    DECLARED_ONLY,
    DISCARDED,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    FOLDED,
    NOT_AN_ADDRESS,
    REMOVED,
    THREAD_LOCAL,
    Array,
    Base,
    CType,
    Image,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
)


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


U8 = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
S8 = Base("signed char", DW_ATE_SIGNED_CHAR, 1)
U16 = Base("short unsigned int", DW_ATE_UNSIGNED, 2)
S16 = Base("short int", DW_ATE_SIGNED, 2)
U32 = Base("unsigned int", DW_ATE_UNSIGNED, 4)
PAIR = Struct("Pair_s", 2, (Member("lo", U8, 0), Member("hi", U8, 8)))
INLET = Struct(
    "Inlet_s",
    16,
    (Member("raw", Array(U16, (4,)), 0), Member("pair", PAIR, 64), Member("Level_2", U32, 96)),
)
CELL = Struct("Cell_s", 4, (Member("raw", U16, 0), Member("v", U16, 16)))
MIXED = Struct(
    "Mixed_s",
    16,
    (
        Member("a", U8, 0, 3),
        Member("b", S8, 3, 4),
        Member("c", U8, 8, 2),
        Member("value", U16, 16),
        Member("d", U32, 32, 20),
        Member("e", S16, 52, 7),
        Member("level", U8, 64),
        Member("count", U32, 96),
    ),
)
"""``uint8_t a:3; int8_t b:4; uint8_t c:2; uint16_t value; uint32_t d:20; int16_t e:7;
uint8_t level; uint32_t count;`` as gcc 15.2 lays it out for x86_64 (measured with its own
``offsetof`` and DWARF): ``c`` would cross a byte and starts the next one, ``e`` shares the
storage unit ``d`` started, and the value members land at bytes 2, 8 and 12."""


def image(*variables: Variable, symbols: frozenset[str] = frozenset()) -> Image:
    return Image(Path("hand.elf"), "little", variables, (), symbols, b"")


def stored(
    name: str,
    ctype: CType = U8,
    *,
    unit: str = "unit.c",
    address: int | None = 0x100,
    missing: str = "",
    external: bool = True,
) -> Variable:
    return Variable(name, unit, ctype, None, address, missing, external)


def placed(img: Image, *symbols: str) -> Placed:
    return addresses_from_image(img, symbols)


def reason(img: Image, symbol: str) -> str:
    """Why ``img`` places ``symbol`` nowhere: the one reason, the symbol placed nowhere."""
    found = addresses_from_image(img, [symbol])
    assert found.addresses == {}
    (said,) = found.reasons.values()
    return said


class TestTheVariable:
    """Which variable of the image a symbol names: the global of that name."""

    def test_an_object_is_placed_at_its_variable_s_address(self) -> None:
        img = image(stored("_Cal_Gain_2", U16, address=0x2000_0100))
        assert placed(img, "_Cal_Gain_2") == Placed({"_Cal_Gain_2": 0x2000_0100}, {})

    def test_a_static_of_a_global_s_name_never_stands_for_it(self) -> None:
        """Review Focus 2: the static comes first, in a unit of its own, and the global is the
        one placed."""
        img = image(
            stored("Gain", unit="a.c", address=0x200, external=False),
            stored("Gain", unit="b.c", address=0x100),
        )
        assert placed(img, "Gain") == Placed({"Gain": 0x100}, {})

    def test_a_global_only_a_static_of_its_name_outlives_is_not_placed(self) -> None:
        """Review Focus 2: a global renamed while a static of its old name lives on is
        reported missing rather than given the static's address."""
        img = image(stored("Gain", unit="a.c", address=0x200, external=False))
        assert reason(img, "Gain") == (
            "the image holds 'Gain' only as a static, and every object a dictionary describes "
            "is a global"
        )

    def test_a_common_pair_is_one_variable(self) -> None:
        """Two units describe one tentative definition at one address, as -fcommon or the
        common attribute make them."""
        img = image(
            stored("Counter", U32, unit="unit_a.c", address=0x300),
            stored("Counter", U32, unit="unit_b.c", address=0x300),
        )
        assert placed(img, "Counter") == Placed({"Counter": 0x300}, {})

    def test_globals_of_one_name_at_two_addresses_are_not_placed(self) -> None:
        """No linker makes them, since one global name is one symbol; a model that holds them
        is not guessed at."""
        img = image(
            stored("Twice", unit="a.c", address=0x2000),
            stored("Twice", unit="b.c", address=0x1000),
        )
        assert reason(img, "Twice") == (
            "'Twice' names globals at 2 addresses of the image, 0x1000, 0x2000"
        )

    def test_a_name_the_image_does_not_describe_is_not_placed(self) -> None:
        assert reason(image(stored("Gain")), "Gian") == (
            "the image's debug information holds no variable named 'Gian'"
        )

    def test_a_name_only_the_symbol_table_holds_is_not_placed_naming_g(self) -> None:
        img = image(symbols=frozenset({"Nodebug_Counter"}))
        assert reason(img, "Nodebug_Counter") == (
            "the image's debug information holds no variable named 'Nodebug_Counter'; the "
            "symbol table holds it, so the unit defining it was built without debug "
            "information (-g)"
        )

    @pytest.mark.parametrize(
        "missing", [DECLARED_ONLY, FOLDED, REMOVED, DISCARDED, THREAD_LOCAL, NOT_AN_ADDRESS]
    )
    def test_a_global_without_storage_is_not_placed_with_the_reader_s_reason(
        self, missing: str
    ) -> None:
        img = image(stored("Gain", address=None, missing=missing))
        assert reason(img, "Gain") == f"'Gain' has no address in the image: {missing}"


class TestThePath:
    """A member by its access path: the variable's address and the offsets its type gives."""

    def test_a_member_is_placed_at_its_offset_through_nested_structures(self) -> None:
        img = image(stored("Inlet", INLET, address=0x400))
        assert placed(img, "Inlet.raw", "Inlet.pair.hi", "Inlet.Level_2") == Placed(
            {"Inlet.raw": 0x400, "Inlet.pair.hi": 0x409, "Inlet.Level_2": 0x40C}, {}
        )

    def test_bitfields_before_value_members_leave_each_value_member_at_its_own_offset(
        self,
    ) -> None:
        """Review Focus 1: each value member is where its own offset says, never where the
        sizes before it add up to, and a path naming a bitfield is refused."""
        img = image(stored("Mixed", MIXED, address=0x500))
        symbols = ("Mixed.value", "Mixed.level", "Mixed.count", "Mixed.b", "Mixed.e")
        assert placed(img, *symbols) == Placed(
            {"Mixed.value": 0x502, "Mixed.level": 0x508, "Mixed.count": 0x50C},
            {
                "Mixed.b": "'Mixed.b' is a bitfield, which an address cannot describe",
                "Mixed.e": "'Mixed.e' is a bitfield, which an address cannot describe",
            },
        )

    def test_an_array_of_structures_is_indexed_by_the_size_of_its_element(self) -> None:
        """An index of two digits, as an array of more than ten structures has."""
        img = image(stored("Cells", Array(CELL, (12,)), address=0x700))
        assert placed(img, "Cells[0].raw", "Cells[10].v") == Placed(
            {"Cells[0].raw": 0x700, "Cells[10].v": 0x72A}, {}
        )

    def test_an_array_of_structures_in_two_dimensions_is_indexed_row_major(self) -> None:
        """Review Focus 3: ``Grid[1][2].v`` is ``(1 * 3 + 2) * sizeof(Cell_s) + offsetof(Cell_s,
        v)``. The column-major sum would put ``Grid[0][1]`` and ``Grid[1][0]`` elsewhere."""
        img = image(stored("Grid", Array(CELL, (2, 3)), address=0x600))
        assert placed(img, "Grid[0][1].v", "Grid[1][0].v", "Grid[1][2].v") == Placed(
            {"Grid[0][1].v": 0x606, "Grid[1][0].v": 0x60E, "Grid[1][2].v": 0x616}, {}
        )

    def test_typedefs_and_qualifiers_are_seen_through_before_each_step(self) -> None:
        cell = Typedef("Cell_t", Qualified(CELL, volatile=True))
        rows = Typedef("Row_t", Qualified(Array(cell, (3,)), const=True))
        outer = Struct("Outer_s", 16, (Member("head", U32, 0), Member("rows", rows, 32)))
        img = image(
            stored("Outer", Qualified(Typedef("Outer_t", outer), const=True), address=0x800)
        )
        assert placed(img, "Outer.rows[2].v") == Placed({"Outer.rows[2].v": 0x80E}, {})

    def test_a_member_the_structure_does_not_have_is_not_placed(self) -> None:
        """The C code and the declaration disagree: a member renamed on one side only."""
        assert reason(image(stored("Inlet", INLET)), "Inlet.pair.mid") == (
            "'Inlet.pair' has no member named 'mid' in the image"
        )

    def test_a_member_of_what_is_no_structure_is_not_placed(self) -> None:
        assert reason(image(stored("Inlet", INLET)), "Inlet.Level_2.bits") == (
            "'Inlet.Level_2' is not a structure, so it has no member named 'bits'"
        )

    def test_an_index_into_what_is_no_array_is_not_placed(self) -> None:
        assert reason(image(stored("Inlet", INLET)), "Inlet[2].raw") == (
            "'Inlet' is not an array, so it has no element [2]"
        )

    @pytest.mark.parametrize(
        ("symbol", "said"),
        [
            ("Grid[2][0].v", "'Grid' has an extent of 2, so it has no element [2]"),
            ("Grid[1][3].v", "'Grid[1]' has an extent of 3, so it has no element [3]"),
        ],
    )
    def test_an_index_out_of_range_is_not_placed(self, symbol: str, said: str) -> None:
        """At the extent itself, the first index past the end, in either dimension."""
        assert reason(image(stored("Grid", Array(CELL, (2, 3)))), symbol) == said

    def test_a_member_whose_offset_the_reader_could_not_read_is_not_placed(self) -> None:
        """DWARF may state a member's offset as an expression the reader does not evaluate,
        which it reads as no bit offset at all."""
        holder = Struct("Holder_s", 4, (Member("odd", U32, None),))
        assert reason(image(stored("Holder", holder)), "Holder.odd") == (
            "where 'Holder.odd' lies cannot be worked out from the image's debug information"
        )

    def test_an_element_of_a_type_the_reader_does_not_size_is_not_placed(self) -> None:
        """An array of what the reader does not describe - unions here - has no element size."""
        unions = Array(Unsupported("a union"), (4,))
        assert reason(image(stored("Unions", unions)), "Unions[1].x") == (
            "where 'Unions[1]' lies cannot be worked out from the image's debug information"
        )


class TestWithoutPyelftools:
    def test_reading_a_map_needs_no_pyelftools(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``generate`` imports this module on every run and only an image needs pyelftools,
        so a broken installation that lacks it still reads a map. Every elftools module an
        earlier test loaded is taken out first, as ``tests/test_cli.py``'s test of a missing
        pyelftools explains, and the package keeps the module it had."""
        for name in [name for name in sys.modules if name.partition(".")[0] == "elftools"]:
            monkeypatch.delitem(sys.modules, name)
        monkeypatch.setitem(sys.modules, "elftools", None)
        monkeypatch.delitem(sys.modules, "ddd.elf")
        monkeypatch.delitem(sys.modules, "ddd.addresses")
        monkeypatch.setattr(ddd, "addresses", ddd.addresses)
        fresh = importlib.import_module("ddd.addresses")
        path = tree / "addresses.json"
        path.write_text('{"A": "0x10"}', encoding="utf-8")
        assert fresh.load_address_map(path) == {"A": 0x10}
