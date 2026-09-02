"""Tests for measurement rasters: the file, the checks, and the event they carry.

A raster is a DAQ event the target offers, and an event channel number is a property of the
ecu rather than of any component - so a raster is declared once, project wide, and a
definition names it the way it names a memory section.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.cli import schema_text
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.models import RastersFile


def rasters(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"rasters": list(entries)}


def raster(name: str = "10ms", event: int = 1, **extra: Any) -> dict[str, Any]:
    return {"raster": name, "event": event, **extra}


class TestTheFile:
    def test_a_raster_carries_its_properties(self) -> None:
        model = RastersFile.model_validate(
            rasters(raster("10ms", 3, cycle="10ms", description="control task"))
        )
        declared = model.rasters[0]
        assert declared.raster == "10ms"
        assert declared.event == 3
        assert declared.cycle_ns == 10_000_000
        assert declared.description == "control task"

    def test_an_event_without_a_cycle_is_not_cyclic(self) -> None:
        """Crank synchronous and on-change events are real; the period is what they lack."""
        declared = RastersFile.model_validate(rasters(raster("crank", 4))).rasters[0]
        assert declared.cycle is None
        assert declared.cycle_ns is None

    def test_a_name_longer_than_the_xcp_event_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RastersFile.model_validate(rasters(raster("Task_10ms")))

    def test_a_name_with_whitespace_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RastersFile.model_validate(rasters(raster("two wds")))

    def test_an_event_number_wider_than_the_field_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RastersFile.model_validate(rasters(raster("x", 0x10000)))

    @pytest.mark.parametrize("cycle", ["10 ms", "1.5ms", "ms", "10min", ""])
    def test_a_period_that_is_not_a_count_and_a_unit_is_refused(self, cycle: str) -> None:
        with pytest.raises(ValidationError, match="is not a period"):
            RastersFile.model_validate(rasters(raster(cycle=cycle)))

    @pytest.mark.parametrize("cycle", ["1234ms", "256s", "0ms"])
    def test_a_period_no_xcp_event_can_carry_is_refused(self, cycle: str) -> None:
        """A count of 1 to 255 times a decade from 1ns to 1s, and nothing else."""
        with pytest.raises(ValidationError, match="no xcp event period"):
            RastersFile.model_validate(rasters(raster(cycle=cycle)))

    @pytest.mark.parametrize(
        ("cycle", "nanoseconds"),
        [
            ("1ns", 1),
            ("100us", 100_000),
            ("1500us", 1_500_000),
            ("500ms", 500_000_000),
            ("255s", 255_000_000_000),
        ],
    )
    def test_a_period_xcp_carries_is_accepted(self, cycle: str, nanoseconds: int) -> None:
        declared = RastersFile.model_validate(rasters(raster(cycle=cycle))).rasters[0]
        assert declared.cycle_ns == nanoseconds

    def test_a_rasters_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        write_tree(tree, {"rasters.ddd.json": rasters(raster())})
        bag = DiagnosticBag()
        assert load_workspace(tree / "rasters.ddd.json", bag) is None
        assert checks(bag) == ["file-kind"]
        assert "list it in the 'includes'" in messages(bag)

    def test_two_files_cannot_declare_the_same_raster(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": rasters(raster("10ms", 1)),
                "two.ddd.json": rasters(raster("10ms", 2)),
            },
        )
        assert checks(bag) == ["duplicate-raster"]
        assert "is already declared" in messages(bag)

    def test_a_project_reads_the_rasters_it_includes(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "r.ddd.json", "a.ddd.json"),
                "r.ddd.json": rasters(raster("10ms", 1), raster("1ms", 0)),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None
        assert [entry.raster for entry in workspace.rasters] == ["10ms", "1ms"]


class TestTheSchema:
    def test_the_schema_is_published(self) -> None:
        published = schema_text("rasters")
        assert '"title": "DDD measurement rasters"' in published
        assert '"additionalProperties": false' in published
