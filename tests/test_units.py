"""Tests for the unit vocabulary: the file, and the check it switches on.

``unit`` is free text everywhere it is written, so without a vocabulary one quantity can
drift into two spellings - ``Nm`` here, ``newton_meter`` there - and nothing says so: each
object agrees with itself. The vocabulary is the opt-in that pins the spellings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.models import UnitsFile


def units(*entries: Any) -> dict[str, Any]:
    return {"units": list(entries)}


class TestTheFile:
    def test_a_bare_string_is_a_unit(self) -> None:
        """The whole file for a project that only wants the spellings pinned."""
        model = UnitsFile.model_validate(units("Nm", "rpm"))
        assert [entry.unit for entry in model.units] == ["Nm", "rpm"]
        assert model.units[0].description == ""

    def test_an_object_carries_the_meaning(self) -> None:
        model = UnitsFile.model_validate(units({"unit": "Nm", "description": "torque"}))
        assert model.units[0].description == "torque"

    def test_an_empty_vocabulary_is_refused(self) -> None:
        """Declaring nothing is done by not writing the file, not by an empty list."""
        with pytest.raises(ValidationError):
            UnitsFile.model_validate(units())

    def test_an_empty_spelling_is_refused(self) -> None:
        """The empty unit is the absence of an answer, not a spelling of one."""
        with pytest.raises(ValidationError):
            UnitsFile.model_validate(units(""))

    def test_a_units_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        write_tree(tree, {"units.ddd.json": units("Nm")})
        bag = DiagnosticBag()
        assert load_workspace(tree / "units.ddd.json", bag) is None
        assert checks(bag) == ["file-kind"]
        assert "list it in the 'includes'" in messages(bag)

    def test_a_malformed_units_file_is_reported_against_its_keys(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "units.ddd.json"),
                "units.ddd.json": {"units": [{"description": "torque"}]},
            },
        )
        assert checks(bag) == ["schema"]
        assert "units[0]" in messages(bag)

    def test_two_files_cannot_declare_the_same_unit(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": units("Nm"),
                "two.ddd.json": units({"unit": "Nm", "description": "torque"}),
            },
        )
        assert checks(bag) == ["duplicate-unit"]
        assert "is declared twice" in messages(bag)


class TestTheCheck:
    def files(self, unit: str, *vocabulary: Any) -> dict[str, Any]:
        return {
            "project.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
            "units.ddd.json": units(*vocabulary),
            "a.ddd.json": component("A", declare("local", "X", unit=unit)),
        }

    def test_a_declared_spelling_passes(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files("Nm", "Nm", "rpm"))
        assert checks(bag) == []

    def test_an_undeclared_spelling_is_reported_where_it_is_written(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files("newton_meter", "Nm", "rpm"))
        assert checks(bag) == ["unknown-unit"]
        rendered = messages(bag)
        assert "a.ddd.json#component.interface[0].definition.unit" in rendered
        assert "'newton_meter' is not a unit this project declares" in rendered

    def test_the_nearest_spelling_is_suggested(self, tree: Path) -> None:
        _, bag = run_analysis(tree, self.files("nm", "Nm", "rpm"))
        assert "did you mean 'Nm'" in messages(bag)

    def test_the_empty_unit_is_always_allowed(self, tree: Path) -> None:
        """A dimensionless value states no unit rather than a spelling of one."""
        _, bag = run_analysis(tree, self.files("", "Nm"))
        assert checks(bag) == []

    def test_without_a_vocabulary_units_stay_free(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", unit="anything goes")),
            },
        )
        assert checks(bag) == []

    def test_a_member_unit_is_checked(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "units.ddd.json", "types.ddd.json"),
                "units.ddd.json": units("degC"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [
                                {
                                    "name": "t",
                                    "member": "value",
                                    "datatype": "uint16",
                                    "conversion": {},
                                    "unit": "celsius",
                                }
                            ],
                        }
                    ]
                },
            },
        )
        assert checks(bag) == ["unknown-unit"]
        assert "types.ddd.json#types[0].members[0].unit" in messages(bag)

    def test_a_scalar_type_unit_is_checked(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "units.ddd.json", "types.ddd.json"),
                "units.ddd.json": units("degC"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Temp_t",
                            "datatype": "uint16",
                            "conversion": {},
                            "unit": "celsius",
                        }
                    ]
                },
            },
        )
        assert checks(bag) == ["unknown-unit"]
        assert "types.ddd.json#types[0].unit" in messages(bag)

    def test_the_check_is_relaxable(self, tree: Path) -> None:
        """A vocabulary being introduced into a grown project needs a ramp."""
        _, bag = run_analysis(
            tree, self.files("newton_meter", "Nm"), severities=["unknown-unit=warning"]
        )
        assert checks(bag) == ["unknown-unit"]
        assert not bag.has_errors
