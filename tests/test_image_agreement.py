"""``elf-mismatch``: the image an a2l takes its addresses from, held to the description.

Finding 1:I12. The C a build compiles is written by templates the project owns and edited by
hand, so what the generator promises of it holds only of the shipped templates. The run that
reads the image sees the C that was compiled: each placed variable is compared on the size and
encoding of an element, the qualifiers its kind carries and its shape, as a warning, and a
variable that agrees is not said a word of.

Three layers, each asking what the others cannot. Images written by hand state every type a
compiler can make of one declaration, and the exact sentence of each difference; the address
fixtures' images, five toolchains each, hold the project as DDD generated it and twice as a
build could have gone wrong (``tests/fixtures/addresses/unqualified`` and ``.../widened``); and
``units-disagree.elf``, an image one name of which two units describe in two ways.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, messages, project, run_analysis, struct_type, types
from conftest import value_member as member_of
from ddd.addresses import addresses_from_image
from ddd.agreement import disagreements
from ddd.cli import EXIT_FINDINGS, EXIT_OK, main
from ddd.elf import (
    DECLARED_ONLY,
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    Array,
    Base,
    CType,
    Enum,
    Image,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
)
from ddd.ir import DataDictionary
from test_addresses import S8, S16, U8, U16, U32, image, stored
from test_cli import ADDRESS_FIXTURES, ADDRESS_PROJECT, ADDRESS_ROWS

FIXTURES = Path(__file__).parent / "fixtures" / "elf"

BOOL = Base("_Bool", DW_ATE_BOOLEAN, 1)
F32 = Base("float", DW_ATE_FLOAT, 4)
F64 = Base("double", DW_ATE_FLOAT, 8)
S32 = Base("int", DW_ATE_SIGNED, 4)
ENUM_U16 = Enum("Mode_e", 2, False, (("OFF", 0), ("ON", 1)))
ENUM_S16 = Enum("Mode_e", 2, True, (("OFF", 0), ("ON", -1)))
POINTER = Unsupported("a pointer")

UWORD = Typedef("UWORD", Typedef("uint16_t", U16))
"""What a platform header makes of ``unsigned short``: a name of the project's over the ISO one."""


def const(inner: CType) -> CType:
    return Qualified(inner, const=True)


def volatile(inner: CType) -> CType:
    return Qualified(inner, volatile=True)


def described(*declarations: dict[str, Any], tmp_path: Path, **files: Any) -> DataDictionary:
    """The dictionary of one component declaring ``declarations``."""
    dictionary, bag = run_analysis(
        tmp_path,
        {
            "project.ddd.json": project("P", "c.ddd.json", *files),
            "c.ddd.json": component("C", *declarations),
            **files,
        },
    )
    assert dictionary is not None, messages(bag)
    return dictionary


def judged(
    dictionary: DataDictionary, held: Image, *symbols: str
) -> tuple[list[str], list[tuple[str, ...]]]:
    """What the comparison says of ``symbols`` as ``held`` holds them: the sentences, and the
    notes of each."""
    placed = addresses_from_image(held, symbols)
    assert placed.reasons == {}
    found = disagreements(dictionary, placed, held)
    return [entry.message for entry in found], [entry.notes for entry in found]


def says(name: str, *differences: str) -> str:
    return f"'{name}' is not held by the image as its description states: " + "; ".join(differences)


def differs(what: str, stated: str, holds: str) -> str:
    return f"as its {what}, the description states {stated} and the image holds {holds}"


KIND = {
    "measurement": {},
    "volatile": {"volatile": True},
    "parameter": {"kind": "parameter"},
    "calibration that something else writes": {"kind": "parameter", "volatile": True},
    "block": {"kind": "value_block", "dimensions": [4]},
    "grid": {"dimensions": [2, 3]},
}


class TestAVariableTheImageHoldsAsDescribed:
    """The agreeing control, row by row: what a build of the generated C holds, in every
    spelling a compiler gives it. Each is silent."""

    @pytest.mark.parametrize(
        ("datatype", "definition", "held"),
        [
            ("uint16", {}, U16),
            ("uint16", {}, UWORD),
            ("uint16", {"volatile": True}, volatile(UWORD)),
            ("uint16", {"kind": "parameter"}, const(UWORD)),
            ("uint16", {"kind": "parameter"}, Typedef("CalWord", const(U16))),
            ("uint16", {"kind": "parameter", "volatile": True}, const(volatile(UWORD))),
            ("uint16", {"kind": "parameter", "volatile": True}, volatile(const(UWORD))),
            ("uint16", {"kind": "value_block", "dimensions": [4]}, Array(const(U16), (4,))),
            ("uint16", {"kind": "value_block", "dimensions": [4]}, const(Array(U16, (4,)))),
            ("uint16", {"dimensions": [2, 3]}, Array(U16, (2, 3))),
            ("uint16", {"dimensions": [2, 3]}, Array(Array(U16, (3,)), (2,))),
            ("uint16", {"dimensions": [2, 3]}, Array(Typedef("Row", Array(U16, (3,))), (2,))),
            ("uint8", {}, U8),
            ("sint8", {}, S8),
            ("sint16", {}, S16),
            ("sint32", {}, S32),
            ("uint32", {}, U32),
            ("boolean", {}, BOOL),
            ("boolean", {}, U8),
            ("float32", {}, F32),
            ("float64", {}, F64),
            ("uint16", {}, ENUM_U16),
            ("sint16", {}, ENUM_S16),
            ("uint16", {}, Unsupported("void")),
        ],
        ids=lambda value: value if isinstance(value, str) else "",
    )
    def test_it_is_not_said_a_word_of(
        self, tmp_path: Path, datatype: str, definition: dict[str, Any], held: CType
    ) -> None:
        dictionary = described(declare("local", "V", datatype, **definition), tmp_path=tmp_path)
        assert judged(dictionary, image(stored("V", held)), "V") == ([], [])

    def test_a_table_storing_its_counts_is_the_one_run_of_them_and_its_values(
        self, tmp_path: Path
    ) -> None:
        """``[1 + 4]`` for a curve of four points, as the generated C declares it."""
        dictionary, bag = run_analysis(
            tmp_path,
            {
                "project.ddd.json": project("P", "c.ddd.json", point_counts="leading"),
                "c.ddd.json": component(
                    "C",
                    declare("local", "AX", "uint16", kind="axis", size=4),
                    declare("local", "Cu", "uint16", kind="curve", axis="AX"),
                ),
            },
        )
        assert dictionary is not None, messages(bag)
        flat = image(
            stored("AX", const(Array(U16, (5,))), address=0x100),
            stored("Cu", const(Array(U16, (5,))), address=0x200),
        )
        assert judged(dictionary, flat, "AX", "Cu") == ([], [])
        nested = image(
            stored("AX", const(Array(U16, (4,))), address=0x100),
            stored("Cu", const(Array(U16, (5,))), address=0x200),
        )
        assert judged(dictionary, nested, "AX", "Cu")[0] == [
            says("AX", differs("shape", "[5]", "[4]"))
        ]

    def test_a_structure_and_each_member_it_places(self, tmp_path: Path) -> None:
        dictionary = described(
            declare("local", "S", typename="Sample_t", volatile=True, dimensions=[2]),
            tmp_path=tmp_path,
            **{"t.ddd.json": types(struct_type("Sample_t", member_of("raw", "uint16")))},
        )
        struct = Struct("Sample_t", 2, (Member("raw", U16, 0),))
        held = image(stored("S", volatile(Array(Typedef("Sample_t", struct), (2,)))))
        assert judged(dictionary, held, "S[0].raw", "S[1].raw") == ([], [])


class TestAVariableTheImageHoldsOtherwise:
    """What a template that leaves a qualifier out, a hand edit that widens a type or one that
    reshapes an array makes of the image, one sentence each."""

    def test_a_uint32_defined_for_a_uint16_declaration_differs_in_its_size(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(declare("local", "ValueE", "uint16"), tmp_path=tmp_path)
        held = image(stored("ValueE", Typedef("uint32_t", U32), address=0x2000_0100))
        assert judged(dictionary, held, "ValueE") == (
            [says("ValueE", differs("size", "2 bytes (uint16)", "4 bytes (uint32_t)"))],
            [
                (
                    "the a2l is written from the description, so a calibration tool reads this "
                    "variable as the image does not hold it",
                )
            ],
        )

    @pytest.mark.parametrize(
        ("datatype", "held", "differences"),
        [
            (
                "uint16",
                S16,
                [differs("encoding", "an unsigned integer", "a signed integer")],
            ),
            (
                "sint16",
                U16,
                [differs("encoding", "a signed integer", "an unsigned integer")],
            ),
            (
                "float32",
                U32,
                [differs("encoding", "a floating point number", "an unsigned integer")],
            ),
            (
                "uint32",
                F32,
                [differs("encoding", "an unsigned integer", "a floating point number")],
            ),
            (
                "boolean",
                S8,
                [differs("encoding", "a boolean", "a signed integer")],
            ),
            (
                "uint8",
                BOOL,
                [differs("encoding", "an unsigned integer", "a boolean")],
            ),
            (
                "uint16",
                ENUM_S16,
                [differs("encoding", "an unsigned integer", "a signed integer enumeration")],
            ),
            (
                "float64",
                U32,
                [
                    differs("size", "8 bytes (float64)", "4 bytes (unsigned int)"),
                    differs("encoding", "a floating point number", "an unsigned integer"),
                ],
            ),
        ],
        ids=[
            "unsigned declared signed",
            "signed declared unsigned",
            "float declared an integer",
            "integer declared a float",
            "boolean declared a signed byte",
            "unsigned byte declared a boolean",
            "an enumeration of the other sign",
            "size and encoding at once",
        ],
    )
    def test_an_encoding_or_both_it_and_the_size(
        self, tmp_path: Path, datatype: str, held: CType, differences: list[str]
    ) -> None:
        dictionary = described(declare("local", "V", datatype), tmp_path=tmp_path)
        assert judged(dictionary, image(stored("V", held)), "V")[0] == [says("V", *differences)]

    @pytest.mark.parametrize(
        ("definition", "held", "stated", "holds"),
        [
            ({"kind": "parameter"}, U16, "const", "none"),
            ({"volatile": True}, U16, "volatile", "none"),
            ({"kind": "parameter", "volatile": True}, const(U16), "const volatile", "const"),
            ({"kind": "parameter", "volatile": True}, volatile(U16), "const volatile", "volatile"),
            ({}, const(U16), "none", "const"),
            ({}, volatile(U16), "none", "volatile"),
            ({"kind": "parameter"}, volatile(Typedef("T", U16)), "const", "volatile"),
            ({"kind": "value_block", "dimensions": [4]}, Array(U16, (4,)), "const", "none"),
        ],
        ids=[
            "calibration without const",
            "volatile dropped",
            "const volatile without volatile",
            "const volatile without const",
            "a measurement made const",
            "a measurement made volatile",
            "the other one of the two",
            "the elements of an array",
        ],
    )
    def test_the_qualifiers_of_the_kind(
        self,
        tmp_path: Path,
        definition: dict[str, Any],
        held: CType,
        stated: str,
        holds: str,
    ) -> None:
        dictionary = described(declare("local", "V", "uint16", **definition), tmp_path=tmp_path)
        said, _ = judged(dictionary, image(stored("V", held)), "V")
        assert said == [says("V", differs("qualifiers", stated, holds))]

    @pytest.mark.parametrize(
        ("definition", "held", "stated", "holds"),
        [
            ({"dimensions": [4]}, U16, "[4]", "a scalar"),
            ({}, Array(U16, (4,)), "a scalar", "[4]"),
            ({"dimensions": [4]}, Array(U16, (5,)), "[4]", "[5]"),
            ({"dimensions": [4]}, Array(U16, (2, 2)), "[4]", "[2][2]"),
            ({"dimensions": [2, 3]}, Array(U16, (6,)), "[2][3]", "[6]"),
            ({"dimensions": [2, 3]}, Array(U16, (3, 2)), "[2][3]", "[3][2]"),
        ],
        ids=[
            "an array that is a scalar",
            "a scalar that is an array",
            "one extent longer",
            "one dimension that is two",
            "two dimensions that are one",
            "the extents the other way round",
        ],
    )
    def test_the_shape(
        self,
        tmp_path: Path,
        definition: dict[str, Any],
        held: CType,
        stated: str,
        holds: str,
    ) -> None:
        dictionary = described(declare("local", "V", "uint16", **definition), tmp_path=tmp_path)
        said, _ = judged(dictionary, image(stored("V", held)), "V")
        assert said == [says("V", differs("shape", stated, holds))]

    def test_every_difference_of_a_variable_is_one_sentence_in_a_fixed_order(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(
            declare("local", "V", "uint16", kind="value_block", dimensions=[4]), tmp_path=tmp_path
        )
        held = image(stored("V", Array(volatile(S32), (2,))))
        assert judged(dictionary, held, "V")[0] == [
            says(
                "V",
                differs("size", "2 bytes (uint16)", "4 bytes (int)"),
                differs("encoding", "an unsigned integer", "a signed integer"),
                differs("shape", "[4]", "[2]"),
                differs("qualifiers", "const", "volatile"),
            )
        ]

    @pytest.mark.parametrize(
        ("datatype", "held", "what"),
        [
            ("uint32", POINTER, "a pointer"),
            ("uint32", Struct("Pair_s", 4, ()), "struct Pair_s"),
            ("uint32", Typedef("Pair_t", Struct(None, 4, ())), "Pair_t"),
        ],
        ids=["a pointer", "a structure", "a typedef of an anonymous structure"],
    )
    def test_a_type_that_is_no_number(
        self, tmp_path: Path, datatype: str, held: CType, what: str
    ) -> None:
        dictionary = described(declare("local", "V", datatype), tmp_path=tmp_path)
        said, _ = judged(dictionary, image(stored("V", held)), "V")
        assert said == [says("V", differs("type", "uint32", f"{what}, which is not a number"))]

    def test_the_type_is_spelled_as_the_source_names_it_outermost_typedef_first(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(declare("local", "V", "uint16"), tmp_path=tmp_path)
        wide = Typedef("UWORD", Typedef("uint32_t", U32))
        said, _ = judged(dictionary, image(stored("V", wide)), "V")
        assert said == [says("V", differs("size", "2 bytes (uint16)", "4 bytes (UWORD)"))]

    def test_the_variables_come_in_the_order_of_their_names_whatever_the_order_asked(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(
            declare("local", "B", "uint16"), declare("local", "A", "uint16"), tmp_path=tmp_path
        )
        held = image(stored("A", U32, address=0x100), stored("B", U32, address=0x200))
        said, _ = judged(dictionary, held, "B", "A")
        assert [text.split("'")[1] for text in said] == ["A", "B"]

    @pytest.mark.parametrize(
        ("definition", "held", "differences", "note"),
        [
            ({"volatile": True}, U16, [differs("qualifiers", "volatile", "none")], "qualifier"),
            (
                {"volatile": True},
                U32,
                [
                    differs("size", "2 bytes (uint16)", "4 bytes (unsigned int)"),
                    differs("qualifiers", "volatile", "none"),
                ],
                "a2l",
            ),
            ({}, Array(U16, (2,)), [differs("shape", "a scalar", "[2]")], "a2l"),
        ],
        ids=["a qualifier alone", "a qualifier beside a size", "a shape alone"],
    )
    def test_the_note_says_what_follows_from_what_differs(
        self,
        tmp_path: Path,
        definition: dict[str, Any],
        held: CType,
        differences: list[str],
        note: str,
    ) -> None:
        """No reader of the a2l misreads a qualifier, which the a2l does not carry: the code is
        what changes. A size, an encoding or a shape is read wrongly from the a2l."""
        dictionary = described(declare("local", "V", "uint16", **definition), tmp_path=tmp_path)
        said, notes = judged(dictionary, image(stored("V", held)), "V")
        assert said == [says("V", *differences)]
        assert notes == [
            (
                {
                    "qualifier": "the a2l carries no qualifier, so what differs is the code "
                    "compiled from this definition, which treats the variable as the image "
                    "holds it",
                    "a2l": "the a2l is written from the description, so a calibration tool "
                    "reads this variable as the image does not hold it",
                }[note],
            )
        ]

    @pytest.mark.parametrize(
        ("datatype", "held", "stated", "holds"),
        [
            ("uint8", U16, "1 byte (uint8)", "2 bytes (short unsigned int)"),
            ("uint16", U8, "2 bytes (uint16)", "1 byte (unsigned char)"),
            ("uint16", Enum("Mode_e", 4, False, ()), "2 bytes (uint16)", "4 bytes (enum Mode_e)"),
            ("uint16", Enum(None, 4, False, ()), "2 bytes (uint16)", "4 bytes (an enumeration)"),
        ],
        ids=[
            "one byte declared",
            "one byte held",
            "a tagged enumeration",
            "an anonymous enumeration",
        ],
    )
    def test_a_size_is_spelled_in_the_singular_for_one_and_a_type_as_the_source_names_it(
        self, tmp_path: Path, datatype: str, held: CType, stated: str, holds: str
    ) -> None:
        dictionary = described(declare("local", "V", datatype), tmp_path=tmp_path)
        said, _ = judged(dictionary, image(stored("V", held)), "V")
        assert said == [says("V", differs("size", stated, holds))]

    def test_a_structure_without_a_tag_or_a_typedef_is_a_structure(self, tmp_path: Path) -> None:
        dictionary = described(declare("local", "V", "uint32"), tmp_path=tmp_path)
        said, _ = judged(dictionary, image(stored("V", Struct(None, 4, ()))), "V")
        assert said == [says("V", differs("type", "uint32", "a structure, which is not a number"))]

    def test_a_base_type_that_is_no_integer_nor_float_is_named_by_its_encoding(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(declare("local", "V", "float64"), tmp_path=tmp_path)
        complex_float = Base("complex double", DW_ATE_COMPLEX_FLOAT, 8)
        said, _ = judged(dictionary, image(stored("V", complex_float)), "V")
        assert said == [
            says(
                "V",
                differs("encoding", "a floating point number", "a base type of DWARF encoding 0x3"),
            )
        ]

    def test_the_declaration_the_image_names_is_a_note(self, tmp_path: Path) -> None:
        from ddd.elf import Declared

        dictionary = described(declare("local", "V", "uint16"), tmp_path=tmp_path)
        variable = Variable(
            "V", "u.c", U32, Declared("src/ddd_globals.c", 12), address=0x100, external=True
        )
        _, notes = judged(dictionary, image(variable), "V")
        assert notes[0][1:] == (
            "the image's debug information declares it at src/ddd_globals.c:12",
        )


class TestAStructuredVariable:
    """It is held to the qualifiers and the shape of the whole variable, and each member it
    places to the datatype and the shape the member states."""

    SAMPLE = Struct("Sample_t", 4, (Member("raw", U16, 0), Member("seen", Array(U8, (2,)), 16)))

    def dictionary(self, tmp_path: Path, **definition: Any) -> DataDictionary:
        sample = struct_type(
            "Sample_t", member_of("raw", "uint16"), member_of("seen", "uint8", dimensions=[2])
        )
        return described(
            declare("local", "S", typename="Sample_t", **definition),
            tmp_path=tmp_path,
            **{"t.ddd.json": types(sample)},
        )

    def test_a_member_of_another_size_is_named_by_its_path(self, tmp_path: Path) -> None:
        wide = Struct("Sample_t", 8, (Member("raw", U32, 0), Member("seen", Array(U8, (2,)), 32)))
        said, _ = judged(self.dictionary(tmp_path), image(stored("S", wide)), "S.raw", "S.seen")
        assert said == [
            says("S.raw", differs("size", "2 bytes (uint16)", "4 bytes (unsigned int)"))
        ]

    def test_a_member_of_another_shape_is_named_by_its_path(self, tmp_path: Path) -> None:
        longer = Struct("Sample_t", 6, (Member("raw", U16, 0), Member("seen", Array(U8, (4,)), 16)))
        said, _ = judged(self.dictionary(tmp_path), image(stored("S", longer)), "S.raw", "S.seen")
        assert said == [says("S.seen", differs("shape", "[2]", "[4]"))]

    def test_the_variable_is_held_to_its_qualifiers_and_shape(self, tmp_path: Path) -> None:
        dictionary = self.dictionary(tmp_path, volatile=True, dimensions=[2])
        held = image(stored("S", Array(self.SAMPLE, (3,))))
        said, _ = judged(dictionary, held, "S[0].raw")
        assert said == [
            says(
                "S",
                differs("shape", "[2]", "[3]"),
                differs("qualifiers", "volatile", "none"),
            )
        ]

    def test_the_variable_and_a_member_are_two_sentences(self, tmp_path: Path) -> None:
        dictionary = self.dictionary(tmp_path, volatile=True)
        wide = Struct("Sample_t", 8, (Member("raw", U32, 0), Member("seen", Array(U8, (2,)), 32)))
        said, _ = judged(dictionary, image(stored("S", wide)), "S.raw")
        assert said == [
            says("S", differs("qualifiers", "volatile", "none")),
            says("S.raw", differs("size", "2 bytes (uint16)", "4 bytes (unsigned int)")),
        ]

    def test_the_members_come_in_the_order_of_their_paths_whatever_the_order_asked(
        self, tmp_path: Path
    ) -> None:
        wide = Struct("Sample_t", 8, (Member("raw", U32, 0), Member("seen", Array(U8, (4,)), 32)))
        said, _ = judged(self.dictionary(tmp_path), image(stored("S", wide)), "S.seen", "S.raw")
        assert [text.split("'")[1] for text in said] == ["S.raw", "S.seen"]


class TestUnitsOfHandBuiltImages:
    """The same account where the image states fewer things than a linked one does."""

    def said(self, tmp_path: Path, *variables: Variable, sizes: dict[tuple[str, int], int]) -> str:
        dictionary = described(declare("local", "V", "uint16"), tmp_path=tmp_path)
        held = image(*variables)
        with_sizes = Image(
            held.path,
            held.byte_order,
            held.variables,
            held.sections,
            held.symbols,
            b"",
            held.objects,
            object_sizes=sizes,
        )
        (said,), _ = judged(dictionary, with_sizes, "V")
        return said

    def test_two_units_with_no_symbol_size_are_two_descriptions(self, tmp_path: Path) -> None:
        said = self.said(
            tmp_path,
            stored("V", U16, unit="a.c"),
            stored("V", U32, unit="b.c"),
            sizes={},
        )
        assert said == (
            "'V' at 0x100 is described by the image as 2 bytes by 'a.c' and as 4 bytes by "
            "'b.c': one name at one address is one variable, so the description is held to none "
            "of them"
        )

    def test_a_single_byte_is_one_byte_in_the_account_too(self, tmp_path: Path) -> None:
        said = self.said(
            tmp_path, stored("V", U8, unit="a.c"), stored("V", U16, unit="b.c"), sizes={}
        )
        assert "as 1 byte by 'a.c' and as 2 bytes by 'b.c'" in said

    def test_a_unit_whose_description_has_no_size_says_nothing_of_one(self, tmp_path: Path) -> None:
        said = self.said(
            tmp_path,
            stored("V", U32, unit="a.c"),
            stored("V", Unsupported("a union"), unit="b.c"),
            sizes={("V", 0x100): 8},
        )
        assert said == (
            "'V' at 0x100 is described by the image as 4 bytes by 'a.c' and as 8 bytes by the "
            "symbol table: one name at one address is one variable, so the description is held "
            "to none of them"
        )


UNITS = FIXTURES / "units-disagree.elf"


def run_generate(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, image_path: Path, *extra: str
) -> tuple[int, str]:
    """``ddd generate a2l`` of the address fixtures' project, or the one a test wrote, out of
    ``image_path``: the exit code and what it said."""
    project_file = tmp_path / "project" / "project.ddd.json"
    if not project_file.is_file():
        project_file = ADDRESS_PROJECT
    arguments = ["generate", "a2l", str(project_file), "-o", str(tmp_path / "gen")]
    code = main([*arguments, "--image", str(image_path), *extra])
    return code, capsys.readouterr().err


def write_project(tmp_path: Path, *declarations: dict[str, Any]) -> None:
    (tmp_path / "project").mkdir()
    files = {
        "project.ddd.json": project("P", "c.ddd.json"),
        "c.ddd.json": component("C", *declarations),
    }
    for name, content in files.items():
        (tmp_path / "project" / name).write_text(json.dumps(content), encoding="utf-8")


class TestUnitsThatDescribeOneVariableInTwoWays:
    """The ``--image`` half of finding 11:M6, over ``units-disagree.elf``: two units stating one
    name at one address in two sizes, which the run says rather than compare against whichever
    unit came first."""

    def address(self, name: str) -> int:
        from ddd.elf import open_image

        (address,) = {
            variable.address for variable in open_image(UNITS).variables if variable.name == name
        }
        assert address is not None
        return address

    def test_each_name_the_units_disagree_on_is_said_once_and_held_to_no_description(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Declared as the first unit has it (``Disagree_Cal`` two bytes), as the second has it
        (``Disagree_Shared`` four elements, a weak definition of two bytes overridden by a strong
        one of four) and as neither does: each is said, and none is held to a unit."""
        write_project(
            tmp_path,
            declare("local", "Disagree_Cal", "uint16"),
            declare("local", "Disagree_Shared", "uint32", dimensions=[4]),
            declare("local", "Disagree_Weak", "uint32"),
        )
        code, said = run_generate(capsys, tmp_path, UNITS)
        assert code == EXIT_OK, said
        shown = re.findall(r"warning\[elf-mismatch\]: (.*)", said)
        tail = (
            ": one name at one address is one variable, so the description is held to none of them"
        )
        assert shown == [
            f"'Disagree_Cal' at {self.address('Disagree_Cal'):#x} is described by the image as 2 "
            f"bytes by 'disagree_a.c' and as 4 bytes by 'disagree_b.c' and the symbol table{tail}",
            f"'Disagree_Shared' at {self.address('Disagree_Shared'):#x} is described by the "
            f"image as 8 bytes by 'disagree_a.c' and as 16 bytes by 'disagree_b.c' and the "
            f"symbol table{tail}",
            f"'Disagree_Weak' at {self.address('Disagree_Weak'):#x} is described by the image "
            f"as 2 bytes by 'disagree_a.c' and as 4 bytes by 'disagree_b.c' and the symbol "
            f"table{tail}",
        ]
        assert "3 warnings" in said

    @pytest.mark.parametrize(("datatype", "said_of"), [("uint32", False), ("uint16", True)])
    def test_the_name_they_agree_on_is_compared_as_any_other(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], datatype: str, said_of: bool
    ) -> None:
        """``Disagree_Agreed`` is four bytes in both units: a uint32 agrees, a uint16 does not."""
        write_project(tmp_path, declare("local", "Disagree_Agreed", datatype))
        code, said = run_generate(capsys, tmp_path, UNITS)
        assert code == EXIT_OK
        mismatch = differs("size", "2 bytes (uint16)", "4 bytes (uint32_t)")
        assert (mismatch in said, "described by the image" in said) == (said_of, False)


def definition_line(variant: str, name: str) -> int:
    """The line of ``name``'s definition in the generated C a variant's images were built from."""
    lines = (ADDRESS_FIXTURES / variant / "ddd_globals.c").read_text(encoding="utf-8").splitlines()
    (line,) = [
        number
        for number, text in enumerate(lines, start=1)
        if re.search(rf"\b{name}\b(\[.*\])?( = .*)?;$", text)
    ]
    return line


QUALIFIERS = {
    "Enabled": "const",
    "Gain": "const volatile",
    "Inlet": "volatile",
    "Limit": "const",
    "Speed": "volatile",
    "Status": "volatile",
    "Table": "const",
    "Ticks": "volatile",
    "Tuning": "const volatile",
}
"""What the project's descriptions give a variable of the address fixtures that carries a
qualifier, as its kind and its ``volatile`` say; the other fourteen carry none."""

QUALIFIER_NOTE = (
    "    note: the a2l carries no qualifier, so what differs is the code compiled from this "
    "definition, which treats the variable as the image holds it\n"
)
NOTE = (
    "    note: the a2l is written from the description, so a calibration tool reads this "
    "variable as the image does not hold it\n"
)


class TestTheImagesOfTheAddressFixtures:
    """Five toolchains' images of the project: as DDD generated it, and twice as a build could
    have gone wrong."""

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_the_project_as_it_was_generated_is_not_said_a_word_of(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        """The agreeing control, strict: every placed variable and member, bitfields' units and
        two dimensions of structures among them."""
        code, said = run_generate(capsys, tmp_path, ADDRESS_FIXTURES / f"{row}.elf", "--strict")
        assert code == EXIT_OK, said
        assert "elf-mismatch" not in said

    def said(self, tmp_path: Path, row: str, image_path: Path, findings: str, warnings: int) -> str:
        """What the run says of a variant's image: its warnings, then the one finding of a
        position independent image where the row is one, the count, and the a2l it writes."""
        shown = where_of(image_path)
        noted = LOAD_RELATIVE.format(shown) if row == "x86_64" else ""
        count = f"{warnings} warning{'s' if warnings != 1 else ''}"
        count += ", 1 info" if row == "x86_64" else ""
        a2l = tmp_path / "gen" / "AddressFixture.a2l"
        return f"{findings}{noted}{count}\nwrote       {a2l.as_posix()} (created)\n"

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_template_leaving_out_the_qualifiers_of_the_kinds_is_said_for_each_variable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        image_path = ADDRESS_FIXTURES / "unqualified" / f"{row}.elf"
        code, said = run_generate(capsys, tmp_path, image_path)
        assert code == EXIT_OK, "a warning: the a2l is written, with the addresses it was asked"
        findings = "".join(
            f"{where_of(image_path)}: warning[elf-mismatch]: '{name}' is not held by the image as "
            f"its description states: as its qualifiers, the description states {stated} and the "
            f"image holds none\n{QUALIFIER_NOTE}"
            f"    note: the image's debug information declares it at "
            f"unqualified/ddd_globals.c:{definition_line('unqualified', name)}\n"
            for name, stated in QUALIFIERS.items()
        )
        assert said == self.said(tmp_path, row, image_path, findings, len(QUALIFIERS))

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_uint32_defined_for_a_uint16_is_said_with_both_sizes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        image_path = ADDRESS_FIXTURES / "widened" / f"{row}.elf"
        code, said = run_generate(capsys, tmp_path, image_path)
        assert code == EXIT_OK
        finding = (
            f"{where_of(image_path)}: warning[elf-mismatch]: 'Speed' is not held by the image as "
            "its description states: as its size, the description states 2 bytes (uint16) and "
            f"the image holds 4 bytes (uint32_t)\n{NOTE}"
            f"    note: the image's debug information declares it at "
            f"widened/ddd_globals.c:{definition_line('widened', 'Speed')}\n"
        )
        assert said == self.said(tmp_path, row, image_path, finding, 1)

    def test_a_strict_build_stops_at_it_and_writes_no_a2l(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        image_path = ADDRESS_FIXTURES / "widened" / "armv7m.elf"
        code, said = run_generate(capsys, tmp_path, image_path, "--strict")
        assert code == EXIT_FINDINGS
        assert "error[elf-mismatch]: 'Speed'" in said
        assert not (tmp_path / "gen" / "AddressFixture.a2l").exists()

    def test_the_finding_is_one_a_severity_override_may_state_or_silence(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        image_path = ADDRESS_FIXTURES / "widened" / "armv7m.elf"
        code, said = run_generate(
            capsys, tmp_path, image_path, "--strict", "-W", "elf-mismatch=ignore"
        )
        assert (code, said.startswith("wrote")) == (EXIT_OK, True)
        code, said = run_generate(capsys, tmp_path, image_path, "-W", "elf-mismatch=info")
        assert "info[elf-mismatch]: 'Speed'" in said

    def test_the_json_report_carries_the_check_and_its_notes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        image_path = ADDRESS_FIXTURES / "widened" / "armv7m.elf"
        project_file = str(ADDRESS_PROJECT)
        output = str(tmp_path / "gen")
        arguments = ["generate", "a2l", project_file, "-o", output, "--image", str(image_path)]
        assert main([*arguments, "--format", "json"]) == EXIT_OK
        report = json.loads(capsys.readouterr().out)
        (found,) = [entry for entry in report["diagnostics"] if entry["check"] == "elf-mismatch"]
        assert found["severity"] == "warning"
        assert found["notes"][0]["message"].startswith("the a2l is written from the description")


CONSUMED = {
    "Enabled": "const",
    "Gain": "const volatile",
    "Inlet": "volatile",
    "Limit": "const",
    "Speed": "volatile",
    "Table": "const",
    "Tuning": "const volatile",
}
"""What the description says of each variable ``consumer.c`` reads, as its kind and ``volatile``
say; the finding's trigger is the ones that carry ``volatile``."""

GCC_ROWS = ["armv7m", "i686", "powerpc", "x86_64"]
"""The rows whose compiler states a unit's declaration of a variable another unit defines in its
debug information. clang's, on ``aarch64_be``, leaves it out, so what a consumer's header says
cannot be seen there."""


def declaration_line(variant: str, name: str) -> int:
    lines = (ADDRESS_FIXTURES / variant / "Engine.h").read_text(encoding="utf-8").splitlines()
    (line,) = [
        number
        for number, text in enumerate(lines, start=1)
        if re.match(rf"extern .*\b{name}\b(\[.*\])?;", text)
    ]
    return line


class TestAConsumersDeclaration:
    """The finding's own trigger: a component header whose ``extern`` leaves out the qualifiers of
    the kind, compiled into a unit that reads the variable (``tests/fixtures/addresses/
    consumer.c``). The definition is right; what a poll on ``Speed`` compiles to is decided by the
    declaration the consumer sees."""

    @pytest.mark.parametrize("row", GCC_ROWS)
    def test_a_header_leaving_out_the_qualifiers_is_said_for_each_variable_the_unit_reads(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        image_path = ADDRESS_FIXTURES / "lostqualifier" / f"{row}.elf"
        code, said = run_generate(capsys, tmp_path, image_path)
        assert code == EXIT_OK
        findings = "".join(
            f"{where_of(image_path)}: warning[elf-mismatch]: '{name}' is declared in "
            f"'consumer.c' otherwise than its description states: as its qualifiers, the "
            f"description states {stated} and the declaration holds none\n"
            "    note: a unit that reads the variable through such a declaration is compiled "
            "without the qualifiers the description gives it\n"
            f"    note: the image's debug information declares it at "
            f"lostqualifier/Engine.h:{declaration_line('lostqualifier', name)}\n"
            for name, stated in CONSUMED.items()
        )
        count = f"{len(CONSUMED)} warnings" + (", 1 info" if row == "x86_64" else "")
        noted = LOAD_RELATIVE.format(where_of(image_path)) if row == "x86_64" else ""
        a2l = tmp_path / "gen" / "AddressFixture.a2l"
        assert said == f"{findings}{noted}{count}\nwrote       {a2l.as_posix()} (created)\n"

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_header_that_adds_const_as_const_inputs_does_is_not_said_a_word_of(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        """``declaration(const=True)``, which is what ``--const-inputs`` gives an input: every
        variable the unit reads gains ``const`` and keeps what the kind carries."""
        image_path = ADDRESS_FIXTURES / "constinputs" / f"{row}.elf"
        code, said = run_generate(capsys, tmp_path, image_path, "--strict")
        assert code == EXIT_OK, said
        assert "elf-mismatch" not in said

    def test_the_clang_row_states_no_declaration_so_it_is_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        image_path = ADDRESS_FIXTURES / "lostqualifier" / "aarch64_be.elf"
        code, said = run_generate(capsys, tmp_path, image_path)
        assert (code, "elf-mismatch" in said) == (EXIT_OK, False)

    def declared(self, tmp_path: Path, stated: dict[str, Any], seen: CType) -> list[str]:
        """What is said of ``V`` defined as the description states and declared by ``c.c`` as
        ``seen``."""
        dictionary = described(declare("local", "V", "uint16", **stated), tmp_path=tmp_path)
        defined: CType = U16
        if stated.get("kind") == "parameter":
            defined = const(defined)
        if stated.get("volatile"):
            defined = volatile(defined)
        definition = stored("V", defined)
        declaration = Variable("V", "c.c", seen, None, None, DECLARED_ONLY, True)
        held = replace(image(definition), declarations=(declaration,))
        return judged(dictionary, held, "V")[0]

    @pytest.mark.parametrize(
        ("stated", "seen", "says_held"),
        [
            ({"volatile": True}, U16, "none"),
            ({"volatile": True}, const(U16), "const"),
            ({}, volatile(U16), "volatile"),
            ({"kind": "parameter"}, U16, "none"),
            ({"kind": "parameter"}, volatile(U16), "volatile"),
            ({"kind": "parameter", "volatile": True}, const(U16), "const"),
        ],
        ids=[
            "volatile lost",
            "volatile lost beside const added",
            "volatile added",
            "const lost",
            "const lost beside volatile added",
            "const volatile losing volatile",
        ],
    )
    def test_every_difference_but_an_added_const_is_said(
        self, tmp_path: Path, stated: dict[str, Any], seen: CType, says_held: str
    ) -> None:
        wanted = (
            ("const " if stated.get("kind") == "parameter" else "")
            + ("volatile" if stated.get("volatile") else "")
        ).strip() or "none"
        assert self.declared(tmp_path, stated, seen) == [
            f"'V' is declared in 'c.c' otherwise than its description states: as its "
            f"qualifiers, the description states {wanted} and the declaration holds {says_held}"
        ]

    @pytest.mark.parametrize(
        ("stated", "seen"),
        [
            ({}, U16),
            ({}, const(U16)),
            ({"volatile": True}, volatile(U16)),
            ({"volatile": True}, const(volatile(UWORD))),
            ({"kind": "parameter"}, const(U16)),
            ({"volatile": True}, Unsupported("void")),
        ],
        ids=[
            "same",
            "const added",
            "volatile kept",
            "const added to volatile",
            "const kept",
            "untyped",
        ],
    )
    def test_what_agrees_or_adds_const_is_not_said(
        self, tmp_path: Path, stated: dict[str, Any], seen: CType
    ) -> None:
        assert self.declared(tmp_path, stated, seen) == []

    def test_a_variable_the_units_disagree_on_is_not_held_through_its_declarations(
        self, tmp_path: Path
    ) -> None:
        dictionary = described(declare("local", "V", "uint16", volatile=True), tmp_path=tmp_path)
        declaration = Variable("V", "c.c", U16, None, None, DECLARED_ONLY, True)
        held = replace(
            image(stored("V", U16, unit="a.c"), stored("V", U32, unit="b.c")),
            declarations=(declaration,),
        )
        said, _ = judged(dictionary, held, "V")
        assert len(said) == 1
        assert "described by the image" in said[0]

    def test_a_structured_variable_is_held_through_its_declarations_as_well(
        self, tmp_path: Path
    ) -> None:
        sample = struct_type("Sample_t", member_of("raw", "uint16"))
        dictionary = described(
            declare("local", "S", typename="Sample_t", volatile=True),
            tmp_path=tmp_path,
            **{"t.ddd.json": types(sample)},
        )
        struct = Struct("Sample_t", 2, (Member("raw", U16, 0),))
        declaration = Variable("S", "c.c", struct, None, None, DECLARED_ONLY, True)
        held = replace(image(stored("S", volatile(struct))), declarations=(declaration,))
        said, _ = judged(dictionary, held, "S.raw")
        assert said == [
            "'S' is declared in 'c.c' otherwise than its description states: as its "
            "qualifiers, the description states volatile and the declaration holds none"
        ]


LOAD_RELATIVE = (
    "{}: info[image-load-relative]: the image is position independent, so the addresses the "
    "a2l states are offsets from where it loads\n"
    "    note: a project that adds its load base when it reads the a2l is right, and one that "
    "does not finds every address wrong\n"
)


def where_of(image_path: Path) -> str:
    from ddd.diagnostics import where

    return where(image_path).render(Path.cwd())
