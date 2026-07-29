"""What the tool refuses, and what it no longer gets wrong.

Every test here stands for a defect that reached a customer-facing artefact or verdict: a
transposed a2l array, a header that does not compile, a legal name rejected, a description
file that ended the run with a python traceback. They are grouped by what was at stake
rather than by module, because that is what a regression here would cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.backends import COptions, load_address_map
from ddd.backends.c.literals import c_literal
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.ir import DICTIONARY_FORMAT
from ddd.loading import load_convention, load_dictionary, load_workspace
from ddd.models import Datatype
from ddd.models.naming import NamingConvention
from ddd.naming import complete, inspect


def enum_declaration(name: str, enum: str, **enumerators: int) -> dict[str, object]:
    return declare(
        "local",
        name,
        "uint8",
        conversion={"kind": "enum", "name": enum, "enumerators": enumerators},
    )


class TestGeneratedArtefactsAreCorrect:
    """A wrong artefact is the worst failure: it compiles, links and lies."""

    def test_matrix_dim_is_not_transposed(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "Blk", "uint8", kind="value_block", dimensions=[2, 3])
                ),
            },
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "const uint8_t Blk[2][3]" in files["ddd_globals.h"]
        # a2l counts the fastest running index first, c declares it last.
        assert "MATRIX_DIM 3 2 1" in files["P.a2l"]

    def test_int64_min_is_written_as_a_valid_literal(self) -> None:
        """'-9223372036854775808LL' negates a literal too large for any signed type."""
        assert c_literal(-(2**63), Datatype.INT64) == "(-9223372036854775807LL - 1)"
        assert c_literal(-(2**63) + 1, Datatype.INT64) == "-9223372036854775807LL"

    def test_a_64_bit_limit_keeps_every_digit(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Big", "uint64")),
            },
        )
        assert dictionary is not None
        content = {f.path.name: f.content for f in render_files(dictionary, tree / "gen")}["P.a2l"]
        assert "18446744073709551615" in content  # not ...616, which a float would give

    def test_an_axis_input_quantity_is_never_left_dangling(self, tree: Path) -> None:
        """An unexported measurement is pulled back in by the axis that names it."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Speed", "uint16", a2l={"export": False}),
                    declare("local", "Ax", "uint16", kind="axis", size=3, input="Speed"),
                ),
            },
        )
        assert dictionary is not None
        content = {f.path.name: f.content for f in render_files(dictionary, tree / "gen")}["P.a2l"]
        assert "/begin MEASUREMENT Speed" in content

    def test_a_description_cannot_end_the_comment_it_sits_in(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "X",
                        "uint8",
                        conversion={
                            "kind": "enum",
                            "name": "E",
                            "enumerators": [
                                {"name": "OFF", "value": 0, "description": "ends */ x"}
                            ],
                        },
                    ),
                    description="component */ int hijack; /*",
                ),
            },
        )
        assert dictionary is not None
        # Only the c files matter here: in the a2l the same text sits inside a quoted
        # string, where a comment marker is just two characters.
        for file in render_files(dictionary, tree / "gen"):
            if file.path.suffix in (".c", ".h"):
                assert "*/ int hijack" not in file.content
                assert "ends */ x" not in file.content

    def test_a_component_named_types_does_not_capture_the_shared_guard(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("types", declare("local", "X")),
            },
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "#ifndef DDD_COMPONENT_TYPES_H" in files["types.h"]
        assert "#ifndef DDD_TYPES_H" in files["ddd_types.h"]

    def test_a_prefix_cannot_escape_the_output_directory(self) -> None:
        for bad in ("../evil", "", "a b"):
            with pytest.raises(ValueError, match="not usable as a file name"):
                COptions(prefix=bad)


class TestNamesThatWouldNotCompile:
    def test_an_enum_and_its_enumerators_are_screened(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", enum_declaration("X", "switch", case=0, default=1)),
            },
        )
        assert checks(bag).count("reserved-identifier") == 3

    def test_identifiers_from_stdint_are_reserved_too(self, tree: Path) -> None:
        """ddd_types.h includes <stdint.h>, so 'uint16_t uint16_t;' has to be refused."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "uint16_t", "uint16")),
            },
        )
        assert "reserved-identifier" in checks(bag)

    def test_two_enums_may_not_contribute_the_same_enumerator(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    enum_declaration("X", "StateA_t", STATE_OFF=0),
                    enum_declaration("Y", "StateB_t", STATE_OFF=4),
                ),
            },
        )
        assert "name-collision" in checks(bag)

    def test_a_variable_may_not_share_a_name_with_an_enumerator(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    enum_declaration("X", "StateA_t", Ready=1),
                    declare("local", "Ready", "uint8"),
                ),
            },
        )
        assert "name-collision" in checks(bag)

    def test_components_differing_only_in_case_ask_for_one_header(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("Sensor", declare("local", "X")),
                "b.ddd.json": component("SENSOR", declare("local", "Y")),
            },
        )
        assert "name-collision" in checks(bag)
        assert "same generated header" in messages(bag)

    def test_an_enumerator_has_to_fit_into_an_int(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "X",
                        "uint64",
                        conversion={
                            "kind": "enum",
                            "name": "E",
                            "enumerators": {"BIG": 5_000_000_000},
                        },
                    ),
                ),
            },
        )
        assert "do not fit into a c 'int'" in messages(bag)


class TestVerdictsThatWereWrong:
    def test_a_multi_word_subject_is_not_blamed_on_the_qualifier(self) -> None:
        """The layout with two subjects fits, so it is the one the name is judged against."""
        convention = NamingConvention.model_validate(
            {
                "name": "c",
                "segments": [
                    {"name": "role", "tokens": [{"value": "val"}]},
                    {"name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$", "repeatable": True},
                    {"name": "qualifier", "optional": True, "tokens": [{"value": "flt"}]},
                ],
            }
        )
        assert inspect("val_Inlet_Temperature", convention).ok
        assert inspect("val_Inlet_Temperature_flt", convention).ok
        assert inspect("val_Inlet", convention).ok
        assert not inspect("val_Inlet_fltr", convention).ok

    def test_completion_continues_past_a_free_position(self) -> None:
        convention = NamingConvention.model_validate(
            {
                "name": "c",
                "segments": [
                    {"name": "role", "tokens": [{"value": "val"}]},
                    {"name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$", "repeatable": True},
                    {"name": "qualifier", "optional": True, "tokens": [{"value": "flt"}]},
                ],
            }
        )
        assert complete("val_Inlet", convention) == ["val_Inlet_flt"]
        assert complete("val_", convention) == []
        assert complete("v", convention) == ["val"]

    def test_an_enum_documented_on_one_side_only_is_not_a_mismatch(self, tree: Path) -> None:
        """The two spellings the format offers cannot carry the same information."""
        spelled_out = declare(
            "input",
            "S",
            "uint8",
            conversion={
                "kind": "enum",
                "name": "E",
                "enumerators": [{"name": "OFF", "value": 0, "description": "off"}],
            },
        )
        shorthand = declare(
            "output",
            "S",
            "uint8",
            conversion={"kind": "enum", "name": "E", "enumerators": {"OFF": 0}},
        )
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", shorthand),
                "b.ddd.json": component("B", spelled_out),
            },
        )
        assert "definition-mismatch" not in checks(bag)

    def test_the_generated_enum_does_not_depend_on_the_include_order(self, tree: Path) -> None:
        documented = declare(
            "output",
            "S",
            "uint8",
            conversion={
                "kind": "enum",
                "name": "E",
                "enumerators": [{"name": "OFF", "value": 0, "description": "documented"}],
            },
        )
        bare = declare(
            "input",
            "S",
            "uint8",
            conversion={"kind": "enum", "name": "E", "enumerators": {"OFF": 0}},
        )
        files = {
            "a.ddd.json": component("A", documented),
            "b.ddd.json": component("B", bare),
        }
        forwards, _ = run_analysis(
            tree / "one", {**files, "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json")}
        )
        backwards, _ = run_analysis(
            tree / "two", {**files, "project.ddd.json": project("P", "b.ddd.json", "a.ddd.json")}
        )
        assert forwards is not None and backwards is not None
        assert forwards.enums == backwards.enums
        assert forwards.enums[0].enumerators[0].description == "documented"

    def test_a_consumer_may_leave_the_limits_to_the_producer(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component("B", declare("input", "X", "uint8")),
            },
        )
        assert "definition-mismatch" not in checks(bag)

    def test_disagreeing_a2l_blocks_are_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", "uint8")),
                "b.ddd.json": component("B", declare("input", "X", "uint8", a2l={"export": False})),
            },
        )
        assert "storage-mismatch" in checks(bag)
        assert "export=" in messages(bag)

    def test_a_glob_does_not_swallow_the_naming_file(self, tree: Path) -> None:
        """The layout the manual shows puts the convention next to the project file."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "*.ddd.json", naming="convention.ddd.json"),
                "convention.ddd.json": {
                    "naming": {
                        "name": "c",
                        "segments": [{"name": "role", "tokens": [{"value": "val"}]}],
                    }
                },
                "a.ddd.json": component("A", declare("local", "val")),
            },
        )
        assert "file-kind" not in checks(bag)

    def test_a_comparison_of_two_different_projects_says_so(self, tree: Path) -> None:
        from ddd.compare import compare

        one, _ = run_analysis(
            tree / "one",
            {
                "project.ddd.json": project("Alpha", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        two, _ = run_analysis(
            tree / "two",
            {
                "project.ddd.json": project("Beta", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert one is not None and two is not None
        bag = DiagnosticBag()
        compare(one, two, bag)
        assert "project-mismatch" in checks(bag)

    def test_wrapping_an_unconditional_object_reads_as_a_loss(self, tree: Path) -> None:
        from ddd.compare import compare

        always, _ = run_analysis(
            tree / "one",
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        guarded, _ = run_analysis(
            tree / "two",
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", condition="defined(F)")),
            },
        )
        assert always is not None and guarded is not None
        bag = DiagnosticBag()
        compare(always, guarded, bag)
        assert "now absent from every build" in messages(bag)

        other = DiagnosticBag()
        compare(guarded, always, other)
        assert "now present in every build" in messages(other)

        both = DiagnosticBag()
        third, _ = run_analysis(
            tree / "three",
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", condition="defined(G)")),
            },
        )
        assert third is not None
        compare(guarded, third, both)
        assert "builds it is present in have changed" in messages(both)

    def test_findings_of_one_file_are_ordered_by_declaration(self) -> None:
        location = Location(Path("a.ddd.json"), "component.declarations[{}]")
        bag = DiagnosticBag()
        for index in (10, 2):
            bag.add("naming", "x", Location(Path("a.ddd.json"), f"component.declarations[{index}]"))
        assert [d.location.pointer for d in bag.sorted if d.location] == [
            "component.declarations[2]",
            "component.declarations[10]",
        ]
        assert location.pointer  # the template itself is not a diagnostic


class TestInputTheToolMustSurvive:
    """Every one of these used to end the run with a traceback or a silent pass."""

    def test_nan_is_refused(self, tree: Path) -> None:
        write_tree(tree, {"a.ddd.json": '{"component": {"name": "A", "declarations": []}}'})
        (tree / "a.ddd.json").write_text(
            '{"component": {"name": "A", "declarations": [{"scope": "local", "definition": '
            '{"name": "X", "datatype": "uint16", "limits": {"min": NaN, "max": 10}}}]}}',
            encoding="utf-8",
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "not valid json" in messages(bag)

    def test_a_literal_that_overflows_to_infinity_is_refused(self, tree: Path) -> None:
        """`1e400` is well formed json, and python reads it as inf: the models catch it."""
        (tree / "a.ddd.json").write_text(
            '{"component": {"name": "A", "declarations": [{"scope": "local", "definition": '
            '{"name": "X", "datatype": "float64", "conversion": {"factor": 1e400}}}]}}',
            encoding="utf-8",
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "schema" in checks(bag)

    def test_a_file_that_is_not_utf8(self, tree: Path) -> None:
        (tree / "a.ddd.json").write_bytes(b"\xff\xfe{ not utf 8")
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "is not valid utf-8" in messages(bag)

    def test_a_byte_order_mark_is_accepted(self, tree: Path) -> None:
        (tree / "a.ddd.json").write_bytes(
            b"\xef\xbb\xbf" + json.dumps(component("A", declare("local", "X"))).encode()
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is not None

    def test_json_nested_beyond_what_python_can_read(self, tree: Path) -> None:
        (tree / "a.ddd.json").write_text("[" * 20_000 + "]" * 20_000, encoding="utf-8")
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "nested too deeply" in messages(bag)

    def test_a_pattern_that_does_not_compile_is_a_finding(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "c.ddd.json": {
                    "naming": {
                        "name": "c",
                        "segments": [{"name": "role", "pattern": "^[A-Z(]$|["}],
                    }
                }
            },
        )
        bag = DiagnosticBag()
        assert load_convention(tree / "c.ddd.json", bag) is None
        assert "invalid pattern" in messages(bag)

    def test_a_token_containing_the_separator_is_refused(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "c.ddd.json": {
                    "naming": {
                        "name": "c",
                        "separator": "_",
                        "segments": [{"name": "role", "tokens": [{"value": "not_known"}]}],
                    }
                }
            },
        )
        bag = DiagnosticBag()
        assert load_convention(tree / "c.ddd.json", bag) is None
        assert "contains the separator" in messages(bag)

    @pytest.mark.parametrize(
        "condition", ["defined(X)\n#include <stdio.h>", "defined(A) /* c */", "defined(A) // c"]
    )
    def test_a_condition_cannot_carry_more_than_an_expression(
        self, tree: Path, condition: str
    ) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", condition=condition)),
            },
        )
        assert "schema" in checks(bag)

    def test_a_blank_condition_is_still_no_condition(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", condition="   ")),
            },
        )
        assert dictionary is not None
        assert dictionary.by_name["X"].condition is None

    def test_a_rooted_include_pattern_does_not_crash(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, {"project.ddd.json": project("P", "/nowhere-at-all/*.ddd.json")}
        )
        assert "include-empty" in checks(bag)

    def test_an_a2l_format_string_has_to_look_like_one(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", a2l={"format": '%8.3" evil'})),
            },
        )
        assert "schema" in checks(bag)

    def test_an_address_outside_the_a2l_field_is_refused(self, tree: Path) -> None:
        write_tree(tree, {"map.json": {"X": -16}})
        with pytest.raises(ValueError, match="outside the range"):
            load_address_map(tree / "map.json")
        write_tree(tree, {"wide.json": {"X": "0x1FFFFFFFF"}})
        with pytest.raises(ValueError, match="outside the range"):
            load_address_map(tree / "wide.json")

    def test_control_characters_never_reach_an_a2l_string(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", description="a\rb\tc", unit="d\x7fe")
                ),
            },
        )
        assert dictionary is not None
        content = {f.path.name: f.content for f in render_files(dictionary, tree / "gen")}["P.a2l"]
        assert "\r" not in content
        assert '"a b c"' in content

    def test_more_dimensions_than_the_a2l_version_can_carry(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", "uint8", kind="value_block", dimensions=[2, 2, 2, 2]),
                ),
            },
        )
        assert "a2l-unrepresentable" in checks(bag)


class TestTheArchivedDictionary:
    def test_a_newer_format_is_refused_rather_than_misread(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        payload = json.loads(dictionary.model_dump_json())
        payload["format"] = DICTIONARY_FORMAT + 1
        (tree / "baseline.json").write_text(json.dumps(payload), encoding="utf-8")
        bag = DiagnosticBag()
        assert load_dictionary(tree / "baseline.json", bag) is None
        assert "use a newer DDD" in messages(bag)

    def test_the_current_format_round_trips(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        (tree / "baseline.json").write_text(dictionary.model_dump_json(), encoding="utf-8")
        bag = DiagnosticBag()
        reloaded = load_dictionary(tree / "baseline.json", bag)
        assert reloaded == dictionary


class TestTheRestOfTheEdges:
    """Paths that only a deliberate mistake reaches, and which must still be findings."""

    def test_two_explicit_and_different_limits_are_spelled_out(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "X", "uint8", limits={"min": 0, "max": 50})
                ),
            },
        )
        assert "definition-mismatch" in checks(bag)
        assert "limits: [0, 50] != [0, 100]" in messages(bag)

    def test_a_path_the_system_cannot_represent(self, tree: Path) -> None:
        bag = DiagnosticBag()
        assert load_workspace(tree / "a\x00b.ddd.json", bag) is None
        assert "cannot read" in messages(bag)

        other = DiagnosticBag()
        assert load_workspace(tree / "in<val>id.ddd.json", other) is None
        assert "cannot read" in messages(other)

    def test_a_pattern_the_platform_refuses_to_expand(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Platforms disagree about which patterns they accept; none may end the run."""

        def refuse(self: Path, pattern: str) -> object:
            msg = "Non-relative patterns are unsupported"
            raise NotImplementedError(msg)

        monkeypatch.setattr(Path, "glob", refuse)
        _, bag = run_analysis(tree, {"project.ddd.json": project("P", "*.ddd.json")})
        assert "include-empty" in checks(bag)
        assert "cannot expand pattern" in messages(bag)

    def test_completion_skips_a_layout_the_typed_parts_do_not_fit(self) -> None:
        convention = NamingConvention.model_validate(
            {
                "name": "c",
                "segments": [
                    {"name": "role", "tokens": [{"value": "flg"}, {"value": "val"}]},
                    {"name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$", "repeatable": True},
                    {"name": "qualifier", "optional": True, "tokens": [{"value": "raw"}]},
                ],
            }
        )
        assert complete("flg_Valid_", convention) == ["flg_Valid_raw"]
        # 'raw' is not a valid subject, so no layout puts anything after it: a completion
        # that offered one would be proposing a name `ddd name` then rejects.
        assert complete("flg_raw_", convention) == []


class TestDiagnosticPlumbing:
    def test_a_severity_of_a_note_carrying_diagnostic_survives_a_copy(self) -> None:
        """`check --baseline` re-adds the baseline's errors; the notes must come along."""
        bag = DiagnosticBag()
        diagnostic = bag.add("schema", "bad", Location(Path("a.json")), notes=[("why", None)])
        assert isinstance(diagnostic, Diagnostic)
        assert diagnostic.severity is Severity.ERROR
        assert diagnostic.notes == (("why", None),)
