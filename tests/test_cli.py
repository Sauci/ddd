"""End to end tests of the command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import (
    DEMO,
    INCONSISTENT,
    TEMPLATES,
    component,
    declare,
    project,
    write_tree,
)
from ddd.build_info import BUILD_INFO_FORMAT
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

    def test_an_instantiated_structure_with_an_unknown_member_type_still_reports(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The unknown-type finding survives the structure being instantiated.

        This used to crash with a KeyError once a declaration named the broken structure,
        which swallowed every finding of the run; now the instance is dropped from
        resolution and every command finishes with the finding on record.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Broken_t",
                            "members": [
                                {"name": "ghost", "member": "value", "typename": "Missing_t"}
                            ],
                        }
                    ]
                },
                "a.ddd.json": component("A", declare("output", "V", typename="Broken_t")),
            },
        )
        target = str(tmp_path / "p.ddd.json")
        assert main(["check", target]) == EXIT_FINDINGS
        assert "unknown-type" in capsys.readouterr().err
        assert main(["dump", target]) == EXIT_FINDINGS
        assert main(["list", target]) == EXIT_FINDINGS
        capsys.readouterr()


class TestGenerate:
    def test_writes_every_artefact(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert main(["generate", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)]) == EXIT_OK
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
        main(["generate", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)])
        capsys.readouterr()
        main(["generate", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)])
        assert "unchanged" in capsys.readouterr().err

    def test_refuses_an_inconsistent_project(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert (
            main(["generate", str(INCONSISTENT), "-o", str(output), "-t", str(TEMPLATES)])
            == EXIT_FINDINGS
        )
        assert not output.exists()

    def test_force_generates_anyway(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert (
            main(
                ["generate", str(INCONSISTENT), "-o", str(output), "-t", str(TEMPLATES), "--force"]
            )
            == EXIT_FINDINGS
        )
        assert (output / "ddd_globals.c").is_file()

    def test_dry_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        assert (
            main(["generate", str(DEMO), "-o", str(output), "-t", str(TEMPLATES), "--dry-run"])
            == EXIT_OK
        )
        assert "would write" in capsys.readouterr().err
        assert not output.exists()

    def test_the_templates_decide_what_the_files_are_called(self, tmp_path: Path) -> None:
        """Renaming a template renames what it generates; there is no prefix option."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "device_globals.c.jinja2").write_text(
            "/* {{ model.project }} */\n", encoding="utf-8"
        )
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output), "-t", str(templates), "--no-a2l"])
        assert (output / "device_globals.c").is_file()
        assert not (output / "ddd_globals.c").exists()
        assert not list(output.glob("*.a2l"))

    def test_a_template_directory_with_nothing_to_render(self, tmp_path: Path) -> None:
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "_helper.jinja2").write_text("{% macro x() %}{% endmacro %}", encoding="utf-8")
        arguments = ["generate", str(DEMO), "-o", str(tmp_path / "gen"), "-t", str(templates)]
        assert main(arguments) == EXIT_USAGE

    def broken_template(self, tmp_path: Path, content: str) -> list[str]:
        """A template directory holding one broken template, and the arguments to render it."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "ddd_globals.c.jinja2").write_text(content, encoding="utf-8")
        output = str(tmp_path / "gen")
        return ["generate", str(DEMO), "-o", output, "-t", str(templates), "--no-a2l"]

    def test_a_template_naming_nothing_the_model_has_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The templates are the project's own files, so a typo in one is reported like any
        other input mistake - one line naming the template - not as a jinja traceback."""
        arguments = self.broken_template(tmp_path, "/* fine */\n/* {{ model.prjoect }} */\n")
        assert main(arguments) == EXIT_USAGE
        err = capsys.readouterr().err
        assert "ddd: cannot render template 'ddd_globals.c.jinja2', line 2" in err
        assert "prjoect" in err
        assert "Traceback" not in err

    def test_a_template_that_does_not_parse_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        arguments = self.broken_template(tmp_path, "line one\n{% if %}\n")
        assert main(arguments) == EXIT_USAGE
        err = capsys.readouterr().err
        assert "ddd: cannot render template 'ddd_globals.c.jinja2', line 2" in err
        assert "Traceback" not in err

    def test_address_map(self, tmp_path: Path) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        output = tmp_path / "gen"
        main(
            [
                "generate",
                str(DEMO),
                "-o",
                str(output),
                "-t",
                str(TEMPLATES),
                "--address-map",
                str(addresses),
            ]
        )
        assert "ECU_ADDRESS 0x20001000" in (output / "DemoDevice.a2l").read_text(encoding="utf-8")

    def test_broken_address_map(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "nowhere"}', encoding="utf-8")
        code = main(
            [
                "generate",
                str(DEMO),
                "-o",
                str(tmp_path / "gen"),
                "-t",
                str(TEMPLATES),
                "--address-map",
                str(addresses),
            ]
        )
        assert code == EXIT_USAGE
        assert "is not an integer" in capsys.readouterr().err

    def test_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        main(["generate", str(DEMO), "-o", str(output), "-t", str(TEMPLATES), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert {entry["status"] for entry in payload["generated"]} == {"created"}


PINNED_LIST_PAYLOAD = """\
{
  "project": "Pin",
  "components": [
    {
      "name": "A",
      "description": "",
      "source": "a.ddd.json",
      "declarations": [
        {
          "name": "Temperature",
          "scope": "local",
          "condition": null
        },
        {
          "name": "State",
          "scope": "local",
          "condition": null
        }
      ]
    }
  ],
  "variables": [
    {
      "name": "State",
      "kind": "measurement",
      "datatype": "uint8",
      "description": "",
      "unit": "",
      "conversion": {
        "kind": "enum",
        "name": "PinState",
        "enumerators": [
          {
            "name": "STATE_OK",
            "value": 0,
            "description": ""
          },
          {
            "name": "STATE_FAULT",
            "value": 15,
            "description": ""
          }
        ]
      },
      "limits": {
        "min": 0.0,
        "max": 15.0
      },
      "shape": [],
      "init": 15,
      "section": null,
      "volatile": false,
      "condition": null,
      "references": {},
      "owner": "A",
      "consumers": [],
      "local": true,
      "a2l": {
        "export": true,
        "format": null,
        "display_identifier": null
      }
    },
    {
      "name": "Temperature",
      "kind": "measurement",
      "datatype": "uint16",
      "description": "",
      "unit": "degC",
      "conversion": {
        "kind": "linear",
        "factor": 0.05,
        "offset": 0.0
      },
      "limits": {
        "min": 0.0,
        "max": 3276.75
      },
      "shape": [],
      "init": 800,
      "section": null,
      "volatile": false,
      "condition": null,
      "references": {},
      "owner": "A",
      "consumers": [],
      "local": true,
      "a2l": {
        "export": true,
        "format": null,
        "display_identifier": null
      }
    }
  ],
  "diagnostics": [],
  "summary": {
    "error": 0,
    "warning": 0,
    "info": 0
  }
}
"""
"""The whole payload of ``ddd list --format json``, captured before the text table learned to
state physical readings. The json is a published shape, so it must stay byte-identical: the
reading is a spelling for people, and it lives in the text table alone."""


class TestList:
    def test_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["list", str(DEMO)]) == EXIT_OK
        out = capsys.readouterr().out
        assert "VARIABLE" in out
        assert "ValueE" in out
        assert "UserInterface, EventLogger" in out

    def test_table_states_the_physical_reading_of_a_scalar_init(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["list", str(DEMO)]) == EXIT_OK
        out = capsys.readouterr().out
        assert "INIT" in out
        assert "3200 (= 800 Hz)" in out  # linear, with the unit of the object
        assert "0 (= STATE_OFF)" in out  # an enum init reads as its enumerator
        assert "[...]" in out  # a nested init is abbreviated, not spelled out
        assert "1000 (= 1 V)" in out  # the reading round-trips through format_number

    def test_json_payload_is_byte_identical_to_the_published_shape(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The text table may say what a raw init reads as; the json payload may not move."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("Pin", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "Temperature",
                        datatype="uint16",
                        unit="degC",
                        conversion={"kind": "linear", "factor": 0.05, "offset": 0.0},
                        init=800,
                    ),
                    declare(
                        "local",
                        "State",
                        conversion={
                            "kind": "enum",
                            "name": "PinState",
                            "enumerators": {"STATE_OK": 0, "STATE_FAULT": 15},
                        },
                        init=15,
                    ),
                ),
            },
        )
        assert main(["list", str(tmp_path / "p.ddd.json"), "--format", "json"]) == EXIT_OK
        assert capsys.readouterr().out == PINNED_LIST_PAYLOAD

    def test_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["list", str(DEMO), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["project"] == "DemoDevice"
        entry = next(v for v in payload["variables"] if v["name"] == "ValueE")
        assert entry["owner"] == "Controller"
        assert entry["consumers"] == ["UserInterface", "EventLogger"]
        assert entry["conversion"] == {"kind": "linear", "factor": 0.25, "offset": 0.0}
        # The json contract of every reporting command: diagnostics and their summary.
        assert payload["diagnostics"] == []
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}


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
        arguments = [
            "generate",
            str(tmp_path / "p.ddd.json"),
            "-o",
            str(tmp_path / "gen"),
            "-t",
            str(TEMPLATES),
        ]
        assert main(arguments) == EXIT_OK
        source = (tmp_path / "gen" / "ddd_globals.c").read_text(encoding="utf-8")
        assert "does not define any global variable" in source


class TestSources:
    """What a build system asks for when it needs to know whether to run DDD again."""

    def test_every_included_file_is_listed(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["sources", str(DEMO)]) == EXIT_OK
        listed = capsys.readouterr().out.split()
        assert str(DEMO.as_posix()) in listed
        # The components are the point: the project file alone would never go out of date.
        assert any(name.endswith("controller.ddd.json") for name in listed)
        assert any(name.endswith("event_logger.ddd.json") for name in listed)

    def test_an_unreadable_root_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["sources", str(tmp_path / "absent.ddd.json")]) == EXIT_FINDINGS
        assert "does not exist" in capsys.readouterr().err

    def test_json_output_carries_the_sources_and_the_summary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The json contract of every reporting command holds here too."""
        assert main(["sources", str(DEMO), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert str(DEMO.as_posix()) in payload["sources"]
        assert any(name.endswith("controller.ddd.json") for name in payload["sources"])
        assert payload["diagnostics"] == []
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}

    def test_an_unreadable_root_is_a_json_finding(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        arguments = ["sources", str(tmp_path / "absent.ddd.json"), "--format", "json"]
        assert main(arguments) == EXIT_FINDINGS
        payload = json.loads(capsys.readouterr().out)
        assert payload["sources"] == []
        assert payload["diagnostics"][0]["check"] == "file-not-found"
        assert payload["summary"]["error"] == 1


class TestBuildInfo:
    """What a build hands to an editor, so that both report the same project the same way.

    The two things in it are the two a description file cannot state: which project the build
    actually runs DDD on, and under which severity policy.
    """

    def test_it_records_the_project_and_the_policy(self, tmp_path: Path) -> None:
        target = tmp_path / "ddd" / "firmware" / "ddd-build.json"
        assert (
            main(
                [
                    "build-info",
                    str(DEMO),
                    "-o",
                    str(target),
                    "--image",
                    "firmware.elf",
                    "-W",
                    "unused-output=info",
                    "--strict",
                ]
            )
            == EXIT_OK
        )
        recorded = json.loads(target.read_text(encoding="utf-8"))
        assert recorded["project"] == DEMO.resolve().as_posix()
        assert recorded["image"] == "firmware.elf"
        assert recorded["severity"] == ["unused-output=info"]
        assert recorded["strict"] is True
        assert recorded["format"] == BUILD_INFO_FORMAT

    def test_the_recorded_project_is_absolute(self, tmp_path: Path) -> None:
        """Whoever reads this file is not in the directory the build ran in."""
        target = tmp_path / "ddd-build.json"
        assert main(["build-info", str(DEMO), "-o", str(target)]) == EXIT_OK
        recorded = json.loads(target.read_text(encoding="utf-8"))
        assert Path(recorded["project"]).is_absolute()
        # Everything else is optional, so a build that tunes nothing writes a usable file.
        assert recorded["image"] == ""
        assert recorded["severity"] == []
        assert recorded["strict"] is False

    def test_a_project_that_does_not_exist_yet_is_recorded_anyway(self, tmp_path: Path) -> None:
        """The collected project description is written later in the same configure run.

        ``file(GENERATE)`` runs at the end of a cmake configure, after the ``execute_process``
        that writes this file, so refusing to name a file that is not there yet would fail
        every first configure of every project that lets cmake collect its components.
        """
        target = tmp_path / "ddd-build.json"
        absent = tmp_path / "build" / "firmware.ddd.json"
        assert main(["build-info", str(absent), "-o", str(target)]) == EXIT_OK
        assert json.loads(target.read_text(encoding="utf-8"))["project"] == absent.as_posix()

    def test_a_severity_override_naming_no_check_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """At configure time, where the typo is, rather than at build time where it lands."""
        target = tmp_path / "ddd-build.json"
        assert main(["build-info", str(DEMO), "-o", str(target), "-W", "nonsense=info"]) == (
            EXIT_USAGE
        )
        assert "unknown check 'nonsense'" in capsys.readouterr().err
        assert not target.exists()

    def test_it_is_not_named_like_a_description_file(self) -> None:
        """``*.ddd.json`` means "a DDD description file", and this is a document about one."""
        from ddd.build_info import BUILD_INFO_FILENAME

        assert not BUILD_INFO_FILENAME.endswith(".ddd.json")


class TestBaselineIsolation:
    """The findings of a past delivery are not findings of this run."""

    def test_the_baseline_findings_are_not_reported_twice(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        project_file = str(tmp_path / "p.ddd.json")
        assert main(["dump", project_file]) == EXIT_OK
        (tmp_path / "base.json").write_text(capsys.readouterr().out, encoding="utf-8")

        # Comparing the project against a dictionary of itself: one clean verdict, and the
        # project's own warnings are not doubled by the baseline being analysed as well.
        assert main(["check", project_file, "--baseline", str(tmp_path / "base.json")]) == EXIT_OK

    def test_a_baseline_that_cannot_be_read_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
                # The baseline reads fine but does not resolve: two producers of Y is the
                # error, and neither output is read, which is a warning. Only the error is
                # carried over - a warning about a past delivery is nobody's problem now.
                "bad.ddd.json": project("B", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": component("First", declare("output", "Y")),
                "two.ddd.json": component("Second", declare("output", "Y")),
            },
        )
        arguments = [
            "check",
            str(tmp_path / "p.ddd.json"),
            "--baseline",
            str(tmp_path / "bad.ddd.json"),
        ]
        assert main(arguments) == EXIT_FINDINGS
        assert "in the baseline:" in capsys.readouterr().err

    def test_a_bom_marked_description_is_compared_as_a_description(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The sniff has to read the byte order mark the loader accepts.

        Read with plain utf-8, a BOM'd project or component file failed the sniff, was
        taken for a dumped dictionary, and the comparison produced schema findings about a
        perfectly good description.
        """
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("local", "X"))})
        plain = tmp_path / "a.ddd.json"
        bom = tmp_path / "bom.ddd.json"
        bom.write_text(chr(0xFEFF) + plain.read_text(encoding="utf-8"), encoding="utf-8")
        # On either side of a comparison, and as the baseline of a check.
        assert main(["compare", str(plain), str(bom)]) == EXIT_OK
        assert main(["compare", str(bom), str(plain)]) == EXIT_OK
        assert main(["check", str(plain), "--baseline", str(bom)]) == EXIT_OK
        assert "schema" not in capsys.readouterr().err


class TestOutputDirectory:
    def test_an_output_directory_that_is_a_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("local", "X"))})
        (tmp_path / "blocked").write_text("not a directory", encoding="utf-8")
        arguments = [
            "generate",
            str(tmp_path / "a.ddd.json"),
            "-o",
            str(tmp_path / "blocked"),
            "-t",
            str(TEMPLATES),
        ]
        assert main(arguments) == EXIT_USAGE
        assert "cannot write into" in capsys.readouterr().err


class TestVersion:
    """The version is what a bug report quotes, so both spellings have to work."""

    @pytest.mark.parametrize("flag", ["-v", "--version"])
    def test_the_version_is_printed_and_the_run_ends(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd import __version__

        # argparse exits directly for an action of type "version".
        with pytest.raises(SystemExit) as exit_code:
            main([flag])
        assert exit_code.value.code == EXIT_OK
        assert capsys.readouterr().out.strip() == f"ddd {__version__}"


class TestTemplatesDir:
    """The example templates are a starting point to copy, never a fallback."""

    def test_it_prints_a_directory_holding_templates(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["templates-dir"]) == EXIT_OK
        directory = Path(capsys.readouterr().out.strip())
        assert directory.is_dir()
        rendered = sorted(p.name for p in directory.glob("*.jinja2"))
        assert "ddd_globals.c.jinja2" in rendered
        assert "{component}.h.jinja2" in rendered
        assert "_macros.jinja2" in rendered  # the helper travels with them

    def test_the_printed_directory_really_generates(self, tmp_path: Path) -> None:
        """Whatever the command prints has to be usable as it stands."""
        import contextlib
        import io

        from ddd.cli import main as run

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run(["templates-dir"])
        directory = out.getvalue().strip()
        assert run(["generate", str(DEMO), "-o", str(tmp_path / "gen"), "-t", directory]) == EXIT_OK
        assert (tmp_path / "gen" / "ddd_globals.c").is_file()

    def test_an_installation_without_the_examples(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd import cli

        monkeypatch.setattr(cli, "example_template_directory", lambda: None)
        assert main(["templates-dir"]) == EXIT_USAGE
        assert "not part of this installation" in capsys.readouterr().err


class TestSchemaAll:
    """One command for a project setting up its editor, rather than one per file format."""

    def test_it_writes_every_schema_into_a_directory(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ddd.cli import _SCHEMA_MODELS, SCHEMA_FILENAME, schema_text

        output = tmp_path / "schemas"
        assert main(["schema", "all", "-o", str(output)]) == EXIT_OK
        assert "wrote" in capsys.readouterr().err
        for kind in _SCHEMA_MODELS:
            path = output / SCHEMA_FILENAME.format(kind=kind)
            assert path.read_text(encoding="utf-8") == schema_text(kind)

    def test_it_needs_a_directory(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Several files cannot go to stdout, and silently writing one would be worse."""
        assert main(["schema", "all"]) == EXIT_USAGE
        assert "needs a directory" in capsys.readouterr().err

    def test_a_written_schema_is_what_the_printed_one_is(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`-o` and stdout must not drift; the committed schemas depend on it."""
        assert main(["schema", "component"]) == EXIT_OK
        printed = capsys.readouterr().out
        target = tmp_path / "one.json"
        assert main(["schema", "component", "-o", str(target)]) == EXIT_OK
        assert target.read_text(encoding="utf-8") == printed
