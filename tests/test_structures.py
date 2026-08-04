"""Reading structured datatype files, and checking the graph they form.

The model level rules are in ``test_types.py``; these are the ones that need more than one
file, or the rest of the project, to have any meaning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import component, declare, project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace


def val(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return {"name": name, "member": "value", "datatype": datatype, **extra}


def nest(name: str, type_name: str) -> dict[str, Any]:
    """A member that nests another structure, which is a value member naming it."""
    return val(name, type_name)


def struct(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members) or [val("value")]}


def scalar(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return {"type": "scalar", "name": name, "datatype": datatype, **extra}


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
                    "A", declare("local", "X", **{"datatype": "Speed_t", **definition})
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
                "a.ddd.json": component("A", declare("output", "EngSpd", datatype="Speed_t")),
                "b.ddd.json": component("B", declare("input", "EngSpd", datatype="Speed_t")),
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
                "a.ddd.json": component("A", declare("local", "X", datatype="Nowhere_t")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        rendered = first(bag).render()
        assert "neither a base datatype nor a type" in rendered
        assert "a.ddd.json#component.declarations[0].definition.datatype" in rendered

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
                    scalar("Speed_t", "uint16"), struct("S_t", val("v", "Speed_t"))
                ),
            },
        )
        assert findings(bag) == []

    def test_naming_a_structure_is_not_available_yet(self, tree: Path) -> None:
        """Reported rather than half generated, and located at the datatype that names it.

        The structure reaches the generated c and the a2l in a later step; until it does, a
        declaration naming one is refused outright, because the alternative is a variable in
        the dictionary with no storage anything can allocate.
        """
        bag = self.project_with(tree, struct("Speed_t", val("v")))
        assert findings(bag) == ["type-kind"]
        rendered = first(bag).render()
        assert "cannot name a structure yet" in rendered
        assert "declared here" in rendered


class TestATypeNameCannotBeADatatypeInDisguise:
    """The protection that pays for one key naming both.

    ``datatype`` accepting a declared name means a mistyped base datatype is a well formed
    *name*, which would otherwise reach the editor as valid and the reader as a variable with
    storage nobody meant. Two layers answer it: the contract refuses a word that is a storage
    stem with the digits wrong, and the check suggests the nearest name for everything else.
    """

    def test_a_mistyped_base_datatype_is_refused_by_the_contract(self, tree: Path) -> None:
        """Refused where it is typed rather than reported a build later.

        Under a plain identifier rule ``uint166`` is a name like any other, so the editor would
        accept it and the run would report a type nobody declares - true, and much later than
        the moment it could have been caught.
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
        assert "a.ddd.json#component.declarations[0].definition.datatype" in rendered
        assert "Input should be" in rendered

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
                "a.ddd.json": component("A", declare("local", "X", datatype="unit16")),
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
                "a.ddd.json": component("A", declare("local", "X", datatype="Sped_t")),
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
                "a.ddd.json": component("A", declare("local", "X", datatype="Quantity")),
            },
        )
        assert findings(bag) == ["unknown-type"]
        assert "did you mean" not in first(bag).render()
