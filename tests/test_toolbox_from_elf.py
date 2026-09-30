"""The translator of ``ddd tool from-elf``, on hand-built images: which variables the
arguments name, how their types are spelled, their initial values, and DDD's own verdict on
the result. The reader has its own tests (``tests/test_elf.py``); here nothing is read from a
file, so every case is exactly the one its test names."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any, Literal

import pytest

from ddd.diagnostics import CHECKS, STANDALONE_POLICY, DiagnosticBag, Location, Severity, where
from ddd.elf import (
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
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
    NOT_INFERRED,
    VALUE_BLOCKS,
    Description,
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
    byte_order: Literal["little", "big"] = "little",
) -> Image:
    return Image(Path("hand.elf"), byte_order, variables, sections, symbols, contents)


def stored(
    name: str,
    ctype: CType = U8,
    *,
    unit: str = "unit.c",
    address: int | None = 0x100,
    line: int | None = None,
    missing: str = "",
) -> Variable:
    declared = Declared(unit, line) if line is not None else None
    return Variable(name, unit, ctype, declared, address, missing)


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
            stored("Twin", unit="unit_a.c", line=9),
            stored("Twin", unit="unit_b.c", line=8),
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
        img = image(stored("Twin", unit="unit_a.c"), stored("Twin", unit="unit_b.c"))
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


U16 = Base("short unsigned int", DW_ATE_UNSIGNED, 2)
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
        assert len(messages) == 1
        assert messages[0].startswith("'L_s.y' starts at bit 12 although it fits at bit 8")

    def test_a_member_whose_offset_is_unknown_leaves_the_next_unjudged(self) -> None:
        assert self.layout(Member("a", U8, None, 2), Member("b", U8, 5, 2)) == []


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
        assert shortest_float32(largest) == 3.4028235e38

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
    img: Image, *arguments: str, scope: str = "output", component: str | None = None
) -> tuple[Description, DiagnosticBag]:
    bag = DiagnosticBag()
    return describe(img, list(arguments), scope=scope, component=component, bag=bag), bag


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
                        "conversion": IDENTITY,
                        "init": 300,
                        "volatile": False,
                    },
                },
            ),
            (),
        )
        assert found(bag) == [("elf-not-inferred", Severity.INFO, NOT_INFERRED)]

    def test_a_definition_states_its_keys_in_the_examples_order(self) -> None:
        calib = Section(".calib", 0x100, 0x100, 0)
        img = image(
            stored("Table", Array(Qualified(U8, const=True), (2,))),
            sections=(calib,),
            contents=filled((0, bytes([1, 2]))),
        )
        description, _ = run(img, "Table")
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
                "conversion": IDENTITY,
                "volatile": False,
            },
        }
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]

    def test_a_local_states_its_storage_as_an_output_does(self) -> None:
        img = image(stored("Gain", U16), contents=filled((0, bytes([0x2C, 0x01]))))
        description, _ = run(img, "Gain", scope="local")
        assert description.interface[0]["scope"] == "local"
        assert description.interface[0]["definition"]["init"] == 300

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
        description, bag = run(img, "Config", component="Pump")
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
                "states none: every conversion but an enum's is the identity, the limits are "
                "the ones DDD derives, and 'ddd id --assign' writes the ids; and a const array "
                "is a value block, since nothing in an image tells a curve, a map or an axis "
                "from any other array",
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
