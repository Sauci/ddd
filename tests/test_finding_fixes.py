"""The fixes a finding of ``ddd gui`` carries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import component, declare, project, write_tree
from ddd.finding_fixes import fixes_for

DEFINITION = "component.interface[0].definition"


def tree(tmp_path: Path, **files: Any) -> Path:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    return tmp_path


class TestAnIdentity:
    def test_a_producing_declaration_without_one_is_offered_an_id(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        offered = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})
        assert [fix.title for fix in offered] == ["Give 'Speed' an id"]
        (operation,) = offered[0].operations
        assert (operation.op, operation.pointer) == ("set", f"{DEFINITION}.id")
        assert len(json.loads(operation.raw or '""')) == 12

    def test_two_asks_propose_two_ids(self, tmp_path: Path) -> None:
        # `ddd.identity` generates a fresh id per call, which is why a caller applies the
        # answer it was given rather than asking again.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        first = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})[0]
        second = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})[0]
        assert first.operations[0].raw != second.operations[0].raw

    def test_a_declaration_that_has_an_id_is_offered_nothing(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm", id="abc123def456")
                )
            },
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_a_declaration_that_reads_the_variable_is_offered_nothing(self, tmp_path: Path) -> None:
        # An identity belongs to whoever produces the object; a reader states none.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("input", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_an_id_stated_as_null_is_replaced_rather_than_added(self, tmp_path: Path) -> None:
        # What `ddd dump` writes for an unstamped object, and what `missing-id` reports too.
        root = tree(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm", id=None))},
        )
        (fix,) = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})
        assert fix.operations[0].pointer == f"{DEFINITION}.id"

    def test_another_check_carries_no_fix(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_a_pointer_naming_no_declaration_carries_no_fix(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", "component.name", {}) == ()

    def test_a_declaration_whose_name_is_not_a_name_carries_no_fix(self, tmp_path: Path) -> None:
        # The file moved on since the analysis: the fix's own title would have nothing to say.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        path = root / "a.ddd.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace('"name": "Speed"', '"name": 3', 1),
            encoding="utf-8",
            newline="",
        )
        assert fixes_for("missing-id", path, DEFINITION, {}) == ()
