"""Tests for reading the file tree."""

from __future__ import annotations

from pathlib import Path

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    run_analysis,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace


def test_project_with_components(tree: Path) -> None:
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "X")),
            "b.ddd.json": component("B", declare("input", "X")),
        },
    )
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["A", "B"]
    assert dictionary.name == "P"
    assert checks(bag) == []


def test_nested_sub_project(tree: Path) -> None:
    write_tree(
        tree,
        {
            "project.ddd.json": project("Top", "a.ddd.json", "sub/sub.ddd.json"),
            "a.ddd.json": component("A", declare("output", "X")),
            "sub/sub.ddd.json": project("Sub", "b.ddd.json"),
            "sub/b.ddd.json": component("B", declare("input", "X")),
        },
    )
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert workspace is not None
    assert [loaded.name for loaded in workspace.components] == ["A", "B"]
    assert workspace.components[1].parents == ("Top", "Sub")


def test_glob_include(tree: Path) -> None:
    dictionary, _ = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "components/*.ddd.json"),
            "components/a.ddd.json": component("A", declare("output", "X")),
            "components/b.ddd.json": component("B", declare("input", "X")),
        },
    )
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["A", "B"]


def test_glob_matching_nothing_is_reported(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": project("P", "components/*.ddd.json")})
    assert checks(bag) == ["include-empty"]


def test_glob_does_not_include_the_project_itself(tree: Path) -> None:
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "*.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        },
    )
    assert dictionary is not None
    assert checks(bag) == []


def test_missing_file(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": project("P", "nope.ddd.json")})
    assert checks(bag) == ["file-not-found"]


def test_missing_root_file(tree: Path) -> None:
    bag = DiagnosticBag()
    assert load_workspace(tree / "absent.ddd.json", bag) is None
    assert checks(bag) == ["file-not-found"]


def test_broken_json(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": "{ not json"})
    assert checks(bag) == ["json-syntax"]
    assert next(iter(bag)).location is not None
    assert next(iter(bag)).location.line == 1


def test_unknown_top_level_key(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": {"components": []}})
    assert checks(bag) == ["file-kind"]
    assert "missing top level key" in next(iter(bag)).message


def test_both_top_level_keys(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": {"project": {}, "component": {}}})
    assert checks(bag) == ["file-kind"]


def test_top_level_array(tree: Path) -> None:
    _, bag = run_analysis(tree, {"project.ddd.json": [1, 2]})
    assert checks(bag) == ["file-kind"]


def test_schema_error_points_at_the_offending_value(tree: Path) -> None:
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("output", "X", datatype="uint7")),
        },
    )
    assert checks(bag) == ["schema"]
    location = next(iter(bag)).location
    assert location is not None
    assert location.pointer == "component.declarations[0].definition.datatype"
    assert location.path.name == "a.ddd.json"


def test_include_cycle(tree: Path) -> None:
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "sub.ddd.json"),
            "sub.ddd.json": project("Sub", "project.ddd.json"),
        },
    )
    assert checks(bag) == ["include-cycle"]


def test_diamond_include_loads_the_component_once(tree: Path) -> None:
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "left.ddd.json", "right.ddd.json"),
            "left.ddd.json": project("Left", "shared.ddd.json"),
            "right.ddd.json": project("Right", "shared.ddd.json"),
            "shared.ddd.json": component("Shared", declare("local", "X")),
        },
    )
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["Shared"]
    assert checks(bag) == []


def test_duplicate_component_name(tree: Path) -> None:
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("Same", declare("local", "X")),
            "b.ddd.json": component("Same", declare("local", "Y")),
        },
    )
    assert checks(bag) == ["duplicate-component"]


def test_component_file_as_root(tree: Path) -> None:
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "a.ddd.json", bag)
    assert workspace is not None
    assert workspace.name == "A"
    assert len(workspace.components) == 1


def test_absolute_include(tree: Path) -> None:
    write_tree(tree, {"other/a.ddd.json": component("A", declare("local", "X"))})
    dictionary, bag = run_analysis(
        tree,
        {"project.ddd.json": project("P", (tree / "other" / "a.ddd.json").as_posix())},
    )
    assert dictionary is not None
    assert checks(bag) == []


def test_a_description_file_must_use_the_ddd_extension(tree: Path) -> None:
    write_tree(tree, {"plain.json": component("A", declare("local", "X"))})
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "plain.json", bag)
    assert workspace is not None  # the file is still loaded, only its name is wrong
    assert checks(bag) == ["file-extension"]
    assert "has to be named '*.ddd.json'" in messages(bag)


def test_an_included_file_must_use_the_ddd_extension(tree: Path) -> None:
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "plain.json"),
            "plain.json": component("A", declare("local", "X")),
        },
    )
    assert checks(bag) == ["file-extension"]


def test_the_extension_check_can_be_relaxed(tree: Path) -> None:
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "plain.json"),
            "plain.json": component("A", declare("local", "X")),
        },
        severities=["file-extension=ignore"],
    )
    assert dictionary is not None
    assert checks(bag) == []


def test_the_extension_is_matched_case_insensitively(tree: Path) -> None:
    write_tree(tree, {"Shouty.DDD.JSON": component("A", declare("local", "X"))})
    bag = DiagnosticBag()
    assert load_workspace(tree / "Shouty.DDD.JSON", bag) is not None
    assert checks(bag) == []


def test_a_missing_file_is_not_also_reported_as_badly_named(tree: Path) -> None:
    bag = DiagnosticBag()
    assert load_workspace(tree / "absent.json", bag) is None
    assert checks(bag) == ["file-not-found"]
