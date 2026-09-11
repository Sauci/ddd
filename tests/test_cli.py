"""End to end tests of the command line interface."""

from __future__ import annotations

import codecs
import json
import os
import re
from pathlib import Path
from typing import Any, ClassVar

import pytest

from conftest import (
    DEMO,
    EXAMPLES,
    INCONSISTENT,
    TEMPLATES,
    component,
    declare,
    project,
    write_tree,
)
from ddd.build_info import BUILD_INFO_FORMAT
from ddd.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, _displayed_path, main
from ddd.ir import DICTIONARY_FORMAT
from ddd.models.common import OBJECT_ID_PATTERN


class TestStandalone:
    """A component checked on its own is judged by what one file can decide.

    Ten checks need every component of a project; the language server holds them back for a
    file no build claims, and a build's per-component target has to do the same instead of
    hand-listing two of them.
    """

    PUMP = EXAMPLES / "vocabulary" / "pump.ddd.json"

    def test_a_component_naming_shared_vocabulary_checks_clean_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["check", str(self.PUMP)]) == EXIT_FINDINGS
        assert "unknown-section" in capsys.readouterr().err
        assert main(["check", str(self.PUMP), "--standalone"]) == EXIT_OK
        assert "are consistent" in capsys.readouterr().err

    def test_it_holds_back_exactly_the_checks_that_need_the_project(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """What the flag silences is what the registry says, not a list kept beside it."""
        from ddd.diagnostics import CHECKS

        held_back = {name for name, info in CHECKS.items() if info.needs_every_component}
        main(["check", str(self.PUMP), "--format", "json"])
        reported = {entry["check"] for entry in json.loads(capsys.readouterr().out)["diagnostics"]}
        assert reported & held_back, "the fixture no longer trips a project-wide check"
        main(["check", str(self.PUMP), "--standalone", "--format", "json"])
        remaining = {entry["check"] for entry in json.loads(capsys.readouterr().out)["diagnostics"]}
        assert not remaining & held_back
        assert remaining == reported - held_back

    def test_an_explicit_override_still_wins(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--standalone`` sets the floor; ``-W`` on the same run says what the caller wants."""
        code = main(["check", str(self.PUMP), "--standalone", "-W", "unknown-section=warning"])
        captured = capsys.readouterr().err
        assert code == EXIT_OK
        assert "warning[unknown-section]" in captured


LAYOUT = EXAMPLES / "layout" / "project.ddd.json"
PLUGIN_FILE = (EXAMPLES / "plugins" / "ddd_layout.py").resolve()


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


class TestGenerateAll:
    """``all`` means everything the project produces, the plugins' artefacts included."""

    def run(
        self,
        artefact: str,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        *extra: str,
    ) -> list[str]:
        renders_c = artefact != "a2l" and "c" not in extra
        templates = ["-t", str(TEMPLATES)] if renders_c else []
        arguments = ["generate", artefact, str(LAYOUT), "-o", str(tmp_path), *templates, *extra]
        assert main([*arguments, "-W", "missing-id=ignore", "--format", "json"]) == EXIT_OK
        return [
            Path(entry["path"]).name for entry in json.loads(capsys.readouterr().out)["generated"]
        ]

    def test_all_produces_the_plugins_artefact_after_the_built_in_ones(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        written = self.run("all", tmp_path, capsys)
        assert written[-1] == "ddd_layout.h"
        assert "ddd_globals.c" in written and "LayoutDevice.a2l" in written
        assert (tmp_path / "ddd_layout.h").is_file()

    @pytest.mark.parametrize("artefact", ["c", "a2l"])
    def test_a_single_built_in_artefact_runs_no_plugin(
        self, tmp_path: Path, artefact: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        written = self.run(artefact, tmp_path, capsys)
        assert "ddd_layout.h" not in written
        assert not (tmp_path / "ddd_layout.h").exists()

    def test_without_the_a2l_keeps_the_plugins_artefact(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """What a build asks for when the a2l is written later, once the addresses are known.

        Selecting the c artefact instead is the trap this option exists to avoid: it drops the
        plugins' artefacts along with the a2l, and says nothing about having done so.
        """
        written = self.run("all", tmp_path, capsys, "--without", "a2l")
        assert "ddd_layout.h" in written and "ddd_globals.c" in written
        assert "LayoutDevice.a2l" not in written
        assert (tmp_path / "ddd_layout.h").is_file()
        assert not (tmp_path / "LayoutDevice.a2l").exists()

    def test_without_the_c_keeps_the_a2l_and_the_plugins_artefact(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        written = self.run("all", tmp_path, capsys, "--without", "c")
        assert "LayoutDevice.a2l" in written and "ddd_layout.h" in written
        assert "ddd_globals.c" not in written

    @pytest.mark.parametrize(
        ("option", "value", "artefact"),
        [
            ("--address-map", "map.json", "a2l"),
            ("--byte-order", "big", "a2l"),
        ],
    )
    def test_an_option_of_a_subtracted_artefact_is_refused(
        self,
        tmp_path: Path,
        option: str,
        value: str,
        artefact: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Subtracting an artefact takes its options with it, rather than ignoring them.

        The address map is the one that matters: loading it is what a two-run build wants to
        avoid before the link, and a run that accepted and ignored it would also drop the
        address coverage check without saying so.
        """
        arguments = ["generate", "all", str(LAYOUT), "-o", str(tmp_path), "-t", str(TEMPLATES)]
        arguments += ["--without", artefact, option, value, "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_USAGE
        assert option in capsys.readouterr().err

    def test_a_run_left_with_nothing_to_write_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Subtracting both built-in artefacts from a project that provides no plugin artefact.

        Reporting success while writing nothing is what this whole option is about, so the one
        combination that would still do it is a usage error.
        """
        arguments = ["generate", "all", str(DEMO), "-o", str(tmp_path)]
        arguments += ["--without", "c", "--without", "a2l"]
        assert main(arguments) == EXIT_USAGE
        assert "would write nothing" in capsys.readouterr().err


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
        # An unchanged file is left alone, not rewritten in place, so a rerun that changes
        # nothing leaves its mtime exactly as the first run left it. Stamped to a sentinel
        # well in the past, rather than read straight after the first run, because two runs
        # close enough together can land on the same clock tick and match by coincidence even
        # when the second one did rewrite the file - a rewrite would replace the sentinel
        # with a fresh time, which is what makes this a real check rather than a flaky one.
        generated = output / "ddd_globals.c"
        stamp = generated.stat().st_mtime_ns - 10**10
        os.utime(generated, ns=(stamp, stamp))
        main(["generate", "all", str(DEMO), "-o", str(output), "-t", str(TEMPLATES)])
        assert "unchanged" in capsys.readouterr().err
        assert generated.stat().st_mtime_ns == stamp

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
        """There is no fallback to relax, only a difference in where the refusal comes from.

        ``c`` cannot be anything but a c run, so its parser demands the directory. ``all`` can
        subtract the c, so it is asked for once the subtraction has been applied - which is why
        the one refuses before parsing finishes and the other after.
        """
        arguments = ["generate", artefact, str(DEMO), "-o", str(tmp_path / "gen")]
        if artefact == "all":
            assert main(arguments) == EXIT_USAGE
        else:
            with pytest.raises(SystemExit) as exit_code:
                main(arguments)
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

    def test_refuses_an_array_too_large_to_carry(self, tmp_path: Path) -> None:
        """A billion elements with a scalar ``init`` used to be a run that never came back.

        ``initializer_of`` broadcasts the scalar over the shape and renders one literal per
        element, so this project produced no file and no message for as long as anybody
        cared to wait. The analysis refuses the array now, and `schema` is an error, so the
        run stops before any backend is asked for anything - and ``--force``, which
        generates over findings, writes the header without the declaration, because a
        refused declaration is not in the dictionary at all.
        """
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "HugeArray", dimensions=[1000000000], init=0)
                ),
            },
        )
        root = str(tmp_path / "project.ddd.json")
        output = tmp_path / "gen"
        arguments = ["generate", "c", root, "-o", str(output), "-t", str(TEMPLATES)]
        assert main(arguments) == EXIT_FINDINGS
        assert not output.exists()
        assert main([*arguments, "--force"]) == EXIT_FINDINGS
        assert "HugeArray" not in (output / "ddd_globals.c").read_text(encoding="utf-8")

    def test_refuses_a_map_too_large_to_carry(self, tmp_path: Path) -> None:
        """Each axis is within the element cap on its own; their product, a map's whole
        shape, is not - and a scalar ``init`` would have broadcast that product the same
        way one over a plain array's dimensions does, so the run has to stop before
        ``generate c`` is asked to write anything.
        """
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=5000),
                    declare("local", "Ay", "uint16", kind="axis", size=5000),
                    declare("local", "M", "uint16", kind="map", x_axis="Ax", y_axis="Ay", init=0),
                ),
            },
        )
        root = str(tmp_path / "project.ddd.json")
        output = tmp_path / "gen"
        arguments = ["generate", "c", root, "-o", str(output), "-t", str(TEMPLATES)]
        assert main(arguments) == EXIT_FINDINGS
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

    def test_a_template_raising_a_bare_exception_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Not every mistake a template's own body makes is one jinja wraps as a
        ``TemplateError`` - dividing by zero raises a bare ``ZeroDivisionError`` - and it is no
        less the template author's mistake for that: reported the same one line, not as a
        python traceback through jinja, a library the author never imported."""
        arguments = self.broken_template(tmp_path, "/* fine */\n/* {{ 1 / 0 }} */\n")
        assert main(arguments) == EXIT_USAGE
        err = capsys.readouterr().err
        expected = "ddd: cannot render template 'ddd_globals.c.jinja2', line 2: division by zero"
        assert expected in err
        assert "Traceback" not in err

    def test_a_template_raising_a_bare_exception_from_a_filter_names_the_template_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        arguments = self.broken_template(
            tmp_path, "/* fine */\n/* {{ model.groups | length + 'x' }} */\n"
        )
        assert main(arguments) == EXIT_USAGE
        err = capsys.readouterr().err
        assert "ddd: cannot render template 'ddd_globals.c.jinja2', line 2:" in err
        assert "unsupported operand type(s) for +: 'int' and 'str'" in err
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

    def test_an_empty_address_map_is_a_first_run_and_not_a_hole(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The two-run flow seeds ``{}`` before anything has linked, and STRICT rides along.

        A map that names some objects and not others has a hole in it; a map that names
        nothing is the run a build makes before it has addresses, and a strict first build
        that failed on it could never reach the second run that fills the map.
        """
        addresses = tmp_path / "addresses.json"
        addresses.write_text("{}", encoding="utf-8")
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
        captured = capsys.readouterr().err
        assert code == EXIT_OK, captured
        assert "address-missing" not in captured
        assert (tmp_path / "gen" / "DemoDevice.a2l").is_file()

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

    def test_json_spells_a_path_the_way_the_output_directory_was_typed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The json payload is what a build reads, so the spelling is part of the contract: a
        relative ``-o`` stays relative here, exactly as it does in the text report, rather than
        turning into whatever absolute path the run happened to resolve it to."""
        monkeypatch.chdir(tmp_path)
        arguments = ["generate", "c", str(DEMO), "-o", "build/gen", "-t", str(TEMPLATES)]
        assert main([*arguments, "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        paths = [entry["path"] for entry in payload["generated"]]
        assert "build/gen/ddd_globals.c" in paths


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

    def test_a_string_init_is_quoted_and_has_no_reading(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "Label",
                        "uint8",
                        kind="value_block",
                        conversion={"kind": "string"},
                        dimensions=[8],
                        init="V1.2",
                    ),
                ),
            },
        )
        assert main(["list", str(tmp_path / "project.ddd.json")]) == EXIT_OK
        out = capsys.readouterr().out
        assert '"V1.2"' in out
        assert "(=" not in out

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
        entry = next(v for v in payload["variables"] if v.get("name") == "ValueE")
        assert entry["owner"] == "Controller"
        assert entry["consumers"] == ["EventLogger", "UserInterface"]
        assert entry["conversion"] == {"kind": "linear", "factor": 0.25, "offset": 0.0}
        # A structured variable is listed by its leaves. They carry the path and the instance
        # they belong to rather than a name of their own, and an external member contributes
        # none at all: DDD does not know what is inside it.
        leaf = next(v for v in payload["variables"] if v.get("path") == "Diagnosis.faults")
        assert leaf["instance"] == "Diagnosis" and leaf["owner"] == "SensorHub"
        assert "name" not in leaf
        assert not [
            v for v in payload["variables"] if v.get("path", "").startswith("Diagnosis.driver")
        ]
        # The json contract of every reporting command: diagnostics and their summary.
        assert payload["diagnostics"] == []
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}


class TestArtefacts:
    """What ``ddd generate`` will accept for a project, which only the project can say."""

    def test_a_project_naming_a_plugin_reports_its_artefact(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["artefacts", str(LAYOUT)]) == EXIT_OK
        lines = capsys.readouterr().out.splitlines()
        assert [line.split()[0] for line in lines] == ["c", "a2l", "layout"]
        assert lines[-1].split()[1] == "plugin"

    def test_a_project_without_plugins_reports_the_built_in_pair(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["artefacts", str(DEMO)]) == EXIT_OK
        assert [line.split()[0] for line in capsys.readouterr().out.splitlines()] == ["c", "a2l"]

    def test_the_plugins_can_be_named_without_a_project(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The question a build asks before it has assembled a project description of its own."""
        arguments = ["artefacts", "--plugin", str(EXAMPLES / "plugins" / "ddd_layout.py")]
        assert main(arguments) == EXIT_OK
        assert "layout" in capsys.readouterr().out

    def test_a_plugin_without_a_backend_is_named_rather_than_omitted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A plugin may contribute only checks and a block, so it is no artefact of its own.

        Leaving it out in silence reads as the plugin having failed to load, and calling it
        one that generates nothing reads as a plugin with no effect. Neither is true, so the
        note says what it is and where the files that do carry its block come from.
        """
        module = tmp_path / "ddd_quiet.py"
        module.write_text(
            "from ddd.plugins import Plugin" + chr(10) + "PLUGIN = Plugin(name='quiet')" + chr(10),
            encoding="utf-8",
        )
        assert main(["artefacts", "--plugin", str(module)]) == EXIT_OK
        captured = capsys.readouterr()
        assert [line.split()[0] for line in captured.out.splitlines()] == ["c", "a2l"]
        assert "'quiet'" in captured.err and "no artefact of its own" in captured.err
        assert "the c artefact renders" in captured.err, "the note says where its block lands"

        assert main(["artefacts", "--plugin", str(module), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["plugins_without_artefact"] == ["quiet"]
        assert [entry["name"] for entry in payload["artefacts"]] == ["c", "a2l"]

    def test_a_project_and_plugins_together_are_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A project names its own, so the two spellings would be two sources of truth."""
        arguments = ["artefacts", str(LAYOUT), "--plugin", "ddd_layout"]
        assert main(arguments) == EXIT_USAGE
        assert "--plugin cannot be given together with a project" in capsys.readouterr().err

    def test_json_carries_the_artefacts_and_the_diagnostics_contract(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["artefacts", str(LAYOUT), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert {"name": "layout", "kind": "plugin"} in payload["artefacts"]
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}

    def test_an_unreadable_project_is_a_finding_in_both_formats(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Tolerant like ``sources``: only a root file nothing can read is fatal."""
        missing = str(tmp_path / "nope.ddd.json")
        assert main(["artefacts", missing]) == EXIT_FINDINGS
        capsys.readouterr()
        assert main(["artefacts", missing, "--format", "json"]) == EXIT_FINDINGS
        assert json.loads(capsys.readouterr().out)["artefacts"] == []


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

    def test_checks_marks_the_project_wide_and_the_comparison_checks(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All three markers are derived from the registry, not hand listed.

        The set marked ``(project)`` in the text form is exactly what ``STANDALONE_POLICY``
        holds back, the set marked ``(comparison)`` is exactly the checks of the delivery
        comparison (section 4.1), and the set marked ``(fixed)`` is exactly the checks whose
        severity cannot be relaxed - all three read off the registry here too, so a check
        gaining or losing a flag would fail this test rather than leave the text form silent
        about it.

        The markers are read out of the trailing parenthetical rather than looked for anywhere
        in the line: a check carrying two of them renders them together, ``(fixed, project)``,
        which a substring search for ``(project)`` would miss.
        """
        from ddd.diagnostics import CHECKS, STANDALONE_POLICY

        def markers(line: str) -> set[str]:
            match = re.search(r"\(([^)]*)\)$", line)
            return set(match.group(1).split(", ")) if match else set()

        project_wide = {entry.removesuffix("=ignore") for entry in STANDALONE_POLICY}
        comparison = {name for name, info in CHECKS.items() if info.comparison}
        fixed = {name for name, info in CHECKS.items() if not info.overridable}
        assert main(["checks"]) == EXIT_OK
        lines = capsys.readouterr().out.splitlines()
        marked_project = {line.split()[0] for line in lines if "project" in markers(line)}
        marked_comparison = {line.split()[0] for line in lines if "comparison" in markers(line)}
        marked_fixed = {line.split()[0] for line in lines if "fixed" in markers(line)}
        assert marked_project == project_wide
        assert marked_comparison == comparison
        assert marked_fixed == fixed

    def test_a_check_carrying_two_markers_lists_them_in_one_parenthetical(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The rendering the registry cannot exercise, pinned from a plugin that can.

        The three flags are independent, and no built-in check sets two of them today, so
        nothing else here would notice the day one did - or the day the two markers started
        being printed as two parentheticals. A plugin declares the pair instead, and the line
        it produces is the one the documentation and the changelog quote.
        """
        module = tmp_path / "ddd_two_markers.py"
        module.write_text(
            """\
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import Plugin

PLUGIN = Plugin(
    name="two",
    checks=(
        CheckInfo(
            "two/needs-everything",
            Severity.ERROR,
            "a plugin check that needs every component and cannot be relaxed",
            overridable=False,
            needs_every_component=True,
        ),
    ),
)
""",
            encoding="utf-8",
        )
        assert main(["checks", "--plugin", str(module)]) == EXIT_OK
        listed = [
            line for line in capsys.readouterr().out.splitlines() if "two/needs-everything" in line
        ]
        assert listed and listed[0].endswith(" (fixed, project)"), listed

    def test_cmake_dir(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["cmake-dir"]) == EXIT_OK
        directory = Path(capsys.readouterr().out.strip())
        assert (directory / "Ddd.cmake").is_file()

    def test_checks_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["checks", "--format", "json"]) == EXIT_OK
        entries = json.loads(capsys.readouterr().out)
        assert {
            "check",
            "default_severity",
            "description",
            "overridable",
            "needs_every_component",
            "comparison",
        } <= set(entries[0])

    def test_checks_json_flags_match_the_registry(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The two new booleans are the registry's own flags, not a copy that can drift."""
        from ddd.diagnostics import CHECKS

        assert main(["checks", "--format", "json"]) == EXIT_OK
        entries = json.loads(capsys.readouterr().out)
        for entry in entries:
            info = CHECKS[entry["check"]]
            assert entry["needs_every_component"] == info.needs_every_component
            assert entry["comparison"] == info.comparison


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

    def test_the_plugin_modules_are_among_the_sources(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A build that does not re-run when a plugin changes generates with yesterday's rules."""
        assert main(["sources", str(LAYOUT)]) == EXIT_OK
        listed = capsys.readouterr().out.splitlines()
        assert PLUGIN_FILE.as_posix() in listed
        assert listed == sorted(listed)

    def test_the_plugin_modules_are_in_the_json_list_too(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["sources", str(LAYOUT), "--format", "json"]) == EXIT_OK
        assert PLUGIN_FILE.as_posix() in json.loads(capsys.readouterr().out)["sources"]

    def test_a_plugin_that_did_not_load_contributes_no_source(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The finding says why; the list stays what a build can watch."""
        write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["missing.py"])})
        assert main(["sources", str(tmp_path / "p.ddd.json")]) == EXIT_OK
        assert not any(line.endswith(".py") for line in capsys.readouterr().out.splitlines())

    def test_a_missing_include_is_reported_beside_the_listing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The root still reads, so the listing goes out; the missing file is a finding on
        stderr rather than a silent gap - only a root that cannot be read stops the listing."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "missing.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert main(["sources", str(tmp_path / "p.ddd.json")]) == EXIT_OK
        captured = capsys.readouterr()
        assert (tmp_path / "a.ddd.json").as_posix() in captured.out.splitlines()
        assert "error[file-not-found]" in captured.err

    def test_a_missing_include_does_not_change_the_json_contract(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The json document already carried the finding; this task only changes text mode."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "missing.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        arguments = ["sources", str(tmp_path / "p.ddd.json"), "--format", "json"]
        assert main(arguments) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["diagnostics"][0]["check"] == "file-not-found"
        assert payload["summary"]["error"] == 1

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
        captured = capsys.readouterr().err
        # The old wording named the output directory generically ("cannot write into"); the
        # new one names the actual path that failed - here, that is the directory itself.
        assert "cannot write '" in captured
        assert (tmp_path / "blocked").as_posix() in captured


RAISING_COMPARE_PLUGIN = '''
"""A plugin whose compare hook always raises, for testing that findings survive it."""

from __future__ import annotations

from ddd.plugins import CompareContext, Plugin


def compare(context: CompareContext) -> None:
    raise RuntimeError("boom")


PLUGIN = Plugin(name="raiser", compare=compare)
'''


RAISING_CHECK_PLUGIN = '''
"""A plugin whose check hook always raises, for testing that findings survive it."""

from __future__ import annotations

from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    raise RuntimeError("boom")


PLUGIN = Plugin(name="raiser", check=check)
'''


class TestFindingsSurviveAFailedStep:
    """A step that fails after the analysis must not take the findings down with it.

    The one run that fails is the one whose findings the reader needs; and the failing step
    - a file that cannot be written, a template that cannot render - is usually unrelated to
    what the findings say.
    """

    def files(self) -> dict[str, Any]:
        # An info finding (`missing-id`) on an otherwise clean project: what has to survive.
        return {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        }

    def test_a_renames_file_that_cannot_be_written(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        (tree / "blocked").mkdir()
        code = main(
            [
                "compare",
                str(tree / "project.ddd.json"),
                str(tree / "project.ddd.json"),
                "--renames",
                str(tree / "blocked"),
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "cannot write the --renames file" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("--renames file")

    def test_a_template_that_fails_to_render(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        templates = tree / "templates"
        templates.mkdir()
        (templates / "ddd_globals.c.jinja2").write_text(
            "{{ model.no_such_attribute.deeper }}", encoding="utf-8"
        )
        code = main(
            [
                "generate",
                "c",
                str(tree / "project.ddd.json"),
                "-t",
                str(templates),
                "-o",
                str(tree / "out"),
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "ddd_globals.c.jinja2" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("ddd_globals.c.jinja2")

    def test_an_address_map_that_cannot_be_read(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        (tree / "map.json").write_text("{ not json", encoding="utf-8")
        code = main(
            [
                "generate",
                "a2l",
                str(tree / "project.ddd.json"),
                "-o",
                str(tree / "out"),
                "--address-map",
                str(tree / "map.json"),
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "not valid json" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("not valid json")

    def test_an_output_file_that_cannot_be_written_is_named(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The directory is fine; one target inside it is a directory itself. Naming the
        directory sent the reader to check its permissions.

        ``ddd_globals.c`` sorts before ``ddd_globals.h`` and so renders and renames first;
        that it never appears is what shows the failure on the second file takes the first
        one back out rather than leaving the run half done. No temporary file survives
        either, wherever in the two files it was writing that the failure actually happened.
        """
        write_tree(tree, self.files())
        out = tree / "out"
        (out / "ddd_globals.h").mkdir(parents=True)
        code = main(
            ["generate", "c", str(tree / "project.ddd.json"), "-t", str(TEMPLATES), "-o", str(out)]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "cannot write '" in captured.err and "ddd_globals.h'" in captured.err
        assert not (out / "ddd_globals.c").exists()
        assert not any(out.rglob("*.ddd-staging"))

    def test_json_output_carries_the_findings_too(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        (tree / "blocked").mkdir()
        code = main(
            [
                "compare",
                str(tree / "project.ddd.json"),
                str(tree / "project.ddd.json"),
                "--renames",
                str(tree / "blocked"),
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        payload = json.loads(captured.out)
        assert [entry["check"] for entry in payload["diagnostics"]] == ["missing-id"]
        assert "cannot write the --renames file" in captured.err

    def test_a_run_that_would_write_nothing(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        code = main(
            [
                "generate",
                "all",
                str(tree / "project.ddd.json"),
                "-o",
                str(tree / "out"),
                "--without",
                "c",
                "--without",
                "a2l",
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "would write nothing" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("would write nothing")

    def test_the_same_in_json(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write_tree(tree, self.files())
        code = main(
            [
                "generate",
                "all",
                str(tree / "project.ddd.json"),
                "-o",
                str(tree / "out"),
                "--without",
                "c",
                "--without",
                "a2l",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        payload = json.loads(captured.out)
        assert [entry["check"] for entry in payload["diagnostics"]] == ["missing-id"]
        assert "would write nothing" in captured.err

    def test_a_plugin_option_refused_beside_a_description(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tree, self.files())
        code = main(
            [
                "compare",
                str(tree / "project.ddd.json"),
                str(tree / "project.ddd.json"),
                "--plugin",
                "nowhere.py",
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "--plugin names the plugins" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("--plugin names the plugins")

    def test_a_compare_hook_that_raises_under_check_baseline(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["raising.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
                "raising.py": RAISING_COMPARE_PLUGIN,
            },
        )
        code = main(
            [
                "check",
                str(tree / "project.ddd.json"),
                "--baseline",
                str(tree / "project.ddd.json"),
            ]
        )
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "failed in its compare hook" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("failed in its compare hook")

    def test_a_check_hook_that_raises_leaves_dump_json_stdout_empty(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``ddd dump`` promises stdout to the dictionary alone, in both formats; a step
        that fails after the analysis must keep that promise too, not just a clean run."""
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["raising.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
                "raising.py": RAISING_CHECK_PLUGIN,
            },
        )
        code = main(["dump", str(tree / "project.ddd.json"), "--format", "json"])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert captured.out == ""
        boundary = captured.err.index("ddd: plugin")
        payload = json.loads(captured.err[:boundary])
        assert payload["summary"]["info"] == 1
        assert "failed in its check hook" in captured.err[boundary:]

    def test_an_unknown_plugin_check_reports_the_load_time_findings_first(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An override naming a plugin check is held until the project is read; what the
        read already found - here a relaxed ``file-extension`` warning - must not be lost
        under the usage error that follows once no loaded plugin registers it."""
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "plain.json"),
                "plain.json": component("A", declare("local", "X")),
            },
        )
        project_path = tree / "project.ddd.json"
        severities = ["-W", "file-extension=warning", "-W", "tag/no-such=error"]
        for arguments in (
            ["check", str(project_path), *severities],
            ["compare", str(project_path), str(project_path), *severities],
        ):
            code = main(arguments)
            captured = capsys.readouterr()
            assert code == EXIT_USAGE
            assert "warning[file-extension]" in captured.err
            assert "unknown check 'tag/no-such'" in captured.err
            assert captured.err.index("warning[file-extension]") < captured.err.index(
                "unknown check 'tag/no-such'"
            )


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


class TestDumpToAFile:
    """``-o`` changes where the dictionary goes; the text, the exit code and the findings stay.

    A build wants the dictionary in a file, and a redirection leaves the bytes to the shell:
    Windows PowerShell writes a byte order mark and crlf, and every shell empties the target
    before the tool has even started. The file is therefore written the way ``generate``
    writes an artefact, while everything a reader of stdout relied on - the text, the exit
    code, the findings on stderr - stays what it was.
    """

    CLEAN: ClassVar[dict[str, Any]] = {
        "project.ddd.json": project("P", "a.ddd.json"),
        "a.ddd.json": component("A", declare("local", "X", description="Température")),
    }
    """Resolves without an error, and carries text beyond ascii, which a codepage would show."""

    WITH_ERRORS: ClassVar[dict[str, Any]] = {
        "project.ddd.json": project("P", "a.ddd.json"),
        "a.ddd.json": component("A", declare("local", "X"), declare("input", "Unproduced")),
    }
    """Resolves, and reports an error: an input no component produces."""

    @pytest.mark.parametrize(
        ("files", "code"),
        [(CLEAN, EXIT_OK), (WITH_ERRORS, EXIT_FINDINGS)],
        ids=["clean", "with-errors"],
    )
    def test_the_file_holds_what_stdout_would_have_carried(
        self,
        files: dict[str, Any],
        code: int,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Byte for byte - utf-8, no byte order mark, lf - and with the same exit code: a
        project whose errors still let it resolve is written, exactly as it is printed."""
        write_tree(tree, files)
        source = str(tree / "project.ddd.json")
        assert main(["dump", source]) == code
        printed = capsys.readouterr().out
        target = tree / "dictionary.json"
        assert main(["dump", source, "-o", str(target)]) == code
        assert capsys.readouterr().out == ""
        assert target.read_bytes() == printed.encode("utf-8")

    def test_a_file_that_would_not_change_is_left_alone(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Its timestamp is what a build compares; a rewrite would re-run whatever reads it."""
        write_tree(tree, self.CLEAN)
        target = tree / "dictionary.json"
        shown = re.escape(target.as_posix())
        arguments = ["dump", str(tree / "project.ddd.json"), "-o", str(target)]
        assert main(arguments) == EXIT_OK
        assert re.search(rf"^wrote\s+{shown} \(created\)$", capsys.readouterr().err, re.M)
        os.utime(target, (1_000_000_000, 1_000_000_000))
        assert main(arguments) == EXIT_OK
        assert re.search(rf"^unchanged\s+{shown}$", capsys.readouterr().err, re.M)
        assert target.stat().st_mtime == 1_000_000_000

    def test_it_creates_the_directory_it_writes_into(self, tree: Path) -> None:
        """A release step names where the dictionary goes before anything has made that place."""
        write_tree(tree, self.CLEAN)
        target = tree / "release" / "1.4.0" / "dictionary.json"
        assert main(["dump", str(tree / "project.ddd.json"), "-o", str(target)]) == EXIT_OK
        assert target.is_file()

    def test_a_project_that_does_not_resolve_leaves_the_file_as_it_was(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """There is no dictionary to write, so the last one stays; a redirection would have
        emptied it before the run even started."""
        target = tree / "dictionary.json"
        target.write_bytes(b"the previous dictionary\n")
        arguments = ["dump", str(tree / "missing.ddd.json"), "-o", str(target)]
        assert main(arguments) == EXIT_FINDINGS
        assert "file-not-found" in capsys.readouterr().err
        assert target.read_bytes() == b"the previous dictionary\n"

    def test_a_target_that_cannot_be_written_is_a_usage_error_after_the_findings(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A directory standing where the file goes is the caller's mistake: one line and
        exit 2, after the findings of the run - which is the run whose findings are needed."""
        write_tree(tree, self.CLEAN)
        target = tree / "dictionary.json"
        target.mkdir()
        assert main(["dump", str(tree / "project.ddd.json"), "-o", str(target)]) == EXIT_USAGE
        err = capsys.readouterr().err
        assert "info[missing-id]" in err
        assert f"cannot write '{target.as_posix()}'" in err
        assert err.index("info[missing-id]") < err.index("cannot write")

    def test_in_json_a_target_that_cannot_be_written_leaves_stdout_empty(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The findings reported ahead of the usage error go to stderr, as every report of
        ``dump`` does: stdout belongs to the dictionary, and there is none to print."""
        write_tree(tree, self.CLEAN)
        target = tree / "dictionary.json"
        target.mkdir()
        arguments = ["dump", str(tree / "project.ddd.json"), "-o", str(target), "--format", "json"]
        assert main(arguments) == EXIT_USAGE
        captured = capsys.readouterr()
        assert captured.out == ""
        boundary = captured.err.index("ddd: cannot write")
        assert json.loads(captured.err[:boundary])["summary"]["info"] == 1

    def test_in_json_the_written_file_is_reported_with_the_findings_on_stderr(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """In the document ``dump`` already sends to stderr, the way ``generate`` reports a
        file in its own; stdout stays empty in both formats."""
        write_tree(tree, self.CLEAN)
        target = tree / "dictionary.json"
        arguments = ["dump", str(tree / "project.ddd.json"), "-o", str(target), "--format", "json"]
        assert main(arguments) == EXIT_OK
        captured = capsys.readouterr()
        assert captured.out == ""
        payload = json.loads(captured.err)
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 1}
        assert payload["generated"] == [{"path": target.as_posix(), "status": "created"}]


class TestGenerateTheDictionary:
    """``--dictionary`` writes the dictionary a run generates from, beside what it generates.

    In the same run - one analysis, one report of its findings - and in the same write as the
    artefacts, so that all of them are written or none is, and a build never keeps a dictionary
    that does not describe the files beside it.
    """

    def a2l(
        self, output: Path, dictionary: Path | str, *extra: str, project: Path = DEMO
    ) -> list[str]:
        """``generate a2l``, the artefact that needs no templates, with the dictionary asked for."""
        arguments = ["generate", "a2l", str(project), "-o", str(output)]
        return [*arguments, "--dictionary", str(dictionary), *extra]

    @pytest.mark.parametrize("artefact", ["c", "a2l", "all"])
    def test_every_artefact_writes_what_dump_prints(
        self, artefact: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["dump", str(DEMO)]) == EXIT_OK
        printed = capsys.readouterr().out
        target = tmp_path / "gen" / "DemoDevice.dictionary.json"
        templates = [] if artefact == "a2l" else ["-t", str(TEMPLATES)]
        arguments = ["generate", artefact, str(DEMO), "-o", str(tmp_path / "gen"), *templates]
        assert main([*arguments, "--dictionary", str(target)]) == EXIT_OK
        assert target.read_bytes() == printed.encode("utf-8")

    def test_it_is_reported_with_the_artefacts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = tmp_path / "gen" / "DemoDevice.dictionary.json"
        assert main([*self.a2l(tmp_path / "gen", target), "--format", "json"]) == EXIT_OK
        generated = json.loads(capsys.readouterr().out)["generated"]
        assert {"path": target.as_posix(), "status": "created"} in generated

    def test_a_run_whose_checks_fail_writes_no_dictionary(self, tmp_path: Path) -> None:
        """The gate the artefacts go through: nothing is written from a project with errors."""
        target = tmp_path / "dictionary.json"
        assert main(self.a2l(tmp_path / "gen", target, project=INCONSISTENT)) == EXIT_FINDINGS
        assert not target.exists()

    def test_a_dry_run_reports_it_and_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = tmp_path / "gen" / "DemoDevice.dictionary.json"
        assert main(self.a2l(tmp_path / "gen", target, "--dry-run")) == EXIT_OK
        shown = re.escape(target.as_posix())
        assert re.search(rf"^would write\s+{shown} \(created\)$", capsys.readouterr().err, re.M)
        assert not target.exists()

    @pytest.mark.parametrize("blocked", ["dictionary", "a2l"])
    def test_it_is_written_with_the_artefacts_or_none_of_them_is(
        self, blocked: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One write for all of them: whichever file cannot be written, the other one the run
        created is taken back - a dictionary never outlives the artefacts it describes, and an
        artefact never appears without the dictionary asked for beside it."""
        output = tmp_path / "gen"
        files = {
            "dictionary": output / "DemoDevice.dictionary.json",
            "a2l": output / "DemoDevice.a2l",
        }
        files[blocked].mkdir(parents=True)
        assert main(self.a2l(output, files["dictionary"])) == EXIT_USAGE
        assert f"cannot write '{files[blocked].as_posix()}'" in capsys.readouterr().err
        assert not any(path.exists() for name, path in files.items() if name != blocked)

    def test_a_path_an_artefact_is_written_to_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two writes to one file would keep whichever came last; the run refuses before either."""
        output = tmp_path / "gen"
        assert main(self.a2l(output, output / "DemoDevice.a2l")) == EXIT_USAGE
        assert "would both write 'DemoDevice.a2l'" in capsys.readouterr().err
        assert not output.exists()

    def test_a_run_left_with_the_dictionary_alone_still_writes_it(self, tmp_path: Path) -> None:
        """``--without`` may take every built-in artefact away; the dictionary is still a file
        this run writes, so the run is not refused as one that would write nothing."""
        target = tmp_path / "dictionary.json"
        arguments = ["generate", "all", str(DEMO), "-o", str(tmp_path / "gen")]
        arguments += ["--without", "c", "--without", "a2l", "--dictionary", str(target)]
        assert main(arguments) == EXIT_OK
        assert target.is_file()

    def test_a_relative_path_is_taken_from_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Like every other path on the command line, and unlike a file a backend names: the
        output directory does not prefix it."""
        monkeypatch.chdir(tmp_path)
        assert main(self.a2l(Path("gen"), "dictionary.json")) == EXIT_OK
        assert (tmp_path / "dictionary.json").is_file()
        assert not (tmp_path / "gen" / "dictionary.json").exists()


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


class TestDisplayedPath:
    """A written path is reported the way the reader typed its output directory.

    A failure on the output directory itself hands the reporter that directory, not a file
    under it, and a text join would print ``out/.``; a path join collapses the dot, for
    ``-o .`` as much as for a directory reported on its own.
    """

    def test_the_output_directory_itself_is_spelled_as_typed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert _displayed_path((tmp_path / "out").resolve(), Path("out")) == "out"
        assert _displayed_path((tmp_path / "out" / "x.h").resolve(), Path("./out")) == "out/x.h"
        assert _displayed_path(tmp_path.resolve(), Path()) == "."
        assert _displayed_path((tmp_path / "x.h").resolve(), Path()) == "x.h"

    def test_an_absolute_output_directory_is_spelled_as_typed_too(self, tmp_path: Path) -> None:
        """An absolute ``-o`` used to be printed resolved, which threw away the very spelling
        this exists to keep: a junction, or - portably - a climb back out of a directory, is
        the reader's own way of naming the place and is what the report should say."""
        out = tmp_path.resolve() / "out"
        typed = out / ".." / "out"
        assert _displayed_path(out / "x.h", typed) == (typed / "x.h").as_posix()
        assert _displayed_path(out / "x.h", out) == (out / "x.h").as_posix()

    def test_a_path_that_is_not_under_the_output_directory_is_left_as_it_is(
        self, tmp_path: Path
    ) -> None:
        """The failure path hands this the raw ``filename`` of an ``OSError``, which is not a
        path the renderer has already vetted: a ``-o build/gen`` whose ``build`` cannot be
        created fails on ``build``, which is above the output directory, not under it."""
        outside = tmp_path.resolve() / "build"
        assert _displayed_path(outside, outside / "gen") == outside.as_posix()
