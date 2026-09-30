"""The translator of ``ddd tool from-elf``, on hand-built images: which variables the
arguments name, how their types are spelled, their initial values, and DDD's own verdict on
the result. The reader has its own tests (``tests/test_elf.py``); here nothing is read from a
file, so every case is exactly the one its test names."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from ddd.diagnostics import CHECKS, DiagnosticBag, Location, Severity, where
from ddd.elf import (
    DW_ATE_UNSIGNED_CHAR,
    Base,
    CType,
    Declared,
    Image,
    Section,
    Variable,
)
from ddd.toolbox.findings import FINDINGS, place, report
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
