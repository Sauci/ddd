"""Reading structured datatype files, and checking the graph they form.

The model level rules are in ``test_types.py``; these are the ones that need more than one
file, or the rest of the project, to have any meaning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace


def val(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return {"name": name, "member": "value", "kind": "measurement", "datatype": datatype, **extra}


def nest(name: str, type_name: str) -> dict[str, Any]:
    return {"name": name, "member": "struct", "type": type_name}


def struct(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "members": list(members) or [val("value")]}


def types(*structures: dict[str, Any]) -> dict[str, Any]:
    return {"types": list(structures)}


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
