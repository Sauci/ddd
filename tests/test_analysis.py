"""One test per consistency check."""

from __future__ import annotations

from pathlib import Path

from conftest import checks, component, declare, messages, project, run_analysis
from ddd.diagnostics import CHECKS, Severity


def two_components(*, a: list[dict], b: list[dict]) -> dict[str, object]:
    return {
        "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
        "a.ddd.json": component("A", *a),
        "b.ddd.json": component("B", *b),
    }


class TestProducersAndConsumers:
    def test_consistent_project_has_no_findings(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X")], b=[declare("input", "X")]),
        )
        assert dictionary is not None
        assert checks(bag) == []
        entry = dictionary.by_name["X"]
        assert entry.owner == "A"
        assert entry.consumers == ("B",)

    def test_multiple_producers(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X")], b=[declare("output", "X")]),
        )
        assert "multiple-producers" in checks(bag)
        assert "exactly one writer" in messages(bag)

    def test_missing_producer(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("input", "X")], b=[declare("input", "X")])
        )
        assert checks(bag).count("missing-producer") == 2

    def test_unused_output_is_a_warning(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("output", "X")], b=[declare("local", "Y")])
        )
        assert checks(bag) == ["unused-output"]
        assert next(iter(bag)).severity is Severity.WARNING

    def test_unused_local_is_fine(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "X")], b=[declare("local", "Y")])
        )
        assert checks(bag) == []

    def test_local_conflict(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "X")], b=[declare("input", "X")])
        )
        assert checks(bag) == ["local-conflict"]

    def test_duplicate_declaration_in_one_component(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X"), declare("input", "X")], b=[declare("input", "X")]
            ),
        )
        assert "duplicate-declaration" in checks(bag)
        assert "declares 'X' twice (as output and as input)" in messages(bag)


class TestDefinitionAgreement:
    def test_datatype_mismatch(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", datatype="uint8")],
                b=[declare("input", "X", datatype="uint16")],
            ),
        )
        assert "definition-mismatch" in checks(bag)
        assert "datatype: uint16 != uint8" in messages(bag)

    def test_unit_mismatch(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", unit="Hz")], b=[declare("input", "X", unit="1/s")]
            ),
        )
        assert "unit: '1/s' != 'Hz'" in messages(bag)

    def test_scaling_mismatch(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", conversion={"factor": 0.5})],
                b=[declare("input", "X", conversion={"factor": 0.25})],
            ),
        )
        assert "conversion: linear(factor=0.25, offset=0) != linear(factor=0.5" in messages(bag)

    def test_dimension_mismatch(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X", dimensions=[4])], b=[declare("input", "X")]),
        )
        assert "shape: scalar != [4]" in messages(bag)

    def test_the_producer_is_the_reference(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X", datatype="uint16")),
                "b.ddd.json": component("B", declare("output", "X", datatype="uint8")),
            },
        )
        assert "'X' is declared differently by component 'A' than by 'B'" in messages(bag)

    def test_description_may_differ(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", description="one")],
                b=[declare("input", "X", description="another")],
            ),
        )
        assert checks(bag) == []

    def test_a_consumer_may_not_state_an_initial_value(self, tree: Path) -> None:
        """Not a disagreement to be settled, but a claim over somebody else's storage.

        Which component a variable starts out belonging to is not a matter of opinion: the one
        that writes it decides, and a reader saying otherwise is wrong rather than outvoted.
        """
        dictionary, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X", init=1)], b=[declare("input", "X", init=2)]),
        )
        assert checks(bag) == ["consumer-storage"]
        assert dictionary is not None
        assert dictionary.by_name["X"].init == 1

    def test_a_producer_states_its_initial_value_freely(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X", init=1)], b=[declare("input", "X")]),
        )
        assert checks(bag) == []

    def test_condition_mismatch_is_only_a_warning(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", condition="defined(A)")],
                b=[declare("input", "X", condition="defined(B)")],
            ),
        )
        assert checks(bag) == ["condition-mismatch"]


class TestValueChecks:
    def test_init_out_of_range(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "X", init=300)], b=[declare("local", "Y")])
        )
        assert checks(bag) == ["init-invalid"]
        assert "does not fit into uint8 (0 .. 255)" in messages(bag)

    def test_fractional_init_for_an_integer(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "X", init=1.5)], b=[declare("local", "Y")])
        )
        assert "written as a fractional number" in messages(bag)

    def test_float_init_is_accepted_for_a_float(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", datatype="float32", init=1.5)],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == []

    def test_array_element_out_of_range(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", dimensions=[3], init=[1, 2, 999])],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["init-invalid"]

    def test_limits_outside_the_datatype_range(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", limits={"min": 0, "max": 1000})],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["limits-out-of-range"]

    def test_limits_exactly_on_the_range_are_fine(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", limits={"min": 0, "max": 255})],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == []

    def test_reserved_variable_name(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "volatile")], b=[declare("local", "Y")])
        )
        assert checks(bag) == ["reserved-identifier"]

    def test_reserved_component_name(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("_Bad", declare("local", "X")),
            },
        )
        assert "reserved-identifier" in checks(bag)

    def test_reserved_project_name(self, tree: Path) -> None:
        """The project name becomes the a2l PROJECT and MODULE, so it is screened too."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("register", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        assert "project name 'register' is reserved by the c language" in messages(bag)
        finding = next(iter(bag))
        assert finding.location is not None
        assert finding.location.pointer == "project.name"
        assert finding.location.path.name == "project.ddd.json"

    def test_names_differing_only_in_case(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree, two_components(a=[declare("local", "Speed")], b=[declare("local", "speed")])
        )
        assert checks(bag) == ["name-similar"]

    def test_empty_component_is_an_info(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")},
        )
        assert checks(bag) == ["empty-component"]
        assert next(iter(bag)).severity is Severity.INFO


class TestEnums:
    def enum(self, *pairs: tuple[str, int]) -> dict[str, object]:
        return {
            "kind": "enum",
            "name": "Mode",
            "enumerators": [{"name": name, "value": value} for name, value in pairs],
        }

    def test_same_enum_twice_is_fine(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", conversion=self.enum(("A", 0), ("B", 1)))],
                b=[declare("input", "X", conversion=self.enum(("A", 0), ("B", 1)))],
            ),
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [enum.name for enum in dictionary.enums] == ["Mode"]

    def test_conflicting_enum(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", conversion=self.enum(("A", 0)))],
                b=[declare("local", "Y", conversion=self.enum(("A", 1)))],
            ),
        )
        assert checks(bag) == ["enum-conflict"]
        assert "first defined as: A=0" in messages(bag)

    def test_duplicate_enumerator_value(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", conversion=self.enum(("A", 0), ("B", 0)))],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["enum-duplicate-value"]

    def test_enumerator_does_not_fit_the_datatype(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", conversion=self.enum(("A", 300)))],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["init-invalid"]
        assert "do not fit into uint8" in messages(bag)


class TestSeverityPolicy:
    def test_check_can_be_ignored(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X")], b=[declare("local", "Y")]),
            severities=["unused-output=ignore"],
        )
        assert checks(bag) == []

    def test_check_can_be_promoted(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X")], b=[declare("local", "Y")]),
            severities=["unused-output=error"],
        )
        assert bag.has_errors

    def test_strict_turns_warnings_into_errors(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("output", "X")], b=[declare("local", "Y")]),
            strict=True,
        )
        assert bag.has_errors

    def test_every_check_is_registered(self, tree: Path) -> None:
        # Guards against a typo in a check identifier used by the analysis.
        assert set(CHECKS) >= {
            "definition-mismatch",
            "multiple-producers",
            "missing-producer",
            "local-conflict",
        }
