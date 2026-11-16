"""The translator of ``ddd tool from-elf``, on hand-built images: which variables the
arguments name, how their types are spelled, their initial values, and DDD's own verdict on
the result. The reader has its own tests (``tests/test_elf.py``); here nothing is read from a
file, so every case is exactly the one its test names."""

from __future__ import annotations

import copy
import json
import math
import struct
from pathlib import Path
from typing import Any, Literal

import pytest

from ddd.diagnostics import CHECKS, STANDALONE_POLICY, DiagnosticBag, Location, Severity, where
from ddd.elf import (
    DECLARED_ONLY,
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    FOLDED,
    OTHER_SCOPE,
    REMOVED,
    Array,
    Base,
    CType,
    Declared,
    Enum,
    Image,
    Member,
    Qualified,
    Section,
    Struct,
    Typedef,
    Unsupported,
    Variable,
)
from ddd.toolbox.checked import POLICY
from ddd.toolbox.findings import FINDINGS, place, report
from ddd.toolbox.from_elf import (
    DEFAULT_SECTIONS,
    IDENTITY_CLAIMED,
    NOT_INFERRED,
    VALUE_BLOCKS,
    Description,
    _unclaimed_type,
    describe,
    document_text,
)
from ddd.toolbox.mapping import Mapper, Shape, Typed, datatype_of, described, shape_of
from ddd.toolbox.selection import Wanted, select, wanted
from ddd.toolbox.values import UnstatableValueError, initial_value, shortest_float32

U8 = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
DATA = Section(".data", 0x100, 0x100, 0)


def image(
    *variables: Variable,
    sections: tuple[Section, ...] = (DATA,),
    contents: bytes = bytes(0x100),
    symbols: frozenset[str] = frozenset(),
    objects: frozenset[tuple[str, int]] | None = None,
    local_objects: frozenset[tuple[str, int]] = frozenset(),
    byte_order: Literal["little", "big"] = "little",
    machine: int | None = None,
    flags: int = 0,
    object_sizes: dict[tuple[str, int], int] | None = None,
    object_sections: dict[tuple[str, int], int | str] | None = None,
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
        byte_order,
        variables,
        sections,
        symbols,
        contents,
        objects,
        local_objects,
        machine,
        flags,
        object_sizes or {},
        object_sections or {},
    )


def stored(
    name: str,
    ctype: CType = U8,
    *,
    unit: str = "unit.c",
    address: int | None = 0x100,
    line: int | None = None,
    missing: str = "",
    external: bool = True,
    alignment: int | None = None,
) -> Variable:
    declared = Declared(unit, line) if line is not None else None
    return Variable(name, unit, ctype, declared, address, missing, external, alignment)


def found(bag: DiagnosticBag) -> list[tuple[str, Severity, str]]:
    return [(d.check, d.severity, d.message) for d in bag.sorted]


def chosen(img: Image, *arguments: str, bag: DiagnosticBag | None = None) -> list[str]:
    # Not `bag or DiagnosticBag()`: a bag has a length, so an empty one is false, and the
    # findings would go into a bag nobody reads.
    if bag is None:
        bag = DiagnosticBag()
    return [v.name for v in select(img, [wanted(a) for a in arguments], bag)]


class TestFindings:
    def test_no_finding_of_the_tool_is_a_check_of_the_catalogue(self) -> None:
        assert not set(FINDINGS) & set(CHECKS)

    @pytest.mark.parametrize(("check", "severity"), sorted(FINDINGS.items()))
    def test_a_finding_goes_in_with_the_severity_the_table_gives_it(
        self, check: str, severity: Severity
    ) -> None:
        bag = DiagnosticBag()
        report(bag, check, "a sentence", Location(Path("main.c"), line=3))
        assert found(bag) == [(check, severity, "a sentence")]

    def test_a_finding_about_a_declaration_is_shown_at_it(self) -> None:
        assert place(image(), Declared("main.c", 3)) == Location(Path("main.c"), line=3)

    def test_a_finding_about_what_dwarf_places_nowhere_is_shown_at_the_image(self) -> None:
        assert place(image(), None) == where(Path("hand.elf"))


class TestWanted:
    def test_a_name_is_matched_exactly(self) -> None:
        assert wanted("Cal_Gain") == Wanted("Cal_Gain", None, "Cal_Gain", False)

    def test_a_unit_narrows_a_glob(self) -> None:
        assert wanted("cal.c:Cal_*") == Wanted("cal.c:Cal_*", "cal.c", "Cal_*", True)

    def test_a_unit_keeps_its_drive_letter(self) -> None:
        assert wanted("C:/src/cal.c:Gain") == Wanted(
            "C:/src/cal.c:Gain", "C:/src/cal.c", "Gain", False
        )

    @pytest.mark.parametrize("pattern", ["Cal_?", "Tab[12]", "*"])
    def test_every_glob_character_makes_a_glob(self, pattern: str) -> None:
        assert wanted(pattern).glob

    def test_a_unit_without_a_name_is_refused(self) -> None:
        with pytest.raises(ValueError) as refused:
            wanted("cal.c:")
        assert str(refused.value) == (
            "'cal.c:' names no variable: give a name or a pattern after the unit"
        )

    def test_a_colon_without_a_unit_is_refused(self) -> None:
        with pytest.raises(ValueError) as refused:
            wanted(":Gain")
        assert str(refused.value) == "':Gain' names no unit before its colon"


class TestSelect:
    def test_arguments_keep_their_order_a_glob_its_names_and_each_variable_comes_once(
        self,
    ) -> None:
        img = image(stored("Zeta"), stored("Alpha"), stored("Beta"))
        assert chosen(img, "Zeta", "*a", "Beta") == ["Zeta", "Alpha", "Beta"]

    def test_a_name_nothing_defines_is_missing(self) -> None:
        bag = DiagnosticBag()
        assert chosen(image(stored("Other")), "Gain", bag=bag) == []
        assert found(bag) == [
            (
                "elf-symbol-missing",
                Severity.ERROR,
                "the image's debug information holds no variable named 'Gain'",
            )
        ]
        assert bag.sorted[0].location == where(Path("hand.elf"))

    def test_a_name_only_the_symbol_table_holds_says_how_that_happens(self) -> None:
        bag = DiagnosticBag()
        chosen(image(symbols=frozenset({"Gain"})), "Gain", bag=bag)
        assert found(bag)[0][2] == (
            "the image's debug information holds no variable named 'Gain'; the symbol table "
            "holds it, so the unit defining it was built without debug information (-g)"
        )

    def test_a_glob_matching_nothing_is_missing_too(self) -> None:
        bag = DiagnosticBag()
        chosen(image(stored("Other")), "cal.c:Cal_*", bag=bag)
        assert found(bag) == [
            (
                "elf-symbol-missing",
                Severity.ERROR,
                "no variable of the image's debug information matches 'Cal_*' in unit 'cal.c'",
            )
        ]

    def test_a_unit_is_matched_whole_or_by_its_last_components(self) -> None:
        img = image(
            stored("Gain", unit="src/app/cal.c"),
            stored("Gain", unit="src/app/xcal.c"),
            stored("Rate", unit="src\\app\\cal.c"),
            stored("Mode", unit="cal.c"),
        )
        picked = select(img, [wanted("cal.c:*")], DiagnosticBag())
        assert [(v.name, v.unit) for v in picked] == [
            ("Gain", "src/app/cal.c"),
            ("Mode", "cal.c"),
            ("Rate", "src\\app\\cal.c"),
        ]

    def test_a_name_two_units_define_is_ambiguous_once_however_often_it_is_asked_for(
        self,
    ) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Twin", unit="unit_a.c", line=9, address=0x100),
            stored("Twin", unit="unit_b.c", line=8, address=0x102),
            stored("Tweed"),
        )
        assert chosen(img, "Tw*", "Twin", bag=bag) == ["Tweed"]
        (diagnostic,) = bag.sorted
        assert (diagnostic.check, diagnostic.message) == (
            "elf-symbol-ambiguous",
            "'Twin' names a variable in 2 units, 'unit_a.c', 'unit_b.c': prefix it with one, "
            "as 'unit_a.c:Twin'",
        )
        assert diagnostic.location == Location(Path("unit_a.c"), line=9)
        assert diagnostic.notes == (
            ("defined in 'unit_a.c'", Location(Path("unit_a.c"), line=9)),
            ("defined in 'unit_b.c'", Location(Path("unit_b.c"), line=8)),
        )

    def test_its_unit_resolves_an_ambiguous_name(self) -> None:
        img = image(
            stored("Twin", unit="unit_a.c", address=0x100),
            stored("Twin", unit="unit_b.c", address=0x102),
        )
        assert chosen(img, "unit_b.c:Twin") == ["Twin"]

    def test_a_variable_without_storage_is_reported_once_with_its_reason(self) -> None:
        bag = DiagnosticBag()
        img = image(stored("Tls", address=None, missing="it is thread-local", line=4))
        assert chosen(img, "Tls", "T*", bag=bag) == []
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "'Tls' has no address in the image: it is thread-local",
            )
        ]
        assert bag.sorted[0].location == Location(Path("unit.c"), line=4)

    def test_one_name_at_one_address_is_one_variable_whichever_units_describe_it(self) -> None:
        """-fcommon, or the common attribute, makes a tentative definition in two units one
        variable, which the DWARF of each unit describes: it is no ambiguity, and it is taken
        from the first unit by name, printed once however it is asked for."""
        bag = DiagnosticBag()
        img = image(
            stored("Shared", unit="unit_b.c", address=0x104),
            stored("Shared", unit="unit_a.c", address=0x104),
        )
        picked = select(img, [wanted("Shared"), wanted("unit_b.c:Shared"), wanted("S*")], bag)
        assert [(v.name, v.unit) for v in picked] == [("Shared", "unit_a.c")]
        assert found(bag) == []

    def test_its_unit_still_takes_one_of_a_name_at_one_address(self) -> None:
        img = image(
            stored("Shared", unit="unit_a.c", address=0x104),
            stored("Shared", unit="unit_b.c", address=0x104),
        )
        picked = select(img, [wanted("unit_b.c:Shared")], DiagnosticBag())
        assert [(v.name, v.unit) for v in picked] == [("Shared", "unit_b.c")]

    def test_a_name_at_two_addresses_is_ambiguous_listing_one_unit_per_address(self) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Twin", unit="unit_a.c", address=0x104),
            stored("Twin", unit="unit_b.c", address=0x104),
            stored("Twin", unit="unit_c.c", address=0x108),
        )
        assert chosen(img, "Twin", bag=bag) == []
        assert [(d.check, d.message) for d in bag.sorted] == [
            (
                "elf-symbol-ambiguous",
                "'Twin' names a variable in 2 units, 'unit_a.c', 'unit_c.c': prefix it with "
                "one, as 'unit_a.c:Twin'",
            )
        ]

    def test_a_name_with_storage_in_one_unit_and_none_in_another_is_ambiguous(self) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Gain", unit="unit_a.c", address=0x104),
            stored("Gain", unit="unit_b.c", address=None, missing="it is thread-local"),
        )
        assert chosen(img, "Gain", bag=bag) == []
        assert [d.check for d in bag.sorted] == ["elf-symbol-ambiguous"]

    def test_a_name_every_unit_left_without_storage_is_said_so_and_not_ambiguous(self) -> None:
        """A header's static const each unit folded has no address anywhere: prefixing a unit
        only earns elf-no-storage, so the name is reported as what it is, once."""
        bag = DiagnosticBag()
        img = image(
            stored("Limit", unit="unit_a.c", address=None, missing=FOLDED, line=3),
            stored("Limit", unit="unit_b.c", address=None, missing=FOLDED, line=3),
        )
        assert chosen(img, "Limit", "unit_a.c:Limit", bag=bag) == []
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                f"'Limit' has no address in the image, in any of its 2 units, 'unit_a.c', "
                f"'unit_b.c': {FOLDED}",
            )
        ]
        assert bag.sorted[0].location == Location(Path("unit_a.c"), line=3)

    def test_the_reasons_of_units_that_differ_are_each_stated_once(self) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Limit", unit="unit_a.c", address=None, missing=FOLDED),
            stored("Limit", unit="unit_b.c", address=None, missing=REMOVED),
            stored("Limit", unit="unit_c.c", address=None, missing=FOLDED),
        )
        assert chosen(img, "Limit", bag=bag) == []
        assert [d.message for d in bag.sorted] == [
            f"'Limit' has no address in the image, in any of its 3 units, 'unit_a.c', "
            f"'unit_b.c', 'unit_c.c': {FOLDED}; {REMOVED}"
        ]

    def test_the_prefix_an_ambiguity_offers_is_of_a_unit_that_has_storage(self) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Gain", unit="unit_a.c", address=None, missing=FOLDED),
            stored("Gain", unit="unit_b.c", address=0x104),
        )
        assert chosen(img, "Gain", bag=bag) == []
        assert [d.message for d in bag.sorted] == [
            "'Gain' names a variable in 2 units, 'unit_a.c', 'unit_b.c': prefix it with one, "
            "as 'unit_b.c:Gain'"
        ]
        assert chosen(img, "unit_b.c:Gain") == ["Gain"]

    def test_a_global_only_declared_where_the_symbol_table_holds_it_is_not_defined_nowhere(
        self,
    ) -> None:
        """Defined in assembly, or in a unit built without -g: the symbol table holds it."""
        bag = DiagnosticBag()
        img = image(
            stored("Asm_Counter", address=None, missing=DECLARED_ONLY, line=5),
            symbols=frozenset({"Asm_Counter"}),
        )
        assert chosen(img, "Asm_Counter", bag=bag) == []
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "'Asm_Counter' has no address in the image: its debug information only "
                "declares it, and the symbol table holds it, defined where the debug "
                "information does not describe it, in assembly or in a unit built without -g",
            )
        ]

    def test_a_global_declared_and_held_by_no_symbol_is_defined_nowhere(self) -> None:
        bag = DiagnosticBag()
        img = image(stored("Lost", address=None, missing=DECLARED_ONLY))
        assert chosen(img, "Lost", bag=bag) == []
        assert [d.message for d in bag.sorted] == [
            f"'Lost' has no address in the image: {DECLARED_ONLY}"
        ]

    @pytest.mark.parametrize("unit", ["src\\app\\a.c", "app\\a.c", "src/app/a.c", "a.c"])
    def test_a_unit_spelled_with_backslashes_matches_as_dwarf_recorded_it(self, unit: str) -> None:
        """A Windows build records its units with backslashes, and the ambiguity's own hint
        repeats the unit as recorded: 'src\\app\\a.c:Twin' must take the variable it names."""
        img = image(
            stored("Twin", unit="src\\app\\a.c", address=0x104),
            stored("Twin", unit="src\\app\\b.c", address=0x108),
        )
        picked = select(img, [wanted(f"{unit}:Twin")], DiagnosticBag())
        assert [(v.name, v.unit) for v in picked] == [("Twin", "src\\app\\a.c")]

    def test_the_g_hint_is_left_out_where_another_unit_s_dwarf_holds_the_name(self) -> None:
        """The symbol table holds the name and so does the DWARF of cal.c: asked for in
        other.c, the variable is missing there, and no unit lacks debug information."""
        bag = DiagnosticBag()
        img = image(stored("Gain", unit="cal.c"), symbols=frozenset({"Gain"}))
        assert chosen(img, "other.c:Gain", bag=bag) == []
        assert found(bag) == [
            (
                "elf-symbol-missing",
                Severity.ERROR,
                "the image's debug information holds no variable named 'Gain' in unit 'other.c'",
            )
        ]


U16 = Base("short unsigned int", DW_ATE_UNSIGNED, 2)
U32 = Base("unsigned int", DW_ATE_UNSIGNED, 4)
U64 = Base("long unsigned int", DW_ATE_UNSIGNED, 8)
S32 = Base("int", DW_ATE_SIGNED, 4)
F32 = Base("float", DW_ATE_FLOAT, 4)
BOOL = Base("_Bool", DW_ATE_BOOLEAN, 1)
LONG_DOUBLE = Base("long double", DW_ATE_FLOAT, 16)
IDENTITY = {"kind": "identity"}
STATE = Enum("State_e", 4, False, (("OFF", 0), ("ON", 1)), Declared("main.c", 2))
PAIR = Struct(
    "Pair_s",
    2,
    (Member("a", U8, 0), Member("b", U8, 8)),
    declared_at=Declared("main.c", 10),
)
PAIR_ENTRY = {
    "type": "struct",
    "name": "Pair_s",
    "members": [
        {"name": "a", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
        {"name": "b", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
    ],
}


def mapped(
    ctype: CType, name: str = "v", *, bag: DiagnosticBag | None = None, mapper: Mapper | None = None
) -> Typed | None:
    if bag is None:
        bag = DiagnosticBag()
    if mapper is None:
        mapper = Mapper(image(), bag)
    return mapper.typed(stored(name, ctype, line=5))


def structure(tag: str | None, *members: Member, size: int = 4, **extra: Any) -> Struct:
    return Struct(tag, size, members, **extra)


class TestShapes:
    def test_qualifiers_and_dimensions_are_collected_on_the_way_to_the_core(self) -> None:
        ctype = Qualified(Typedef("Row_t", Array(Qualified(U8, const=True), (2, 3))), volatile=True)
        assert shape_of(ctype) == Shape(U8, (2, 3), const=True, volatile=True, name=None)

    def test_the_name_is_the_typedef_closest_to_the_core(self) -> None:
        assert shape_of(Typedef("Alias_t", Typedef("Pair_t", PAIR))).name == "Pair_t"

    @pytest.mark.parametrize(
        ("core", "datatype"),
        [
            (BOOL, "boolean"),
            (Base("_Bool", DW_ATE_BOOLEAN, 2), None),
            (Base("signed char", DW_ATE_SIGNED_CHAR, 1), "sint8"),
            (Base("long long unsigned int", DW_ATE_UNSIGNED, 8), "uint64"),
            (F32, "float32"),
            (Base("double", DW_ATE_FLOAT, 8), "float64"),
            (LONG_DOUBLE, None),
            (Base("complex float", DW_ATE_COMPLEX_FLOAT, 8), None),
            (Base("char8_t", 0x10, 1), None),
            (Enum(None, 2, True, ()), "sint16"),
            (Enum(None, 3, False, ()), None),
        ],
    )
    def test_a_datatype_holds_a_base_type_or_an_enum_of_its_encoding_and_size(
        self, core: Base | Enum, datatype: str | None
    ) -> None:
        assert datatype_of(core) == datatype

    @pytest.mark.parametrize(
        ("core", "words"),
        [
            (LONG_DOUBLE, "'long double', a floating point number of 16 bytes"),
            (Base("char8_t", 0x10, 1), "'char8_t', a value of DWARF encoding 0x10 of 1 byte"),
            (Enum(None, 3, False, ()), "an enum of 3 bytes"),
        ],
    )
    def test_what_no_datatype_holds_is_said_in_words(self, core: Base | Enum, words: str) -> None:
        assert described(core) == words

    @pytest.mark.parametrize(
        ("core", "datatype"),
        [(S32, "sint32"), (Base("long long int", DW_ATE_SIGNED, 8), "sint64")],
    )
    def test_plain_signed_ints_have_their_own_row_beside_signed_char(
        self, core: Base, datatype: str | None
    ) -> None:
        """Every signed case above is ``DW_ATE_SIGNED_CHAR``; ``S32`` names the encoding the
        brief defines but never spends. Dropping ``_FAMILIES[DW_ATE_SIGNED]`` or either of
        ``_DATATYPES``'s ``("signed", 4)``/``("signed", 8)`` rows survives every test above."""
        assert datatype_of(core) == datatype

    @pytest.mark.parametrize(
        ("core", "words"),
        [
            (BOOL, "'_Bool', a boolean of 1 byte"),
            (
                Base("complex float", DW_ATE_COMPLEX_FLOAT, 8),
                "'complex float', a complex number of 8 bytes",
            ),
            (S32, "'int', a signed integer of 4 bytes"),
            (
                Base("signed char", DW_ATE_SIGNED_CHAR, 1),
                "'signed char', a signed character of 1 byte",
            ),
            (U16, "'short unsigned int', an unsigned integer of 2 bytes"),
            (U8, "'unsigned char', an unsigned character of 1 byte"),
        ],
    )
    def test_every_encoding_datatype_of_can_miss_is_worded_not_only_float(
        self, core: Base, words: str
    ) -> None:
        """Only ``DW_ATE_FLOAT`` is worded above, through ``LONG_DOUBLE``: the other six rows
        of ``_ENCODED_AS`` are never rendered by a named assertion otherwise."""
        assert described(core) == words


class TestScalars:
    def test_a_variable_is_a_measurement_of_its_datatype_under_the_identity(self) -> None:
        assert mapped(U8) == Typed(
            "measurement", "uint8", None, (), IDENTITY, False, frozenset(), 1
        )

    @pytest.mark.parametrize(
        ("ctype", "kind", "dimensions", "volatile"),
        [
            (Qualified(U16, const=True), "parameter", (), False),
            (Array(Qualified(U16, const=True), (4,)), "value_block", (4,), False),
            (Array(U16, (2, 3)), "measurement", (2, 3), False),
            (Qualified(U16, volatile=True), "measurement", (), True),
            (Qualified(Qualified(U16, volatile=True), const=True), "parameter", (), True),
        ],
    )
    def test_const_decides_the_kind_and_the_shape_the_calibration_kind(
        self, ctype: CType, kind: str, dimensions: tuple[int, ...], volatile: bool
    ) -> None:
        result = mapped(ctype)
        assert result is not None
        assert (result.kind, result.dimensions, result.volatile, result.element_size) == (
            kind,
            dimensions,
            volatile,
            2,
        )

    def test_an_enum_is_its_datatype_under_an_enum_conversion_named_by_its_typedef(self) -> None:
        result = mapped(Typedef("State_t", STATE))
        assert result is not None
        assert (result.datatype, result.conversion, result.reaches) == (
            "uint32",
            {"kind": "enum", "name": "State_t", "enumerators": {"OFF": 0, "ON": 1}},
            frozenset({"State_t"}),
        )

    def test_an_enum_without_a_typedef_is_named_by_its_tag(self) -> None:
        result = mapped(STATE)
        assert result is not None
        assert result.conversion == {
            "kind": "enum",
            "name": "State_e",
            "enumerators": {"OFF": 0, "ON": 1},
        }

    def test_an_anonymous_enum_is_named_after_the_variable_and_says_so(self) -> None:
        bag = DiagnosticBag()
        result = mapped(Enum(None, 1, False, (("A", 1),), Declared("main.c", 3)), "Mode", bag=bag)
        assert result is not None
        assert result.conversion == {"kind": "enum", "name": "Mode_t", "enumerators": {"A": 1}}
        assert found(bag) == [
            (
                "elf-name-synthesized",
                Severity.WARNING,
                "an anonymous enum is named 'Mode_t', after the first thing that reaches it; "
                "rename it if the source has a better name",
            )
        ]
        assert bag.sorted[0].location == Location(Path("main.c"), line=3)

    @pytest.mark.parametrize(
        ("ctype", "message"),
        [
            (Unsupported("a pointer"), "'v' is a pointer, which DDD cannot state"),
            (
                LONG_DOUBLE,
                "'v' is 'long double', a floating point number of 16 bytes, which DDD cannot state",
            ),
            (
                Enum(None, 3, False, (("A", 1),)),
                "'v' is an enum of 3 bytes, which DDD cannot state",
            ),
            (
                Array(Qualified(PAIR, const=True), (2,)),
                "'v' is a const array of structures, which DDD cannot state: a parameter has no "
                "dimensions, and a value block holds no structure",
            ),
        ],
    )
    def test_what_ddd_cannot_state_is_refused_at_the_variable(
        self, ctype: CType, message: str
    ) -> None:
        bag = DiagnosticBag()
        assert mapped(ctype, bag=bag) is None
        assert found(bag) == [("elf-type-unsupported", Severity.ERROR, message)]
        assert bag.sorted[0].location == Location(Path("unit.c"), line=5)


class TestStructures:
    def test_a_structure_is_a_typename_and_one_entry_of_types(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        assert mapped(PAIR, mapper=mapper) == Typed(
            "measurement", None, "Pair_s", (), None, False, frozenset({"Pair_s"}), 2
        )
        assert mapper.types({"Pair_s"}) == [PAIR_ENTRY]

    @pytest.mark.parametrize(
        ("ctype", "kind", "dimensions"),
        [(Qualified(PAIR, const=True), "parameter", ()), (Array(PAIR, (3,)), "measurement", (3,))],
    )
    def test_a_structured_object_is_a_measurement_or_a_parameter(
        self, ctype: CType, kind: str, dimensions: tuple[int, ...]
    ) -> None:
        result = mapped(ctype)
        assert result is not None
        assert (result.kind, result.typename, result.dimensions) == (kind, "Pair_s", dimensions)

    def test_a_structure_is_named_by_the_typedef_closest_to_it(self) -> None:
        result = mapped(Typedef("Alias_t", Typedef("Pair_t", PAIR)))
        assert result is not None
        assert result.typename == "Pair_t"

    def test_an_anonymous_structure_is_named_once_after_the_first_variable_reaching_it(
        self,
    ) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        anonymous = structure(None, Member("x", U8, 0), size=1, declared_at=Declared("main.c", 7))
        first = mapped(anonymous, "First", mapper=mapper)
        second = mapped(anonymous, "Second", mapper=mapper)
        assert first is not None
        assert second is not None
        assert (first.typename, second.typename) == ("First_t", "First_t")
        assert found(bag) == [
            (
                "elf-name-synthesized",
                Severity.WARNING,
                "an anonymous structure is named 'First_t', after the first thing that reaches "
                "it; rename it if the source has a better name",
            )
        ]

    def test_members_are_values_arrays_nested_structures_enums_and_bitfields(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        inner = structure(None, Member("lo", U8, 0), Member("hi", U8, 8), size=2)
        outer = structure(
            "Outer_s",
            Member("raw", Array(U16, (4,)), 0),
            Member("pair", inner, 64),
            Member("pairs", Array(inner, (2,)), 80),
            Member("state", Typedef("State_t", STATE), 128),
            Member("flags", U8, 160, 3),
            Member("mode", Typedef("State_t", STATE), 163, 2),
            Member("ready", BOOL, 165, 1, declared_at=Declared("main.c", 30)),
            size=24,
        )
        result = mapped(outer, mapper=mapper)
        assert result is not None
        assert result.reaches == frozenset({"Outer_s", "Outer_s_pair_t", "State_t"})
        state = {"kind": "enum", "name": "State_t", "enumerators": {"OFF": 0, "ON": 1}}
        assert mapper.types(result.reaches) == [
            {
                "type": "struct",
                "name": "Outer_s_pair_t",
                "members": [
                    {"name": "lo", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
                    {"name": "hi", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
                ],
            },
            {
                "type": "struct",
                "name": "Outer_s",
                "members": [
                    {
                        "name": "raw",
                        "member": "value",
                        "datatype": "uint16",
                        "conversion": IDENTITY,
                        "dimensions": [4],
                    },
                    {"name": "pair", "member": "value", "typename": "Outer_s_pair_t"},
                    {
                        "name": "pairs",
                        "member": "value",
                        "typename": "Outer_s_pair_t",
                        "dimensions": [2],
                    },
                    {"name": "state", "member": "value", "datatype": "uint32", "conversion": state},
                    {
                        "name": "flags",
                        "member": "bits",
                        "datatype": "uint8",
                        "conversion": IDENTITY,
                        "bits": 3,
                    },
                    {
                        "name": "mode",
                        "member": "bits",
                        "datatype": "uint32",
                        "conversion": state,
                        "bits": 2,
                    },
                    {
                        "name": "ready",
                        "member": "bits",
                        "datatype": "uint8",
                        "conversion": IDENTITY,
                        "bits": 1,
                    },
                ],
            },
        ]
        assert [(check, severity) for check, severity, _ in found(bag)] == [
            ("elf-name-synthesized", Severity.WARNING),
            ("elf-boolean-bitfield", Severity.INFO),
        ]
        assert found(bag)[1][2] == (
            "'Outer_s.ready' is a _Bool bitfield, described as a uint8 one of the same width: DDD "
            "refuses a boolean bitfield"
        )

    @pytest.mark.parametrize(
        ("member", "path", "what"),
        [
            (Member("ptr", Unsupported("a pointer"), 0), "Holder_s.ptr", "a pointer"),
            (Member(None, U8, 0), "Holder_s.<anonymous>", "an anonymous member"),
            (
                Member("far", LONG_DOUBLE, 0),
                "Holder_s.far",
                "'long double', a floating point number of 16 bytes",
            ),
            (Member("packed", PAIR, 0, 3), "Holder_s.packed", "a bitfield of a structure"),
            (Member("wide", Enum(None, 3, False, ()), 0, 2), "Holder_s.wide", "an enum of 3 bytes"),
        ],
    )
    def test_a_member_ddd_cannot_state_refuses_every_variable_reaching_it(
        self, member: Member, path: str, what: str
    ) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        declared = Member(
            member.name,
            member.type,
            member.bit_offset,
            member.bit_size,
            declared_at=Declared("main.c", 21),
        )
        holder = structure("Holder_s", declared)
        assert mapped(holder, mapper=mapper) is None
        assert mapped(Array(holder, (2,)), "w", mapper=mapper) is None
        errors = [d for d in bag.sorted if d.check == "elf-type-unsupported"]
        assert [d.message for d in errors] == [
            f"'{name}' cannot be described: '{path}' is {what}, which DDD cannot state"
            for name in ("v", "w")
        ]
        assert errors[0].notes == (
            (f"'{path}' is declared here", Location(Path("main.c"), line=21)),
        )

    def test_a_refusal_deep_inside_a_nested_structure_names_the_member_it_occurs_at(self) -> None:
        bag = DiagnosticBag()
        inner = structure("Inner_s", Member("ptr", Unsupported("a pointer"), 0))
        assert mapped(structure("Outer_s", Member("inner", inner, 0)), bag=bag) is None
        assert found(bag) == [
            (
                "elf-type-unsupported",
                Severity.ERROR,
                "'v' cannot be described: 'Inner_s.ptr' is a pointer, which DDD cannot state",
            )
        ]

    def test_a_synthesised_name_that_is_taken_is_named_once_and_conflicts(self) -> None:
        """A variable ``S_m`` of one anonymous structure and a member ``m`` of ``S`` of
        another both synthesise ``S_m_t``: the name is announced once, and the two ways it is
        defined are a conflict, which refuses both (Task 7)."""
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        mapped(structure(None, Member("x", U8, 0), size=1), "S_m", mapper=mapper)
        mapped(
            structure("S", Member("m", structure(None, Member("y", U16, 0), size=2), 0)),
            mapper=mapper,
        )
        assert [check for check, _, _ in found(bag)] == ["elf-name-synthesized"]
        assert set(mapper.conflicts()) == {"S_m_t"}

    def test_a_qualified_member_says_ddd_qualifies_whole_objects(self) -> None:
        bag = DiagnosticBag()
        holder = structure(
            "Q_s",
            Member("v", Qualified(U8, volatile=True), 0),
            Member("c", Qualified(U8, const=True), 8),
            Member("cv", Qualified(Qualified(U8, volatile=True), const=True), 16),
        )
        mapped(holder, bag=bag)
        assert [message for _, _, message in found(bag)] == [
            "'Q_s.v' is volatile in C, which DDD cannot state of a member: DDD qualifies whole "
            "objects",
            "'Q_s.c' is const in C, which DDD cannot state of a member: DDD qualifies whole "
            "objects",
            "'Q_s.cv' is const volatile in C, which DDD cannot state of a member: DDD qualifies "
            "whole objects",
        ]

    def test_one_structure_reached_by_two_variables_is_one_entry_described_once(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        holder = structure("Q_s", Member("v", Qualified(U8, volatile=True), 0))
        mapped(holder, "a", mapper=mapper)
        mapped(holder, "b", mapper=mapper)
        assert len(mapper.types({"Q_s"})) == 1
        assert len(found(bag)) == 1

    def test_one_name_described_two_ways_is_a_conflict_naming_both_declarations(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        first = structure(
            "Clash_s", Member("a", U8, 0), size=1, declared_at=Declared("unit_a.c", 11)
        )
        second = structure(
            "Clash_s",
            Member("a", U16, 0),
            Member("b", U16, 16),
            declared_at=Declared("unit_b.c", 10),
        )
        mapped(first, "A", mapper=mapper)
        mapped(second, "B", mapper=mapper)
        mapped(first, "C", mapper=mapper)
        assert mapper.conflicts() == {
            "Clash_s": [Declared("unit_a.c", 11), Declared("unit_b.c", 10)]
        }

    def test_two_enums_under_one_name_with_different_enumerators_conflict(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        mapped(Enum("Mode_e", 4, False, (("A", 1),)), "a", mapper=mapper)
        mapped(Enum("Mode_e", 4, False, (("A", 2),)), "b", mapper=mapper)
        assert set(mapper.conflicts()) == {"Mode_e"}

        # The same enumerators, only reordered, are not proven identical either: comparing
        # by their serialised text (rather than as dicts, which `==` would call equal
        # whatever order their keys came in) is what tells the two apart.
        reordered = Mapper(image(), DiagnosticBag())
        mapped(Enum("Pair_e", 4, False, (("A", 1), ("B", 2))), "c", mapper=reordered)
        mapped(Enum("Pair_e", 4, False, (("B", 2), ("A", 1))), "d", mapper=reordered)
        assert set(reordered.conflicts()) == {"Pair_e"}

    def test_types_lists_only_the_structures_it_is_asked_for(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        mapped(PAIR, mapper=mapper)
        mapped(Typedef("State_t", STATE), mapper=mapper)
        assert mapper.types({"State_t"}) == []
        assert mapper.types({"Pair_s", "State_t"}) == [PAIR_ENTRY]


class TestLayout:
    def layout(self, *members: Member, **extra: Any) -> list[str]:
        bag = DiagnosticBag()
        mapped(structure("L_s", *members, **extra), bag=bag)
        return [message for _, _, message in found(bag)]

    def test_an_alignment_the_source_states_is_said_not_to_be_carried(self) -> None:
        messages = self.layout(Member("x", U8, 0, alignment=8), alignment=8, size=8)
        assert messages == [
            "'L_s' is aligned to 8 bytes in C, which DDD cannot state: the structure DDD "
            "generates is aligned as its members are",
            "'L_s.x' is aligned to 8 bytes in C, which DDD cannot state",
        ]

    def test_bits_a_bitfield_would_have_fit_into_are_a_gap(self) -> None:
        messages = self.layout(Member("a", U8, 0, 2), Member("b", U8, 5, 2), Member("c", U16, 7, 9))
        assert messages == [
            "'L_s.b' starts at bit 5 although it fits at bit 2: an unnamed or zero width "
            "bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            "starts it at bit 2"
        ]

    def test_bits_the_rule_itself_skips_are_no_gap(self) -> None:
        assert self.layout(Member("a", U8, 0, 7), Member("b", U8, 8, 2)) == []

    def test_a_gap_before_the_first_bitfield_counts_from_the_start(self) -> None:
        messages = self.layout(Member("a", U8, 3, 2))
        assert messages == [
            "'L_s.a' starts at bit 3 although it fits at bit 0: an unnamed or zero width "
            "bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            "starts it at bit 0"
        ]

    def test_a_gap_after_a_value_member_counts_from_its_end(self) -> None:
        messages = self.layout(Member("x", U8, 0), Member("y", U8, 12, 2))
        assert messages == [
            "'L_s.y' starts at bit 12 although it fits at bit 8: an unnamed or zero width "
            "bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            "starts it at bit 8"
        ]

    def test_a_member_whose_offset_is_unknown_leaves_the_next_unjudged(self) -> None:
        assert self.layout(Member("a", U8, None, 2), Member("b", U8, 5, 2)) == []


X86_64 = 62
I386 = 3
ARM = 40
RISCV = 243
AAPCS = 0x5000200


class TestAnAlignmentTheSourceStates:
    """``elf-alignment`` on a variable, and on a GNU vector wherever one is a variable or a
    member: what DDD's generated C would align differently, and cannot be told to."""

    VECTOR = Array(F32, (4,), vector=True)

    def said(
        self, variable: Variable, *, machine: int | None = X86_64, flags: int = 0
    ) -> list[tuple[str, Severity, str]]:
        bag = DiagnosticBag()
        Mapper(image(machine=machine, flags=flags), bag).typed(variable)
        return [item for item in found(bag) if item[0] == "elf-alignment"]

    def test_an_alignment_stated_on_a_variable_is_reported_against_the_one_generated(self) -> None:
        assert self.said(stored("Buf", U32, line=5, alignment=64)) == [
            (
                "elf-alignment",
                Severity.WARNING,
                "'Buf' is aligned to 64 bytes in C, where the variable DDD generates is aligned "
                "to 4: DDD cannot state an alignment on a variable",
            )
        ]

    def test_the_alignment_generated_follows_the_target_s_cap(self) -> None:
        (item,) = self.said(stored("Wide", U64, line=5, alignment=64), machine=I386)
        assert "aligned to 4: DDD" in item[2]

    def test_a_structure_variable_is_generated_as_aligned_as_its_members_are(self) -> None:
        pair = structure("Pair_s", Member("a", U8, 0), Member("b", U32, 32), size=8)
        (item,) = self.said(stored("Pair", pair, line=5, alignment=32))
        assert (
            "aligned to 32 bytes in C, where the variable DDD generates is aligned to 4:"
            in (item[2])
        )

    def test_the_alignment_generated_is_left_out_where_it_cannot_be_known(self) -> None:
        (item,) = self.said(stored("Buf", U32, line=5, alignment=64), machine=None)
        assert item[2] == (
            "'Buf' is aligned to 64 bytes in C, which DDD cannot state: the variable DDD "
            "generates is aligned as its type is"
        )

    def test_an_alignment_the_generated_one_already_has_is_not_reported(self) -> None:
        assert self.said(stored("Same", U32, line=5, alignment=4)) == []

    def test_a_variable_of_its_natural_alignment_is_not_reported(self) -> None:
        assert self.said(stored("Plain", U32, line=5)) == []

    def test_a_variable_refused_is_not_also_reported_aligned(self) -> None:
        assert self.said(stored("Gone", Unsupported("a pointer"), line=5, alignment=64)) == []

    def test_a_gnu_vector_is_reported_where_it_is_a_variable(self) -> None:
        assert self.said(stored("Lanes", self.VECTOR, line=5)) == [
            (
                "elf-alignment",
                Severity.WARNING,
                "'Lanes' is a GNU vector of 16 bytes, which the target aligns as a whole, where "
                "the array of 4 byte elements DDD generates is aligned to 4: DDD cannot state "
                "an alignment on a variable",
            )
        ]

    def test_a_vector_is_reported_without_the_generated_alignment_where_it_is_unknown(self) -> None:
        (item,) = self.said(stored("Lanes", self.VECTOR, line=5), machine=None)
        assert item[2] == (
            "'Lanes' is a GNU vector of 16 bytes, which the target aligns as a whole, where the "
            "array of 4 byte elements DDD generates is aligned as its elements are: DDD cannot "
            "state an alignment on a variable"
        )

    def test_a_vector_is_found_under_a_typedef_a_qualifier_and_an_array(self) -> None:
        named = Qualified(Typedef("Vec4_t", self.VECTOR), const=True)
        assert len(self.said(stored("Named", named, line=5))) == 1
        assert len(self.said(stored("Several", Array(self.VECTOR, (2,)), line=5))) == 1

    def test_a_vector_of_one_element_is_aligned_as_its_element_is(self) -> None:
        assert self.said(stored("One", Array(U32, (1,), vector=True), line=5)) == []

    def test_an_array_that_is_no_vector_is_not_reported(self) -> None:
        assert self.said(stored("Plain", Array(F32, (4,)), line=5)) == []

    def test_a_stated_alignment_on_a_vector_is_reported_once_as_stated(self) -> None:
        (item,) = self.said(stored("Lanes", self.VECTOR, line=5, alignment=32))
        assert item[2].startswith("'Lanes' is aligned to 32 bytes in C, where")

    def test_a_vector_member_is_reported_with_the_structure_it_is_in(self) -> None:
        holder = structure("Holder_s", Member("tag", U8, 0), Member("lanes", self.VECTOR, 128))
        bag = DiagnosticBag()
        mapped(holder, bag=bag, mapper=Mapper(image(machine=X86_64), bag))
        assert [m for c, _, m in found(bag) if c == "elf-alignment"] == [
            "'Holder_s.lanes' is a GNU vector of 16 bytes, which the target aligns as a whole, "
            "where the array of 4 byte elements DDD generates is aligned to 4: DDD cannot "
            "state an alignment"
        ]

    def test_a_member_stating_an_alignment_and_a_vector_is_reported_once(self) -> None:
        holder = structure("Holder_s", Member("lanes", self.VECTOR, 0, alignment=32), size=32)
        bag = DiagnosticBag()
        mapped(holder, bag=bag, mapper=Mapper(image(machine=X86_64), bag))
        assert [m for c, _, m in found(bag) if c == "elf-alignment" and "lanes" in m] == [
            "'Holder_s.lanes' is aligned to 32 bytes in C, which DDD cannot state"
        ]


class TestWhereTheSourceLaidAStructureOutDifferently:
    """``elf-layout``: a member's offset, or the structure's size, where the generated C would
    put it elsewhere - packing, ``#pragma pack``, an unnamed or a zero width bitfield."""

    def layout(
        self,
        *members: Member,
        size: int,
        machine: int | None = X86_64,
        flags: int = 0,
        **extra: Any,
    ) -> list[tuple[str, Severity, str]]:
        bag = DiagnosticBag()
        mapper = Mapper(image(machine=machine, flags=flags), bag)
        mapped(structure("L_s", *members, size=size, **extra), bag=bag, mapper=mapper)
        return [item for item in found(bag) if item[0] in ("elf-layout", "elf-layout-unchecked")]

    def test_a_packed_structure_puts_its_member_where_the_generated_one_does_not(self) -> None:
        assert self.layout(Member("a", U8, 0), Member("b", U32, 8), size=5) == [
            (
                "elf-layout",
                Severity.WARNING,
                "'L_s.b' is at byte 1 in C, where the structure DDD generates puts it at byte 4: "
                "the source packed the structure, or left room with an unnamed or zero width "
                "bitfield, which DDD cannot state",
            )
        ]

    def test_pack_two_is_the_same_departure_at_another_offset(self) -> None:
        (only,) = self.layout(Member("a", U8, 0), Member("b", U32, 16), size=6)
        assert (
            "'L_s.b' is at byte 2 in C, where the structure DDD generates puts it at byte 4"
            in (only[2])
        )

    def test_only_the_size_departs_where_the_members_sit_as_generated(self) -> None:
        assert self.layout(Member("a", U32, 0), Member("b", U8, 32), size=5) == [
            (
                "elf-layout",
                Severity.WARNING,
                "'L_s' is 5 bytes in C, where the structure DDD generates is 8: the source "
                "packed, aligned or padded the structure, which DDD cannot state",
            )
        ]

    def test_an_unnamed_bitfield_moves_the_member_after_it(self) -> None:
        (only,) = self.layout(Member("a", U8, 8), size=2)
        assert (
            "'L_s.a' is at byte 1 in C, where the structure DDD generates puts it at byte 0"
            in (only[2])
        )

    def test_a_zero_width_bitfield_moves_the_member_after_it(self) -> None:
        (only,) = self.layout(Member("a", U8, 0), Member("b", U8, 32), size=5)
        assert (
            "'L_s.b' is at byte 4 in C, where the structure DDD generates puts it at byte 1"
            in (only[2])
        )

    def test_a_trailing_zero_width_bitfield_is_seen_in_the_size_alone(self) -> None:
        assert self.layout(Member("a", U8, 0, 2), size=4) == [
            (
                "elf-layout",
                Severity.WARNING,
                "'L_s' is 4 bytes in C, where the structure DDD generates is 1: the source "
                "packed, aligned or padded the structure, which DDD cannot state",
            )
        ]

    def test_a_bitfield_is_named_at_its_bit(self) -> None:
        (only,) = self.layout(Member("a", U8, 0, 7), Member("b", U8, 16, 2), size=4)
        assert (
            "'L_s.b' is at bit 16 in C, where the structure DDD generates puts it at bit 8"
            in (only[2])
        )

    def test_only_the_first_member_that_departs_is_named(self) -> None:
        assert (
            len(self.layout(Member("a", U8, 0), Member("b", U32, 8), Member("c", U8, 40), size=6))
            == 1
        )

    def test_a_bitfield_gives_the_structure_the_alignment_of_its_type(self) -> None:
        assert self.layout(Member("a", U32, 0, 3), size=4) == []

    def test_the_warning_is_shown_at_the_member_and_a_size_alone_at_the_structure(self) -> None:
        bag = DiagnosticBag()
        located = structure(
            "L_s",
            Member("a", U8, 0),
            Member("b", U32, 8, declared_at=Declared("main.c", 7)),
            size=5,
            declared_at=Declared("main.c", 5),
        )
        mapped(located, bag=bag, mapper=Mapper(image(machine=X86_64), bag))
        (member,) = [d for d in bag.sorted if d.check == "elf-layout"]
        assert member.location == Location(Path("main.c"), line=7)
        bag = DiagnosticBag()
        sized = structure(
            "L_s",
            Member("a", U32, 0, declared_at=Declared("main.c", 7)),
            Member("b", U8, 32, declared_at=Declared("main.c", 8)),
            size=5,
            declared_at=Declared("main.c", 5),
        )
        mapped(sized, bag=bag, mapper=Mapper(image(machine=X86_64), bag))
        (whole,) = [d for d in bag.sorted if d.check == "elf-layout"]
        assert whole.location == Location(Path("main.c"), line=5)
        bag = DiagnosticBag()
        undeclared = structure(
            "L_s",
            Member("a", U8, 0),
            Member("b", U32, 8),
            size=5,
            declared_at=Declared("main.c", 5),
        )
        mapped(undeclared, bag=bag, mapper=Mapper(image(machine=X86_64), bag))
        (fallen,) = [d for d in bag.sorted if d.check == "elf-layout"]
        assert fallen.location == Location(Path("main.c"), line=5)

    def test_a_natural_structure_is_not_warned(self) -> None:
        members = (
            Member("a", U8, 0),
            Member("b", U32, 32),
            Member("c", U8, 64, 3),
            Member("d", U16, 80),
            Member("e", U64, 128),
            Member("f", Array(U8, (3,)), 192),
        )
        assert self.layout(*members, size=32) == []

    def test_a_double_is_aligned_to_four_inside_a_structure_on_i386_and_to_eight_on_x86_64(
        self,
    ) -> None:
        members = (Member("a", U8, 0), Member("b", U64, 32))
        assert self.layout(*members, size=12, machine=I386) == []
        assert len(self.layout(*members, size=12, machine=X86_64)) == 1

    def test_a_structure_inside_one_is_aligned_as_its_own_members_are(self) -> None:
        inner = structure("In_s", Member("x", U32, 0), size=4)
        members = (Member("a", U8, 0), Member("i", inner, 32), Member("b", U8, 64))
        assert self.layout(*members, size=12) == []
        assert len(self.layout(Member("a", U8, 0), Member("i", inner, 8), size=5)) == 1

    def test_an_array_of_structures_counts_every_element(self) -> None:
        inner = structure("In_s", Member("x", U16, 0), Member("y", U8, 16), size=4)
        members = (Member("i", Array(inner, (3,)), 0), Member("b", U8, 96))
        assert self.layout(*members, size=14) == []

    def test_a_member_whose_offset_is_unknown_is_not_judged_and_the_size_still_is(self) -> None:
        assert self.layout(Member("a", U8, None), size=1) == []
        assert len(self.layout(Member("a", U8, None), size=4)) == 1

    def test_an_alignment_the_source_states_departs_by_the_size_it_gives_the_structure(
        self,
    ) -> None:
        (only,) = self.layout(Member("x", U8, 0, alignment=8), alignment=8, size=8)
        assert only[2].startswith("'L_s' is 8 bytes in C, where the structure DDD generates is 1")

    def test_a_gap_already_reported_is_not_reported_twice(self) -> None:
        members = (Member("a", U8, 0, 2), Member("b", U8, 5, 2), Member("c", U16, 7, 9))
        assert self.layout(*members, size=2) == []

    def test_a_bitfield_wider_than_the_alignment_cap_is_not_judged(self) -> None:
        assert self.layout(Member("a", U64, 0, 3), Member("b", U8, 8), size=4, machine=I386) == []

    def test_a_structure_inside_one_that_is_not_judged_leaves_the_outer_one_unjudged(self) -> None:
        inner = structure("In_s", Member("x", U64, 0, 3), size=8)
        outer = (Member("a", U8, 0), Member("i", inner, 8))
        assert self.layout(*outer, size=40, machine=I386) == []

    def test_a_machine_whose_rules_are_not_held_is_not_checked_and_says_so_once(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(machine=4660), bag)
        for name in ("a", "b"):
            packed = structure(f"{name}_s", Member("a", U8, 0), Member("b", U32, 8), size=5)
            mapped(packed, bag=bag, mapper=mapper)
        assert [(c, s) for c, s, _ in found(bag)] == [("elf-layout-unchecked", Severity.INFO)]
        assert found(bag)[0][2] == (
            "the layout of a structure is not checked against what DDD generates: the image is "
            "for a machine and ABI (e_machine 4660, e_flags 0x0) whose alignment rules this "
            "tool does not hold"
        )

    PACKED = (Member("a", U8, 0), Member("b", U32, 8))

    @pytest.mark.parametrize(("machine", "flags"), [(ARM, AAPCS), (RISCV, 0x1)])
    def test_an_abi_the_table_holds_is_checked(self, machine: int, flags: int) -> None:
        assert len(self.layout(*self.PACKED, size=5, machine=machine, flags=flags)) == 1

    @pytest.mark.parametrize(
        ("machine", "flags", "said"),
        [
            (ARM, 0, "e_machine 40, e_flags 0x0"),
            (ARM, 0x600, "e_machine 40, e_flags 0x600"),
            (RISCV, 0x9, "e_machine 243, e_flags 0x9"),
        ],
    )
    def test_an_abi_of_a_machine_the_table_holds_in_part_is_not_checked_and_says_so(
        self, machine: int, flags: int, said: str
    ) -> None:
        assert self.layout(*self.PACKED, size=5, machine=machine, flags=flags) == [
            (
                "elf-layout-unchecked",
                Severity.INFO,
                f"the layout of a structure is not checked against what DDD generates: the "
                f"image is for a machine and ABI ({said}) whose alignment rules this tool "
                f"does not hold",
            )
        ]

    def test_a_hand_built_image_that_states_no_machine_is_not_checked(self) -> None:
        assert self.layout(Member("a", U8, 0), Member("b", U32, 8), size=5, machine=None) == []

    def test_one_name_laid_out_two_ways_is_a_conflict_though_its_members_read_alike(self) -> None:
        mapper = Mapper(image(machine=X86_64), DiagnosticBag())
        packed = structure(
            "Pair_s",
            Member("a", U8, 0),
            Member("b", U32, 8),
            size=5,
            declared_at=Declared("unit_a.c", 3),
        )
        natural = structure(
            "Pair_s",
            Member("a", U8, 0),
            Member("b", U32, 32),
            size=8,
            declared_at=Declared("unit_b.c", 3),
        )
        mapped(packed, "A", mapper=mapper)
        mapped(natural, "B", mapper=mapper)
        assert mapper.conflicts() == {"Pair_s": [Declared("unit_a.c", 3), Declared("unit_b.c", 3)]}

    def test_two_structures_that_differ_in_offsets_alone_conflict(self) -> None:
        mapper = Mapper(image(machine=X86_64), DiagnosticBag())
        mapped(structure("T_s", Member("a", U8, 0), Member("b", U8, 8), size=4), "A", mapper=mapper)
        mapped(
            structure("T_s", Member("a", U8, 0), Member("b", U8, 16), size=4), "B", mapper=mapper
        )
        assert set(mapper.conflicts()) == {"T_s"}

    def test_two_structures_that_differ_in_size_alone_conflict(self) -> None:
        mapper = Mapper(image(machine=X86_64), DiagnosticBag())
        mapped(structure("T_s", Member("a", U8, 0), size=1), "A", mapper=mapper)
        mapped(structure("T_s", Member("a", U8, 0), size=4), "B", mapper=mapper)
        assert set(mapper.conflicts()) == {"T_s"}

    def test_two_structures_laid_out_alike_are_one(self) -> None:
        mapper = Mapper(image(machine=X86_64), DiagnosticBag())
        mapped(structure("T_s", Member("a", U8, 0), size=1), "A", mapper=mapper)
        mapped(structure("T_s", Member("a", U8, 0), size=1), "B", mapper=mapper)
        assert mapper.conflicts() == {}


class TestValues:
    @pytest.mark.parametrize(
        ("raw", "datatype", "byte_order", "value"),
        [
            (bytes([0x34, 0x12]), "uint16", "little", 0x1234),
            (bytes([0x12, 0x34]), "uint16", "big", 0x1234),
            (bytes([0xFE, 0xFF]), "sint16", "little", -2),
            (bytes([1, 2, 3, 4, 5, 6, 7, 8]), "uint64", "big", 0x0102030405060708),
            (bytes([0xFF]), "sint8", "little", -1),
            (bytes([1]), "boolean", "little", True),
            (bytes([0]), "boolean", "little", False),
            (struct.pack(">d", 0.1), "float64", "big", 0.1),
            (struct.pack("<f", 1.5), "float32", "little", 1.5),
            (struct.pack("<f", 0.1), "float32", "little", 0.1),
        ],
    )
    def test_a_scalar_is_read_in_the_image_s_byte_order(
        self, raw: bytes, datatype: str, byte_order: str, value: Any
    ) -> None:
        result = initial_value(raw, datatype, (), byte_order)
        assert result == value
        assert type(result) is type(value)

    def test_an_array_is_nested_lists_in_c_order(self) -> None:
        assert initial_value(bytes([1, 2, 3, 4, 5, 6]), "uint8", (2, 3), "little") == [
            [1, 2, 3],
            [4, 5, 6],
        ]

    def test_three_dimensions_nest_three_deep(self) -> None:
        assert initial_value(bytes(range(8)), "uint8", (2, 2, 2), "little") == [
            [[0, 1], [2, 3]],
            [[4, 5], [6, 7]],
        ]

    def test_an_array_of_one_value_is_that_value(self) -> None:
        assert initial_value(bytes([9, 9, 9, 9]), "uint8", (4,), "little") == 9

    def test_bytes_not_values_decide_whether_an_array_is_one_value(self) -> None:
        value = initial_value(struct.pack("<ff", -0.0, 0.0), "float32", (2,), "little")
        assert [math.copysign(1.0, item) for item in value] == [-1.0, 1.0]

    @pytest.mark.parametrize(
        ("raw", "datatype", "reason"),
        [
            (bytes([2]), "boolean", "a boolean byte of 2, which is neither 0 nor 1"),
            (struct.pack("<f", math.nan), "float32", "NaN"),
            (struct.pack("<d", -math.inf), "float64", "an infinity"),
        ],
    )
    def test_a_value_ddd_has_no_spelling_for_is_refused(
        self, raw: bytes, datatype: str, reason: str
    ) -> None:
        with pytest.raises(UnstatableValueError) as refused:
            initial_value(raw, datatype, (), "little")
        assert str(refused.value) == reason

    def test_one_element_ddd_has_no_spelling_for_refuses_the_array(self) -> None:
        with pytest.raises(UnstatableValueError):
            initial_value(bytes([1, 3]), "boolean", (2,), "little")

    def test_a_float32_is_spelled_with_the_fewest_digits_that_read_it_back(self) -> None:
        tenth = struct.unpack("<f", struct.pack("<f", 0.1))[0]
        assert shortest_float32(tenth) == 0.1

    def test_the_largest_float32_is_not_spelled_past_what_a_float32_holds(self) -> None:
        largest = struct.unpack("<f", (0x7F7FFFFF).to_bytes(4, "little"))[0]
        assert shortest_float32(largest) == 3.4028234663852886e38

    def test_a_float32_needing_nine_digits_gets_nine(self) -> None:
        value = struct.unpack("<f", (0x03AD66B5).to_bytes(4, "little"))[0]
        assert shortest_float32(value) == 1.01916065e-36

    @pytest.mark.parametrize(
        ("raw", "datatype", "value"),
        [
            (bytes([0xFF]), "uint8", 255),
            (bytes([0xFF, 0xFF]), "uint16", 0xFFFF),
            (bytes([0xFF, 0xFF, 0xFF, 0xFF]), "uint32", 0xFFFFFFFF),
            (bytes([0xFF, 0xFF, 0xFF, 0xFF]), "sint32", -1),
            (bytes([0xFF] * 8), "uint64", 0xFFFFFFFFFFFFFFFF),
            (bytes([0xFF] * 8), "sint64", -1),
        ],
    )
    def test_every_row_of_formats_keeps_its_own_width_and_signedness(
        self, raw: bytes, datatype: str, value: int
    ) -> None:
        """``uint32``, ``sint32`` and ``sint64`` appear in no test above; ``uint8``,
        ``uint16`` and ``uint64`` do, but only under 128 (2**15 for ``uint16``, 2**63 for
        ``uint64``), where the signed reading of the same bytes agrees. All bits set
        disagrees, and pins the row; a wrong width instead sends this same call into
        ``_nested`` with no dimensions, back as a list rather than the int compared above."""
        assert initial_value(raw, datatype, (), "little") == value

    def test_a_boolean_byte_is_read_as_unsigned(self) -> None:
        """The 2 above stays under 128, where ``b`` (signed) and ``B`` (unsigned) read back
        the same value; 255 does not, and only ``B`` spells the refusal this way."""
        with pytest.raises(UnstatableValueError) as refused:
            initial_value(bytes([0xFF]), "boolean", (), "little")
        assert str(refused.value) == "a boolean byte of 255, which is neither 0 nor 1"


def run(
    img: Image,
    *arguments: str,
    scope: str = "output",
    component: str | None = None,
    identity: bool = False,
) -> tuple[Description, DiagnosticBag]:
    bag = DiagnosticBag()
    description = describe(
        img, list(arguments), scope=scope, component=component, identity=identity, bag=bag
    )
    return description, bag


def filled(*pairs: tuple[int, bytes], size: int = 0x100) -> bytes:
    data = bytearray(size)
    for offset, raw in pairs:
        data[offset : offset + len(raw)] = raw
    return bytes(data)


def names(description: Description) -> list[str]:
    return [entry["definition"]["name"] for entry in description.interface]


class TestDescribe:
    def test_a_variable_becomes_one_entry_and_the_run_says_what_it_leaves_out(self) -> None:
        img = image(stored("Gain", U16, line=3), contents=filled((0, bytes([0x2C, 0x01]))))
        description, bag = run(img, "Gain")
        assert description == Description(
            (
                {
                    "scope": "output",
                    "definition": {
                        "name": "Gain",
                        "kind": "measurement",
                        "datatype": "uint16",
                        "init": 300,
                        "volatile": False,
                    },
                },
            ),
            (),
        )
        assert found(bag) == [("elf-not-inferred", Severity.INFO, NOT_INFERRED)]

    def test_with_the_option_a_variable_states_the_identity_the_author_asked_for(self) -> None:
        img = image(stored("Gain", U16, line=3), contents=filled((0, bytes([0x2C, 0x01]))))
        description, bag = run(img, "Gain", identity=True)
        assert description.interface[0]["definition"] == {
            "name": "Gain",
            "kind": "measurement",
            "datatype": "uint16",
            "conversion": IDENTITY,
            "init": 300,
            "volatile": False,
        }
        assert found(bag) == [("elf-not-inferred", Severity.INFO, IDENTITY_CLAIMED)]

    def test_a_definition_states_its_keys_in_the_examples_order(self) -> None:
        calib = Section(".calib", 0x100, 0x100, 0)
        img = image(
            stored("Table", Array(Qualified(U8, const=True), (2,))),
            sections=(calib,),
            contents=filled((0, bytes([1, 2]))),
        )
        description, _ = run(img, "Table", identity=True)
        assert list(description.interface[0]["definition"]) == [
            "name",
            "kind",
            "datatype",
            "dimensions",
            "conversion",
            "init",
            "section",
            "volatile",
        ]

    def test_a_consumer_states_no_storage_and_reads_none(self) -> None:
        img = image(
            stored("Level", F32),
            sections=(Section(".calib", 0x100, 4, 0),),
            contents=filled((0, struct.pack("<f", math.nan))),
        )
        description, bag = run(img, "Level", scope="input")
        assert description.interface[0] == {
            "scope": "input",
            "definition": {
                "name": "Level",
                "kind": "measurement",
                "datatype": "float32",
                "volatile": False,
            },
        }
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]

    def test_a_local_states_its_storage_as_an_output_does(self) -> None:
        img = image(stored("Gain", U16), contents=filled((0, bytes([0x2C, 0x01]))))
        description, _ = run(img, "Gain", scope="local")
        assert description.interface[0]["scope"] == "local"
        assert description.interface[0]["definition"]["init"] == 300

    def test_an_image_with_nothing_but_a_note_holding_contents_is_refused(self) -> None:
        build_id = Section(".note.gnu.build-id", 0x0, 0x24, 0, note=True)
        data = Section(".data", 0x100, 0x100, None)
        img = image(stored("Gain", U16, address=0x100), sections=(build_id, data))
        with pytest.raises(ValueError, match="debug information"):
            describe(img, ["Gain"], scope="local", component=None, bag=DiagnosticBag())

    def test_an_image_without_a_section_of_the_program_is_not_refused(self) -> None:
        img = image(stored("Gain", U16, address=0x100), sections=())
        _, bag = run(img, "Gain")
        assert any(check == "elf-no-storage" for check, _, _ in found(bag))

    def test_an_image_whose_code_has_no_contents_is_refused(self) -> None:
        """The shape ``objcopy --only-keep-debug`` leaves: every section is there and none has
        its bytes, so no initial value is."""
        text = Section(".text", 0x0, 0x40, None)
        data = Section(".data", 0x100, 0x100, None)
        img = image(stored("Gain", U16, address=0x100), sections=(text, data))
        with pytest.raises(ValueError, match="debug information") as refused:
            describe(img, ["Gain"], scope="local", component=None, bag=DiagnosticBag())
        assert str(refused.value) == (
            "'hand.elf' is debug information without the image's contents: its sections "
            "hold none of the program, so no initial value can be read from it; give it the linked "
            "image it was split from"
        )

    def test_an_image_whose_code_has_contents_is_not_refused(self) -> None:
        text = Section(".text", 0x0, 0x40, 0)
        img = image(stored("Gain", U16, address=0x100), sections=(text, DATA))
        description, _ = run(img, "Gain")
        assert description.interface[0]["definition"]["init"] == 0

    def test_an_image_whose_code_is_contentless_but_whose_data_is_in_the_file_is_read(self) -> None:
        """A NOLOAD code region has no bytes in the file by design, and the initial values are
        in .data and .rodata: every one is readable, so nothing is refused."""
        noload = Section(".boot", 0x0, 0x40, None)
        img = image(stored("Gain", U16, address=0x100), sections=(noload, DATA))
        description, _ = run(img, "Gain")
        assert description.interface[0]["definition"]["init"] == 0

    def test_an_image_with_one_code_section_holding_contents_is_not_refused(self) -> None:
        """A linker script may leave one executable section without bytes (a ``.bss``-like
        code region) beside the ones that have them: the image is still one to read."""
        text = Section(".text", 0x0, 0x40, 0)
        ramcode = Section(".ramcode", 0x400, 0x40, None)
        img = image(stored("Gain", U16, address=0x100), sections=(text, ramcode, DATA))
        description, _ = run(img, "Gain")
        assert description.interface[0]["definition"]["init"] == 0

    def test_a_default_section_without_contents_states_neither_init_nor_section(self) -> None:
        bss = Section(".bss", 0x200, 4, None)
        description, _ = run(
            image(stored("Counter", U16, address=0x200), sections=(DATA, bss)), "Counter"
        )
        assert {"init", "section"}.isdisjoint(description.interface[0]["definition"])

    def test_a_custom_section_without_contents_is_stated_without_an_init(self) -> None:
        """The case no portable C spelling builds (Task 1): a .noinit the startup code leaves
        alone."""
        noinit = Section(".noinit", 0x200, 4, None)
        img = image(stored("Retained", U16, address=0x200), sections=(DATA, noinit))
        description, bag = run(img, "Retained")
        definition = description.interface[0]["definition"]
        assert ("init" in definition, definition["section"]) == (False, ".noinit")
        assert [check for check, _, _ in found(bag)] == ["elf-section", "elf-not-inferred"]

    @pytest.mark.parametrize("section", sorted(DEFAULT_SECTIONS))
    def test_a_toolchain_default_section_is_not_stated(self, section: str) -> None:
        img = image(stored("Gain", U16), sections=(Section(section, 0x100, 4, 0),))
        description, _ = run(img, "Gain")
        assert "section" not in description.interface[0]["definition"]

    def test_a_section_the_output_states_is_warned_about_once(self) -> None:
        calib = Section(".calib", 0x100, 8, 0)
        img = image(
            stored("A", U16, line=3), stored("B", U16, address=0x102, line=4), sections=(calib,)
        )
        _, bag = run(img, "A", "B")
        sections = [d for d in bag.sorted if d.check == "elf-section"]
        assert [(d.message, d.location) for d in sections] == [
            (
                "'A' is placed in '.calib', the name of the image's output section: DDD's "
                "section is the one the source places it in, which the linker script may have "
                "renamed, and the project has to declare it in a sections file, or 'ddd check' "
                "reports unknown-section",
                Location(Path("unit.c"), line=3),
            )
        ]

    def test_an_address_no_section_holds_is_refused(self) -> None:
        description, bag = run(image(stored("Lost", U16, address=0x900)), "Lost")
        assert description.interface == ()
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "'Lost' has an address, 0x900, that no section of the image holds",
            )
        ]

    def test_a_global_the_symbol_table_does_not_hold_at_its_address_is_refused(self) -> None:
        """A section holds the address, so that what gold leaves of a discarded unit - an offset
        into the section, where the code of another may sit - is not read as the variable's."""
        description, bag = run(
            image(stored("Gone", U16, address=0x110), objects=frozenset()), "Gone"
        )
        assert description.interface == ()
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "the symbol table holds no object named 'Gone' at 0x110, where its debug "
                "information puts it, as a linker leaves a variable of a unit it discarded",
            )
        ]

    def test_a_static_is_read_without_a_symbol_since_a_link_may_drop_the_locals(self) -> None:
        description, bag = run(
            image(stored("Local", U16, address=0x110, external=False), objects=frozenset()),
            "Local",
        )
        assert [entry["definition"]["name"] for entry in description.interface] == ["Local"]
        assert [check for check, severity, _ in found(bag) if severity is Severity.ERROR] == []

    def test_a_static_at_an_address_no_section_holds_is_refused(self) -> None:
        """The exemption from the symbol table is not one from the sections."""
        description, bag = run(image(stored("Local", U16, address=0x900, external=False)), "Local")
        assert description.interface == ()
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "'Local' has an address, 0x900, that no section of the image holds",
            )
        ]

    def test_a_static_the_local_symbols_of_the_image_do_not_hold_is_refused(self) -> None:
        """A link made without -Wl,-x keeps its local symbols, and gold leaves the statics of a
        unit it discarded at offsets, where none sits."""
        description, bag = run(
            image(
                stored("Local", U16, address=0x110, external=False),
                local_objects=frozenset({("Local", 0x120), ("Other", 0x110)}),
            ),
            "Local",
        )
        assert description.interface == ()
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "the symbol table holds no object named 'Local' at 0x110, where its debug "
                "information puts it, as a linker leaves a variable of a unit it discarded",
            )
        ]

    def test_a_static_the_local_symbols_hold_is_read(self) -> None:
        description, _ = run(
            image(
                stored("Local", U16, address=0x110, external=False),
                local_objects=frozenset({("Local", 0x110)}),
            ),
            "Local",
        )
        assert [entry["definition"]["name"] for entry in description.interface] == ["Local"]

    def test_a_variable_running_past_its_section_is_refused(self) -> None:
        img = image(stored("Wide", Base("unsigned int", DW_ATE_UNSIGNED, 4), address=0x1FE))
        _, bag = run(img, "Wide")
        assert found(bag) == [
            (
                "elf-init-unsupported",
                Severity.ERROR,
                "'Wide' runs past the end of section '.data', so its initial value cannot be read",
            )
        ]

    def test_a_value_ddd_cannot_state_is_refused(self) -> None:
        img = image(stored("Level", F32), contents=filled((0, struct.pack("<f", math.nan))))
        _, bag = run(img, "Level")
        assert found(bag) == [
            (
                "elf-init-unsupported",
                Severity.ERROR,
                "'Level' starts as NaN, which DDD cannot state as an initial value",
            )
        ]

    def test_a_structured_object_s_values_are_dropped_and_said_to_be(self) -> None:
        img = image(
            stored("Config", Qualified(PAIR, const=True), line=7),
            contents=filled((0, bytes([1, 2]))),
        )
        description, bag = run(img, "Config", component="Pump", identity=True)
        assert description.interface[0]["definition"] == {
            "name": "Config",
            "kind": "parameter",
            "typename": "Pair_s",
            "volatile": False,
        }
        assert description.types == (PAIR_ENTRY,)
        assert found(bag)[0] == (
            "elf-init-dropped",
            Severity.WARNING,
            "'Config' starts with values the image holds, which DDD does not carry: a structured "
            "object is zero-initialised, and its values reach it from the running software or "
            "from the calibration tool",
        )

    def test_a_structured_object_of_zeros_loses_nothing(self) -> None:
        _, bag = run(image(stored("Config", PAIR)), "Config", component="Pump")
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]

    def test_the_list_output_says_where_the_types_went(self) -> None:
        _, bag = run(image(stored("Config", PAIR)), "Config")
        assert (
            "elf-types-omitted",
            Severity.WARNING,
            "the list output has no place for the types its structured objects name: "
            "'--component NAME' prints a component file that holds them",
        ) in found(bag)

    def test_a_value_block_adds_why_it_is_one_to_what_the_run_leaves_out(self) -> None:
        _, bag = run(image(stored("Table", Array(Qualified(U8, const=True), (2,)))), "Table")
        assert found(bag) == [("elf-not-inferred", Severity.INFO, NOT_INFERRED + VALUE_BLOCKS)]

    def test_what_is_not_inferred_and_why_a_value_block_is_one_are_spelled_out_word_for_word(
        self,
    ) -> None:
        """The two tests above compare against ``NOT_INFERRED``/``VALUE_BLOCKS`` themselves, so
        a wording change to either constant would not fail them: pinned here against the
        literal sentences instead."""
        _, bag = run(image(stored("Table", Array(Qualified(U8, const=True), (2,)))), "Table")
        assert found(bag) == [
            (
                "elf-not-inferred",
                Severity.INFO,
                "an image states no unit, description, limits, scaling or id, so the output "
                "states none: it states no conversion for what is not an enum either, since raw "
                "equalling physical is a claim about the data that an image does not make, and "
                "'ddd check' asks its author to state it ('--identity-conversions' writes the "
                "identity, where you state it); the limits are the ones DDD derives, and "
                "'ddd id --assign' writes the ids; and a const array is a value block, since "
                "nothing in an image tells a curve, a map or an axis from any other array",
            )
        ]

    def test_every_variable_reaching_a_name_defined_two_ways_is_refused(self) -> None:
        first = structure(
            "Clash_s", Member("a", U8, 0), size=1, declared_at=Declared("unit_a.c", 11)
        )
        second = structure(
            "Clash_s", Member("a", U16, 0), size=2, declared_at=Declared("unit_b.c", 10)
        )
        img = image(
            stored("A", first, unit="unit_a.c", line=13),
            stored("B", second, unit="unit_b.c", line=13),
            stored("Gain", U8),
        )
        description, bag = run(img, "A", "B", "Gain")
        assert names(description) == ["Gain"]
        conflicts = [d for d in bag.sorted if d.check == "elf-type-conflict"]
        assert [d.message for d in conflicts] == [
            f"'{name}' reaches 'Clash_s', which the image defines 2 different ways, so no one "
            f"description of it is right"
            for name in ("A", "B")
        ]
        assert conflicts[0].notes == (
            ("'Clash_s' is defined one way here", Location(Path("unit_a.c"), line=11)),
            ("'Clash_s' is defined one way here", Location(Path("unit_b.c"), line=10)),
        )

    def test_a_variable_the_mapping_refuses_is_left_out_and_the_rest_described(self) -> None:
        img = image(stored("Pointer", Unsupported("a pointer")), stored("Gain", U16))
        description, bag = run(img, "Pointer", "Gain")
        assert names(description) == ["Gain"]
        assert [check for check, _, _ in found(bag)] == ["elf-type-unsupported", "elf-not-inferred"]

    def test_a_malformed_argument_is_refused_before_anything_is_read(self) -> None:
        with pytest.raises(ValueError):
            run(image(), "unit.c:")


class TestDocumentText:
    def test_the_list_output_is_the_entries(self) -> None:
        description = Description(
            ({"scope": "output", "definition": {"name": "A"}},), (PAIR_ENTRY,)
        )
        assert document_text(description, None) == (
            '[\n  {\n    "scope": "output",\n    "definition": {\n'
            '      "name": "A"\n    }\n  }\n]\n'
        )

    def test_the_component_output_holds_the_types_where_there_are_some(self) -> None:
        with_types = Description(({"scope": "output", "definition": {"name": "A"}},), (PAIR_ENTRY,))
        without = Description(with_types.interface, ())
        document = json.loads(document_text(with_types, "Pump"))
        assert document == {
            "component": {
                "name": "Pump",
                "types": [PAIR_ENTRY],
                "interface": list(with_types.interface),
            }
        }
        assert list(document["component"]) == ["name", "types", "interface"]
        assert json.loads(document_text(without, "Pump")) == {
            "component": {"name": "Pump", "interface": list(without.interface)}
        }


class TestTheCheckByDdd:
    def test_the_policy_is_standalone_s_and_leaves_missing_id_out(self) -> None:
        assert (*STANDALONE_POLICY, "missing-id=ignore") == POLICY

    def test_a_load_error_then_an_analysis_error_each_refuse_their_variable(self) -> None:
        """Review Focus 4: the schema error stops DDD before its analysis, so the enumerator
        wider than an int is only found on the second pass."""
        wide = Enum("Wide_e", 8, False, (("SMALL", 1), ("HUGE", 1 << 40)))
        long_name = "L" * 130
        img = image(
            stored("Good", U8, line=1),
            stored(long_name, U8, address=0x101, line=2),
            stored("Wide", wide, address=0x108, line=3),
        )
        description, bag = run(img, "Good", "L*", "Wide")
        assert names(description) == ["Good"]
        errors = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert [(d.check, d.location, d.notes[-1]) for d in errors] == [
            ("schema", Location(Path("unit.c"), line=2), (f"'{long_name}' is left out", None)),
            ("init-invalid", Location(Path("unit.c"), line=3), ("'Wide' is left out", None)),
        ]

    def test_an_error_found_while_loading_skips_the_analysis_even_when_it_still_loaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No real check of ddd's reaches this under one component file: every ``None``
        workspace already comes with an error of its own, so a real load never shows this
        guard pinning anything beyond ``not found.has_errors`` alone - which is why
        ``workspace is not None`` is dropped above and nothing dies. Patched in directly:
        a load that both errors and still returns a workspace must not reach ``analyze``."""

        def fake_load_workspace(path: Path, bag: DiagnosticBag) -> object:
            bag.add("made-up", "a made-up load problem", Location(Path("nowhere")))
            return object()

        def fake_analyze(workspace: Any, bag: DiagnosticBag) -> None:
            raise AssertionError("analyze must not run once a load error is on the bag")

        monkeypatch.setattr("ddd.toolbox.checked.load_workspace", fake_load_workspace)
        monkeypatch.setattr("ddd.toolbox.checked.analyze", fake_analyze)
        description, bag = run(image(stored("Gain", U8, line=1)), "Gain")
        assert names(description) == ["Gain"]
        assert [d.check for d in bag.sorted] == ["made-up", "elf-not-inferred"]

    def test_a_finding_on_a_type_refuses_every_variable_reaching_it(self) -> None:
        wide = Enum("Wide_e", 8, False, (("HUGE", 1 << 40),))
        holder = structure("Holder_s", Member("level", wide, 0), size=8)
        img = image(
            stored("A", holder, line=4),
            stored("B", holder, address=0x108, line=5),
            stored("Good", U8, address=0x110),
        )
        description, bag = run(img, "A", "B", "Good", component="Pump")
        assert names(description) == ["Good"]
        assert description.types == ()
        (error,) = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert (error.check, error.location) == ("init-invalid", Location(Path("unit.c"), line=4))
        assert error.notes[-2:] == (("'A' is left out", None), ("'B' is left out", None))

    def test_ddd_s_warnings_of_the_last_pass_are_relayed_at_the_declaration(self) -> None:
        twice = Enum("Twice_e", 1, False, (("ONE", 1), ("UNO", 1)))
        _, bag = run(image(stored("Mode", twice, line=6)), "Mode")
        (duplicate,) = [d for d in bag.sorted if d.check == "enum-duplicate-value"]
        assert (duplicate.severity, duplicate.location) == (
            Severity.WARNING,
            Location(Path("unit.c"), line=6),
        )

    def test_a_warning_with_no_error_leaves_its_candidate_in_the_output(self) -> None:
        """Were ``errors``'s filter to admit a warning alongside the errors it is meant for,
        ``Mode`` would be refused for one; it is kept, and both findings are still reported."""
        twice = Enum("Twice_e", 1, False, (("ONE", 1), ("UNO", 1)))
        description, bag = run(image(stored("Mode", twice, line=6)), "Mode")
        assert names(description) == ["Mode"]
        assert [check for check, _, _ in found(bag)] == ["enum-duplicate-value", "elf-not-inferred"]

    def test_a_note_of_ddd_s_is_moved_to_the_declaration_it_points_at(self) -> None:
        img = image(stored("gain", U8, line=1), stored("Gain", U8, address=0x101, line=2))
        _, bag = run(img, "gain", "Gain")
        (similar,) = [d for d in bag.sorted if d.check == "name-similar"]
        assert (similar.severity, similar.location) == (
            Severity.WARNING,
            Location(Path("unit.c"), line=1),
        )
        assert similar.notes == (("other variable", Location(Path("unit.c"), line=2)),)

    def test_a_note_pointing_outside_every_candidate_gets_no_location(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No check of ddd's own reaches this in the tests above: every note one of them adds
        here names another candidate. Patched in directly, to pin the branch coverage cannot
        see - a note ``_concerned`` cannot place gets no location, rather than the wrong one."""

        def fake_analyze(workspace: Any, bag: DiagnosticBag) -> None:
            bag.add(
                "made-up",
                "a made-up problem",
                Location(Path("nowhere"), "component.interface[0]"),
                notes=[("elsewhere", Location(Path("nowhere"), "component.name"))],
            )

        monkeypatch.setattr("ddd.toolbox.checked.analyze", fake_analyze)
        _, bag = run(image(stored("Gain", U8, line=1)), "Gain")
        (diagnostic,) = [d for d in bag.sorted if d.check == "made-up"]
        assert diagnostic.notes[0] == ("elsewhere", None)

    def test_a_finding_about_no_variable_is_relayed_at_the_image_and_ends_the_passes(
        self,
    ) -> None:
        description, bag = run(image(stored("Gain", U8)), "Gain", component="1bad")
        (error,) = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert (error.check, error.location) == ("schema", where(Path("hand.elf")))
        assert names(description) == ["Gain"]

    def test_a_run_ddd_refuses_everything_of_has_nothing_left_to_check(self) -> None:
        wide = Enum("Wide_e", 8, False, (("HUGE", 1 << 40),))
        description, bag = run(image(stored("Wide", wide)), "Wide")
        assert description.interface == ()
        assert [d.check for d in bag.sorted] == ["init-invalid"]


FLT_MAX = struct.unpack("<f", (0x7F7FFFFF).to_bytes(4, "little"))[0]


class TestTheLargestFloat:
    """A float32 of FLT_MAX is written as DDD's own check accepts it (finding 11:M1)."""

    def test_the_largest_float32_is_spelled_as_the_double_it_is(self) -> None:
        assert shortest_float32(FLT_MAX) == FLT_MAX
        assert shortest_float32(-FLT_MAX) == -FLT_MAX

    def test_a_float32_whose_shortest_spelling_reads_back_is_still_spelled_so(self) -> None:
        tenth = struct.unpack("<f", struct.pack("<f", 0.1))[0]
        assert shortest_float32(tenth) == 0.1
        assert shortest_float32(-tenth) == -0.1

    @pytest.mark.parametrize("value", [FLT_MAX, -FLT_MAX], ids=["FLT_MAX", "-FLT_MAX"])
    def test_ddd_accepts_what_the_tool_writes_for_it(self, value: float) -> None:
        img = image(stored("Peak", F32), contents=filled((0, struct.pack("<f", value))))
        description, bag = run(img, "Peak")
        assert names(description) == ["Peak"]
        assert description.interface[0]["definition"]["init"] == value
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]
        assert not bag.has_errors


class TestUnitsThatDisagree:
    """One name at one address, stated two ways, is reported and not described (finding 11:M6)."""

    COMMON = (
        "'Cal' at 0x100 is described as 2 bytes by 'unit_a.c' and as 4 bytes by 'unit_b.c': "
        "one name at one address is one variable, so no one description of it is right"
    )

    def two_units(self, first: CType, second: CType) -> Image:
        return image(
            stored("Cal", first, unit="unit_a.c", line=3),
            stored("Cal", second, unit="unit_b.c", line=4),
            stored("Fine", U8, address=0x108),
        )

    def test_two_sizes_of_a_name_at_one_address_are_a_type_conflict(self) -> None:
        description, bag = run(self.two_units(U16, U32), "Cal", "Fine")
        assert names(description) == ["Fine"]
        conflicts = [d for d in bag.sorted if d.check == "elf-type-conflict"]
        assert [(d.severity, d.message, d.location) for d in conflicts] == [
            (Severity.ERROR, self.COMMON, Location(Path("unit_a.c"), line=3))
        ]
        assert conflicts[0].notes == (
            ("described as 2 bytes here", Location(Path("unit_a.c"), line=3)),
            ("described as 4 bytes here", Location(Path("unit_b.c"), line=4)),
        )

    def test_an_array_declared_with_two_lengths_is_one(self) -> None:
        img = image(
            stored("Shared", Array(U32, (2,)), unit="unit_a.c"),
            stored("Shared", Array(U32, (4,)), unit="unit_b.c"),
        )
        description, bag = run(img, "Shared")
        assert description.interface == ()
        assert [d.message for d in bag.sorted if d.check == "elf-type-conflict"] == [
            "'Shared' at 0x100 is described as 8 bytes by 'unit_a.c' and as 16 bytes by "
            "'unit_b.c': one name at one address is one variable, so no one description of it "
            "is right"
        ]

    def test_units_of_one_size_are_one_variable(self) -> None:
        description, bag = run(self.two_units(U32, S32), "Cal")
        assert names(description) == ["Cal"]
        assert not [d for d in bag.sorted if d.check == "elf-type-conflict"]

    def test_the_symbol_s_size_is_held_against_a_single_description(self) -> None:
        img = image(stored("Cal", U16, unit="unit_a.c", line=3), object_sizes={("Cal", 0x100): 4})
        description, bag = run(img, "Cal")
        assert description.interface == ()
        assert [(d.check, d.message) for d in bag.sorted if d.check == "elf-type-conflict"] == [
            (
                "elf-type-conflict",
                "'Cal' at 0x100 is described as 2 bytes by 'unit_a.c', and the symbol table "
                "holds it as 4 bytes: one name at one address is one variable, so no one "
                "description of it is right",
            )
        ]

    def test_a_description_and_the_symbol_of_one_size_agree(self) -> None:
        img = image(stored("Cal", U16), object_sizes={("Cal", 0x100): 2})
        description, _ = run(img, "Cal")
        assert names(description) == ["Cal"]

    def test_a_symbol_of_no_size_says_nothing(self) -> None:
        img = image(stored("Cal", U16), object_sizes={("Cal", 0x100): 0})
        description, _ = run(img, "Cal")
        assert names(description) == ["Cal"]

    def test_a_type_with_no_size_is_not_compared(self) -> None:
        img = image(
            stored("Cal", Unsupported("a pointer"), unit="unit_a.c"),
            stored("Cal", U32, unit="unit_b.c"),
        )
        _, bag = run(img, "Cal")
        assert not [d for d in bag.sorted if d.check == "elf-type-conflict"]

    def test_two_units_stating_one_size_beside_a_third_stating_another_are_named_together(
        self,
    ) -> None:
        img = image(
            stored("Cal", U16, unit="a.c"),
            stored("Cal", U16, unit="b.c"),
            stored("Cal", U32, unit="c.c"),
        )
        _, bag = run(img, "Cal")
        assert [d.message for d in bag.sorted if d.check == "elf-type-conflict"] == [
            "'Cal' at 0x100 is described as 2 bytes by 'a.c' and 'b.c' and as 4 bytes by "
            "'c.c': one name at one address is one variable, so no one description of it is "
            "right"
        ]

    def test_a_unit_whose_type_has_no_size_is_left_out_of_the_account(self) -> None:
        img = image(
            stored("Cal", Unsupported("a pointer"), unit="unit_a.c", line=3),
            stored("Cal", U16, unit="unit_b.c", line=4),
            object_sizes={("Cal", 0x100): 4},
        )
        _, bag = run(img, "Cal")
        assert [d.message for d in bag.sorted if d.check == "elf-type-conflict"] == [
            "'Cal' at 0x100 is described as 2 bytes by 'unit_b.c', and the symbol table holds "
            "it as 4 bytes: one name at one address is one variable, so no one description of "
            "it is right"
        ]
        (conflict,) = [d for d in bag.sorted if d.check == "elf-type-conflict"]
        assert conflict.location == Location(Path("unit_b.c"), line=4)
        assert conflict.notes == (
            ("described as 2 bytes here", Location(Path("unit_b.c"), line=4)),
        )

    def test_a_unit_prefix_chooses_the_unit_and_nothing_more(self) -> None:
        description, bag = run(self.two_units(U16, U32), "unit_b.c:Cal")
        assert description.interface == ()
        assert [d.check for d in bag.sorted if d.check == "elf-type-conflict"] == [
            "elf-type-conflict"
        ]

    def test_a_unit_prefix_reports_the_addresses_it_reaches_and_no_other(self) -> None:
        """Two statics of one name at another address, which disagree with each other, are not
        the disagreement of the variable a prefix asked for."""
        img = image(
            stored("Cal", U16, unit="a.c"),
            stored("Cal", U16, unit="b.c", address=0x180, external=False),
            stored("Cal", U32, unit="c.c", address=0x180, external=False),
        )
        description, bag = run(img, "a.c:Cal")
        assert names(description) == ["Cal"]
        assert not [d for d in bag.sorted if d.check == "elf-type-conflict"]

    def test_a_disagreeing_global_does_not_hide_another_unit_s_static_of_the_name(self) -> None:
        img = image(
            stored("Cal", U16, unit="a.c"),
            stored("Cal", U32, unit="b.c"),
            stored("Cal", U8, unit="c.c", address=0x180, external=False),
            object_sizes={("Cal", 0x100): 4},
        )
        description, bag = run(img, "Cal")
        assert description.interface == ()
        checks = [d.check for d in bag.sorted]
        assert "elf-type-conflict" in checks
        (ambiguous,) = [d for d in bag.sorted if d.check == "elf-symbol-ambiguous"]
        assert "names a variable in 2 units, 'a.c', 'c.c': prefix it with one" in ambiguous.message

    def test_a_name_is_reported_once_however_many_arguments_reach_it(self) -> None:
        _, bag = run(self.two_units(U16, U32), "Cal", "Ca*", "unit_a.c:Cal")
        assert len([d for d in bag.sorted if d.check == "elf-type-conflict"]) == 1

    def test_a_static_of_two_units_at_two_addresses_is_no_disagreement(self) -> None:
        img = image(
            stored("Gain", U16, unit="unit_a.c", address=0x100, external=False),
            stored("Gain", U32, unit="unit_b.c", address=0x108, external=False),
        )
        _, bag = run(img, "Gain")
        checks = [d.check for d in bag.sorted]
        assert "elf-symbol-ambiguous" in checks
        assert "elf-type-conflict" not in checks


GOLD = Section(".data", 0x100, 4, 0, index=1)
SILVER = Section(".alt", 0x100, 4, 0, index=2)


class TestSectionsAtOneAddress:
    """Where two sections hold an address, the symbol's own section is the variable's, and
    where nothing says which, the variable is refused (finding 11:M7)."""

    def overlaid(self, **extra: Any) -> Image:
        data = bytes([1, 0, 0, 0]) + bytes(0xFC)
        return image(
            stored("Page", U32, line=3),
            sections=(GOLD, SILVER),
            contents=data,
            **extra,
        )

    def test_the_section_the_symbol_names_is_the_one(self) -> None:
        img = self.overlaid(object_sections={("Page", 0x100): 2})
        description, bag = run(img, "Page")
        assert description.interface[0]["definition"]["section"] == ".alt"
        assert [d.check for d in bag.sorted] == ["elf-section", "elf-not-inferred"]

    def test_the_first_section_is_the_one_where_the_symbol_names_it(self) -> None:
        img = self.overlaid(object_sections={("Page", 0x100): 1})
        description, _ = run(img, "Page")
        assert "section" not in description.interface[0]["definition"]

    def test_where_nothing_says_which_the_variable_is_refused_and_both_are_named(self) -> None:
        description, bag = run(self.overlaid(), "Page")
        assert description.interface == ()
        ambiguous = [d for d in bag.sorted if d.check == "elf-section-ambiguous"]
        assert [(d.severity, d.message, d.location) for d in ambiguous] == [
            (
                Severity.ERROR,
                "'Page' lies at 0x100, which the sections '.data' and '.alt' both hold, and "
                "nothing in the image says which of them is its own, so its section and its "
                "initial value cannot be stated",
                Location(Path("unit.c"), line=3),
            )
        ]

    def test_a_symbol_naming_a_section_that_does_not_hold_the_address_says_nothing(self) -> None:
        elsewhere = Section(".far", 0x900, 4, 0, index=3)
        img = image(
            stored("Page", U32),
            sections=(GOLD, SILVER, elsewhere),
            object_sections={("Page", 0x100): 3},
        )
        _, bag = run(img, "Page")
        assert [d.check for d in bag.sorted] == ["elf-section-ambiguous"]

    def test_a_symbol_naming_a_special_section_says_nothing_either(self) -> None:
        _, bag = run(self.overlaid(object_sections={("Page", 0x100): "SHN_ABS"}), "Page")
        assert [d.check for d in bag.sorted] == ["elf-section-ambiguous"]

    def test_three_sections_are_all_named(self) -> None:
        third = Section(".third", 0x100, 4, 0, index=3)
        img = image(stored("Page", U32), sections=(GOLD, SILVER, third))
        _, bag = run(img, "Page")
        (ambiguous,) = [d for d in bag.sorted if d.check == "elf-section-ambiguous"]
        assert "the sections '.data', '.alt' and '.third' all hold" in ambiguous.message

    def test_a_consumer_states_no_section_and_is_not_asked_which(self) -> None:
        description, bag = run(self.overlaid(), "Page", scope="input")
        assert names(description) == ["Page"]
        assert not [d for d in bag.sorted if d.check == "elf-section-ambiguous"]

    def test_the_initial_value_is_read_from_the_section_the_symbol_names(self) -> None:
        silver = Section(".alt", 0x100, 4, 4, index=2)
        data = bytes([1, 0, 0, 0, 9, 0, 0, 0]) + bytes(0xF8)
        img = image(
            stored("Page", U32),
            sections=(GOLD, silver),
            contents=data,
            object_sections={("Page", 0x100): 2},
        )
        description, _ = run(img, "Page")
        assert description.interface[0]["definition"]["init"] == 9


class TestAnotherScope:
    """A variable of a C++ namespace is no candidate by its short name (finding 11:M8)."""

    def scoped(self) -> Image:
        return image(
            stored("OnlyInNs", U16, address=None, missing=OTHER_SCOPE, line=24),
            stored("Gain", U16, address=0x100),
        )

    def test_it_is_refused_in_a_sentence_of_its_own(self) -> None:
        description, bag = run(self.scoped(), "OnlyInNs", "Gain")
        assert names(description) == ["Gain"]
        assert [(d.check, d.message) for d in bag.sorted if d.check == "elf-no-storage"] == [
            (
                "elf-no-storage",
                "'OnlyInNs' is a variable of a C++ namespace or class, which DDD does "
                "not read: it reads C, and a short name does not say which one it is",
            )
        ]

    def test_several_units_leaving_it_without_storage_are_named_with_their_reasons(self) -> None:
        img = image(
            stored("OnlyInNs", unit="a.cc", address=None, missing=OTHER_SCOPE),
            stored("OnlyInNs", unit="b.cc", address=None, missing=OTHER_SCOPE),
        )
        _, bag = run(img, "OnlyInNs")
        assert [d.message for d in bag.sorted if d.check == "elf-no-storage"] == [
            f"'OnlyInNs' has no address in the image, in any of its 2 units, 'a.cc', 'b.cc': "
            f"{OTHER_SCOPE}"
        ]


class TestAskedTwice:
    """A name two variables share is refused in the reader's own terms (finding 11:M9)."""

    def statics(self) -> Image:
        return image(
            stored("Offset", U16, unit="io_a.c", address=0x100, external=False, line=3),
            stored("Offset", U16, unit="io_b.c", address=0x108, external=False, line=4),
        )

    def test_both_spellings_are_named_and_no_component_is(self) -> None:
        description, bag = run(self.statics(), "io_a.c:Offset", "io_b.c:Offset")
        assert description.interface == ()
        refused = [d for d in bag.sorted if d.check == "elf-symbol-ambiguous"]
        assert [(d.severity, d.message, d.location) for d in refused] == [
            (
                Severity.ERROR,
                "'Offset' is asked for twice, as 'io_a.c:Offset' (in 'io_a.c') and as "
                "'io_b.c:Offset' (in 'io_b.c'): DDD names an object once, so two variables of "
                "one name cannot both be described",
                Location(Path("io_b.c"), line=4),
            )
        ]
        assert refused[0].notes == (
            ("asked for as 'io_a.c:Offset'", Location(Path("io_a.c"), line=3)),
            ("asked for as 'io_b.c:Offset'", Location(Path("io_b.c"), line=4)),
        )
        assert not [d for d in bag.sorted if "FromElf" in d.message]

    def test_three_spellings_are_listed_with_a_count(self) -> None:
        img = image(
            stored("Offset", U16, unit="a.c", address=0x100, external=False),
            stored("Offset", U16, unit="b.c", address=0x108, external=False),
            stored("Offset", U16, unit="c.c", address=0x110, external=False),
        )
        _, bag = run(img, "a.c:Offset", "b.c:Offset", "c.c:Offset")
        (refused,) = [d for d in bag.sorted if d.check == "elf-symbol-ambiguous"]
        assert refused.message.startswith(
            "'Offset' is asked for 3 times, as 'a.c:Offset' (in 'a.c'), as 'b.c:Offset' (in 'b.c') "
            "and as 'c.c:Offset' (in 'c.c'): "
        )

    def test_a_pattern_reaching_both_is_the_ambiguity_it_always_was(self) -> None:
        _, bag = run(self.statics(), "Off*")
        (refused,) = [d for d in bag.sorted if d.check == "elf-symbol-ambiguous"]
        assert refused.message.startswith("'Offset' names a variable in 2 units, ")

    def test_the_first_is_left_out_with_the_second_so_that_neither_stands_for_the_name(
        self,
    ) -> None:
        description, _ = run(self.statics(), "io_a.c:Offset", "io_b.c:Offset")
        assert names(description) == []

    def test_a_name_asked_twice_in_one_spelling_is_one_variable(self) -> None:
        description, bag = run(image(stored("Offset", U16)), "Offset", "Offset")
        assert names(description) == ["Offset"]
        assert not bag.has_errors

    def test_the_internal_name_reaches_no_message_of_a_check_ddd_makes(self) -> None:
        img = image(stored("a-b", U16))
        _, bag = run(img, "a-b")
        assert bag.has_errors
        assert not [d for d in bag.sorted if "FromElf" in d.message]


class TestTheIdentityIsTheAuthors:
    """An image does not say that raw is physical, so by default no conversion is written for
    what is not an enum, and an option writes the identity where the author says so (finding
    1:M7)."""

    def variables(self) -> Image:
        return image(
            stored("Gain", U16, line=3),
            stored("State", STATE, address=0x104),
            stored("Pair", PAIR, address=0x108),
        )

    def test_by_default_a_scalar_states_no_conversion(self) -> None:
        description, _ = run(self.variables(), "Gain")
        assert "conversion" not in description.interface[0]["definition"]

    def test_by_default_an_enum_still_states_its_enumerators(self) -> None:
        description, _ = run(self.variables(), "State")
        assert description.interface[0]["definition"]["conversion"]["kind"] == "enum"

    def test_by_default_a_structure_s_members_state_none(self) -> None:
        description, _ = run(self.variables(), "Pair", component="Inlet")
        (entry,) = description.types
        assert entry["members"] == [
            {"name": "a", "member": "value", "datatype": "uint8"},
            {"name": "b", "member": "value", "datatype": "uint8"},
        ]

    def test_the_option_writes_the_identity_where_the_author_says_so(self) -> None:
        description, _ = run(self.variables(), "Gain", "Pair", identity=True)
        assert description.interface[0]["definition"]["conversion"] == IDENTITY
        assert description.types == (PAIR_ENTRY,)

    def test_the_entry_the_check_saw_is_not_changed_to_leave_the_identity_out(self) -> None:
        entry = copy.deepcopy(PAIR_ENTRY)
        unclaimed = _unclaimed_type(entry)
        assert entry == PAIR_ENTRY
        assert "conversion" not in unclaimed["members"][0]

    def test_the_run_says_what_it_left_out_and_why(self) -> None:
        _, bag = run(self.variables(), "Gain")
        assert found(bag) == [
            (
                "elf-not-inferred",
                Severity.INFO,
                "an image states no unit, description, limits, scaling or id, so the output "
                "states none: it states no conversion for what is not an enum either, since "
                "raw equalling physical is a claim about the data that an image does not make, "
                "and 'ddd check' asks its author to state it ('--identity-conversions' writes "
                "the identity, where you state it); the limits are the ones DDD derives, and "
                "'ddd id --assign' writes the ids",
            )
        ]

    def test_with_the_option_the_run_says_the_claim_is_the_author_s(self) -> None:
        _, bag = run(self.variables(), "Gain", identity=True)
        assert found(bag) == [
            (
                "elf-not-inferred",
                Severity.INFO,
                "an image states no unit, description, limits, scaling or id, so the output "
                "states none: every conversion but an enum's is the identity, which "
                "'--identity-conversions' writes on your word, since nothing in an image says "
                "that raw equals physical; the limits are the ones DDD derives, and "
                "'ddd id --assign' writes the ids",
            )
        ]

    def test_ddd_still_checks_the_identity_it_does_not_print(self) -> None:
        img = image(stored("Level", F32), contents=filled((0, struct.pack("<f", 1.5))))
        description, bag = run(img, "Level")
        assert names(description) == ["Level"]
        assert not bag.has_errors
