"""Where each finding of ``ddd gui`` leads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args, get_type_hints

import pytest

from conftest import EXAMPLES, component, declare, project, scalar_type, types, write_tree
from ddd.finding_routes import Route, route_of
from ddd.gui.contract import FindingRoute
from ddd.lsp.ranges import Document

DEFINITION = "component.interface[0].definition"


def built(tmp_path: Path, **files: Any) -> Path:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    return tmp_path


@pytest.fixture
def structures() -> Path:
    return EXAMPLES / "structures"


@pytest.fixture
def demo() -> Path:
    return EXAMPLES / "demo"


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


class TestRoutes:
    def test_a_finding_inside_a_declaration_leads_to_its_variable(self, tmp_path: Path) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "definition-mismatch", root / "a.ddd.json", DEFINITION, "component", True, {}
        )
        assert route == Route(kind="variable", name="Speed")

    def test_a_finding_deep_inside_a_declaration_leads_to_the_same_variable(
        self, tmp_path: Path
    ) -> None:
        # `limits-out-of-range` is filed on the range itself, not on the definition.
        root = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                )
            },
        )
        route = route_of(
            "limits-out-of-range",
            root / "a.ddd.json",
            f"{DEFINITION}.limits.max",
            "component",
            True,
            {},
        )
        assert route == Route(kind="variable", name="Speed")

    def test_a_finding_missing_a_producer_leads_to_its_variable(self, tmp_path: Path) -> None:
        # `missing-producer` is filed on the consumer's own declaration, not its definition:
        # `DeclarationRef.location()` with no suffix gives the bare `component.interface[0]`.
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("input", "Speed", unit="rpm"))}
        )
        route = route_of(
            "missing-producer", root / "a.ddd.json", "component.interface[0]", "component", True, {}
        )
        assert route == Route(kind="variable", name="Speed")

    def test_a_local_conflict_leads_to_its_variable(self, tmp_path: Path) -> None:
        # Same bare declaration pointer as `missing-producer`, on whichever side
        # `_select_producer` reports - here the second declaration, `Torque`.
        root = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("local", "Torque", unit="Nm"),
                )
            },
        )
        route = route_of(
            "local-conflict", root / "a.ddd.json", "component.interface[1]", "component", True, {}
        )
        assert route == Route(kind="variable", name="Torque")

    def test_a_condition_mismatch_leads_to_its_variable_with_or_without_its_own_condition(
        self, tmp_path: Path
    ) -> None:
        # `condition-mismatch` is filed on the condition when the losing side states one
        # (`other.location("condition")`) and on the bare declaration when it does not
        # (`other.location()`) - both lead to the same variable either way.
        root = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("input", "Torque", unit="Nm"),
                    declare("input", "Flow", unit="l/min"),
                )
            },
        )
        with_condition = route_of(
            "condition-mismatch",
            root / "a.ddd.json",
            "component.interface[2].condition",
            "component",
            True,
            {},
        )
        without_condition = route_of(
            "condition-mismatch",
            root / "a.ddd.json",
            "component.interface[1]",
            "component",
            True,
            {},
        )
        assert with_condition == Route(kind="variable", name="Flow")
        assert without_condition == Route(kind="variable", name="Torque")

    def test_an_unknown_unit_leads_to_the_unit_it_names(self, tmp_path: Path) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="degC"))}
        )
        route = route_of(
            "unknown-unit", root / "a.ddd.json", f"{DEFINITION}.unit", "component", True, {}
        )
        assert route == Route(kind="unit", name="degC")

    def test_an_unknown_unit_on_a_type_leads_to_the_unit_as_well(self, tmp_path: Path) -> None:
        # The unit panel of part 2 lists every place a unit is stated, a scalar type's included,
        # so this leads somewhere although no page opens a types file.
        root = built(tmp_path, **{"t.ddd.json": types(scalar_type("Speed_t", unit="degC"))})
        route = route_of("unknown-unit", root / "t.ddd.json", "types[0].unit", "types", True, {})
        assert route == Route(kind="unit", name="degC")

    def test_a_duplicate_unit_leads_to_the_unit_it_names(self, tmp_path: Path) -> None:
        # Filed at the vocabulary entry itself - measured: `u.ddd.json#units[1]`. The unit's own
        # panel lists every place stating it and the vocabulary entries too, so the finding has
        # somewhere to go; until now the page told the reader a units file "has no page yet".
        root = built(
            tmp_path,
            **{
                "u.ddd.json": {"units": ["rpm", "rpm"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        route = route_of("duplicate-unit", root / "u.ddd.json", "units[1]", "units", True, {})
        assert route == Route(kind="unit", name="rpm")

    def test_a_duplicate_unit_written_as_an_object_leads_there_too(self, tmp_path: Path) -> None:
        # A vocabulary entry is a spelling on its own or an object carrying a description, and
        # `ddd.lsp.units` writes whichever the file already uses. Read as a whole value, the
        # object is no string and the finding would lead nowhere.
        root = built(
            tmp_path,
            **{
                "u.ddd.json": {
                    "units": [
                        {"unit": "rpm", "description": "revolutions"},
                        {"unit": "rpm", "description": "again"},
                    ]
                },
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        route = route_of("duplicate-unit", root / "u.ddd.json", "units[1]", "units", True, {})
        assert route == Route(kind="unit", name="rpm")

    def test_a_finding_inside_a_type_leads_to_that_type(self, structures, cache) -> None:
        route = route_of(
            "type-kind", structures / "types.ddd.json", "types[0].datatype", "types", True, cache
        )
        assert route == Route("type", "Temperature_t")

    def test_a_finding_inside_a_member_leads_to_the_structure_holding_it(
        self, structures, cache
    ) -> None:
        route = route_of(
            "init-invalid",
            structures / "types.ddd.json",
            "types[3].members[1].conversion.enumerators[0].value",
            "types",
            True,
            cache,
        )
        assert route == Route("type", "Status_t")

    def test_a_unit_stated_by_a_type_still_leads_to_the_unit(self, structures, cache) -> None:
        # The one route that crosses the file kinds, as part 4 settled it: a unit's panel lists
        # every place stating it, a scalar type's included.
        route = route_of(
            "unknown-unit", structures / "types.ddd.json", "types[0].unit", "types", True, cache
        )
        assert route == Route("unit", "degC")

    def test_a_finding_on_a_types_file_naming_no_type_leads_nowhere(self, structures, cache):
        assert route_of("schema", structures / "types.ddd.json", "", "types", True, cache) is None

    def test_a_types_file_that_did_not_load_leads_nowhere(self, structures, cache) -> None:
        assert (
            route_of("type-kind", structures / "types.ddd.json", "types[0]", "types", False, cache)
            is None
        )

    def test_a_finding_inside_a_component_declared_type_leads_to_that_type(
        self, demo, cache
    ) -> None:
        # A component may declare its own types, inline, alongside naming a standalone types
        # file: `SensorHub` in examples/demo does, declaring `DriverState_t` and
        # `SensorDiagnosis_t` at `component.types[0]` and `component.types[1]`.
        # `Index.types` holds a type the same way wherever it was declared, so the type's own
        # panel is still the better destination than the component's - even though the file's
        # kind is `component`, not `types`. Measured against the real file with a scratch probe
        # rather than guessed: `component.types[1].members[0].typename` is the `driver` member
        # of `SensorDiagnosis_t`, referencing `DriverState_t`.
        route = route_of(
            "unknown-type",
            demo / "components" / "sensor_hub.ddd.json",
            "component.types[1].members[0].typename",
            "component",
            True,
            cache,
        )
        assert route == Route("type", "SensorDiagnosis_t")

    def test_a_finding_on_a_component_file_naming_no_declaration_leads_to_the_component(
        self, tmp_path: Path
    ) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "duplicate-component", root / "a.ddd.json", "component.name", "component", True, {}
        )
        assert route == Route(kind="component", name=None)

    def test_a_finding_on_a_file_that_did_not_load_leads_nowhere(self, tmp_path: Path) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert route_of("json-syntax", root / "a.ddd.json", "", "component", False, {}) is None

    def test_a_finding_naming_no_place_leads_nowhere(self, tmp_path: Path) -> None:
        # No check in `analysis.py` files without a location - every `self._bag.add(...)` call
        # there passes a real `Location` (`missing-producer` included: see
        # `test_a_finding_missing_a_producer_leads_to_its_variable` above). An empty pointer is
        # `ddd.gui.api._finding`'s own fallback for a `Diagnostic` whose `location` is `None`
        # (`pointer="" if finding.location is None else ...`), exercised today only by a
        # hand-built diagnostic
        # (`tests/test_gui_api.py::test_a_note_without_a_place_is_carried_without_one`).
        # `route_of` still has to answer it the same way, since nothing stops a future check -
        # a plugin's, say - from filing one, so this stands in with a check name that names no
        # real one.
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert route_of("no-location", root / "a.ddd.json", "", "component", True, {}) is None

    def test_a_declaration_the_file_no_longer_holds_leads_nowhere(self, tmp_path: Path) -> None:
        # The analysis read the file; the pointer describes where the declaration was then.
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "definition-mismatch",
            root / "a.ddd.json",
            "component.interface[7].definition",
            "component",
            True,
            {},
        )
        assert route is None

    def test_a_type_the_file_no_longer_holds_leads_nowhere(self, structures, cache) -> None:
        # The analysis read the file; the pointer describes where the type was then.
        route = route_of(
            "type-kind", structures / "types.ddd.json", "types[99].datatype", "types", True, cache
        )
        assert route is None

    def test_a_file_that_broke_since_the_analysis_leads_nowhere_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        # Every finding of the project is routed on every state request, so a file saved
        # half-edited between the analysis and the request must answer nothing rather than
        # raise: `ddd.lsp.ranges.read` gives an empty document for a file it cannot read, and
        # an empty document answers every question with nothing.
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        (root / "a.ddd.json").write_text('{"component": {"name": "A", "inter', encoding="utf-8")
        assert (
            route_of("definition-mismatch", root / "a.ddd.json", DEFINITION, "component", True, {})
            is None
        )

    def test_a_file_gone_since_the_analysis_leads_nowhere(self, tmp_path: Path) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        (root / "a.ddd.json").unlink()
        assert (
            route_of(
                "unknown-unit", root / "a.ddd.json", f"{DEFINITION}.unit", "component", True, {}
            )
            is None
        )

    def test_a_finding_on_an_init_leads_to_that_object_s_values(
        self, tmp_path: Path, cache
    ) -> None:
        # Measured: the analysis files an init-invalid at `…definition.init`, the declaration's
        # own pointer with `.definition.init` after it and no element index.
        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Bad",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[2],
                        init=[1, 9999],
                    ),
                )
            },
        )
        route = route_of(
            "init-invalid",
            tmp_path / "a.ddd.json",
            "component.interface[0].definition.init",
            "component",
            True,
            cache,
        )
        assert route == Route("values", "Bad")

    def test_a_finding_elsewhere_in_the_declaration_still_leads_to_the_variable(
        self, tmp_path: Path, cache
    ) -> None:
        # The init route must not swallow its neighbours: `missing-id` is filed at
        # `…definition.name` on the same declaration and still opens the variable's panel.
        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Bad",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[2],
                        init=[1, 2],
                    ),
                )
            },
        )
        route = route_of(
            "missing-id",
            tmp_path / "a.ddd.json",
            "component.interface[0].definition.name",
            "component",
            True,
            cache,
        )
        assert route == Route("variable", "Bad")

    def test_a_finding_on_an_init_the_file_no_longer_holds_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        # The same "moved on since" case WITHIN_DECLARATION already has its own test for
        # (test_a_declaration_the_file_no_longer_holds_leads_nowhere above): the analysis read
        # the file: the pointer describes where the declaration was then, and index 7 is past
        # the file's one declaration, so `value_at` answers no name to route by.
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "init-invalid",
            root / "a.ddd.json",
            "component.interface[7].definition.init",
            "component",
            True,
            {},
        )
        assert route is None

    def test_an_unknown_unit_whose_pointer_holds_no_string_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "unknown-unit",
            root / "a.ddd.json",
            f"{DEFINITION}.datatype.nothing",
            "component",
            True,
            {},
        )
        assert route is None


# The three places a shape names a constant (a declaration's `dimensions[i]`, a declaration's
# `size` - the axis case - and a structure member's `dimensions[i]`), a constant declared in a
# constants file and one declared inline by a component, and one file of neither kind.
SHAPES = {
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 8}],
            "interface": [
                {
                    "scope": "public",
                    "definition": {
                        "kind": "value",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "dimensions": ["MISSING_CELLS"],
                    },
                },
                {
                    "scope": "public",
                    "definition": {
                        "kind": "axis",
                        "name": "TrendAxis",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "size": "MISSING_CELLS",
                    },
                },
            ],
            "types": [
                {
                    "type": "struct",
                    "name": "Sample_t",
                    "members": [
                        {"name": "history", "datatype": "uint16", "dimensions": ["MISSING_CELLS"]}
                    ],
                }
            ],
        }
    },
    "c.ddd.json": {"constants": [{"name": "TREND_SAMPLES", "value": 16}]},
}


class TestAConstant:
    def test_unknown_constant_leads_to_the_name_the_shape_spells(self, tmp_path: Path) -> None:
        """The name does not exist - that is what the finding says - and the route still carries
        it: the page opens the add form with it filled in, which is the whole point of the tab
        for this check."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.interface[0].definition.dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_dimension_value_leads_to_the_constant_whose_value_is_wrong(
        self, tmp_path: Path
    ) -> None:
        """The one check of the three whose target is directly editable: the value is what has to
        change, and the panel is where it changes."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "dimension-value",
            path,
            "component.interface[0].definition.dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_an_axis_size_leads_there_too(self, tmp_path: Path) -> None:
        """The second of the three places a shape is written: an axis states its length as
        `size`, not as a `dimensions` entry."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.interface[1].definition.size",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_a_constant_check_inside_a_type_beats_the_type_route(self, tmp_path: Path) -> None:
        """A structure member's dimension is inside `types[i]`, which `WITHIN_TYPE` matches. Tried
        after it, an `unknown-constant` on a member would open the type instead of the constant -
        the same ordering `UNIT_CHECKS` already needs and already has."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.types[0].members[0].dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_duplicate_constant_leads_to_the_constant_its_entry_declares(
        self, tmp_path: Path
    ) -> None:
        path = write_tree(tmp_path, SHAPES) / "c.ddd.json"
        assert route_of(
            "duplicate-constant", path, "constants[0].name", "constants", True, {}
        ) == Route("constant", "TREND_SAMPLES")

    def test_a_constant_declared_inline_by_a_component_leads_there_as_well(
        self, tmp_path: Path
    ) -> None:
        """`ddd.loading` registers `component.constants[i]` and a constants file's `constants[i]`
        under one name, so the tab lists both and a finding on either leads to the same panel."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "duplicate-constant", path, "component.constants[0].name", "component", True, {}
        ) == Route("constant", "CELLS")

    def test_a_shape_holding_no_string_leads_nowhere(self, tmp_path: Path) -> None:
        """A dimension written as a number names no constant, and a file that changed since the
        analysis can have anything there.

        Measured against the brief: the pointer the brief names for this test
        (`component.interface[0].definition.dimensions[0]`) holds the string `"MISSING_CELLS"` in
        `SHAPES`, the same as the first three tests above, so asserting `None` of it would fail
        against a correct `route_of` - it would answer `Route("constant", "MISSING_CELLS")`, not
        nothing. `component.constants[0].value` is the one place in `SHAPES` a `CONSTANT_CHECKS`
        pointer can be aimed at that actually holds a number rather than a string.
        """
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert (
            route_of(
                "unknown-constant",
                path,
                "component.constants[0].value",
                "component",
                True,
                {},
            )
            is None
        )

    def test_a_constant_the_file_no_longer_holds_leads_nowhere(self, tmp_path: Path) -> None:
        """The analysis read the file; the pointer describes where the entry was then - the same
        "moved on since" case `WITHIN_TYPE` already has a test for
        (`test_a_type_the_file_no_longer_holds_leads_nowhere`), pinning `WITHIN_CONSTANT`'s own
        `isinstance(name, str)` guard rather than leaving it exercised only by the happy path."""
        path = write_tree(tmp_path, SHAPES) / "c.ddd.json"
        assert (
            route_of("duplicate-constant", path, "constants[99].name", "constants", True, {})
            is None
        )


# The second vocabulary: a sections file declaring one section and a definition placing its data
# there. Held here rather than imported, as `tests/test_project_shared.py` and
# `tests/test_shared_plans.py` each hold their own copy - a four line tree is cheaper to spell
# than to couple three suites through - and in the same spelling those two use, `.calib`
# read-only and aligned 4 with the variable called `Gain`.
PLACED = {
    "s.ddd.json": {"sections": [{"section": ".calib", "access": "read-only", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "Gain", section=".calib")),
}

# The same tree with the definition placed in a section no file declares, which is exactly the
# state `unknown-section` reports: the name is in the definition and nowhere else.
PLACED_NOWHERE = {
    "s.ddd.json": {"sections": [{"section": ".calib", "access": "read-only", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "Gain", section=".nvm")),
}


class TestASection:
    def test_unknown_section_leads_to_the_name_the_definition_places_data_in(
        self, tmp_path: Path
    ) -> None:
        # Measured: filed at `component.interface[0].definition.section`, whose value is the name -
        # the same shape the unit and constant branches read.
        root = built(tmp_path, **PLACED_NOWHERE)
        assert route_of(
            "unknown-section",
            root / "a.ddd.json",
            "component.interface[0].definition.section",
            "component",
            True,
            {},
        ) == Route("section", ".nvm")

    @pytest.mark.parametrize("check", ["unknown-section", "section-access", "section-alignment"])
    def test_every_check_about_a_placement_leads_to_the_section(
        self, tmp_path: Path, check: str
    ) -> None:
        """Spec 4.6's route is pointer shaped, not check-id shaped: a finding filed at
        `component.interface[i].definition.section` and about the placement leads to that section,
        whichever check filed it.

        Each case fails if its check falls back to `WITHIN_DECLARATION`, which matches this pointer
        too and would answer `Route("variable", "Gain")` - the arbitrary split this test exists to
        forbid, since two checks about one thing cannot honestly open two screens.

        The three are measured, not guessed: all of them come off one `where` in
        `Analysis._check_sections`. A fourth placement check would lead here without this module
        hearing about it, which is the point of matching on the pointer.
        """
        root = built(tmp_path, **PLACED)
        assert route_of(
            check,
            root / "a.ddd.json",
            "component.interface[0].definition.section",
            "component",
            True,
            {},
        ) == Route("section", ".calib")

    def test_a_consumer_stating_a_section_leads_to_the_declaration_that_states_it(
        self, tmp_path: Path
    ) -> None:
        """The one check filed at that pointer that is not about the section. `consumer-storage`
        comes off `PRODUCER_KEYS`, not off the section checks, and says a consumer stated a key
        only the producing component may state - the section it names may well be the right one,
        and what has to go is the key. `analysis.py`'s own comment at the filing site says where
        that is: "reported where the claim is written rather than where it is overruled ... and
        the fix is here".

        This is the test that fails if the exclusion is ever simplified away as a special case
        nobody could explain. Its sibling below is the second half of the same argument.
        """
        root = built(tmp_path, **PLACED)
        assert route_of(
            "consumer-storage",
            root / "a.ddd.json",
            "component.interface[0].definition.section",
            "component",
            True,
            {},
        ) == Route("variable", "Gain")

    def test_the_same_check_at_its_other_key_opens_that_object_s_values(
        self, tmp_path: Path
    ) -> None:
        """`PRODUCER_KEYS` gives `consumer-storage` exactly two keys, `init` and `section` - the
        other three entries there are `consumer-raster`, `consumer-identity` and
        `consumer-extension`, one key each. The `init` copy is claimed by `WITHIN_INIT`, which
        opens the values grid, so both of this check's keys lead to a screen of the variable's own
        and the `section` key agrees with its sibling rather than inventing a third destination.

        That is the argument `ABOUT_THE_DECLARATION`'s docstring makes, and until the branch's
        final review nothing asserted it: this test used to aim at `definition.raster`, which is
        `consumer-raster`'s key and not this check's at all, so it pinned a pair the analysis never
        files. It passed, and could not have failed for the right reason."""
        root = built(tmp_path, **PLACED)
        assert route_of(
            "consumer-storage",
            root / "a.ddd.json",
            "component.interface[0].definition.init",
            "component",
            True,
            {},
        ) == Route("values", "Gain")

    def test_duplicate_section_leads_to_the_section_its_entry_declares(
        self, tmp_path: Path
    ) -> None:
        root = built(tmp_path, **PLACED)
        assert route_of(
            "duplicate-section", root / "s.ddd.json", "sections[0].section", "sections", True, {}
        ) == Route("section", ".calib")

    def test_a_pointer_inside_a_sections_entry_leads_to_the_section_too(
        self, tmp_path: Path
    ) -> None:
        """`WITHIN_SECTION` covers the whole entry, not the name alone: a schema finding on an
        `alignment` is about the section that entry declares, which is what the panel opens - the
        same reach `WITHIN_CONSTANT` has over a constant's own keys."""
        root = built(tmp_path, **PLACED)
        assert route_of(
            "schema", root / "s.ddd.json", "sections[0].alignment", "sections", True, {}
        ) == Route("section", ".calib")

    def test_the_section_route_is_tried_before_the_kind_gate(self, tmp_path: Path) -> None:
        """A sections file's kind is `sections`, not `component`, so a branch placed after the
        `kind != COMPONENT_KIND` gate would never be reached from one - which is why both arms go
        above it. Asserted through the gate's own argument rather than by reading the source: the
        same pointer answers the same section whatever kind the file is said to be, and a `sections`
        kind is the only one a real sections file ever carries."""
        root = built(tmp_path, **PLACED)
        assert route_of(
            "duplicate-section", root / "s.ddd.json", "sections[0].section", "sections", True, {}
        ) == route_of(
            "duplicate-section", root / "s.ddd.json", "sections[0].section", "component", True, {}
        )

    def test_a_section_the_file_no_longer_holds_leads_nowhere(self, tmp_path: Path) -> None:
        """The analysis read the file; the pointer describes where the entry was then - the same
        "moved on since" case `WITHIN_CONSTANT` has its own test for, pinning `WITHIN_SECTION`'s
        `isinstance` guard rather than leaving it exercised only by the happy path."""
        root = built(tmp_path, **PLACED)
        assert (
            route_of(
                "duplicate-section",
                root / "s.ddd.json",
                "sections[99].section",
                "sections",
                True,
                {},
            )
            is None
        )

    def test_a_placement_holding_no_string_leads_nowhere(self, tmp_path: Path) -> None:
        """A file that changed since the analysis can have anything at that pointer, and a number
        names no section. Written by hand rather than through a valid tree, because a component
        stating `"section": 4` is one the loader refuses - which is exactly the state a file saved
        between the analysis and the request can be in."""
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Gain", section=4))}
        )
        assert (
            route_of(
                "unknown-section",
                root / "a.ddd.json",
                "component.interface[0].definition.section",
                "component",
                True,
                {},
            )
            is None
        )

    def test_an_unknown_section_naming_the_empty_string_leads_nowhere(self, tmp_path: Path) -> None:
        """The other half of the guard `CONSTANT_CHECKS` reads by, which no type answers for it: a
        definition drifted to `"section": ""` names a section with no name, and a panel opened on
        one would be a heading with nothing in it."""
        root = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Gain", section=""))}
        )
        assert (
            route_of(
                "unknown-section",
                root / "a.ddd.json",
                "component.interface[0].definition.section",
                "component",
                True,
                {},
            )
            is None
        )

    def test_a_pointer_inside_no_sections_entry_the_file_holds_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        """`WITHIN_SECTION` matches on the pointer alone, so it is asked of a file that holds no
        `sections` key at all - a component the analysis filed a section finding on, whose text
        has since been replaced. It has to answer nothing rather than raise."""
        root = built(tmp_path, **PLACED)
        assert (
            route_of(
                "duplicate-section",
                root / "a.ddd.json",
                "sections[0].section",
                "sections",
                True,
                {},
            )
            is None
        )


# The third vocabulary, copied by hand from `TIMED` in tests/test_lsp.py (the fixture
# `TestSectionsAndRasters` indexes) rather than imported across suites, as `PLACED` above is
# copied rather than shared: a rasters file declaring `10ms`, a component naming it as its own
# default, and a definition naming it too - the two shapes a raster is spelled at, in one tree.
TIMED = {
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}

# The same tree with the definition measured in a raster no file declares, which is exactly the
# state `unknown-raster` reports at that pointer. The component's own default is left declared, so
# one tree answers both shapes: `50ms` from the definition, `10ms` from the component.
TIMED_NOWHERE = {
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="50ms"), raster="10ms"),
}


class TestARaster:
    def test_unknown_raster_leads_to_the_name_the_definition_asks_for(self, tmp_path: Path) -> None:
        """The name is in no file - that is what the finding says - and the route carries it
        anyway, as `unknown-constant`'s does: the panel's 404 is what tells the reader the name is
        the problem.

        This is also the test that pins the arm's *place*. `WITHIN_DECLARATION` matches this
        pointer, being broader, so a raster arm written below it answers `Route("variable", "X")`
        and the finding opens the wrong screen - which is why the arm goes beside `CONSTANT_CHECKS`
        and not beside `WITHIN_INIT`.
        """
        root = built(tmp_path, **TIMED_NOWHERE)
        assert route_of(
            "unknown-raster",
            root / "a.ddd.json",
            "component.interface[0].definition.raster",
            "component",
            True,
            {},
        ) == Route("raster", "50ms")

    def test_a_component_s_own_raster_leads_there_too(self, tmp_path: Path) -> None:
        """The use inside no definition still names a raster, and a finding filed at it must reach
        the raster rather than falling through to the component's page.

        Measured: `Analysis._check_rasters` files `unknown-raster` at
        `loaded.location("component.raster")` for a component whose default names nothing, which
        is the second of the two shapes `navigation._RASTER_KEY` spells."""
        root = built(tmp_path, **TIMED_NOWHERE)
        assert route_of(
            "unknown-raster", root / "a.ddd.json", "component.raster", "component", True, {}
        ) == Route("raster", "10ms")

    def test_a_consumer_stating_a_raster_leads_to_the_declaration_that_states_it(
        self, tmp_path: Path
    ) -> None:
        """The raster's copy of `test_a_consumer_stating_a_section_leads_to_the_declaration_that
        _states_it`, and the reason the route is check-id shaped where a section's is pointer
        shaped. `consumer-raster` comes off `PRODUCER_KEYS`, not off `_check_rasters`, and says a
        consumer stated a key only the producing component may state: the raster it names may well
        be the right one, and what has to go is the key."""
        root = built(
            tmp_path,
            **{
                "r.ddd.json": TIMED["r.ddd.json"],
                "a.ddd.json": component("A", declare("output", "X", raster="10ms")),
                "b.ddd.json": component("B", declare("input", "X", raster="10ms")),
            },
        )
        assert route_of(
            "consumer-raster",
            root / "b.ddd.json",
            "component.interface[0].definition.raster",
            "component",
            True,
            {},
        ) == Route("variable", "X")

    def test_a_raster_on_a_calibration_object_leads_to_the_declaration_as_well(
        self, tmp_path: Path
    ) -> None:
        """The third check filed at `definition.raster`, and the second of the two that are not
        about the raster. `raster-kind` says a calibration object states a raster and no daq list
        carries one: the raster entry is innocent, and both fixes - drop the key, or make the
        object a measurement - are edits to the declaration."""
        root = built(
            tmp_path,
            **{
                "r.ddd.json": TIMED["r.ddd.json"],
                "a.ddd.json": component(
                    "A", declare("output", "Gain", kind="parameter", init=1, raster="10ms")
                ),
            },
        )
        assert route_of(
            "raster-kind",
            root / "a.ddd.json",
            "component.interface[0].definition.raster",
            "component",
            True,
            {},
        ) == Route("variable", "Gain")

    def test_duplicate_raster_leads_to_the_raster_its_entry_declares(self, tmp_path: Path) -> None:
        root = built(tmp_path, **TIMED)
        assert route_of(
            "duplicate-raster", root / "r.ddd.json", "rasters[0]", "rasters", True, {}
        ) == Route("raster", "10ms")

    def test_a_pointer_inside_a_rasters_entry_leads_to_the_raster_too(self, tmp_path: Path) -> None:
        """`WITHIN_RASTER` covers the whole entry, not the name alone - the same reach
        `WITHIN_SECTION` has over a section's own keys. `duplicate-event` is filed at the entry
        itself (`LoadedRaster.location()`), and a schema finding can sit at any key of it."""
        root = built(tmp_path, **TIMED)
        assert route_of(
            "schema", root / "r.ddd.json", "rasters[0].cycle", "rasters", True, {}
        ) == Route("raster", "10ms")

    def test_the_raster_route_is_tried_before_the_kind_gate(self, tmp_path: Path) -> None:
        """A rasters file's kind is `rasters`, not `component`, so a branch placed after the
        `kind != COMPONENT_KIND` gate would never be reached from one - which is why `WITHIN_RASTER`
        goes above it, beside `WITHIN_SECTION`. Asserted through the gate's own argument, as the
        section's twin is: the same pointer answers the same raster whatever kind the file is said
        to be, and a `rasters` kind is the only one a real rasters file ever carries."""
        root = built(tmp_path, **TIMED)
        assert route_of(
            "duplicate-raster", root / "r.ddd.json", "rasters[0]", "rasters", True, {}
        ) == route_of("duplicate-raster", root / "r.ddd.json", "rasters[0]", "component", True, {})

    def test_a_raster_the_file_no_longer_holds_leads_nowhere(self, tmp_path: Path) -> None:
        """The analysis read the file; the pointer describes where the entry was then - the same
        "moved on since" case `WITHIN_SECTION` has its own test for, pinning `WITHIN_RASTER`'s
        `isinstance` guard rather than leaving it exercised only by the happy path."""
        root = built(tmp_path, **TIMED)
        assert (
            route_of("duplicate-raster", root / "r.ddd.json", "rasters[99]", "rasters", True, {})
            is None
        )

    def test_a_raster_key_holding_no_string_leads_nowhere(self, tmp_path: Path) -> None:
        """A file that changed since the analysis can have anything at that pointer, and a number
        names no raster. Written by hand rather than through a valid tree, because a component
        stating `"raster": 4` is one the loader refuses - which is exactly the state a file saved
        between the analysis and the request can be in."""
        root = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "X", raster=4))})
        assert (
            route_of(
                "unknown-raster",
                root / "a.ddd.json",
                "component.interface[0].definition.raster",
                "component",
                True,
                {},
            )
            is None
        )

    def test_an_unknown_raster_naming_the_empty_string_leads_nowhere(self, tmp_path: Path) -> None:
        """The other half of the same guard, which no type answers for it: a definition drifted to
        `"raster": ""` names a raster with no name, and a panel opened on one would be a heading
        with nothing in it."""
        root = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "X", raster=""))})
        assert (
            route_of(
                "unknown-raster",
                root / "a.ddd.json",
                "component.interface[0].definition.raster",
                "component",
                True,
                {},
            )
            is None
        )

    def test_a_pointer_inside_no_rasters_entry_the_file_holds_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        """`WITHIN_RASTER` matches on the pointer alone, so it is asked of a file that holds no
        `rasters` key at all - a component the analysis filed a raster finding on, whose text has
        since been replaced. It has to answer nothing rather than raise."""
        root = built(tmp_path, **TIMED)
        assert (
            route_of("duplicate-raster", root / "a.ddd.json", "rasters[0]", "rasters", True, {})
            is None
        )


def test_every_kind_a_route_answers_is_one_the_contract_publishes() -> None:
    """The guard for the drift that has now come within one test of shipping three parts running.

    `_finding` builds a `contract.FindingRoute` for every finding of every request, so a kind
    `route_of` answers that the contract's `Literal` leaves out raises a `pydantic.ValidationError`
    for every finding carrying it - a crash, not a finding that merely leads nowhere. Part 13's
    `constant`, part 14's `section` and this part's `raster` were each caught by whichever api test
    happened to build a finding with the new kind, which is luck rather than a guard.

    Two tables of one fact, and this is the assertion that makes them one. They cannot be shared:
    `ddd.gui.contract` is the wire format and imports nothing of `ddd.finding_routes`, so the list
    is written out in both. A test may import both where neither may import the other.

    Compared as sets: the order a `Literal` lists its members in is meaningful to nobody, and a
    test failing because the two tuples were reordered would be noise. The literal on the last line
    is what keeps the relation from passing vacuously - both sides reverted to a bare `str` would
    give `get_args` two empty tuples and an assertion that holds and says nothing.
    """
    answers = get_args(get_type_hints(Route)["kind"])
    published = get_args(FindingRoute.model_fields["kind"].annotation)
    assert set(answers) == set(published)
    assert set(answers) == {
        "variable",
        "unit",
        "component",
        "type",
        "values",
        "constant",
        "section",
        "raster",
    }
