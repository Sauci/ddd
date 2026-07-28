"""The paths the happy-path tests never reach: bad input, odd values, rare branches.

Every test here exists because a coverage gap pointed at a line no test executed. They are
kept in one place so it stays obvious which behaviour is only guarded by a coverage run.
"""

from __future__ import annotations

import importlib
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from conftest import (
    DEMO,
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.backends.a2l.model import build_a2l_model
from ddd.backends.a2l.options import A2lOptions
from ddd.backends.base import GeneratedFile, make_environment, render_template
from ddd.backends.c.literals import c_literal, guard_name
from ddd.diagnostics import (
    CHECKS,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.loading import load_workspace
from ddd.models import AnyDataObject, Datatype, EnumConversion, IdentityConversion, format_number
from ddd.models.objects import check_shape

DEFINITION = TypeAdapter(AnyDataObject)


class TestLoadingFailures:
    def test_a_root_component_that_does_not_match_the_contract(self, tree: Path) -> None:
        write_tree(tree, {"a.ddd.json": {"component": {"name": "A", "bogus": 1}}})
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert checks(bag) == ["schema"]

    def test_a_root_project_that_does_not_match_the_contract(self, tree: Path) -> None:
        write_tree(tree, {"p.ddd.json": {"project": {"name": "P", "bogus": 1}}})
        bag = DiagnosticBag()
        assert load_workspace(tree / "p.ddd.json", bag) is None
        assert checks(bag) == ["schema"]

    def test_an_included_project_that_does_not_match_the_contract(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json"),
                "sub.ddd.json": {"project": {"name": "Sub", "bogus": 1}},
            },
        )
        assert checks(bag) == ["schema"]

    def test_an_included_file_of_an_unknown_kind_is_skipped(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "mystery.ddd.json"),
                "mystery.ddd.json": {"something": "else"},
            },
        )
        assert checks(bag) == ["file-kind"]

    def test_a_missing_required_field_is_reported_without_a_value(self, tree: Path) -> None:
        """A "missing" error has no input to quote, unlike a wrong one."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": {"component": {"declarations": []}},
            },
        )
        assert checks(bag) == ["schema"]
        assert "component.name" in messages(bag)
        assert "got:" not in messages(bag)

    def test_a_directory_in_place_of_a_description_file(self, tree: Path) -> None:
        """Anything the filesystem refuses is reported, not raised."""
        (tree / "adirectory.ddd.json").mkdir()
        bag = DiagnosticBag()
        assert load_workspace(tree / "adirectory.ddd.json", bag) is None
        assert checks(bag) == ["file-not-found"]
        assert "cannot read" in messages(bag)


class TestDiagnosticRendering:
    def test_a_location_with_line_and_column(self) -> None:
        location = Location(Path("a.ddd.json"), line=3, column=7)
        assert location.render() == "a.ddd.json:3:7"

    def test_a_location_with_a_line_only(self) -> None:
        assert Location(Path("a.ddd.json"), line=3).render() == "a.ddd.json:3"

    def test_a_syntax_error_is_rendered_with_its_position(self, tree: Path) -> None:
        write_tree(tree, {"p.ddd.json": '{\n  "project": {,\n}'})
        bag = DiagnosticBag()
        load_workspace(tree / "p.ddd.json", bag)
        assert ":2:" in messages(bag)


class TestSeverityPolicy:
    def test_an_override_without_an_equals_sign(self) -> None:
        with pytest.raises(UnknownCheckError, match="expected 'check=severity'"):
            SeverityPolicy.from_strings(["unused-output"])

    def test_an_unregistered_check_defaults_to_error(self) -> None:
        """A typo in a check identifier inside DDD must not silently disable a finding."""
        assert "not-a-check" not in CHECKS
        assert SeverityPolicy().resolve("not-a-check") is Severity.ERROR

    def test_an_unregistered_check_is_still_reported(self) -> None:
        bag = DiagnosticBag()
        bag.add("not-a-check", "something went wrong")
        assert bag.has_errors


class TestModelEdges:
    def test_an_explicit_null_condition(self) -> None:
        model = component("A", declare("local", "X"))
        model["component"]["declarations"][0]["condition"] = None
        from ddd.models import ComponentFile

        assert ComponentFile.model_validate(model).component.declarations[0].condition is None

    def test_an_empty_conversion_object_means_identity(self) -> None:
        definition = DEFINITION.validate_python(
            {"name": "X", "datatype": "uint8", "conversion": {}}
        )
        assert isinstance(definition.conversion, IdentityConversion)

    def test_identity_and_enum_conversions_leave_the_value_alone(self) -> None:
        identity = IdentityConversion()
        assert identity.to_physical(7) == 7
        assert identity.to_raw(7) == 7
        enum = EnumConversion(name="E", enumerators=[{"name": "A", "value": 3}])
        assert enum.to_physical(3) == 3
        assert enum.to_raw(3) == 3
        assert enum.describe() == "enum(E)"

    def test_an_enum_that_is_not_an_object_at_all(self) -> None:
        """The shorthand expansion must pass anything it does not understand straight on."""
        with pytest.raises(ValidationError):
            EnumConversion.model_validate("not an object")

    def test_format_number_of_a_boolean(self) -> None:
        assert format_number(True) == "1"
        assert format_number(False) == "0"

    def test_a_scalar_inside_a_nested_init_is_rejected(self) -> None:
        assert check_shape((1, (2, 3)), (2, 2)) is not None
        with pytest.raises(ValueError, match="must be a list of 2 elements"):
            DEFINITION.validate_python(
                {"name": "X", "datatype": "uint8", "dimensions": [2, 2], "init": [1, [2, 3]]}
            )


class TestMismatchMessages:
    def test_the_shape_of_a_curve_is_described_as_coming_from_its_axes(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=3),
                    declare("output", "C", "uint8", kind="curve", axis="Ax"),
                ),
                "b.ddd.json": component("B", declare("input", "C", "uint8")),
            },
        )
        assert "definition-mismatch" in checks(bag)
        assert "shape: scalar != from the axes" in messages(bag)

    def test_a_missing_init_is_described_as_none(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", init=1)),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        assert checks(bag) == ["storage-mismatch"]
        assert "init: none != 1" in messages(bag)

    def test_a_volatile_disagreement_is_described(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", volatile=True)),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        assert checks(bag) == ["storage-mismatch"]
        assert "volatile: false != true" in messages(bag)

    def test_an_enum_conversion_is_named_in_a_mismatch(self, tree: Path) -> None:
        enum = {"kind": "enum", "name": "E", "enumerators": {"A": 0}}
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", conversion=enum)),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        assert "conversion: identity != enum(E)" in messages(bag)

    def test_a_boolean_with_a_nonsense_init(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "bool", init=7)),
            },
        )
        assert checks(bag) == ["init-invalid"]
        assert "is not a valid bool" in messages(bag)

    def test_a_map_whose_axes_are_unknown_has_no_shape(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "M", "uint8", kind="map", x_axis="Nx", y_axis="Ny")
                ),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["unknown-reference", "unknown-reference"]
        assert dictionary.by_name["M"].shape == ()


class TestBackendEdges:
    def test_a_curve_whose_axis_is_missing_gets_no_axis_descr(self, tree: Path) -> None:
        """Only reachable with a relaxed severity, but the backend must not crash."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "C", "uint8", kind="curve", axis="Nx")
                ),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None
        model = build_a2l_model(dictionary, A2lOptions(), "test")
        assert model.characteristics[0].axis_descrs == ()

    def test_one_enum_with_two_units_shares_its_value_table(self, tree: Path) -> None:
        enum = {"kind": "enum", "name": "E", "enumerators": {"A": 0, "B": 1}}
        files = render_files(
            *_dictionary_of(
                tree,
                declare("local", "X", "uint8", unit="Hz", conversion=enum),
                declare("local", "Y", "uint8", unit="V", conversion=enum),
            )
        )
        content = next(f.content for f in files if f.path.name.endswith(".a2l"))
        assert content.count("/begin COMPU_VTAB") == 1
        assert content.count("/begin COMPU_METHOD") == 2

    def test_a_prefix_starting_with_a_digit_still_yields_a_valid_guard(self) -> None:
        assert guard_name("2fast", "types") == "N2FAST_TYPES_H"

    def test_float_literals_are_never_mistaken_for_integers(self) -> None:
        assert c_literal(2, Datatype.FLOAT32) == "2.0F"
        assert c_literal(1e17, Datatype.FLOAT64) == "1e+17"

    def test_a_template_without_a_trailing_newline_gets_one(self, tree: Path) -> None:
        (tree / "templates").mkdir()
        (tree / "templates" / "bare.jinja").write_text("no newline here", encoding="utf-8")
        environment = make_environment(tree / "templates")
        file = render_template(environment, "bare.jinja", tree / "out.txt")
        assert file.content == "no newline here\n"
        assert isinstance(file, GeneratedFile)


def _dictionary_of(tree: Path, *declarations: dict) -> tuple[object, Path]:
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", *declarations),
        },
    )
    assert dictionary is not None, [d.render() for d in bag]
    return dictionary, tree / "gen"


class TestCommandLineEdges:
    def test_listing_a_project_that_cannot_be_loaded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import EXIT_FINDINGS, main

        assert main(["list", "no-such-file.ddd.json"]) == EXIT_FINDINGS
        assert "file-not-found" in capsys.readouterr().err

    def test_dump_prints_the_contract(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        from ddd.cli import EXIT_OK, main
        from ddd.ir import DataDictionary

        assert main(["dump", str(DEMO)]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert DataDictionary.model_validate(payload).name == "DemoDevice"

    def test_dump_of_a_project_that_cannot_be_loaded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import EXIT_FINDINGS, main

        assert main(["dump", "no-such-file.ddd.json"]) == EXIT_FINDINGS
        assert "file-not-found" in capsys.readouterr().err

    def test_dump_reports_findings_next_to_the_contract(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import EXIT_OK, main

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
            },
        )
        assert main(["dump", str(tmp_path / "p.ddd.json")]) == EXIT_OK
        captured = capsys.readouterr()
        assert '"name": "X"' in captured.out
        assert "unused-output" in captured.err

    def test_dump_in_json_format_prints_nothing_else(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json

        from ddd.cli import EXIT_OK, main

        assert main(["dump", str(DEMO), "--format", "json"]) == EXIT_OK
        captured = capsys.readouterr()
        json.loads(captured.out)
        assert captured.err == ""

    def test_cmake_dir_without_the_packaged_module(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd import cli
        from ddd.cli import EXIT_USAGE, main

        monkeypatch.setattr(cli, "cmake_module_directory", lambda: None)
        assert main(["cmake-dir"]) == EXIT_USAGE
        assert "not part of this installation" in capsys.readouterr().err

    def test_the_module_entry_point_exits_with_the_command_status(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``python -m ddd`` has to hand the exit code of the command to the shell."""
        monkeypatch.setattr(sys, "argv", ["ddd", "checks"])
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_module("ddd", run_name="__main__")
        assert exit_info.value.code == 0
        assert "multiple-producers" in capsys.readouterr().out

    def test_importing_the_entry_point_module_does_not_run_it(self) -> None:
        """Only `python -m ddd` may call sys.exit; a plain import must stay silent."""
        module = importlib.import_module("ddd.__main__")
        importlib.reload(module)  # re-executes with __name__ != "__main__"

    def test_the_module_entry_point_runs_as_documented(self) -> None:
        """`python -m ddd` is the documented way to run from a source checkout."""
        result = subprocess.run(
            [sys.executable, "-m", "ddd", "--version"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[1],
            env={**_source_env()},
        )
        assert result.stdout.startswith("ddd ")


def _source_env() -> dict[str, str]:
    import os

    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    return environment
