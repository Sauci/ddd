"""The decision a settlement makes about one declaration."""

from __future__ import annotations

from pathlib import Path

from conftest import built_of, component, declare, scalar_type, types
from ddd.lsp.edits import _propagate, reconciliations, settled_at
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read

DEFINITION = "component.interface[0].definition"


def drifted(tmp_path: Path) -> tuple[Index, Site, Site]:
    """One component having adopted the project's scalar type and the other not.

    The ordinary drift this tool is for, and the shape in which what a declaration *states* and
    what it *resolves to* part company: `a` says `Speed_t` and means uint16 in rpm, `b` says
    uint16 in Hz and means it. Every decision below is about a key one of them holds through its
    type, which reads as silence in its file.
    """
    built, root = built_of(
        tmp_path,
        **{
            "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
            "b.ddd.json": component("B", declare("input", "Speed", datatype="uint16", unit="Hz")),
            "t.ddd.json": types(scalar_type("Speed_t", datatype="uint16", unit="rpm")),
        },
    )
    return built, Site(root / "a.ddd.json", DEFINITION), Site(root / "b.ddd.json", DEFINITION)


class TestWhatATypeFixes:
    """A declaration naming a declared type is silent in its file about every key the type
    states - `FIXED_BY_A_TYPE`, the storage as much as the meaning - and not silent at all about
    the variable. Answering `Settled` for one of those keys offers a file the loader refuses.
    """

    def test_the_datatype_a_type_fixes_is_refused_beside_it(self, tmp_path: Path) -> None:
        built, a, _ = drifted(tmp_path)
        refused = settled_at(built, a, "Speed", "datatype", '"sint16"', {})
        assert (refused.site, refused.reason, refused.type_name) == (a, "type", "Speed_t")

    def test_the_datatype_a_type_fixes_is_already_what_it_means(self, tmp_path: Path) -> None:
        # Nothing to do rather than refused: the declaration already means uint16, through the
        # type, so writing one beside the `typename` would settle nothing and break the file.
        built, a, _ = drifted(tmp_path)
        assert settled_at(built, a, "Speed", "datatype", '"uint16"', {}) is None

    def test_a_key_the_type_states_cannot_be_removed_here(self, tmp_path: Path) -> None:
        # How a removal that settled nothing used to be offered: `a` states no `unit` of its own,
        # so removing the unit "everywhere" left `a` still meaning rpm and the mismatch standing.
        built, a, _ = drifted(tmp_path)
        refused = settled_at(built, a, "Speed", "unit", None, {})
        assert (refused.site, refused.reason) == (a, "type")


class TestWhatItsStorageNeeds:
    """A definition names its storage exactly once, and a base datatype comes with its
    conversion: two rules the models check after the fact, which no kind's field list expresses
    and which every one of these changes would break.
    """

    def test_a_typename_is_refused_where_a_datatype_is_stated(self, tmp_path: Path) -> None:
        built, _, b = drifted(tmp_path)
        refused = settled_at(built, b, "Speed", "typename", '"Speed_t"', {})
        assert (refused.site, refused.reason) == (b, "storage")

    def test_the_datatype_in_use_cannot_be_taken_away(self, tmp_path: Path) -> None:
        built, _, b = drifted(tmp_path)
        refused = settled_at(built, b, "Speed", "datatype", None, {})
        assert (refused.site, refused.reason) == (b, "storage")

    def test_the_conversion_a_datatype_comes_with_cannot_be_taken_away(
        self, tmp_path: Path
    ) -> None:
        built, _, b = drifted(tmp_path)
        refused = settled_at(built, b, "Speed", "conversion", None, {})
        assert (refused.site, refused.reason) == (b, "storage")

    def test_the_typename_in_use_cannot_be_taken_away(self, tmp_path: Path) -> None:
        # The other side of the pair, and the one key of it a type does not fix for itself: `a`
        # left with neither a `typename` nor a `datatype` names no storage at all.
        built, a, _ = drifted(tmp_path)
        refused = settled_at(built, a, "Speed", "typename", None, {})
        assert (refused.site, refused.reason) == (a, "storage")

    def test_a_key_that_is_not_storage_is_settled_as_before(self, tmp_path: Path) -> None:
        # The guard reaches only the storage pair: `b` may still lose its unit, which is what
        # makes the four refusals above about the pair rather than about removals.
        built, _, b = drifted(tmp_path)
        decided = settled_at(built, b, "Speed", "unit", None, {})
        assert (decided.site, decided.raw) == (b, None)


class TestOneDeclaration:
    def test_a_declaration_that_can_take_the_value_takes_it(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        site = Site(root / "b.ddd.json", "component.interface[0].definition")
        cache: dict[Path, Document] = {}
        decided = settled_at(built, site, "Speed", "unit", '"rpm"', cache)
        assert decided is not None
        assert (decided.site, decided.raw) == (site, '"rpm"')

    def test_a_declaration_that_already_means_it_does_nothing(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))},
        )
        site = Site(root / "a.ddd.json", "component.interface[0].definition")
        assert settled_at(built, site, "Speed", "unit", '"rpm"', {}) is None


class TestWhatTheSpellingRefuses:
    """`_assign` and `_erase` kept their own refusals for a kind that does not accept the key,
    a named type that fixes it, and the one member of an object - the first two now made
    for the three single-declaration builders by :func:`settled_at` instead, before either
    is ever called. Tested here directly, the way the suite already tests the third: nothing
    left in `_on_the_declaration`'s call graph still asks `_assign` a question `settled_at`
    has not already asked, or asks `_erase` anything but the one question that stayed.
    """

    def test_a_kind_that_does_not_accept_the_key_refuses_it(self) -> None:
        from ddd.lsp.edits import _assign

        document = Document('{"component": {"interface": [{"definition": {}}]}}')
        assert _assign(document, "component.interface[0].definition", "unit", '"rpm"') is None

    def test_a_named_type_fixing_the_key_refuses_it(self) -> None:
        from ddd.lsp.edits import _assign

        document = Document(
            '{"component": {"interface": [{"definition": '
            '{"kind": "measurement", "typename": "Speed_t"}}]}}'
        )
        assert _assign(document, "component.interface[0].definition", "unit", '"rpm"') is None

    def test_a_reconciliation_erase_cannot_spell_offers_no_edit(self, tmp_path: Path) -> None:
        """`settled_at` does not read how many members a definition has, so a removal it
        settles can still be one `_erase` refuses - the guard :func:`_protocol_action`'s own
        docstring says stays in the spelling. Offered with nothing to change rather than not
        offered at all, exactly as a change `_erase` refuses for any other reason would be."""
        from ddd.lsp.edits import QUICK_FIX, Reconciliation, Settled, Settlement, _protocol_action

        document = Document('{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}')
        site = Site(tmp_path / "a.ddd.json", "component.interface[0].definition")
        reconciliation = Reconciliation(
            "Remove this unit", "unit", Settlement((Settled(site, None),), ())
        )
        assert _protocol_action(reconciliation, {site.path: document}) == {
            "title": "Remove this unit",
            "kind": QUICK_FIX,
            "edit": {"changes": {}},
        }


class TestTheOtherDeclarations:
    def test_a_value_sent_out_names_every_declaration_that_takes_it(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        here = Site(root / "a.ddd.json", "component.interface[0].definition")
        document = read(here.path, {})
        decision = _propagate(built, here, document, "Speed", "unit", {})
        assert decision is not None
        assert decision.title == "Apply this unit to 2 other declarations of 'Speed'"
        assert {change.site.path.name for change in decision.settlement.changes} == {
            "b.ddd.json",
            "c.ddd.json",
        }
        assert all(change.raw == '"rpm"' for change in decision.settlement.changes)


class TestReconciliations:
    """`reconciliations` repeats the two guards `_on_the_declaration` already made before ever
    calling it, so that the function reads the same whichever caller reaches it - the editor,
    through `_on_the_declaration`, or the page, directly. That duplication means neither guard
    is reachable through `actions()` any more: `_on_the_declaration` already returned before
    `reconciliations` is called, for both a pointer outside a definition and one whose
    declaration states no name. Covered here the way `TestOneDeclaration` covers `settled_at`
    directly, rather than only through whatever caller happens to reach it today.
    """

    def test_outside_a_definition_nothing_is_settled(self, tmp_path: Path) -> None:
        document = Document('{"component": {"interface": [{"definition": {"name": "S"}}]}}')
        assert (
            reconciliations(Index(), tmp_path / "a.ddd.json", document, "component.name", {}) == []
        )

    def test_a_declaration_with_no_name_settles_nothing(self, tmp_path: Path) -> None:
        document = Document('{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}')
        assert (
            reconciliations(
                Index(),
                tmp_path / "a.ddd.json",
                document,
                "component.interface[0].definition",
                {},
            )
            == []
        )
