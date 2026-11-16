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
    OTHER_SCOPE,
    REMOVED,
    THREAD_LOCAL,
    Array,
    Base,
    CType,
    Image,
    Member,
    Qualified,
    Section,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    open_image,
)

FIXTURES = Path(__file__).parent / "fixtures" / "elf"


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

    def test_a_map_that_is_not_utf_8_names_the_file_and_what_wrote_it(self, tree: Path) -> None:
        """What Windows PowerShell's ``>`` writes: UTF-16 with its byte order mark. Python's
        own words about a byte at a position name no file and no remedy."""
        path = tree / "addresses.json"
        path.write_bytes(b"\xff\xfe" + '{"A": "0x10"}'.encode("utf-16-le"))
        assert refusal(path) == (
            f"the address map '{path.as_posix()}' is not valid json: it is not UTF-8 text, and "
            f"Windows PowerShell's > writes UTF-16; write the map as UTF-8"
        )

    def test_a_map_nested_deeper_than_the_reader_takes_is_refused_naming_the_file(
        self, tree: Path
    ) -> None:
        # The limit is the interpreter's, and a different one on each python: 200,000 is past
        # all of them, and a document that deep is 400 KB.
        depth = 200_000
        path = tree / "addresses.json"
        path.write_text("[" * depth + "]" * depth, encoding="utf-8")
        assert refusal(path) == (
            f"the address map '{path.as_posix()}' is not valid json: it is nested more "
            f"deeply than this tool reads"
        )

    def test_a_number_of_more_digits_than_the_reader_takes_is_refused_naming_the_file(
        self, tree: Path
    ) -> None:
        limit = sys.get_int_max_str_digits()
        assert limit > 0
        path = tree / "addresses.json"
        path.write_text('{"A": ' + "9" * (limit + 1) + "}", encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: the address map holds a number of more than {limit} digits, "
            f"which this tool does not read"
        )

    def test_an_address_written_in_more_digits_than_the_reader_takes_names_its_symbol(
        self, tree: Path
    ) -> None:
        limit = sys.get_int_max_str_digits()
        path = tree / "addresses.json"
        path.write_text('{"A": "' + "9" * (limit + 1) + '"}', encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: address of 'A' has more than {limit} digits, which this "
            f"tool does not read"
        )

    def test_a_number_of_as_many_digits_as_the_reader_takes_is_read(self, tree: Path) -> None:
        limit = sys.get_int_max_str_digits()
        path = tree / "addresses.json"
        path.write_text('{"A": ' + "9" * limit + "}", encoding="utf-8")
        assert load_address_map(path) == {"A": int("9" * limit)}

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


EVERYWHERE = Section(".data", 0, 1 << 64, 0)
"""A section holding every address a test names, so that the tests of a path or a name leave
where an address lies to the ones that ask."""


def image(
    *variables: Variable,
    symbols: frozenset[str] = frozenset(),
    objects: frozenset[tuple[str, int]] | None = None,
    sections: tuple[Section, ...] = (EVERYWHERE,),
    split_dwarf: bool = False,
) -> Image:
    """An image holding ``variables``. Unless ``objects`` says otherwise its symbol table holds
    each global at its address, as a linker that kept the variable leaves it."""
    if objects is None:
        objects = frozenset(
            (variable.name, variable.address)
            for variable in variables
            if variable.external and variable.address is not None
        )
    return Image(
        Path("hand.elf"),
        "little",
        variables,
        sections,
        symbols,
        b"",
        objects,
        split_dwarf=split_dwarf,
    )


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


class TestACplusplusScope:
    """A variable of a namespace is no candidate by its short name, so a DDD object of that name
    is not placed at it (finding 11:M8)."""

    def test_a_variable_of_another_scope_places_nothing_and_says_why(self) -> None:
        img = image(stored("OnlyInNs", address=None, missing=OTHER_SCOPE))
        assert reason(img, "OnlyInNs") == f"'OnlyInNs' is {OTHER_SCOPE}"

    def test_a_c_variable_of_the_same_short_name_is_the_one_placed(self) -> None:
        img = image(stored("Shared", address=0x120))
        assert placed(img, "Shared").addresses == {"Shared": 0x120}

    def test_the_image_of_cplusplus_places_its_c_variable_and_not_the_namespace_s(self) -> None:
        found = placed(open_image(FIXTURES / "cplusplus.elf"), "Cpp_Plain", "OnlyInNs")
        assert sorted(found.addresses) == ["Cpp_Plain"]
        assert found.reasons == {"OnlyInNs": f"'OnlyInNs' is {OTHER_SCOPE}"}


class TestWhatTheImageDoesNotDefine:
    """``Placed.absent`` marks the symbols whose variable the image does not define at all, and
    no other reason: the ones a build without a feature leaves behind."""

    def absent(self, img: Image, *symbols: str) -> frozenset[str]:
        found = placed(img, *symbols)
        assert set(symbols) - set(found.addresses) == set(found.reasons)
        return found.absent

    def test_a_name_the_image_knows_nowhere_is_absent(self) -> None:
        assert self.absent(image(stored("Gain")), "Gian") == {"Gian"}

    def test_a_member_of_a_variable_it_does_not_define_is_absent_too(self) -> None:
        assert self.absent(image(), "Cells[0].raw") == {"Cells[0].raw"}

    def test_a_declaration_alone_with_no_symbol_is_absent(self) -> None:
        """A header's ``extern`` stays where the unit that defined the variable was left out."""
        img = image(stored("Gain", address=None, missing=DECLARED_ONLY))
        assert self.absent(img, "Gain") == {"Gain"}

    def test_a_declaration_alone_beside_a_symbol_of_its_name_is_not(self) -> None:
        img = image(
            stored("Gain", address=None, missing=DECLARED_ONLY), symbols=frozenset({"Gain"})
        )
        assert self.absent(img, "Gain") == frozenset()

    def test_a_name_only_the_symbol_table_holds_is_not(self) -> None:
        assert self.absent(image(symbols=frozenset({"Nodebug"})), "Nodebug") == frozenset()

    def test_a_static_is_not(self) -> None:
        img = image(stored("Gain", address=0x200, external=False))
        assert self.absent(img, "Gain") == frozenset()

    def test_globals_at_two_addresses_are_not(self) -> None:
        img = image(stored("Twice", unit="a.c", address=0x2000), stored("Twice", address=0x1000))
        assert self.absent(img, "Twice") == frozenset()

    def test_a_variable_with_no_storage_is_not(self) -> None:
        for missing in (FOLDED, REMOVED, DISCARDED, THREAD_LOCAL, NOT_AN_ADDRESS):
            img = image(stored("Gain", address=None, missing=missing))
            assert self.absent(img, "Gain") == frozenset(), missing

    def test_a_variable_the_linker_left_with_no_symbol_is_not(self) -> None:
        img = image(stored("Gain", address=0x100), objects=frozenset())
        assert self.absent(img, "Gain") == frozenset()

    def test_a_member_the_c_lacks_is_not(self) -> None:
        img = image(stored("P", PAIR, address=0x100))
        assert self.absent(img, "P.mid") == frozenset()


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

    def test_a_name_only_declared_where_the_symbol_table_holds_it_is_not_placed_naming_g(
        self,
    ) -> None:
        """The definition file built without -g and a unit reading the global built with it:
        gcc writes that unit's ``extern`` declaration into its debug information, and the
        symbol table still holds the global."""
        img = image(
            stored("Gain", address=None, missing=DECLARED_ONLY), symbols=frozenset({"Gain"})
        )
        assert reason(img, "Gain") == (
            "the image's debug information only declares 'Gain'; the symbol table holds it, so "
            "the unit defining it was built without debug information (-g)"
        )

    def test_any_other_reason_of_a_name_the_symbol_table_holds_is_the_reader_s(self) -> None:
        """Only a declaration says that no unit with debug information defines the global."""
        img = image(stored("Gain", address=None, missing=FOLDED), symbols=frozenset({"Gain"}))
        assert reason(img, "Gain") == f"'Gain' has no address in the image: {FOLDED}"

    def test_a_name_only_the_symbol_table_holds_in_a_split_image_is_not_placed_naming_the_dwo(
        self,
    ) -> None:
        """``-gsplit-dwarf`` leaves a skeleton in the image and the debug information in ``.dwo``
        files beside it: the unit was built with ``-g``, and saying it was not sends the reader
        to what the build already did."""
        img = image(symbols=frozenset({"Cal_Gain"}), split_dwarf=True)
        assert reason(img, "Cal_Gain") == (
            "the image's debug information holds no variable named 'Cal_Gain'; the symbol "
            "table holds it, and the debug information of this image is in separate .dwo files "
            "(-gsplit-dwarf), which this tool does not read"
        )

    def test_a_name_only_declared_in_a_split_image_is_not_placed_naming_the_dwo(self) -> None:
        img = image(
            stored("Gain", address=None, missing=DECLARED_ONLY),
            symbols=frozenset({"Gain"}),
            split_dwarf=True,
        )
        assert reason(img, "Gain") == (
            "the image's debug information only declares 'Gain'; the symbol table holds it, and "
            "the debug information of this image is in separate .dwo files (-gsplit-dwarf), "
            "which this tool does not read"
        )

    def test_a_name_the_split_image_does_not_hold_at_all_is_still_absent(self) -> None:
        found = addresses_from_image(image(split_dwarf=True), ["Gone"])
        assert found.absent == frozenset({"Gone"})

    @pytest.mark.parametrize("symbol", ["Notyped.raw[0]", "Notyped[0]"])
    def test_a_path_into_a_variable_the_debug_level_gave_no_type_says_so(self, symbol: str) -> None:
        """``-g1`` keeps the variable and its address and no type: it is not an array or a
        structure that the path was wrong about."""
        img = image(stored("Notyped", Unsupported("void")))
        assert reason(img, symbol) == (
            "the image's debug information gives 'Notyped' no type, as -g1 leaves it, so no "
            "path into it can be followed"
        )

    def test_the_variable_itself_is_placed_where_the_debug_level_gave_it_no_type(self) -> None:
        img = image(stored("Notyped", Unsupported("void"), address=0x40))
        assert placed(img, "Notyped") == Placed({"Notyped": 0x40}, {})

    def test_a_name_that_is_no_array_is_still_said_so_beside_the_untyped_one(self) -> None:
        assert reason(image(stored("Inlet", Unsupported("a pointer"))), "Inlet[2]") == (
            "'Inlet' is not an array, so it has no element [2]"
        )

    @pytest.mark.parametrize(
        "missing", [DECLARED_ONLY, FOLDED, REMOVED, DISCARDED, THREAD_LOCAL, NOT_AN_ADDRESS]
    )
    def test_a_global_without_storage_is_not_placed_with_the_reader_s_reason(
        self, missing: str
    ) -> None:
        img = image(stored("Gain", address=None, missing=missing))
        assert reason(img, "Gain") == f"'Gain' has no address in the image: {missing}"


class TestWhereTheImageKeepsAVariable:
    """A global is where the symbol table puts it: a linker that discards a unit keeps its debug
    information, and gold leaves each address in it as an offset into the discarded section."""

    def test_a_global_with_no_symbol_of_its_name_at_its_address_is_not_placed(self) -> None:
        """The address is held by a section, so that nothing but the symbol table says the
        variable is gone."""
        img = image(stored("First_Unused", U32, address=0x4), objects=frozenset())
        assert reason(img, "First_Unused") == (
            "the symbol table holds no object named 'First_Unused' at 0x4, where its debug "
            "information puts it, as a linker leaves a variable of a unit it discarded"
        )

    def test_a_symbol_of_its_name_at_another_address_does_not_place_it(self) -> None:
        img = image(
            stored("Gain", address=0x4), objects=frozenset({("Gain", 0x100), ("Other", 0x4)})
        )
        assert reason(img, "Gain") == (
            "the symbol table holds no object named 'Gain' at 0x4, where its debug information "
            "puts it, as a linker leaves a variable of a unit it discarded"
        )

    def test_a_member_of_a_global_the_linker_discarded_is_not_placed_either(self) -> None:
        img = image(stored("Struct_Unused", PAIR, address=0), objects=frozenset())
        assert reason(img, "Struct_Unused.hi") == (
            "the symbol table holds no object named 'Struct_Unused' at 0x0, where its debug "
            "information puts it, as a linker leaves a variable of a unit it discarded"
        )

    def test_a_global_whose_symbol_sits_at_its_address_is_placed(self) -> None:
        img = image(stored("Gain", address=0x4), objects=frozenset({("Gain", 0x4)}))
        assert placed(img, "Gain") == Placed({"Gain": 0x4}, {})

    def test_an_address_no_section_holds_is_not_placed_in_the_words_from_elf_uses(self) -> None:
        """The symbol is there, and so the symbol table has no complaint."""
        img = image(
            stored("Gain", address=0x40),
            sections=(Section(".data", 0x100, 0x10, 0),),
        )
        assert reason(img, "Gain") == (
            "'Gain' has an address, 0x40, that no section of the image holds"
        )

    def test_the_first_byte_past_a_section_is_held_by_none(self) -> None:
        img = image(stored("Gain", address=0x110), sections=(Section(".data", 0x100, 0x10, 0),))
        assert "no section of the image holds" in reason(img, "Gain")

    def test_the_last_byte_of_a_section_is_held(self) -> None:
        img = image(stored("Gain", address=0x10F), sections=(Section(".data", 0x100, 0x10, 0),))
        assert placed(img, "Gain") == Placed({"Gain": 0x10F}, {})

    def test_the_debug_only_companion_places_what_the_image_it_was_split_from_does(self) -> None:
        """--image keeps reading it: objcopy --only-keep-debug leaves every address as it was,
        and its sections have no contents, which placing never needs."""
        linked = open_image(FIXTURES / "x86_64.elf")
        companion = open_image(FIXTURES / "x86_64.debug")
        names = ["Cal_Gain", "Cal_Table", "Meas_U16", "Missing_Name"]
        assert placed(companion, *names) == placed(linked, *names)
        assert len(placed(companion, *names).addresses) == 3

    def test_the_variables_of_a_unit_gold_discarded_are_not_placed(self) -> None:
        """gold-gc-sections.elf: the unit nothing references has debug information and no
        symbol, and its three variables sit at the offsets 0, 4 and 8 of the discarded
        section; the one the entry reads is placed."""
        found = placed(
            open_image(FIXTURES / "gold-gc-sections.elf"),
            "First_Unused",
            "Second_Unused",
            "Struct_Unused.a",
            "Struct_Unused.b",
            "Gold_Kept",
        )
        assert sorted(found.addresses) == ["Gold_Kept"]
        assert sorted(found.reasons) == [
            "First_Unused",
            "Second_Unused",
            "Struct_Unused.a",
            "Struct_Unused.b",
        ]
        assert found.reasons["First_Unused"] == (
            "the symbol table holds no object named 'First_Unused' at 0x8, where its debug "
            "information puts it, as a linker leaves a variable of a unit it discarded"
        )

    def test_the_same_source_linked_by_gnu_ld_places_the_same_one(self) -> None:
        """GNU ld drops the debug information of the unit it discarded, and the reader finds
        no variable of the name."""
        found = placed(open_image(FIXTURES / "bfd-gc-sections.elf"), "First_Unused", "Gold_Kept")
        assert sorted(found.addresses) == ["Gold_Kept"]
        assert found.reasons == {
            "First_Unused": "the image's debug information holds no variable named 'First_Unused'"
        }


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


class TestWhatTheImageHoldsOfEachSymbol:
    """``Placed.held``: the variable a symbol is, or belongs to, and the type its path ends at,
    which ``ddd.agreement`` holds to the description."""

    def test_an_object_is_held_as_the_type_of_its_variable_qualifiers_and_typedefs_kept(
        self,
    ) -> None:
        ctype = Qualified(Typedef("UWORD", U16), const=True)
        variable = stored("Gain", ctype, address=0x100)
        held = placed(image(variable), "Gain").held["Gain"]
        assert (held.variable, held.ctype, held.apart) == (variable, ctype, ())

    def test_a_member_is_held_as_the_type_its_path_ends_at_of_the_variable_it_belongs_to(
        self,
    ) -> None:
        variable = stored("Cells", Array(CELL, (3,)), address=0x700)
        found = placed(image(variable), "Cells[2].v", "Cells[0].raw")
        assert {symbol: (held.variable, held.ctype) for symbol, held in found.held.items()} == {
            "Cells[2].v": (variable, U16),
            "Cells[0].raw": (variable, U16),
        }

    def test_a_symbol_the_image_does_not_place_is_held_as_nothing(self) -> None:
        found = placed(image(stored("Inlet", INLET)), "Inlet.pair.mid", "Missing")
        assert found.held == {}

    def test_units_stating_one_size_hold_no_two_descriptions(self) -> None:
        first = stored("Gain", U32, unit="a.c", address=0x100)
        second = stored("Gain", U32, unit="b.c", address=0x100)
        assert placed(image(first, second), "Gain").held["Gain"].apart == ()

    def test_units_stating_two_sizes_hold_both_descriptions_and_the_first_is_not_the_variable(
        self,
    ) -> None:
        first = stored("Gain", U16, unit="a.c", address=0x100)
        second = stored("Gain", U32, unit="b.c", address=0x100)
        held = placed(image(first, second), "Gain").held["Gain"]
        assert held.apart == (first, second)

    def test_a_description_and_the_symbol_table_disagreeing_are_two_descriptions_too(self) -> None:
        variable = stored("Gain", U16, address=0x100)
        sized = Image(
            Path("hand.elf"),
            "little",
            (variable,),
            (EVERYWHERE,),
            frozenset(),
            b"",
            frozenset({("Gain", 0x100)}),
            object_sizes={("Gain", 0x100): 4},
        )
        assert addresses_from_image(sized, ["Gain"]).held["Gain"].apart == (variable,)

    def test_a_static_of_the_same_name_at_the_same_address_is_no_second_description(self) -> None:
        stray = stored("Gain", U32, unit="b.c", address=0x100, external=False)
        variable = stored("Gain", U16, unit="a.c", address=0x100)
        assert placed(image(variable, stray), "Gain").held["Gain"].apart == ()

    def test_a_static_of_the_same_name_elsewhere_is_no_second_description(self) -> None:
        stray = stored("Gain", U32, unit="b.c", address=0x200, external=False)
        variable = stored("Gain", U16, unit="a.c", address=0x100)
        assert placed(image(variable, stray), "Gain").held["Gain"].apart == ()


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


class TestTheImagesOfTwoCompilerOptions:
    """Built by ``docker/build_elf_fixtures.py`` from the source of the type unit fixture, which
    holds ``Struct_Inlet`` (a structure with an array) and ``Cal_Gain``."""

    def test_a_split_image_names_the_dwo_files_for_every_symbol(self) -> None:
        img = open_image(FIXTURES / "split-dwarf.elf")
        found = addresses_from_image(img, ["Struct_Inlet.raw[0]", "Cal_Gain"])
        assert found.addresses == {}
        said = (
            "the symbol table holds it, and the debug information of this image is in separate "
            ".dwo files (-gsplit-dwarf), which this tool does not read"
        )
        assert found.reasons == {
            "Struct_Inlet.raw[0]": (
                f"the image's debug information holds no variable named 'Struct_Inlet'; {said}"
            ),
            "Cal_Gain": f"the image's debug information holds no variable named 'Cal_Gain'; {said}",
        }

    def test_a_split_image_of_dwarf_4_is_told_the_same(self) -> None:
        """GNU's DWARF 4 extension names the skeleton's ``.dwo`` another way."""
        img = open_image(FIXTURES / "split-dwarf-4.elf")
        assert img.split_dwarf
        assert "separate .dwo files" in reason(img, "Cal_Gain")

    def test_an_image_of_debug_level_1_places_the_variables_and_not_a_path_into_one(self) -> None:
        img = open_image(FIXTURES / "debug-level-1.elf")
        found = addresses_from_image(img, ["Struct_Inlet", "Cal_Gain", "Struct_Inlet.raw[0]"])
        assert sorted(found.addresses) == ["Cal_Gain", "Struct_Inlet"]
        assert found.reasons == {
            "Struct_Inlet.raw[0]": (
                "the image's debug information gives 'Struct_Inlet' no type, as -g1 leaves it, "
                "so no path into it can be followed"
            )
        }

    def test_an_image_of_full_debug_information_is_neither(self) -> None:
        for name in ("x86_64", "armv7m"):
            assert not open_image(FIXTURES / f"{name}.elf").split_dwarf
        assert open_image(FIXTURES / "split-dwarf.elf").split_dwarf
        assert not open_image(FIXTURES / "debug-level-1.elf").split_dwarf
