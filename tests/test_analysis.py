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

    def test_init_shape_against_the_declared_dimensions(self, tree: Path) -> None:
        """The wrong shape is init-invalid at the init, like the curve and map path."""
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", dimensions=[2], init=[1, 2, 3])],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["init-invalid"]
        assert "init has 3 elements, expected 2" in messages(bag)
        assert "definition.init" in messages(bag)

    def test_init_list_for_a_scalar(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            two_components(a=[declare("local", "X", init=[1, 2])], b=[declare("local", "Y")]),
        )
        assert checks(bag) == ["init-invalid"]
        assert "init is a list but the object is a scalar" in messages(bag)

    def test_a_conversion_whose_derived_limits_overflow_is_refused(self, tree: Path) -> None:
        """float64 under a factor of 1.8 runs past the largest float there is.

        Resolving it used to construct limits of infinity, which aborted the whole run with
        a validation error; now the pair is refused where it is written and the run reports
        everything else.
        """
        dictionary, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", datatype="float64", conversion={"factor": 1.8})],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["schema"]
        assert "the limits derived from 'float64' and this conversion are not finite" in (
            messages(bag)
        )
        assert "definition.conversion" in messages(bag)
        assert dictionary is not None
        assert [entry.name for entry in dictionary.objects] == ["Y"]

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

    def test_a_value_outside_the_datatype_and_the_c_int_is_reported_once(self, tree: Path) -> None:
        """The c int bound only covers values the datatype holds; one bad value, one finding."""
        _, bag = run_analysis(
            tree,
            two_components(
                a=[declare("local", "X", datatype="sint32", conversion=self.enum(("BIG", 2**31)))],
                b=[declare("local", "Y")],
            ),
        )
        assert checks(bag) == ["init-invalid"]
        assert "do not fit into sint32" in messages(bag)
        assert "c 'int'" not in messages(bag)


class TestLimitsDeference:
    """Omitting limits defers to whoever states them (SPEC 3.3.1.1).

    The resolved limits are the producer's stated ones, else the first stated set in load
    order, else derived from the datatype and the conversion - and only two *stated* sets of
    limits can disagree.
    """

    def test_limits_stated_only_by_a_consumer_reach_the_dictionary(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", "uint16")],
                b=[declare("input", "X", "uint16", limits={"min": 0, "max": 10})],
            ),
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["X"].limits.as_tuple() == (0.0, 10.0)

    def test_two_consumers_stating_different_limits_disagree(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", "uint16")),
                "b.ddd.json": component(
                    "B", declare("input", "X", "uint16", limits={"min": 0, "max": 10})
                ),
                "c.ddd.json": component(
                    "C", declare("input", "X", "uint16", limits={"min": 0, "max": 20})
                ),
            },
        )
        assert checks(bag) == ["definition-mismatch"]
        assert "limits: [0, 20] != [0, 10]" in messages(bag)
        # On the deviating declaration, with a note at the stated reference.
        finding = next(iter(bag))
        assert finding.location is not None
        assert finding.location.path.name == "c.ddd.json"
        note_text, note_location = finding.notes[0]
        assert note_text == "reference declaration"
        assert note_location is not None
        assert note_location.path.name == "b.ddd.json"

    def test_two_consumers_stating_the_same_limits_agree(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", "uint16")),
                "b.ddd.json": component(
                    "B", declare("input", "X", "uint16", limits={"min": 0, "max": 10})
                ),
                "c.ddd.json": component(
                    "C", declare("input", "X", "uint16", limits={"min": 0, "max": 10})
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["X"].limits.as_tuple() == (0.0, 10.0)

    def test_the_producers_stated_limits_win(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", "uint16", limits={"min": 0, "max": 100})],
                b=[declare("input", "X", "uint16", limits={"min": 0, "max": 10})],
            ),
        )
        assert checks(bag) == ["definition-mismatch"]
        assert "limits: [0, 10] != [0, 100]" in messages(bag)
        assert dictionary is not None
        assert dictionary.by_name["X"].limits.as_tuple() == (0.0, 100.0)

    def test_limits_omitted_everywhere_are_derived(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            two_components(
                a=[declare("output", "X", "uint16")], b=[declare("input", "X", "uint16")]
            ),
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.by_name["X"].limits.as_tuple() == (0.0, 65535.0)


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


class TestConsumerOrder:
    def test_the_consumers_of_a_plain_object_are_sorted_whatever_the_include_order(
        self, tree: Path
    ) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "p.ddd.json", "z.ddd.json", "a.ddd.json"),
                "p.ddd.json": component("Prod", declare("output", "S")),
                "z.ddd.json": component("Zeta", declare("input", "S")),
                "a.ddd.json": component("Alpha", declare("input", "S")),
            },
        )
        assert dictionary is not None, messages(bag)
        assert dictionary.by_name["S"].consumers == ("Alpha", "Zeta")
