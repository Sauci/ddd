"""The fixes a finding of ``ddd gui`` carries."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import built_of, component, declare, scalar_type, types
from ddd.finding_fixes import fixes_for
from ddd.lsp.edits import reconciliations, settle
from ddd.lsp.ranges import read

DEFINITION = "component.interface[0].definition"


class TestAnIdentity:
    def test_a_producing_declaration_without_one_is_offered_an_id(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        offered = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == ["Give 'Speed' an id"]
        (edit,) = offered[0].changes
        (operation,) = edit.operations
        assert (operation.op, operation.pointer) == ("set", f"{DEFINITION}.id")
        assert len(json.loads(operation.raw or '""')) == 12

    def test_two_asks_propose_two_ids(self, tmp_path: Path) -> None:
        # `ddd.identity` generates a fresh id per call, which is why a caller applies the
        # answer it was given rather than asking again.
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        first = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built)[0]
        second = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built)[0]
        assert first.changes[0].operations[0].raw != second.changes[0].operations[0].raw

    def test_a_declaration_that_has_an_id_is_offered_nothing(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm", id="abc123def456")
                )
            },
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built) == ()

    def test_a_declaration_that_reads_the_variable_is_offered_nothing(self, tmp_path: Path) -> None:
        # An identity belongs to whoever produces the object; a reader states none.
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("input", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built) == ()

    def test_an_id_stated_as_null_is_replaced_rather_than_added(self, tmp_path: Path) -> None:
        # What `ddd dump` writes for an unstamped object, and what `missing-id` reports too.
        built, root = built_of(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm", id=None))},
        )
        (fix,) = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}, built)
        assert fix.changes[0].operations[0].pointer == f"{DEFINITION}.id"

    def test_a_lone_declaration_has_nothing_to_reconcile(self, tmp_path: Path) -> None:
        # A variable one component declares has no mismatch and no fix: there is nobody to
        # disagree with.
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        # Pinned first, like every `== ()` case below it: empty because there is nothing to
        # reconcile at all, not because a settlement failed or an owner could not be found.
        document = read(root / "a.ddd.json", {})
        assert reconciliations(built, root / "a.ddd.json", document, DEFINITION, {}) == []
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built) == ()

    def test_a_pointer_naming_no_declaration_carries_no_fix(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", "component.name", {}, built) == ()

    def test_a_declaration_whose_name_is_not_a_name_carries_no_fix(self, tmp_path: Path) -> None:
        # The file moved on since the analysis: the fix's own title would have nothing to say.
        built, root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        path = root / "a.ddd.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace('"name": "Speed"', '"name": 3', 1),
            encoding="utf-8",
            newline="",
        )
        assert fixes_for("missing-id", path, DEFINITION, {}, built) == ()


class TestAMismatch:
    def test_a_consumer_is_offered_the_producer_s_value(self, tmp_path: Path) -> None:
        # One consumer: the count pinned at this end of the pair with
        # `test_a_consumer_s_fix_reaches_every_other_declaration_too` below - `(edit,) =
        # ...changes` would itself raise if this ever widened to more than one file.
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

    def test_a_consumer_s_fix_reaches_every_other_declaration_too(self, tmp_path: Path) -> None:
        # The reach is the whole variable, not the declaration the finding happened to be filed
        # on. `b` and `c` both disagree with the producer `a`; pressing the button on `b`'s own
        # finding must also clear `c`'s, or the page would leave a sibling finding behind the
        # spec says one press should settle. `_from_producer` (the editor's own, untouched)
        # changes only the declaration under the cursor - right for a cursor, wrong for a
        # finding - so `reconciliations` widens the kept `taken` action across the variable
        # before handing it back.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="kPa")),
            },
        )
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == ["Use the unit declared in a"]
        # An exact set, not a superset check: this is what pins the producer *out*.
        assert {edit.path.name for edit in offered[0].changes} == {"b.ddd.json", "c.ddd.json"}

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

    def test_a_variable_with_two_producers_is_offered_nothing(self, tmp_path: Path) -> None:
        # The case `examples/inconsistent` is: `SharedValue` written by two components. There is
        # no producer whose value is *the* producer's, so `taken` (`_from_producer`) refuses -
        # but nothing about `given` (`_propagate`) asks who produces, and queried at `c` it
        # would happily offer to overwrite *both* correct, agreeing producers with `c`'s own,
        # disagreeing value. That is what `owned=True` exists to stop: the first of the pair if
        # it exists, and otherwise nothing - never falling through to the second.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        # Asserted first, so this cannot pass because the fixture quietly has nothing to offer
        # at all: unowned, `reconciliations` really does offer the dangerous direction here -
        # the editor still shows it, letting a reader who understands it decide for themselves.
        document = read(root / "c.ddd.json", {})
        unowned = reconciliations(built, root / "c.ddd.json", document, DEFINITION, {})
        assert [decision.title for decision in unowned] == [
            "Apply this unit to 2 other declarations of 'Speed'"
        ]
        assert fixes_for("definition-mismatch", root / "c.ddd.json", DEFINITION, {}, built) == ()

    def test_a_producer_with_only_the_taking_direction_offers_nothing(self, tmp_path: Path) -> None:
        # The mirror image of the case above, on the giving side instead of the taking side.
        # `a` is the sole producer, so the no-single-producer guard does not apply here - this
        # isolates the other guard, the one inside the per-key loop. `b` reads `Speed` and names
        # a type that fixes `unit` to a value `a` does not state, so `a`'s own value cannot be
        # sent to `b` at all (`given` is blocked) - but `a` stating no unit is something `b`'s
        # type does not contradict, so `a` *could* adopt that silence (`taken` exists, via
        # `_remove_here`). A producer's finding owns the giving direction, not the taking one;
        # asked unowned, `a` is still offered that button - asked the way the page asks, nothing
        # is, rather than quietly falling through to the direction it does not own.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", typename="Speed_t")),
                "t.ddd.json": types(scalar_type("Speed_t", unit="kPa")),
            },
        )
        unit = f"{DEFINITION}.unit"
        document = read(root / "a.ddd.json", {})
        unowned = reconciliations(built, root / "a.ddd.json", document, unit, {})
        assert [decision.title for decision in unowned] == [
            "Remove this unit, which no other declaration of 'Speed' has"
        ]
        assert fixes_for("definition-mismatch", root / "a.ddd.json", unit, {}, built) == ()

    def test_two_producers_disagreeing_with_each_other_are_offered_nothing(
        self, tmp_path: Path
    ) -> None:
        # No consumer at all, just the dispute the ownership rule has no standing to settle:
        # `a` and `b` both produce `Speed` and state different units. Queried at either, `given`
        # succeeds (each can push its own value onto the other) and, with exactly one *other*
        # producer to source from, so does `taken` - unowned, both directions are offered, each
        # a button that overwrites the other file. `owned=True` now refuses before the per-key
        # loop even starts, because `built.producers.get("Speed")` has two entries, not one.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="Hz")),
            },
        )
        document = read(root / "b.ddd.json", {})
        unowned = reconciliations(built, root / "b.ddd.json", document, DEFINITION, {})
        assert [decision.title for decision in unowned] == [
            "Apply this unit to 1 other declaration of 'Speed'",
            "Use the unit declared in a",
        ]
        assert fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built) == ()

    def test_no_producer_at_all_is_offered_nothing(self, tmp_path: Path) -> None:
        # The other half of "no single producer": nobody, not several. Two components both
        # *read* `Speed` and disagree about its unit - `missing-producer` is `examples/
        # inconsistent`'s own name for this, filed on `MissingValue` there, and it does not
        # stop `definition-mismatch` from also being filed between the readers. Queried at `a`,
        # `given` still succeeds (nothing about `_propagate` asks whether anyone produces the
        # variable at all), so unowned this offers a button that overwrites `b` with `a`'s own,
        # equally unowned, value. `built.producers.get("Speed")` is empty - zero entries, still
        # not one - so `owned=True` refuses here the same way it does for two.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("input", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        assert built.producers.get("Speed") is None
        document = read(root / "a.ddd.json", {})
        unowned = reconciliations(built, root / "a.ddd.json", document, DEFINITION, {})
        assert [decision.title for decision in unowned] == [
            "Apply this unit to 1 other declaration of 'Speed'"
        ]
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built) == ()

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
