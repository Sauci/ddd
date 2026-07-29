"""Tests for the generated c code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, project, render_files, run_analysis
from ddd.backends import WriteStatus, write


def generate(tree: Path, files: dict[str, Any], **options: Any) -> dict[str, str]:
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [d.render() for d in bag]
    assert not bag.has_errors, [d.render() for d in bag]
    rendered = render_files(dictionary, tree / "gen", **options)
    return {file.path.name: file.content for file in rendered}


def simple(*declarations: dict[str, Any], name: str = "A") -> dict[str, Any]:
    return {
        "project.ddd.json": project("P", "a.ddd.json"),
        "a.ddd.json": component(name, *declarations, description="the component"),
    }


class TestGlobalDefinitionFile:
    def test_scalar_definition(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16", init=7)))
        assert "uint16_t Speed = 7U;" in files["ddd_globals.c"]
        assert 'include "ddd_globals.h"' in files["ddd_globals.c"]

    def test_without_init_no_initialiser_is_emitted(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16")))
        assert "uint16_t Speed;" in files["ddd_globals.c"]

    def test_volatile(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16", volatile=True)))
        assert "volatile uint16_t Speed;" in files["ddd_globals.c"]

    def test_signed_negative_and_float_literals(self, tree: Path) -> None:
        files = generate(
            tree,
            simple(
                declare("local", "A", "int16", init=-400),
                declare("local", "B", "float32", init=1.5),
                declare("local", "C", "float64", init=2),
                declare("local", "D", "bool", init=True),
                declare("local", "E", "uint64", init=5),
                declare("local", "F", "int64", init=-5),
            ),
        )
        source = files["ddd_globals.c"]
        assert "int16_t A = -400;" in source
        assert "float B = 1.5F;" in source
        assert "double C = 2.0;" in source
        assert "bool D = true;" in source
        assert "uint64_t E = 5ULL;" in source
        assert "int64_t F = -5LL;" in source

    def test_one_dimensional_array(self, tree: Path) -> None:
        declaration = declare("local", "A", "uint8", dimensions=[3], init=[1, 2, 3])
        files = generate(tree, simple(declaration))
        assert "uint8_t A[3] = { 1U, 2U, 3U };" in files["ddd_globals.c"]

    def test_long_array_is_wrapped(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", "uint8", dimensions=[10], init=1)))
        source = files["ddd_globals.c"]
        assert "uint8_t A[10] = {\n    1U, 1U, 1U, 1U, 1U, 1U, 1U, 1U,\n    1U, 1U\n};" in source

    def test_two_dimensional_array(self, tree: Path) -> None:
        files = generate(
            tree, simple(declare("local", "A", "int8", dimensions=[2, 2], init=[[1, 2], [3, 4]]))
        )
        assert "int8_t A[2][2] = {\n    { 1, 2 },\n    { 3, 4 }\n};" in files["ddd_globals.c"]

    def test_condition_wraps_the_definition(self, tree: Path) -> None:
        files = generate(
            tree, simple(declare("local", "A", condition="defined(FEATURE_X) && VERSION > 2"))
        )
        source = files["ddd_globals.c"]
        assert "#if defined(FEATURE_X) && VERSION > 2\n" in source
        assert "#endif /* defined(FEATURE_X) && VERSION > 2 */" in source
        assert source.index("#if ") < source.index("uint8_t A;") < source.index("#endif")

    def test_description_and_unit_become_a_comment(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", description="Flow rate", unit="l/min")))
        assert "/** Flow rate [l/min] */" in files["ddd_globals.c"]

    def test_comment_end_marker_is_escaped(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", description="a */ b")))
        assert "/** a * / b */" in files["ddd_globals.c"]

    def test_variables_are_grouped_by_owning_component(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X"), declare("local", "Y")),
            },
        )
        source = files["ddd_globals.c"]
        assert source.index("uint8_t X;") < source.index("uint8_t Y;")
        assert source.count("uint8_t X;") == 1


class TestTypesHeader:
    def test_enum_typedef(self, tree: Path) -> None:
        files = generate(
            tree,
            simple(
                declare(
                    "local",
                    "Mode",
                    conversion={
                        "kind": "enum",
                        "name": "Mode_t",
                        "enumerators": [
                            {"name": "OFF", "value": 0, "description": "switched off"},
                            {"name": "ON", "value": 1},
                        ],
                    },
                )
            ),
        )
        header = files["ddd_types.h"]
        assert "typedef enum\n{\n    OFF = 0, /**< switched off */\n    ON = 1\n} Mode_t;" in header

    def test_stdint_is_included_only_when_needed(self, tree: Path) -> None:
        assert "#include <stdint.h>" in generate(tree, simple(declare("local", "A")))["ddd_types.h"]
        only_bool = generate(tree, simple(declare("local", "A", "bool")))["ddd_types.h"]
        assert "#include <stdint.h>" not in only_bool
        assert "#include <stdbool.h>" in only_bool

    def test_include_guard(self, tree: Path) -> None:
        """The template writes its own guard; the model only normalises the spelling."""
        files = generate(tree, simple(declare("local", "A")))
        assert "#ifndef DDD_TYPES_H" in files["ddd_types.h"]
        assert "#endif /* DDD_TYPES_H */" in files["ddd_types.h"]


class TestComponentHeaders:
    def test_only_the_own_interface_is_visible(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Shared"), declare("local", "Hidden")
                ),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        assert "Shared" in files["B.h"]
        assert "Hidden" not in files["B.h"]
        assert "Hidden" in files["A.h"]

    def test_sections(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Out"), declare("local", "Own")),
                "b.ddd.json": component("B", declare("input", "Out")),
            },
        )
        header = files["A.h"]
        assert "extern uint8_t Out;" in header
        assert "extern uint8_t Own;" in header
        assert "/* outputs - written by A" in header
        assert "/* locals - owned exclusively by A */" in header
        assert "/* inputs" not in header

    def test_input_mentions_the_producer(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("Producer", declare("output", "X")),
                "b.ddd.json": component("Consumer", declare("input", "X")),
            },
        )
        assert "extern uint8_t X;  /* produced by Producer */" in files["Consumer.h"]

    def test_const_inputs(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
            },
            const_inputs=True,
        )
        assert "extern const uint8_t X;" in files["B.h"]
        assert "extern uint8_t X;" in files["A.h"]
        assert "const" not in files["ddd_globals.c"]

    def test_empty_component_gets_a_header(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")},
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "This component declares no global variable." in files["A.h"]

    def test_header_uses_the_own_condition(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", condition="defined(F)")),
                "b.ddd.json": component("B", declare("input", "X", condition="defined(F)")),
            },
        )
        assert "#if defined(F)" in files["B.h"]


class TestWriting:
    def test_create_update_and_unchanged(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        first = write(render_files(dictionary, tree / "gen"))
        assert {result.status for result in first} == {WriteStatus.CREATED}
        assert (tree / "gen" / "ddd_globals.c").is_file()

        second = write(render_files(dictionary, tree / "gen"))
        assert {result.status for result in second} == {WriteStatus.UNCHANGED}

        (tree / "gen" / "ddd_globals.c").write_text("stale", encoding="utf-8")
        third = write(render_files(dictionary, tree / "gen"))
        assert any(
            result.status is WriteStatus.UPDATED and result.path.name == "ddd_globals.c"
            for result in third
        )

    def test_dry_run_writes_nothing(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        results = write(render_files(dictionary, tree / "gen"), dry_run=True)
        assert {result.status for result in results} == {WriteStatus.CREATED}
        assert not (tree / "gen").exists()

    def test_files_use_unix_line_endings(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        write(render_files(dictionary, tree / "gen"))
        assert b"\r\n" not in (tree / "gen" / "ddd_globals.c").read_bytes()

    def test_a2l_can_be_switched_off(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A")), emit_a2l=False)
        assert not any(name.endswith(".a2l") for name in files)

    def test_a_component_may_not_overwrite_a_shared_file(self, tree: Path) -> None:
        """A component named after a shared file is refused, and the message says who by."""
        with pytest.raises(ValueError, match=r"c backend would write 'ddd_types\.h' twice"):
            generate(tree, simple(declare("local", "A"), name="ddd_types"))
