"""Tests for the naming convention: validating, locating, explaining and completing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, write_tree
from ddd.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, main
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_convention
from ddd.models import NamingConvention, NamingFile
from ddd.naming import check_names, complete, explain, inspect

CONVENTION = Path(__file__).resolve().parents[1] / "examples" / "naming" / "convention.ddd.json"


def convention(**overrides: Any) -> NamingConvention:
    """A two segment convention: <role>_<Subject>[_<qualifier>]."""
    payload: dict[str, Any] = {
        "name": "test",
        "separator": "_",
        "segments": [
            {
                "name": "role",
                "tokens": [{"value": "val", "description": "a value"}, {"value": "flg"}],
            },
            {"name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$"},
            {"name": "qualifier", "optional": True, "tokens": [{"value": "raw"}, {"value": "flt"}]},
        ],
        **overrides,
    }
    return NamingConvention.model_validate(payload)


class TestContract:
    def test_the_example_convention_loads(self) -> None:
        model = NamingFile.model_validate_json(CONVENTION.read_text(encoding="utf-8"))
        assert model.naming.segment_names == ("role", "subject", "qualifier")

    def test_a_segment_needs_tokens_or_a_pattern(self) -> None:
        with pytest.raises(ValidationError, match="needs either tokens or a pattern"):
            convention(segments=[{"name": "anything"}])

    def test_a_segment_cannot_have_both(self) -> None:
        with pytest.raises(ValidationError, match="use one"):
            convention(segments=[{"name": "x", "tokens": [{"value": "a"}], "pattern": "^a$"}])

    def test_a_duplicated_token_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="lists 'a' twice"):
            convention(segments=[{"name": "x", "tokens": [{"value": "a"}, {"value": "a"}]}])

    def test_a_required_segment_cannot_follow_an_optional_one(self) -> None:
        """Otherwise a name could not be split unambiguously."""
        with pytest.raises(ValidationError, match="follows an optional one"):
            convention(
                segments=[
                    {"name": "a", "optional": True, "tokens": [{"value": "x"}]},
                    {"name": "b", "tokens": [{"value": "y"}]},
                ]
            )

    def test_only_one_segment_may_repeat(self) -> None:
        with pytest.raises(ValidationError, match="only one segment may be repeatable"):
            convention(
                segments=[
                    {"name": "a", "repeatable": True, "pattern": "^.$"},
                    {"name": "b", "repeatable": True, "pattern": "^.$"},
                ]
            )

    def test_a_token_may_not_contain_whitespace(self) -> None:
        with pytest.raises(ValidationError, match="contains whitespace"):
            convention(segments=[{"name": "x", "tokens": [{"value": "a b"}]}])

    def test_a_convention_needs_a_segment(self) -> None:
        with pytest.raises(ValidationError):
            convention(segments=[])


class TestInspection:
    @pytest.mark.parametrize(
        "name", ["val_Inlet", "val_Inlet_raw", "flg_InletValid", "flg_Inlet_flt"]
    )
    def test_well_formed_names_pass(self, name: str) -> None:
        assert inspect(name, convention()).ok

    def test_an_unknown_token_is_located_and_a_correction_offered(self) -> None:
        result = inspect("vl_Inlet", convention())
        assert not result.ok
        part = result.problems[0]
        assert part.text == "vl"
        assert part.start == 0
        assert "is not a known role" in (part.problem or "")
        assert part.suggestions == ("'val'",)

    def test_a_pattern_violation_is_located(self) -> None:
        result = inspect("val_inlet", convention())
        part = result.problems[0]
        assert part.text == "inlet"
        assert part.start == 4
        assert "does not match the subject pattern" in (part.problem or "")

    def test_the_offending_part_is_underlined(self) -> None:
        """The reason for splitting into segments: show where, not just that."""
        assert inspect("val_inlet_raw", convention()).underline() == ("val_inlet_raw\n    ^^^^^")

    def test_a_name_that_stops_too_early(self) -> None:
        result = inspect("val", convention())
        assert not result.ok
        assert [segment.name for segment in result.missing] == ["subject"]

    def test_a_name_with_one_part_too_many(self) -> None:
        result = inspect("val_Inlet_raw_extra", convention())
        assert not result.ok
        assert "one part too many" in messages_of(result)

    def test_an_empty_part(self) -> None:
        result = inspect("val__raw", convention())
        assert "the subject part is empty" in messages_of(result)

    def test_a_repeatable_segment_swallows_the_middle(self) -> None:
        rule = convention(
            segments=[
                {"name": "role", "tokens": [{"value": "val"}]},
                {"name": "subject", "pattern": "^[A-Z][A-Za-z0-9]*$", "repeatable": True},
                {"name": "qualifier", "optional": True, "tokens": [{"value": "raw"}]},
            ]
        )
        assert inspect("val_Inlet_Temperature_Sensor_raw", rule).ok
        assert inspect("val_Inlet", rule).ok

    def test_a_repeatable_segment_is_still_required_once(self) -> None:
        rule = convention(
            segments=[
                {"name": "role", "tokens": [{"value": "val"}]},
                {"name": "subject", "pattern": "^[A-Z].*$", "repeatable": True},
            ]
        )
        assert [s.name for s in inspect("val", rule).missing] == ["subject"]

    def test_case_insensitive_matching_can_be_asked_for(self) -> None:
        rule = convention(case_sensitive=False)
        assert inspect("VAL_Inlet", rule).ok
        assert not inspect("VAL_Inlet", convention()).ok

    def test_a_part_beyond_the_convention_has_no_meaning(self) -> None:
        surplus = inspect("val_Inlet_raw_extra", convention()).parts[-1]
        assert surplus.segment is None
        assert surplus.meaning == ""

    def test_explain_gives_the_meaning_of_each_part(self) -> None:
        parts = explain("val_Inlet_raw", convention()).parts
        assert [part.segment.name for part in parts if part.segment] == [
            "role",
            "subject",
            "qualifier",
        ]
        assert parts[0].meaning == "a value"
        assert parts[1].meaning == ""  # a pattern segment has no per-token meaning


def messages_of(result: Any) -> str:
    return " | ".join(part.problem or "" for part in result.problems)


class TestCompletion:
    def test_the_first_segment_is_offered_from_nothing(self) -> None:
        assert complete("", convention()) == ["val", "flg"]

    def test_a_partial_token_filters(self) -> None:
        assert complete("v", convention()) == ["val"]

    def test_the_separator_asks_for_the_next_segment(self) -> None:
        assert complete("val_Inlet_", convention()) == ["val_Inlet_raw", "val_Inlet_flt"]

    def test_a_partial_token_of_a_later_segment_filters(self) -> None:
        assert complete("val_Inlet_r", convention()) == ["val_Inlet_raw"]

    def test_a_free_segment_offers_nothing(self) -> None:
        """There is nothing to suggest for a pattern; the caller keeps typing."""
        assert complete("val_", convention()) == []

    def test_a_finished_name_offers_nothing(self) -> None:
        assert complete("val_Inlet_raw_", convention()) == []

    def test_completion_is_case_insensitive_when_the_convention_is(self) -> None:
        assert complete("V", convention(case_sensitive=False)) == ["val"]


class TestProjectIntegration:
    def test_a_project_can_point_at_its_convention(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "p.ddd.json": {
                    "project": {
                        "name": "P",
                        "naming": "c.ddd.json",
                        "includes": ["a.ddd.json"],
                    }
                },
                "c.ddd.json": json.loads(CONVENTION.read_text(encoding="utf-8")),
                "a.ddd.json": component("A", declare("local", "val_Inlet_flt", "uint16")),
            },
        )
        assert main(["check", str(tree / "p.ddd.json")]) == EXIT_OK

    def test_a_project_reports_every_name_it_does_not_like(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "p.ddd.json": {
                    "project": {
                        "name": "P",
                        "naming": "c.ddd.json",
                        "includes": ["a.ddd.json"],
                    }
                },
                "c.ddd.json": json.loads(CONVENTION.read_text(encoding="utf-8")),
                "a.ddd.json": component(
                    "A",
                    declare("local", "vl_Inlet", "uint16"),
                    declare("local", "val_inlet", "uint16"),
                ),
            },
        )
        assert main(["check", str(tree / "p.ddd.json")]) == EXIT_FINDINGS

    def test_a_naming_convention_cannot_be_included_as_a_component(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "p.ddd.json": project("P", "c.ddd.json"),
                "c.ddd.json": json.loads(CONVENTION.read_text(encoding="utf-8")),
            },
        )
        bag = DiagnosticBag()
        from ddd.loading import load_workspace

        load_workspace(tree / "p.ddd.json", bag)
        assert checks(bag) == ["file-kind"]
        assert "point the 'naming' key of the project at it" in messages(bag)

    def test_a_missing_convention_file_is_reported(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "p.ddd.json": {"project": {"name": "P", "naming": "gone.ddd.json", "includes": []}},
            },
        )
        bag = DiagnosticBag()
        from ddd.loading import load_workspace

        load_workspace(tree / "p.ddd.json", bag)
        assert checks(bag) == ["file-not-found"]

    def test_a_broken_convention_file_is_reported(self, tree: Path) -> None:
        bag = DiagnosticBag()
        write_tree(tree, {"c.ddd.json": {"naming": {"name": "x"}}})
        assert load_convention(tree / "c.ddd.json", bag) is None
        assert checks(bag) == ["schema"]

    def test_a_rejected_name_is_reported_with_its_underline(self) -> None:
        bag = DiagnosticBag()
        check_names({"vl_Inlet": None}, convention(), bag)
        assert checks(bag) == ["naming"]
        assert "vl_Inlet\n          ^^" in messages(bag)

    def test_a_name_stopping_short_is_reported_too(self) -> None:
        bag = DiagnosticBag()
        check_names({"val": None}, convention(), bag)
        assert checks(bag) == ["naming"]
        assert "stops before the subject part" in messages(bag)


class TestCommandLine:
    def test_explaining_a_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["name", "-c", str(CONVENTION), "val_InletTemperature_flt"]) == EXIT_OK
        out = capsys.readouterr().out
        assert "a measured or computed value" in out
        assert "filtered" in out

    def test_a_bad_name_exits_with_a_finding(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["name", "-c", str(CONVENTION), "vl_Inlet"]) == EXIT_FINDINGS
        out = capsys.readouterr().out
        assert "^^" in out
        assert "did you mean 'val'?" in out

    def test_a_missing_part_is_named(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["name", "-c", str(CONVENTION), "val"]) == EXIT_FINDINGS
        assert "the subject part is missing" in capsys.readouterr().out

    def test_json_output_carries_the_positions(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["name", "-c", str(CONVENTION), "vl_Inlet", "--format", "json"]) == (
            EXIT_FINDINGS
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["ok"] is False
        assert payload[0]["parts"][0]["start"] == 0
        assert payload[0]["parts"][0]["suggestions"] == ["'val'"]

    def test_an_unreadable_convention_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["name", "-c", "gone.ddd.json", "val_Inlet"]) == EXIT_USAGE
        assert "does not exist" in capsys.readouterr().err

    def test_completion_prints_one_candidate_per_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["complete", "-c", str(CONVENTION), "c"]) == EXIT_OK
        assert capsys.readouterr().out.split() == ["cnt", "crv"]

    def test_completion_with_no_prefix(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["complete", "-c", str(CONVENTION)]) == EXIT_OK
        assert "val" in capsys.readouterr().out.split()

    def test_completion_never_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A shell completion that errors is worse than one that offers nothing."""
        assert main(["complete", "-c", "gone.ddd.json", "v"]) == EXIT_OK
        assert capsys.readouterr().out == ""

    def test_the_convention_has_a_published_schema(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["schema", "naming"]) == EXIT_OK
        assert "naming" in json.loads(capsys.readouterr().out)["properties"]
