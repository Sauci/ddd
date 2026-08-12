"""Tests for comparing two deliveries: can the candidate replace the baseline?"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import DEMO, checks, component, declare, messages, project, write_tree
from ddd.analysis import analyze
from ddd.cli import EXIT_FINDINGS, EXIT_OK, main
from ddd.compare import compare
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.ir import DataDictionary
from ddd.loading import load_workspace


def resolve(base: Path, root: str) -> DataDictionary:
    bag = DiagnosticBag()
    workspace = load_workspace(base / root, bag)
    assert workspace is not None, messages(bag)
    return analyze(workspace, bag)


def one_component(base: Path, name: str, *declarations: dict[str, Any]) -> DataDictionary:
    """Resolve a single component project into a dictionary."""
    write_tree(
        base,
        {
            f"{name}.ddd.json": project("P", f"{name}-a.ddd.json"),
            f"{name}-a.ddd.json": component("A", *declarations),
        },
    )
    return resolve(base, f"{name}.ddd.json")


def verdict(baseline: DataDictionary, candidate: DataDictionary, *severities: str) -> DiagnosticBag:
    bag = DiagnosticBag(SeverityPolicy.from_strings(severities))
    compare(baseline, candidate, bag)
    return bag


class TestBreakingChanges:
    def test_an_identical_delivery_is_a_drop_in_replacement(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", "uint16", init=1))
        new = one_component(tree, "new", declare("local", "X", "uint16", init=1))
        bag = verdict(old, new)
        assert checks(bag) == []
        assert not bag.has_errors

    def test_a_rescaled_conversion_is_breaking(self, tree: Path) -> None:
        """The failure that compiles, links, runs and reports wrong numbers."""
        old = one_component(
            tree, "old", declare("local", "X", "uint16", unit="Hz", conversion={"factor": 0.25})
        )
        new = one_component(
            tree, "new", declare("local", "X", "uint16", unit="Hz", conversion={"factor": 0.5})
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "conversion: linear(factor=0.5" in messages(bag)
        assert bag.has_errors

    def test_an_enumerator_description_edit_is_no_finding_at_all(self, tree: Path) -> None:
        """Descriptions are not compared, an enumerator's free text included.

        The live checks already ignore it - ``enum-conflict`` compares the ordered name and
        value pairs - so a delivery that only documents an enumerator has to compare clean
        as well, instead of failing as ``changed-interface`` over identical generated code.
        """
        old = one_component(
            tree, "old", declare("local", "X", "uint8", conversion=self.enum(("M_OFF", 0, "")))
        )
        new = one_component(
            tree,
            "new",
            declare("local", "X", "uint8", conversion=self.enum(("M_OFF", 0, "switched off"))),
        )
        assert checks(verdict(old, new)) == []

    @pytest.mark.parametrize(
        ("was", "now"),
        [
            # A reordering moves every enumerator of the generated typedef.
            ([("M_OFF", 0, ""), ("M_ON", 1, "")], [("M_ON", 1, ""), ("M_OFF", 0, "")]),
            # A revalued enumerator falsifies every archived reading of the state.
            ([("M_OFF", 0, "")], [("M_OFF", 1, "")]),
        ],
    )
    def test_enumerator_order_and_values_still_break(
        self,
        tree: Path,
        was: list[tuple[str, int, str]],
        now: list[tuple[str, int, str]],
    ) -> None:
        old = one_component(tree, "old", declare("local", "X", "uint8", conversion=self.enum(*was)))
        new = one_component(tree, "new", declare("local", "X", "uint8", conversion=self.enum(*now)))
        assert checks(verdict(old, new)) == ["changed-interface"]

    @staticmethod
    def enum(*enumerators: tuple[str, int, str]) -> dict[str, Any]:
        return {
            "kind": "enum",
            "name": "Mode_t",
            "enumerators": [
                {"name": name, "value": value, "description": description}
                for name, value, description in enumerators
            ],
        }

    @pytest.mark.parametrize(
        ("field", "was", "now"),
        [
            ("datatype", "uint16", "uint32"),
            ("datatype", "sint32", "sint16"),
            ("unit", "Hz", "V"),
        ],
    )
    def test_widening_and_narrowing_are_both_breaking(
        self, tree: Path, field: str, was: str, now: str
    ) -> None:
        old = one_component(tree, "old", declare("local", "X", **{field: was}))
        new = one_component(tree, "new", declare("local", "X", **{field: now}))
        assert checks(verdict(old, new)) == ["changed-interface"]

    def test_a_removed_object_nobody_read_is_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X"), declare("local", "Y"))
        new = one_component(tree, "new", declare("local", "Y"))
        bag = verdict(old, new)
        assert checks(bag) == ["removed-unused-object"]
        assert "no component read it" in messages(bag)
        assert not bag.has_errors

    def test_a_removed_object_with_consumers_is_an_error(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "old.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
                "new.ddd.json": project("P", "c.ddd.json"),
                "c.ddd.json": component("C", declare("local", "Z")),
            },
        )
        report = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
        assert "removed-object" in checks(report)
        assert "was read by B" in messages(report)

    def test_an_object_turning_local_is_breaking(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("output", "X"))
        new = one_component(tree, "new", declare("local", "X"))
        bag = verdict(old, new)
        assert "changed-interface" in checks(bag)
        assert "local: true != false" in messages(bag)

    def test_a_curve_pointed_at_another_axis_is_breaking(self, tree: Path) -> None:
        """The values stay, the break points move: every interpolated result changes."""
        old = one_component(
            tree,
            "old",
            declare("local", "Ax", "uint16", kind="axis", size=3),
            declare("local", "Ay", "uint16", kind="axis", size=3),
            declare("local", "C", "uint8", kind="curve", axis="Ax"),
        )
        new = one_component(
            tree,
            "new",
            declare("local", "Ax", "uint16", kind="axis", size=3),
            declare("local", "Ay", "uint16", kind="axis", size=3),
            declare("local", "C", "uint8", kind="curve", axis="Ay"),
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "references: axis=Ay != axis=Ax" in messages(bag)

    def test_gaining_a_reference_is_reported_against_none(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "Ax", "uint16", kind="axis", size=3))
        new = one_component(
            tree, "new", declare("local", "Ax", "uint16", kind="axis", size=3, input="Ax")
        )
        assert "references: input=Ax != none" in messages(verdict(old, new))

    def test_a_kind_change_is_breaking(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", "uint16"))
        new = one_component(tree, "new", declare("local", "X", "uint16", kind="parameter"))
        assert "changed-interface" in checks(verdict(old, new))


class TestGradedChanges:
    def test_an_added_object_is_only_information(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X"))
        new = one_component(tree, "new", declare("local", "X"), declare("local", "Y"))
        bag = verdict(old, new)
        assert checks(bag) == ["added-object"]
        assert not bag.has_errors

    def test_widened_limits_are_silent(self, tree: Path) -> None:
        """Every value the baseline allowed still fits, so there is nothing to report."""
        old = one_component(tree, "old", declare("local", "X", limits={"min": 10, "max": 20}))
        new = one_component(tree, "new", declare("local", "X", limits={"min": 0, "max": 30}))
        assert checks(verdict(old, new)) == []

    def test_narrowed_limits_are_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", limits={"min": 0, "max": 30}))
        new = one_component(tree, "new", declare("local", "X", limits={"min": 10, "max": 20}))
        bag = verdict(old, new)
        assert checks(bag) == ["narrowed-limits"]
        assert "tightened from [0, 30] to [10, 20]" in messages(bag)
        assert not bag.has_errors

    def test_a_changed_initial_value_is_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", init=1))
        new = one_component(tree, "new", declare("local", "X", init=2))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"]
        assert "init: 2 != 1" in messages(bag)

    def test_a_new_producer_is_a_warning(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "old.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
                "new.ddd.json": project("P", "c.ddd.json", "b.ddd.json"),
                "c.ddd.json": component("C", declare("output", "X")),
            },
        )
        report = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
        assert checks(report) == ["changed-owner"]
        assert "produced by C instead of A" in messages(report)

    def test_a_changed_condition_is_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", condition="defined(A)"))
        new = one_component(tree, "new", declare("local", "X", condition="defined(B)"))
        assert checks(verdict(old, new)) == ["changed-condition"]

    def test_a_changed_a2l_entry_is_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X"))
        new = one_component(tree, "new", declare("local", "X", a2l={"export": False}))
        assert checks(verdict(old, new)) == ["changed-a2l"]

    def test_stating_an_export_that_was_already_in_force_is_no_change(self, tree: Path) -> None:
        """An a2l entry is compared as it will be, not as it happens to be written.

        A baseline that leaves ``export`` out exports the object, so a delivery that spells
        out ``true`` delivers the same a2l. Comparing the records raw made that a warning, and
        one nobody can act on: the fix is to write the key the baseline did not have.
        """
        old = one_component(tree, "old", declare("local", "X"))
        new = one_component(tree, "new", declare("local", "X", a2l={"export": True}))
        assert checks(verdict(old, new)) == []

    def test_a_changed_a2l_entry_names_only_what_changed(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X"))
        new = one_component(
            tree, "new", declare("local", "X", a2l={"export": True, "format": "%8.2"})
        )
        report = verdict(old, new)
        assert checks(report) == ["changed-a2l"]
        assert "format: none -> '%8.2'" in messages(report)
        assert "export" not in messages(report)

    def test_a_team_can_relax_any_of_it(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", "uint16"))
        new = one_component(tree, "new", declare("local", "X", "uint32"))
        assert checks(verdict(old, new, "changed-interface=ignore")) == []


class TestCommandLine:
    def dump_to(self, path: Path, source: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["dump", str(source)]) == EXIT_OK
        path.write_text(capsys.readouterr().out, encoding="utf-8")

    def test_comparing_a_dump_with_a_project(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = tmp_path / "baseline.json"
        self.dump_to(baseline, DEMO, capsys)
        assert main(["compare", str(baseline), str(DEMO)]) == EXIT_OK
        assert "can replace baseline.json" in capsys.readouterr().err

    def test_a_project_can_be_checked_against_a_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The ci shape: one command, one exit code, for both questions."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "uint16")),
            },
        )
        self.dump_to(tmp_path / "baseline.json", tmp_path / "p.ddd.json", capsys)

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("local", "X", "uint32"))})
        arguments = [
            "check",
            str(tmp_path / "p.ddd.json"),
            "--baseline",
            str(tmp_path / "baseline.json"),
        ]
        assert main(arguments) == EXIT_FINDINGS
        assert "changed-interface" in capsys.readouterr().err

    def test_a_check_without_a_baseline_compares_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["check", str(DEMO)]) == EXIT_OK
        assert "changed-" not in capsys.readouterr().err

    def test_an_unreadable_baseline_is_reported(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["compare", "nope.json", str(DEMO)]) == EXIT_FINDINGS
        assert "does not exist" in capsys.readouterr().err

    def test_a_baseline_that_is_not_a_dictionary_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        broken = tmp_path / "broken.json"
        broken.write_text('{"objects": "not a list"}', encoding="utf-8")
        assert main(["compare", str(broken), str(DEMO)]) == EXIT_FINDINGS
        assert "schema" in capsys.readouterr().err

    def test_an_inconsistent_candidate_project_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Missing")),
            },
        )
        self.dump_to(tmp_path / "baseline.json", DEMO, capsys)
        arguments = ["compare", str(tmp_path / "baseline.json"), str(tmp_path / "p.ddd.json")]
        assert main(arguments) == EXIT_FINDINGS
        assert "missing-producer" in capsys.readouterr().err

    def test_a_check_whose_baseline_cannot_be_read_still_reports(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["check", str(DEMO), "--baseline", "absent.json"]) == EXIT_FINDINGS
        assert "does not exist" in capsys.readouterr().err

    def test_json_output_carries_the_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = tmp_path / "baseline.json"
        self.dump_to(baseline, DEMO, capsys)
        assert main(["compare", str(baseline), str(DEMO), "--format", "json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}
