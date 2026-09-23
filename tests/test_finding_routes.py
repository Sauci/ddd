"""Where each finding of ``ddd gui`` leads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import EXAMPLES, component, declare, project, scalar_type, types, write_tree
from ddd.finding_routes import Route, route_of
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
