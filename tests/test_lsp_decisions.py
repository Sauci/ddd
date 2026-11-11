"""The decision a settlement makes about one declaration."""

from __future__ import annotations

import copy
from pathlib import Path

from conftest import (
    DOUBLE_BESIDE_SCALED,
    FLOAT_BESIDE_ENUM,
    TEXT,
    UNIT_BESIDE_TEXT,
    built_of,
    component,
    declare,
    scalar_type,
    types,
)
from ddd.lsp.edits import _propagate, loading_problem, reconciliations, settled_at
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


class TestWhatTheModelsSay:
    """A declaration takes a value only if the definition, with it written, still loads.

    Storage and kind above are two rules the models hold; every other rule between keys - an
    enumeration wants an integer, a string wants a byte and no unit and one dimension - is theirs
    alone, and a key written against one leaves a file the loader refuses. Asked of the models,
    and answered ``load`` with their sentence rather than ``Settled``.
    """

    def test_a_value_the_definition_cannot_hold_beside_the_others_is_refused(
        self, tmp_path: Path
    ) -> None:
        built, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        reader = Site(root / "r.ddd.json", DEFINITION)
        refused = settled_at(built, reader, "V", "datatype", '"float32"', {})
        assert (refused.site, refused.reason) == (reader, "load")
        assert (
            refused.problem
            == "enum conversion 'Mode_t' requires an integer datatype, got 'float32'"
        )

    def test_a_key_taken_out_that_the_definition_cannot_do_without_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A kind that does not require a key does not say a string does: `dimensions` is the
        optional key of a measurement, and the one thing a string measurement needs."""
        built, root = built_of(tmp_path, **UNIT_BESIDE_TEXT)
        reader = Site(root / "r.ddd.json", DEFINITION)
        refused = settled_at(built, reader, "V", "dimensions", None, {})
        assert (refused.site, refused.reason) == (reader, "load")
        assert refused.problem is not None
        assert refused.problem.startswith("a string states exactly one dimension")

    def test_a_value_that_leaves_the_definition_loading_is_taken(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        reader = Site(root / "r.ddd.json", DEFINITION)
        decided = settled_at(built, reader, "V", "conversion", '{"kind": "identity"}', {})
        assert (decided.site, decided.raw) == (reader, '{"kind": "identity"}')

    def test_the_panel_settles_what_the_models_refuse_and_says_so_elsewhere(
        self, tmp_path: Path
    ) -> None:
        """The reader chose the value; the page plans it and says that the file will not load
        (``ddd.variables.unloadable``) where a button for it is withheld."""
        built, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        reader = Site(root / "r.ddd.json", DEFINITION)
        decided = settled_at(built, reader, "V", "datatype", '"float32"', {}, withholding=False)
        assert (decided.site, decided.raw) == (reader, '"float32"')

    def test_the_rules_asked_first_keep_their_own_reasons(self, tmp_path: Path) -> None:
        """Storage and kind say why in a sentence of the panel's own, which an answer from the
        models would replace with theirs: they are asked first."""
        built, root = built_of(tmp_path, **UNIT_BESIDE_TEXT)
        reader = Site(root / "r.ddd.json", DEFINITION)
        assert settled_at(built, reader, "V", "datatype", None, {}).reason == "storage"
        assert settled_at(built, reader, "V", "size", "4", {}).reason == "kind"

    def test_what_is_asked_is_the_definition_as_the_key_leaves_it(self, tmp_path: Path) -> None:
        """Not the definition as it stands: the reader reads text and states no unit, so it
        loads - until the writer's unit is given to it."""
        _, root = built_of(tmp_path, **UNIT_BESIDE_TEXT)
        document = read(root / "r.ddd.json", {})
        before = copy.deepcopy(document.value_at(DEFINITION))
        assert loading_problem(document, DEFINITION, "volatile", "false") is None
        assert (
            loading_problem(document, DEFINITION, "unit", '"rpm"')
            == "a string has no unit, got 'rpm'"
        )
        assert loading_problem(document, DEFINITION, "unit", None) is None
        assert loading_problem(document, DEFINITION, "dimensions", None) is not None
        assert document.value_at(DEFINITION) == before, "what is asked about is not changed"

    def test_a_key_stated_as_null_is_replaced_like_any_other(self, tmp_path: Path) -> None:
        stated = component(
            "R", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8], unit=None)
        )
        _, root = built_of(tmp_path, **{"r.ddd.json": stated})
        document = read(root / "r.ddd.json", {})
        assert (
            loading_problem(document, DEFINITION, "unit", '"rpm"')
            == "a string has no unit, got 'rpm'"
        )
        assert loading_problem(document, DEFINITION, "unit", None) is None


class TestWhatTheAnalysisSays:
    """The models take a definition whose derived limits are not finite, and the analysis files
    it as ``schema`` all the same - from the definition alone. A declaration does not take the
    value that leaves it so, and the sentence is the analysis's own."""

    LIMITS = "the limits derived from 'float64' and this conversion are not finite"

    def test_a_datatype_that_makes_the_limits_infinite_is_refused(self, tmp_path: Path) -> None:
        """The first fix of the reader: the writer's double under the reader's factor of two."""
        built, root = built_of(tmp_path, **DOUBLE_BESIDE_SCALED)
        reader = Site(root / "r.ddd.json", DEFINITION)
        refused = settled_at(built, reader, "V", "datatype", '"float64"', {})
        assert (refused.site, refused.reason, refused.problem) == (reader, "load", self.LIMITS)

    def test_a_conversion_that_makes_the_limits_infinite_is_refused(self, tmp_path: Path) -> None:
        """The other way: the reader's factor of two over the writer's double."""
        built, root = built_of(tmp_path, **DOUBLE_BESIDE_SCALED)
        writer = Site(root / "w.ddd.json", DEFINITION)
        raw = '{"kind": "linear", "factor": 2}'
        refused = settled_at(built, writer, "V", "conversion", raw, {})
        assert (refused.site, refused.reason, refused.problem) == (writer, "load", self.LIMITS)

    def test_a_value_that_keeps_the_limits_finite_is_taken(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **DOUBLE_BESIDE_SCALED)
        reader = Site(root / "r.ddd.json", DEFINITION)
        decided = settled_at(built, reader, "V", "conversion", '{"kind": "identity"}', {})
        assert (decided.site, decided.raw) == (reader, '{"kind": "identity"}')

    def test_the_panel_settles_it_all_the_same(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **DOUBLE_BESIDE_SCALED)
        reader = Site(root / "r.ddd.json", DEFINITION)
        decided = settled_at(built, reader, "V", "datatype", '"float64"', {}, withholding=False)
        assert (decided.site, decided.raw) == (reader, '"float64"')

    def test_what_is_asked_is_the_definition_as_the_key_leaves_it(self, tmp_path: Path) -> None:
        """Not the definition as it stands: the reader loads, and stops loading with the double."""
        _, root = built_of(tmp_path, **DOUBLE_BESIDE_SCALED)
        document = read(root / "r.ddd.json", {})
        assert loading_problem(document, DEFINITION, "volatile", "false") is None
        assert loading_problem(document, DEFINITION, "datatype", '"float64"') == self.LIMITS
        assert loading_problem(document, DEFINITION, "datatype", '"float32"') is None


class TestAValueTheLoaderWouldRefuseAsJson:
    """A value is the text of one declaration, and an editor's buffer or a file on disk is read as
    python reads json, which takes what the loader refuses: a key written twice, ``NaN``. Writing
    that text into another declaration is a file the loader refuses as ``json-syntax``, so it is
    said as the problem it is and not raised, which ended the language server's run."""

    def test_a_key_written_twice_is_said_and_not_raised(self, tmp_path: Path) -> None:
        _, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        document = read(root / "r.ddd.json", {})
        problem = loading_problem(document, DEFINITION, "limits", '{"min": 0, "max": 5, "max": 6}')
        assert problem == (
            "key 'max' appears twice in one object; json would silently keep the last spelling, "
            "so decide which one stays"
        )

    def test_a_constant_json_has_no_spelling_for_is_said_and_not_raised(
        self, tmp_path: Path
    ) -> None:
        _, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        document = read(root / "r.ddd.json", {})
        problem = loading_problem(document, DEFINITION, "limits", '{"min": 0, "max": NaN}')
        assert problem == "'NaN' is not valid json; DDD has no representation for it"

    def test_a_declaration_is_refused_the_value_with_the_reason_load(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **FLOAT_BESIDE_ENUM)
        reader = Site(root / "r.ddd.json", DEFINITION)
        typed = '{"kind": "linear", "factor": 2, "factor": 3}'
        refused = settled_at(built, reader, "V", "conversion", typed, {})
        assert (refused.site, refused.reason) == (reader, "load")
        assert refused.problem is not None
        assert refused.problem.startswith("key 'factor' appears twice in one object")


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
