"""Tests for memory sections: the file, the checks, and the placement they carry.

Placement is a property of one object - one address, one section - so a definition names a
section the way it names a declared type: a reference to something declared once. The two
properties a section declares are exactly what the checks consume: whether the software can
write it, and the alignment it guarantees.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.models import SectionsFile


def sections(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"sections": list(entries)}


def section(name: str, access: str = "read-write", alignment: int = 4) -> dict[str, Any]:
    return {"section": name, "access": access, "alignment": alignment}


class TestTheFile:
    def test_a_section_carries_its_properties(self) -> None:
        model = SectionsFile.model_validate(sections(section(".calib", "read-only", 2)))
        declared = model.sections[0]
        assert declared.section == ".calib"
        assert not declared.writable
        assert declared.alignment == 2

    def test_an_alignment_that_is_not_a_power_of_two_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="not a power of two"):
            SectionsFile.model_validate(sections(section(".x", alignment=3)))

    def test_a_name_with_whitespace_is_refused(self) -> None:
        """No linker accepts one either, and a finding would quote it confusingly."""
        with pytest.raises(ValidationError):
            SectionsFile.model_validate(sections(section("two words")))

    def test_a_sections_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        write_tree(tree, {"sections.ddd.json": sections(section(".data"))})
        bag = DiagnosticBag()
        assert load_workspace(tree / "sections.ddd.json", bag) is None
        assert checks(bag) == ["file-kind"]
        assert "list it in the 'includes'" in messages(bag)

    def test_two_files_cannot_declare_the_same_section(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": sections(section(".calib")),
                "two.ddd.json": sections(section(".calib", "read-only", 8)),
            },
        )
        assert checks(bag) == ["duplicate-section"]
        assert "is already declared" in messages(bag)


class TestTheChecks:
    def files(self, *declarations: dict[str, Any], **declared: Any) -> dict[str, Any]:
        vocabulary = declared.pop(
            "vocabulary", [section(".fast_ram"), section(".calib", "read-only", 2)]
        )
        assert not declared
        return {
            "project.ddd.json": project("P", "sections.ddd.json", "a.ddd.json"),
            "sections.ddd.json": sections(*vocabulary),
            "a.ddd.json": component("A", *declarations),
        }

    def test_a_declared_section_passes(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files(declare("local", "X", section=".fast_ram")))
        assert checks(bag) == []

    def test_an_undeclared_section_is_reported_with_the_nearest_name(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files(declare("local", "X", section=".fast_rams")))
        assert checks(bag) == ["unknown-section"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition.section" in rendered
        assert "did you mean '.fast_ram'" in rendered

    def test_a_section_is_a_reference_even_without_a_sections_file(self, tree: Path) -> None:
        """Unlike a unit: a section without declared properties tells the checks nothing."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", section=".data")),
            },
        )
        assert checks(bag) == ["unknown-section"]

    def test_a_measurement_cannot_live_in_a_read_only_section(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files(declare("local", "X", section=".calib")))
        assert checks(bag) == ["section-access"]
        assert "the software writes" in messages(bag)

    def test_a_parameter_may_live_in_a_writable_section(self, tree: Path) -> None:
        """A mirrored calibration: const data in RAM is a normal arrangement."""
        _, bag = run_analysis(
            tree,
            self.files(
                declare(
                    "local", "X", kind="parameter", init=0, section=".fast_ram", datatype="uint8"
                )
            ),
        )
        assert checks(bag) == []

    def test_an_object_needing_stricter_alignment_is_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            self.files(
                declare("local", "X", kind="parameter", init=0, section=".calib", datatype="uint32")
            ),
        )
        assert checks(bag) == ["section-alignment"]
        assert "needs an alignment of 4, but '.calib' guarantees 2" in messages(bag)

    def test_a_scalar_typed_object_needs_its_type_storage(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "sections.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "sections.ddd.json": sections(section(".small", "read-write", 4)),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Stamp_t",
                            "datatype": "uint64",
                            "conversion": {},
                        }
                    ]
                },
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Stamp_t", section=".small")
                ),
            },
        )
        assert checks(bag) == ["section-alignment"]
        assert "needs an alignment of 8" in messages(bag)

    def test_a_structure_needs_its_strictest_member(self, tree: Path) -> None:
        """Walked through nested structures; the estimate is the description's best."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "sections.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "sections.ddd.json": sections(section(".small", "read-write", 2)),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Inner_t",
                            "members": [
                                {
                                    "name": "wide",
                                    "member": "value",
                                    "datatype": "uint64",
                                    "conversion": {},
                                }
                            ],
                        },
                        {
                            "type": "struct",
                            "name": "Outer_t",
                            "members": [
                                {"name": "inner", "member": "value", "typename": "Inner_t"}
                            ],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Outer_t", section=".small")
                ),
            },
        )
        assert checks(bag) == ["section-alignment", "unused-output"] or checks(bag) == [
            "section-alignment"
        ]
        assert "needs an alignment of 8" in messages(bag)

    def test_a_malformed_sections_file_is_reported_against_its_keys(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "sections.ddd.json"),
                "sections.ddd.json": {"sections": [{"section": ".x", "alignment": 4}]},
            },
        )
        assert checks(bag) == ["schema"]
        assert "sections[0]" in messages(bag)

    def test_a_placed_object_of_an_unknown_type_gets_no_second_finding(self, tree: Path) -> None:
        """The unknown type is the finding; an alignment guess on top would be noise."""
        _, bag = run_analysis(
            tree,
            self.files(declare("local", "X", typename="Nowhere_t", section=".fast_ram")),
        )
        assert checks(bag) == ["unknown-type"]

    def test_a_cyclic_structure_gets_no_alignment_finding(self, tree: Path) -> None:
        """The cycle is the finding: a structure without a size has no alignment either."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "sections.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "sections.ddd.json": sections(section(".small", "read-write", 1)),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "A_t",
                            "members": [{"name": "b", "member": "value", "typename": "B_t"}],
                        },
                        {
                            "type": "struct",
                            "name": "B_t",
                            "members": [{"name": "a", "member": "value", "typename": "A_t"}],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="A_t", section=".small")
                ),
            },
        )
        assert checks(bag) == ["type-cycle"]

    def test_a_consumer_stating_a_section_claims_storage_it_does_not_own(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "sections.ddd.json", "a.ddd.json", "b.ddd.json"),
                "sections.ddd.json": sections(section(".fast_ram")),
                "a.ddd.json": component("A", declare("output", "X", section=".fast_ram")),
                "b.ddd.json": component("B", declare("input", "X", section=".fast_ram")),
            },
        )
        assert checks(bag) == ["consumer-storage"]
        assert "the memory section is decided by the component that produces" in messages(bag)


class TestPlacementReachesTheOutputs:
    def project_files(self) -> dict[str, Any]:
        return {
            "project.ddd.json": project("P", "sections.ddd.json", "a.ddd.json"),
            "sections.ddd.json": sections(section(".fast_ram", "read-write", 8)),
            "a.ddd.json": component(
                "A",
                declare("local", "Wide", datatype="uint64", section=".fast_ram"),
                declare("local", "Narrow", datatype="uint8", section=".fast_ram"),
                declare("local", "Unplaced", datatype="uint8"),
            ),
        }

    def test_the_dictionary_records_the_section(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, self.project_files())
        assert dictionary is not None, [d.render() for d in bag]
        by_name = {entry.name: entry.section for entry in dictionary.objects}
        assert by_name == {"Wide": ".fast_ram", "Narrow": ".fast_ram", "Unplaced": None}

    def test_the_generated_definition_carries_the_attribute(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, self.project_files())
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        source = files["ddd_globals.c"]
        assert 'uint64_t Wide __attribute__((section(".fast_ram")));' in source
        assert "uint8_t Unplaced;" in source

    def test_the_template_model_groups_per_section_strictest_first(self, tree: Path) -> None:
        from ddd.backends import COptions
        from ddd.backends.c.model import build_code_model

        dictionary, _ = run_analysis(tree, self.project_files())
        assert dictionary is not None
        model = build_code_model(dictionary, COptions(), "test")
        (group,) = model.sections
        assert group.name == ".fast_ram"
        assert [view.name for view in group.objects] == ["Wide", "Narrow"]

    def test_a_placed_structure_joins_its_section_group(self, tree: Path) -> None:
        from ddd.backends import COptions
        from ddd.backends.c.model import build_code_model

        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "sections.ddd.json", "types.ddd.json", "a.ddd.json"
                ),
                "sections.ddd.json": sections(section(".fast_ram", "read-write", 8)),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Inner_t",
                            "members": [
                                {
                                    "name": "wide",
                                    "member": "value",
                                    "datatype": "uint64",
                                    "conversion": {},
                                }
                            ],
                        },
                        {
                            "type": "struct",
                            "name": "Outer_t",
                            "members": [
                                {"name": "inner", "member": "value", "typename": "Inner_t"},
                                {
                                    "name": "tag",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                },
                            ],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A",
                    declare("local", "Pack", typename="Outer_t", section=".fast_ram"),
                    declare("local", "Tiny", datatype="uint8", section=".fast_ram"),
                ),
            },
        )
        assert dictionary is not None, [d.render() for d in bag]
        model = build_code_model(dictionary, COptions(), "test")
        (group,) = model.sections
        assert [view.name for view in group.objects] == ["Pack", "Tiny"]

    def test_a_moved_object_is_a_storage_change_between_deliveries(self, tree: Path) -> None:
        from ddd.compare import compare

        before, _ = run_analysis(tree, self.project_files())
        files = self.project_files()
        files["a.ddd.json"]["component"]["interface"][1]["definition"]["section"] = None
        del files["a.ddd.json"]["component"]["interface"][1]["definition"]["section"]
        after, _ = run_analysis(tree, files, root="project.ddd.json")
        assert before is not None and after is not None
        bag = DiagnosticBag()
        compare(before, after, bag)
        assert "changed-storage" in checks(bag)
        assert "section" in messages(bag)


class TestSectionSpelling:
    def test_a_name_that_would_end_a_c_string_literal_is_refused(self) -> None:
        """The name is spliced into ``__attribute__((section("...")))`` by the templates."""
        with pytest.raises(ValidationError):
            SectionsFile.model_validate(sections(section('.calib")x')))

    def test_a_name_with_a_dollar_or_a_dot_is_a_section_name(self) -> None:
        SectionsFile.model_validate(sections(section(".CRT$XCU")))

    def test_a_definition_naming_a_section_is_held_to_the_same_spelling(self) -> None:
        from ddd.models import ComponentFile

        with pytest.raises(ValidationError):
            ComponentFile.model_validate(component("A", declare("local", "X", section='.x"')))
