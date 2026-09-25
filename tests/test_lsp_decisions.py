"""The decision a settlement makes about one declaration."""

from __future__ import annotations

from pathlib import Path

from conftest import built_of, component, declare
from ddd.lsp.edits import settled_at
from ddd.lsp.navigation import Site
from ddd.lsp.ranges import Document


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
