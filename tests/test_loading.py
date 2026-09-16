"""Tests for reading the file tree."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest

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
from ddd.loading import _pattern_anchor, load_dictionary, load_workspace, resolve_path


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


def test_an_entry_naming_an_existing_file_is_that_file(tree: Path) -> None:
    """A checkout under a directory whose name carries a bracket - ``C:/work/proj [v2]``, a
    copy Windows or a user names that way - made every include of the collected project file
    match nothing and every build fail: the cmake module writes its includes as literal
    absolute paths, and a path carrying one of ``*``, ``?`` or ``[`` was read as a pattern.
    A name that is a file is that file, whatever characters are in it."""
    write_tree(
        tree,
        {
            "proj [v2]/a.ddd.json": component("A", declare("local", "X")),
            "project.ddd.json": project("P", str(tree / "proj [v2]" / "a.ddd.json")),
        },
    )
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert workspace is not None
    assert checks(bag) == []
    assert [loaded.name for loaded in workspace.components] == ["A"]


def test_a_pattern_is_still_a_pattern_where_no_such_file_exists(tree: Path) -> None:
    """The literal reading is tried first and falls through: nothing is named ``a[12].ddd.json``
    here, so the class still matches ``a1.ddd.json`` and ``a2.ddd.json``."""
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a[12].ddd.json"),
            "a1.ddd.json": component("A1", declare("local", "X")),
            "a2.ddd.json": component("A2", declare("local", "Y")),
        },
    )
    assert checks(bag) == []
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["A1", "A2"]


def test_a_pattern_naming_a_file_of_its_own_name_reads_that_file(tree: Path) -> None:
    """Where both readings are possible the file wins, which is what makes a literal path
    safe to write; a project wanting the class renames the file it collides with."""
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a[12].ddd.json"),
            "a[12].ddd.json": component("Literal", declare("local", "X")),
            "a1.ddd.json": component("A1", declare("local", "Y")),
        },
    )
    assert checks(bag) == []
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["Literal"]


def test_a_pattern_that_matches_nothing_and_names_nothing_is_still_empty(tree: Path) -> None:
    """The finding of an entry with a wildcard character stays ``include-empty``: a pattern
    may legitimately match nothing, where a named file must not be missing."""
    _, bag = run_analysis(tree, {"project.ddd.json": project("P", "a[12].ddd.json")})
    assert checks(bag) == ["include-empty"]
    assert "matches no file" in messages(bag)


def test_the_matches_of_a_pattern_are_ordered_by_code_point(tree: Path) -> None:
    """The order of the matches is the order of the components, and it reaches the artefacts.

    Sorting the resolved paths as the platform compares them put ``alpha`` before ``Zeta`` on
    Windows and ``Zeta`` before ``alpha`` on Linux, so one project generated two different
    definition files and two different a2l files depending on the machine that built it -
    against the promise that the same project generates the same bytes on any machine. The
    key is the POSIX spelling, which is what names are already ordered by.
    """
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "components/*.ddd.json"),
            "components/Zeta.ddd.json": component("Zeta", declare("local", "X")),
            "components/alpha.ddd.json": component("alpha", declare("local", "Y")),
            "components/_under.ddd.json": component("Under", declare("local", "Z")),
        },
    )
    assert checks(bag) == []
    assert dictionary is not None
    assert [loaded.name for loaded in dictionary.components] == ["Zeta", "Under", "alpha"]


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


def test_a_file_reached_deep_before_shallow_is_not_reported_for_depth_either(
    tree: Path,
) -> None:
    """The same tree as above with the two entries of the root written the other way round.

    The over-deep route is walked first now, so ``leaf.ddd.json`` is not in ``_seen_paths``
    yet when the entry at level sixty five names it, and the diamond test cannot excuse it.
    Held back rather than reported, that crossing is answered once the whole tree is read -
    by which time the root's own entry has read the file - so the run is as silent as it is
    the other way round. Which of two includes an author happened to write first is not a
    fact about the tree, and cannot be what decides whether the tree has a finding.
    """
    files: dict[str, Any] = {
        "project.ddd.json": project("P", "p1.ddd.json", "leaf.ddd.json"),
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


def test_two_over_deep_entries_naming_the_same_unread_file_are_two_findings(
    tree: Path,
) -> None:
    """One finding per entry that crosses the cap, not one per file left out.

    ``left.ddd.json`` and ``right.ddd.json`` sit at level sixty four, the deepest DDD reads,
    and both name ``deep.ddd.json``; no shallower entry does, so the file really is left out
    and both entries are lines someone wrote and can shorten. Reporting the file once would
    have to pick one of the two, and the one it picks is whichever route the loader walked
    first - which is the ordering holding the finding back is here to make invisible.
    """
    files: dict[str, Any] = {"project.ddd.json": project("P", "p1.ddd.json")}
    for index in range(1, 62):
        files[f"p{index}.ddd.json"] = project(f"P{index}", f"p{index + 1}.ddd.json")
    files["p62.ddd.json"] = project("P62", "left.ddd.json", "right.ddd.json")
    files["left.ddd.json"] = project("Left", "deep.ddd.json")
    files["right.ddd.json"] = project("Right", "deep.ddd.json")
    files["deep.ddd.json"] = component("Deep", declare("local", "X"))
    write_tree(tree, files)
    bag = DiagnosticBag()
    workspace = load_workspace(tree / "project.ddd.json", bag)
    assert checks(bag) == ["include-depth", "include-depth"]
    rendered = messages(bag)
    assert "left.ddd.json#project.includes[0]" in rendered
    assert "right.ddd.json#project.includes[0]" in rendered
    assert "'deep.ddd.json' is included 65 levels deep" in rendered
    assert workspace is not None
    assert workspace.components == ()


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

    @staticmethod
    def _under_a_definition(tree: Path, extensions: dict[str, Any]) -> DiagnosticBag:
        write_tree(
            tree,
            {"a.ddd.json": component("A", declare("local", "X", extensions=extensions))},
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        return bag

    @pytest.mark.parametrize("name", ["my-plugin", "map", "axis", "enum", "string", "linear"])
    def test_a_key_below_a_union_tag_is_named_in_the_pointer(self, tree: Path, name: str) -> None:
        """A definition is a tagged union and pydantic reports the tag it chose as a path
        segment. The walk steps over the tag; losing the document with it left every key
        below judged by shape alone, so a punctuated one - or one spelled like another
        variant, all of them legal plugin names - was dropped and the editor underlined the
        whole block."""
        bag = self._under_a_definition(tree, {name: 1})
        assert f"definition.extensions.{name}: error[schema]" in messages(bag), messages(bag)

    def test_two_malformed_blocks_in_one_definition_are_two_findings(self, tree: Path) -> None:
        """One finding per place, and these are two places: the reader who fixes the first
        used to run again to meet the second."""
        bag = self._under_a_definition(tree, {"a-b": 1, "c-d": 2})
        assert len(bag) == 2, messages(bag)
        assert "definition.extensions.a-b: error[schema]" in messages(bag), messages(bag)
        assert "definition.extensions.c-d: error[schema]" in messages(bag), messages(bag)

    def test_two_blocks_named_after_variants_are_two_findings(self, tree: Path) -> None:
        bag = self._under_a_definition(tree, {"map": [1], "axis": [2]})
        assert len(bag) == 2, messages(bag)
        assert "definition.extensions.map: error[schema]" in messages(bag), messages(bag)
        assert "definition.extensions.axis: error[schema]" in messages(bag), messages(bag)

    def test_two_plainly_named_blocks_are_still_two_findings(self, tree: Path) -> None:
        """The control: a key nothing mistakes for a tag was reported twice all along."""
        bag = self._under_a_definition(tree, {"aa": 1, "bb": 2})
        assert len(bag) == 2, messages(bag)

    def test_two_malformed_blocks_on_the_project_are_two_findings(self, tree: Path) -> None:
        write_tree(
            tree,
            {"project.ddd.json": {"project": {"name": "P", "extensions": {"a-b": 1, "c-d": 2}}}},
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert len(bag) == 2, messages(bag)
        assert "project.extensions.a-b: error[schema]" in messages(bag), messages(bag)
        assert "project.extensions.c-d: error[schema]" in messages(bag), messages(bag)


class TestPathsAsWritten:
    """A path is read as the author wrote it; expansion is the shell's business."""

    def test_a_name_beginning_with_a_tilde_names_a_file(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``~x.ddd.json`` used to be looked for in user ``x``'s home directory."""
        write_tree(tree, {"~x.ddd.json": component("A", declare("local", "X"))})
        monkeypatch.chdir(tree)
        bag = DiagnosticBag()
        assert load_workspace(Path("~x.ddd.json"), bag) is not None, messages(bag)
        assert checks(bag) == []

    def test_resolve_path_leaves_a_tilde_where_it_stands(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tree)
        assert resolve_path(Path("~x.ddd.json")) == resolve_path(tree) / "~x.ddd.json"


class TestTheMappingFormOfEnumerators:
    """The shorthand is rewritten into the list the model holds, and the file is not."""

    @staticmethod
    def _with(tree: Path, enumerators: Any) -> DiagnosticBag:
        write_tree(
            tree,
            {
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "X",
                        conversion={"kind": "enum", "name": "E", "enumerators": enumerators},
                    ),
                )
            },
        )
        bag = DiagnosticBag()
        assert load_workspace(tree / "a.ddd.json", bag) is None
        return bag

    def test_a_bad_value_is_located_at_the_key_that_holds_it(self, tree: Path) -> None:
        """``enumerators[0].value`` named neither a key nor an index the file has."""
        bag = self._with(tree, {"A": "x"})
        assert "definition.conversion.enumerators.A: error[schema]" in messages(bag), messages(bag)

    def test_a_bad_name_is_located_at_the_entry_that_spells_it(self, tree: Path) -> None:
        bag = self._with(tree, {"1bad": 0})
        assert "definition.conversion.enumerators.1bad: error[schema]" in messages(bag), messages(
            bag
        )

    def test_the_second_entry_is_located_at_the_second_key(self, tree: Path) -> None:
        """The i-th key, not the first: a mapping keeps the order it was written in."""
        bag = self._with(tree, {"A": 0, "B": "x"})
        assert "definition.conversion.enumerators.B: error[schema]" in messages(bag), messages(bag)

    def test_the_list_form_is_still_indexed(self, tree: Path) -> None:
        """The control: written as a list, the file does have an ``[1]`` to point at."""
        bag = self._with(tree, [{"name": "A", "value": 0}, {"name": "B", "value": "x"}])
        assert "definition.conversion.enumerators[1].value: error[schema]" in messages(bag), (
            messages(bag)
        )


class TestWhereAWildcardIncludeStartsWalking:
    """A pattern starts where the literal reading of the same entry would join it.

    On Windows a spelling can carry an anchor and still not be absolute: ``/shared/*.json``
    is rooted on whatever drive the process is on, and ``C:*.json`` means "on drive C, in
    whatever directory I am". Taken as the whole base, either made the expansion depend on
    where ``ddd`` was run from, while the same spelling written without a wildcard was
    joined onto the project's own directory - two answers to one question.
    """

    def test_a_relative_pattern_starts_at_the_file_that_names_it(self) -> None:
        assert _pattern_anchor(PurePosixPath("/proj"), PurePosixPath("sub/*.json")) == (
            PurePosixPath("/proj")
        )

    def test_a_posix_rooted_pattern_starts_at_the_root(self) -> None:
        assert _pattern_anchor(PurePosixPath("/proj"), PurePosixPath("/shared/*.json")) == (
            PurePosixPath("/")
        )

    def test_a_windows_rooted_pattern_starts_on_the_project_s_own_drive(self) -> None:
        assert _pattern_anchor(PureWindowsPath("D:/proj"), PureWindowsPath("/shared/*.json")) == (
            PureWindowsPath("D:/")
        )

    def test_a_drive_relative_pattern_starts_where_the_literal_would(self) -> None:
        assert _pattern_anchor(PureWindowsPath("C:/proj"), PureWindowsPath("C:*.json")) == (
            PureWindowsPath("C:/proj")
        )

    def test_a_pattern_on_another_drive_starts_there(self) -> None:
        assert _pattern_anchor(PureWindowsPath("C:/proj"), PureWindowsPath("D:/lib/*.json")) == (
            PureWindowsPath("D:/")
        )


class TestWhatADumpedDictionaryIsToldAboutItself:
    """A dump is read by the same reader a description is, and located the same way.

    The document was not handed to the reporter, so every pointer below the first place was
    judged by its spelling alone - which is how a punctuated key vanished from a finding
    about a description, and the fix for that one did not reach this path.
    """

    @staticmethod
    def _dumped(tree: Path, **extra: Any) -> DiagnosticBag:
        write_tree(tree, {"d.json": {"format": 1, "name": "P", "objects": [], **extra}})
        bag = DiagnosticBag()
        assert load_dictionary(tree / "d.json", bag) is None
        return bag

    def test_two_malformed_blocks_are_two_findings_naming_their_keys(self, tree: Path) -> None:
        bag = self._dumped(tree, extensions={"a-b": 1, "c-d": 2})
        assert len(bag) == 2, messages(bag)
        assert "d.json#extensions.a-b: error[schema]" in messages(bag), messages(bag)
        assert "d.json#extensions.c-d: error[schema]" in messages(bag), messages(bag)
