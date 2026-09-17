"""What the tool refuses, and what it no longer gets wrong.

Every test here stands for a defect that reached a customer-facing artefact or verdict: a
transposed a2l array, a header that does not compile, a legal name rejected, a description
file that ended the run with a python traceback. They are grouped by what was at stake
rather than by module, because that is what a regression here would cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from ddd.backends import load_address_map
from ddd.backends.c.literals import c_literal
from ddd.cli import EXIT_FINDINGS, main
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity, index_order
from ddd.ir import DICTIONARY_FORMAT, DataDictionary
from ddd.loading import load_dictionary, load_workspace
from ddd.models import Datatype


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
        assert c_literal(-(2**63), Datatype.SINT64) == "(-9223372036854775807LL - 1)"
        assert c_literal(-(2**63) + 1, Datatype.SINT64) == "-9223372036854775807LL"

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

    def test_a_template_directory_that_renders_nothing_is_refused(self, tree: Path) -> None:
        """Silence would look like a project with no variables; it is a missing template."""
        from ddd.backends import CBackend

        empty = tree / "templates"
        empty.mkdir()
        (empty / "_helper.jinja2").write_text("{% macro noop() %}{% endmacro %}", encoding="utf-8")
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        with pytest.raises(ValueError, match="no template to render"):
            CBackend(empty).generate(dictionary, tree / "gen")

    def loaded(self, tree: Path) -> DataDictionary:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        return dictionary

    def test_a_template_directory_that_is_not_there_says_so(self, tree: Path) -> None:
        """A path nobody created and a directory holding the wrong files are two different
        mistakes with two different answers; reported as an empty one, the author reads the
        advice about helper templates and goes looking for a template that is not the
        problem."""
        from ddd.backends import CBackend

        dictionary = self.loaded(tree)
        missing = tree / "nowhere"
        with pytest.raises(ValueError) as caught:
            CBackend(missing).generate(dictionary, tree / "gen")
        assert str(caught.value).startswith(f"no template directory at '{missing.as_posix()}'")
        assert "ddd templates-dir" in str(caught.value)

    def test_a_template_directory_that_is_a_file_says_so(self, tree: Path) -> None:
        """``-t`` pointed at one template rather than at the directory holding it."""
        from ddd.backends import CBackend

        dictionary = self.loaded(tree)
        single = tree / "ddd_globals.c.jinja2"
        single.write_text("/* nothing */\n", encoding="utf-8")
        with pytest.raises(ValueError) as caught:
            CBackend(single).generate(dictionary, tree / "gen")
        assert str(caught.value).startswith(f"'{single.as_posix()}' is not a directory")
        assert "ddd templates-dir" in str(caught.value)


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

    def test_a_variable_may_not_share_a_name_with_an_enum(self, tree: Path) -> None:
        """The enum becomes a typedef name, which c keeps with the variables at file scope."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    enum_declaration("X", "State", STATE_OFF=0),
                    declare("local", "State", "uint8"),
                ),
            },
        )
        assert "name-collision" in checks(bag)
        assert "typedef name" in messages(bag)

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
        """How the object is displayed: two *stated* format strings cannot both be used."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", a2l={"format": "%4.1"})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "X", "uint8", a2l={"format": "%8.3"})
                ),
            },
        )
        assert "storage-mismatch" in checks(bag)
        assert "a2l format: '%8.3' != '%4.1'" in messages(bag)

    def test_an_unstated_a2l_block_defers_to_whoever_states_one(self, tree: Path) -> None:
        """Only a consumer stating something else is told so (SPEC 3.3.1.3).

        A consumer that simply omits the block, or one of its keys, is not disagreeing with
        the producer's presentation, so there is nothing to warn about.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "X",
                        "uint8",
                        a2l={"format": "%8.3", "display_identifier": "Xd"},
                    ),
                ),
                "b.ddd.json": component("B", declare("input", "X", "uint8")),
            },
        )
        assert "storage-mismatch" not in checks(bag)

    def test_a_consumer_stating_only_export_is_not_disagreeing(self, tree: Path) -> None:
        """Export is combined, not ranked, so stating it alone leaves nothing to mismatch."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", a2l={"format": "%8.3"})
                ),
                "b.ddd.json": component("B", declare("input", "X", "uint8", a2l={"export": True})),
            },
        )
        assert "storage-mismatch" not in checks(bag)

    def test_any_component_may_ask_for_the_a2l_and_none_may_veto_that(self, tree: Path) -> None:
        """Which signals a calibration engineer needs is not the producer's to decide alone.

        An object missing from the a2l costs somebody a measurement they cannot take; one
        nobody looks at costs a longer file. So asking wins over declining.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", a2l={"export": False})
                ),
                "b.ddd.json": component("B", declare("input", "X", "uint8", a2l={"export": True})),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["X"].a2l.export is True

    def test_a_producer_can_still_keep_an_object_out_of_the_a2l(self, tree: Path) -> None:
        """The opt-out that existed before consumers could ask; two examples rely on it."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "X", "uint8", a2l={"export": False})
                ),
                "b.ddd.json": component("B", declare("input", "X", "uint8")),
            },
        )
        assert dictionary is not None
        assert dictionary.by_name["X"].a2l.export is False

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

    def test_changed_a2l_names_only_what_differs(self, tree: Path) -> None:
        """Rendering the whole record made one change read as several."""
        from ddd.compare import compare

        def delivery(where: str, **a2l: object) -> object:
            dictionary, _ = run_analysis(
                tree / where,
                {
                    "project.ddd.json": project("P", "a.ddd.json"),
                    "a.ddd.json": component(
                        "A", declare("local", "Gain", "uint8", **({"a2l": a2l} if a2l else {}))
                    ),
                },
            )
            return dictionary

        plain = delivery("one")
        named = delivery("two", display_identifier="FiltGain")
        assert plain is not None and named is not None

        bag = DiagnosticBag()
        compare(plain, named, bag)
        assert "display_identifier: none -> 'FiltGain'" in messages(bag)
        assert "export" not in messages(bag)  # it did not change, so it is not mentioned

        back = DiagnosticBag()
        compare(named, plain, back)
        assert "display_identifier: 'FiltGain' -> none" in messages(back)

    def test_findings_of_one_file_are_ordered_by_declaration(self) -> None:
        bag = DiagnosticBag()
        for index in (10, 2):
            bag.add("schema", "x", Location(Path("a.ddd.json"), f"component.interface[{index}]"))
        assert [d.location.pointer for d in bag.sorted if d.location] == [
            "component.interface[2]",
            "component.interface[10]",
        ]


class TestInputTheToolMustSurvive:
    """Every one of these used to end the run with a traceback or a silent pass."""

    def test_nan_is_refused(self, tree: Path) -> None:
        (tree / "a.ddd.json").write_text(
            '{"component": {"name": "A", "interface": [{"scope": "local", "definition": '
            '{"name": "X", "datatype": "uint16", "limits": {"min": NaN, "max": 10}}}]}}',
            encoding="utf-8",
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "not valid json" in messages(bag)

    def test_a_literal_that_overflows_to_infinity_is_refused(self, tree: Path) -> None:
        """`1e400` is well formed json, and python reads it as inf: the models catch it.

        Everything the definition needs is written out - `kind` and `volatile` included -
        because a definition missing either fails on the discriminator before a number is
        read at all, and the finding is then `Unable to extract tag using discriminator
        'kind'` at `definition`. That is a `schema` finding too, so a test asserting the
        identifier alone on an incomplete payload stays green with the infinity refusal
        deleted. The pointer and the phrase below are what only the refusal produces.
        """
        (tree / "a.ddd.json").write_text(
            '{"component": {"name": "A", "interface": [{"scope": "local", "definition": '
            '{"name": "X", "kind": "measurement", "volatile": false, "datatype": "float64", '
            '"conversion": {"factor": 1e400}}}]}}',
            encoding="utf-8",
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert checks(bag) == ["schema"]
        assert [d.location.pointer for d in bag.sorted if d.location] == [
            "component.interface[0].definition.conversion.factor"
        ]
        assert "finite number" in messages(bag)

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

    def test_a_file_too_large_to_hold_in_memory_is_a_finding(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A log a careless include pattern matched, larger than the memory left.

        ``MemoryError`` was the one failure of the read that reached the caller as a
        traceback, where everything else it can do - missing, unreadable, not utf-8, a
        directory - is a located finding and the run goes on to the rest of the tree.
        """
        write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
        reading = Path.read_text

        def refusing(self: Path, *args: Any, **kwargs: Any) -> str:
            if self.name == "a.ddd.json":
                raise MemoryError
            return str(reading(self, *args, **kwargs))

        monkeypatch.setattr(Path, "read_text", refusing)
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert checks(bag) == ["file-not-found"]
        assert "is too large to read" in messages(bag)

    def test_json_nested_beyond_what_python_can_read(self, tree: Path) -> None:
        (tree / "a.ddd.json").write_text("[" * 20_000 + "]" * 20_000, encoding="utf-8")
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "nested too deeply" in messages(bag)

    def test_a_dumped_dictionary_nested_beyond_what_python_can_read(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Neither side of this comparison names a project or a component, so both reach
        the dictionary reader through ``_holds_a_description``'s own sniff - which used to
        run ``json.loads`` unguarded and end the run with an uncaught ``RecursionError``
        before ``load_dictionary`` ever had a chance to report anything."""
        deep = "[" * 100_000 + "]" * 100_000
        (tree / "baseline.json").write_text(deep, encoding="utf-8")
        (tree / "candidate.json").write_text(deep, encoding="utf-8")
        code = main(["compare", str(tree / "baseline.json"), str(tree / "candidate.json")])
        captured = capsys.readouterr()
        assert code == EXIT_FINDINGS
        assert "json-syntax" in captured.err
        assert "nested too deeply" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

    def test_assigning_ids_to_a_document_nested_beyond_what_python_can_read(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``ddd id --assign`` delegates its parse to ``Document``, which used to catch
        only ``ValueError`` - so a ``RecursionError`` from a document nested this deeply
        ended the run instead of being reported the way any other unparsable file is."""
        (tree / "a.ddd.json").write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
        code = main(["id", "--assign", str(tree / "a.ddd.json")])
        captured = capsys.readouterr()
        assert code == EXIT_FINDINGS
        assert "not readable as json, skipped" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

    def test_a_document_python_can_read_but_the_scanner_cannot_has_no_spans(self) -> None:
        """The scan sat outside the guard, which covered ``json.loads`` alone - and the
        scanner recurses two frames per level where the parser recurses less, so between
        about five hundred and three thousand levels python read the document and the scanner
        died on it. A document nobody can point into answers every question with nothing,
        which is what the callers already read an unparsable one as."""
        from ddd.lsp.ranges import Document

        text = "[" * 600 + "]" * 600
        assert json.loads(text) is not None
        document = Document(text)
        assert document.data is None
        assert document.range_of("")["start"] == {"line": 0, "character": 0}

    def test_assigning_ids_to_a_document_deeper_than_the_scanner_walks(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Reported as a file it cannot read, which is a sentence somebody can act on, rather
        than as the ``RecursionError`` traceback that used to end the run."""
        (tree / "a.ddd.json").write_text("[" * 600 + "]" * 600, encoding="utf-8")
        code = main(["id", "--assign", str(tree / "a.ddd.json")])
        captured = capsys.readouterr()
        assert code == EXIT_FINDINGS
        assert "not readable as json, skipped" in captured.err
        assert "Traceback" not in captured.err + captured.out

    def test_a_non_utf8_compare_candidate_is_a_finding_not_a_usage_error(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``_holds_a_description`` used to raise the bare ``UnicodeDecodeError`` its own
        read hit, which is a ``ValueError`` that ``main`` already catches - so the file was
        refused as a usage error (exit 2) instead of the located finding every other
        unreadable file gets."""
        write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
        (tree / "candidate.json").write_bytes(b"\xff\xfe\x00")
        code = main(["compare", str(tree / "a.ddd.json"), str(tree / "candidate.json")])
        captured = capsys.readouterr()
        assert code == EXIT_FINDINGS
        assert "json-syntax" in captured.err
        assert "not valid utf-8" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

    def test_a_key_that_looks_numeric_does_not_break_the_pointer_sort(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``str.isdigit`` is true of a superscript two, which ``int`` refuses; sorting the
        findings of this file by pointer used to raise that bare ``ValueError`` - which
        ``main`` already catches - so the file was refused as a usage error (exit 2) instead
        of reporting the extra key it actually has."""
        document = component("A", declare("local", "X"))
        document["²"] = 1
        write_tree(tree, {"a.ddd.json": document})
        code = main(["check", str(tree / "a.ddd.json"), "--standalone"])
        captured = capsys.readouterr()
        assert code == EXIT_FINDINGS
        assert "schema" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out

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
        """For a symbol the a2l states an address for: a negative value renders as
        ``0x-0000010`` and a wider one as a 33 bit literal, either of which makes the whole
        file unreadable."""
        write_tree(tree, {"map.json": {"X": -16}})
        with pytest.raises(ValueError, match="outside the range"):
            load_address_map(tree / "map.json", carried=("X",))
        write_tree(tree, {"wide.json": {"X": "0x1FFFFFFFF"}})
        with pytest.raises(ValueError, match="outside the range"):
            load_address_map(tree / "wide.json", carried=("X",))

    def test_an_address_outside_it_is_kept_for_a_symbol_the_a2l_never_states(
        self, tree: Path
    ) -> None:
        """The documented recipe extracts every defined symbol of the image, which on a 64 bit
        host puts a hundred entries of the c runtime above 4 GB. None of them is formatted
        into the a2l, so refusing them failed every build after the first for entries nobody
        asked for; they stay in the map and are named in the ``address-missing`` note."""
        write_tree(tree, {"map.json": {"X": "0x1000", "___crt_xc_end__": "0x140009018"}})
        assert load_address_map(tree / "map.json", carried=("X",)) == {
            "X": 0x1000,
            "___crt_xc_end__": 0x140009018,
        }

    def test_an_address_map_that_is_not_json_names_the_file(self, tree: Path) -> None:
        """The bare json message says where inside the document; the reader's first question
        is which file, and the map is typically written by a tool nobody is watching."""
        (tree / "map.json").write_text("{ not json", encoding="utf-8")
        with pytest.raises(ValueError) as caught:
            load_address_map(tree / "map.json", carried=())
        assert "map.json" in str(caught.value)
        assert "is not valid json" in str(caught.value)

    @pytest.mark.parametrize("value", [12.5, None, [1]])
    def test_an_address_that_is_no_integer_is_told_the_rule(
        self, tree: Path, value: object
    ) -> None:
        """12.5 *is* a number, so 'not a number' left the actual rule unsaid."""
        write_tree(tree, {"map.json": {"X": value}})
        with pytest.raises(ValueError, match="address of 'X' is not an integer"):
            load_address_map(tree / "map.json", carried=())

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

    def hyper_member(self, **member_extra: object) -> dict[str, object]:
        """A structure whose member needs one dimension more than MATRIX_DIM has."""
        return {
            "types": [
                {
                    "type": "struct",
                    "name": "S_t",
                    "members": [
                        {
                            "name": "hyper",
                            "member": "value",
                            "datatype": "uint8",
                            "conversion": {},
                            "dimensions": [2, 2, 2, 2],
                            **member_extra,
                        }
                    ],
                }
            ]
        }

    def test_more_dimensions_on_a_member_than_the_a2l_version_can_carry(self, tree: Path) -> None:
        """The member is an a2l object of its own, so it gets the warning a plain object with
        too many dimensions gets; it used to get a four entry MATRIX_DIM silently."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": self.hyper_member(),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert "a2l-unrepresentable" in checks(bag)
        assert "'X.hyper' has 4 dimensions" in messages(bag)

    def test_a_member_kept_out_of_the_a2l_raises_no_dimension_warning(self, tree: Path) -> None:
        """The warning is about the file the member reaches; a member that reaches none has
        nothing to be unrepresentable in."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": self.hyper_member(a2l={"export": False}),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert "a2l-unrepresentable" not in checks(bag)

    def test_an_instance_kept_out_of_the_a2l_raises_no_dimension_warning(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": self.hyper_member(),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="S_t", a2l={"export": False})
                ),
            },
        )
        assert "a2l-unrepresentable" not in checks(bag)


class TestWhatABuildSystemIsTold:
    def test_a_rejected_file_is_still_a_source(self, tree: Path) -> None:
        """A file read and then rejected still belongs to the dependency list.

        Otherwise the build never re-runs DDD when somebody fixes it, and the fix appears to
        change nothing.
        """
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "c/*.ddd.json"),
                "c/a.ddd.json": component("Same", declare("output", "X")),
                "c/b.ddd.json": component("Same", declare("input", "X")),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None
        assert "duplicate-component" in checks(bag)  # b was read, and rejected
        names = {path.name for path in workspace.sources()}
        assert names == {"project.ddd.json", "a.ddd.json", "b.ddd.json"}

    def test_a_file_that_is_not_even_json_is_still_a_source(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "c/*.ddd.json"),
                "c/broken.ddd.json": "{ not json",
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None
        assert "broken.ddd.json" in {path.name for path in workspace.sources()}


class TestOneMistakeIsOneFinding:
    def test_a_list_emptied_by_a_rejected_entry_is_not_reported_as_well(self, tree: Path) -> None:
        """pydantic drops the bad entry and then calls the list too short; one mistake."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json"),
                "s.ddd.json": {
                    "sections": [{"section": "", "access": "read-only", "alignment": 4}]
                },
            },
        )
        assert len(bag) == 1
        assert "sections[0].section" in messages(bag)

    def test_a_list_that_was_written_empty_still_reports_itself(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json"),
                "s.ddd.json": {"sections": []},
            },
        )
        assert "at least 1 item" in messages(bag)

    @staticmethod
    def _bad_init(tree: Path, init: Any) -> DiagnosticBag:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", dimensions=[2, 2], init=init)),
            },
        )
        return bag

    @pytest.mark.parametrize(
        ("written", "spelled"),
        [
            (None, "Input should be a valid integer (got: None)"),
            ("x", "Input should be a valid integer (got: 'x')"),
            ({}, "Input should be a valid integer (got: {})"),
        ],
    )
    def test_a_mistake_inside_a_nested_init_is_one_finding_at_the_value(
        self, tree: Path, written: Any, spelled: str
    ) -> None:
        """The enclosing lists are not three mistakes, and they are not lists that should
        have been integers: each one holds the finding below it, which is the whole story."""
        bag = self._bad_init(tree, [[1, 2], [3, written]])
        assert len(bag) == 1, messages(bag)
        assert f"definition.init[1][1]: error[schema]: {spelled}" in messages(bag), messages(bag)

    def test_a_value_too_wide_for_64_bits_is_reported_where_it_is_written(self, tree: Path) -> None:
        """The real finding used to arrive behind 'init: should be a valid integer'."""
        bag = self._bad_init(tree, [[1, 2], [3, 2**64]])
        assert len(bag) == 1, messages(bag)
        assert "definition.init[1][1]: error[schema]:" in messages(bag), messages(bag)
        assert "does not fit 64 bits" in messages(bag), messages(bag)

    def test_two_mistakes_in_one_init_are_still_two_findings(self, tree: Path) -> None:
        bag = self._bad_init(tree, [[None, 2], [3, None]])
        assert len(bag) == 2, messages(bag)
        assert "definition.init[0][0]: error[schema]:" in messages(bag), messages(bag)
        assert "definition.init[1][1]: error[schema]:" in messages(bag), messages(bag)

    def test_a_whole_init_that_is_the_mistake_still_reports_itself(self, tree: Path) -> None:
        """Nothing is written under it, so there is no deeper finding to stand in for it."""
        bag = self._bad_init(tree, {"a": 1})
        assert len(bag) == 1, messages(bag)
        assert "definition.init: error[schema]:" in messages(bag), messages(bag)


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

    @pytest.mark.parametrize(
        "payload",
        [
            "{ not json at all",
            "[1, 2, 3]",
            '{"format": "two", "name": "P"}',
            '{"format": true, "name": "P"}',
        ],
        ids=["unparseable", "not-an-object", "format-not-a-number", "format-is-a-bool"],
    )
    def test_the_version_peek_judges_only_the_version(self, tree: Path, payload: str) -> None:
        """Anything else wrong with the document is left to the real validation.

        The peek runs before pydantic and on unvalidated json, so it has to keep its hands
        off everything it is not there to decide: a document that is not json, or not an
        object, or whose ``format`` is not a number it recognises, must come back with
        pydantic's located finding rather than with a complaint about the version.
        """
        (tree / "bad.json").write_text(payload, encoding="utf-8")
        bag = DiagnosticBag()
        load_dictionary(tree / "bad.json", bag)
        assert "use a newer DDD" not in messages(bag)

    def test_the_version_is_read_before_the_document_is_validated(self, tree: Path) -> None:
        """A newer dump carries unknown fields, and the contract forbids those.

        Validating first would answer 'extra inputs are not permitted', which says nothing
        about what actually happened.
        """
        (tree / "future.json").write_text(
            json.dumps(
                {
                    "format": DICTIONARY_FORMAT + 1,
                    "name": "P",
                    "objects": [{"name": "X", "kind": "measurement", "future_field": 1}],
                }
            ),
            encoding="utf-8",
        )
        bag = DiagnosticBag()
        assert load_dictionary(tree / "future.json", bag) is None
        assert "use a newer DDD" in messages(bag)
        assert "Extra inputs are not permitted" not in messages(bag)

    def dump(self, tree: Path) -> dict[str, Any]:
        """A dumped dictionary of a one-object project, as json a test can doctor."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        payload: dict[str, Any] = json.loads(dictionary.model_dump_json())
        return payload

    @pytest.mark.parametrize(
        "spelled",
        ["9", 9.0, 0, -3],
        ids=["text", "fractional", "zero", "negative"],
    )
    def test_a_format_that_is_not_a_version_is_refused(self, tree: Path, spelled: object) -> None:
        """The version gate compares a number, and the field coerced whatever it was given.

        ``"9"`` and ``9.0`` went past the gate - neither is an ``int``, so there was nothing
        to compare - and were then coerced to the 9 the gate exists to refuse, so a dictionary
        from a DDD that does not exist yet compared clean and "can replace". ``0`` and ``-3``
        are versions no DDD ever wrote.
        """
        payload = self.dump(tree)
        payload["format"] = spelled
        (tree / "baseline.json").write_text(json.dumps(payload), encoding="utf-8")
        bag = DiagnosticBag()
        assert load_dictionary(tree / "baseline.json", bag) is None
        assert checks(bag) == ["schema"], messages(bag)
        assert "format" in messages(bag)

    def test_a_duplicate_key_in_a_dump_is_refused_as_it_is_in_a_description(
        self, tree: Path
    ) -> None:
        """json lets an object spell one key twice and the last spelling wins silently.

        The description loader refuses it; the dictionary reader handed the text straight to
        pydantic, whose parser has no such hook, so a baseline carrying ``"name": "P",
        "name": "Q"`` read back as a delivery of a project called 'Q' and the comparison
        reported a project-mismatch against a file that says 'P' on the line above.
        """
        payload = self.dump(tree)
        text = json.dumps(payload)
        doctored = text.replace('"name": "P"', '"name": "P", "name": "Q"', 1)
        assert doctored != text
        (tree / "baseline.json").write_text(doctored, encoding="utf-8")
        bag = DiagnosticBag()
        assert load_dictionary(tree / "baseline.json", bag) is None
        assert checks(bag) == ["json-syntax"], messages(bag)
        assert "appears twice in one object" in messages(bag)

    def test_a_finding_inside_a_dumped_entry_names_the_entry(self, tree: Path) -> None:
        """A dump is validated without the document beside it, so every segment of a finding
        in it is judged by its shape: an index into a list is an index and not a union tag,
        and the entry that is wrong is named rather than the list holding it."""
        payload = self.dump(tree)
        payload["objects"][0]["name"] = 5
        (tree / "baseline.json").write_text(json.dumps(payload), encoding="utf-8")
        bag = DiagnosticBag()
        assert load_dictionary(tree / "baseline.json", bag) is None
        assert "baseline.json#objects[0].name: error[schema]" in messages(bag), messages(bag)

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
        """Where such a path is refused differs by platform; the finding must not.

        linux rejects a NUL byte already in ``resolve()`` while Windows carries it as far as
        the read, so the loader has to survive both and report the same thing.
        """
        bag = DiagnosticBag()
        assert load_workspace(tree / "a\x00b.ddd.json", bag) is None
        assert "cannot read" in messages(bag)

    def test_a_path_refused_by_resolve_itself(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other half of the platform split, forced so that both are tested everywhere.

        linux raises inside ``resolve()`` for a NUL byte and Windows does not, so whichever
        platform runs the suite would otherwise leave one of the two paths unexercised.
        """

        def refuse(self: Path, *args: object, **kwargs: object) -> Path:
            msg = "lstat: embedded null character in path"
            raise ValueError(msg)

        monkeypatch.setattr(Path, "resolve", refuse)
        bag = DiagnosticBag()
        assert load_workspace(tree / "a\x00b.ddd.json", bag) is None
        assert "cannot read" in messages(bag)

    def test_a_file_the_filesystem_refuses_to_open(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Permissions, a device that went away, a name this platform will not have.

        Forced rather than provoked with an odd file name: which names are illegal is itself
        platform specific, and this is about the handler, not about the name.
        """
        write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})

        def refuse(self: Path, *args: object, **kwargs: object) -> str:
            msg = "Input/output error"
            raise OSError(5, msg)

        monkeypatch.setattr(Path, "read_text", refuse)
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "cannot read" in messages(bag)
        assert "Input/output error" in messages(bag)

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


class TestDiagnosticPlumbing:
    def test_a_severity_of_a_note_carrying_diagnostic_survives_a_copy(self) -> None:
        """`check --baseline` re-adds the baseline's errors; the notes must come along."""
        bag = DiagnosticBag()
        diagnostic = bag.add("schema", "bad", Location(Path("a.json")), notes=[("why", None)])
        assert isinstance(diagnostic, Diagnostic)
        assert diagnostic.severity is Severity.ERROR
        assert diagnostic.notes == (("why", None),)

    def test_a_pointer_index_sorts_as_a_number(self) -> None:
        assert index_order("a[10].b") > index_order("a[2].b")

    def test_a_key_that_looks_numeric_still_sorts_as_text(self) -> None:
        """``str.isdigit`` is true of a superscript two, which ``int`` refuses; whether a
        part is an index has to come from its position in the split, not from this check."""
        assert "²".isdigit()
        with pytest.raises(ValueError, match="invalid literal"):
            int("²")
        assert index_order("²") == ((True, "²"),)


class TestBrokenInitPointers:
    def test_a_wrong_typed_element_of_a_nested_init_is_reported_without_crashing(
        self, tree: Path
    ) -> None:
        """pydantic tries every branch of the init union and names each one in the location;
        those names are not keys of the document, and a sort key built from them must not
        compare a list index with a branch name."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "V", kind="value_block", dimensions=[1, 2], init=[[1, "bad"]]),
                ),
            },
        )
        listed = bag.sorted
        assert listed and {diagnostic.check for diagnostic in listed} == {"schema"}
        pointers = [diagnostic.location.pointer for diagnostic in listed if diagnostic.location]
        assert pointers
        assert not any(pointer.endswith((".bool", ".int", ".float")) for pointer in pointers)


class TestTheA2lClosure:
    def test_an_object_pulled_into_the_a2l_by_a_reference_is_checked_for_dimensions(
        self, tree: Path
    ) -> None:
        """The a2l backend pulls an axis's input into the file whatever its own export says;
        the dimension warning has to follow the same closure, not the object's own flag."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "M2", "uint8", dimensions=[2, 2, 2, 2], a2l={"export": False}),
                    declare("local", "Ax2", "uint16", kind="axis", size=4, input="M2"),
                ),
            },
        )
        assert "a2l-unrepresentable" in checks(bag)
        assert "'M2' has 4 dimensions" in messages(bag)
