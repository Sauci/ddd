"""The fixes a finding of ``ddd gui`` carries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import built_of, component, declare, project, write_tree
from ddd.finding_fixes import fixes_for
from ddd.lsp.edits import settle

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
        (edit,) = offered[0].changes
        (operation,) = edit.operations
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
        assert first.changes[0].operations[0].raw != second.changes[0].operations[0].raw

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
        assert fix.changes[0].operations[0].pointer == f"{DEFINITION}.id"

    def test_a_lone_declaration_has_nothing_to_reconcile(self, tmp_path: Path) -> None:
        # A variable one component declares has no mismatch and no fix: there is nobody to
        # disagree with.
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built) == ()

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


class TestAMismatch:
    def test_a_consumer_is_offered_the_producer_s_value(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == ["Use the unit declared in a"]
        (edit,) = offered[0].changes
        assert edit.path == root / "b.ddd.json"
        assert [(o.op, o.pointer, o.raw) for o in edit.operations] == [
            ("set", f"{DEFINITION}.unit", '"rpm"')
        ]

    def test_the_producer_is_offered_its_own_value_outward(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        offered = fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == [
            "Apply this unit to 2 other declarations of 'Speed'"
        ]
        assert {edit.path.name for edit in offered[0].changes} == {"b.ddd.json", "c.ddd.json"}

    def test_two_keys_disagreeing_are_two_fixes(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm", datatype="uint16")
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", unit="Hz", datatype="uint8")
                ),
            },
        )
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == [
            "Use the datatype declared in a",
            "Use the unit declared in a",
        ]

    def test_a_declaration_that_cannot_take_the_value_stops_the_fix_being_offered(
        self, tmp_path: Path
    ) -> None:
        # The natural way to block a key is a declared type that fixes it - but any fixture
        # that names one this way also states no `datatype` (a type and a base datatype are
        # mutually exclusive), which makes the plain declarations' own `datatype` look "missing"
        # from it too and offers a *second*, unrelated fix that turns out to be its own defect
        # (see the report: `settled_at` does not know `datatype` is fixed by a type - only
        # `unit`, `conversion` and `limits` are `MEANING_KEYS` - so it would write `datatype`
        # right beside `typename`, which the schema refuses). That defect belongs to
        # `ddd.lsp.edits.settled_at`, outside this module, and is reported rather than patched
        # here. What this test isolates instead is the guarantee `_reconciled` itself owns: a
        # settlement that cannot reach every declaration is dropped rather than offered - shown
        # here the way a file can genuinely go out of reach, by drifting after the index was
        # built, the same as a concurrent edit would leave it.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        path_c = root / "c.ddd.json"
        path_c.write_text(
            path_c.read_text(encoding="utf-8").replace('"Speed"', '"Other"', 1),
            encoding="utf-8",
            newline="",
        )
        # Asserted first, so this cannot pass by the fixture quietly having no mismatch at all:
        # `c` really is the declaration that cannot move, and `b` really is the one that would.
        settlement = settle(built, "Speed", "unit", '"rpm"', {})
        assert [change.site.path.name for change in settlement.changes] == ["b.ddd.json"]
        assert [(u.site.path.name, u.reason) for u in settlement.unsettled] == [
            ("c.ddd.json", "unreachable")
        ]
        # Queried at `a`, the sole producer: with nobody else producing, the only candidate for
        # `unit` is sending its own value out to both other declarations - and that is exactly
        # the settlement just shown above cannot reach `c`.
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built) == ()

    def test_a_check_with_no_fix_at_all_carries_nothing(self, tmp_path: Path) -> None:
        # Neither of the two checks this module knows: not `missing-id`'s pointer-and-cache
        # walk, not `definition-mismatch`'s reconciliations - the plain fallthrough every other
        # check answers with.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        assert fixes_for("unknown-unit", root / "a.ddd.json", DEFINITION, {}, built) == ()
