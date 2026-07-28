"""End to end tests of the command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import DEMO, INCONSISTENT, component, declare, project, write_tree
from ddd.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, main


class TestCheck:
    def test_consistent_project(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(DEMO)]) == EXIT_OK
        assert "are consistent" in capsys.readouterr().err

    def test_inconsistent_project(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(INCONSISTENT)]) == EXIT_FINDINGS
        captured = capsys.readouterr().err
        assert "multiple-producers" in captured
        assert "definition-mismatch" in captured
        assert "4 errors, 1 warning" in captured

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(INCONSISTENT), "--format", "json"]) == EXIT_FINDINGS
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"] == {"error": 4, "warning": 1, "info": 0}
        assert payload["diagnostics"][0]["check"] == "multiple-producers"
        assert payload["diagnostics"][0]["location"]["pointer"].startswith("component")

    def test_severity_override(self) -> None:
        arguments = [
            "check",
            str(INCONSISTENT),
            "-W",
            "multiple-producers=ignore",
            "-W",
            "definition-mismatch=ignore",
            "-W",
            "missing-producer=ignore",
            "-W",
            "local-conflict=ignore",
        ]
        assert main(arguments) == EXIT_OK

    def test_strict_promotes_warnings(self) -> None:
        assert main(["check", str(DEMO)]) == EXIT_OK
        assert main(["check", str(DEMO), "--strict"]) == EXIT_OK

    def test_unknown_check_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(DEMO), "-W", "nope=error"]) == EXIT_USAGE
        assert "unknown check 'nope'" in capsys.readouterr().err

    def test_unknown_severity_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(DEMO), "-W", "unused-output=loud"]) == EXIT_USAGE
        assert "unknown severity" in capsys.readouterr().err

    def test_fixed_check_cannot_be_overridden(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(DEMO), "-W", "schema=ignore"]) == EXIT_USAGE
        assert "cannot be changed" in capsys.readouterr().err

    def test_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", "does-not-exist.ddd.json"]) == EXIT_FINDINGS
        assert "file-not-found" in capsys.readouterr().err

    def test_warnings_alone_do_not_fail_the_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
            },
        )
        assert main(["check", str(tmp_path / "p.ddd.json")]) == EXIT_OK
        captured = capsys.readouterr().err
        assert "unused-output" in captured
        assert "1 warning" in captured
        assert "are consistent" not in captured


class TestGenerate:
    def test_writes_every_artefact(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert main(["generate", str(DEMO), "-o", str(output)]) == EXIT_OK
        names = sorted(path.name for path in output.iterdir())
        assert names == [
            "Controller.h",
            "DemoDevice.a2l",
            "EventLogger.h",
            "SensorHub.h",
            "UserInterface.h",
            "ddd_globals.c",
            "ddd_globals.h",
            "ddd_types.h",
        ]

    def test_is_idempotent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output)])
        capsys.readouterr()
        main(["generate", str(DEMO), "-o", str(output)])
        assert "unchanged" in capsys.readouterr().err

    def test_refuses_an_inconsistent_project(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert main(["generate", str(INCONSISTENT), "-o", str(output)]) == EXIT_FINDINGS
        assert not output.exists()

    def test_force_generates_anyway(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert main(["generate", str(INCONSISTENT), "-o", str(output), "--force"]) == EXIT_FINDINGS
        assert (output / "ddd_globals.c").is_file()

    def test_dry_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        assert main(["generate", str(DEMO), "-o", str(output), "--dry-run"]) == EXIT_OK
        assert "would write" in capsys.readouterr().err
        assert not output.exists()

    def test_prefix_and_no_a2l(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output), "--prefix", "device", "--no-a2l"])
        assert (output / "device_globals.c").is_file()
        assert not list(output.glob("*.a2l"))

    def test_address_map(self, tmp_path: Path) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output), "--address-map", str(addresses)])
        assert "ECU_ADDRESS 0x20001000" in (output / "DemoDevice.a2l").read_text(encoding="utf-8")

    def test_broken_address_map(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "nowhere"}', encoding="utf-8")
        code = main(
            ["generate", str(DEMO), "-o", str(tmp_path / "gen"), "--address-map", str(addresses)]
        )
        assert code == EXIT_USAGE
        assert "is not a number" in capsys.readouterr().err

    def test_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert {entry["status"] for entry in payload["generated"]} == {"created"}


class TestList:
    def test_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["list", str(DEMO)]) == EXIT_OK
        out = capsys.readouterr().out
        assert "VARIABLE" in out
        assert "ValueE" in out
        assert "UserInterface, EventLogger" in out

    def test_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["list", str(DEMO), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["project"] == "DemoDevice"
        entry = next(v for v in payload["variables"] if v["name"] == "ValueE")
        assert entry["owner"] == "Controller"
        assert entry["consumers"] == ["UserInterface", "EventLogger"]
        assert entry["conversion"] == {"kind": "linear", "factor": 0.25, "offset": 0.0}


class TestSchemaAndChecks:
    def test_schema_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["schema", "component"]) == EXIT_OK
        schema = json.loads(capsys.readouterr().out)
        assert "component" in schema["properties"]

    def test_schema_to_file(self, tmp_path: Path) -> None:
        target = tmp_path / "schema" / "project-schema.json"
        assert main(["schema", "project", "-o", str(target)]) == EXIT_OK
        assert "project" in json.loads(target.read_text(encoding="utf-8"))["properties"]

    def test_checks_listing(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["checks"]) == EXIT_OK
        out = capsys.readouterr().out
        assert "multiple-producers" in out
        assert "(fixed)" in out

    def test_cmake_dir(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["cmake-dir"]) == EXIT_OK
        directory = Path(capsys.readouterr().out.strip())
        assert (directory / "Ddd.cmake").is_file()

    def test_checks_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["checks", "--format", "json"]) == EXIT_OK
        entries = json.loads(capsys.readouterr().out)
        assert {"check", "default_severity", "description", "overridable"} <= set(entries[0])


class TestSingleComponent:
    def test_a_component_file_can_be_checked_on_its_own(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("input", "X"))})
        assert main(["check", str(tmp_path / "a.ddd.json")]) == EXIT_FINDINGS
        assert "missing-producer" in capsys.readouterr().err

    def test_project_without_components(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("Empty")})
        arguments = ["generate", str(tmp_path / "p.ddd.json"), "-o", str(tmp_path / "gen")]
        assert main(arguments) == EXIT_OK
        source = (tmp_path / "gen" / "ddd_globals.c").read_text(encoding="utf-8")
        assert "does not define any global variable" in source
