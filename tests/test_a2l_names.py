"""What the a2l format forbids in a name, and what it caps in a string or an identifier.

A name that is a keyword of ASAP2 1.6.1 is refused (``a2l-keyword``, an error), because the
standard keeps identifiers off its index of keywords and enum values and a tool may drop a
record it cannot resolve. A string past ``MAX_STRING`` 255, an identifier past ``MAX_IDENT``
1024 and a partial identifier past ``MAX_PARTIAL_IDENT`` 128 are ``a2l-unrepresentable``, a
warning: the file is still written, and the standard's letter is what it breaks.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from conftest import (
    bits_member,
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    scalar_type,
    struct_type,
    types,
    value_member,
)
from ddd.backends import a2l as a2l_package
from ddd.backends.a2l.model import _RecordLayoutBuilder
from ddd.diagnostics import DiagnosticBag
from ddd.models import Datatype, ObjectKind
from ddd.models.a2l_keywords import A2L_KEYWORDS, IDENTITY_METHOD_PREFIX, is_a2l_keyword


def run(tree: Path, *declarations: dict[str, Any]) -> DiagnosticBag:
    files = {
        "project.ddd.json": project("Device", "a.ddd.json"),
        "a.ddd.json": component("A", *declarations),
    }
    return run_analysis(tree, files)[1]


def over(tree: Path, files: dict[str, Any]) -> DiagnosticBag:
    return run_analysis(tree, files)[1]


def at(bag: DiagnosticBag, check: str) -> list[str]:
    """The findings of one check, rendered with the file named relative to the project."""
    return [d.render().rsplit("/", 1)[-1] for d in bag if d.check == check]


class TestTheKeywordList:
    def test_it_holds_the_index_the_review_named(self) -> None:
        for word in ("MAP", "VALUE", "IDENTICAL", "ROOT", "MODULE", "UBYTE", "RAT_FUNC"):
            assert is_a2l_keyword(word)

    def test_a_keyword_is_matched_exactly(self) -> None:
        """ASAP2 is case sensitive: ``Map`` and ``map`` are names, ``MAP`` is the keyword."""
        assert not is_a2l_keyword("map")
        assert not is_a2l_keyword("Map")
        assert not is_a2l_keyword("MAP_1")

    def test_it_holds_every_word_the_template_writes(self) -> None:
        """What DDD's own a2l spells in capitals is the format's, so it is in the list."""
        source = (Path(a2l_package.__file__).parent / "templates" / "project.a2l.jinja").read_text(
            encoding="utf-8"
        )
        source = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", source)
        source = re.sub(r'"[^"]*"', " ", source)
        source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
        # the XCP block's words are the metalanguage's, not ASAP2's
        source = re.sub(r"/begin IF_DATA.*?/end IF_DATA", " ", source, flags=re.DOTALL)
        words = set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", source))
        assert words
        assert words - A2L_KEYWORDS == set()

    def test_the_words_of_the_xcp_block_are_not_asap2s(self) -> None:
        """A measurement called ``EVENT`` or ``VARIABLE`` reads fine to an a2l reader."""
        for word in ("XCP", "DAQ_EVENT", "DEFAULT_EVENT_LIST", "EVENT", "VARIABLE"):
            assert not is_a2l_keyword(word)

    def test_it_holds_the_values_of_the_calibration_access_and_the_naming_blocks(self) -> None:
        for word in (
            "USER_RIGHTS",
            "CALIBRATION",
            "NO_CALIBRATION",
            "NOT_IN_MCD_SYSTEM",
            "OFFLINE_CALIBRATION",
            "NUMERIC",
            "ALPHA",
        ):
            assert is_a2l_keyword(word)

    def test_it_holds_every_word_the_backend_writes_from_python(self) -> None:
        """The datatypes, the byte orders, the object and conversion types and the layouts'
        words, read off the string literals of the writer's own code (docstrings left out)."""
        own = {
            "ASAP2", "UTF", "NONE", "DEG", "MICRO", "OHM", "PCT",
            "CM_", "CM_IDENT_", "CM_LIN_", "RL_", "RL_AXIS_", "RL_VALUES_", "VTAB_",
            "NO_COMPU_METHOD", "NO_INPUT_QUANTITY",
        }  # fmt: skip
        words: set[str] = set()
        for name in ("model", "types", "options", "backend"):
            path = Path(a2l_package.__file__).parent / f"{name}.py"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docstrings
                ):
                    words.update(re.findall(r"\b[A-Z][A-Z0-9_]*\b", node.value))
        assert {"UBYTE", "MSB_FIRST", "COM_AXIS", "RAT_FUNC", "VAL_BLK"} <= words
        assert words - own - A2L_KEYWORDS == set()

    def test_it_holds_every_word_a_record_layout_spells(self) -> None:
        builder = _RecordLayoutBuilder()
        for datatype in Datatype:
            if datatype is Datatype.BOOLEAN:
                continue
            builder.values(datatype)
            builder.axis(datatype)
            for kind in (ObjectKind.CURVE, ObjectKind.MAP, ObjectKind.AXIS):
                builder.counted(kind, datatype)
        words = {
            word
            for layout in builder.layouts()
            for entry in layout.entries
            for word in re.findall(r"\b[A-Z][A-Z0-9_]*\b", entry)
        }
        assert words
        assert words - A2L_KEYWORDS == set()


class TestAKeywordIsRefused:
    def test_a_measurement_called_map(self, tree: Path) -> None:
        bag = run(tree, declare("local", "MAP"))
        assert checks(bag) == ["a2l-keyword"]
        assert at(bag, "a2l-keyword") == [
            "a.ddd.json#component.interface[0].definition.name: error[a2l-keyword]: "
            "'MAP' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_parameter_called_value(self, tree: Path) -> None:
        bag = run(tree, declare("local", "VALUE", kind="parameter", init=1))
        assert checks(bag) == ["a2l-keyword"]

    def test_a_component_called_root(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component("ROOT", declare("local", "X")),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-keyword") == [
            "a.ddd.json#component.name: error[a2l-keyword]: "
            "'ROOT' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_component_that_writes_no_group_is_not_held(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component("ROOT", declare("local", "X", a2l={"export": False})),
        }
        assert checks(over(tree, files)) == []

    def test_a_project_called_module(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("MODULE", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-keyword") == [
            "project.ddd.json#project.name: error[a2l-keyword]: "
            "'MODULE' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_an_object_the_a2l_leaves_out_is_not_held(self, tree: Path) -> None:
        bag = run(tree, declare("local", "MAP", a2l={"export": False}))
        assert checks(bag) == []

    def test_an_axis_the_a2l_must_carry_is_held(self, tree: Path) -> None:
        """An exported curve pulls its axis in whatever the axis says, and the file names it."""
        bag = run(
            tree,
            declare("local", "Speed"),
            declare(
                "local",
                "ROOT",
                "uint16",
                kind="axis",
                size=2,
                input="Speed",
                a2l={"export": False},
            ),
            declare("local", "Cv", "uint8", kind="curve", axis="ROOT"),
        )
        assert checks(bag) == ["a2l-keyword"]

    def test_the_names_of_the_lower_case_are_free(self, tree: Path) -> None:
        bag = run(tree, declare("local", "map"), declare("local", "Value"))
        assert checks(bag) == []

    def test_a_display_identifier_is_held(self, tree: Path) -> None:
        bag = run(tree, declare("local", "X", a2l={"display_identifier": "MAP"}))
        assert checks(bag) == ["a2l-keyword"]
        assert "definition.a2l.display_identifier" in messages(bag)

    def test_a_display_identifier_of_a_member_is_held(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                struct_type("S_t", value_member("v", a2l={"display_identifier": "ROOT"}))
            ),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-keyword") == [
            "t.ddd.json#types[0].members[0].a2l.display_identifier: error[a2l-keyword]: "
            "'ROOT' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_structure_instance_called_root(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "ROOT", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", value_member("v"))),
        }
        bag = over(tree, files)
        assert checks(bag) == ["a2l-keyword"]
        assert "a.ddd.json#component.interface[0].definition.name" in messages(bag)

    def test_a_component_that_declares_only_a_structure_gets_its_group(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("ROOT", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", value_member("v"))),
        }
        assert at(over(tree, files), "a2l-keyword") == [
            "a.ddd.json#component.name: error[a2l-keyword]: "
            "'ROOT' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_structure_whose_members_are_all_bitfields_writes_nothing(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("ROOT", declare("local", "MAP", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", bits_member("flag"))),
        }
        assert checks(over(tree, files)) == []

    def test_a_member_called_map_is_the_type_files_and_is_said_once(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A",
                declare("local", "X", typename="S_t"),
                declare("local", "Y", typename="S_t"),
            ),
            "t.ddd.json": types(struct_type("S_t", value_member("MAP"))),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-keyword") == [
            "t.ddd.json#types[0].members[0].name: error[a2l-keyword]: "
            "'MAP' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_nested_member_called_value_is_held_where_it_is_declared(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="Outer_t")),
            "t.ddd.json": types(
                struct_type("Outer_t", value_member("VALUE", typename="Inner_t")),
                struct_type("Inner_t", value_member("v")),
            ),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-keyword") == [
            "t.ddd.json#types[0].members[0].name: error[a2l-keyword]: "
            "'VALUE' is a keyword of ASAP2 1.6.1, which an identifier of the a2l may not be"
        ]

    def test_a_member_of_an_instance_the_a2l_leaves_out_is_not_held(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", typename="S_t", a2l={"export": False})
            ),
            "t.ddd.json": types(struct_type("S_t", value_member("MAP"))),
        }
        assert checks(over(tree, files)) == []


class TestWhatTheA2lDoesNotCarryIsNotHeld:
    def test_a_bitfield_member_has_no_record(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                struct_type(
                    "S_t",
                    value_member("v"),
                    bits_member("MAP", description="d" * 300, unit="u" * 300),
                )
            ),
        }
        assert checks(over(tree, files)) == []

    def test_a_member_the_a2l_leaves_out_is_not_held(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                struct_type(
                    "S_t",
                    value_member("v"),
                    value_member("MAP", a2l={"export": False}, description="d" * 300),
                )
            ),
        }
        assert checks(over(tree, files)) == []

    def test_a_project_the_root_includes_writes_no_a2l_of_its_own(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "sub.ddd.json"),
            "sub.ddd.json": project("MODULE", "a.ddd.json", description="d" * 300),
            "a.ddd.json": component("A", declare("local", "X")),
        }
        assert checks(over(tree, files)) == []


def enum_of(name: str, *enumerators: str) -> dict[str, Any]:
    return {
        "kind": "enum",
        "name": name,
        "enumerators": [{"name": e, "value": i} for i, e in enumerate(enumerators)],
    }


def long_unit_files(unit: str) -> dict[str, Any]:
    return {
        "project.ddd.json": project("Device", "a.ddd.json"),
        "a.ddd.json": component("A", declare("local", "X", unit=unit)),
    }


class TestAStringPastTheLimit:
    def test_a_unit_of_300_characters(self, tree: Path) -> None:
        bag = over(tree, long_unit_files("u" * 300))
        assert at(bag, "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition.unit: "
            "warning[a2l-unrepresentable]: the unit of 'X' is a string of 300 characters, "
            "but the a2l of ASAP2 1.6.1 carries 255 (MAX_STRING); it is written whole"
        ]

    def test_a_unit_of_255_characters_is_clean_under_a_conversion_that_does_not_repeat_it(
        self, tree: Path
    ) -> None:
        files = long_unit_files("u" * 255)
        files["a.ddd.json"] = component(
            "A", declare("local", "X", unit="u" * 255, conversion={"kind": "linear", "factor": 2})
        )
        assert checks(over(tree, files)) == []

    def test_an_identity_unit_that_fits_with_the_words_before_it_is_clean(self, tree: Path) -> None:
        """The compu method of an identity conversion is described as the unit, after
        ``physical value in `` of 18 characters, so 237 is the longest unit that fits whole."""
        assert checks(over(tree, long_unit_files("u" * 237))) == []

    def test_an_identity_unit_past_the_words_before_it_warns_on_the_description(
        self, tree: Path
    ) -> None:
        assert at(over(tree, long_unit_files("u" * 238)), "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition.unit: "
            "warning[a2l-unrepresentable]: the unit of 'X' is a string of 238 characters, and "
            "the description of the conversion the a2l builds from it, which opens with "
            "'physical value in ', is 256, but the a2l of ASAP2 1.6.1 carries 255 "
            "(MAX_STRING); both are written whole"
        ]

    def test_the_words_before_the_unit_are_the_ones_the_a2l_writes(self, tree: Path) -> None:
        files = long_unit_files("u" * 250)
        dictionary, _ = run_analysis(tree, files)
        assert dictionary is not None
        text = next(
            f.content for f in render_files(dictionary, tree / "gen") if f.path.name == "Device.a2l"
        )
        assert f'"{IDENTITY_METHOD_PREFIX}{"u" * 250}"' in text
        assert len(IDENTITY_METHOD_PREFIX) == 18

    def test_every_string_the_a2l_derives_from_a_name_fits_a_name_of_128(self, tree: Path) -> None:
        """The ones built around a project's name, an enum's, a constant's: the longest a name
        can be leaves them inside ``MAX_STRING``, so none needs a finding of its own."""
        long = "n" * 128
        files = {
            "project.ddd.json": project(long, "a.ddd.json", "c.ddd.json"),
            "a.ddd.json": component(
                "A",
                declare("local", "X", "uint8", conversion=enum_of(long, "ONE")),
                declare("local", "Y", "uint8", conversion={"kind": "linear", "factor": 0.5}),
            ),
            "c.ddd.json": {"constants": [{"name": long, "value": 1}]},
        }
        dictionary, bag = run_analysis(tree, files)
        assert dictionary is not None, messages(bag)
        text = next(
            f.content
            for f in render_files(dictionary, tree / "gen")
            if f.path.name.endswith(".a2l")
        )
        strings = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
        assert strings
        assert max(len(string) for string in strings) <= 255

    def test_a_unit_on_an_object_the_a2l_leaves_out_is_clean(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", unit="u" * 300, a2l={"export": False})
            ),
        }
        assert checks(over(tree, files)) == []

    def test_a_description_of_300_characters(self, tree: Path) -> None:
        bag = run(tree, declare("local", "X", description="d" * 300))
        assert at(bag, "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition.description: "
            "warning[a2l-unrepresentable]: the description of 'X' is a string of 300 "
            "characters, but the a2l of ASAP2 1.6.1 carries 255 (MAX_STRING); it is "
            "written whole"
        ]

    def test_a_description_of_255_characters_is_clean(self, tree: Path) -> None:
        assert checks(run(tree, declare("local", "X", description="d" * 255))) == []

    def test_a_component_description_reaches_the_group(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X"), description="d" * 300),
        }
        assert at(over(tree, files), "a2l-unrepresentable") == [
            "a.ddd.json#component.description: warning[a2l-unrepresentable]: the description "
            "of component 'A' is a string of 300 characters, but the a2l of ASAP2 1.6.1 "
            "carries 255 (MAX_STRING); it is written whole"
        ]

    def test_a_component_description_with_no_group_is_clean(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", a2l={"export": False}), description="d" * 300
            ),
        }
        assert checks(over(tree, files)) == []

    def test_a_project_description_reaches_project_header_and_module(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", description="d" * 300),
            "a.ddd.json": component("A", declare("local", "X")),
        }
        assert at(over(tree, files), "a2l-unrepresentable") == [
            "project.ddd.json#project.description: warning[a2l-unrepresentable]: the "
            "description of project 'Device' is a string of 300 characters, but the a2l of "
            "ASAP2 1.6.1 carries 255 (MAX_STRING); it is written whole on PROJECT, HEADER "
            "and MODULE"
        ]

    def test_a_project_description_of_255_characters_is_clean(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", description="d" * 255),
            "a.ddd.json": component("A", declare("local", "X")),
        }
        assert checks(over(tree, files)) == []

    def test_a_member_description_and_unit_are_the_type_files_and_said_once(
        self, tree: Path
    ) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", typename="S_t"), declare("local", "Y", typename="S_t")
            ),
            "t.ddd.json": types(
                struct_type("S_t", value_member("v", description="d" * 256, unit="u" * 256))
            ),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-unrepresentable") == [
            "t.ddd.json#types[0].members[0].description: warning[a2l-unrepresentable]: the "
            "description of member 'v' of structure 'S_t' is a string of 256 characters, but "
            "the a2l of ASAP2 1.6.1 carries 255 (MAX_STRING); it is written whole",
            "t.ddd.json#types[0].members[0].unit: warning[a2l-unrepresentable]: the unit of "
            "member 'v' of structure 'S_t' is a string of 256 characters, but the a2l of "
            "ASAP2 1.6.1 carries 255 (MAX_STRING); it is written whole",
        ]

    def test_the_unit_of_a_scalar_type_is_the_types_own(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                {
                    "type": "scalar",
                    "name": "Speed_t",
                    "datatype": "uint16",
                    "conversion": {"kind": "identity"},
                    "unit": "u" * 256,
                },
                struct_type("S_t", value_member("v", typename="Speed_t")),
            ),
        }
        assert at(over(tree, files), "a2l-unrepresentable") == [
            "t.ddd.json#types[0].unit: warning[a2l-unrepresentable]: the unit of type "
            "'Speed_t' is a string of 256 characters, but the a2l of ASAP2 1.6.1 carries 255 "
            "(MAX_STRING); it is written whole"
        ]

    def test_the_unit_of_a_scalar_type_a_variable_names_is_the_types_own(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="Speed_t")),
            "t.ddd.json": types(
                {
                    "type": "scalar",
                    "name": "Speed_t",
                    "datatype": "uint16",
                    "conversion": {"kind": "identity"},
                    "unit": "u" * 256,
                }
            ),
        }
        assert at(over(tree, files), "a2l-unrepresentable") == [
            "t.ddd.json#types[0].unit: warning[a2l-unrepresentable]: the unit of type "
            "'Speed_t' is a string of 256 characters, but the a2l of ASAP2 1.6.1 carries 255 "
            "(MAX_STRING); it is written whole"
        ]

    def test_a_member_unit_past_the_words_before_it_is_the_members(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(struct_type("S_t", value_member("v", unit="u" * 238))),
        }
        found = at(over(tree, files), "a2l-unrepresentable")
        assert len(found) == 1
        assert found[0].startswith("t.ddd.json#types[0].members[0].unit: ")
        assert "which opens with 'physical value in '" in found[0]

    def test_the_unit_of_a_scalar_type_a_member_names_is_the_types(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                scalar_type("T_t", "uint16", unit="u" * 238),
                struct_type("S_t", value_member("v", typename="T_t")),
            ),
        }
        found = at(over(tree, files), "a2l-unrepresentable")
        assert len(found) == 1
        assert found[0].startswith("t.ddd.json#types[0].unit: ")
        assert "which opens with" in found[0]

    def test_a_scaled_member_and_a_scaled_type_keep_the_whole_of_255(self, tree: Path) -> None:
        scaled = {"kind": "linear", "factor": 2}
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", typename="S_t"), declare("local", "Y", typename="T_t")
            ),
            "t.ddd.json": types(
                struct_type("S_t", value_member("v", unit="u" * 255, conversion=scaled)),
                scalar_type("T_t", "uint16", unit="u" * 255, conversion=scaled),
            ),
        }
        assert checks(over(tree, files)) == []

    def test_the_unit_of_a_scalar_type_past_the_words_before_it_is_the_types(
        self, tree: Path
    ) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="Speed_t")),
            "t.ddd.json": types(scalar_type("Speed_t", "uint16", unit="u" * 238)),
        }
        found = at(over(tree, files), "a2l-unrepresentable")
        assert len(found) == 1
        assert found[0].startswith("t.ddd.json#types[0].unit: ")

    def test_a_member_description_of_255_characters_is_clean(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            "t.ddd.json": types(
                struct_type("S_t", value_member("v", description="d" * 255, unit="u" * 237))
            ),
        }
        assert checks(over(tree, files)) == []


def chain(depth: int, width: int | list[int]) -> dict[str, Any]:
    """An instance ``X`` of a chain of structures, each nesting the next through a member of
    ``width`` characters, so a leaf's path is ``X`` and ``depth`` members long. A list gives
    each member its own width."""
    widths = width if isinstance(width, list) else [width] * depth
    entries = []
    for level in range(depth):
        name = f"S{level}_t"
        member_name = "m" * widths[level]
        member = (
            value_member(member_name, typename=f"S{level + 1}_t")
            if level + 1 < depth
            else value_member(member_name)
        )
        entries.append(struct_type(name, member))
    return {
        "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
        "a.ddd.json": component("A", declare("local", "X", typename="S0_t")),
        "t.ddd.json": types(*entries),
    }


class TestAPathPastTheLimit:
    def test_a_path_past_255_is_a_symbol_link_string(self, tree: Path) -> None:
        # X.m(100).m(100).m(100) is 1 + 3 * 101 = 304 characters
        bag = over(tree, chain(3, 100))
        assert at(bag, "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition: warning[a2l-unrepresentable]: "
            "'X' reaches the a2l under a path of 304 characters, but a string of the a2l of "
            "ASAP2 1.6.1 carries 255 (MAX_STRING), which is what the SYMBOL_LINK of a record "
            "holds until the image names the variable"
        ]

    def test_a_path_of_255_is_clean(self, tree: Path) -> None:
        # 1 + 2 * 127 = 255: two members of 126 characters
        assert checks(over(tree, chain(2, 126))) == []

    def test_a_path_past_1024_is_an_identifier_past_the_limit(self, tree: Path) -> None:
        # 1 + 8 * 129 = 1033
        bag = over(tree, chain(8, 128))
        assert at(bag, "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition: warning[a2l-unrepresentable]: "
            "'X' reaches the a2l under a path of 1033 characters, but an identifier of the "
            "a2l of ASAP2 1.6.1 carries 1024 (MAX_IDENT)"
        ]

    def test_a_path_of_exactly_1024_is_still_a_string_finding_only(self, tree: Path) -> None:
        # 1 + 8 * 1 + 7 * 128 + 119 = 1024
        bag = over(tree, chain(8, [128] * 7 + [119]))
        found = at(bag, "a2l-unrepresentable")
        assert len(found) == 1
        assert "path of 1024 characters" in found[0]
        assert "MAX_STRING" in found[0]
        assert "MAX_IDENT" not in found[0]

    def test_a_path_one_past_1024_is_the_identifier_finding(self, tree: Path) -> None:
        found = at(over(tree, chain(8, [128] * 7 + [120])), "a2l-unrepresentable")
        assert len(found) == 1
        assert "path of 1025 characters" in found[0]
        assert "MAX_IDENT" in found[0]

    def test_a_path_inside_1024_draws_no_identifier_finding(self, tree: Path) -> None:
        # 1 + 7 * 129 = 904
        messages_ = at(over(tree, chain(7, 128)), "a2l-unrepresentable")
        assert all("MAX_IDENT" not in text for text in messages_)

    def test_a_path_of_a_member_the_a2l_leaves_out_is_not_held(self, tree: Path) -> None:
        files = chain(3, 100)
        files["a.ddd.json"] = component(
            "A", declare("local", "X", typename="S0_t", a2l={"export": False})
        )
        assert checks(over(tree, files)) == []


def arrays(name: str, size: int = 2) -> dict[str, Any]:
    return {
        "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
        "a.ddd.json": component("A", declare("local", name, typename="S_t", dimensions=[size])),
        "t.ddd.json": types(struct_type("S_t", value_member("v"))),
    }


class TestAPartialIdentifierPastTheLimit:
    def test_a_128_character_name_with_its_index(self, tree: Path) -> None:
        bag = over(tree, arrays("x" * 128))
        assert at(bag, "a2l-unrepresentable") == [
            "a.ddd.json#component.interface[0].definition.name: "
            f"warning[a2l-unrepresentable]: the name '{'x' * 128}' with its index is 131 "
            "characters, but a partial identifier of the a2l of ASAP2 1.6.1 carries 128 "
            "(MAX_PARTIAL_IDENT), an index counted within it"
        ]

    def test_a_name_that_fits_with_its_index_is_clean(self, tree: Path) -> None:
        # 125 characters and "[1]" make 128
        assert checks(over(tree, arrays("x" * 125))) == []

    def test_a_name_that_fits_only_without_the_last_digit_is_held(self, tree: Path) -> None:
        # 125 characters with ten elements: "[9]" fits, and so does every one of them
        assert checks(over(tree, arrays("x" * 125, 10))) == []
        # 125 characters with eleven elements: "[10]" makes 129
        assert len(at(over(tree, arrays("x" * 125, 11)), "a2l-unrepresentable")) == 1

    def test_a_member_name_with_its_index_is_the_type_files(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json", "t.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", typename="O_t"), declare("local", "Y", typename="O_t")
            ),
            "t.ddd.json": types(
                struct_type("O_t", value_member("m" * 128, typename="S_t", dimensions=[3])),
                struct_type("S_t", value_member("v")),
            ),
        }
        bag = over(tree, files)
        assert at(bag, "a2l-unrepresentable") == [
            "t.ddd.json#types[0].members[0].name: warning[a2l-unrepresentable]: the name of "
            f"member '{'m' * 128}' of structure 'O_t' with its index is 131 characters, but a "
            "partial identifier of the a2l of ASAP2 1.6.1 carries 128 (MAX_PARTIAL_IDENT), an "
            "index counted within it"
        ]

    def test_an_array_of_values_has_no_index_in_its_name(self, tree: Path) -> None:
        files = {
            "project.ddd.json": project("Device", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "x" * 128, dimensions=[4])),
        }
        assert checks(over(tree, files)) == []

    def test_the_array_of_an_object_the_a2l_leaves_out_is_clean(self, tree: Path) -> None:
        files = arrays("x" * 128)
        files["a.ddd.json"] = component(
            "A", declare("local", "x" * 128, typename="S_t", dimensions=[2], a2l={"export": False})
        )
        assert checks(over(tree, files)) == []
