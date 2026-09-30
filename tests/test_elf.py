"""The reader of ``ddd tool from-elf``: DWARF entries to the C model (with doubles here), and
linked images to it (over the fixture matrix, from Task 3 on)."""

from __future__ import annotations

import itertools
import json
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from elftools.elf.elffile import ELFFile

from ddd.elf import (
    DECLARED_ONLY,
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
    Declared,
    ElfReadError,
    Enum,
    FileTable,
    Image,
    Member,
    Qualified,
    Section,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    file_path,
    file_table,
    open_image,
    read_variables,
    size_of,
)

_OFFSETS = itertools.count(1)


@dataclass(frozen=True)
class Attr:
    """A double of pyelftools' ``AttributeValue``: the reader reads its value and its form."""

    value: Any
    form: str = "DW_FORM_data1"


@dataclass(eq=False)
class Die:
    """A double of pyelftools' ``DIE``, as :class:`ddd.elf.Entry` asks for one."""

    tag: str | int | None
    attributes: dict[str, Attr] = field(default_factory=dict)
    children: list[Die] = field(default_factory=list)
    references: dict[str, Die] = field(default_factory=dict)
    offset: int = field(default_factory=lambda: next(_OFFSETS))

    def iter_children(self) -> Iterator[Die]:
        return iter(self.children)

    def get_DIE_from_attribute(self, name: str) -> Die:  # noqa: N802 - pyelftools' name
        return self.references[name]


@dataclass
class FakeUnit:
    """A double of a compilation unit: its expressions are already ``(operation, arguments)``
    pairs, and its ``.debug_addr`` and file table are plain mappings."""

    top: Die
    name: str = "unit.c"
    files: dict[int, str] = field(default_factory=lambda: {1: "unit.c"})
    addresses: dict[int, int] = field(default_factory=dict)

    def operations(self, expression: Any) -> list[tuple[str, list[Any]]]:
        return list(expression)

    def indexed_address(self, index: int) -> int:
        return self.addresses[index]

    def file(self, index: int) -> str | None:
        return self.files.get(index)


def die(
    tag: str | int,
    *children: Die,
    of: Die | None = None,
    specification: Die | None = None,
    **attributes: Any,
) -> Die:
    """A DWARF entry: ``of`` is its ``DW_AT_type``, ``specification`` its declaration."""
    made = Die(
        tag,
        {
            name: value if isinstance(value, Attr) else Attr(value)
            for name, value in attributes.items()
        },
        list(children),
    )
    for name, target in (("DW_AT_type", of), ("DW_AT_specification", specification)):
        if target is not None:
            made.attributes[name] = Attr(target.offset, "DW_FORM_ref4")
            made.references[name] = target
    return made


U8 = die(
    "DW_TAG_base_type",
    DW_AT_name=b"unsigned char",
    DW_AT_encoding=DW_ATE_UNSIGNED_CHAR,
    DW_AT_byte_size=1,
)
U8_TYPE = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
AT = [("DW_OP_addr", [0x100])]
DECLARATION = Attr(True, "DW_FORM_flag_present")


def variable(
    name: bytes | str = b"v", *, of: Die | None = None, located: bool = True, **attributes: Any
) -> Die:
    attributes["DW_AT_name"] = name
    if located:
        attributes.setdefault("DW_AT_location", Attr(AT, "DW_FORM_exprloc"))
    return die("DW_TAG_variable", of=U8 if of is None else of, **attributes)


def read(*entries: Die, big_endian: bool = False, **unit: Any) -> tuple[Variable, ...]:
    return read_variables(
        [FakeUnit(die("DW_TAG_compile_unit", *entries), **unit)], big_endian=big_endian
    )


def type_of(entry: Die, *, big_endian: bool = False) -> CType:
    (found,) = read(variable(of=entry), big_endian=big_endian)
    return found.type


def subrange(**attributes: Any) -> Die:
    return die("DW_TAG_subrange_type", **attributes)


def enumerator(name: bytes, value: int, form: str = "DW_FORM_data1") -> Die:
    return die("DW_TAG_enumerator", DW_AT_name=name, DW_AT_const_value=Attr(value, form))


def member(name: bytes | None, of: Die, **attributes: Any) -> Die:
    if name is not None:
        attributes["DW_AT_name"] = name
    return die("DW_TAG_member", of=of, **attributes)


class TestTypes:
    def test_a_base_type_is_its_name_encoding_and_size(self) -> None:
        entry = die(
            "DW_TAG_base_type",
            DW_AT_name=b"unsigned int",
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=4,
        )
        assert type_of(entry) == Base("unsigned int", DW_ATE_UNSIGNED, 4)

    def test_a_typedef_keeps_its_name_over_what_it_stands_for(self) -> None:
        assert type_of(die("DW_TAG_typedef", of=U8, DW_AT_name=b"uint8_t")) == Typedef(
            "uint8_t", U8_TYPE
        )

    def test_const_and_volatile_are_one_qualifier_each(self) -> None:
        entry = die("DW_TAG_const_type", of=die("DW_TAG_volatile_type", of=U8))
        assert type_of(entry) == Qualified(Qualified(U8_TYPE, volatile=True), const=True)

    def test_restrict_is_passed_through(self) -> None:
        assert type_of(die("DW_TAG_restrict_type", of=U8)) == U8_TYPE

    def test_a_qualifier_of_nothing_qualifies_void(self) -> None:
        assert type_of(die("DW_TAG_const_type")) == Qualified(Unsupported("void"), const=True)

    @pytest.mark.parametrize(
        ("tag", "what"),
        [
            ("DW_TAG_pointer_type", "a pointer"),
            ("DW_TAG_union_type", "a union"),
            ("DW_TAG_class_type", "a class"),
            ("DW_TAG_reference_type", "a reference"),
            ("DW_TAG_rvalue_reference_type", "a reference"),
            ("DW_TAG_subroutine_type", "a function"),
            ("DW_TAG_ptr_to_member_type", "a pointer to member"),
            ("DW_TAG_atomic_type", "an _Atomic type"),
            ("DW_TAG_unspecified_type", "an unspecified type"),
        ],
    )
    def test_a_type_ddd_has_no_word_for_is_unsupported_by_name(self, tag: str, what: str) -> None:
        assert type_of(die(tag, of=U8)) == Unsupported(what)

    def test_a_tag_nobody_named_is_unsupported_by_its_number(self) -> None:
        assert type_of(die(0x4109)) == Unsupported("a type DWARF tags 16649")

    def test_an_array_states_its_extents_in_c_order(self) -> None:
        entry = die(
            "DW_TAG_array_type", subrange(DW_AT_upper_bound=1), subrange(DW_AT_count=3), of=U8
        )
        assert type_of(entry) == Array(U8_TYPE, (2, 3))

    def test_a_lower_bound_counts(self) -> None:
        entry = die("DW_TAG_array_type", subrange(DW_AT_lower_bound=1, DW_AT_upper_bound=4), of=U8)
        assert type_of(entry) == Array(U8_TYPE, (4,))

    def test_a_child_that_is_no_subrange_is_passed_over(self) -> None:
        entry = die(
            "DW_TAG_array_type", die("DW_TAG_enumeration_type"), subrange(DW_AT_count=2), of=U8
        )
        assert type_of(entry) == Array(U8_TYPE, (2,))

    @pytest.mark.parametrize(
        "bounds",
        [
            {},
            {"DW_AT_upper_bound": Attr([0x91, 0x00], "DW_FORM_exprloc")},
            {"DW_AT_lower_bound": Attr([0x91, 0x00], "DW_FORM_exprloc"), "DW_AT_upper_bound": 3},
            {"DW_AT_count": 0},
        ],
        ids=["flexible", "variable length", "variable lower bound", "zero length"],
    )
    def test_an_array_without_a_fixed_positive_size_is_unsupported(
        self, bounds: dict[str, Any]
    ) -> None:
        assert type_of(die("DW_TAG_array_type", subrange(**bounds), of=U8)) == Unsupported(
            "an array without a fixed size of at least one element"
        )

    def test_an_array_without_any_subrange_is_unsupported(self) -> None:
        assert type_of(die("DW_TAG_array_type", of=U8)) == Unsupported(
            "an array without a fixed size of at least one element"
        )

    def test_an_enum_takes_its_sign_from_its_underlying_type(self) -> None:
        signed_char = die(
            "DW_TAG_base_type",
            DW_AT_name=b"signed char",
            DW_AT_encoding=DW_ATE_SIGNED_CHAR,
            DW_AT_byte_size=1,
        )
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"LOW", 0xFE),
            of=die("DW_TAG_typedef", of=signed_char, DW_AT_name=b"int8_t"),
            DW_AT_name=b"Level_e",
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum("Level_e", 1, True, (("LOW", -2),))

    def test_an_underlying_type_that_is_no_base_type_leaves_the_encoding_to_decide(
        self,
    ) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 200),
            of=die("DW_TAG_pointer_type"),
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, False, (("A", 200),))

    def test_without_an_underlying_type_the_encoding_decides(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 0xFF),
            DW_AT_encoding=DW_ATE_SIGNED,
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, True, (("A", -1),))

    def test_with_neither_a_negative_enumerator_makes_an_enum_signed(self) -> None:
        """What strict DWARF 2 leaves to go on: the armv7m-dwarf2 row's Enum_Signed."""
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"NEG", -2, "DW_FORM_sdata"),
            enumerator(b"POS", 3),
            DW_AT_byte_size=4,
        )
        assert type_of(entry) == Enum(None, 4, True, (("NEG", -2), ("POS", 3)))

    def test_with_neither_and_no_negative_enumerator_an_enum_is_unsigned(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"BIG", 0xFF),
            enumerator(b"NONE", 0, "DW_FORM_sdata"),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, False, (("BIG", 255), ("NONE", 0)))

    def test_an_enumerator_in_a_form_of_its_own_sign_is_read_as_it_is(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"WIDE", 255, "DW_FORM_udata"),
            DW_AT_encoding=DW_ATE_SIGNED,
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Enum(None, 2, True, (("WIDE", 255),))

    @pytest.mark.parametrize(
        ("form", "raw"),
        [
            ("DW_FORM_data1", 0xFF),
            ("DW_FORM_data2", 0xFFFF),
            ("DW_FORM_data4", 0xFFFF_FFFF),
            ("DW_FORM_data8", 0xFFFF_FFFF_FFFF_FFFF),
        ],
    )
    def test_an_enumerator_is_sign_extended_from_the_width_of_its_form(
        self, form: str, raw: int
    ) -> None:
        """Each ``DW_FORM_dataN`` sign-extends from its own width: ``raw`` is all ones at
        that width and no wider, so it reads as -1 only where the width is the right one."""
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"NEG", raw, form),
            of=die(
                "DW_TAG_base_type",
                DW_AT_name=b"int",
                DW_AT_encoding=DW_ATE_SIGNED,
                DW_AT_byte_size=4,
            ),
            DW_AT_name=b"Wide_e",
            DW_AT_byte_size=4,
        )
        assert type_of(entry) == Enum("Wide_e", 4, True, (("NEG", -1),))

    def test_an_enum_declared_but_never_defined_is_unsupported(self) -> None:
        entry = die("DW_TAG_enumeration_type", DW_AT_declaration=DECLARATION)
        assert type_of(entry) == Unsupported("an enum declared but never defined")

    def test_an_enum_knows_where_it_is_declared(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 1),
            DW_AT_byte_size=4,
            DW_AT_decl_file=1,
            DW_AT_decl_line=7,
        )
        assert type_of(entry) == Enum(None, 4, False, (("A", 1),), Declared("unit.c", 7))

    def test_a_child_that_is_no_enumerator_is_passed_over(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            die("DW_TAG_subprogram"),
            enumerator(b"A", 1),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, False, (("A", 1),))

    def test_a_structure_lists_its_members_where_they_start(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"a", U8, DW_AT_data_member_location=0),
            member(b"b", U8, DW_AT_data_member_location=1),
            DW_AT_name=b"Pair_s",
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(
            "Pair_s", 2, (Member("a", U8_TYPE, 0), Member("b", U8_TYPE, 8))
        )

    def test_a_member_offset_given_as_an_expression_is_read(self) -> None:
        """DW_OP_plus_uconst 300, its operand two bytes of ULEB128, as DWARF 2 spells it."""
        entry = die(
            "DW_TAG_structure_type",
            member(
                b"far", U8, DW_AT_data_member_location=Attr([0x23, 0xAC, 0x02], "DW_FORM_block1")
            ),
            DW_AT_byte_size=301,
        )
        assert type_of(entry) == Struct(None, 301, (Member("far", U8_TYPE, 2400),))

    def test_a_member_offset_given_as_another_expression_is_unknown(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"odd", U8, DW_AT_data_member_location=Attr([0x10, 0x01], "DW_FORM_block1")),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("odd", U8_TYPE, None),))

    def test_an_operand_cut_short_is_read_as_far_as_it_goes(self) -> None:
        """0x81 announces a second byte that never comes: the loop runs out of data rather
        than reaching a last byte, which is the one arc of it the other tests do not take."""
        entry = die(
            "DW_TAG_structure_type",
            member(b"cut", U8, DW_AT_data_member_location=Attr([0x23, 0x81], "DW_FORM_block1")),
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(None, 2, (Member("cut", U8_TYPE, 8),))

    def test_a_member_without_an_offset_starts_the_structure(self) -> None:
        entry = die("DW_TAG_structure_type", member(b"only", U8), DW_AT_byte_size=1)
        assert type_of(entry) == Struct(None, 1, (Member("only", U8_TYPE, 0),))

    def test_dwarf_4_and_later_may_state_a_bitfield_s_offset_outright(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"b", U8, DW_AT_bit_size=2, DW_AT_data_bit_offset=5),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("b", U8_TYPE, 5, 2),))

    @pytest.mark.parametrize(("big_endian", "bit_offset"), [(False, 1), (True, 5)])
    def test_older_dwarf_counts_a_bitfield_from_its_unit_s_most_significant_bit(
        self, big_endian: bool, bit_offset: int
    ) -> None:
        """``b`` of ``uint8_t a:2; uint8_t :3; uint8_t b:2`` starts at bit 5 on every target.
        gcc states it as DW_AT_bit_offset 1 in a one byte unit on a little endian one
        (measured, gcc 15 at DWARF 2), counting from the unit's most significant bit, which is
        its last; and as 5 on a big endian one, where that bit is the unit's first."""
        entry = die(
            "DW_TAG_structure_type",
            member(
                b"b",
                U8,
                DW_AT_bit_size=2,
                DW_AT_bit_offset=bit_offset,
                DW_AT_byte_size=1,
                DW_AT_data_member_location=0,
            ),
            DW_AT_byte_size=1,
        )
        assert type_of(entry, big_endian=big_endian) == Struct(
            None, 1, (Member("b", U8_TYPE, 5, 2),)
        )

    def test_a_bitfield_without_a_unit_size_takes_its_type_s(self) -> None:
        u16 = die(
            "DW_TAG_base_type",
            DW_AT_name=b"short unsigned int",
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=2,
        )
        entry = die(
            "DW_TAG_structure_type",
            member(b"c", u16, DW_AT_bit_size=9, DW_AT_bit_offset=0, DW_AT_data_member_location=0),
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(
            None, 2, (Member("c", Base("short unsigned int", DW_ATE_UNSIGNED, 2), 7, 9),)
        )

    def test_a_bit_offset_without_a_width_leaves_the_byte_offset(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_bit_offset=3, DW_AT_data_member_location=2),
            DW_AT_byte_size=3,
        )
        assert type_of(entry) == Struct(None, 3, (Member("x", U8_TYPE, 16),))

    def test_a_member_without_a_name_is_kept_anonymous(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(None, U8, DW_AT_data_member_location=0),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member(None, U8_TYPE, 0),))

    def test_alignment_is_kept_where_dwarf_states_it(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_data_member_location=0, DW_AT_alignment=8),
            DW_AT_byte_size=8,
            DW_AT_alignment=8,
        )
        assert type_of(entry) == Struct(
            None, 8, (Member("x", U8_TYPE, 0, alignment=8),), alignment=8
        )

    def test_a_child_that_is_no_member_is_passed_over(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            die("DW_TAG_subprogram"),
            member(b"x", U8, DW_AT_data_member_location=0),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("x", U8_TYPE, 0),))

    def test_a_structure_declared_but_never_defined_is_unsupported(self) -> None:
        entry = die("DW_TAG_structure_type", DW_AT_declaration=DECLARATION)
        assert type_of(entry) == Unsupported("a structure declared but never defined")

    def test_a_structure_and_its_members_know_where_they_are_declared(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_data_member_location=0, DW_AT_decl_file=1, DW_AT_decl_line=4),
            DW_AT_byte_size=1,
            DW_AT_decl_file=1,
            DW_AT_decl_line=3,
        )
        assert type_of(entry) == Struct(
            None,
            1,
            (Member("x", U8_TYPE, 0, declared_at=Declared("unit.c", 4)),),
            declared_at=Declared("unit.c", 3),
        )

    def test_a_type_reached_twice_is_built_once(self) -> None:
        shared = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_data_member_location=0),
            DW_AT_byte_size=1,
        )
        first, second = read(variable(b"a", of=shared), variable(b"b", of=shared))
        assert first.type is second.type


class TestVariables:
    def test_a_variable_has_its_name_unit_type_declaration_and_address(self) -> None:
        (found,) = read(variable(b"Gain", DW_AT_decl_file=1, DW_AT_decl_line=12))
        assert found == Variable("Gain", "unit.c", U8_TYPE, Declared("unit.c", 12), 0x100)

    def test_an_indexed_address_is_resolved_through_the_unit(self) -> None:
        location = Attr([("DW_OP_addrx", [3])], "DW_FORM_exprloc")
        (found,) = read(variable(DW_AT_location=location), addresses={3: 0x2000})
        assert found.address == 0x2000

    @pytest.mark.parametrize("operation", ["DW_OP_form_tls_address", "DW_OP_GNU_push_tls_address"])
    def test_a_thread_local_variable_has_no_address(self, operation: str) -> None:
        location = Attr([("DW_OP_const8u", [0]), (operation, [])], "DW_FORM_exprloc")
        (found,) = read(variable(DW_AT_location=location))
        assert (found.address, found.missing) == (None, THREAD_LOCAL)

    @pytest.mark.parametrize(
        "location",
        [
            Attr(0x40, "DW_FORM_sec_offset"),
            Attr([("DW_OP_fbreg", [-8])], "DW_FORM_exprloc"),
            Attr([], "DW_FORM_exprloc"),
        ],
        ids=["location list", "frame relative", "empty"],
    )
    def test_a_location_that_is_not_one_address_is_no_address(self, location: Attr) -> None:
        (found,) = read(variable(DW_AT_location=location))
        assert (found.address, found.missing) == (None, NOT_AN_ADDRESS)

    def test_a_variable_the_compiler_folded_has_no_address(self) -> None:
        (found,) = read(variable(located=False, DW_AT_const_value=7))
        assert (found.address, found.missing) == (None, FOLDED)

    def test_a_variable_without_location_or_value_was_removed(self) -> None:
        (found,) = read(variable(located=False))
        assert (found.address, found.missing) == (None, REMOVED)

    def test_a_variable_without_a_location_the_symbol_table_calls_thread_local_is(self) -> None:
        """What aarch64's DWARF leaves for a thread-local variable: no location at all."""
        units = [FakeUnit(die("DW_TAG_compile_unit", variable(b"Counter", located=False)))]
        (found,) = read_variables(units, big_endian=False, thread_local=frozenset({"Counter"}))
        assert (found.address, found.missing) == (None, THREAD_LOCAL)

    def test_a_declaration_is_dropped_where_something_defines_its_name(self) -> None:
        declared = variable(b"Elsewhere", located=False, DW_AT_declaration=DECLARATION)
        (found,) = read(declared, variable(b"Elsewhere"))
        assert found.address == 0x100

    def test_a_declaration_is_kept_where_nothing_defines_its_name(self) -> None:
        (found,) = read(variable(b"Nowhere", located=False, DW_AT_declaration=DECLARATION))
        assert (found.address, found.missing) == (None, DECLARED_ONLY)

    def test_a_name_declared_by_two_units_is_kept_once(self) -> None:
        units = [
            FakeUnit(
                die(
                    "DW_TAG_compile_unit",
                    variable(b"Nowhere", located=False, DW_AT_declaration=DECLARATION),
                )
            )
            for _ in range(2)
        ]
        assert len(read_variables(units, big_endian=False)) == 1

    def test_a_definition_completing_a_declaration_takes_its_name_type_and_file_from_it(
        self,
    ) -> None:
        declaration = variable(
            b"Spec",
            located=False,
            DW_AT_declaration=DECLARATION,
            DW_AT_decl_file=1,
            DW_AT_decl_line=4,
        )
        definition = die(
            "DW_TAG_variable",
            specification=declaration,
            DW_AT_decl_line=5,
            DW_AT_location=Attr(AT, "DW_FORM_exprloc"),
        )
        (found,) = read(declaration, definition)
        assert found == Variable("Spec", "unit.c", U8_TYPE, Declared("unit.c", 5), 0x100)

    def test_a_definition_completing_an_array_of_no_size_takes_its_own_type(self) -> None:
        """``extern const uint16_t Cal_Curve[];`` then ``const uint16_t Cal_Curve[4] = ...``:
        gcc 15.2 states the completed type on the definition, beside DW_AT_specification, and
        the declaration's array has no extent (measured)."""
        declaration = variable(
            b"Curve",
            of=die("DW_TAG_array_type", subrange(), of=U8),
            located=False,
            DW_AT_declaration=DECLARATION,
        )
        definition = die(
            "DW_TAG_variable",
            specification=declaration,
            of=die("DW_TAG_array_type", subrange(DW_AT_upper_bound=3), of=U8),
            DW_AT_location=Attr(AT, "DW_FORM_exprloc"),
        )
        (found,) = read(declaration, definition)
        assert (found.name, found.type) == ("Curve", Array(U8_TYPE, (4,)))

    def test_an_entry_without_a_name_is_passed_over(self) -> None:
        assert read(die("DW_TAG_variable", of=U8, DW_AT_location=Attr(AT, "DW_FORM_exprloc"))) == ()

    def test_only_the_top_of_a_unit_is_read(self) -> None:
        assert read(die("DW_TAG_subprogram", variable(b"Local"), DW_AT_name=b"f")) == ()

    def test_a_variable_without_a_type_is_void(self) -> None:
        (found,) = read(
            die("DW_TAG_variable", DW_AT_name=b"v", DW_AT_location=Attr(AT, "DW_FORM_exprloc"))
        )
        assert found.type == Unsupported("void")

    def test_a_declaration_the_file_table_does_not_hold_is_none(self) -> None:
        (found,) = read(variable(DW_AT_decl_file=9, DW_AT_decl_line=3))
        assert found.declared_at is None

    def test_a_declaration_without_a_line_is_none(self) -> None:
        (found,) = read(variable(DW_AT_decl_file=1))
        assert found.declared_at is None

    def test_a_name_may_arrive_as_text(self) -> None:
        (found,) = read(variable("Text"))
        assert found.name == "Text"


class TestFileTable:
    def test_no_table_names_no_file(self) -> None:
        assert file_path(None, 1) is None

    def test_dwarf_5_counts_from_zero_with_directory_zero_the_compilation_directory(self) -> None:
        table = FileTable(5, (("main.c", 0), ("shared.h", 1)), ("/work/src", "include"), "/x")
        assert (file_path(table, 0), file_path(table, 1)) == (
            "/work/src/main.c",
            "include/shared.h",
        )

    def test_older_dwarf_counts_from_one_and_takes_directory_zero_from_the_unit(self) -> None:
        table = FileTable(4, (("main.c", 0), ("shared.h", 1)), ("include",), ".")
        assert (file_path(table, 0), file_path(table, 1), file_path(table, 2)) == (
            None,
            "main.c",
            "include/shared.h",
        )

    def test_an_index_past_the_table_names_no_file(self) -> None:
        assert file_path(FileTable(5, (("main.c", 0),), (".",), "."), 1) is None

    def test_a_directory_index_past_the_table_is_left_out(self) -> None:
        assert file_path(FileTable(5, (("main.c", 7),), (".",), "."), 0) == "main.c"

    @pytest.mark.parametrize("name", ["/abs/main.c", "C:/proj/main.c", "C:\\proj\\main.c"])
    def test_an_absolute_name_ignores_its_directory(self, name: str) -> None:
        table = FileTable(5, ((name, 0),), ("/elsewhere",), ".")
        assert file_path(table, 0) == name.replace("\\", "/")

    def test_backslashes_become_slashes(self) -> None:
        table = FileTable(5, (("src\\main.c", 0),), ("C:\\proj",), ".")
        assert file_path(table, 0) == "C:/proj/src/main.c"


class TestSizes:
    def test_a_size_follows_qualifiers_typedefs_and_arrays(self) -> None:
        assert size_of(Qualified(Typedef("t", Array(U8_TYPE, (2, 3))), const=True)) == 6

    def test_an_enum_and_a_structure_have_their_own(self) -> None:
        assert (size_of(Enum(None, 1, False, ())), size_of(Struct(None, 12, ()))) == (1, 12)

    def test_what_the_model_does_not_describe_has_none(self) -> None:
        assert size_of(Unsupported("a pointer")) is None
        assert size_of(Array(Unsupported("a pointer"), (2,))) is None


IMAGE = Image(
    Path("hand.elf"),
    "little",
    (),
    (Section(".data", 0x100, 4, 0x10), Section(".bss", 0x200, 4, None)),
    frozenset(),
    bytes(range(32)),
)


class TestImage:
    def test_a_read_takes_bytes_out_of_the_section_s_contents(self) -> None:
        assert IMAGE.read(0x101, 2) == bytes([0x11, 0x12])

    def test_a_section_without_contents_holds_no_bytes(self) -> None:
        assert IMAGE.read(0x200, 4) is None

    def test_a_read_past_the_end_of_a_section_is_none(self) -> None:
        assert IMAGE.read(0x102, 4) is None

    def test_an_address_outside_every_section_is_none(self) -> None:
        assert IMAGE.read(0x300, 1) is None
        assert IMAGE.section_of(0x300) is None

    def test_the_section_holding_an_address_is_the_one_that_spans_it(self) -> None:
        found = IMAGE.section_of(0x103)
        assert found is not None
        assert found.name == ".data"
        assert IMAGE.section_of(0x104) is None


FIXTURES = Path(__file__).parent / "fixtures" / "elf"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
MAIN = (FIXTURES / "src" / "main.c").read_text(encoding="utf-8").splitlines()


def line_of(text: str) -> int:
    """The line of main.c holding ``text``: the oracle for where a variable is declared."""
    (found,) = [number for number, line in enumerate(MAIN, start=1) if text in line]
    return found


def by_name(image: Image, name: str) -> Variable:
    (found,) = [variable for variable in image.variables if variable.name == name]
    return found


def core(ctype: CType) -> CType:
    while isinstance(ctype, Qualified | Typedef | Array):
        ctype = ctype.element if isinstance(ctype, Array) else ctype.inner
    return ctype


@pytest.fixture(scope="module", params=sorted(MANIFEST["rows"]))
def row(request: pytest.FixtureRequest) -> tuple[Image, dict[str, Any]]:
    """One row of the matrix, opened once for every test that reads it."""
    return open_image(FIXTURES / f"{request.param}.elf"), MANIFEST["rows"][request.param]


class TestTheMatrix:
    """Every row read against what its own toolchain said about it (the manifest)."""

    def test_the_byte_order_is_the_toolchain_s(self, row: tuple[Image, dict[str, Any]]) -> None:
        image, entry = row
        assert image.byte_order == entry["traits"]["byte_order"]

    def test_every_variable_is_in_the_section_the_symbol_table_puts_it_in(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        found: dict[str, set[tuple[str, bool]]] = {}
        for variable in image.variables:
            if variable.address is None:
                continue
            section = image.section_of(variable.address)
            assert section is not None, variable.name
            found.setdefault(variable.name, set()).add((section.name, section.offset is not None))
        expected: dict[str, set[tuple[str, bool]]] = {}
        for record in entry["variables"]:
            if record["name"] in found:
                expected.setdefault(record["name"], set()).add(
                    (record["section"], record["contents"])
                )
        assert found == expected

    def test_every_sized_variable_is_the_size_the_symbol_table_gives_it(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        sizes = {record["name"]: record["size"] for record in entry["variables"]}
        stored = [variable for variable in image.variables if variable.address is not None]
        unsized = {variable.name for variable in stored if size_of(variable.type) is None}
        assert unsized == {"Type_Pointer", "Type_Union"}
        for variable in stored:
            if variable.name not in unsized:
                assert size_of(variable.type) == sizes[variable.name], variable.name

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("Meas_U16", 0x1234),
            ("Meas_Volatile", 0x12345678),
            ("Cal_Gain", 300),
            ("Type_U64", 0x0102030405060708),
            ("Static_Used", 0x0102),
        ],
    )
    def test_an_initial_value_reads_back_in_the_image_s_byte_order(
        self, row: tuple[Image, dict[str, Any]], name: str, value: int
    ) -> None:
        image, _ = row
        variable = by_name(image, name)
        assert variable.address is not None
        size = size_of(variable.type)
        assert size is not None
        raw = image.read(variable.address, size)
        assert raw is not None
        assert int.from_bytes(raw, image.byte_order) == value

    def test_char_long_and_long_double_are_what_the_target_makes_them(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        traits = entry["traits"]
        char = core(by_name(image, "Type_Char").type)
        assert isinstance(char, Base)
        unsigned = traits["char_unsigned"]
        assert char.encoding == (DW_ATE_UNSIGNED_CHAR if unsigned else DW_ATE_SIGNED_CHAR)
        assert size_of(by_name(image, "Type_Long").type) == traits["sizeof_long"]
        assert size_of(by_name(image, "Type_Long_Double").type) == traits["sizeof_long_double"]

    def test_an_enum_is_as_wide_as_the_target_makes_it_and_signed_where_its_values_are(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 2: on strict DWARF 2 an enum states no underlying type and no
        encoding, and only its negative enumerator says it is signed."""
        image, entry = row
        state = core(by_name(image, "Enum_State").type)
        signed = core(by_name(image, "Enum_Signed").type)
        assert isinstance(state, Enum)
        assert isinstance(signed, Enum)
        width = entry["traits"]["sizeof_enum"]
        assert (state.size, state.signed) == (width, False)
        assert (signed.size, signed.signed) == (width, True)
        assert signed.enumerators == (("SIGNED_NEG", -2), ("SIGNED_POS", 3))

    def test_bitfields_start_at_the_same_bits_whatever_the_byte_order_or_the_dwarf(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 1: DWARF 2 and 3 count DW_AT_bit_offset from the storage unit's most
        significant bit, so the conversion differs by byte order; the offsets must not."""
        image, _ = row
        gapped = core(by_name(image, "Layout_Gapped").type)
        padded = core(by_name(image, "Layout_Padded").type)
        assert isinstance(gapped, Struct)
        assert isinstance(padded, Struct)
        assert [(m.name, m.bit_offset, m.bit_size) for m in gapped.members] == [
            ("a", 0, 2),
            ("b", 5, 2),
            ("c", 7, 9),
        ]
        assert [(m.name, m.bit_offset, m.bit_size) for m in padded.members] == [
            ("a", 0, 7),
            ("b", 8, 2),
        ]

    def test_structures_of_structures_arrays_and_signed_bitfields_read_the_same_everywhere(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """An array of structures inside a structure, a two dimensional array member and
        signed bitfields: the member shapes the fixture gained after Task 1. DWARF 2 to 4 state
        a bitfield from its storage unit's most significant bit, so on big endian rows the
        conversion runs the other way; the offsets must not move."""
        image, _ = row
        frame = core(by_name(image, "Nested_Frame").type)
        assert isinstance(frame, Struct)
        samples, grid, trim = frame.members
        assert isinstance(samples.type, Array)
        assert (samples.name, samples.bit_offset, samples.type.dimensions) == ("samples", 0, (3,))
        assert isinstance(grid.type, Array)
        assert (grid.name, grid.bit_offset, grid.type.dimensions) == ("grid", 48, (2, 3))
        assert (trim.name, trim.bit_offset, trim.bit_size) == ("trim", 144, 4)
        sample = core(samples.type)
        assert isinstance(sample, Struct)
        assert [(m.name, m.bit_offset, m.bit_size) for m in sample.members] == [
            ("low", 0, 3),
            ("high", 3, 5),
            ("level", 8, None),
        ]
        signed = [core(member.type) for member in (*sample.members[:2], trim)]
        assert [(base.encoding, base.size) for base in signed if isinstance(base, Base)] == [
            (DW_ATE_SIGNED_CHAR, 1),
            (DW_ATE_SIGNED, 2),
            (DW_ATE_SIGNED_CHAR, 1),
        ]

    def test_an_explicit_alignment_is_read_where_the_dwarf_states_it(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """gcc on the Linux targets states it on the structure and on the member, gcc for
        arm-none-eabi and clang on the member alone (the trial build): the member is held to
        the trait, the structure may carry it or not."""
        image, entry = row
        aligned = core(by_name(image, "Layout_Aligned").type)
        assert isinstance(aligned, Struct)
        expected = 8 if entry["traits"]["alignment_attribute"] else None
        assert aligned.members[0].alignment == expected
        assert aligned.alignment in (expected, None)

    def test_thread_local_storage_has_no_address_and_its_sections_are_left_out(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 5: .tbss shares its addresses with the section after it."""
        image, entry = row
        assert "FIXTURE_TLS" in entry["cases"], "every row builds the thread-local case"
        assert by_name(image, "Tls_Counter").missing == THREAD_LOCAL
        placed = {r["section"] for r in entry["variables"] if r["name"] == "Tls_Counter"}
        assert placed
        assert not placed & {section.name for section in image.sections}

    def test_an_unallocated_section_is_left_out_of_the_image(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """The other half of _sections' filter: .symtab and .debug_info are in every file but
        never loaded into the target's memory and state no real address - unfiltered, either
        could shadow a real section that happens to start at address zero."""
        image, _ = row
        with image.path.open("rb") as stream:
            names = {section.name for section in ELFFile(stream).iter_sections()}
        assert {".symtab", ".debug_info"} <= names
        assert not {".symtab", ".debug_info"} & {section.name for section in image.sections}

    def test_a_folded_static_has_no_address_where_the_row_builds_one(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        names = {variable.name for variable in image.variables}
        assert ("Static_Folded" in names) == ("FIXTURE_FOLDED" in entry["cases"])
        if "Static_Folded" in names:
            assert by_name(image, "Static_Folded").missing == FOLDED

    def test_a_variable_of_a_unit_without_dwarf_is_in_the_symbol_table_only(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        assert "Nodebug_Counter" in image.symbols
        assert "Nodebug_Counter" not in {variable.name for variable in image.variables}

    def test_a_function_and_a_thread_local_variable_are_left_out_of_the_symbols(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """The other half of _symbols' filter: a function is STT_FUNC and a thread-local
        variable is STT_TLS, neither of which the STT_OBJECT-only image.symbols keeps."""
        image, entry = row
        with image.path.open("rb") as stream:
            symtab = ELFFile(stream).get_section_by_name(".symtab")
            names = {symbol.name for symbol in symtab.iter_symbols()}
        assert "fixture_entry" in names
        assert any(record["name"] == "Tls_Counter" for record in entry["variables"])
        assert not {"fixture_entry", "Tls_Counter"} & image.symbols

    def test_a_definition_completing_a_declaration_is_declared_at_its_own_line(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        assert by_name(image, "Cal_Declared_First").declared_at == Declared(
            "main.c", line_of("const uint16_t Cal_Declared_First = 0x1234;")
        )

    def test_a_static_two_units_define_is_two_variables(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        twins = sorted(variable.unit for variable in image.variables if variable.name == "Twin")
        assert twins == ["unit_a.c", "unit_b.c"]


class TestRefusals:
    """What open_image refuses, each in a sentence naming the file. Where the end of the
    sentence is pyelftools' own words about a damaged file, the test pins ours and leaves
    theirs to them."""

    def test_a_file_that_cannot_be_read_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.elf"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (f"cannot read '{path.as_posix()}': No such file or directory")

    def test_a_file_that_is_not_elf_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.txt"
        path.write_bytes(b"not an image")
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
            f"Magic number does not match"
        )

    def test_a_truncated_image_is_refused(self, tmp_path: Path) -> None:
        data = (FIXTURES / "x86_64.elf").read_bytes()
        path = tmp_path / "truncated.elf"
        path.write_bytes(data[: len(data) // 2])
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value).startswith(
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
        )

    def test_debug_information_of_a_version_pyelftools_does_not_read_is_refused(
        self, tmp_path: Path
    ) -> None:
        data = bytearray((FIXTURES / "x86_64.elf").read_bytes())
        with (FIXTURES / "x86_64.elf").open("rb") as stream:
            offset = ELFFile(stream).get_section_by_name(".debug_info")["sh_offset"]
        # A unit's header: a four byte length, then its two byte version.
        data[offset + 4 : offset + 6] = (9).to_bytes(2, "little")
        path = tmp_path / "future.elf"
        path.write_bytes(bytes(data))
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
            f"Expected supported DWARF version. Got '9'"
        )

    def test_an_image_without_dwarf_is_refused_naming_g(self) -> None:
        path = FIXTURES / "stripped.elf"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' carries no DWARF debug information: build it with -g"
        )

    def test_a_relocatable_object_is_refused(self) -> None:
        path = FIXTURES / "main.o"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is a relocatable object, not a linked image: its addresses "
            f"and its initial values are not final until it is linked"
        )

    def test_an_elf_file_of_another_kind_is_refused(self, tmp_path: Path) -> None:
        data = bytearray((FIXTURES / "x86_64.elf").read_bytes())
        data[16:18] = (4).to_bytes(2, "little")  # e_type ET_CORE; the row is little endian
        path = tmp_path / "core.elf"
        path.write_bytes(bytes(data))
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is an ELF file of type ET_CORE, not a linked image"
        )

    def test_an_image_whose_section_runs_past_the_end_of_its_file_is_refused(
        self, tmp_path: Path
    ) -> None:
        data = bytearray((FIXTURES / "armv7m.elf").read_bytes())
        with (FIXTURES / "armv7m.elf").open("rb") as stream:
            elf = ELFFile(stream)
            index = elf.get_section_index(".data")
            entry = elf.header["e_shoff"] + index * elf.header["e_shentsize"]
        struct.pack_into("<I", data, entry + 16, len(data) - 2)
        path = tmp_path / "overrun.elf"
        path.write_bytes(bytes(data))
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is not an ELF image this tool can read: its section "
            f"'.data' runs past the end of the file"
        )

    def test_a_unit_without_a_line_program_has_no_file_table(self) -> None:
        assert file_table(None, ".") is None
