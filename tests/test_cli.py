"""End to end tests of the command line interface."""

from __future__ import annotations

import codecs
import json
import re
from pathlib import Path
from typing import Any

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
from ddd.ir import DICTIONARY_FORMAT
from ddd.models.common import OBJECT_ID_PATTERN


class TestCheck:
    def test_consistent_project(self, capsys: pytest.CaptureFixture[str]) -> None:
        # The demo has not adopted ids, so 'missing-id' is silenced here; it is an adoption
        # nudge, not a consistency problem, and is not what this test is about.
        assert main(["check", str(DEMO), "-W", "missing-id=ignore"]) == EXIT_OK
        assert "are consistent" in capsys.readouterr().err

    def test_inconsistent_project(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(INCONSISTENT)]) == EXIT_FINDINGS
        captured = capsys.readouterr().err
        assert "multiple-producers" in captured
        assert "definition-mismatch" in captured
        assert "4 errors, 1 warning" in captured

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        # The known 4 errors and 1 warning of this fixture are the point; the example has not
        # adopted ids, and that adoption nudge is not one of them.
        arguments = ["check", str(INCONSISTENT), "--format", "json", "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_FINDINGS
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
        assert (
            main(["generate", "all", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)]) == EXIT_OK
        )
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
        main(["generate", "all", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)])
        capsys.readouterr()
        main(["generate", "all", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)])
        assert "unchanged" in capsys.readouterr().err

    def test_the_a2l_artefact_writes_the_a2l_and_nothing_else(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The second run of a build regenerates the a2l once the linker has decided the
        addresses; `generate a2l` says so, needing no templates and reporting no c."""
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        output = tmp_path / "gen"
        arguments = ["generate", "a2l", str(DEMO), "-o", str(output)]
        assert main([*arguments, "--address-map", str(addresses)]) == EXIT_OK
        assert [path.name for path in output.iterdir()] == ["DemoDevice.a2l"]
        assert "ECU_ADDRESS 0x20001000" in (output / "DemoDevice.a2l").read_text(encoding="utf-8")
        assert "unchanged" not in capsys.readouterr().err

    @pytest.mark.parametrize("artefact", ["c", "all"])
    def test_whatever_renders_c_requires_the_template_directory(
        self, artefact: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Structurally, by the parser of the artefact: there is no fallback to relax."""
        with pytest.raises(SystemExit) as exit_code:
            main(["generate", artefact, str(DEMO), "-o", str(tmp_path / "gen")])
        assert exit_code.value.code == EXIT_USAGE
        assert "-t/--template-dir" in capsys.readouterr().err

    def test_the_a2l_artefact_refuses_the_options_of_the_c_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Each artefact carries only its own options, so handing the a2l run a template
        directory is a contradiction the parser itself reports, not an ignored no-op."""
        arguments = ["generate", "a2l", str(DEMO), "-o", str(tmp_path / "gen")]
        with pytest.raises(SystemExit) as exit_code:
            main([*arguments, "-t", str(TEMPLATES)])
        assert exit_code.value.code == EXIT_USAGE
        assert "unrecognized arguments" in capsys.readouterr().err

    def test_the_artefact_is_not_optional(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bare `ddd generate PROJECT` predates the artefacts; the error names them.

        Asserted as three names in the message rather than as one spelling of the list,
        because the spelling is argparse's and it moves: 3.13 writes ``choose from 'c',
        'a2l', 'all'`` and 3.12.14 writes ``choose from c, a2l, all``. Both name the three
        artefacts, which is the whole of what this command promises the reader.
        """
        with pytest.raises(SystemExit) as exit_code:
            main(["generate", str(DEMO), "-o", str(tmp_path / "gen"), "-t", str(TEMPLATES)])
        assert exit_code.value.code == EXIT_USAGE
        reported = capsys.readouterr().err
        assert "invalid choice" in reported
        offered = reported.split("choose from", 1)[1]
        assert all(artefact in offered for artefact in ("c", "a2l", "all"))

    def test_refuses_an_inconsistent_project(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert (
            main(["generate", "all", str(INCONSISTENT), "-o", str(output), "-t", str(TEMPLATES)])
            == EXIT_FINDINGS
        )
        assert not output.exists()

    def test_force_generates_anyway(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert (
            main(
                [
                    "generate",
                    "all",
                    str(INCONSISTENT),
                    "-o",
                    str(output),
                    "-t",
                    str(TEMPLATES),
                    "--force",
                ]
            )
            == EXIT_FINDINGS
        )
        assert (output / "ddd_globals.c").is_file()

    def test_dry_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        output = tmp_path / "gen"
        assert (
            main(
                ["generate", "all", str(DEMO), "-o", str(output), "-t", str(TEMPLATES), "--dry-run"]
            )
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
        main(["generate", "c", str(DEMO), "-o", str(output), "-t", str(templates)])
        assert (output / "device_globals.c").is_file()
        assert not (output / "ddd_globals.c").exists()
        assert not list(output.glob("*.a2l"))

    def test_a_template_directory_with_nothing_to_render(self, tmp_path: Path) -> None:
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "_helper.jinja2").write_text("{% macro x() %}{% endmacro %}", encoding="utf-8")
        arguments = [
            "generate",
            "all",
            str(DEMO),
            "-o",
            str(tmp_path / "gen"),
            "-t",
            str(templates),
        ]
        assert main(arguments) == EXIT_USAGE

    def broken_template(self, tmp_path: Path, content: str) -> list[str]:
        """A template directory holding one broken template, and the arguments to render it."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "ddd_globals.c.jinja2").write_text(content, encoding="utf-8")
        output = str(tmp_path / "gen")
        return ["generate", "c", str(DEMO), "-o", output, "-t", str(templates)]

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

    def test_a_component_template_error_names_the_component(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``{component}`` template renders once per component, over data that differs per
        render, so the one line says which component's render failed."""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "{component}.h.jinja2").write_text(
            "/* fine */\n/* {{ header.nonsense }} */\n", encoding="utf-8"
        )
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "beta.ddd.json"),
                "beta.ddd.json": component("Beta", declare("local", "X")),
            },
        )
        arguments = [
            "generate",
            "c",
            str(tmp_path / "project.ddd.json"),
            "-o",
            str(tmp_path / "gen"),
            "-t",
            str(templates),
        ]
        assert main(arguments) == EXIT_USAGE
        err = capsys.readouterr().err
        expected = "cannot render template '{component}.h.jinja2' for component 'Beta', line 2"
        assert f"ddd: {expected}" in err
        assert "Traceback" not in err

    def test_a_dropped_declaration_is_absent_from_every_artefact(self, tmp_path: Path) -> None:
        """unknown-constant relaxed to a warning: per the spec a warnings-only run is clean,
        the artefacts are written, and the dropped axis - with the curve over it, dropped
        along quietly - is simply absent from the headers and the a2l."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "GoneAxis", kind="axis", size="NOPE", datatype="uint16"),
                    declare("local", "GoneCurve", kind="curve", axis="GoneAxis", datatype="uint16"),
                    declare("local", "KeptValue"),
                ),
            },
        )
        output = tmp_path / "gen"
        arguments = [
            "generate",
            "all",
            str(tmp_path / "project.ddd.json"),
            "-o",
            str(output),
            "-t",
            str(TEMPLATES),
            "-W",
            "unknown-constant=warning",
        ]
        assert main(arguments) == EXIT_OK
        generated = {path.name: path.read_text(encoding="utf-8") for path in output.iterdir()}
        assert "KeptValue" in generated["A.h"]
        assert "KeptValue" in generated["ddd_globals.c"]
        for content in generated.values():
            assert "GoneAxis" not in content
            assert "GoneCurve" not in content

    def test_force_generates_through_every_kind_of_dropped_declaration(
        self, tmp_path: Path
    ) -> None:
        """Every way a declaration can be dropped, stacked into one project: an unknown
        member type, a type cycle, a poisoned member dimension, an unknown declaration
        dimension, a curve over the dropped axis, and an init on a structure. ``--force``
        still writes the artefacts, without the dropped objects and without a traceback."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Bad_t",
                            "members": [
                                {
                                    "name": "a",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                    "dimensions": ["NOPE"],
                                }
                            ],
                        },
                        {
                            "type": "struct",
                            "name": "Cyc_t",
                            "members": [{"name": "b", "member": "value", "typename": "Cyc2_t"}],
                        },
                        {
                            "type": "struct",
                            "name": "Cyc2_t",
                            "members": [{"name": "c", "member": "value", "typename": "Cyc_t"}],
                        },
                        {
                            "type": "struct",
                            "name": "Ghostly_t",
                            "members": [{"name": "d", "member": "value", "typename": "Ghost_t"}],
                        },
                        {
                            "type": "struct",
                            "name": "Fine_t",
                            "members": [
                                {
                                    "name": "e",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                }
                            ],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A",
                    declare("local", "GonePoisoned", typename="Bad_t"),
                    declare("local", "GoneCyclic", typename="Cyc_t"),
                    declare("local", "GoneGhostly", typename="Ghostly_t"),
                    declare("local", "GoneAxis", kind="axis", size="NOPE2", datatype="uint16"),
                    declare("local", "GoneCurve", kind="curve", axis="GoneAxis", datatype="uint16"),
                    declare("local", "GoneDims", dimensions=["NOPE3"]),
                    declare("local", "GoneInit", typename="Fine_t", init=1),
                    declare("local", "KeptValue"),
                ),
            },
        )
        output = tmp_path / "gen"
        arguments = [
            "generate",
            "all",
            str(tmp_path / "project.ddd.json"),
            "-o",
            str(output),
            "-t",
            str(TEMPLATES),
            "--force",
        ]
        assert main(arguments) == EXIT_FINDINGS
        generated = {path.name: path.read_text(encoding="utf-8") for path in output.iterdir()}
        assert "KeptValue" in generated["A.h"]
        for content in generated.values():
            assert "Gone" not in content

    def test_address_map(self, tmp_path: Path) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        output = tmp_path / "gen"
        main(
            [
                "generate",
                "all",
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

    def test_a_symbol_the_address_map_leaves_out_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Address zero is what a missing entry silently became, on every object at once.

        The map is written by a linker script or a patch tool against the names of one build,
        so a renamed variable or a stale file covers some of the objects and not the rest -
        and the a2l that comes out points a calibration tool at 0x00000000 without anything
        in the run saying so.
        """
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        code = main(
            [
                "generate",
                "a2l",
                str(DEMO),
                "-o",
                str(tmp_path / "gen"),
                "--address-map",
                str(addresses),
            ]
        )
        captured = capsys.readouterr().err
        assert code == EXIT_OK
        assert "address-missing" in captured
        assert "ValueE" not in captured.split("address-missing", 1)[1].splitlines()[0]

    def a2l_symbols(self, written: str) -> list[str]:
        """Every record of an emitted a2l, read back out of the file it was written to.

        Read rather than asked for, so that what the check compares against is the file a
        calibration tool would open and not a second opinion from the same function.
        """
        wanted = [["/begin", kind] for kind in ("MEASUREMENT", "CHARACTERISTIC", "AXIS_PTS")]
        return [line.split()[2] for line in written.splitlines() if line.split()[:2] in wanted]

    def test_a_complete_address_map_is_not_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        addresses = tmp_path / "addresses.json"
        output = tmp_path / "gen"
        assert main(["generate", "a2l", str(DEMO), "-o", str(output)]) == EXIT_OK
        symbols = self.a2l_symbols((output / "DemoDevice.a2l").read_text(encoding="utf-8"))
        assert symbols, "the demo project has records to address"
        addresses.write_text(json.dumps(dict.fromkeys(symbols, "0x20001000")), encoding="utf-8")
        capsys.readouterr()
        code = main(
            [
                "generate",
                "a2l",
                str(DEMO),
                "-o",
                str(tmp_path / "gen2"),
                "--address-map",
                str(addresses),
                "--strict",
            ]
        )
        assert code == EXIT_OK
        assert "address-missing" not in capsys.readouterr().err

    def test_a_map_entry_matching_nothing_is_named_beside_the_missing_ones(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Usually the other half of one mistake: the old spelling of the renamed symbol."""
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueEE": "0x20001000"}', encoding="utf-8")
        main(
            [
                "generate",
                "a2l",
                str(DEMO),
                "-o",
                str(tmp_path / "gen"),
                "--address-map",
                str(addresses),
            ]
        )
        captured = capsys.readouterr().err
        assert "the map also carries 'ValueEE', which the a2l does not" in captured

    def test_a_project_that_cannot_be_read_generates_nothing(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"broken.ddd.json": "{ not json"})
        code = main(
            [
                "generate",
                "a2l",
                str(tmp_path / "broken.ddd.json"),
                "-o",
                str(tmp_path / "gen"),
            ]
        )
        assert code == EXIT_FINDINGS
        assert not (tmp_path / "gen").exists()

    def test_a_missing_address_fails_a_strict_run(self, tmp_path: Path) -> None:
        """What a post-link build wants: the map covers the file, or the build stops."""
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x20001000"}', encoding="utf-8")
        code = main(
            [
                "generate",
                "a2l",
                str(DEMO),
                "-o",
                str(tmp_path / "gen"),
                "--address-map",
                str(addresses),
                "--strict",
            ]
        )
        assert code == EXIT_FINDINGS

    def test_no_address_map_reports_nothing(self, tmp_path: Path) -> None:
        """Without a map every address is zero on purpose: this is the pre-link run."""
        code = main(["generate", "a2l", str(DEMO), "-o", str(tmp_path / "gen"), "--strict"])
        assert code == EXIT_OK

    def test_broken_address_map(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "nowhere"}', encoding="utf-8")
        code = main(
            [
                "generate",
                "all",
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
        main(
            [
                "generate",
                "all",
                str(DEMO),
                "-o",
                str(output),
                "-t",
                str(TEMPLATES),
                "--format",
                "json",
            ]
        )
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
      "id": null,
      "extensions": {},
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
      "dimensions": [],
      "init": 15,
      "section": null,
      "raster": null,
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
      "id": null,
      "extensions": {},
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
      "dimensions": [],
      "init": 800,
      "section": null,
      "raster": null,
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
        assert "EventLogger, UserInterface" in out

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

    def test_the_reading_carries_no_float_artifacts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """3 raw counts of 0.1 compute as 0.30000000000000004 in binary floats; the reading
        rounds the artifact away and says what the author meant."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Offset", unit="V", conversion={"factor": 0.1}, init=3),
                ),
            },
        )
        assert main(["list", str(tmp_path / "project.ddd.json")]) == EXIT_OK
        assert "3 (= 0.3 V)" in capsys.readouterr().out

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
        # Neither declaration carries an id; the payload this pins predates the check, and
        # the adoption nudge is not part of the shape being pinned here.
        arguments = [
            "list",
            str(tmp_path / "p.ddd.json"),
            "--format",
            "json",
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_OK
        assert capsys.readouterr().out == PINNED_LIST_PAYLOAD

    def test_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        # The demo has not adopted ids; that adoption nudge is not what this test is about.
        assert main(["list", str(DEMO), "--format", "json", "-W", "missing-id=ignore"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["project"] == "DemoDevice"
        entry = next(v for v in payload["variables"] if v["name"] == "ValueE")
        assert entry["owner"] == "Controller"
        assert entry["consumers"] == ["EventLogger", "UserInterface"]
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
            "all",
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
            "all",
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
        assert (
            run(["generate", "all", str(DEMO), "-o", str(tmp_path / "gen"), "-t", directory])
            == EXIT_OK
        )
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


def test_the_dictionary_carries_the_identity_and_states_the_format(tree, capsys):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
        },
    )
    assert main(["dump", str(tree / "project.ddd.json")]) == EXIT_OK
    dumped = json.loads(capsys.readouterr().out)
    assert dumped["format"] == DICTIONARY_FORMAT
    assert dumped["objects"][0]["id"] == "k7m2q9xr4t8w"


def test_the_dump_states_a_null_id_for_an_object_that_carries_none(tree, capsys):
    """``id`` serializes like every other optional field of the model.

    Unstated, it writes ``null`` exactly as ``section``, ``raster`` and ``condition`` do -
    there is no consumer of a dumped dictionary to protect from the key's arrival.
    """
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        },
    )
    assert main(["dump", str(tree / "project.ddd.json")]) == EXIT_OK
    dumped = json.loads(capsys.readouterr().out)
    assert dumped["objects"][0]["id"] is None


def test_assigning_ids_writes_one_per_producing_declaration(tree, capsys):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X"), declare("output", "Y"), declare("input", "Z")
            ),
        },
    )
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    assert "wrote 2 ids" in capsys.readouterr().err
    written = json.loads((tree / "a.ddd.json").read_text(encoding="utf-8"))
    interface = written["component"]["interface"]
    # Against the published pattern rather than a hand-written one: `[a-z0-9]{12}` would
    # accept `i`, `l`, `o` and `u`, which the alphabet excludes precisely so that an id read
    # off a screen can be typed back. The alphabet itself is pinned in tests/test_models.py.
    assert re.fullmatch(OBJECT_ID_PATTERN, interface[0]["definition"]["id"])
    assert re.fullmatch(OBJECT_ID_PATTERN, interface[1]["definition"]["id"])
    assert "id" not in interface[2]["definition"], "a consumer owns no identity"


def test_assigning_ids_twice_changes_nothing(tree):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        },
    )
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    once = (tree / "a.ddd.json").read_text(encoding="utf-8")
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == once


def test_assigning_ids_leaves_the_rest_of_the_file_alone(tree):
    """One inserted line per declaration, and nothing else touched."""
    original = (
        '{\n  "component": {\n    "name": "A",\n    "interface": [\n      {\n'
        '        "scope": "local",\n        "definition": {\n'
        '          "name": "X",\n          "datatype": "uint8",\n'
        '          "conversion": {"kind": "identity"},\n          "kind": "measurement",\n'
        '          "volatile": false\n        }\n      }\n    ]\n  }\n}\n'
    )
    write_tree(tree, {"a.ddd.json": original})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    after = (tree / "a.ddd.json").read_text(encoding="utf-8")
    added = [line for line in after.splitlines() if line not in original.splitlines()]
    assert len(added) == 1
    assert added[0].startswith('          "id": "')


def test_assigning_ids_skips_a_file_it_cannot_parse(tree, capsys):
    write_tree(tree, {"a.ddd.json": "{ not json"})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_FINDINGS
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == "{ not json"
    captured = capsys.readouterr().err
    assert "not readable as json, skipped" in captured
    assert "wrote 0 ids" in captured


def test_assigning_ids_keeps_a_byte_order_mark(tree):
    """``ranges.read`` reads with utf-8-sig, so the mark is invisible by the time we edit.

    Written back as plain utf-8 it would be silently dropped - a change to a file this
    command promises to leave alone but for one line, and one that several Windows editors
    and PowerShell redirection put there in the first place.
    """
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    path.write_bytes(codecs.BOM_UTF8 + path.read_bytes())
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert path.read_bytes().startswith(codecs.BOM_UTF8)


def test_assigning_ids_keeps_the_line_endings(tree):
    """``read`` decodes with universal newlines, so a crlf file arrives here as lf.

    Written back with the default translation it would come out lf on Linux and crlf on
    Windows, whatever it went in as - a diff on every line of the file, which is exactly what
    makes editing a hand-authored source unreviewable.
    """
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert b"\r\n" in path.read_bytes()
    assert path.read_bytes().replace(b"\r\n", b"").count(b"\n") == 0


def test_assigning_ids_keeps_a_file_free_of_crlf(tree):
    """The other side of ``test_assigning_ids_keeps_the_line_endings``.

    ``write_tree`` writes through a text-mode file handle with no explicit ``newline``, so on
    Windows the fixture itself already carries ``\\r\\n`` before this test ever runs -
    translated back to plain ``\\n`` here first, so the assertion below is actually about
    ``assign``'s own choice and not an accident of how the fixture wrote the file. A project
    that has only ever seen ``\\n`` must not gain a ``\\r`` from being stamped.
    """
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert b"\r\n" not in path.read_bytes()


def test_assigning_ids_ignores_a_file_that_is_not_a_json_object(tree):
    """A component file is the only kind that declares data objects.

    ``ddd id --assign`` is pointed at whatever files a shell glob expands to, so a stray
    json file that is not even an object - an array, here - has to be left alone rather
    than crash the run.
    """
    write_tree(tree, {"a.ddd.json": "[]"})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == "[]"


def test_assigning_ids_ignores_a_project_file(tree):
    """A project file is valid json and an object, but declares no interface at all.

    Pointing the command at a whole project's file list has to be as safe as pointing it at
    one component, so the project file in the middle of that list is skipped rather than
    reported as a problem.
    """
    write_tree(tree, {"project.ddd.json": project("P", "a.ddd.json")})
    assert main(["id", "--assign", str(tree / "project.ddd.json")]) == EXIT_OK


def test_assigning_ids_ignores_a_component_with_no_interface(tree):
    """A component may declare no interface at all; there is then nothing to stamp."""
    write_tree(tree, {"a.ddd.json": {"component": {"name": "A"}}})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK


def test_assigning_ids_skips_a_declaration_whose_key_the_scanner_cannot_relocate(tree, capsys):
    r"""A defensive branch a hand authored file can still reach, if never on purpose.

    The scanner in ``ranges.py`` records a value's span under the *raw* text of the key in
    front of it, unescaped, while ``json.loads`` decodes it - documented on
    :meth:`~ddd.lsp.ranges._Scanner._string`. The two agree for every key anybody actually
    types, but a ``"name"`` spelled with a json unicode escape - legal json, if not
    something a person writes by hand - decodes to the plain string while scanning to the
    escaped one. ``value_span_of`` then finds nothing for the pointer this module builds
    off the decoded document, and the declaration is left unstamped rather than the run
    crashing on a ``None`` span.

    Also the regression check for ``assign`` once counting ``len(pointers)`` - declarations
    *found* - rather than insertions actually made: this file has exactly one pointer and
    zero of them resolve, so a miscount would print ``wrote 1 id`` for a file the assertion
    above has just shown was never touched.
    """
    original = (
        '{\n  "component": {\n    "name": "A",\n    "interface": [\n      {\n'
        '        "scope": "local",\n        "definition": {\n'
        '          "\\u006eame": "X",\n          "datatype": "uint8",\n'
        '          "conversion": {"kind": "identity"},\n          "kind": "measurement",\n'
        '          "volatile": false\n        }\n      }\n    ]\n  }\n}\n'
    )
    write_tree(tree, {"a.ddd.json": original})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == original
    assert "wrote 0 ids" in capsys.readouterr().err


class TestBaselineUnderStrict:
    def test_a_warning_in_the_baseline_does_not_abort_a_strict_comparison(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A past delivery's warnings are nobody's problem now, however strict this run is:
        the comparison still runs and the renames are still written."""

        def delivery(alignment: int) -> dict[str, Any]:
            return {
                "p.ddd.json": project("P", "s.ddd.json", "a.ddd.json"),
                "s.ddd.json": {
                    "sections": [
                        {"section": ".slow", "access": "read-write", "alignment": alignment}
                    ]
                },
                "a.ddd.json": component("A", declare("local", "X", "uint32", section=".slow")),
            }

        write_tree(tmp_path / "old", delivery(1))
        write_tree(tmp_path / "new", delivery(4))
        renames = tmp_path / "renames.json"
        arguments = [
            "compare",
            "--strict",
            str(tmp_path / "old" / "p.ddd.json"),
            str(tmp_path / "new" / "p.ddd.json"),
            "--renames",
            str(renames),
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_OK
        assert "can replace" in capsys.readouterr().err
        assert renames.read_text(encoding="utf-8") == "[]\n"


class TestCmakeModule:
    def test_the_a2l_options_are_not_passed_to_a_c_only_generation(self) -> None:
        """``ddd generate c`` has neither option; a rule carrying them fails on every build."""
        from ddd.cli import cmake_module_directory

        directory = cmake_module_directory()
        assert directory is not None
        text = (directory / "Ddd.cmake").read_text(encoding="utf-8")
        for option in ("--byte-order", "--address-map"):
            appended = text.index(f"list(APPEND generate_options {option}")
            guard = text[:appended].rsplit("if(", 1)[1]
            assert "NOT arg_NO_A2L" in guard, f"{option} is appended without a NO_A2L guard"


def test_assigning_ids_fills_an_explicit_null(tree, capsys):
    """``"id": null`` is what the dump writes for an unstamped object; a description carrying
    it is as unstamped as one without the key, and the check says so."""
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("output", "X", id=None))})
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert "wrote 1 id" in capsys.readouterr().err
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert re.fullmatch(OBJECT_ID_PATTERN, stamped["component"]["interface"][0]["definition"]["id"])


def test_assigning_ids_keeps_mixed_line_endings(tree):
    """A file with one stray CRLF line keeps exactly that one; the rest stays LF."""
    text = json.dumps(component("A", declare("output", "X")), indent=2)
    first, rest = text.split("\n", 1)
    path = tree / "a.ddd.json"
    path.write_bytes((first + "\r\n" + rest + "\n").encode("utf-8"))
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    after = path.read_bytes()
    assert after.count(b"\r\n") == 1
    assert after.count(b"\n") == text.count("\n") + 2  # the final newline and one line added


def test_the_renames_file_is_written_with_the_line_endings_ddd_always_writes(tree, monkeypatch):
    """Every file DDD writes passes ``newline=""``: the same bytes on Windows as anywhere."""
    written: dict[str, object] = {}
    original = Path.write_text

    def spy(self: Path, data: str, *args: Any, **kwargs: Any) -> int:
        written[self.name] = kwargs.get("newline", "unset")
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy)
    for name in ("old", "new"):
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project("P", f"{name}-a.ddd.json"),
                f"{name}-a.ddd.json": component("A", declare("local", "X")),
            },
        )
    renames = tree / "renames.json"
    arguments = ["compare", str(tree / "old.ddd.json"), str(tree / "new.ddd.json"), "--renames"]
    assert main([*arguments, str(renames), "-W", "missing-id=ignore"]) == EXIT_OK
    assert written["renames.json"] == ""


def test_assigning_ids_to_a_missing_file_says_so(tree, capsys):
    assert main(["id", "--assign", str(tree / "missing.ddd.json")]) == EXIT_FINDINGS
    assert "not readable as json, skipped" in capsys.readouterr().err


def test_assigning_ids_skips_a_definition_without_a_name(tree, capsys):
    """Nothing to hang an id on; the loader is what has something to say about the file."""
    path = tree / "a.ddd.json"
    write_tree(
        tree,
        {
            "a.ddd.json": {
                "component": {"name": "A", "interface": [{"scope": "output", "definition": {}}]}
            }
        },
    )
    before = path.read_bytes()
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert "wrote 0 ids" in capsys.readouterr().err
    assert path.read_bytes() == before
