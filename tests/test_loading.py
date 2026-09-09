"""Tests for reading the file tree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def test_a_repeated_key_is_refused(tree: Path) -> None:
    """json lets one object spell a key twice, and parsers silently keep the last spelling.

    The author reads the first one, the tool would use the second, and in a grown file
    that is a debugging session; refused at the parser, it is a finding instead.
    """
    _, bag = run_analysis(
        tree, {"project.ddd.json": '{"project": {"name": "P", "name": "Q", "includes": []}}'}
    )
    assert checks(bag) == ["json-syntax"]
    assert "key 'name' appears twice" in next(iter(bag)).message


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
    # ``datatype`` also accepts the name of a declared type, so a typo in a base datatype is a
    # perfectly well formed name and would slip past the contract - except that a name reading
    # as a storage stem with the digits wrong is refused outright. See TYPE_NAME_PATTERN.
    assert checks(bag) == ["schema"]
    location = next(iter(bag)).location
    assert location is not None
    assert location.pointer == "component.interface[0].definition.datatype"
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


def _include_chain(depth: int) -> dict[str, Any]:
    """A root project over ``depth`` sub-projects, each including the next one.

    Two components hang off it: ``Top`` beside the chain and ``Deep`` under its last project,
    so which of them the workspace carries says how far down the loader read.
    """
    files: dict[str, Any] = {
        "project.ddd.json": project("P0", "p1.ddd.json", "top.ddd.json"),
        "top.ddd.json": component("Top", declare("local", "X")),
        f"p{depth}.ddd.json": project(f"P{depth}", "deep.ddd.json"),
        "deep.ddd.json": component("Deep", declare("local", "Y")),
    }
    for index in range(1, depth):
        files[f"p{index}.ddd.json"] = project(f"P{index}", f"p{index + 1}.ddd.json")
    return files


def test_an_include_tree_deeper_than_the_cap_stops_where_it_crosses(tree: Path) -> None:
    """Sixty five projects deep: the entry naming the sixty fifth is refused, and that is all.

    The rest of the run stands - ``Top``, included beside the chain, is loaded - because a
    tree DDD will not follow says nothing about the files it can read.
    """
    write_tree(tree, _include_chain(64))
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert checks(bag) == ["include-depth"]
    rendered = messages(bag)
    assert "p63.ddd.json#project.includes[0]" in rendered
    assert "'p64.ddd.json' is included 65 levels deep; DDD reads at most 64" in rendered
    assert workspace is not None
    assert [loaded.name for loaded in workspace.components] == ["Top"]


def test_five_hundred_nested_projects_are_a_finding_rather_than_a_traceback(tree: Path) -> None:
    """The loader walks the include tree by recursion, and python gives up long before 500."""
    write_tree(tree, _include_chain(500))
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert checks(bag) == ["include-depth"]
    assert workspace is not None
    assert [loaded.name for loaded in workspace.components] == ["Top"]


def test_the_deepest_tree_there_is_gets_read_whole(tree: Path) -> None:
    """The root counts as the first level, so this one is exactly 64 levels deep.

    Sixty two sub-projects under the root, and ``Deep`` included by the last of them; nothing
    is refused, and a level of any kind counts, not only a level of projects.
    """
    write_tree(tree, _include_chain(62))
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert checks(bag) == []
    assert workspace is not None
    assert len(workspace.projects) == 63
    assert [loaded.name for loaded in workspace.components] == ["Deep", "Top"]


def test_a_file_already_seen_through_a_shallow_route_is_not_reported_for_depth(
    tree: Path,
) -> None:
    """A diamond that closes on an over-deep route is still a diamond, not a depth refusal.

    ``leaf.ddd.json`` is read once, directly, at level two. A second, sixty three project
    chain reaches for the same file again from a project at level sixty four - the deepest a
    project loads - so naming ``leaf.ddd.json`` there sits at level sixty five, one past the
    cap; no other file on that chain is over the limit, so the leaf is the only over-deep
    entry. Testing ``_seen_paths`` before the depth cap means that second attempt finds the
    file already in the workspace and reuses it in silence, rather than reporting
    ``include-depth`` and saying everything under it was left out - false, since it was
    already read whole through the shallow route.
    """
    files: dict[str, Any] = {
        "project.ddd.json": project("P", "leaf.ddd.json", "p1.ddd.json"),
        "leaf.ddd.json": component("Leaf", declare("local", "X")),
    }
    for index in range(1, 63):
        files[f"p{index}.ddd.json"] = project(f"P{index}", f"p{index + 1}.ddd.json")
    files["p63.ddd.json"] = project("P63", "leaf.ddd.json")
    write_tree(tree, files)
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert checks(bag) == []
    assert workspace is not None
    assert [loaded.name for loaded in workspace.components] == ["Leaf"]


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


class TestSchemaBinding:
    """The one unknown-looking key that has to be allowed: the editor's schema binding."""

    def test_every_hand_written_file_kind_accepts_a_schema_key(self, tree: Path) -> None:
        """`$schema` is how an editor binds a file to `ddd schema -o` output.

        Rejecting it would block completion and as-you-type validation - the cheap version
        of every authoring aid - while accepting any other unknown key would let typos
        through. So exactly this key is modelled, and DDD ignores its value.
        """
        write_tree(
            tree,
            {
                "project.ddd.json": {
                    "$schema": "./schemas/project.schema.json",
                    "project": {"name": "P", "includes": ["a.ddd.json"]},
                },
                "a.ddd.json": {
                    "$schema": "./schemas/component.schema.json",
                    **component("A", declare("local", "val")),
                },
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None
        assert not bag.has_errors, [d.render() for d in bag]

    def test_any_other_unknown_key_is_still_a_typo(self, tree: Path) -> None:
        write_tree(
            tree,
            {"a.ddd.json": {"schema": "./x.json", **component("A", declare("local", "X"))}},
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        assert "Extra inputs are not permitted" in messages(bag)


class TestPointersWithPunctuation:
    def test_a_key_with_a_hyphen_is_named_in_the_pointer(self, tree: Path) -> None:
        """A branch of a union is recognised as one; a key of the document, however spelled,
        is not mistaken for one and dropped from the place a finding names."""
        write_tree(
            tree,
            {
                "project.ddd.json": {
                    "project": {"name": "P", "extensions": {"my-plugin": "not an object"}}
                }
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert "project.ddd.json#project.extensions.my-plugin: error[schema]" in messages(bag)
