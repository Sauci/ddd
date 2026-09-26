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
        # The case `examples/inconsistent` is: `SharedValue` written by two components. `a` and
        # `b` agree the way silence agrees - neither states `unit` at all - so `c`, the one
        # declaration that does state it, is where the mismatch shows and where `_from_producer`
        # refuses: there is no producer whose value is *the* producer's. Unowned, `c` is still
        # offered *both* other directions: `_remove_here` (nobody else states it, so match their
        # silence) and `_propagate` (spread `c`'s own value to both of them) - each as dangerous
        # as the other, since neither producer is *the* one to defer to. Note what this is not:
        # a fixture where `a`/`b` explicitly state the *same* value as each other would leave
        # `_from_producer`'s own producer-count check as the only thing blocking `taken` here,
        # which holds with or without `owned`'s own guard and would not prove this guard does
        # anything - checked by deleting the guard and re-running this exact fixture before
        # writing the assertion below, not by reasoning about it.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("output", "Speed")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        # Asserted first, so this cannot pass because the fixture quietly has nothing to offer
        # at all: unowned, `reconciliations` really does offer the dangerous directions here -
        # the editor still shows them, letting a reader who understands it decide for themselves.
        document = read(root / "c.ddd.json", {})
        unowned = reconciliations(built, root / "c.ddd.json", document, DEFINITION, {})
        assert [decision.title for decision in unowned] == [
            "Remove this unit, which no other declaration of 'Speed' has",
            "Apply this unit to 2 other declarations of 'Speed'",
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
        # The other half of "no single producer": nobody, not several. `missing-producer` is
        # `examples/inconsistent`'s own name for a variable with no producer at all, filed on
        # `MissingValue` there, and it does not stop `definition-mismatch` from also being filed
        # between readers who disagree. `b` states nothing, so `a` (the one that does state it)
        # is where `_remove_here` fires - "nobody else has it" is true whether that is because
        # nobody produces the variable or because everyone who could differs some other way, and
        # this fixture is built to isolate the first. A fixture where `b` states a *conflicting*
        # value instead of nothing would leave `_remove_here` blocked on its own terms (somebody
        # else *does* state the key) and `_adopt` blocked on its own (`a` already states one) -
        # neither reaching this guard at all, which is exactly the shape the reviewer's re-review
        # found this test's comment claiming a pin it did not make. Checked by deleting the guard
        # and re-running both shapes, not by reasoning about which one would go red.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("input", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert built.producers.get("Speed") is None
        document = read(root / "a.ddd.json", {})
        unowned = reconciliations(built, root / "a.ddd.json", document, DEFINITION, {})
        assert [decision.title for decision in unowned] == [
            "Remove this unit, which no other declaration of 'Speed' has",
            "Apply this unit to 1 other declaration of 'Speed'",
        ]
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built) == ()

    def test_adopting_the_readers_consensus_is_not_offered_under_ownership(
        self, tmp_path: Path
    ) -> None:
        # `a` is the sole producer and states no `unit`; `b` disagrees with `c` about `datatype`,
        # which is what files the mismatch here - on `datatype`, not `unit` - but a finding's
        # pointer names the whole definition, so `reconciliations` walks every reconcilable key
        # of `b`, not only the one the finding is about. For `unit`, `_from_producer` refuses (the
        # producer states nothing to take), and unowned the editor would still offer `_adopt`:
        # `b` and `c` (the other declarations) do not actually agree with each other here - only
        # `c` states a unit at all - but `_adopt` only requires the ones that *do* state something
        # to agree, and one is trivially one. Widening that adopted value would write `unit` into
        # `a`, the producer, which never asked for one: a reader taking what *readers* agree on
        # over a silent owner, exactly what the ownership rule exists to refuse. Unowned still
        # offers it, because the editor is not making this specific finding's request - a human
        # reading the lightbulb decides; the page, asked for this one finding, must not.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", datatype="uint16")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        document = read(root / "b.ddd.json", {})
        unowned = reconciliations(built, root / "b.ddd.json", document, DEFINITION, {})
        assert "Take the unit the other declarations of 'Speed' state" in [
            decision.title for decision in unowned
        ]
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == ["Use the datatype declared in a"]
        assert "a.ddd.json" not in {edit.path.name for fix in offered for edit in fix.changes}

    def test_a_mismatch_between_a_type_and_a_base_datatype_offers_nothing(
        self, tmp_path: Path
    ) -> None:
        # One component has adopted the project's scalar type and the other has not, which is
        # the shape in which what a declaration states and what it resolves to part company: `a`
        # is silent in its file about the datatype, the conversion and the unit, and means all
        # three through `Speed_t`. Read as silence, that offered six one-click buttons across the
        # two mirrored rows, five of which wrote a file the loader then refused - a `typename`
        # beside a `datatype`, either storage key taken away, the conversion a datatype comes
        # with taken away - and the sixth removed `b`'s unit and left the mismatch standing.
        # `settled_at` now reads both rules, so every one of them is withheld: settling this
        # takes more than one key at a time, and the reader follows the panel link the finding
        # already carries.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", datatype="uint16", unit="Hz")
                ),
                "t.ddd.json": types(scalar_type("Speed_t", datatype="uint16", unit="rpm")),
            },
        )
        for name in ("a.ddd.json", "b.ddd.json"):
            assert fixes_for("definition-mismatch", root / name, DEFINITION, {}, built) == ()
        # And not because there is nothing to report: the unit really does disagree, through the
        # type, which is what the panel this finding links to settles a key at a time.
        assert settle(built, "Speed", "unit", '"rpm"', {}).unsettled == ()

    def test_a_declaration_that_cannot_take_the_value_stops_the_fix_being_offered(
        self, tmp_path: Path
    ) -> None:
        # The natural way to block a key is a declared type that fixes it - which the test above
        # now does, since `settled_at` learnt that a type fixes the storage as well as what it
        # means. What this test isolates instead is the guarantee `_reconciled` itself owns: a
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
