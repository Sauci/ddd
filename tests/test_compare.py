"""Tests for comparing two deliveries: can the candidate replace the baseline?"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

from conftest import DEMO, checks, component, declare, messages, project, write_tree
from ddd.analysis import analyze
from ddd.cli import EXIT_FINDINGS, EXIT_OK, _build_parser, main
from ddd.compare import _MOST_CANDIDATES, compare
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.ir import DataDictionary, ResolvedObject
from ddd.loading import load_workspace
from ddd.models import Datatype, IdentityConversion, Limits, ObjectKind


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


def ruling(base: Path, capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str]:
    """Run ``ddd compare`` over the two deliveries ``one_component`` writes as ``old``/``new``.

    What a comparison is *for* is the verdict line and the exit code, and a check that only
    counts the findings cannot see either: a delivery whose findings are all warnings is a
    replacement, and the same run under ``--strict`` is not. The tests of this file that
    decide whether one delivery can stand in for another therefore go through the command.
    """
    capsys.readouterr()
    code = main(["compare", str(base / "old.ddd.json"), str(base / "new.ddd.json"), *arguments])
    return code, capsys.readouterr().err


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
        ("was", "now", "spelled"),
        [
            # A reordering moves every enumerator of the generated typedef.
            (
                [("M_OFF", 0, ""), ("M_ON", 1, "")],
                [("M_ON", 1, ""), ("M_OFF", 0, "")],
                "enum(Mode_t: M_ON=1, M_OFF=0) != enum(Mode_t: M_OFF=0, M_ON=1)",
            ),
            # A revalued enumerator falsifies every archived reading of the state.
            (
                [("M_OFF", 0, "")],
                [("M_OFF", 1, "")],
                "enum(Mode_t: M_OFF=1) != enum(Mode_t: M_OFF=0)",
            ),
        ],
    )
    def test_enumerator_order_and_values_still_break(
        self,
        tree: Path,
        was: list[tuple[str, int, str]],
        now: list[tuple[str, int, str]],
        spelled: str,
    ) -> None:
        """The finding spells the enumerators out: a delivery comparison has no
        ``enum-conflict`` to leave them to, and ``enum(Mode_t) != enum(Mode_t)`` said nothing."""
        old = one_component(tree, "old", declare("local", "X", "uint8", conversion=self.enum(*was)))
        new = one_component(tree, "new", declare("local", "X", "uint8", conversion=self.enum(*now)))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert f"conversion: {spelled}" in messages(bag)

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
        old = one_component(
            tree,
            "old",
            declare("local", "In", "uint16"),
            declare("local", "Ax", "uint16", kind="axis", size=3),
        )
        new = one_component(
            tree,
            "new",
            declare("local", "In", "uint16"),
            declare("local", "Ax", "uint16", kind="axis", size=3, input="In"),
        )
        assert "references: input=In != none" in messages(verdict(old, new))

    def test_a_kind_change_is_breaking(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", "uint16"))
        new = one_component(tree, "new", declare("local", "X", "uint16", kind="parameter"))
        assert "changed-interface" in checks(verdict(old, new))

    def test_bytes_becoming_text_is_breaking(self, tree: Path) -> None:
        """A consumer reading numbers is handed characters: a changed conversion, as written."""
        old = one_component(
            tree,
            "old",
            declare("local", "Label", "uint8", kind="value_block", dimensions=[16], conversion={}),
        )
        new = one_component(
            tree,
            "new",
            declare(
                "local",
                "Label",
                "uint8",
                kind="value_block",
                dimensions=[16],
                conversion={"kind": "string"},
            ),
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "conversion: string != identity" in messages(bag)
        assert bag.has_errors

    def test_two_deliveries_of_one_string_compare_clean(self, tree: Path) -> None:
        string = declare(
            "local",
            "Label",
            "uint8",
            kind="value_block",
            dimensions=[16],
            conversion={"kind": "string"},
            init="V1.2",
        )
        assert (
            checks(verdict(one_component(tree, "old", string), one_component(tree, "new", string)))
            == []
        )


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

    def test_gaining_an_initial_value_is_a_warning(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X"))
        new = one_component(tree, "new", declare("local", "X", init=1))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"]
        assert "init: 1 != none" in messages(bag)

    def test_a_changed_string_initial_value_is_a_warning(self, tree: Path) -> None:
        """A string init is spelled the way the file spells it, not as ``repr`` would."""
        string_block = {
            "datatype": "uint8",
            "kind": "value_block",
            "dimensions": [16],
            "conversion": {"kind": "string"},
        }
        old = one_component(tree, "old", declare("local", "X", init="V1.2", **string_block))
        new = one_component(tree, "new", declare("local", "X", init="V1.3", **string_block))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"]
        assert 'init: "V1.3" != "V1.2"' in messages(bag)

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


class TestAStructuredVariableIsComparedAsAVariable:
    """A structured variable used to be compared only through its members.

    ``DataDictionary.comparable`` offers the plain objects and the leaves and never the
    instances, and two things fell between the two. What no member carries at all - the
    ``type``: renaming ``Sensor_t`` to ``Sensor2_t`` with the members untouched changes what
    every consumer's header declares and left every leaf identical to the byte, so the
    comparison said nothing whatsoever. And what every member carries only because the
    variable does - ``volatile``, ``section``, ``raster``, the producer, the condition: one
    flip of the variable's ``volatile`` was one ``changed-storage`` per member.
    """

    MEMBERS: ClassVar[tuple[str, ...]] = ("count", "flags", "value")

    def delivery(
        self,
        tree: Path,
        name: str,
        *,
        type_name: str = "Sensor_t",
        owner: str = "A",
        constants: str | None = None,
        **declaration: Any,
    ) -> DataDictionary:
        members = [
            {
                "name": member,
                "member": "value",
                "datatype": "uint8",
                "conversion": {"kind": "identity"},
            }
            for member in self.MEMBERS
        ]
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P",
                    *([constants] if constants else []),
                    f"{name}-t.ddd.json",
                    f"{name}-s.ddd.json",
                    f"{name}-r.ddd.json",
                    f"{name}-a.ddd.json",
                ),
                f"{name}-t.ddd.json": {
                    "types": [{"type": "struct", "name": type_name, "members": members}]
                },
                f"{name}-s.ddd.json": {
                    "sections": [{"section": ".fast", "access": "read-write", "alignment": 4}]
                },
                f"{name}-r.ddd.json": {
                    "rasters": [{"raster": "10ms", "event": 0, "cycle": "10ms"}]
                },
                f"{name}-a.ddd.json": component(
                    owner, declare("local", "Inlet", typename=type_name, **declaration)
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def test_a_type_renamed_with_identical_members_is_a_changed_interface(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", type_name="Sensor_t")
        new = self.delivery(tree, "new", type_name="Sensor2_t")
        assert [leaf.path for leaf in old.leaves] == ["Inlet.count", "Inlet.flags", "Inlet.value"]
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "'Inlet' is not the same object any more (type: 'Sensor2_t' != 'Sensor_t')" in (
            messages(bag)
        )
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    @pytest.mark.parametrize(
        ("changed", "check", "spelled"),
        [
            ({"volatile": True}, "changed-storage", "'Inlet': volatile: true != false"),
            ({"section": ".fast"}, "changed-storage", "'Inlet': section: .fast != none"),
            ({"raster": "10ms"}, "changed-storage", "'Inlet': raster: 10ms != none"),
            (
                {"condition": "defined(FAST)"},
                "changed-condition",
                "'Inlet': condition none became 'defined(FAST)'",
            ),
            ({"dimensions": [2]}, "changed-interface", "'Inlet' is not the same object any more"),
        ],
    )
    def test_a_change_to_the_variable_is_reported_once_and_not_once_per_member(
        self,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
        changed: dict[str, Any],
        check: str,
        spelled: str,
    ) -> None:
        """Three members, and one edit on the declaration above them: one finding."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", **changed)
        bag = verdict(old, new)
        assert len(self.MEMBERS) == 3
        assert [entry for entry in checks(bag) if entry == check] == [check]
        assert spelled in messages(bag)
        for member in self.MEMBERS:
            assert f"'Inlet.{member}': {check.removeprefix('changed-')}" not in messages(bag)
        # Graded as the same change on a plain object is: only a changed interface refuses.
        breaking = check == "changed-interface"
        code, report = ruling(tree, capsys)
        assert code == (EXIT_FINDINGS if breaking else EXIT_OK), report
        assert ("cannot replace" if breaking else "can replace") in report

    def test_a_variable_produced_by_another_component_is_reported_once(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", owner="A")
        new = self.delivery(tree, "new", owner="B")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-owner"]
        assert "'Inlet' is now produced by B instead of A" in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_OK, report
        assert "can replace" in report

    def test_a_member_of_its_own_is_still_reported_at_the_member(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """What the variable now answers for is taken off the leaves and nothing else is."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new")
        wider = new.leaves[0].model_copy(update={"datatype": old.leaves[0].datatype.SINT16})
        bag = verdict(old, new.model_copy(update={"leaves": (wider, *new.leaves[1:])}))
        assert checks(bag) == ["changed-interface"]
        assert "'Inlet.count' is not the same object any more (datatype: sint16 != uint8)" in (
            messages(bag)
        )

    def archived(self, dictionary: DataDictionary) -> DataDictionary:
        """The dictionary as a format 3 dump carried it: no dimension spellings anywhere."""
        stripped = json.loads(dictionary.model_dump_json())
        stripped["format"] = 3
        for group in ("objects", "instances", "leaves"):
            for entry in stripped[group]:
                del entry["dimensions"]
        return DataDictionary.model_validate(stripped)

    def test_an_older_baseline_compares_the_array_dimension_by_value(self, tree: Path) -> None:
        """An array of structures defers exactly as an array of plain objects does.

        A format 3 dump recorded no spellings at all, so against one only the values can
        disagree: adopting a declared constant for an array of two structures whose size
        stands is a clean migration, not a changed interface.
        """
        old = self.delivery(tree, "old", dimensions=[2])
        write_tree(tree, {"new-c.ddd.json": {"constants": [{"name": "N", "value": 2}]}})
        new = self.delivery(tree, "new", dimensions=["N"], constants="new-c.ddd.json")
        assert new.instances[0].spelled_shape == ("N",)
        assert checks(verdict(self.archived(old), new)) == []

    def test_a_resized_array_against_an_older_baseline_still_reports(self, tree: Path) -> None:
        """The deference is about the spelling only; another size is a changed interface."""
        old = self.delivery(tree, "old", dimensions=[2])
        write_tree(tree, {"new-c.ddd.json": {"constants": [{"name": "N", "value": 3}]}})
        new = self.delivery(tree, "new", dimensions=["N"], constants="new-c.ddd.json")
        bag = verdict(self.archived(old), new)
        assert "changed-interface" in checks(bag)
        assert "'Inlet' is not the same object any more (shape: [N] != [2])" in messages(bag)

    def test_two_identical_deliveries_of_a_structured_variable_compare_clean(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", volatile=True, section=".fast", raster="10ms")
        new = self.delivery(tree, "new", volatile=True, section=".fast", raster="10ms")
        assert checks(verdict(old, new)) == []
        code, report = ruling(tree, capsys)
        assert code == EXIT_OK, report
        assert "can replace" in report


class TestTheLayoutOfAStructureIsInterface:
    """A structure's layout is part of what its consumers compiled against.

    Two edits move every address after them and left no trace at all in the report. A member
    whose bit width changed carries the new width on its leaf, and ``bits`` was in neither
    comparison table - narrowing one from four to two was reported as nothing worse than
    tightened limits, widening it as nothing at all. And a reordering touches no leaf
    whatsoever: same paths, same datatypes, same conversions, same limits, so the members
    themselves compare clean however far they have moved. The ``Member`` docstring published
    in ``ddd_types.schema.json`` and ``ddd_component.schema.json`` has always said a
    comparison against a baseline reports the reordering.
    """

    def member(self, name: str, **extra: Any) -> dict[str, Any]:
        return {
            "name": name,
            "member": "bits" if "bits" in extra else "value",
            "datatype": "uint16",
            "conversion": {"kind": "identity"},
            **extra,
        }

    def delivery(self, tree: Path, name: str, *members: dict[str, Any]) -> DataDictionary:
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project("P", f"{name}-t.ddd.json", f"{name}-a.ddd.json"),
                f"{name}-t.ddd.json": {
                    "types": [{"type": "struct", "name": "S_t", "members": list(members)}]
                },
                f"{name}-a.ddd.json": component("A", declare("local", "Inst", typename="S_t")),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    @pytest.mark.parametrize(
        ("was", "now", "spelled"),
        [
            # Widening moves every member after it, and was silent: the derived limits of a
            # wider field only grow, and growing limits are deliberately not reported.
            (2, 4, "bits: 4 != 2"),
            # Narrowing changes the value every reader gets out of the word, and was reported
            # as tightened limits alone - the layout change itself unmentioned.
            (4, 2, "bits: 2 != 4"),
        ],
    )
    def test_a_bitfield_of_another_width_is_a_changed_interface(
        self,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
        was: int,
        now: int,
        spelled: str,
    ) -> None:
        old = self.delivery(tree, "old", self.member("a"), self.member("f", bits=was))
        new = self.delivery(tree, "new", self.member("a"), self.member("f", bits=now))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert spelled in messages(bag)
        assert "'Inst.f'" in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_two_members_swapped_are_reported_once_at_the_structure(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Nothing about either leaf changed, and every offset of every variable moved."""
        first, second = self.member("a", datatype="uint8"), self.member("b")
        old = self.delivery(tree, "old", first, second)
        new = self.delivery(tree, "new", second, first)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "'S_t' is not the same structure any more (members: b, a != a, b)" in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_a_member_appended_is_an_addition_and_not_a_reordering(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The members that stayed are where they were, so there is one thing to say."""
        old = self.delivery(tree, "old", self.member("a"))
        new = self.delivery(tree, "new", self.member("a"), self.member("b"))
        bag = verdict(old, new)
        assert checks(bag) == ["added-object"]
        assert "'Inst.b' is new" in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_OK, report
        assert "can replace" in report

    def test_an_identical_structure_compares_clean(self, tree: Path) -> None:
        members = (self.member("a", datatype="uint8"), self.member("f", bits=3))
        old = self.delivery(tree, "old", *members)
        new = self.delivery(tree, "new", *members)
        assert checks(verdict(old, new)) == []


class TestDerivedLimitsCarryTheAnalysisTolerance:
    """A limit nobody wrote is computed, and computing it goes through a float.

    ``sint16`` under ``{"factor": 0.1}`` implies [-3276.8, 3276.7], and the binary arithmetic
    that derives the upper end used to write it out as ``3276.7000000000003``. Rounding it
    where it is derived is not enough on its own: every dictionary archived before that
    rounding still carries the unrounded number, and a candidate that makes the implicit
    limits explicit - or adopts a scalar type that states them - was then narrowing the range
    by 3e-13. That is a ``narrowed-limits`` warning and, under the ``--strict`` gate the
    comparison page recommends, "cannot replace" and exit 1 over nothing at all.

    The analysis has weighed a derived limit with a relative tolerance since it was written;
    the comparison now weighs one with the same one, so the check that reports an impossible
    limit and the check that reports a narrowed one cannot disagree about which two numbers
    are the same number.
    """

    SCALED: ClassVar[dict[str, float]] = {"factor": 0.1}

    def archived(self, tree: Path, dictionary: DataDictionary, **ends: float) -> Path:
        """The baseline as an older DDD dumped it: the derived limits, unrounded."""
        entry = dictionary.objects[0].model_copy(update={"limits": Limits(**ends)})
        path = tree / "baseline.json"
        older = dictionary.model_copy(update={"objects": (entry,)})
        path.write_text(older.model_dump_json(indent=2), encoding="utf-8")
        return path

    def against(
        self, tree: Path, capsys: pytest.CaptureFixture[str], baseline: Path
    ) -> tuple[int, str]:
        capsys.readouterr()
        code = main(["compare", str(baseline), str(tree / "new.ddd.json"), "--strict"])
        return code, capsys.readouterr().err

    @pytest.mark.parametrize(
        ("conversion", "implied", "unrounded"),
        [
            # The upper end, where 32767 counts of 0.1 overshoot the range they cover.
            ({"factor": 0.1}, {"min": -3276.8, "max": 3276.7}, 3276.7000000000003),
            # The lower one, which the same arithmetic overshoots as soon as an offset moves
            # the raw zero: -32768 counts of 0.1 plus 0.1 is -3276.7000000000003.
            (
                {"factor": 0.1, "offset": 0.1},
                {"min": -3276.7, "max": 3276.8},
                -3276.7000000000003,
            ),
        ],
    )
    def test_a_candidate_stating_the_limits_its_datatype_implies_compares_clean(
        self,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
        conversion: dict[str, float],
        implied: dict[str, float],
        unrounded: float,
    ) -> None:
        scaled = {"conversion": conversion}
        old = one_component(tree, "old", declare("local", "T", "sint16", **scaled))
        assert old.by_name["T"].limits == Limits(**implied), "derived, and rounded where derived"

        end = "min" if unrounded < 0 else "max"
        baseline = self.archived(tree, old, **{**implied, end: unrounded})
        assert repr(unrounded) in baseline.read_text(encoding="utf-8"), "the archive is unrounded"

        one_component(tree, "new", declare("local", "T", "sint16", limits=implied, **scaled))
        code, report = self.against(tree, capsys, baseline)
        assert code == EXIT_OK, report
        assert "narrowed-limits" not in report
        assert "can replace" in report and "cannot replace" not in report

    def test_a_narrowing_anybody_wrote_on_purpose_is_still_reported(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The tolerance absorbs the arithmetic, not a range somebody actually tightened."""
        scaled = {"conversion": self.SCALED}
        old = one_component(tree, "old", declare("local", "T", "sint16", **scaled))
        baseline = self.archived(tree, old, min=-3276.8, max=3276.7000000000003)
        one_component(
            tree,
            "new",
            declare("local", "T", "sint16", limits={"min": -3276.8, "max": 3000}, **scaled),
        )
        code, report = self.against(tree, capsys, baseline)
        assert code == EXIT_FINDINGS
        assert "narrowed-limits" in report
        assert "cannot replace" in report


class TestAnInitComparesAsBytes:
    """An init is compared as the storage it produces, not as the way it was spelled.

    A delivery whose bytes are identical can replace the one before it, so a respelling is
    not a change: ``7`` on a ``uint8[4]`` is the array it fills, and a string's text is its
    bytes padded with zeros to the dimension, which is what c writes after the characters.
    Both respellings are ones the tool itself invites - the strings feature offers the text
    form for an array of character codes - and both used to be a ``changed-storage`` warning
    and, under the ``--strict`` gate the comparison page recommends, a "cannot replace".

    The dumped dictionary is not touched: it carries the init as the description wrote it,
    so an archive still says what was stated. Only the comparison normalises.
    """

    ARRAY: ClassVar[dict[str, Any]] = {"kind": "value_block", "dimensions": [4]}
    TEXT: ClassVar[dict[str, Any]] = {
        "kind": "value_block",
        "dimensions": [4],
        "conversion": {"kind": "string"},
    }

    def deliveries(
        self, tree: Path, before: object, after: object
    ) -> tuple[DataDictionary, DataDictionary]:
        return (
            one_component(tree, "old", declare("local", "V", "uint8", init=before, **self.ARRAY)),
            one_component(tree, "new", declare("local", "V", "uint8", init=after, **self.ARRAY)),
        )

    def text_deliveries(
        self, tree: Path, before: object, after: object
    ) -> tuple[DataDictionary, DataDictionary]:
        return (
            one_component(tree, "old", declare("local", "V", "uint8", init=before, **self.TEXT)),
            one_component(tree, "new", declare("local", "V", "uint8", init=after, **self.TEXT)),
        )

    def test_a_scalar_init_is_the_array_it_fills(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self.deliveries(tree, 7, [7, 7, 7, 7])
        assert checks(verdict(old, new)) == []
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_OK, report
        assert "can replace" in report and "cannot replace" not in report

    def test_a_scalar_init_is_the_array_it_fills_the_other_way_round(self, tree: Path) -> None:
        """The rule is symmetric, and the baseline is as likely to be the expanded side."""
        old, new = self.deliveries(tree, [7, 7, 7, 7], 7)
        assert checks(verdict(old, new)) == []

    def test_a_strings_text_is_the_bytes_it_stores(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self.text_deliveries(tree, [72, 105, 0, 0], "Hi")
        assert checks(verdict(old, new)) == []
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_OK, report
        assert "can replace" in report and "cannot replace" not in report

    def test_a_different_value_in_the_array_is_still_reported(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The normalisation must not swallow the finding it exists to stop over-reporting."""
        old, new = self.deliveries(tree, 7, [7, 7, 7, 8])
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"]
        assert "'V': init:" in messages(bag)
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_a_different_character_in_the_text_is_still_reported(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self.text_deliveries(tree, [72, 105, 0, 0], "Ho")
        assert checks(verdict(old, new)) == ["changed-storage"]
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_a_resized_array_does_not_invent_an_initial_value_change(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The array got longer and what it is filled with did not: one finding, not two.

        The shape is a changed interface and says so; a ``changed-storage`` beside it saying
        ``init: 7 != 7`` would be true of the bytes and nonsense on the page.
        """
        one_component(tree, "old", declare("local", "V", "uint8", init=7, **self.ARRAY))
        new = declare("local", "V", "uint8", init=7, kind="value_block", dimensions=[8])
        one_component(tree, "new", new)
        bag = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
        assert checks(bag) == ["changed-interface"]
        assert "shape: [8] != [4]" in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_the_dictionary_still_carries_the_init_as_it_was_written(self, tree: Path) -> None:
        """Only the comparison normalises; the archive says what the description said."""
        old, new = self.deliveries(tree, 7, [7, 7, 7, 7])
        assert old.by_name["V"].init == 7
        assert new.by_name["V"].init == (7, 7, 7, 7)


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


def test_a_name_freed_by_a_removal_and_taken_by_a_rename_is_an_error(tree, capsys):
    """The mirror of the two above, and it used to be two warnings and "can replace".

    The baseline's 'A' never adopted an id, so nothing about *it* can be proved from one; but
    'B' carries one and the candidate's 'A' carries the same one, which proves the candidate's
    'A' is the baseline's 'B' and not the 'A' that went. A calibration dataset or a recording
    keyed by 'A' binds to what the baseline called 'B' - the hazard reused-name is an error
    for - and the report said only that something was renamed and something else removed.
    """
    one_component(tree, "old", declare("local", "A"), declare("local", "B", id="k7m2q9xr4t8w"))
    one_component(tree, "new", declare("local", "A", id="k7m2q9xr4t8w"))
    bag = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
    assert checks(bag) == ["renamed-object", "reused-name", "removed-unused-object"], messages(bag)
    reused = next(diagnostic for diagnostic in bag if diagnostic.check == "reused-name")
    assert list(reused.notes) == [("the object now under it is the baseline's 'B'", None)]
    code, report = ruling(tree, capsys)
    assert code == EXIT_FINDINGS
    assert "cannot replace" in report


def test_a_swap_notes_both_halves_of_each_reuse(tree, capsys):
    """Each name is the old side of one rename and the new side of the other, so each
    finding says where the object that had the name went *and* what answers to it now."""
    one_component(
        tree,
        "old",
        declare("local", "A", id="k7m2q9xr4t8w"),
        declare("local", "B", id="p3rt5vwx9z2q"),
    )
    one_component(
        tree,
        "new",
        declare("local", "B", id="k7m2q9xr4t8w"),
        declare("local", "A", id="p3rt5vwx9z2q"),
    )
    bag = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
    reused = [diagnostic for diagnostic in bag if diagnostic.check == "reused-name"]
    assert [note for note, _ in reused[0].notes] == [
        "'A' is now called 'B'",
        "the object now under it is the baseline's 'B'",
    ]
    code, report = ruling(tree, capsys)
    assert code == EXIT_FINDINGS
    assert "cannot replace" in report


def test_a_rename_whose_old_name_nobody_claims_is_no_reuse(tree, capsys):
    """The new side of a rename only proves a reuse when the baseline used that name too."""
    one_component(tree, "old", declare("local", "A", id="k7m2q9xr4t8w"))
    one_component(tree, "new", declare("local", "B", id="k7m2q9xr4t8w"))
    bag = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
    assert checks(bag) == ["renamed-object"], messages(bag)
    code, report = ruling(tree, capsys)
    assert code == EXIT_OK, report
    assert "can replace" in report


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


class TestTheLostIdentityNoteIsBounded:
    """The note is advisory, and it used to cost more than the comparison it annotates.

    It asks of every removal which additions are identical to it, and the additions were
    grouped on ``kind``, ``datatype`` and ``unit`` alone - so a naming-convention sweep on a
    project that has no ids yet, which is exactly what ``--renames`` exists for, put every
    object in one bucket and ran the whole field comparison between every removal and every
    addition. Ten seconds at 5 300 objects, and no answer at all at 53 000.

    Two halves, and both are load bearing: the bucket now keys on everything hashable the
    note compares, so a bucket holds genuine candidates rather than everything of one
    datatype; and a bucket past a small bound is given up on, because the note names a
    candidate only when there is exactly one and a crowd of identical additions was never
    going to produce one.
    """

    def sweep(self, count: int) -> tuple[DataDictionary, DataDictionary]:
        """Two deliveries of ``count`` objects, every one of them renamed and none of them
        carrying an id - the project that has not adopted ids renaming everything at once."""

        def objects(prefix: str) -> tuple[ResolvedObject, ...]:
            return tuple(
                ResolvedObject(
                    name=f"{prefix}V{number}",
                    kind=ObjectKind.MEASUREMENT,
                    datatype=Datatype.UINT8,
                    conversion=IdentityConversion(),
                    limits=Limits(min=0, max=255),
                )
                for number in range(count)
            )

        return (
            DataDictionary(name="P", objects=objects("")),
            DataDictionary(name="P", objects=objects("x_")),
        )

    def test_a_sweep_of_five_thousand_renamed_objects_compares_in_seconds(self) -> None:
        """The measurement the finding is: 5 000 objects took about three minutes.

        The bound is generous - the comparison is a tenth of a second here - because what is
        being asserted is that the work is no longer quadratic, and a slower machine may take
        several times as long without that having changed.
        """
        baseline, candidate = self.sweep(5000)
        bag = DiagnosticBag()
        start = time.perf_counter()
        compare(baseline, candidate, bag)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"the sweep took {elapsed:.1f} s"
        assert len(list(bag)) == 10000, "every object removed and every object added"

    def test_a_removal_with_one_candidate_is_still_offered_it(self, tree: Path) -> None:
        """The note has to survive the bucketing on an object that fills every keyed field:
        an enum conversion (whose identity is not a plain value), an array shape, an init, a
        section, a raster and a reference. Keying on any of them wrongly - spelling one of
        them into the key in a form that does not compare the way the field does - would file
        the removal and its one candidate in different buckets and lose the note silently.
        """
        for delivery, name in (("before", "FiltGain"), ("after", "FilterGain")):
            write_tree(
                tree,
                {
                    f"{delivery}.ddd.json": project(
                        "P", f"{delivery}-r.ddd.json", f"{delivery}-a.ddd.json"
                    ),
                    f"{delivery}-r.ddd.json": {
                        "rasters": [{"raster": "10ms", "event": 0, "cycle": "10ms"}]
                    },
                    f"{delivery}-a.ddd.json": component(
                        "A",
                        declare("local", "Ax", "uint16", kind="axis", size=3),
                        declare(
                            "local",
                            name,
                            "uint8",
                            kind="curve",
                            axis="Ax",
                            raster="10ms",
                            init=[1, 2, 3],
                            conversion={"kind": "enum", "name": "Mode_t", "enumerators": {"A": 1}},
                        ),
                    ),
                },
            )
        bag = verdict(resolve(tree, "before.ddd.json"), resolve(tree, "after.ddd.json"))
        findings = [entry for entry in bag if entry.check == "removed-unused-object"]
        assert len(findings) == 1, messages(bag)
        assert findings[0].notes, messages(bag)
        note_text, _ = findings[0].notes[0]
        assert note_text.startswith("'FilterGain' was added with an identical interface")

    def test_a_member_is_offered_a_candidate_under_a_differently_stored_variable(
        self, tree: Path
    ) -> None:
        """A leaf is compared without the fields it only carries because its variable does,
        so the bucket it is looked up in must leave them out too. ``Outlet`` is volatile where
        ``Inlet`` was not, which is a property of the variable and nothing the member states:
        the members themselves are identical, and ``Outlet.a`` is the candidate for the lost
        identity of ``Inlet.a``.
        """
        for delivery, variable, volatile in (("before", "Inlet", False), ("after", "Outlet", True)):
            write_tree(
                tree,
                {
                    f"{delivery}.ddd.json": project(
                        "P", f"{delivery}-t.ddd.json", f"{delivery}-a.ddd.json"
                    ),
                    f"{delivery}-t.ddd.json": {
                        "types": [
                            {
                                "type": "struct",
                                "name": "S_t",
                                "members": [
                                    {
                                        "name": "a",
                                        "member": "value",
                                        "datatype": "uint8",
                                        "conversion": {"kind": "identity"},
                                    }
                                ],
                            }
                        ]
                    },
                    f"{delivery}-a.ddd.json": component(
                        "A",
                        declare("local", variable, typename="S_t", volatile=volatile),
                    ),
                },
            )
        bag = verdict(resolve(tree, "before.ddd.json"), resolve(tree, "after.ddd.json"))
        findings = [entry for entry in bag if entry.check == "removed-unused-object"]
        assert len(findings) == 1, messages(bag)
        assert findings[0].notes, messages(bag)
        note_text, _ = findings[0].notes[0]
        assert note_text.startswith("'Outlet.a' was added with an identical interface")

    def test_a_crowded_bucket_is_given_up_on(self, tree: Path) -> None:
        """What the bound buys, on the one input the key cannot separate.

        Every one of these curves agrees on every hashable field the note compares - kind,
        datatype, unit, conversion, shape, init, locality, storage and the *names* of its
        reference fields - and they are told apart only by which axis each one resolves to,
        which no key can hold. Exactly one of them would match, so without the bound the note
        would be earned at the price of the full comparison against all of them; past the
        bound the note is simply not offered.
        """
        wanted = _MOST_CANDIDATES + 1
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
            *[
                declare(
                    "local",
                    f"D{number}",
                    "uint8",
                    kind="curve",
                    axis="Ax" if number == 0 else "Ay",
                )
                for number in range(wanted)
            ],
        )
        bag = verdict(before, after)
        findings = [entry for entry in bag if entry.check == "removed-unused-object"]
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


def test_a_comparison_without_the_flag_writes_no_renames_file(tree):
    """``--renames`` is opt-in, and the parser must not quietly acquire a default for it.

    An *unconditional* write already fails loudly, since ``None.write_text`` raises and every
    other comparison in this file runs without the flag. A *defaulted* one would not: the file
    would simply appear where nobody asked for it. So the assertion is on the parser's default,
    which is where such a change would be made; the run below is here to show the comparison
    still does its work without the flag, not to prove a negative about the filesystem.
    """
    assert _build_parser().parse_args(["compare", "a.json", "b.json"]).renames is None

    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component("A", declare("local", "FiltGain", id="k7m2q9xr4t8w")),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component("A", declare("local", "FilterGain", id="k7m2q9xr4t8w")),
        },
    )
    assert main(["compare", str(tree / "before.ddd.json"), str(tree / "after.ddd.json")]) == EXIT_OK


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
    assert json.loads(baseline.read_text(encoding="utf-8"))["format"] == 8

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


class TestReportOrder:
    def test_reused_name_is_reported_above_the_removal_it_accompanies(self, tree: Path) -> None:
        """SPEC 4.1: the finding that explains the removal and the addition comes first."""
        for name, identity in (("old", "aaaaaaaaaaaa"), ("new", "bbbbbbbbbbbb")):
            write_tree(
                tree,
                {
                    f"{name}.ddd.json": project("P", f"{name}-a.ddd.json", f"{name}-b.ddd.json"),
                    f"{name}-a.ddd.json": component("A", declare("output", "Foo", id=identity)),
                    f"{name}-b.ddd.json": component("B", declare("input", "Foo")),
                },
            )
        bag = verdict(resolve(tree, "old.ddd.json"), resolve(tree, "new.ddd.json"))
        listed = [diagnostic.check for diagnostic in bag.sorted]
        assert listed.index("reused-name") < listed.index("removed-object")


class TestTheDictionaryContract:
    def test_a_spelled_dimension_has_to_agree_with_the_numeric_one(self) -> None:
        from pydantic import ValidationError

        from ddd.ir import ResolvedObject
        from ddd.models import Datatype, IdentityConversion, Limits, ObjectKind

        with pytest.raises(ValidationError, match="agree"):
            ResolvedObject(
                name="X",
                kind=ObjectKind.MEASUREMENT,
                datatype=Datatype.UINT8,
                conversion=IdentityConversion(),
                limits=Limits(min=0, max=255),
                shape=(4,),
                dimensions=(5,),
            )


class TestRenamesOfStructuredVariables:
    def test_each_member_of_a_renamed_structure_gets_an_id_of_its_own(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One id per row, or a migration tool keying on it keeps one member and drops the rest."""
        types = {
            "types": [
                {
                    "type": "struct",
                    "name": "Pair_t",
                    "members": [
                        {
                            "name": member,
                            "member": "value",
                            "datatype": "uint8",
                            "conversion": {"kind": "identity"},
                        }
                        for member in ("x", "y")
                    ],
                }
            ]
        }
        for delivery, name in (("old", "Old"), ("new", "New")):
            write_tree(
                tree,
                {
                    f"{delivery}.ddd.json": project(
                        "P", f"{delivery}-t.ddd.json", f"{delivery}-a.ddd.json"
                    ),
                    f"{delivery}-t.ddd.json": types,
                    f"{delivery}-a.ddd.json": component(
                        "A", declare("local", name, typename="Pair_t", id="abcdefghjkmn")
                    ),
                },
            )
        renamed = tree / "renames.json"
        arguments = [
            "compare",
            str(tree / "old.ddd.json"),
            str(tree / "new.ddd.json"),
            "--renames",
            str(renamed),
        ]
        main(arguments)
        rows = json.loads(renamed.read_text(encoding="utf-8"))
        assert [row["to"] for row in rows] == ["New.x", "New.y"]
        assert [row["id"] for row in rows] == ["abcdefghjkmn.x", "abcdefghjkmn.y"]
