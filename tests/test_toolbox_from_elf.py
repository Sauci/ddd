"""The translator of ``ddd tool from-elf``, on hand-built images: which variables the
arguments name, how their types are spelled, their initial values, and DDD's own verdict on
the result. The reader has its own tests (``tests/test_elf.py``); here nothing is read from a
file, so every case is exactly the one its test names."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pytest

from ddd.diagnostics import CHECKS, DiagnosticBag, Location, Severity, where
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
from ddd.toolbox.findings import FINDINGS, place, report
from ddd.toolbox.mapping import Mapper, Shape, Typed, datatype_of, described, shape_of
from ddd.toolbox.selection import Wanted, select, wanted

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
