"""One variable as the unit panel of ddd gui shows it, and what settling one of its keys takes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.editing import UNREADABLE, EditError, Operation, fingerprint
from ddd.loading import load_workspace
from ddd.lsp.edits import Settled, Settlement, Unsettled, settle
from ddd.lsp.navigation import Index, Site, index
from ddd.lsp.ranges import Document
from ddd.variables import (
    Hunk,
    declarations_of,
    located_on,
    narrowed,
    preview,
    refusal,
    units_in_use,
    vocabulary_of,
)

DEFINITION = "component.interface[0].definition"
UNIT = f"{DEFINITION}.unit"


def built(tmp_path: Path, **files: Any) -> Index:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def speed(tmp_path: Path, reader_unit: str = "%") -> Index:
    return built(
        tmp_path,
        **{
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit=reader_unit)),
        },
    )


def stamps(tmp_path: Path, *names: str) -> dict[Path, str]:
    return {
        (tmp_path / name).resolve(): fingerprint((tmp_path / name).read_bytes()) for name in names
    }


class TestDeclarations:
    def test_every_declaration_is_listed_with_its_component_and_role(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        assert [(entry.component, entry.role) for entry in found] == [
            ("A", "produces"),
            ("B", "reads"),
        ]
        assert found[1].stated["unit"] == '"%"'
        assert found[1].stated["kind"] == '"measurement"'
        assert "typename" not in found[1].stated
        assert (found[1].type_name, dict(found[1].fixed)) == (None, {})

    def test_a_local_declaration_is_local(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("local", "Speed", unit="rpm"))}
        )
        assert [entry.role for entry in declarations_of(idx, "Speed", {})] == ["local"]

    def test_a_declaration_naming_a_type_carries_what_the_type_fixes(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
            },
        )
        (entry,) = declarations_of(idx, "Speed", {})
        assert entry.type_name == "Speed_t"
        assert entry.fixed["unit"] == '"rpm"'
        assert entry.fixed["datatype"] == '"uint16"'
        assert "limits" not in entry.fixed

    def test_a_type_the_project_does_not_declare_fixes_nothing(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", typename="Nowhere_t"))},
        )
        (entry,) = declarations_of(idx, "Speed", {})
        assert (entry.type_name, dict(entry.fixed)) == ("Nowhere_t", {})

    def test_a_declaration_its_file_no_longer_holds_is_left_out(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "Torque"))})
        assert [entry.component for entry in declarations_of(idx, "Speed", {})] == ["A"]

    def test_a_file_rewritten_without_a_name_or_a_scope_is_named_by_its_file(
        self, tmp_path: Path
    ) -> None:
        idx = speed(tmp_path)
        rewritten = {"component": {"interface": [{"definition": {"name": "Speed"}}]}}
        write_tree(tmp_path, {"b.ddd.json": rewritten})
        assert [(entry.component, entry.role) for entry in declarations_of(idx, "Speed", {})] == [
            ("A", "produces"),
            ("b", "reads"),
        ]


class TestFindings:
    def finding(self, path: Path, pointer: str | None) -> Diagnostic:
        location = None if pointer is None else Location(path, pointer)
        return Diagnostic("definition-mismatch", Severity.ERROR, "differs", location)

    def test_a_finding_on_a_declaration_or_under_it_is_located_on_it(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        b = tmp_path / "b.ddd.json"
        assert located_on(found, b, self.finding(b, "component.interface[0]"))
        assert located_on(found, b, self.finding(b, UNIT))
        assert located_on(found, b, self.finding(b, "component.interface[0][1]"))

    def test_a_finding_elsewhere_is_not(self, tmp_path: Path) -> None:
        found = declarations_of(speed(tmp_path), "Speed", {})
        b = tmp_path / "b.ddd.json"
        assert not located_on(found, b, self.finding(b, "component.interface[1]"))
        assert not located_on(found, b, self.finding(b, "component.interface[10]"))
        assert not located_on(found, tmp_path / "p.ddd.json", self.finding(b, UNIT))
        assert not located_on(found, b, self.finding(b, None))


class TestUnits:
    def test_the_units_in_use_are_counted_by_variable_most_used_first(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("output", "Torque", unit="Nm"),
                    declare("output", "Idle", unit="rpm"),
                    declare("output", "Plain", unit=""),
                    declare("output", "Bare"),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert units_in_use(idx) == (("rpm", 2), ("Nm", 1))

    def test_without_a_units_file_the_vocabulary_is_none(self) -> None:
        assert vocabulary_of([]) is None

    def test_a_vocabulary_lists_its_units_with_their_descriptions(self) -> None:
        declared = Document(
            json.dumps(
                {
                    "units": [
                        "rpm",
                        {"unit": "Nm", "description": "torque"},
                        {"unit": "degC", "description": 3},
                        {"description": "no unit here"},
                        7,
                    ]
                }
            )
        )
        broken = Document(json.dumps({"units": "rpm"}))
        assert vocabulary_of([declared, broken]) == (
            ("rpm", None),
            ("Nm", "torque"),
            ("degC", None),
        )


class TestPreview:
    def test_a_preview_is_the_edit_and_the_lines_it_changes(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        b = tmp_path / "b.ddd.json"
        before = b.read_bytes()
        (planned,) = preview(
            settle(idx, "Speed", "unit", '"rpm"', {}), "unit", stamps(tmp_path, "b.ddd.json")
        )
        lines = before.decode("utf-8").splitlines()
        line = next(number for number, text in enumerate(lines, 1) if '"unit": "%"' in text)
        assert planned.path.name == "b.ddd.json"
        assert planned.fingerprint == fingerprint(before)
        assert planned.operations == (Operation("set", UNIT, '"rpm"'),)
        assert planned.hunks == (
            Hunk(line, (lines[line - 1],), (lines[line - 1].replace('"%"', '"rpm"'),)),
        )
        assert b.read_bytes() == before

    def test_taking_a_key_out_is_a_removal(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        planned = preview(
            settle(idx, "Speed", "unit", None, {}),
            "unit",
            stamps(tmp_path, "a.ddd.json", "b.ddd.json"),
        )
        assert [(entry.path.name, entry.operations) for entry in planned] == [
            ("a.ddd.json", (Operation("remove", UNIT),)),
            ("b.ddd.json", (Operation("remove", UNIT),)),
        ]
        assert all(not any("unit" in text for text in entry.hunks[0].after) for entry in planned)

    def test_a_file_the_analysis_did_not_read_is_unreadable(self, tmp_path: Path) -> None:
        idx = speed(tmp_path)
        with pytest.raises(EditError) as refused:
            preview(settle(idx, "Speed", "unit", '"rpm"', {}), "unit", {})
        assert refused.value.code == UNREADABLE

    @pytest.mark.parametrize("damage", ["remove", "latin-1"])
    def test_a_file_that_can_no_longer_be_read_as_utf8_is_unreadable(
        self, tmp_path: Path, damage: str
    ) -> None:
        idx = speed(tmp_path)
        settlement = settle(idx, "Speed", "unit", '"rpm"', {})
        known = stamps(tmp_path, "b.ddd.json")
        b = tmp_path / "b.ddd.json"
        if damage == "remove":
            b.unlink()
        else:
            b.write_bytes(b"\xff\xfe not utf-8")
        with pytest.raises(EditError) as refused:
            preview(settlement, "unit", known)
        assert refused.value.code == UNREADABLE


class TestNarrowed:
    def test_a_declaration_already_meaning_the_value_has_nothing_to_change(
        self, tmp_path: Path
    ) -> None:
        idx = speed(tmp_path, reader_unit="rpm")
        declared = declarations_of(idx, "Speed", {})
        settlement = Settlement(tuple(Settled(entry.site, '"rpm"') for entry in declared), ())
        assert narrowed(settlement, "unit", declared).changes == ()

    def test_a_site_no_declaration_was_read_at_keeps_its_change(self, tmp_path: Path) -> None:
        """A miss is not agreement: nothing here read that declaration's own text, so the
        change it was given stays, rather than being dropped as one that changes nothing."""
        idx = speed(tmp_path)
        elsewhere = Settled(Site(tmp_path / "c.ddd.json", DEFINITION), '"rpm"')
        settlement = Settlement((elsewhere,), ())
        assert narrowed(settlement, "unit", declarations_of(idx, "Speed", {})).changes == (
            elsewhere,
        )


class TestRefusal:
    @pytest.mark.parametrize(
        ("reason", "code", "says"),
        [
            ("type", "fixed-by-type", "names the type 'Speed_t', which fixes its unit"),
            ("kind", "invalid", "is of a kind that does not allow that unit"),
            ("unreachable", "unreadable", "is no longer where the last analysis found it"),
        ],
    )
    def test_each_reason_has_its_code_and_names_the_declaration(
        self, reason: Any, code: str, says: str
    ) -> None:
        refused = Unsettled(Site(Path("/w/b.ddd.json"), DEFINITION), reason, "Speed_t")
        assert refusal(refused, "Speed", "unit") == (
            code,
            f"the declaration of 'Speed' in b.ddd.json {says}",
        )


def test_a_settlement_with_nothing_to_change_previews_nothing() -> None:
    assert preview(Settlement((), ()), "unit", {}) == ()
