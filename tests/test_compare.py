"""Tests for comparing two deliveries: can the candidate replace the baseline?"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

from conftest import (
    DEMO,
    checks,
    component,
    declare,
    messages,
    project,
    struct_type,
    types,
    value_member,
    write_tree,
)
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


def without_spellings(dictionary: DataDictionary) -> DataDictionary:
    """The dictionary as a format 3 dump carried it: no dimension spellings anywhere."""
    stripped = json.loads(dictionary.model_dump_json())
    stripped["format"] = 3
    for group in ("objects", "instances", "leaves"):
        for entry in stripped[group]:
            del entry["dimensions"]
    return DataDictionary.model_validate(stripped)


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
        assert "first differs" not in messages(bag), "two scalars name no index"

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

    def test_a_kind_change_is_one_finding_at_the_variable_and_none_per_member(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One edit of one declaration, and the declaration in every reader's header gains a
        ``const``."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", kind="parameter")
        assert len(self.MEMBERS) == 3
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert "'Inlet' is not the same object any more (kind: parameter != measurement)" in (
            messages(bag)
        )
        for member in self.MEMBERS:
            assert f"'Inlet.{member}'" not in messages(bag)
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS, report
        assert "cannot replace" in report

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
        assert checks(verdict(without_spellings(old), new)) == []

    def test_a_resized_array_against_an_older_baseline_still_reports(self, tree: Path) -> None:
        """The deference is about the spelling only; another size is a changed interface."""
        old = self.delivery(tree, "old", dimensions=[2])
        write_tree(tree, {"new-c.ddd.json": {"constants": [{"name": "N", "value": 3}]}})
        new = self.delivery(tree, "new", dimensions=["N"], constants="new-c.ddd.json")
        bag = verdict(without_spellings(old), new)
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

    def test_two_members_swapped_are_reported_once_at_the_variable(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Nothing about either leaf changed, and every offset of the variable moved."""
        first, second = self.member("a", datatype="uint8"), self.member("b")
        old = self.delivery(tree, "old", first, second)
        new = self.delivery(tree, "new", second, first)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "'Inst' is not the same object any more (members of S_t: b, a != a, b)" in (
            messages(bag)
        )
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


def members_named(*names: str) -> list[dict[str, Any]]:
    """A ``value`` member of each name, all of one datatype, so that only their names and their
    order tell them apart."""
    return [value_member(name) for name in names]


def rec_t(*members: dict[str, Any]) -> dict[str, Any]:
    """``Rec_t``, the structure the variable ``Rec`` of a delivery below is."""
    return struct_type("Rec_t", *members)


IN_V = struct_type("In_t", *members_named("v"))
"""A structure of one member, for nesting."""

WITH_H = rec_t(value_member("speed"), value_member("h", typename="Ha_t"), value_member("torque"))
"""``Rec_t`` with an external member between two that hold values."""

LAYOUTS_THAT_MOVED = [
    pytest.param(
        [rec_t(*members_named("a", "b"))],
        [rec_t(*members_named("a", "b", "c"))],
        [2],
        "members of Rec_t: a, b, c != a, b",
        2,
        id="the structure of an array gained a member at its end",
    ),
    pytest.param(
        [IN_V, rec_t(value_member("inner", typename="In_t"), value_member("tail"))],
        [
            struct_type("In_t", *members_named("v", "w")),
            rec_t(value_member("inner", typename="In_t"), value_member("tail")),
        ],
        None,
        "members of Rec_t.inner: v, w != v",
        1,
        id="a nested structure gained a member",
    ),
    pytest.param(
        [IN_V, rec_t(value_member("cell", typename="In_t", dimensions=[2]), value_member("tail"))],
        [IN_V, rec_t(value_member("cell", typename="In_t", dimensions=[3]), value_member("tail"))],
        None,
        "member Rec_t.cell: structure[3] != structure[2]",
        1,
        id="a nested array of structures grew",
    ),
    pytest.param(
        [
            struct_type("In_t", *members_named("v", "w")),
            rec_t(value_member("inner", typename="In_t"), value_member("tail")),
        ],
        [
            struct_type("In2_t", *members_named("w", "v")),
            rec_t(value_member("inner", typename="In2_t"), value_member("tail")),
        ],
        None,
        "members of Rec_t.inner: w, v != v, w",
        0,
        id="a nested structure renamed and its members swapped",
    ),
    pytest.param(
        [rec_t(*members_named("speed", "torque"))],
        [rec_t(*members_named("status", "speed", "torque"))],
        None,
        "members of Rec_t: status, speed, torque != speed, torque",
        1,
        id="a member inserted ahead of the others",
    ),
    pytest.param(
        [WITH_H],
        [rec_t(value_member("speed"), value_member("h", typename="Hb_t"), value_member("torque"))],
        None,
        "member Rec_t.h: Hb_t from hb.h != Ha_t from ha.h",
        0,
        id="an external member of another type",
    ),
    pytest.param(
        [WITH_H],
        [rec_t(*members_named("speed", "torque"))],
        None,
        "members of Rec_t: speed, torque != speed, h, torque",
        0,
        id="an external member removed",
    ),
    pytest.param(
        [WITH_H],
        [
            rec_t(
                value_member("speed"),
                value_member("h", typename="Ha_t", dimensions=[4]),
                value_member("torque"),
            )
        ],
        None,
        "member Rec_t.h: Ha_t[4] from ha.h != Ha_t from ha.h",
        0,
        id="an external member given a dimension",
    ),
]
"""Each structure before and after, the dimensions of the variable, where the two layouts part
as the finding spells it, and how many leaves the candidate adds."""


class TestTheLayoutOfAStructuredVariableIsInterface:
    """What a reader compiled against the baseline finds where it looks in a structured variable.

    The comparison used to line up only the members that a structure of the same name declared
    on both sides, and left everything else to the leaves: a member inserted ahead of the others
    was the addition of its leaf, an ``info``, and an external member, which contributes no leaf,
    was compared by nothing at all. Either moves every member after it. So does a structure
    nested in the variable that grew or was rearranged, a nested array of structures that grew,
    and a member added at the end of the structure of an array, which moves every element after
    the first - while every leaf still compares identical to the byte, and the delivery replaced
    its predecessor under ``--strict``.

    A structured variable now has one layout, read from the dictionary's ``types``: the members
    of its structure in order, a nested structure expanded into its own whatever it is called,
    an external member by its type's name and its dimensions, and a dimension by its spelling and
    its value. A difference is a changed interface of the variable, said once there. A member
    added after every member of the structure of a single variable moves nothing such a reader
    reads, and stays the addition of its leaves.
    """

    EXTERNAL: ClassVar[tuple[dict[str, Any], ...]] = (
        {"type": "external", "name": "Ha_t", "header": "ha.h"},
        {"type": "external", "name": "Hb_t", "header": "hb.h"},
    )

    def delivery(
        self,
        tree: Path,
        name: str,
        *structures: dict[str, Any],
        typename: str = "Rec_t",
        dimensions: list[int | str] | None = None,
        constants: dict[str, int] | None = None,
        externals: tuple[dict[str, Any], ...] | None = None,
    ) -> DataDictionary:
        """``Rec``, written by ``A`` and read by ``B``, beside these structures and constants."""
        shape = {} if dimensions is None else {"dimensions": dimensions}
        named = [] if constants is None else [f"{name}-c.ddd.json"]
        declared = [{"name": key, "value": value} for key, value in (constants or {}).items()]
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P", *named, f"{name}-t.ddd.json", f"{name}-a.ddd.json", f"{name}-b.ddd.json"
                ),
                f"{name}-c.ddd.json": {"constants": declared},
                f"{name}-t.ddd.json": types(*(externals or self.EXTERNAL), *structures),
                f"{name}-a.ddd.json": component(
                    "A", declare("output", "Rec", typename=typename, **shape)
                ),
                f"{name}-b.ddd.json": component(
                    "B", declare("input", "Rec", typename=typename, **shape)
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def against_a_dump(
        self, tree: Path, capsys: pytest.CaptureFixture[str], *arguments: str
    ) -> tuple[int, str]:
        """``ddd compare`` with the baseline archived first, the way a release keeps it."""
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json"), *arguments])
        return code, capsys.readouterr().err

    def verdicts(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> tuple[tuple[int, str], tuple[int, str]]:
        """Both sides as descriptions, and the baseline as a dump, each under ``--strict``."""
        return ruling(tree, capsys, "--strict"), self.against_a_dump(tree, capsys, "--strict")

    @pytest.mark.parametrize(
        ("before", "after", "dimensions", "spelled", "additions"), LAYOUTS_THAT_MOVED
    )
    def test_a_layout_that_moved_cannot_replace_its_predecessor(
        self,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        dimensions: list[int | str] | None,
        spelled: str,
        additions: int,
    ) -> None:
        """Each leaf the two share compares identical to the byte, and a reader of the baseline
        reads another member, or another element, than the one it was built to read."""
        old = self.delivery(tree, "old", *before, dimensions=dimensions)
        new = self.delivery(tree, "new", *after, dimensions=dimensions)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"] + ["added-object"] * additions, messages(bag)
        assert f"'Rec' is not the same object any more ({spelled}), read by B" in messages(bag)
        for code, report in self.verdicts(tree, capsys):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def test_a_member_appended_to_a_single_structure_is_its_addition_alone(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every member a reader of the baseline reads is where it was, so this alone of the
        layout's changes replaces its predecessor; under an array it moved every element after
        the first, which the first case above holds."""
        old = self.delivery(tree, "old", rec_t(*members_named("a", "b")))
        new = self.delivery(tree, "new", rec_t(*members_named("a", "b", "c")))
        bag = verdict(old, new)
        assert checks(bag) == ["added-object"], messages(bag)
        assert "'Rec.c' is new" in messages(bag)
        for code, report in self.verdicts(tree, capsys):
            assert code == EXIT_OK, report
            assert "can replace" in report and "cannot replace" not in report

    def test_a_nested_structure_renamed_with_its_layout_kept_is_no_change(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader reaches a nested structure through the member that holds it, so the name it
        has moves nothing that reader reads; the structure the variable itself names is what
        every consumer's header declares it as, and that one stays an interface."""
        held = members_named("v", "w")
        holder = rec_t(value_member("inner", typename="In_t"), value_member("tail"))
        renamed = rec_t(value_member("inner", typename="In2_t"), value_member("tail"))
        old = self.delivery(tree, "old", struct_type("In_t", *held), holder)
        new = self.delivery(tree, "new", struct_type("In2_t", *held), renamed)
        assert checks(verdict(old, new)) == []
        for code, report in self.verdicts(tree, capsys):
            assert code == EXIT_OK, report
            assert "can replace" in report and "cannot replace" not in report

    def test_the_variables_own_structure_renamed_and_rearranged_is_one_finding(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", rec_t(*members_named("a", "b")))
        new = self.delivery(
            tree, "new", struct_type("Rec2_t", *members_named("b", "a")), typename="Rec2_t"
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert (
            "'Rec' is not the same object any more (type: 'Rec2_t' != 'Rec_t', members of "
            "Rec2_t: b, a != a, b), read by B"
        ) in messages(bag)

    def test_one_edit_of_a_structure_is_said_at_each_variable_it_moved(self, tree: Path) -> None:
        """At the variable, where its readers look, and never a second time at the structure.
        The same edit moves an array of the structure and not a single one of it, so whether it
        moved anything is the variable's question."""
        for name, order in (("old", ("a", "b")), ("new", ("b", "a")), ("grown", ("a", "b", "c"))):
            write_tree(
                tree,
                {
                    f"{name}.ddd.json": project("P", f"{name}-t.ddd.json", f"{name}-a.ddd.json"),
                    f"{name}-t.ddd.json": types(struct_type("S_t", *members_named(*order))),
                    f"{name}-a.ddd.json": component(
                        "A",
                        declare("local", "Many", typename="S_t", dimensions=[2]),
                        declare("local", "Single", typename="S_t"),
                    ),
                },
            )
        old = resolve(tree, "old.ddd.json")
        bag = verdict(old, resolve(tree, "new.ddd.json"))
        assert checks(bag) == ["changed-interface"] * 2, messages(bag)
        for variable in ("Many", "Single"):
            spelled = f"'{variable}' is not the same object any more (members of S_t: b, a != a, b)"
            assert spelled in messages(bag)
        bag = verdict(old, resolve(tree, "grown.ddd.json"))
        assert checks(bag) == ["changed-interface"] + ["added-object"] * 3, messages(bag)
        assert "'Many' is not the same object any more (members of S_t: a, b, c != a, b)" in (
            messages(bag)
        )

    def test_a_structure_no_variable_declares_has_no_layout_to_compare(self, tree: Path) -> None:
        """Reordered or removed, it moved nothing anybody reads."""
        rec = rec_t(*members_named("a"))
        old = self.delivery(tree, "old", rec, struct_type("Lone_t", *members_named("x", "y")))
        reordered = self.delivery(tree, "new", rec, struct_type("Lone_t", *members_named("y", "x")))
        removed = self.delivery(tree, "gone", rec)
        assert checks(verdict(old, reordered)) == []
        assert checks(verdict(old, removed)) == []

    def test_a_nested_array_respelled_with_an_equal_size_is_a_changed_interface(
        self, tree: Path
    ) -> None:
        """The generated structure declares the member by the spelling, as it does an array
        that holds values, so a nested array's dimension compares as its spelling and its
        value, exactly as every other dimension does."""
        old = self.delivery(
            tree,
            "old",
            IN_V,
            rec_t(value_member("cell", typename="In_t", dimensions=[4]), value_member("tail")),
        )
        new = self.delivery(
            tree,
            "new",
            IN_V,
            rec_t(
                value_member("cell", typename="In_t", dimensions=["N_CELLS"]),
                value_member("tail"),
            ),
            constants={"N_CELLS": 4},
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface", "added-constant"], messages(bag)
        assert "(member Rec_t.cell: structure[N_CELLS=4] != structure[4])" in messages(bag)

    def test_a_size_changed_behind_one_spelling_is_read_at_its_value(self, tree: Path) -> None:
        cell = rec_t(value_member("cell", typename="In_t", dimensions=["N"]), value_member("tail"))
        old = self.delivery(tree, "old", IN_V, cell, constants={"N": 2})
        new = self.delivery(tree, "new", IN_V, cell, constants={"N": 3})
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"] * 2 + ["added-object"], messages(bag)
        assert "(member Rec_t.cell: structure[N=3] != structure[N=2])" in messages(bag)
        assert "constant 'N' is not the same any more (value: 3 != 2)" in messages(bag)

    def test_against_a_baseline_without_spellings_only_the_sizes_count(self, tree: Path) -> None:
        """A dictionary of format 3 or older records no spelling of a dimension, so against one
        a nested array compares by its size, as every other dimension does."""
        old = self.delivery(
            tree,
            "old",
            IN_V,
            rec_t(value_member("cell", typename="In_t", dimensions=[4]), value_member("tail")),
        )
        named = rec_t(
            value_member("cell", typename="In_t", dimensions=["N_CELLS"]), value_member("tail")
        )
        same = self.delivery(tree, "same", IN_V, named, constants={"N_CELLS": 4})
        grown = self.delivery(tree, "grown", IN_V, named, constants={"N_CELLS": 5})
        assert checks(verdict(without_spellings(old), same)) == []
        bag = verdict(without_spellings(old), grown)
        assert checks(bag) == ["changed-interface", "added-object"], messages(bag)
        assert "(member Rec_t.cell: structure[5] != structure[4])" in messages(bag)

    def test_a_member_of_another_datatype_is_told_once_at_its_leaf(self, tree: Path) -> None:
        """Widened, it moves every member after it, as a wider bitfield does; its leaf says so,
        and the variable does not say it a second time."""
        old = self.delivery(tree, "old", rec_t(value_member("a", "uint8"), value_member("b")))
        new = self.delivery(tree, "new", rec_t(value_member("a", "uint16"), value_member("b")))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert (
            "'Rec.a' is not the same object any more (datatype: uint16 != uint8), read by B"
        ) in messages(bag)

    def test_a_member_turned_from_a_value_into_an_external_type_moved_the_layout(
        self, tree: Path
    ) -> None:
        """Its leaf is gone, which is a finding of its own, and what follows it may be somewhere
        else, which no leaf says."""
        old = self.delivery(
            tree,
            "old",
            rec_t(value_member("speed"), value_member("h", "uint32"), value_member("torque")),
        )
        new = self.delivery(tree, "new", WITH_H)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface", "removed-object"], messages(bag)
        assert (
            "'Rec' is not the same object any more "
            "(member Rec_t.h: Ha_t from ha.h != value), read by B"
        ) in messages(bag)

    def test_an_external_member_whose_header_was_renamed_is_one_changed_interface(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The generated header includes the file that defines the external type, so a reader
        compiled against the baseline's headers is built against another definition. It is
        the variable's one finding, and the member's name and shape are what they were."""
        old = self.delivery(tree, "old", WITH_H)
        new = self.delivery(
            tree,
            "new",
            WITH_H,
            externals=(
                {"type": "external", "name": "Ha_t", "header": "<other.h>"},
                self.EXTERNAL[1],
            ),
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert (
            "'Rec' is not the same object any more "
            "(member Rec_t.h: Ha_t from <other.h> != Ha_t from ha.h), read by B"
        ) in messages(bag)
        for code, report in self.verdicts(tree, capsys):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def test_a_structure_the_dictionary_does_not_lay_out_holds_nothing(self, tree: Path) -> None:
        """A dump written under ``--force`` lists every structure declared, so it may hold one
        naming a type nobody declares and two that nest each other, none of which a variable can
        be; one edited by hand may leave out the very structure its variable is, on either side.
        Each is read as holding no members rather than ending the comparison in a traceback."""
        unusable = (
            struct_type("Lost_t", value_member("x", typename="Missing_t")),
            struct_type("Loop_t", value_member("y", typename="Back_t")),
            struct_type("Back_t", value_member("z", typename="Loop_t")),
        )
        rec = rec_t(*members_named("a"))
        old = self.delivery(tree, "old", rec, *unusable, dimensions=[2])
        new = self.delivery(tree, "new", rec, *unusable, dimensions=[2])
        assert {"Lost_t", "Loop_t", "Back_t"} <= {structure.name for structure in new.types}
        assert checks(verdict(old, new)) == []
        for baseline, candidate, spelled in (
            (old, new.model_copy(update={"types": ()}), "none != a"),
            (old.model_copy(update={"types": ()}), new, "a != none"),
        ):
            bag = verdict(baseline, candidate)
            assert checks(bag) == ["changed-interface"], messages(bag)
            assert (
                f"'Rec' is not the same object any more (members of Rec_t: {spelled}), read by B"
            ) in messages(bag)


class TestAStructureWithNoLeafIsComparedAsAnObjectIs:
    """A variable's removal, rename and reuse are said by its leaves, and some have none.

    A structure holding only members of external types holds nothing DDD can see into, so its
    variable reaches the a2l as no record at all and the comparison dropped what the pairing
    left over: every reader of such a variable could lose it, or find another object under its
    name, and the delivery replaced its predecessor under ``--strict``. The variable is then
    graded as an object is. One that has leaves is not said twice, and a leaf is told as it
    was.
    """

    ID: ClassVar[str] = "k7m2q9xr4t8w"
    OTHER: ClassVar[str] = "w9x8y7z6q5r4"
    EXTERNAL: ClassVar[tuple[dict[str, Any], ...]] = (
        {"type": "external", "name": "Ha_t", "header": "ha.h"},
        {"type": "external", "name": "Hb_t", "header": "hb.h"},
    )
    BUS: ClassVar[dict[str, Any]] = struct_type(
        "Bus_t", value_member("h", typename="Ha_t"), value_member("g", typename="Hb_t")
    )
    BUS_AND_A_VALUE: ClassVar[dict[str, Any]] = struct_type(
        "Bus_t",
        value_member("h", typename="Ha_t"),
        value_member("g", typename="Hb_t"),
        value_member("count"),
    )

    def delivery(
        self,
        tree: Path,
        name: str,
        *,
        variable: str | None = "I",
        reader: bool = True,
        structure: dict[str, Any] | None = None,
        **declaration: Any,
    ) -> DataDictionary:
        """``A`` writes the variable and ``B`` reads it; ``variable=None`` drops both."""
        # The identity is the producer's to state: a reader that states one is refused.
        made = [declare("output", variable, typename="Bus_t", **{"id": self.ID, **declaration})]
        read = [declare("input", variable, typename="Bus_t", **declaration)]
        made, read = (made, read) if variable else ([], [])
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", f"{name}-b.ddd.json"
                ),
                f"{name}-t.ddd.json": types(*self.EXTERNAL, structure or self.BUS),
                f"{name}-a.ddd.json": component("A", *made),
                f"{name}-b.ddd.json": component("B", *(read if reader else [])),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def archived(
        self, tree: Path, capsys: pytest.CaptureFixture[str], *arguments: str
    ) -> tuple[int, str]:
        """``ddd compare`` with the baseline archived first, the way a release keeps it."""
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json"), *arguments])
        return code, capsys.readouterr().err

    def refused(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Both ways of running the comparison refuse the candidate under ``--strict``."""
        for code, report in (
            ruling(tree, capsys, "--strict"),
            self.archived(tree, capsys, "--strict"),
        ):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def test_the_structure_has_no_leaf(self, tree: Path) -> None:
        old = self.delivery(tree, "old")
        assert old.leaves == ()
        assert [entry.name for entry in old.instances] == ["I"]

    def test_both_declarations_dropped_is_a_removal_somebody_read(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", variable=None)
        bag = verdict(old, new)
        assert checks(bag) == ["removed-object"], messages(bag)
        assert "'I' is gone, but was read by B" in messages(bag)
        self.refused(tree, capsys)

    def test_a_variable_nobody_reads_that_is_gone_is_the_warning_an_object_gets(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", reader=False)
        new = self.delivery(tree, "new", variable=None)
        bag = verdict(old, new)
        assert checks(bag) == ["removed-unused-object"], messages(bag)
        assert "'I' is gone; no component read it" in messages(bag)
        self.refused(tree, capsys)

    def test_a_rename_under_the_same_id_is_a_rename_somebody_read(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", variable="K")
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-read-object"], messages(bag)
        assert "'I' is now called 'K', read by B" in messages(bag)
        self.refused(tree, capsys)

    def test_a_rename_nobody_read_is_the_object_rename(self, tree: Path) -> None:
        old = self.delivery(tree, "old", reader=False)
        new = self.delivery(tree, "new", variable="K", reader=False)
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-object"], messages(bag)
        assert "'I' is now called 'K'; every dataset" in messages(bag)

    def test_the_migration_map_holds_the_rename(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self.delivery(tree, "old")
        self.delivery(tree, "new", variable="K")
        out = tree / "renames.json"
        ruling(tree, capsys, "--renames", str(out))
        assert json.loads(out.read_text(encoding="utf-8")) == [
            {"id": self.ID, "from": "I", "to": "K"}
        ]
        self.archived(tree, capsys, "--renames", str(out))
        assert json.loads(out.read_text(encoding="utf-8")) == [
            {"id": self.ID, "from": "I", "to": "K"}
        ]

    def test_another_id_under_the_name_is_a_reused_name(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", id=self.OTHER)
        bag = verdict(old, new)
        # As for an object: the name is now another object, so the old one is gone and the new
        # one is new, beside the finding that says why the spelling no longer means the same.
        assert sorted(checks(bag)) == ["added-object", "removed-object", "reused-name"], messages(
            bag
        )
        assert "'I' now names a different object" in messages(bag)
        assert "'I' is gone, but was read by B" in messages(bag)
        self.refused(tree, capsys)

    def test_a_kind_change_is_one_changed_interface_at_the_variable(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The declaration in every reader's header gains a ``const``, and no leaf says so."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", kind="parameter")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert (
            "'I' is not the same object any more (kind: parameter != measurement), read by B"
        ) in messages(bag)
        self.refused(tree, capsys)

    def test_a_variable_that_arrived_is_information(self, tree: Path) -> None:
        old = self.delivery(tree, "old", variable=None)
        new = self.delivery(tree, "new")
        bag = verdict(old, new)
        assert checks(bag) == ["added-object"], messages(bag)
        assert "'I' is new in P (measurement, produced by A)" in messages(bag)

    def test_an_identical_delivery_compares_clean(self, tree: Path) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new")
        assert checks(verdict(old, new)) == []

    def test_a_variable_with_a_leaf_is_not_said_a_second_time_at_the_variable(
        self, tree: Path
    ) -> None:
        """The control: a value member added, and the leaf says it all as it did."""
        old = self.delivery(tree, "old", structure=self.BUS_AND_A_VALUE)
        gone = self.delivery(tree, "new", variable=None, structure=self.BUS_AND_A_VALUE)
        bag = verdict(old, gone)
        assert checks(bag) == ["removed-object"], messages(bag)
        assert "'I.count' is gone, but was read by B" in messages(bag)
        renamed = self.delivery(tree, "new", variable="K", structure=self.BUS_AND_A_VALUE)
        bag = verdict(old, renamed)
        assert checks(bag) == ["renamed-read-object"], messages(bag)
        assert "'I.count' is now called 'K.count'" in messages(bag)
        reused = self.delivery(tree, "new", id=self.OTHER, structure=self.BUS_AND_A_VALUE)
        bag = verdict(old, reused)
        assert sorted(checks(bag)) == ["added-object", "removed-object", "reused-name"], messages(
            bag
        )
        assert "'I.count' now names" in messages(bag)
        assert "'I' " not in messages(bag).replace("'I.count'", "")
        arrived = verdict(gone, old)
        assert checks(arrived) == ["added-object"], messages(arrived)
        assert "'I.count' is new" in messages(arrived)

    def test_a_variable_that_gained_a_leaf_is_not_said_gone(self, tree: Path) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", structure=self.BUS_AND_A_VALUE)
        bag = verdict(old, new)
        assert "removed-object" not in checks(bag), messages(bag)
        assert "removed-unused-object" not in checks(bag), messages(bag)


class TestAStructureWithNoLeafReadAlone:
    """A component read alone grades a gone leafless variable as it grades an object."""

    def delivery(self, tree: Path, name: str, scope: str | None) -> DataDictionary:
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project("P", f"{name}-t.ddd.json", f"{name}-a.ddd.json"),
                f"{name}-t.ddd.json": types(
                    {"type": "external", "name": "Ha_t", "header": "ha.h"},
                    struct_type("Bus_t", value_member("h", typename="Ha_t")),
                ),
                f"{name}-a.ddd.json": component(
                    "A",
                    declare("output", "Kept"),
                    *([declare(scope, "Gone", typename="Bus_t")] if scope else []),
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    @pytest.mark.parametrize(
        ("scope", "check", "severity"),
        [
            ("output", "removed-object", "error"),
            ("local", "removed-unused-object", "warning"),
            ("input", "removed-input", "info"),
        ],
    )
    def test_each_scope_is_graded_as_it_is_for_an_object(
        self, tree: Path, scope: str, check: str, severity: str
    ) -> None:
        old = self.delivery(tree, "old", scope)
        new = self.delivery(tree, "new", None)
        assert old.leaves == ()
        bag = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, bag, baseline_alone=True)
        assert checks(bag) == [check], messages(bag)
        assert [found.severity.value for found in bag] == [severity]


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


class TestTwoDifferentInitsAreTwoDifferentInits:
    """An init is collapsed to a scalar only when every element of the whole of it is one value.

    The collapse used to run level by level, so ``[[4, 4, 4], [5, 5, 5], [6, 6, 6]]`` read as
    ``(4, 5, 6)`` and so did its transpose: two tables that generate different initialisers
    compared equal, ``--strict`` exited 0, and the index named for a real difference was
    another one. Each pair below is stored differently and each is a ``changed-storage``.
    """

    TABLE: ClassVar[list[list[int]]] = [[4, 5, 6], [4, 5, 6], [4, 5, 6]]
    LAST_ROW_CHANGED: ClassVar[list[list[int]]] = [[4, 5, 6], [4, 5, 6], [4, 5, 7]]

    EDGES: ClassVar[list[Any]] = [
        pytest.param(
            [2, 2], [[10, 10], [20, 20]], [[10, 20], [10, 20]], "[0][1]: 20 != 10", id="2x2"
        ),
        pytest.param(
            [3, 3],
            [[4, 4, 4], [5, 5, 5], [6, 6, 6]],
            [[4, 5, 6], [4, 5, 6], [4, 5, 6]],
            "[0][1]: 5 != 4",
            id="3x3",
        ),
        pytest.param(
            [2, 2, 2],
            [[[3, 3], [3, 3]], [[4, 4], [4, 4]]],
            [[[3, 4], [3, 4]], [[3, 4], [3, 4]]],
            "[0][0][1]: 4 != 3",
            id="2x2x2",
        ),
        pytest.param([3, 3], TABLE, LAST_ROW_CHANGED, "[2][2]: 7 != 6", id="the index of the part"),
        pytest.param([2, 2], 7, [[7, 7], [7, 8]], "[1][1]: 8 != 7", id="a scalar against a table"),
    ]

    def deliveries(
        self, tree: Path, datatype: str, dimensions: list[int], before: object, after: object
    ) -> tuple[DataDictionary, DataDictionary]:
        block = {"kind": "value_block", "dimensions": dimensions}
        return (
            one_component(tree, "old", declare("local", "V", datatype, init=before, **block)),
            one_component(tree, "new", declare("local", "V", datatype, init=after, **block)),
        )

    def rulings(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> list[tuple[int, str]]:
        """``--strict`` over both descriptions, and over a baseline archived as a dump."""
        both = [ruling(tree, capsys, "--strict")]
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json"), "--strict"])
        both.append((code, capsys.readouterr().err))
        return both

    @pytest.mark.parametrize(("dimensions", "before", "after", "where"), EDGES)
    def test_two_tables_that_store_differently_are_a_finding(
        self,
        tree: Path,
        capsys: pytest.CaptureFixture[str],
        dimensions: list[int],
        before: object,
        after: object,
        where: str,
    ) -> None:
        old, new = self.deliveries(tree, "uint8", dimensions, before, after)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert f"first differs at {where}" in messages(bag)
        for code, report in self.rulings(tree, capsys):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def test_a_scalar_is_still_the_long_spelling_of_itself(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        for before, after in ((7, [[7, 7], [7, 7]]), ([[7, 7], [7, 7]], 7)):
            old, new = self.deliveries(tree, "uint8", [2, 2], before, after)
            assert checks(verdict(old, new)) == []
            for code, report in self.rulings(tree, capsys):
                assert code == EXIT_OK, report

    @pytest.mark.parametrize("datatype", ["float32", "float64"])
    def test_a_negative_zero_is_not_a_zero(
        self, tree: Path, capsys: pytest.CaptureFixture[str], datatype: str
    ) -> None:
        """The sign bit is a byte of the initialiser: ``0.0F`` and ``-0.0F`` are two floats."""
        old = one_component(tree, "old", declare("local", "F", datatype, init=0.0))
        new = one_component(tree, "new", declare("local", "F", datatype, init=-0.0))
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert "'F': init: -0.0 != 0.0" in messages(bag)
        for code, report in self.rulings(tree, capsys):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def test_a_negative_zero_in_a_table_is_told_at_its_index(self, tree: Path) -> None:
        old, new = self.deliveries(
            tree, "float32", [2, 2], [[0.0, 0.0], [0.0, 0.0]], [[0.0, 0.0], [0.0, -0.0]]
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert "first differs at [1][1]: -0.0 != 0.0" in messages(bag)

    def test_a_negative_zero_against_itself_is_no_finding(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "F", "float32", init=-0.0))
        new = one_component(tree, "new", declare("local", "F", "float32", init=-0.0))
        assert checks(verdict(old, new)) == []

    def test_an_integers_minus_zero_is_zero(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """json reads ``-0`` as the integer 0: no sign survives in an integer datatype."""
        old = one_component(tree, "old", declare("local", "I", "sint16", init=0))
        text = json.dumps(component("A", declare("local", "I", "sint16", init=0)))
        (tree / "new-a.ddd.json").write_text(text.replace('"init": 0', '"init": -0'), "utf-8")
        write_tree(tree, {"new.ddd.json": project("P", "new-a.ddd.json")})
        new = resolve(tree, "new.ddd.json")
        assert '"init": -0' in (tree / "new-a.ddd.json").read_text("utf-8")
        assert checks(verdict(old, new)) == []
        for code, report in self.rulings(tree, capsys):
            assert code == EXIT_OK, report

    def test_a_literal_no_double_holds_is_refused_where_it_is_written(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``1e-400`` read as 0 before anything looked at it, so a comparison against ``0`` was
        clean and ``ddd list`` showed 0: it is refused by name instead, as NaN is."""
        one_component(tree, "old", declare("local", "F", "float64", init=0))
        text = json.dumps(component("A", declare("local", "F", "float64", init="@@")))
        (tree / "new-a.ddd.json").write_text(text.replace('"@@"', "1e-400"), "utf-8")
        write_tree(tree, {"new.ddd.json": project("P", "new-a.ddd.json")})
        code, report = ruling(tree, capsys, "--strict")
        assert code != EXIT_OK, report
        assert "1e-400" in report

    def test_the_dump_of_a_zero_is_what_it_stores(self, tree: Path) -> None:
        """A dump holds what the loader read, so there is nothing for the literal to be."""
        old = one_component(tree, "old", declare("local", "F", "float64", init=0))
        new = one_component(tree, "new", declare("local", "F", "float64", init=0.0))
        assert checks(verdict(old, new)) == []


class TestAnInitIsSpelledForAReader:
    """``changed-storage`` used to print the whole of both inits, in python's spelling.

    A ``uint8[100000]`` block with one element changed was one warning of 600 017 characters,
    in the text report and in the json, and the reader still had to find the element that
    moved; a 16 x 16 map cost about 1.6 kB per changed table. And a list came out as a python
    tuple - ``(7, 7, 7, 8)`` - where the description file, ``ddd list`` and the hover all
    spell it ``[7, 7, 7, 8]``.
    """

    def block(self, init: tuple[object, ...]) -> DataDictionary:
        return DataDictionary(
            name="P",
            objects=(
                ResolvedObject(
                    name="Table",
                    kind=ObjectKind.VALUE_BLOCK,
                    datatype=Datatype.UINT8,
                    conversion=IdentityConversion(),
                    limits=Limits(min=0, max=255),
                    shape=(len(init),),
                    init=init,
                ),
            ),
        )

    def test_a_long_init_is_abbreviated_and_the_difference_is_named(self) -> None:
        """Abbreviating alone would be worse than saying nothing: two truncated heads that
        read identical, on a finding whose whole content is that they differ. The index the
        two part at is what makes the short spelling safe to print.
        """
        changed = [7] * 100000
        changed[51234] = 8
        bag = verdict(self.block((7,) * 100000), self.block(tuple(changed)))
        assert checks(bag) == ["changed-storage"], messages(bag)
        spelled = messages(bag)
        assert len(spelled) < 200, f"{len(spelled)} characters"
        assert "100000 values" in spelled
        assert "first differs at [51234]: 8 != 7" in spelled

    def test_a_list_init_is_spelled_as_the_file_spells_it(self, tree: Path) -> None:
        old = one_component(
            tree, "old", declare("local", "V", "uint8", kind="value_block", dimensions=[4], init=7)
        )
        new = one_component(
            tree,
            "new",
            declare("local", "V", "uint8", kind="value_block", dimensions=[4], init=[7, 7, 7, 8]),
        )
        bag = verdict(old, new)
        assert "'V': init: [7, 7, 7, 8] != 7" in messages(bag), messages(bag)

    def test_a_nested_init_is_spelled_as_the_file_spells_it(self, tree: Path) -> None:
        old = one_component(
            tree,
            "old",
            declare(
                "local", "M", "uint8", kind="value_block", dimensions=[2, 2], init=[[1, 2], [3, 4]]
            ),
        )
        new = one_component(
            tree,
            "new",
            declare(
                "local", "M", "uint8", kind="value_block", dimensions=[2, 2], init=[[1, 2], [3, 5]]
            ),
        )
        bag = verdict(old, new)
        assert "'M': init: [[1, 2], [3, 5]] != [[1, 2], [3, 4]]" in messages(bag), messages(bag)

    def test_a_text_init_longer_than_a_finding_carries_is_abbreviated(self, tree: Path) -> None:
        """A string's init is its text, and its array is capped by the shape cap and nothing
        else, so the same warning printed whatever a description happened to write there."""
        text = {"kind": "value_block", "dimensions": [200], "conversion": {"kind": "string"}}
        old = one_component(tree, "old", declare("local", "S", "uint8", init="a" * 150, **text))
        new = one_component(tree, "new", declare("local", "S", "uint8", init="b" * 150, **text))
        bag = verdict(old, new)
        spelled = messages(bag)
        assert checks(bag) == ["changed-storage"], spelled
        assert len(spelled) < 200, f"{len(spelled)} characters"
        assert "150 characters" in spelled

    def test_the_index_is_read_off_the_bytes_whichever_side_was_abbreviated(
        self, tree: Path
    ) -> None:
        """A scalar stands for every element of the array it fills, so the two part inside
        the array and not at the top - from whichever side the scalar was written on."""
        block: dict[str, Any] = {"kind": "value_block", "dimensions": [4]}
        old = one_component(tree, "old", declare("local", "V", "uint8", init=[7, 7, 7, 8], **block))
        new = one_component(tree, "new", declare("local", "V", "uint8", init=7, **block))
        assert "first differs at [3]: 7 != 8" in messages(verdict(old, new))

    def test_a_resized_array_is_not_given_an_index_it_has_no_element_at(self, tree: Path) -> None:
        """Two lists that agree as far as the shorter one goes have no first differing
        element: what differs is how many there are, and both counts are printed already."""
        old = one_component(
            tree,
            "old",
            declare("local", "V", "uint8", kind="value_block", dimensions=[3], init=[1, 2, 3]),
        )
        new = one_component(
            tree,
            "new",
            declare("local", "V", "uint8", kind="value_block", dimensions=[2], init=[1, 2]),
        )
        bag = verdict(old, new)
        assert "'V': init: [1, 2] != [1, 2, 3]" in messages(bag), messages(bag)
        assert "first differs" not in messages(bag)

    def test_a_short_init_is_still_printed_whole(self, tree: Path) -> None:
        """The abbreviation must not reach the inits a reader can simply be shown."""
        old = one_component(tree, "old", declare("local", "V", "uint8", init=1))
        new = one_component(tree, "new", declare("local", "V", "uint8", init=2))
        assert "'V': init: 2 != 1" in messages(verdict(old, new))

    def test_gaining_an_init_still_reads_against_none(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "V", "uint8"))
        new = one_component(tree, "new", declare("local", "V", "uint8", init=3))
        assert "'V': init: 3 != none" in messages(verdict(old, new))

    def test_a_boolean_init_is_spelled_as_json_spells_it(self, tree: Path) -> None:
        """``True`` is python's spelling of what every file, listing and hover writes
        ``true``, and the storage table beside it already renders ``volatile`` that way."""
        boolean: dict[str, Any] = {"datatype": "boolean", "conversion": {"kind": "identity"}}
        old = one_component(tree, "old", declare("local", "V", init=False, **boolean))
        new = one_component(tree, "new", declare("local", "V", init=True, **boolean))
        assert "'V': init: true != false" in messages(verdict(old, new))


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

    def test_the_verdict_spells_the_paths_out_when_the_two_names_coincide(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The line names files rather than projects because two deliveries of one project
        share a project name - and, kept in a directory each, they share the file name too,
        so ``pressure.ddd.json can replace pressure.ddd.json`` answered nothing at all."""
        for release in ("v1.3", "release"):
            write_tree(
                tmp_path / release,
                {
                    "p.ddd.json": project("P", "a.ddd.json"),
                    "a.ddd.json": component("A", declare("local", "X", "uint16")),
                },
            )
        old = tmp_path / "v1.3" / "p.ddd.json"
        new = tmp_path / "release" / "p.ddd.json"
        arguments = ["compare", str(old), str(new), "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_OK
        assert capsys.readouterr().err.splitlines()[-1] == (
            f"{new.as_posix()} can replace {old.as_posix()}"
        )

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
    assert sorted(checks(bag)) == [
        "renamed-object",
        "renamed-object",
        "reused-name",
        "reused-name",
    ], messages(bag)


def test_objects_without_an_identity_still_pair_by_name(tree):
    before = one_component(tree, "before", declare("local", "X"))
    after = one_component(tree, "after", declare("local", "X"))
    report = verdict(before, after)
    assert checks(report) == [], messages(report)


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
    assert sorted(checks(bag)) == ["removed-unused-object", "renamed-object", "reused-name"], (
        messages(bag)
    )
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
    report = verdict(before, after)
    assert "reused-name" in checks(report), messages(report)


def test_a_name_kept_by_the_same_object_is_not_a_reuse(tree):
    before = one_component(tree, "before", declare("local", "X", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "X", id="k7m2q9xr4t8w"))
    report = verdict(before, after)
    assert checks(report) == [], messages(report)


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
    report = verdict(before, after)
    assert "changed-interface" in checks(report), messages(report)


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
    report = verdict(before, after)
    assert checks(report) == [], messages(report)


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
    report = verdict(before, after)
    assert checks(report) == [], messages(report)


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
    assert sorted(checks(bag)) == ["changed-interface", "renamed-object"], messages(bag)


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
    assert sorted(checks(bag)) == ["added-object", "removed-unused-object", "reused-name"], (
        messages(bag)
    )
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
    assert json.loads(baseline.read_text(encoding="utf-8"))["format"] == 10

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


class TestARenamedInstanceKeepsItsComposedDisplayIdentifier:
    """A member's display identifier stands for its own segment of each leaf's path, so the
    identifier a leaf is shown under starts with the instance's own name: ``V.J.b``, or
    ``V[1].J.b`` in an array. Renaming an instance the id keeps changes that head on every
    leaf, which is the leaf's ``renamed-object`` told a second time as ``changed-a2l``, as a
    narrowing of limits is not told beside the interface change that caused it."""

    def delivery(
        self,
        tree: Path,
        name: str,
        instance: str,
        *,
        shown: str = "J",
        own: str | None = None,
        **declaration: Any,
    ) -> DataDictionary:
        own_block = {"a2l": {"display_identifier": own}} if own else {}
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project("P", "t.ddd.json", f"{name}-a.ddd.json"),
                "t.ddd.json": types(
                    struct_type(
                        "In_t",
                        {"name": "b", "member": "value", "datatype": "uint8", "conversion": {}},
                        {"name": "c", "member": "value", "datatype": "uint8", "conversion": {}},
                    ),
                    struct_type(
                        "Out_t",
                        {
                            "name": "v",
                            "member": "value",
                            "datatype": "uint8",
                            "conversion": {},
                            **own_block,
                        },
                        {
                            "name": "j",
                            "member": "value",
                            "typename": "In_t",
                            "a2l": {"display_identifier": shown},
                        },
                    ),
                ),
                f"{name}-a.ddd.json": component(
                    "A",
                    declare("local", instance, typename="Out_t", id="abcdefghjkmn", **declaration),
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def test_the_rename_alone_is_each_leafs_renamed_object_and_nothing_more(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", "V")
        new = self.delivery(tree, "new", "W")
        shown = {leaf.path: leaf.a2l.display_identifier for leaf in new.leaves}
        assert shown == {"W.v": None, "W.j.b": "W.J.b", "W.j.c": "W.J.c"}
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-object"] * 3, messages(bag)

    def test_an_element_of_an_array_of_structures_is_read_the_same_way(self, tree: Path) -> None:
        old = self.delivery(tree, "old", "V", dimensions=[2])
        new = self.delivery(tree, "new", "W", dimensions=[2])
        assert "W[1].J.b" in [leaf.a2l.display_identifier for leaf in new.leaves]
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-object"] * 6, messages(bag)

    def test_a_display_identifier_that_changed_besides_the_head_is_still_a_change(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", "V")
        new = self.delivery(tree, "new", "W", shown="K")
        bag = verdict(old, new)
        assert sorted(checks(bag)) == ["changed-a2l"] * 2 + ["renamed-object"] * 3, messages(bag)
        assert "display_identifier: 'V.J.b' -> 'W.K.b'" in messages(bag)

    def test_the_same_change_without_a_rename_is_a_change(self, tree: Path) -> None:
        old = self.delivery(tree, "old", "V")
        new = self.delivery(tree, "new", "V", shown="K")
        assert checks(verdict(old, new)) == ["changed-a2l"] * 2

    def test_a_leafs_own_identifier_carries_no_instance_name(self, tree: Path) -> None:
        """One stated on the leaf's own member is written as stated, so a rename leaves it as
        it was, and a change of it, one that merely spells the new instance's name included,
        is a change."""
        old = self.delivery(tree, "old", "V", own="V")
        same = self.delivery(tree, "same", "W", own="V")
        assert checks(verdict(old, same)) == ["renamed-object"] * 3
        spelled = self.delivery(tree, "spelled", "W", own="W")
        bag = verdict(old, spelled)
        assert sorted(checks(bag)) == ["changed-a2l"] + ["renamed-object"] * 3, messages(bag)
        assert "display_identifier: 'V' -> 'W'" in messages(bag)

    def test_a_plain_object_has_no_instance_name_to_read_at_its_head(self, tree: Path) -> None:
        old = one_component(tree, "old", declare("local", "X", a2l={"display_identifier": "Shown"}))
        same = one_component(
            tree, "same", declare("local", "X", a2l={"display_identifier": "Shown"})
        )
        other = one_component(
            tree, "other", declare("local", "X", a2l={"display_identifier": "Other"})
        )
        assert checks(verdict(old, same)) == []
        assert checks(verdict(old, other)) == ["changed-a2l"]


class TestWhatAReaderPrecompiledAgainstTheBaselineCannotAbsorb:
    """Two edits whose grade depends on whether anybody reads the object.

    A reader may be a binary compiled against the previous headers. One that never saw the
    qualifier now reaches a ``volatile`` object through a lvalue that is not, which C leaves
    undefined, and one that looks for the old spelling finds nothing. So turning ``volatile``
    on is a ``changed-interface`` and a rename is a ``renamed-read-object``, each an error,
    for an object a component reads; for one nobody reads they stay ``changed-storage`` and
    ``renamed-object``, the warnings they always were. One id carries one severity, so the
    grade that depends on readers is carried by the id the finding goes under.
    """

    ID: ClassVar[str] = "k7m2q9xr4t8w"

    def delivery(
        self,
        tree: Path,
        name: str,
        *,
        read: bool,
        variable: str = "X",
        structured: bool = False,
        **definition: Any,
    ) -> DataDictionary:
        typed: dict[str, Any] = {"typename": "Pair_t"} if structured else {}
        files: dict[str, Any] = {
            f"{name}.ddd.json": project(
                "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", f"{name}-b.ddd.json"
            ),
            f"{name}-t.ddd.json": types(
                struct_type("Pair_t", value_member("x"), value_member("y"))
            ),
            f"{name}-a.ddd.json": component(
                "A", declare("output", variable, id=self.ID, **typed, **definition)
            ),
            f"{name}-b.ddd.json": component(
                "B", *([declare("input", variable, **typed)] if read else [])
            ),
        }
        write_tree(tree, files)
        return resolve(tree, f"{name}.ddd.json")

    def test_volatile_turned_on_under_a_reader_cannot_replace(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", read=True)
        new = self.delivery(tree, "new", read=True, volatile=True)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert "'X' is not the same object any more (volatile: true != false), read by B" in (
            messages(bag)
        )
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_volatile_turned_on_that_nobody_reads_is_changed_storage(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=False)
        new = self.delivery(tree, "new", read=False, volatile=True)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert not bag.has_errors

    def test_volatile_turned_off_stays_changed_storage_under_a_reader(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=True, volatile=True)
        new = self.delivery(tree, "new", read=True)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert not bag.has_errors

    def test_the_storage_finding_keeps_what_is_left_of_storage(self, tree: Path) -> None:
        """``volatile`` is said once, in the interface finding, and the initial value that
        changed beside it stays the storage finding's."""
        old = self.delivery(tree, "old", read=True)
        new = self.delivery(tree, "new", read=True, volatile=True, init=3)
        bag = verdict(old, new)
        assert sorted(checks(bag)) == ["changed-interface", "changed-storage"], messages(bag)
        for diagnostic in bag:
            volatile = "volatile: true != false" in diagnostic.render()
            assert volatile == (diagnostic.check == "changed-interface"), messages(bag)

    def test_a_structured_variable_turned_volatile_is_one_finding_at_the_variable(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", read=True, structured=True, variable="Rec")
        new = self.delivery(tree, "new", read=True, structured=True, variable="Rec", volatile=True)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert "'Rec' is not the same object any more (volatile: true != false), read by B" in (
            messages(bag)
        )

    def test_a_structured_variable_nobody_reads_turned_volatile_is_changed_storage(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", read=False, structured=True, variable="Rec")
        new = self.delivery(tree, "new", read=False, structured=True, variable="Rec", volatile=True)
        assert checks(verdict(old, new)) == ["changed-storage"]

    def test_a_rename_under_a_reader_is_an_error_naming_the_readers(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", read=True, variable="Old")
        new = self.delivery(tree, "new", read=True, variable="New")
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-read-object"], messages(bag)
        assert "'Old' is now called 'New', read by B" in messages(bag)
        assert bag.has_errors
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report

    def test_a_rename_nobody_reads_is_a_warning(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=False, variable="Old")
        new = self.delivery(tree, "new", read=False, variable="New")
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-object"], messages(bag)
        assert not bag.has_errors

    def test_a_relaxed_renamed_object_leaves_the_rename_of_a_read_one_standing(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", read=True, variable="Old")
        new = self.delivery(tree, "new", read=True, variable="New")
        bag = verdict(old, new, "renamed-object=ignore")
        assert checks(bag) == ["renamed-read-object"], messages(bag)
        assert bag.has_errors

    def test_a_structured_variable_renamed_under_a_reader_is_each_leafs_error(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", read=True, structured=True, variable="Old")
        new = self.delivery(tree, "new", read=True, structured=True, variable="New")
        bag = verdict(old, new)
        assert checks(bag) == ["renamed-read-object"] * 2, messages(bag)
        assert "'Old.x' is now called 'New.x', read by B" in messages(bag)


class TestNarrowingAnObjectSomebodyReadsByAConditionCannotReplace:
    """Wrapping a read object in a condition takes it from every build where that is false.

    A reader compiled against the baseline looks for the object in every build, and in one
    where the condition is false it links against nothing. So narrowing an object a component
    reads - from no condition to one, or from one to another, which DDD cannot weigh and takes
    as the builds it is present in changing - is a ``narrowed-condition``, an error. A
    condition going away, and any change of one on an object nobody reads, stay the
    ``changed-condition`` warning: an id carries one severity, so the grade that depends on
    readers is carried by the id the finding goes under.
    """

    ID: ClassVar[str] = "w3n8c5hq2d6y"

    def delivery(
        self,
        tree: Path,
        name: str,
        *,
        read: bool,
        condition: str | None = None,
        variable: str = "Speed",
        structured: bool = False,
    ) -> DataDictionary:
        typed: dict[str, Any] = {"typename": "Pair_t"} if structured else {}
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", f"{name}-b.ddd.json"
                ),
                f"{name}-t.ddd.json": types(
                    struct_type("Pair_t", value_member("x"), value_member("y"))
                ),
                f"{name}-a.ddd.json": component(
                    "A",
                    declare("output", variable, condition=condition, id=self.ID, **typed),
                ),
                f"{name}-b.ddd.json": component(
                    "B",
                    *([declare("input", variable, condition=condition, **typed)] if read else []),
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def against_a_dump(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json")])
        return code, capsys.readouterr().err

    def test_a_read_object_gaining_a_condition_is_an_error_naming_the_readers(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", read=True)
        new = self.delivery(tree, "new", read=True, condition="defined(FEATURE_X)")
        bag = verdict(old, new)
        assert checks(bag) == ["narrowed-condition"], messages(bag)
        assert bag.has_errors
        text = messages(bag)
        assert "'Speed': condition none became 'defined(FEATURE_X)'" in text
        assert "read by B" in text
        assert "read by B, whose builds do not link there" in text
        code, report = ruling(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report
        code, report = self.against_a_dump(tree, capsys)
        assert code == EXIT_FINDINGS
        assert "narrowed-condition" in report
        assert "cannot replace" in report

    def test_one_condition_for_another_under_a_reader_is_an_error(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=True, condition="defined(A)")
        new = self.delivery(tree, "new", read=True, condition="defined(B)")
        bag = verdict(old, new)
        assert checks(bag) == ["narrowed-condition"], messages(bag)
        assert bag.has_errors
        assert "read by B" in messages(bag)

    def test_a_condition_going_away_under_a_reader_is_a_warning(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=True, condition="defined(A)")
        new = self.delivery(tree, "new", read=True)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-condition"], messages(bag)
        assert "now present in every build" in messages(bag)
        assert not bag.has_errors

    def test_the_same_narrowing_on_an_object_nobody_reads_is_a_warning(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=False)
        new = self.delivery(tree, "new", read=False, condition="defined(FEATURE_X)")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-condition"], messages(bag)
        assert "absent from every build" in messages(bag)
        assert not bag.has_errors

    def test_a_structured_variable_narrowed_under_a_reader_is_one_error(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=True, structured=True, variable="Rec")
        new = self.delivery(
            tree, "new", read=True, structured=True, variable="Rec", condition="defined(X)"
        )
        bag = verdict(old, new)
        assert checks(bag) == ["narrowed-condition"], messages(bag)
        assert "'Rec': condition none became 'defined(X)'" in messages(bag)
        assert "read by B" in messages(bag)

    def test_relaxing_the_warning_leaves_the_error_standing(self, tree: Path) -> None:
        old = self.delivery(tree, "old", read=True)
        new = self.delivery(tree, "new", read=True, condition="defined(FEATURE_X)")
        bag = verdict(old, new, "changed-condition=ignore")
        assert checks(bag) == ["narrowed-condition"], messages(bag)
        assert bag.has_errors


class TestLimitsAreGradedByTheDirectionDataFlows:
    """A measurement's limits are what the producer states for its readers.

    Widening one is what can break a reader - a lookup indexed by the value, a clamp sized for
    it - so on a measurement somebody reads it is ``widened-limits``, a warning, and narrowing
    it is ``narrowed-read-limits``, an information: a reader still gets values
    inside the range it was written for. Calibration data is written *into* the software, so
    it keeps its grades: narrowing is ``narrowed-limits``, widening is silent. A measurement
    nobody reads has no reader to promise anything to and keeps them as well. An id carries
    one severity, so the grade that depends on the object is carried by the id.
    """

    ID: ClassVar[str] = "m4r7k2xv9c3q"
    WIDE: ClassVar[dict[str, int]] = {"min": 0, "max": 60000}
    NARROW: ClassVar[dict[str, int]] = {"min": 0, "max": 50}
    BASE: ClassVar[dict[str, int]] = {"min": 0, "max": 100}

    def delivery(
        self,
        tree: Path,
        name: str,
        limits: dict[str, int],
        *,
        read: bool = True,
        kind: str = "measurement",
        structured: bool = False,
        datatype: str = "uint16",
        conversion: dict[str, Any] | None = None,
    ) -> DataDictionary:
        """``A`` produces ``Speed`` and ``B`` reads it, omitting the limits as the FAQ advises."""
        if structured:
            shaped: dict[str, Any] = {"typename": "Pair_t"}
            entries = types(
                struct_type("Pair_t", value_member("x", limits=limits), value_member("y"))
            )
            producer = declare("output", "Speed", id=self.ID, **shaped)
            reader = declare("input", "Speed", **shaped)
        else:
            entries = types()
            changed: dict[str, Any] = {} if conversion is None else {"conversion": conversion}
            producer = declare(
                "output", "Speed", datatype, id=self.ID, kind=kind, limits=limits, **changed
            )
            reader = declare("input", "Speed", datatype, kind=kind, **changed)
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", f"{name}-b.ddd.json"
                ),
                f"{name}-t.ddd.json": entries,
                f"{name}-a.ddd.json": component("A", producer),
                f"{name}-b.ddd.json": component("B", *([reader] if read else [])),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def against_a_dump(
        self, tree: Path, capsys: pytest.CaptureFixture[str], *arguments: str
    ) -> tuple[int, str]:
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json"), *arguments])
        return code, capsys.readouterr().err

    def test_a_read_measurement_widened_is_a_warning_that_stops_a_strict_run(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", self.BASE, structured=False)
        new = self.delivery(tree, "new", self.WIDE)
        bag = verdict(old, new)
        assert checks(bag) == ["widened-limits"], messages(bag)
        assert "'Speed': limits widened from [0, 100] to [0, 60000], read by B" in messages(bag)
        assert not bag.has_errors
        code, report = ruling(tree, capsys)
        assert code == EXIT_OK
        assert "can replace" in report
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_FINDINGS
        assert "cannot replace" in report
        code, report = self.against_a_dump(tree, capsys, "--strict")
        assert code == EXIT_FINDINGS
        assert "widened-limits" in report
        assert "cannot replace" in report

    def test_a_read_measurement_narrowed_is_an_information(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", self.BASE)
        new = self.delivery(tree, "new", self.NARROW)
        bag = verdict(old, new)
        assert checks(bag) == ["narrowed-read-limits"], messages(bag)
        assert "'Speed': limits tightened from [0, 100] to [0, 50], read by B" in messages(bag)
        code, report = ruling(tree, capsys, "--strict")
        assert code == EXIT_OK
        assert "can replace" in report
        code, report = self.against_a_dump(tree, capsys, "--strict")
        assert code == EXIT_OK
        assert "narrowed-read-limits" in report

    def test_a_parameter_keeps_its_grades_whoever_reads_it(self, tree: Path) -> None:
        old = self.delivery(tree, "old", self.BASE, kind="parameter")
        wider = self.delivery(tree, "new", self.WIDE, kind="parameter")
        assert checks(verdict(old, wider)) == []
        narrower = self.delivery(tree, "narrower", self.NARROW, kind="parameter")
        bag = verdict(old, narrower)
        assert checks(bag) == ["narrowed-limits"], messages(bag)
        assert "limits tightened from [0, 100] to [0, 50]" in messages(bag)

    def test_a_measurement_nobody_reads_keeps_its_grades(self, tree: Path) -> None:
        old = self.delivery(tree, "old", self.BASE, read=False)
        wider = self.delivery(tree, "new", self.WIDE, read=False)
        assert checks(verdict(old, wider)) == []
        narrower = self.delivery(tree, "narrower", self.NARROW, read=False)
        assert checks(verdict(old, narrower)) == ["narrowed-limits"]

    def test_a_measurement_leaf_of_a_structure_somebody_reads_takes_the_grade(
        self, tree: Path
    ) -> None:
        old = self.delivery(tree, "old", self.BASE, structured=True)
        new = self.delivery(tree, "new", self.WIDE, structured=True)
        bag = verdict(old, new)
        assert checks(bag) == ["widened-limits"], messages(bag)
        assert "widened from [0, 100] to [0, 60000]" in messages(bag)
        narrower = self.delivery(tree, "narrower", self.NARROW, structured=True)
        assert checks(verdict(old, narrower)) == ["narrowed-read-limits"]

    def test_a_widening_beside_a_changed_interface_is_said_once(self, tree: Path) -> None:
        old = self.delivery(tree, "old", self.BASE, datatype="uint16")
        new = self.delivery(tree, "new", self.WIDE, datatype="uint32")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)

    def test_a_narrowing_beside_a_changed_interface_is_said_once(self, tree: Path) -> None:
        old = self.delivery(tree, "old", self.BASE, datatype="uint16")
        new = self.delivery(tree, "new", self.NARROW, datatype="uint32")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)

    def test_a_derived_end_archived_with_float_noise_is_no_change(self, tree: Path) -> None:
        old = self.delivery(tree, "old", {"min": 0, "max": 3276.7000000000003})
        new = self.delivery(tree, "new", {"min": 0, "max": 3276.7})
        assert checks(verdict(old, new)) == []
        assert checks(verdict(new, old)) == []

    def test_a_range_moved_both_ways_is_a_widening(self, tree: Path) -> None:
        """One end out and the other in: a reader can meet a value it was not sized for."""
        old = self.delivery(tree, "old", {"min": 10, "max": 100})
        new = self.delivery(tree, "new", {"min": 0, "max": 50})
        bag = verdict(old, new)
        assert checks(bag) == ["widened-limits"], messages(bag)


class TestAComponentFileReadAloneIsGradedByWhatOneFileCanKnow:
    """A supplier's gate compares one component with its predecessor, and that run was not shown
    who reads what: the readers of a component alone are, by construction, itself.

    So an output gone cannot be said to have been read by nobody - that is what the run was not
    shown - and an input dropped harms nobody, a component that stops reading something being
    no reason to hold the delivery back.
    """

    @staticmethod
    def sensor(*declarations: dict[str, Any]) -> dict[str, Any]:
        return component("Sensor", *declarations)

    PRESSURE = declare("output", "Pressure")
    CLOCK = declare("input", "Clock")
    TEMPERATURE = declare("output", "Temperature")

    def run(
        self, tree: Path, capsys: pytest.CaptureFixture[str], command: str, *arguments: str
    ) -> tuple[int, list[dict[str, Any]]]:
        capsys.readouterr()
        code = main([command, *arguments, "--format", "json", "-W", "missing-id=ignore"])
        payload = json.loads(capsys.readouterr().out)
        return code, payload["diagnostics"]

    def gate(
        self, tree: Path, capsys: pytest.CaptureFixture[str], baseline: dict[str, Any], new: Any
    ) -> tuple[int, list[dict[str, Any]]]:
        write_tree(tree, {"base.ddd.json": baseline, "s.ddd.json": new})
        return self.run(
            tree,
            capsys,
            "check",
            str(tree / "s.ddd.json"),
            "--standalone",
            "--baseline",
            str(tree / "base.ddd.json"),
        )

    def test_an_output_gone_is_an_error_that_does_not_claim_to_know_the_readers(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, found = self.gate(
            tree,
            capsys,
            self.sensor(self.PRESSURE, self.CLOCK),
            self.sensor(self.CLOCK),
        )
        assert code == EXIT_FINDINGS
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [(entry["check"], entry["severity"]) for entry in removed] == [
            ("removed-object", "error")
        ], found
        assert removed[0]["message"] == (
            "'Pressure' is gone; the baseline is one component read alone, so who read it is "
            "not known"
        )

    def test_an_input_dropped_harms_nobody(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, found = self.gate(
            tree,
            capsys,
            self.sensor(self.PRESSURE, self.CLOCK),
            self.sensor(self.PRESSURE),
        )
        assert code == EXIT_OK
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [(entry["check"], entry["severity"]) for entry in removed] == [
            ("removed-input", "info")
        ], found
        assert removed[0]["message"] == (
            "'Clock' is no longer read by Sensor; the component stops reading it, which "
            "harms nobody"
        )

    def test_an_input_dropped_stays_an_info_under_strict(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tree,
            {
                "base.ddd.json": self.sensor(self.PRESSURE, self.CLOCK),
                "s.ddd.json": self.sensor(self.PRESSURE),
            },
        )
        code, _ = self.run(
            tree,
            capsys,
            "check",
            str(tree / "s.ddd.json"),
            "--standalone",
            "--strict",
            "--baseline",
            str(tree / "base.ddd.json"),
        )
        assert code == EXIT_OK

    def test_the_same_output_gone_from_a_whole_project_names_its_reader(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tree,
            {
                "p.ddd.json": project("P", "a.ddd.json", "r.ddd.json"),
                "a.ddd.json": self.sensor(self.PRESSURE),
                "r.ddd.json": component("R", declare("input", "Pressure")),
            },
        )
        assert main(["dump", str(tree / "p.ddd.json"), "-o", str(tree / "base.json")]) == EXIT_OK
        write_tree(
            tree,
            {
                "a.ddd.json": self.sensor(declare("output", "Other")),
                "r.ddd.json": component("R", declare("input", "Other")),
            },
        )
        code, found = self.run(
            tree, capsys, "compare", str(tree / "base.json"), str(tree / "p.ddd.json")
        )
        assert code == EXIT_FINDINGS
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [(entry["check"], entry["message"]) for entry in removed] == [
            ("removed-object", "'Pressure' is gone, but was read by R")
        ], found

    def test_compare_grades_a_component_file_on_the_baseline_side_the_same_way(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Both are component files, which ``ddd compare`` reads without ``--standalone``, so
        neither has an input: nothing it reads is left without a producer."""
        write_tree(
            tree,
            {
                "base.ddd.json": self.sensor(self.PRESSURE, self.TEMPERATURE),
                "new.ddd.json": self.sensor(self.TEMPERATURE),
            },
        )
        code, found = self.run(
            tree, capsys, "compare", str(tree / "base.ddd.json"), str(tree / "new.ddd.json")
        )
        assert code == EXIT_FINDINGS
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [(entry["check"], entry["severity"]) for entry in removed] == [
            ("removed-object", "error")
        ], found
        assert "who read it is not known" in removed[0]["message"]

    def test_a_component_file_against_a_whole_project_is_graded_by_scope_too(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The baseline is the component read alone, the candidate the project that took it in:
        the output the project no longer offers is an error whose readers nobody knows."""
        write_tree(
            tree,
            {
                "base.ddd.json": self.sensor(self.PRESSURE, self.TEMPERATURE),
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": self.sensor(self.TEMPERATURE),
            },
        )
        code, found = self.run(
            tree, capsys, "compare", str(tree / "base.ddd.json"), str(tree / "p.ddd.json")
        )
        assert code == EXIT_FINDINGS
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [entry["check"] for entry in removed] == ["removed-object"], found
        assert "who read it is not known" in removed[0]["message"]

    def test_a_whole_project_against_a_component_file_keeps_the_readers_it_knows(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The baseline here is a whole project, so its readers are known and are named; only a
        baseline read alone does not know them."""
        write_tree(
            tree,
            {
                "p.ddd.json": project("P", "a.ddd.json", "r.ddd.json"),
                "a.ddd.json": self.sensor(self.PRESSURE),
                "r.ddd.json": component("R", declare("input", "Pressure")),
                "s.ddd.json": self.sensor(declare("output", "Other")),
            },
        )
        code, found = self.run(
            tree, capsys, "compare", str(tree / "p.ddd.json"), str(tree / "s.ddd.json")
        )
        assert code == EXIT_FINDINGS
        removed = [entry for entry in found if entry["check"].startswith("removed")]
        assert [entry["message"] for entry in removed] == [
            "'Pressure' is gone, but was read by R"
        ], found

    def test_compare_takes_the_baseline_as_read_alone_from_its_caller(self, tree: Path) -> None:
        """The dictionary carries no mark of how it was read, so the caller says."""
        old = self.resolved(tree, "old", self.sensor(self.PRESSURE, self.CLOCK))
        new = self.resolved(tree, "new", self.sensor(self.CLOCK))
        whole = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, whole)
        alone = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, alone, baseline_alone=True)
        assert checks(alone) == ["removed-object"], messages(alone)
        assert checks(whole) == ["removed-unused-object"], messages(whole)
        assert "Pressure" in messages(whole)

    @staticmethod
    def resolved(tree: Path, name: str, document: dict[str, Any]) -> DataDictionary:
        write_tree(tree, {f"{name}.ddd.json": document})
        bag = DiagnosticBag()
        workspace = load_workspace(tree / f"{name}.ddd.json", bag)
        assert workspace is not None, messages(bag)
        return analyze(workspace, bag)


class TestWhatAComponentReadAloneKeepsToItself:
    """Nobody outside a component can read what it declares ``local``, so a baseline read alone
    does know its readers, and a private object that is gone keeps the grade it always had.

    Held for a structured variable as well, whose members answer for the scope of the variable.
    """

    PAIR: ClassVar[dict[str, Any]] = {
        "t.ddd.json": types(struct_type("Pair_t", value_member("x"), value_member("y")))
    }

    def delivery(self, tree: Path, name: str, scope: str | None, *, structured: bool) -> Any:
        typed: dict[str, Any] = {"typename": "Pair_t"} if structured else {}
        kept = declare("output", "Kept")
        files = {
            f"{name}.ddd.json": project("P", f"{name}-t.ddd.json", f"{name}-a.ddd.json"),
            f"{name}-t.ddd.json": self.PAIR["t.ddd.json"],
            f"{name}-a.ddd.json": component(
                "A", kept, *([declare(scope, "Gone", **typed)] if scope else [])
            ),
        }
        write_tree(tree, files)
        return resolve(tree, f"{name}.ddd.json")

    def grade(self, tree: Path, scope: str, *, structured: bool) -> DiagnosticBag:
        old = self.delivery(tree, "old", scope, structured=structured)
        new = self.delivery(tree, "new", None, structured=structured)
        bag = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, bag, baseline_alone=True)
        return bag

    def test_a_local_object_gone_keeps_its_warning(self, tree: Path) -> None:
        bag = self.grade(tree, "local", structured=False)
        assert checks(bag) == ["removed-unused-object"], messages(bag)
        assert not bag.has_errors

    def test_a_local_structured_variable_gone_keeps_its_warning_under_every_member(
        self, tree: Path
    ) -> None:
        bag = self.grade(tree, "local", structured=True)
        assert set(checks(bag)) == {"removed-unused-object"}, messages(bag)
        assert not bag.has_errors

    def test_an_output_structured_variable_gone_is_an_error_under_every_member(
        self, tree: Path
    ) -> None:
        bag = self.grade(tree, "output", structured=True)
        assert set(checks(bag)) == {"removed-object"}, messages(bag)
        assert all("who read it is not known" in found.message for found in bag)

    def test_an_input_structured_variable_gone_is_information_under_every_member(
        self, tree: Path
    ) -> None:
        bag = self.grade(tree, "input", structured=True)
        assert set(checks(bag)) == {"removed-input"}, messages(bag)
        assert not bag.has_errors


class TestConstantsAndRastersAreComparedAsEntries:
    """The vocabularies an object reaches the outputs through.

    Every constant reaches the generated header as a macro and the a2l as a
    ``SYSTEM_CONSTANT``, and every raster is an ``EVENT`` the ``IF_DATA`` of each object that
    names it points at. A constant no object is dimensioned by, or a raster renumbered, changed
    nothing the objects compare on, so the delivery replaced its predecessor under ``--strict``
    while its outputs differed.
    """

    def delivery(
        self,
        tree: Path,
        name: str,
        *,
        gain: int | float | None = 2,
        gain_name: str = "GAIN",
        cells: int = 4,
        event: int = 1,
        cycle: str = "10ms",
        extra_raster: bool = False,
    ) -> DataDictionary:
        """``Arr`` sized by the constant ``N``, ``X`` measured in the raster ``10ms``, and a
        ``GAIN`` that no object uses."""
        constants = [{"name": "N", "value": cells}]
        if gain is not None:
            constants.append({"name": gain_name, "value": gain})
        rasters = [
            {"raster": "1ms", "event": 0, "cycle": "1ms"},
            {"raster": "10ms", "event": event, "cycle": cycle},
        ]
        if extra_raster:
            rasters.append({"raster": "100ms", "event": 5, "cycle": "100ms"})
        write_tree(
            tree,
            {
                f"{name}.ddd.json": project(
                    "P", f"{name}-c.ddd.json", f"{name}-r.ddd.json", f"{name}-a.ddd.json"
                ),
                f"{name}-c.ddd.json": {"constants": constants},
                f"{name}-r.ddd.json": {"rasters": rasters},
                f"{name}-a.ddd.json": component(
                    "A",
                    declare("local", "Arr", dimensions=["N"]),
                    declare("local", "X", raster="10ms"),
                ),
            },
        )
        return resolve(tree, f"{name}.ddd.json")

    def strict(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> tuple[tuple[int, str], tuple[int, str]]:
        """Both sides as descriptions, and the baseline as a dump, each under ``--strict``."""
        described = ruling(tree, capsys, "--strict")
        assert main(["dump", str(tree / "old.ddd.json"), "-o", str(tree / "old.json")]) == EXIT_OK
        capsys.readouterr()
        code = main(["compare", str(tree / "old.json"), str(tree / "new.ddd.json"), "--strict"])
        return described, (code, capsys.readouterr().err)

    def cannot_replace(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        for code, report in self.strict(tree, capsys):
            assert code == EXIT_FINDINGS, report
            assert "cannot replace" in report

    def can_replace(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        for code, report in self.strict(tree, capsys):
            assert code == EXIT_OK, report
            assert "can replace" in report and "cannot replace" not in report

    def test_two_identical_deliveries_compare_clean(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new")
        assert checks(verdict(old, new)) == []
        self.can_replace(tree, capsys)

    def test_a_constant_no_object_uses_changing_its_value_is_a_changed_interface(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every reader's header holds the macro, whatever the objects hold."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", gain=3)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"], messages(bag)
        assert "constant 'GAIN' is not the same any more (value: 3 != 2)" in messages(bag)
        self.cannot_replace(tree, capsys)

    def test_a_constant_gone_is_an_error_of_its_own(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader that uses the macro no longer builds."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", gain=None)
        bag = verdict(old, new)
        assert checks(bag) == ["removed-constant"], messages(bag)
        assert "constant 'GAIN' is gone; a reader that uses it no longer builds" in messages(bag)
        self.cannot_replace(tree, capsys)

    def test_a_constant_renamed_is_one_removal_and_one_addition(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A constant has no id to pair a rename by, so the old name is gone and the new one
        arrived; the removal is the error, since a reader names the old macro."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", gain_name="AMPLIFICATION")
        bag = verdict(old, new)
        assert sorted(checks(bag)) == ["added-constant", "removed-constant"], messages(bag)
        assert "constant 'GAIN' is gone" in messages(bag)
        assert "constant 'AMPLIFICATION' is new in P (2)" in messages(bag)
        self.cannot_replace(tree, capsys)

    def test_a_constant_added_is_information(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old", gain=None)
        new = self.delivery(tree, "new")
        bag = verdict(old, new)
        assert checks(bag) == ["added-constant"], messages(bag)
        assert "constant 'GAIN' is new in P (2)" in messages(bag)
        self.can_replace(tree, capsys)

    def test_a_constant_that_dimensions_an_object_is_said_at_both(self, tree: Path) -> None:
        """The macro and the size are two facts, and the object's shape is still said at the
        object, as the layout says it at each variable."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", cells=5)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"] * 2, messages(bag)
        assert "constant 'N' is not the same any more (value: 5 != 4)" in messages(bag)
        assert "'Arr' is not the same object any more (shape: [N] != [N])" in messages(bag)

    def test_a_raster_given_another_event_is_a_changed_storage(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every ``IF_DATA`` that names it carries the event."""
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", event=7)
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert "raster '10ms' is not the same any more (event: 7 != 1)" in messages(bag)
        self.cannot_replace(tree, capsys)

    def test_a_raster_given_another_cycle_is_a_changed_storage(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", cycle="20ms")
        bag = verdict(old, new)
        assert checks(bag) == ["changed-storage"], messages(bag)
        assert "raster '10ms' is not the same any more (cycle: '20ms' != '10ms')" in messages(bag)
        self.cannot_replace(tree, capsys)

    def test_a_raster_respelled_with_the_same_period_is_no_change(self, tree: Path) -> None:
        old = self.delivery(tree, "old")
        new = self.delivery(tree, "new", cycle="10000us")
        assert checks(verdict(old, new)) == []

    def test_a_raster_no_object_names_coming_or_going_says_nothing(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An object that names a raster says its own change, and one that names none has
        nothing the raster reaches."""
        bare = self.delivery(tree, "old")
        more = self.delivery(tree, "new", extra_raster=True)
        assert checks(verdict(bare, more)) == []
        assert checks(verdict(more, bare)) == []
        self.can_replace(tree, capsys)

    def test_a_baseline_of_format_3_recorded_no_constants_to_compare(self, tree: Path) -> None:
        """Against a dump that predates the vocabulary every constant of the candidate would
        arrive, and none could have changed or gone."""
        old = without_spellings(self.delivery(tree, "old", gain=None))
        new = self.delivery(tree, "new", gain=3)
        assert checks(verdict(old, new)) == []
        assert checks(verdict(old, new.model_copy(update={"constants": ()}))) == []
