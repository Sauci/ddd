"""Reading structured datatype files, and checking the graph they form.

The model level rules are in ``test_types.py``; these are the ones that need more than one
file, or the rest of the project, to have any meaning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import (
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace


def val(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "value", **storage, **extra}


def nest(name: str, type_name: str) -> dict[str, Any]:
    """A member that nests another structure, which is a value member naming it."""
    return val(name, typename=type_name)


def struct(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members) or [val("value")]}


def scalar(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    meaning: dict[str, Any] = {} if "conversion" in extra else {"conversion": {"kind": "identity"}}
    return {"type": "scalar", "name": name, "datatype": datatype, **meaning, **extra}


def types(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"types": list(entries)}


def load(tree: Path, files: dict[str, Any], root: str = "project.ddd.json") -> Any:
    bag = DiagnosticBag()
    write_tree(tree, files)
    workspace = load_workspace(tree / root, bag)
    return workspace, bag


def findings(bag: DiagnosticBag) -> list[str]:
    return [diagnostic.check for diagnostic in bag]


def first(bag: DiagnosticBag) -> Any:
    return next(iter(bag))


class TestReadingTypes:
    def test_a_project_collects_the_structures_it_includes(self, tree: Path) -> None:
        workspace, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("B_t"), struct("A_t")),
            },
        )
        assert not findings(bag)
        assert workspace is not None
        # sorted by name, so the include order cannot change the generated output
        assert [entry.name for entry in workspace.types] == ["A_t", "B_t"]

    def test_the_file_is_reported_as_a_source(self, tree: Path) -> None:
        """A build has to run DDD again when a structure changes."""
        workspace, _ = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t")),
            },
        )
        assert workspace is not None
        assert any(path.name == "types.ddd.json" for path in workspace.sources())

    def test_two_files_cannot_declare_the_same_structure(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": types(struct("A_t")),
                "two.ddd.json": types(struct("A_t")),
            },
        )
        assert findings(bag) == ["duplicate-type"]
        assert "is declared twice" in first(bag).render()
        assert first(bag).notes, "the first declaration has to be pointed at as well"

    def test_a_malformed_types_file_is_reported_against_its_keys(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": {"types": [{"name": "A_t", "members": [{"name": "x"}]}]},
            },
        )
        assert findings(bag) == ["schema"]

    def test_a_types_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        """It declares no variable, so there is nothing to resolve or generate from it."""
        workspace, bag = load(tree, {"types.ddd.json": types(struct("A_t"))}, root="types.ddd.json")
        assert workspace is None
        assert findings(bag) == ["file-kind"]
        assert "list it in the 'includes'" in first(bag).render()

    def test_a_file_cannot_be_two_kinds_at_once(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {"both.ddd.json": {"component": {"name": "X"}, "types": [struct("A_t")]}},
            root="both.ddd.json",
        )
        assert findings(bag) == ["file-kind"]
        assert "'component' and 'types'" in first(bag).render()

    def test_a_file_of_no_known_kind_lists_what_it_should_have(self, tree: Path) -> None:
        _, bag = load(tree, {"stray.ddd.json": {"stuff": 1}}, root="stray.ddd.json")
        assert findings(bag) == ["file-kind"]
        rendered = first(bag).render()
        assert "'project', 'component', 'types'" in rendered
        assert "found: stuff" in rendered


class TestTypeGraph:
    def test_a_sound_graph_reports_nothing(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("Inner_t", val("value")),
                    struct("Outer_t", nest("inner", "Inner_t"), val("count", "uint32")),
                ),
            },
        )
        assert not findings(bag)

    def test_a_member_nesting_an_undeclared_structure(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t", nest("gone", "Missing_t"))),
            },
        )
        assert findings(bag) == ["unknown-type"]
        rendered = first(bag).render()
        assert "'Missing_t'" in rendered
        assert "types[0].members[0]" in rendered

    def test_two_structures_nesting_each_other(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("A_t", nest("b", "B_t")), struct("B_t", nest("a", "A_t"))
                ),
            },
        )
        # once, not once per participant: the chain names them all
        assert findings(bag) == ["type-cycle"]
        assert "A_t -> B_t -> A_t" in first(bag).render()

    def test_a_structure_nesting_itself(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t", nest("self", "A_t"))),
            },
        )
        assert findings(bag) == ["type-cycle"]
        assert "A_t -> A_t" in first(bag).render()

    def test_a_sound_structure_leading_to_a_cycle_is_reported_at_the_cycle(
        self, tree: Path
    ) -> None:
        """``Head_t`` is not itself recursive, so the finding belongs to the pair that is."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("Head_t", nest("down", "A_t")),
                    struct("A_t", nest("b", "B_t")),
                    struct("B_t", nest("a", "A_t")),
                ),
            },
        )
        assert findings(bag) == ["type-cycle"]
        rendered = first(bag).render()
        assert "A_t -> B_t -> A_t" in rendered
        assert "types.ddd.json#types[1]" in rendered


class TestNamingAType:
    """A declaration whose ``datatype`` names a type the project declares.

    One key names a type everywhere, so this is the same key a structure member uses. What the
    analysis does with it is fill the declaration in and hand an ordinary definition on, which
    is why nothing downstream - the comparison tables, the backends, ``compare`` - had to learn
    anything about types at all.
    """

    def project_with(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> Any:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*entries),
                "a.ddd.json": component(
                    "A", declare("local", "X", **{"typename": "Speed_t", **definition})
                ),
            },
        )
        return bag

    def test_a_scalar_type_fills_in_what_it_fixes(self, tree: Path) -> None:
        """The point of the feature: agreement by naming rather than by copying.

        Three components consuming an engine speed used to write the datatype, the unit, the
        scaling and the limits out in full and leave DDD to notice when one of them was wrong.
        Naming ``Speed_t`` leaves nothing to disagree about.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
                "types.ddd.json": types(
                    scalar(
                        "Speed_t",
                        "uint16",
                        unit="rpm",
                        conversion={"factor": 0.25},
                        limits={"min": 0, "max": 8000},
                    )
                ),
                "a.ddd.json": component("A", declare("output", "EngSpd", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "EngSpd", typename="Speed_t")),
            },
        )
        assert findings(bag) == []
        assert dictionary is not None
        (engine_speed,) = dictionary.objects
        assert engine_speed.datatype.value == "uint16"
        assert engine_speed.unit == "rpm"
        assert engine_speed.conversion.describe() == "linear(factor=0.25, offset=0)"
        assert engine_speed.limits.as_tuple() == (0, 8000)

    def test_a_scalar_type_may_leave_its_limits_to_be_derived(self, tree: Path) -> None:
        """A type states what it wants to state; the rest follows as it does for any object."""
        bag = self.project_with(tree, scalar("Speed_t", "uint8", unit="rpm"))
        assert findings(bag) == []

    def test_a_name_no_file_declares_is_reported_where_it_is_written(self, tree: Path) -> None:
        """Which is also where a typo in a base datatype now lands.

        One key naming a type is what costs this: ``uint166`` is no longer refused by the
        contract as it is typed, because it is a perfectly well formed *name*. It is caught
        here instead, at the same pointer and with a message that says what was looked for.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="Nowhere_t")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        rendered = first(bag).render()
        assert "neither a base datatype nor a type" in rendered
        assert "a.ddd.json#component.interface[0].definition.typename" in rendered

    def test_restating_what_the_type_fixes_is_refused_by_the_contract(self, tree: Path) -> None:
        """An error rather than an override, so there is one answer to where a unit is written.

        Refused by the definition itself, so it surfaces under ``schema`` with a pointer, the
        same route the member shape rules take - no check identifier of its own.
        """
        bag = self.project_with(tree, scalar("Speed_t", "uint16", unit="rpm"), unit="1/min")
        assert findings(bag) == ["schema"]
        assert "already fixes what this value means" in first(bag).render()

    def test_a_scalar_type_nests_nothing_and_is_not_walked_for_members(self, tree: Path) -> None:
        """The type graph is about structures; a scalar has no members to follow."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar("Speed_t", "uint16"), struct("S_t", val("v", typename="Speed_t"))
                ),
            },
        )
        assert findings(bag) == []

    def test_naming_a_structure_makes_the_variable_one(self, tree: Path) -> None:
        """The variable becomes an instance, and its members become the leaves of the a2l."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("Speed_t", val("raw", "uint16", unit="rpm"))),
                "a.ddd.json": component("A", declare("local", "X", typename="Speed_t")),
            },
        )
        assert findings(bag) == []
        assert dictionary is not None
        assert dictionary.objects == ()
        (instance,) = dictionary.instances
        assert (instance.name, instance.type) == ("X", "Speed_t")
        (leaf,) = dictionary.leaves
        assert leaf.path == "X.raw"
        assert leaf.unit == "rpm"


class TestBaseAndDeclaredNamesAreKeptApart:
    """What the two storage keys buy.

    ``datatype`` is one of eleven values, so a mistyped base datatype dies in the contract as
    it is typed; ``typename`` refuses a name spelling a base datatype in any case, so a type
    cannot wear the name of storage it is not; and a name that merely dresses like one -
    ``Int16_t`` - is unambiguous, because the key already says it is declared.
    """

    def test_a_mistyped_base_datatype_is_refused_by_the_contract(self, tree: Path) -> None:
        """Refused where it is typed rather than reported a build later.

        ``uint166`` under ``datatype`` is not one of the eleven, so the editor refuses it as
        it is written instead of a check reporting a type nobody declares a build later.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", datatype="uint166")),
            },
        )
        assert findings(bag) == ["schema"]
        rendered = first(bag).render()
        assert "a.ddd.json#component.interface[0].definition.datatype" in rendered
        assert "Input should be" in rendered

    def test_a_typename_spelling_a_base_datatype_is_refused(self, tree: Path) -> None:
        """In any case: a type called ``UINT16`` reads as storage it is not."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="UINT16")),
            },
        )
        assert findings(bag) == ["schema"]
        assert "spells a base datatype" in first(bag).render()

    def test_storage_is_named_exactly_once_on_a_definition(self, tree: Path) -> None:
        """Both keys at once is a contradiction, refused where it is written."""
        definition = {
            "name": "X",
            "kind": "measurement",
            "volatile": False,
            "datatype": "uint8",
            "typename": "S_t",
        }
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": {
                    "component": {
                        "name": "A",
                        "interface": [{"scope": "local", "definition": definition}],
                    }
                },
            },
        )
        assert findings(bag) == ["schema"]
        assert "storage is named exactly once" in first(bag).render()

    def test_a_name_dressed_like_a_datatype_is_just_a_name(self, tree: Path) -> None:
        """``Int16_t`` under ``typename`` is unambiguous: the key says it is declared."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "types.ddd.json"),
                "types.ddd.json": types(scalar("Int16_t", "sint16")),
                "a.ddd.json": component("A", declare("local", "X", typename="Int16_t")),
            },
        )
        assert findings(bag) == []

    def test_the_eleven_ways_to_fail_at_one_key_are_one_finding(self, tree: Path) -> None:
        """A union that is not discriminated fails once per branch; a reader wants it once.

        The branch kept is the first declared, which is why ``datatype`` puts the base
        datatypes first: "one of these eleven" says far more than a regular expression does.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", datatype="float3")),
            },
        )
        assert findings(bag) == ["schema"]
        assert "should match pattern" not in first(bag).render()

    def test_a_type_may_not_be_declared_under_a_datatype_like_name(self, tree: Path) -> None:
        """Otherwise it would be a type nothing could ever name: the base datatype wins."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar("uint16", "uint16")),
            },
        )
        assert findings(bag) == ["schema"]

    def test_a_transposition_is_answered_with_the_nearest_name(self, tree: Path) -> None:
        """``unit16`` is not a storage stem, so the contract lets it through as a name.

        What catches it is the check, asking the question this project asks everywhere a name
        does not resolve.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="unit16")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        assert "did you mean 'uint16'" in first(bag).render()

    def test_a_misremembered_type_name_suggests_the_declared_one(self, tree: Path) -> None:
        """The declared types are candidates too, which is the more common mistake by far."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar("Speed_t", "uint16", unit="rpm")),
                "a.ddd.json": component("A", declare("local", "X", typename="Sped_t")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        assert "did you mean 'Speed_t'?" in first(bag).render()

    def test_a_name_close_to_nothing_is_left_without_a_guess(self, tree: Path) -> None:
        """A wrong guess reads as authoritative, so no guess is better than a poor one."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="Quantity")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        assert "did you mean" not in first(bag).render()


class TestDeclaringAStructure:
    """A variable whose datatype is a structure: one c object, many a2l ones."""

    def resolve(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> Any:
        return run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*entries),
                "a.ddd.json": component(
                    "A", declare("local", "X", **{"typename": "S_t", **definition})
                ),
            },
        )

    def test_a_structured_variable_is_not_an_object(self, tree: Path) -> None:
        """It has no single datatype and no limits, so it is not one of those.

        Widening ``ResolvedObject`` to hold it would turn every reader of ``datatype`` and
        ``limits`` into a branch, and they are read unconditionally in a dozen places on the
        strength of always being there.
        """
        dictionary, bag = self.resolve(tree, struct("S_t", val("a"), val("b", "uint32")))
        assert findings(bag) == []
        assert dictionary is not None and dictionary.objects == ()
        (instance,) = dictionary.instances
        assert instance.type == "S_t"
        assert [leaf.path for leaf in dictionary.leaves] == ["X.a", "X.b"]

    def test_a_nested_structure_lengthens_the_path(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree, struct("Inner_t", val("v")), struct("S_t", val("inner", typename="Inner_t"))
        )
        assert findings(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X.inner.v"]

    def test_an_array_of_structures_contributes_one_set_per_element(self, tree: Path) -> None:
        """There is no one address describing ``cell[0].v`` and ``cell[1].v`` at the same time.

        An array of *values* is left whole, because a ``MATRIX_DIM`` describes exactly that:
        contiguous elements of one datatype. The members of two structures are a structure
        apart, so no single record can cover both.
        """
        dictionary, bag = self.resolve(
            tree,
            struct("Inner_t", val("v")),
            struct(
                "S_t",
                val("cell", typename="Inner_t", dimensions=[2]),
                val("flat", "uint8", dimensions=[4]),
            ),
        )
        assert findings(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == [
            "X.cell[0].v",
            "X.cell[1].v",
            "X.flat",
        ]
        flat = next(leaf for leaf in dictionary.leaves if leaf.path == "X.flat")
        assert flat.shape == (4,)

    def test_the_variable_itself_may_be_an_array(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t", dimensions=[2])),
            },
        )
        assert findings(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X[0].v", "X[1].v"]

    def test_a_member_takes_its_meaning_from_the_type_it_names(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint16", unit="rpm", conversion={"factor": 0.25}),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert findings(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert (leaf.unit, leaf.datatype.value) == ("rpm", "uint16")
        assert leaf.limits.as_tuple() == (0, 16383.75)

    def test_the_limits_a_scalar_type_states_reach_the_member(self, tree: Path) -> None:
        """Stated on the type once, rather than on every member and variable that uses it."""
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint16", unit="rpm", limits={"min": 0, "max": 8000}),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert findings(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.limits.as_tuple() == (0, 8000)

    def test_a_scalar_type_that_states_no_limits_has_them_derived(self, tree: Path) -> None:
        """A type states what it wants to; the rest follows as it does for any other object."""
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint8", unit="rpm"),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert findings(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.limits.as_tuple() == (0, 255)

    def test_a_leaf_knows_whether_it_is_calibration_data(self, tree: Path) -> None:
        """Taken from the variable: every member of one object has its storage class."""
        dictionary, bag = self.resolve(tree, struct("S_t", val("v")), kind="parameter")
        assert findings(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.is_calibration
        (instance,) = dictionary.instances
        assert instance.is_calibration

    def test_a_member_states_its_own_meaning_when_it_has_one(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree, struct("S_t", val("t", "uint16", unit="ms", limits={"min": 0, "max": 1000}))
        )
        assert findings(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert (leaf.unit, leaf.limits.as_tuple()) == ("ms", (0, 1000))

    def test_the_structures_come_out_in_an_order_c_can_be_written_in(self, tree: Path) -> None:
        """Alphabetical order does not do it, and this is the case that proves it.

        ``Sensor_t`` sorts before ``Status_t`` and nests it, so a template looping over the
        list in name order would declare a member of an incomplete type.
        """
        dictionary, bag = self.resolve(
            tree,
            struct("Status_t", val("flag", "uint8")),
            struct("Sensor_t", val("status", typename="Status_t")),
            struct("S_t", val("sensor", typename="Sensor_t")),
        )
        assert findings(bag) == []
        assert dictionary is not None
        assert [entry.name for entry in dictionary.types] == ["Status_t", "Sensor_t", "S_t"]

    def test_the_members_keep_the_order_they_were_written_in(self, tree: Path) -> None:
        """That order is the one the compiler lays out, so nothing may reorder it."""
        dictionary, bag = self.resolve(tree, struct("S_t", val("zulu"), val("alpha"), val("mike")))
        assert findings(bag) == []
        assert dictionary is not None
        (structure,) = dictionary.types
        assert [member.name for member in structure.members] == ["zulu", "alpha", "mike"]

    @pytest.mark.parametrize(
        ("definition", "because"),
        [
            ({"kind": "curve", "axis": "Ax"}, "refers to other objects"),
            ({"init": 3}, "written by the code that starts it"),
        ],
    )
    def test_what_a_structured_declaration_may_not_be(
        self, tree: Path, definition: dict[str, Any], because: str
    ) -> None:
        """Each refused rather than ignored, and located where it is written."""
        _, bag = self.resolve(tree, struct("S_t", val("v")), **definition)
        assert "type-kind" in findings(bag)
        assert because in first(bag).render()

    def test_a_datatype_the_project_declares_is_compared_by_name(self, tree: Path) -> None:
        """The message names the mistake instead of one of its symptoms."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
                "types.ddd.json": types(struct("A_t", val("v")), struct("B_t", val("v"))),
                "a.ddd.json": component("A", declare("output", "X", typename="A_t")),
                "b.ddd.json": component("B", declare("input", "X", typename="B_t")),
            },
        )
        assert "definition-mismatch" in findings(bag)
        assert "datatype: B_t != A_t" in messages(bag)


class TestGeneratingAStructure:
    """What a structured declaration turns into: one c object, an a2l object per member."""

    def render(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> dict[str, str]:
        files = {
            "project.ddd.json": project("Device", "types.ddd.json", "a.ddd.json"),
            "types.ddd.json": types(*entries),
            "a.ddd.json": component(
                "A",
                declare("local", "X", **{"typename": "S_t", **definition}),
                description="a component",
            ),
        }
        dictionary, bag = run_analysis(tree, files)
        assert dictionary is not None, [d.render() for d in bag]
        assert not bag.has_errors, [d.render() for d in bag]
        rendered = render_files(dictionary, tree / "gen")
        return {file.path.name: file.content for file in rendered}

    def test_the_types_header_declares_the_structure(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct(
                "S_t",
                val("plain", "uint16"),
                val("table", "uint8", dimensions=[4]),
                {"name": "flag", "member": "bits", "datatype": "uint16", "bits": 1,
                 "conversion": {}},
            ),
        )
        header = files["ddd_types.h"]
        assert "typedef struct" in header
        assert "uint16_t plain;" in header
        assert "uint8_t table[4];" in header
        # The width goes after the declarator, not after the type: a rule about c, which is
        # why the model composes the whole declaration rather than leaving it to a template.
        assert "uint16_t flag : 1;" in header
        assert "} S_t;" in header

    def test_a_nested_structure_is_declared_before_the_one_that_holds_it(self, tree: Path) -> None:
        """c needs it complete first, and the name order would have put it second."""
        files = self.render(
            tree,
            struct("Status_t", val("f", "uint8")),
            struct("S_t", val("status", typename="Status_t")),
        )
        header = files["ddd_types.h"]
        assert header.index("} Status_t;") < header.index("Status_t status;")

    def test_the_variable_declares_like_any_other(self, tree: Path) -> None:
        files = self.render(tree, struct("S_t", val("v")))
        assert "S_t X;" in files["ddd_globals.c"]
        assert "extern S_t X;" in files["ddd_globals.h"]

    def test_a_calibratable_structure_is_const_volatile(self, tree: Path) -> None:
        """The qualifier belongs to the whole object; a member cannot differ from it."""
        files = self.render(tree, struct("S_t", val("v")), kind="parameter", volatile=True)
        assert "const volatile S_t X;" in files["ddd_globals.c"]

    def test_every_member_becomes_an_a2l_object_at_its_own_path(self, tree: Path) -> None:
        """Flattened rather than described as an a2l structure.

        The name is the c expression that reads the member, so the a2l, the generated c and a
        map file all spell one thing one way.
        """
        files = self.render(
            tree,
            struct("Inner_t", val("v", "uint16", unit="degC")),
            struct("S_t", val("inner", typename="Inner_t"), val("table", "uint8", dimensions=[4])),
        )
        content = files["Device.a2l"]
        assert "/begin MEASUREMENT X.inner.v" in content
        assert 'SYMBOL_LINK "X.inner.v" 0' in content
        assert "/begin MEASUREMENT X.table" in content
        assert "MATRIX_DIM 4 1 1" in content
        # The group has to name the members, since there is no record called 'X' to name.
        assert "X.inner.v" in content.split("/begin GROUP")[1]

    def test_a_calibratable_member_is_a_characteristic(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct("S_t", val("gain", "uint16"), val("table", "uint8", dimensions=[2])),
            kind="parameter",
        )
        content = files["Device.a2l"]
        assert "/begin CHARACTERISTIC X.gain" in content
        assert "VALUE 0x00000000" in content
        assert "/begin CHARACTERISTIC X.table" in content
        assert "VAL_BLK 0x00000000" in content

    def test_a_bitfield_member_reaches_no_a2l(self, tree: Path) -> None:
        """``&s.flag`` does not compile, so no build can report where that member is.

        A ``SYMBOL_LINK`` carries a byte offset and has nowhere to put a bit position; leaving
        the mask out would claim the whole word and writing zero would claim nothing. Both are
        wrong answers dressed as output, so the member waits for a build that can say.
        """
        files = self.render(
            tree,
            struct(
                "S_t",
                val("plain", "uint16"),
                {"name": "flag", "member": "bits", "datatype": "uint16", "bits": 1,
                 "conversion": {}},
            ),
        )
        content = files["Device.a2l"]
        assert "X.plain" in content
        assert "X.flag" not in content

    def test_a_member_may_be_kept_out_of_the_a2l_on_its_own(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct("S_t", val("shown"), val("hidden", "uint16", a2l={"export": False})),
        )
        content = files["Device.a2l"]
        assert "X.shown" in content
        assert "X.hidden" not in content

    def test_keeping_the_whole_object_out_keeps_every_member_out(self, tree: Path) -> None:
        files = self.render(tree, struct("S_t", val("v")), a2l={"export": False})
        assert "X.v" not in files["Device.a2l"]

    def test_a_structured_output_nobody_reads_is_reported(self, tree: Path) -> None:
        """The same finding any other unread output gets, and for the same reason."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component("A", declare("output", "X", typename="S_t")),
            },
        )
        assert findings(bag) == ["unused-output"]

    def test_the_stdint_include_counts_the_members(self, tree: Path) -> None:
        """A project whose only integer sits inside a structure still needs the header.

        Counting only the plain objects left a header that spelled ``uint16_t`` and never
        included ``<stdint.h>`` - a generated file that does not compile.
        """
        files = self.render(tree, struct("S_t", val("v", "uint16")))
        assert "#include <stdint.h>" in files["ddd_types.h"]


class TestTypeNamesInTheCNamespace:
    """Every declared type becomes a typedef, which c keeps with the variables at file scope."""

    def test_a_type_named_after_a_c_keyword_is_refused(self, tree: Path) -> None:
        """A structure called ``register`` generates a header that does not compile."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("register", val("v"))),
            },
        )
        assert findings(bag) == ["reserved-identifier"]
        assert "reserved by the c language" in first(bag).render()

    def test_a_variable_may_not_share_a_name_with_a_type(self, tree: Path) -> None:
        """The same argument the enum names already go through, one level along."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar("Speed", "uint16")),
                "a.ddd.json": component("A", declare("local", "Speed", "uint16")),
            },
        )
        assert "name-collision" in findings(bag)
        assert "type declared here" in first(bag).render()


class TestStructuresReachEverythingElse:
    """A structured variable is an object to the rest of the tool, not a special case."""

    def project(self, tree: Path) -> Any:
        return run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    struct(
                        "S_t",
                        val("plain", "uint16", unit="rpm"),
                        {
                            "name": "mode",
                            "member": "bits",
                            "datatype": "uint8",
                            "bits": 2,
                            "conversion": {
                                "kind": "enum",
                                "name": "Mode_t",
                                "enumerators": [{"name": "M_OFF", "value": 0}],
                            },
                        },
                    )
                ),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )

    def test_an_enum_a_member_names_reaches_the_types_header(self, tree: Path) -> None:
        """Its enumerators are c identifiers like any others, and need the same typedef.

        Registering it here is also what screens its enumerators against every other name the
        project takes; a member's enum used to reach the a2l and nothing else.
        """
        dictionary, bag = self.project(tree)
        assert findings(bag) == []
        assert dictionary is not None
        assert [enum.name for enum in dictionary.enums] == ["Mode_t"]

    def test_the_members_are_counted_and_listed_as_objects(self, tree: Path) -> None:
        """A summary that counted only the plain objects told a project of two that it had none."""
        dictionary, _ = self.project(tree)
        assert dictionary is not None
        assert [entry.name for entry in dictionary.listed] == ["X.mode", "X.plain"]

    def test_a_delivery_that_drops_a_structure_does_not_pass_unnoticed(self, tree: Path) -> None:
        """The one thing ``ddd compare`` exists to prevent.

        The members are compared as the objects they are: leaving them out of the comparison
        made a delivery that dropped every structure look identical to the one before it.
        """
        from ddd.compare import compare
        from ddd.diagnostics import DiagnosticBag

        dictionary, _ = self.project(tree)
        assert dictionary is not None
        stripped = dictionary.model_copy(update={"instances": (), "leaves": ()})
        bag = DiagnosticBag()
        compare(dictionary, stripped, bag)
        assert {finding.check for finding in bag} == {"removed-unused-object"}
        assert "X.plain" in messages(bag)

    def test_a_member_that_changes_datatype_is_an_interface_change(self, tree: Path) -> None:
        from ddd.compare import compare
        from ddd.diagnostics import DiagnosticBag
        from ddd.models import Datatype

        dictionary, _ = self.project(tree)
        assert dictionary is not None
        widened = dictionary.model_copy(
            update={
                "leaves": tuple(
                    leaf.model_copy(update={"datatype": Datatype.UINT32})
                    if leaf.path == "X.plain"
                    else leaf
                    for leaf in dictionary.leaves
                )
            }
        )
        bag = DiagnosticBag()
        compare(dictionary, widened, bag)
        assert "changed-interface" in {finding.check for finding in bag}

    def test_a_member_states_no_initial_value_and_refers_to_nothing(self, tree: Path) -> None:
        """Both are what let a leaf be compared as an ordinary object without a second rule."""
        dictionary, _ = self.project(tree)
        assert dictionary is not None
        leaf = dictionary.comparable["X.plain"]
        assert leaf.init is None
        assert leaf.references == {}
