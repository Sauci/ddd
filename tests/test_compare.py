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


def one_component_measuring(base: Path, name: str, raster: str) -> DataDictionary:
    """A single component project whose one measurement names a raster."""
    write_tree(
        base,
        {
            f"{name}.ddd.json": project("P", f"{name}-r.ddd.json", f"{name}-a.ddd.json"),
            f"{name}-r.ddd.json": {
                "rasters": [
                    {"raster": "1ms", "event": 0, "cycle": "1ms"},
                    {"raster": "10ms", "event": 1, "cycle": "10ms"},
                ]
            },
            f"{name}-a.ddd.json": component("A", declare("local", "X", raster=raster)),
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

    def test_a_changed_raster_is_a_warning(self, tree: Path) -> None:
        """A signal moving from the 10 ms to the 1 ms event changes the a2l a calibration
        engineer works with, and invalidates nobody's code."""
        old = one_component_measuring(tree, "old", "10ms")
        new = one_component_measuring(tree, "new", "1ms")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"]
        assert "raster: 1ms != 10ms" in messages(bag)

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
        # The candidate side is analysed fresh from its description, so the demo's own
        # missing-id nudges would otherwise land in this bag alongside the comparison; they
        # are not a finding of the comparison this test is about.
        arguments = [
            "compare",
            str(baseline),
            str(DEMO),
            "--format",
            "json",
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"] == {"error": 0, "warning": 0, "info": 0}


def test_a_renamed_object_is_one_finding_not_two(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "FilterGain", id="k7m2q9xr4t8w"))
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object"], messages(bag)
    assert "'FiltGain'" in messages(bag) and "'FilterGain'" in messages(bag)


def test_a_rename_that_also_changed_the_interface_reports_both(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", "uint8", id="k7m2q9xr4t8w"))
    after = one_component(
        tree, "after", declare("local", "FilterGain", "uint16", id="k7m2q9xr4t8w")
    )
    bag = verdict(before, after)
    assert set(checks(bag)) == {"renamed-object", "changed-interface"}, messages(bag)


def test_a_swap_is_two_renames_and_two_reused_names(tree):
    """The case no name-matching heuristic can get right.

    A swap is also the most damaging reuse there is: each name genuinely does come to mean
    a different object, so `reused-name` firing here alongside the renames is correct - not
    a false positive to suppress.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", id="k7m2q9xr4t8w"),
        declare("local", "B", id="p3rt5vwx9z2q"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "B", id="k7m2q9xr4t8w"),
        declare("local", "A", id="p3rt5vwx9z2q"),
    )
    bag = verdict(before, after)
    assert checks(bag) == [
        "renamed-object",
        "renamed-object",
        "reused-name",
        "reused-name",
    ], messages(bag)


def test_objects_without_an_identity_still_pair_by_name(tree):
    before = one_component(tree, "before", declare("local", "X"))
    after = one_component(tree, "after", declare("local", "X"))
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))


def test_a_baseline_without_identities_infers_no_rename(tree):
    """A format 5 baseline recorded none, so a rename against it is still two findings."""
    before = one_component(tree, "before", declare("local", "FiltGain"))
    after = one_component(tree, "after", declare("local", "FilterGain", id="k7m2q9xr4t8w"))
    bag = verdict(before, after)
    assert "renamed-object" not in checks(bag), messages(bag)
    assert "removed-unused-object" in checks(bag)


def test_two_different_objects_that_share_a_name_are_not_paired(tree):
    """Ruling 3: when both sides carry an id for this name and the ids differ, that says
    outright that these are two different objects. Pairing them by name anyway would run
    the whole interface comparison between two unrelated things and report nothing at all
    here, since only the id differs and an id is never a compared field - silently hiding
    the fact that the name now means something else. Leaving them unpaired is what lets
    `reused-name` say so explicitly instead, alongside the removal and the addition it
    accompanies (design doc section 5.3).
    """
    before = one_component(tree, "before", declare("local", "A", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "A", id="p3rt5vwx9z2q"))
    bag = verdict(before, after)
    assert "renamed-object" not in checks(bag), messages(bag)
    assert set(checks(bag)) == {
        "reused-name",
        "removed-unused-object",
        "added-object",
    }, messages(bag)


def test_a_name_freed_by_a_rename_and_claimed_again_is_an_error(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", id="k7m2q9xr4t8w"))
    after = one_component(
        tree,
        "after",
        declare("local", "FilterGain", id="k7m2q9xr4t8w"),
        declare("local", "FiltGain", id="p3rt5vwx9z2q"),
    )
    bag = verdict(before, after)
    assert "reused-name" in checks(bag), messages(bag)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "reused-name"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes, "the note says where it went"
    note_text, _ = findings[0].notes[0]
    assert note_text == "'FiltGain' is now called 'FilterGain'"


def test_a_reused_name_is_caught_even_when_the_claimant_has_no_id_yet(tree):
    """Pairing has already proved, by id, that the baseline's 'FiltGain' is now called
    'FilterGain', so whatever still answers to 'FiltGain' in the candidate provably is not it -
    whether or not that entry has adopted an id of its own yet. Requiring both sides to state
    one stayed silent on exactly this asymmetry, which is not a corner case: it is a project
    migrating one component at a time (design section 5.1), caught mid-migration.
    """
    before = one_component(tree, "before", declare("local", "FiltGain", id="k7m2q9xr4t8w"))
    after = one_component(
        tree,
        "after",
        declare("local", "FilterGain", id="k7m2q9xr4t8w"),
        declare("local", "FiltGain"),
    )
    bag = verdict(before, after)
    assert set(checks(bag)) == {"renamed-object", "reused-name", "added-object"}, messages(bag)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "reused-name"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes, "the note says where the old object went"
    note_text, _ = findings[0].notes[0]
    assert note_text == "'FiltGain' is now called 'FilterGain'"


def test_a_name_reused_after_a_deletion_is_an_error(tree):
    before = one_component(tree, "before", declare("local", "X", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "X", id="p3rt5vwx9z2q"))
    assert "reused-name" in checks(verdict(before, after)), messages(verdict(before, after))


def test_a_name_kept_by_the_same_object_is_not_a_reuse(tree):
    before = one_component(tree, "before", declare("local", "X", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "X", id="k7m2q9xr4t8w"))
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))


def _curve_over(axis: str, axis_id: str, curve_id: str) -> list[dict[str, Any]]:
    return [
        declare("local", axis, kind="axis", size=8, id=axis_id),
        declare("local", "Curve", kind="curve", axis=axis, id=curve_id),
    ]


def test_renaming_an_axis_does_not_report_its_curve(tree):
    before = one_component(tree, "before", *_curve_over("A", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    after = one_component(tree, "after", *_curve_over("B", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object"], messages(bag)


def test_pointing_a_curve_at_a_different_axis_is_still_an_interface_change(tree):
    before = one_component(tree, "before", *_curve_over("A", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    after = one_component(
        tree,
        "after",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "Other", kind="axis", size=8, id="w9x8y7z6q5r4"),
        declare("local", "Curve", kind="curve", axis="Other", id="p3rt5vwx9z2q"),
    )
    assert "changed-interface" in checks(verdict(before, after)), messages(verdict(before, after))


def test_a_format_5_style_baseline_against_a_stamped_candidate_has_no_false_change(tree):
    """The exact first step ``docs/comparing_deliveries.rst`` teaches: archive a baseline
    before adopting ids, then run ``ddd id --assign`` on the working tree and compare against
    it. Resolving each side's referent on its own made a tuple and a bare name compare unequal,
    so this reported a phantom ``changed-interface`` on the curve the moment the candidate
    alone had adopted ids - on every project taking this exact first migration step.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", kind="axis", size=8),
        declare("local", "Curve", kind="curve", axis="A"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "Curve", kind="curve", axis="A", id="p3rt5vwx9z2q"),
    )
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))


def test_only_the_axis_gaining_an_id_this_delivery_has_no_false_change(tree):
    """Partial adoption within format 6: the curve already carries a stable id from an earlier
    delivery and pairs on it, while the axis it refers to is only gaining one now. The fallback
    to comparing written names has to hold regardless of how the *referring* object itself
    happened to be paired.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", kind="axis", size=8),
        declare("local", "Curve", kind="curve", axis="A", id="p3rt5vwx9z2q"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "Curve", kind="curve", axis="A", id="p3rt5vwx9z2q"),
    )
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))


def test_a_reference_change_still_suppresses_its_own_limits_narrowing(tree):
    """The gate that suppresses a limits narrowing which is a consequence of an interface
    change - ``narrowed and not interface and references is None`` in ``_compare_object`` -
    reads ``_compare_references``'s return value directly. A genuine reference change, an axis
    actually swapped for another rather than the asymmetric false positive above, still has to
    suppress it: fixing the false positive must not detach the gate from a real one.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "B", kind="axis", size=8, id="w9x8y7z6q5r4"),
        declare(
            "local",
            "Curve",
            kind="curve",
            axis="A",
            id="p3rt5vwx9z2q",
            limits={"min": 0, "max": 30},
        ),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "B", kind="axis", size=8, id="w9x8y7z6q5r4"),
        declare(
            "local",
            "Curve",
            kind="curve",
            axis="B",
            id="p3rt5vwx9z2q",
            limits={"min": 10, "max": 20},
        ),
    )
    bag = verdict(before, after)
    assert checks(bag) == ["changed-interface"], messages(bag)


def test_a_stale_reference_through_a_reused_name_says_so(tree):
    """The discriminating case a same-text comparison cannot tell apart from no change at all.

    The curve's own declaration is untouched - it still spells ``"axis": "A"`` on both sides -
    but 'A' was freed by a rename (old 'A' became 'R') and immediately reused by a different
    axis (old 'Q' became 'A'), so the curve is silently rebound to an object it never named.
    Printing ``axis=A != axis=A`` would read as nothing having changed; the message has to
    name what actually happened instead.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "Q", kind="axis", size=8, id="b4n6p8qs2v4w"),
        declare("local", "C", kind="curve", axis="A", id="p3rt5vwx9z2q"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "R", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "A", kind="axis", size=8, id="b4n6p8qs2v4w"),
        declare("local", "C", kind="curve", axis="A", id="p3rt5vwx9z2q"),
    )
    bag = verdict(before, after)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "changed-interface"]
    assert len(findings) == 1, messages(bag)
    assert "axis=A (now names a different object) != axis=A" in findings[0].render(), messages(bag)


def test_a_renamed_instance_keeps_its_array_elements_paired(tree):
    """A leaf's identity is its instance's id together with the part of its path below the
    instance, so ``Inlet[2].value`` stays paired with itself - not with a neighbouring
    element - when the instance, not the member, is renamed.
    """
    cell_type = {
        "types": [
            {
                "type": "struct",
                "name": "Cell_t",
                "members": [
                    {
                        "name": "value",
                        "member": "value",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                    }
                ],
            }
        ]
    }
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "t.ddd.json", "before-a.ddd.json"),
            "after.ddd.json": project("P", "t.ddd.json", "after-a.ddd.json"),
            "t.ddd.json": cell_type,
            "before-a.ddd.json": component(
                "A",
                declare("local", "Inlet", typename="Cell_t", dimensions=[3], id="k7m2q9xr4t8w"),
            ),
            "after-a.ddd.json": component(
                "A",
                declare("local", "Sensor", typename="Cell_t", dimensions=[3], id="k7m2q9xr4t8w"),
            ),
        },
    )
    bag = verdict(resolve(tree, "before.ddd.json"), resolve(tree, "after.ddd.json"))
    assert checks(bag) == ["renamed-object"] * 3, messages(bag)
    assert "'Inlet[2].value'" in messages(bag) and "'Sensor[2].value'" in messages(bag)


def test_a_baseline_whose_identities_collide_drops_no_object(tree):
    """``duplicate-id`` refuses this inside a project, but a baseline is read back rather than
    re-checked, so an archive written with that check relaxed - or edited by hand - can carry a
    collision anyway.

    Indexed naively the later entry wins: ``B`` would pair with the candidate's ``A`` and be
    reported as a rename, and ``A`` - present in both deliveries - would fall through to a
    removal. Two wrong findings about objects that did not move, caused by a defect in the file
    the baseline was read from. Excluding the collided identity leaves both entries to pair on
    their names, and only ``B``, which really is gone, is reported.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "A", id="k7m2q9xr4t8w"),
        declare("local", "B", id="k7m2q9xr4t8w"),
    )
    after = one_component(tree, "after", declare("local", "A", id="k7m2q9xr4t8w"))
    bag = verdict(before, after)
    assert checks(bag) == ["removed-unused-object"], messages(bag)
    assert "'B' is gone" in messages(bag)


def test_a_mixed_regime_pairs_each_object_by_what_it_carries(tree):
    """The half-migrated delivery, which is what most of a migration actually looks like.

    One object has adopted an id and its neighbour has not. The first pairs on its identity and
    reports the rename; the second pairs by name exactly as it did before ids existed, and
    reports its own change. Neither regime disturbs the other.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "FiltGain", id="k7m2q9xr4t8w"),
        declare("local", "Untouched", "uint8"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "FilterGain", id="k7m2q9xr4t8w"),
        declare("local", "Untouched", "uint16"),
    )
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object", "changed-interface"], messages(bag)


def test_two_instances_sharing_a_name_under_different_ids_are_not_paired(tree):
    """The same-name-different-id refusal reaches a leaf as it does a plain object.

    ``Inlet`` names a different variable in the two deliveries, so its members are not the same
    places either. The pairing refuses them rather than comparing one against the other, and
    ``reused-name`` says why the spelling no longer means what a dataset thinks it means.
    """
    cell_type = {
        "types": [
            {
                "type": "struct",
                "name": "Cell_t",
                "members": [
                    {
                        "name": "value",
                        "member": "value",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                    }
                ],
            }
        ]
    }
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "t.ddd.json", "before-a.ddd.json"),
            "after.ddd.json": project("P", "t.ddd.json", "after-a.ddd.json"),
            "t.ddd.json": cell_type,
            "before-a.ddd.json": component(
                "A", declare("local", "Inlet", typename="Cell_t", id="k7m2q9xr4t8w")
            ),
            "after-a.ddd.json": component(
                "A", declare("local", "Inlet", typename="Cell_t", id="p3rt5vwx9z2q")
            ),
        },
    )
    bag = verdict(resolve(tree, "before.ddd.json"), resolve(tree, "after.ddd.json"))
    assert checks(bag) == ["reused-name", "removed-unused-object", "added-object"], messages(bag)
    assert "'Inlet.value'" in messages(bag)


def test_an_identical_removal_and_addition_suggest_a_lost_identity(tree):
    """Nothing in one version can see a hand-edited id; this is the only net under it."""
    before = one_component(tree, "before", declare("local", "FiltGain"))
    after = one_component(tree, "after", declare("local", "FilterGain"))
    bag = verdict(before, after)
    assert "removed-unused-object" in checks(bag), messages(bag)
    assert "the id did not travel with it" in messages(bag)


def test_no_such_note_when_the_two_differ(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", "uint8"))
    after = one_component(tree, "after", declare("local", "FilterGain", "uint16"))
    assert "did not travel" not in messages(verdict(before, after))


def test_two_equally_identical_additions_name_neither(tree):
    """Naming either candidate would be a guess dressed as a suggestion, so the note stays
    silent once more than one addition matches equally well - the ``len(same) != 1`` guard
    is the point of the note, not an accident of its implementation.
    """
    before = one_component(tree, "before", declare("local", "FiltGain"))
    after = one_component(
        tree,
        "after",
        declare("local", "FilterGainA"),
        declare("local", "FilterGainB"),
    )
    bag = verdict(before, after)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "removed-unused-object"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes == (), messages(bag)


def test_a_curve_over_a_different_axis_is_not_offered_as_a_lost_identity(tree):
    """Ruling 1: once ``references`` left the interface table, the note's own filter has to
    look at referents by hand - otherwise a curve over axis A and one over axis B, alike in
    every field the table still checks, would be offered as the same curve under a new name.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "Ax", "uint16", kind="axis", size=3),
        declare("local", "Ay", "uint16", kind="axis", size=3),
        declare("local", "C", "uint8", kind="curve", axis="Ax"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "Ax", "uint16", kind="axis", size=3),
        declare("local", "Ay", "uint16", kind="axis", size=3),
        declare("local", "D", "uint8", kind="curve", axis="Ay"),
    )
    bag = verdict(before, after)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "removed-unused-object"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes == (), messages(bag)


def test_the_note_still_fires_when_the_shared_axis_was_only_renamed(tree):
    """Ruling 1's refinement: referents are compared through ``_compare_references``, which
    resolves an identity before falling back to a name. A curve that follows its axis through
    a rename is still offered as a possible lost identity of its own - which a raw comparison
    of the written reference names would have missed, since 'Ax' and 'Bx' do not read equal.
    """
    before = one_component(
        tree,
        "before",
        declare("local", "Ax", "uint16", kind="axis", size=3, id="k7m2q9xr4t8w"),
        declare("local", "C", "uint8", kind="curve", axis="Ax"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "Bx", "uint16", kind="axis", size=3, id="k7m2q9xr4t8w"),
        declare("local", "D", "uint8", kind="curve", axis="Bx"),
    )
    bag = verdict(before, after)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "removed-unused-object"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes, "the note names the identical addition"
    note_text, _ = findings[0].notes[0]
    assert note_text == (
        "'D' was added with an identical interface; if that was a rename, "
        "the id did not travel with it"
    )


def test_a_shared_name_under_different_ids_gets_no_lost_identity_note(tree):
    """Ruling 3's pairing skip is the only way an unpaired removal and an unpaired addition
    still share a name: both sides already agree on what the name is, so there is no rename
    to hypothesise. `reused-name` already says exactly what happened here, at the highest
    severity this feature produces - the note must not contradict it right beside it.
    """
    before = one_component(tree, "before", declare("local", "A", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "A", id="p3rt5vwx9z2q"))
    bag = verdict(before, after)
    assert set(checks(bag)) == {
        "reused-name",
        "removed-unused-object",
        "added-object",
    }, messages(bag)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "removed-unused-object"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes == (), messages(bag)


def test_a_storage_only_difference_is_not_offered_as_a_lost_identity(tree):
    """Isolates the guard's storage clause: interface and referents agree (there are none),
    only a storage field differs, so this must not be offered as a possible rename either.
    """
    before = one_component(tree, "before", declare("local", "FiltGain", init=1))
    after = one_component(tree, "after", declare("local", "FilterGain", init=2))
    bag = verdict(before, after)
    findings = [diagnostic for diagnostic in bag if diagnostic.check == "removed-unused-object"]
    assert len(findings) == 1, messages(bag)
    assert findings[0].notes == (), messages(bag)


def test_the_renames_file_lists_the_pairs_a_dataset_needs(tree, tmp_path):
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component("A", declare("local", "FiltGain", id="k7m2q9xr4t8w")),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component("A", declare("local", "FilterGain", id="k7m2q9xr4t8w")),
        },
    )
    out = tmp_path / "renames.json"
    main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"id": "k7m2q9xr4t8w", "from": "FiltGain", "to": "FilterGain"}
    ]


def test_a_comparison_with_no_renames_writes_an_empty_list(tree, tmp_path):
    """So a build step can tell 'no renames' from 'compare never ran'."""
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
        },
    )
    out = tmp_path / "renames.json"
    main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    assert json.loads(out.read_text(encoding="utf-8")) == []


def test_the_renames_file_is_sorted_by_the_new_name(tree, tmp_path):
    """Neither test above can tell a sort by ``to`` from no sort at all: one has a single
    entry and the other has none, so either order - or none - reads the same. Pairing is
    itself ordered by the *old* name, so two renames whose old and new names fall in opposite
    orders are what it takes to tell the two apart.
    """
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component(
                "A",
                declare("local", "Zeta", id="k7m2q9xr4t8w"),
                declare("local", "Beta", id="p3rt5vwx9z2q"),
            ),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component(
                "A",
                declare("local", "Alpha", id="k7m2q9xr4t8w"),
                declare("local", "Omega", id="p3rt5vwx9z2q"),
            ),
        },
    )
    out = tmp_path / "renames.json"
    main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    # By old name this would be Beta->Omega then Zeta->Alpha; sorted by new name it is the
    # other way round.
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"id": "k7m2q9xr4t8w", "from": "Zeta", "to": "Alpha"},
        {"id": "p3rt5vwx9z2q", "from": "Beta", "to": "Omega"},
    ]


def test_a_failing_comparison_still_writes_the_renames_file(tree, tmp_path):
    """None of the tests above ever fail the comparison, so a write silently skipped whenever
    ``bag.has_errors`` would pass every one of them. A delivery that cannot be accepted still
    needs its renames listed, so this pairs the rename with a breaking datatype change and
    checks both: the run reports failure, and the file is there anyway.
    """
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component(
                "A", declare("local", "FiltGain", "uint8", id="k7m2q9xr4t8w")
            ),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component(
                "A", declare("local", "FilterGain", "uint16", id="k7m2q9xr4t8w")
            ),
        },
    )
    out = tmp_path / "renames.json"
    exit_code = main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    assert exit_code == EXIT_FINDINGS
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"id": "k7m2q9xr4t8w", "from": "FiltGain", "to": "FilterGain"}
    ]


def test_a_dumped_baseline_survives_a_rename_end_to_end(tree, capsys):
    """Every other identity test builds its dictionaries in memory through ``resolve()``; none
    of them go through the path a project actually runs in production: ``ddd dump`` to a real
    file, archived, and ``ddd compare`` reading it back through
    :func:`ddd.loading.load_dictionary` rather than the project loader, against a candidate
    resolved fresh from a later working tree.

    It is also the shape that reproduces Finding 1: the curve's own rename is tracked by a
    stable id carried on both sides, but the axis it points at has only just adopted one, so
    the reference field is the unchanged spelling ``'A'`` on both sides while what it resolves
    to is a bare name on one and an id on the other - a ``changed-interface`` on the curve
    under the old, per-side fallback, and nothing under the fix.
    """
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component(
                "A",
                declare("local", "A", kind="axis", size=8),
                declare("local", "Curve", kind="curve", axis="A", id="p3rt5vwx9z2q"),
            ),
        },
    )
    baseline = tree / "baseline.json"
    assert main(["dump", str(tree / "before.ddd.json")]) == EXIT_OK
    baseline.write_text(capsys.readouterr().out, encoding="utf-8")
    assert json.loads(baseline.read_text(encoding="utf-8"))["format"] == 6

    write_tree(
        tree,
        {
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component(
                "A",
                declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
                declare("local", "CurveX", kind="curve", axis="A", id="p3rt5vwx9z2q"),
            ),
        },
    )
    exit_code = main(["compare", str(baseline), str(tree / "after.ddd.json")])
    err = capsys.readouterr().err
    assert exit_code == EXIT_OK, err
    assert "renamed-object" in err and "'Curve'" in err and "'CurveX'" in err
    assert "changed-interface" not in err
