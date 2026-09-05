"""Tests of the plugin mechanism: the object, loading, the keys, the blocks and the hooks.

The example plugin under ``examples/plugins`` is tested separately; what is tested here is
the api it is written against, with a plugin small enough to live in this file.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest
from pydantic import BaseModel, ValidationError

from conftest import (
    TEMPLATES,
    checks,
    component,
    declare,
    messages,
    project,
    run_analysis,
    write_tree,
)
from ddd.analysis import analyze
from ddd.backends import CBackend, render
from ddd.cli import (
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_USAGE,
    _plugin_artefact,
    _plugins_from_arguments,
    main,
    schema_text,
)
from ddd.diagnostics import (
    CHECKS,
    CheckInfo,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.ir import DICTIONARY_FORMAT, DataDictionary
from ddd.loading import load_dictionary, load_workspace
from ddd.lsp import analyse_standalone
from ddd.models import ComponentFile, ProjectFile
from ddd.plugins import (
    Plugin,
    PluginError,
    PluginInvalidError,
    PluginNotFoundError,
    backend_of,
    load_plugin,
    settings_of,
)

TAG_PLUGIN = '''
"""A plugin that tags an object; the smallest consumer of every hook."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ddd.backends import GeneratedFile
from ddd.diagnostics import CheckInfo, Severity
from ddd.ir import DataDictionary
from ddd.plugins import CheckContext, CompareContext, GenerateContext, Plugin


class Tag(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tag: str


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    prefix: str = ""


def check(context: CheckContext) -> None:
    assert isinstance(context.settings, Settings)
    for entry in (*context.dictionary.objects, *context.dictionary.instances):
        block = entry.extensions.get("tag")
        if block is not None and not block["tag"].startswith(context.settings.prefix):
            context.bag.add(
                "tag/bad-prefix",
                f"'{entry.name}' is tagged '{block['tag']}', outside '{context.settings.prefix}'",
                context.locate(entry.name),
            )


def compare(context: CompareContext) -> None:
    for entry in context.candidate.objects:
        was = context.baseline.by_name.get(entry.name)
        if was is not None and was.extensions.get("tag") != entry.extensions.get("tag"):
            context.bag.add(
                "tag/retagged", f"'{entry.name}' was retagged", context.locate(entry.name)
            )


class TagBackend:
    name = "tag"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        lines = [
            f"{entry.name} {entry.extensions['tag']['tag']}"
            for entry in dictionary.objects
            if "tag" in entry.extensions
        ]
        return [GeneratedFile(output_dir / "tags.txt", "\\n".join(lines) + "\\n")]


def backend(context: GenerateContext) -> TagBackend:
    assert isinstance(context.settings, Settings)
    return TagBackend(context.settings)


PLUGIN = Plugin(
    name="tag",
    object_model=Tag,
    project_model=Settings,
    checks=(
        CheckInfo("tag/bad-prefix", Severity.WARNING, "a tag is outside the project's prefix"),
        CheckInfo("tag/retagged", Severity.ERROR, "the tag of an object changed"),
    ),
    check=check,
    compare=compare,
    backend=backend,
)
'''


def write_plugin(base: Path, name: str = "tag_plugin.py", source: str = TAG_PLUGIN) -> Path:
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


class TestThePluginObject:
    def test_a_plugin_needs_nothing_but_a_name(self) -> None:
        plugin = Plugin(name="bare")
        assert plugin.object_model is None
        assert plugin.checks == ()

    @pytest.mark.parametrize("name", ["Tag", "1tag", "tag-x", "", "tag/x"])
    def test_a_name_is_a_lowercase_identifier(self, name: str) -> None:
        with pytest.raises(ValueError, match="lowercase identifier"):
            Plugin(name=name)

    @pytest.mark.parametrize("identifier", ["bad-prefix", "other/bad-prefix", "tag/Bad", "tag/"])
    def test_a_check_is_spelled_with_the_plugin_name_and_a_slash(self, identifier: str) -> None:
        with pytest.raises(ValueError, match="is not spelled 'tag/<check>'"):
            Plugin(name="tag", checks=(CheckInfo(identifier, Severity.ERROR, "x"),))

    def test_a_check_is_registered_once(self) -> None:
        info = CheckInfo("tag/twice", Severity.ERROR, "x")
        with pytest.raises(ValueError, match="registers check 'tag/twice' twice"):
            Plugin(name="tag", checks=(info, info))


class TestLoading:
    def test_a_path_is_relative_to_the_base(self, tmp_path: Path) -> None:
        write_plugin(tmp_path / "tools")
        plugin = load_plugin("tools/tag_plugin.py", tmp_path)
        assert plugin.name == "tag"

    def test_an_absolute_path_is_taken_as_written(self, tmp_path: Path) -> None:
        path = write_plugin(tmp_path)
        assert load_plugin(str(path), Path("/elsewhere")).name == "tag"

    def test_the_same_file_loads_to_the_same_object(self, tmp_path: Path) -> None:
        """Which is what lets the loader tell 'named twice' from 'two plugins, one name'."""
        write_plugin(tmp_path)
        assert load_plugin("tag_plugin.py", tmp_path) is load_plugin("./tag_plugin.py", tmp_path)

    def test_a_module_name_imports_from_the_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_plugin(tmp_path, "installed_tag_plugin.py")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            assert load_plugin("installed_tag_plugin", tmp_path).name == "tag"
        finally:
            sys.modules.pop("installed_tag_plugin", None)

    def test_a_missing_file_is_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(PluginNotFoundError, match="does not exist"):
            load_plugin("nowhere.py", tmp_path)

    def test_a_missing_module_is_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(PluginNotFoundError, match="not an importable module"):
            load_plugin("ddd_no_such_plugin_module", tmp_path)

    def test_a_file_that_raises_on_import_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "broken.py", "raise RuntimeError('boom')\n")
        with pytest.raises(PluginInvalidError, match="failed to import: boom"):
            load_plugin("broken.py", tmp_path)

    def test_a_module_whose_own_import_is_missing_is_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The module exists; something it needs does not. That is not 'not found'."""
        write_plugin(tmp_path, "needs_dep.py", "import ddd_no_such_dependency\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            with pytest.raises(PluginInvalidError, match="failed to import"):
                load_plugin("needs_dep", tmp_path)
        finally:
            sys.modules.pop("needs_dep", None)

    def test_a_module_whose_name_extends_a_missing_dependencys_name_is_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'reqplugin' importing missing 'req' is not 'reqplugin' itself being missing: a raw
        prefix match would say so, but the dotted-path boundary does not."""
        write_plugin(tmp_path, "reqplugin.py", "import req\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            with pytest.raises(PluginInvalidError, match="failed to import"):
                load_plugin("reqplugin", tmp_path)
        finally:
            sys.modules.pop("reqplugin", None)

    def test_a_module_that_raises_on_import_is_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_plugin(tmp_path, "raises_on_import.py", "raise RuntimeError('boom')\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            with pytest.raises(PluginInvalidError, match="failed to import: boom"):
                load_plugin("raises_on_import", tmp_path)
        finally:
            sys.modules.pop("raises_on_import", None)

    def test_a_module_without_a_plugin_object_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "empty.py", "X = 1\n")
        with pytest.raises(PluginInvalidError, match="exposes no PLUGIN"):
            load_plugin("empty.py", tmp_path)

    def test_a_plugin_object_of_the_wrong_type_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "wrong.py", "PLUGIN = object()\n")
        with pytest.raises(PluginInvalidError, match="exposes no PLUGIN"):
            load_plugin("wrong.py", tmp_path)


class TestTheKeys:
    def test_a_definition_carries_blocks_keyed_by_plugin(self) -> None:
        model = ComponentFile.model_validate(
            component("A", declare("local", "X", extensions={"tag": {"tag": "t"}}))
        )
        assert model.component.interface[0].definition.extensions == {"tag": {"tag": "t"}}

    def test_a_definition_without_blocks_has_none(self) -> None:
        model = ComponentFile.model_validate(component("A", declare("local", "X")))
        assert model.component.interface[0].definition.extensions == {}

    def test_a_block_is_an_object(self) -> None:
        with pytest.raises(ValidationError):
            ComponentFile.model_validate(
                component("A", declare("local", "X", extensions={"tag": "not an object"}))
            )

    def test_a_project_names_its_plugins_and_their_settings(self) -> None:
        model = ProjectFile.model_validate(
            project("P", plugins=["tools/tag.py"], extensions={"tag": {"prefix": "p"}})
        )
        assert model.project.plugins == ("tools/tag.py",)
        assert model.project.extensions == {"tag": {"prefix": "p"}}

    def test_an_empty_plugin_spelling_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ProjectFile.model_validate(project("P", plugins=[""]))

    def test_a_project_hashes_despite_its_settings_dict(self) -> None:
        loaded = ProjectFile.model_validate(
            project("P", extensions={"tag": {"prefix": "p"}})
        ).project
        hash(loaded)  # must not raise
        again = ProjectFile.model_validate(
            project("P", extensions={"tag": {"prefix": "p"}})
        ).project
        assert loaded == again
        assert hash(loaded) == hash(again)


class TestThePolicy:
    """A plugin's checks are known only once the project is read; the policy is parsed first."""

    def test_an_override_of_a_plugin_check_is_kept_provisionally(self) -> None:
        policy = SeverityPolicy.from_strings(["tag/bad-prefix=error", "unused-output=info"])
        assert policy.provisional == ("tag/bad-prefix",)
        assert policy.overrides["tag/bad-prefix"] is Severity.ERROR

    def test_a_bad_severity_on_a_provisional_override_is_still_refused(self) -> None:
        with pytest.raises(UnknownCheckError, match="unknown severity 'loud'"):
            SeverityPolicy.from_strings(["tag/bad-prefix=loud"])

    def test_verifying_holds_the_provisional_overrides_to_what_was_registered(self) -> None:
        policy = SeverityPolicy.from_strings(["tag/bad-prefix=error"])
        info = CheckInfo("tag/bad-prefix", Severity.WARNING, "x")
        policy.verify({"tag/bad-prefix": info})
        with pytest.raises(UnknownCheckError, match="no loaded plugin registers it"):
            policy.verify({})

    def test_a_registered_check_resolves_like_a_built_in_one(self) -> None:
        info = CheckInfo("tag/bad-prefix", Severity.WARNING, "x")
        bag = DiagnosticBag()
        bag.register([info])
        assert bag.registered == {"tag/bad-prefix": info}
        found = bag.add("tag/bad-prefix", "m")
        assert found is not None and found.severity is Severity.WARNING

    def test_an_override_and_strict_apply_to_a_registered_check(self) -> None:
        info = CheckInfo("tag/bad-prefix", Severity.WARNING, "x")
        overridden = DiagnosticBag(SeverityPolicy.from_strings(["tag/bad-prefix=info"]))
        overridden.register([info])
        found = overridden.add("tag/bad-prefix", "m")
        assert found is not None and found.severity is Severity.INFO
        strict = DiagnosticBag(SeverityPolicy.from_strings([], strict=True))
        strict.register([info])
        found = strict.add("tag/bad-prefix", "m")
        assert found is not None and found.severity is Severity.ERROR

    def test_ignoring_a_registered_check_drops_the_finding(self) -> None:
        bag = DiagnosticBag(SeverityPolicy.from_strings(["tag/bad-prefix=ignore"]))
        bag.register([CheckInfo("tag/bad-prefix", Severity.WARNING, "x")])
        assert bag.add("tag/bad-prefix", "m") is None


BARE_PLUGIN = 'from ddd.plugins import Plugin\n\nPLUGIN = Plugin(name="bare")\n'


def tagged(base: Path, *declarations: dict, settings: dict | None = None, **project_keys):
    """A project naming the tag plugin, with one component; returns the loaded workspace."""
    write_plugin(base / "tools")
    extensions = {} if settings is None else {"extensions": {"tag": settings}}
    files = {
        "project.ddd.json": project(
            "P", "a.ddd.json", plugins=["tools/tag_plugin.py"], **extensions, **project_keys
        ),
        "a.ddd.json": component("A", *declarations),
    }
    write_tree(base, files)
    bag = DiagnosticBag(SeverityPolicy.from_strings(["missing-id=ignore"]))
    return load_workspace(base / "project.ddd.json", bag), bag


class TestLoadingAProject:
    def test_a_project_loads_the_plugins_it_names(self, tree: Path) -> None:
        workspace, bag = tagged(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}))
        assert workspace is not None, messages(bag)
        assert [plugin.name for plugin in workspace.plugins] == ["tag"]
        assert set(bag.registered) == {"tag/bad-prefix", "tag/retagged"}
        assert checks(bag) == []

    def test_a_plugin_that_cannot_be_found_stops_the_run(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["nowhere.py"]),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["plugin-not-found"]
        assert "project.ddd.json#project.plugins[0]" in messages(bag)
        assert not CHECKS["plugin-not-found"].overridable

    def test_a_plugin_that_is_broken_stops_the_run(self, tree: Path) -> None:
        write_plugin(tree, "broken.py", "raise RuntimeError('boom')\n")
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["broken.py"]),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["plugin-invalid"]
        assert "boom" in messages(bag)
        assert not CHECKS["plugin-invalid"].overridable

    def test_two_plugins_claiming_one_name_is_refused_on_the_second(self, tree: Path) -> None:
        write_plugin(tree, "one.py")
        write_plugin(tree, "two.py")
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["one.py", "two.py"]),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["plugin-invalid"]
        assert "plugin 'tag' is already provided by 'one.py'" in messages(bag)
        assert "project.plugins[0]: first named here" in messages(bag)
        assert workspace is not None and len(workspace.plugins) == 1

    def test_the_same_plugin_named_by_two_projects_loads_once(self, tree: Path) -> None:
        write_plugin(tree / "tools")
        write_tree(
            tree,
            {
                "project.ddd.json": project(
                    "P", "sub/sub.ddd.json", "a.ddd.json", plugins=["tools/tag_plugin.py"]
                ),
                "sub/sub.ddd.json": project("S", plugins=["../tools/tag_plugin.py"]),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == []
        assert workspace is not None and len(workspace.plugins) == 1

    def test_a_block_is_validated_against_the_plugin_model(self, tree: Path) -> None:
        _, bag = tagged(tree, declare("local", "X", extensions={"tag": {"tag": 3}}))
        assert checks(bag) == ["schema"]
        assert "a.ddd.json#component.interface[0].definition.extensions.tag.tag" in messages(bag)

    def test_a_typo_inside_a_block_is_caught(self, tree: Path) -> None:
        _, bag = tagged(tree, declare("local", "X", extensions={"tag": {"tag": "t", "tg": 1}}))
        assert checks(bag) == ["schema"]
        assert "definition.extensions.tag.tg" in messages(bag)

    def test_a_block_naming_no_loaded_plugin_is_unknown(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", extensions={"nvm": {}})),
            },
        )
        assert checks(bag) == ["unknown-extension"]
        assert "'nvm' names no plugin this project loads" in messages(bag)
        assert CHECKS["unknown-extension"].needs_every_component

    def test_an_unknown_block_can_be_relaxed(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", extensions={"nvm": {}})),
            },
            severities=["unknown-extension=ignore"],
        )
        assert dictionary is not None and checks(bag) == []

    def test_the_settings_are_validated(self, tree: Path) -> None:
        _, bag = tagged(tree, declare("local", "X"), settings={"prefix": 3})
        assert checks(bag) == ["schema"]
        assert "project.ddd.json#project.extensions.tag.prefix" in messages(bag)

    def test_settings_a_plugin_requires_are_missed_where_they_belong(self, tree: Path) -> None:
        source = TAG_PLUGIN.replace('prefix: str = ""', "prefix: str")
        write_plugin(tree / "tools", source=source)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert "project.ddd.json#project.extensions.tag.prefix" in messages(bag)
        assert "required" in messages(bag).lower()

    def test_settings_stated_twice_are_refused_on_the_second(self, tree: Path) -> None:
        write_plugin(tree / "tools")
        write_tree(
            tree,
            {
                "project.ddd.json": project(
                    "P",
                    "sub/sub.ddd.json",
                    "a.ddd.json",
                    plugins=["tools/tag_plugin.py"],
                    extensions={"tag": {"prefix": "a"}},
                ),
                "sub/sub.ddd.json": project("S", extensions={"tag": {"prefix": "b"}}),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert (
            "sub.ddd.json#project.extensions.tag: error[schema]: the settings of plugin 'tag' "
            "are already stated"
        ) in messages(bag)
        assert "project.ddd.json#project.extensions.tag: first stated here" in messages(bag)

    def test_a_plugin_without_a_project_model_takes_no_settings(self, tree: Path) -> None:
        write_plugin(tree, "bare.py", BARE_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project(
                    "P", "a.ddd.json", plugins=["bare.py"], extensions={"bare": {}}
                ),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert "plugin 'bare' takes no 'extensions' block on the project" in messages(bag)

    def test_a_plugin_without_an_object_model_takes_no_block(self, tree: Path) -> None:
        write_plugin(tree, "bare.py", BARE_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["bare.py"]),
                "a.ddd.json": component("A", declare("local", "X", extensions={"bare": {}})),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert "plugin 'bare' takes no 'extensions' block on a definition" in messages(bag)

    def test_a_block_on_a_consumer_is_still_validated(self, tree: Path) -> None:
        """Whose claim it is comes later, in the analysis; a typo is a typo either way."""
        _, bag = tagged(tree, declare("input", "X", extensions={"tag": {"tag": 3}}))
        assert checks(bag) == ["schema"]


class TestLocating:
    def test_the_producing_declaration_is_where_a_finding_belongs(self, tree: Path) -> None:
        workspace, _ = tagged(tree, declare("input", "X"), declare("local", "Y"))
        assert workspace is not None
        assert workspace.locate("Y") == Location(tree / "a.ddd.json", "component.interface[1]")

    def test_a_consumer_is_the_fallback(self, tree: Path) -> None:
        workspace, _ = tagged(tree, declare("input", "X"))
        assert workspace is not None
        assert workspace.locate("X") == Location(tree / "a.ddd.json", "component.interface[0]")

    def test_an_unknown_name_has_no_place(self, tree: Path) -> None:
        workspace, _ = tagged(tree, declare("local", "X"))
        assert workspace is not None
        assert workspace.locate("Nope") is None


def analysed(base: Path, *declarations: dict, settings: dict | None = None, **project_keys):
    """The dictionary of a project naming the tag plugin, and the bag it was analysed into."""
    workspace, bag = tagged(base, *declarations, settings=settings, **project_keys)
    assert workspace is not None and not bag.has_errors, messages(bag)
    return analyze(workspace, bag), bag


class TestTheDictionary:
    def test_a_block_reaches_the_object_in_resolved_form(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}))
        assert dictionary.by_name["X"].extensions == {"tag": {"tag": "t"}}
        assert dictionary.by_name["X"].model_dump()["extensions"] == {"tag": {"tag": "t"}}

    def test_the_settings_reach_the_dictionary_with_defaults_filled_in(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X"), settings={})
        assert dictionary.extensions == {"tag": {"prefix": ""}}
        assert dictionary.plugins == ("tag",)

    def test_a_project_stating_no_settings_still_records_them(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X"))
        assert dictionary.extensions == {"tag": {"prefix": ""}}

    def test_the_extensions_are_sorted_by_plugin_name(self, tree: Path) -> None:
        # Two plugins under different names, named in an order that would not itself sort
        # them, and settings stated for only one - so a dictionary that merely appended the
        # stated settings after the resolved blocks would still come out sorted by luck.
        write_plugin(
            tree / "tools",
            "beta_plugin.py",
            TAG_PLUGIN.replace('name="tag"', 'name="beta"').replace("tag/", "beta/"),
        )
        write_plugin(
            tree / "tools",
            "alpha_plugin.py",
            TAG_PLUGIN.replace('name="tag"', 'name="alpha"').replace("tag/", "alpha/"),
        )
        write_tree(
            tree,
            {
                "project.ddd.json": project(
                    "P",
                    "a.ddd.json",
                    plugins=["tools/beta_plugin.py", "tools/alpha_plugin.py"],
                    extensions={"beta": {"prefix": "p"}},
                ),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        bag = DiagnosticBag(SeverityPolicy.from_strings(["missing-id=ignore"]))
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None and not bag.has_errors, messages(bag)
        dictionary = analyze(workspace, bag)
        assert list(dictionary.extensions) == ["alpha", "beta"]
        assert dictionary.plugins == ("alpha", "beta")

    def test_an_unknown_block_that_was_relaxed_is_carried_as_written(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", extensions={"nvm": {"id": 1}})),
            },
            severities=["unknown-extension=ignore"],
        )
        assert dictionary is not None, messages(bag)
        assert dictionary.by_name["X"].extensions == {"nvm": {"id": 1}}
        assert dictionary.plugins == ()

    def test_an_instance_carries_the_block_and_its_leaves_do_not(self, tree: Path) -> None:
        write_plugin(tree / "tools")
        write_tree(
            tree,
            {
                "project.ddd.json": project(
                    "P", "t.ddd.json", "a.ddd.json", plugins=["tools/tag_plugin.py"]
                ),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Pair_t",
                            "members": [
                                {
                                    "name": "a",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {"kind": "identity"},
                                },
                            ],
                        }
                    ]
                },
                "a.ddd.json": component(
                    "A",
                    declare("local", "P", typename="Pair_t", extensions={"tag": {"tag": "s"}}),
                ),
            },
        )
        bag = DiagnosticBag(SeverityPolicy.from_strings(["missing-id=ignore"]))
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None and not bag.has_errors, messages(bag)
        dictionary = analyze(workspace, bag)
        assert dictionary.instances[0].extensions == {"tag": {"tag": "s"}}
        assert not hasattr(dictionary.leaves[0], "extensions")

    def test_the_format_is_seven(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X"))
        assert DICTIONARY_FORMAT == 7
        assert dictionary.format == 7

    def test_an_older_dump_reads_back_with_empty_blocks(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X"))
        archived = json.loads(dictionary.model_dump_json())
        archived["format"] = 6
        del archived["plugins"]
        del archived["extensions"]
        for entry in archived["objects"]:
            del entry["extensions"]
        (tree / "old.json").write_text(json.dumps(archived), encoding="utf-8")
        bag = DiagnosticBag()
        old = load_dictionary(tree / "old.json", bag)
        assert old is not None, messages(bag)
        assert old.plugins == () and old.extensions == {}
        assert old.by_name["X"].extensions == {}

    def test_the_dictionary_round_trips(self, tree: Path) -> None:
        dictionary, _ = analysed(
            tree, declare("local", "X", extensions={"tag": {"tag": "t"}}), settings={"prefix": "p"}
        )
        again = DataDictionary.model_validate_json(dictionary.model_dump_json())
        assert again == dictionary


class TestConsumerExtension:
    def test_a_consumer_stating_a_block_is_refused_where_it_is_written(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X", extensions={"nvm": {}})),
            },
            severities=["unknown-extension=ignore"],
        )
        assert checks(bag) == ["consumer-extension"]
        assert "b.ddd.json#component.interface[0].definition.extensions" in messages(bag)
        assert "decided by the component that produces the variable" in messages(bag)

    def test_a_local_declaration_is_a_producer(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", extensions={"nvm": {}})),
            },
            severities=["unknown-extension=ignore"],
        )
        assert checks(bag) == []


class TestTheTemplates:
    def test_a_block_reaches_the_c_templates(self, tree: Path) -> None:
        from ddd.backends import CBackend, render

        dictionary, _ = analysed(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}))
        templates = tree / "templates"
        templates.mkdir()
        (templates / "blocks.txt.jinja2").write_text(
            "{% for group in model.groups %}{% for v in group.variables %}"
            "{{ v.name }}={{ v.extensions.tag.tag }}\n{% endfor %}{% endfor %}",
            encoding="utf-8",
        )
        (file,) = render(dictionary, [CBackend(templates)], tree / "out")
        assert file.content == "X=t\n"


def definitions_with_extensions(schema: dict) -> list[dict]:
    return [
        node
        for node in (schema, *schema.get("$defs", {}).values())
        if "extensions" in node.get("properties", {})
    ]


class TestSchemaWithPlugins:
    def test_without_plugins_the_block_is_open(self) -> None:
        schema = json.loads(schema_text("component"))
        nodes = definitions_with_extensions(schema)
        assert nodes, "no definition publishes extensions"
        for node in nodes:
            assert node["properties"]["extensions"].get("additionalProperties") is not False

    def test_a_plugin_closes_the_block_over_its_model(self, tmp_path: Path) -> None:
        plugin = load_plugin(str(write_plugin(tmp_path)), tmp_path)
        schema = json.loads(schema_text("component", (plugin,)))
        for node in definitions_with_extensions(schema):
            extensions = node["properties"]["extensions"]
            assert extensions["additionalProperties"] is False
            assert extensions["properties"]["tag"]["properties"]["tag"]["type"] == "string"
            assert extensions["properties"]["tag"]["additionalProperties"] is False

    def test_the_project_schema_takes_the_project_model(self, tmp_path: Path) -> None:
        plugin = load_plugin(str(write_plugin(tmp_path)), tmp_path)
        schema = json.loads(schema_text("project", (plugin,)))
        (node,) = definitions_with_extensions(schema)
        assert "prefix" in node["properties"]["extensions"]["properties"]["tag"]["properties"]

    def test_a_plugin_without_the_model_is_left_out(self) -> None:
        plugin = Plugin(name="bare")
        schema = json.loads(schema_text("component", (plugin,)))
        for node in definitions_with_extensions(schema):
            assert node["properties"]["extensions"]["properties"] == {}
            assert node["properties"]["extensions"]["additionalProperties"] is False

    def test_a_nested_model_is_hoisted_under_the_plugin_name(self) -> None:
        class Inner(BaseModel):
            x: int

        class Outer(BaseModel):
            inner: Inner

        schema = json.loads(schema_text("component", (Plugin(name="nest", object_model=Outer),)))
        assert "nest.Inner" in schema["$defs"]
        node = definitions_with_extensions(schema)[0]
        reference = node["properties"]["extensions"]["properties"]["nest"]["properties"]["inner"]
        assert reference["$ref"] == "#/$defs/nest.Inner"

    def test_a_plugin_model_may_have_a_field_named_extensions(self) -> None:
        class Nested(BaseModel):
            extensions: dict[str, str] = {}

        class Outer(BaseModel):
            inner: Nested

        plugin = Plugin(name="weird", object_model=Outer)
        schema = json.loads(schema_text("component", (plugin,)))
        nested = schema["$defs"]["weird.Nested"]["properties"]["extensions"]
        assert nested["type"] == "object"
        assert "properties" not in nested
        closed = schema["$defs"]["Parameter"]["properties"]["extensions"]
        assert closed["additionalProperties"] is False
        assert "weird" in closed["properties"]

    def test_the_dictionary_schema_stays_open(self, tmp_path: Path) -> None:
        plugin = load_plugin(str(write_plugin(tmp_path)), tmp_path)
        assert schema_text("dictionary", (plugin,)) == schema_text("dictionary")

    def test_an_editor_validates_a_block_against_the_published_schema(self, tmp_path: Path) -> None:
        plugin = load_plugin(str(write_plugin(tmp_path)), tmp_path)
        schema = json.loads(schema_text("component", (plugin,)))
        good = component("A", declare("local", "X", extensions={"tag": {"tag": "t"}}))
        jsonschema.validate(good, schema)
        typo = component("A", declare("local", "X", extensions={"tag": {"tg": "t"}}))
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(typo, schema)
        unknown = component("A", declare("local", "X", extensions={"nvm": {}}))
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(unknown, schema)


class TestSchemaCommand:
    def test_the_option_names_a_plugin_relative_to_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tmp_path / "tools")
        monkeypatch.chdir(tmp_path)
        assert main(["schema", "component", "--plugin", "tools/tag_plugin.py"]) == EXIT_OK
        schema = json.loads(capsys.readouterr().out)
        assert definitions_with_extensions(schema)[0]["properties"]["extensions"]["properties"][
            "tag"
        ]

    def test_all_writes_every_schema_with_the_plugins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_plugin(tmp_path / "tools")
        monkeypatch.chdir(tmp_path)
        arguments = ["schema", "all", "-o", "schemas", "--plugin", "tools/tag_plugin.py"]
        assert main(arguments) == EXIT_OK
        written = json.loads((tmp_path / "schemas" / "ddd_project.schema.json").read_text())
        (node,) = definitions_with_extensions(written)
        assert "tag" in node["properties"]["extensions"]["properties"]

    def test_a_plugin_that_cannot_be_loaded_is_a_usage_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert main(["schema", "component", "--plugin", "nowhere.py"]) == EXIT_USAGE
        assert "does not exist" in capsys.readouterr().err
        write_plugin(tmp_path, "broken.py", "raise RuntimeError('boom')\n")
        assert main(["schema", "component", "--plugin", "broken.py"]) == EXIT_USAGE
        assert "boom" in capsys.readouterr().err

    def test_the_same_plugin_twice_is_loaded_once_and_two_with_one_name_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tmp_path, "one.py")
        write_plugin(tmp_path, "two.py")
        monkeypatch.chdir(tmp_path)
        twice = ["schema", "project", "--plugin", "one.py", "--plugin", "./one.py"]
        assert main(twice) == EXIT_OK
        clash = ["schema", "project", "--plugin", "one.py", "--plugin", "two.py"]
        assert main(clash) == EXIT_USAGE
        assert "plugin 'tag' is named twice" in capsys.readouterr().err


class TestPluginsFromArguments:
    """The loading helper other commands - not yet wired to a bag in this task - will reuse."""

    def test_the_bag_learns_the_plugins_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_plugin(tmp_path)
        monkeypatch.chdir(tmp_path)
        bag = DiagnosticBag()
        (plugin,) = _plugins_from_arguments(["tag_plugin.py"], bag)
        assert set(bag.registered) == {info.identifier for info in plugin.checks}


RAISING_PLUGIN = TAG_PLUGIN.replace(
    "def check(context: CheckContext) -> None:\n",
    'def check(context: CheckContext) -> None:\n    raise RuntimeError("boom")\n',
)


class TestTheCheckHook:
    def test_a_hook_reports_through_the_bag_at_the_producing_declaration(self, tree: Path) -> None:
        _, bag = analysed(
            tree, declare("local", "X", extensions={"tag": {"tag": "zz"}}), settings={"prefix": "p"}
        )
        assert checks(bag) == ["tag/bad-prefix"]
        assert "a.ddd.json#component.interface[0]: warning[tag/bad-prefix]" in messages(bag)

    def test_the_hook_sees_the_defaults_of_its_settings(self, tree: Path) -> None:
        _, bag = analysed(tree, declare("local", "X", extensions={"tag": {"tag": "zz"}}))
        assert checks(bag) == []

    def test_the_policy_applies_to_a_hook_finding(self, tree: Path) -> None:
        tagged(
            tree, declare("local", "X", extensions={"tag": {"tag": "zz"}}), settings={"prefix": "p"}
        )
        root = str(tree / "project.ddd.json")
        quiet = ["-W", "missing-id=ignore"]
        assert main(["check", root, *quiet]) == EXIT_OK
        assert main(["check", root, *quiet, "--strict"]) == EXIT_FINDINGS
        assert main(["check", root, *quiet, "-W", "tag/bad-prefix=error"]) == EXIT_FINDINGS
        assert main(["check", root, *quiet, "-W", "tag/bad-prefix=ignore", "--strict"]) == EXIT_OK

    def test_an_override_no_plugin_registered_is_a_usage_error(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tagged(tree, declare("local", "X"))
        root = str(tree / "project.ddd.json")
        assert main(["check", root, "-W", "tag/no-such=error"]) == EXIT_USAGE
        assert (
            "unknown check 'tag/no-such': no loaded plugin registers it" in capsys.readouterr().err
        )

    def test_a_hook_that_raises_is_a_usage_error_naming_the_plugin(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tree / "tools", source=RAISING_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert main(["check", str(tree / "project.ddd.json")]) == EXIT_USAGE
        assert "plugin 'tag' failed in its check hook: boom" in capsys.readouterr().err

    def test_the_language_server_runs_the_hook_too(self, tree: Path) -> None:
        tagged(
            tree, declare("local", "X", extensions={"tag": {"tag": "zz"}}), settings={"prefix": "p"}
        )
        bag, _ = analyse_standalone(tree / "project.ddd.json")
        assert "tag/bad-prefix" in checks(bag)

    def test_the_language_server_survives_a_hook_that_raises(self, tree: Path) -> None:
        write_plugin(tree / "tools", source=RAISING_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        bag, _ = analyse_standalone(tree / "project.ddd.json")
        assert "plugin-invalid" in checks(bag)
        assert "failed in its check hook: boom" in messages(bag)

    def test_a_plugin_without_a_hook_is_nothing(self, tree: Path) -> None:
        write_plugin(tree, "bare.py", BARE_PLUGIN)
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["bare.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert checks(bag) == []


class TestSettings:
    def test_a_plugin_without_a_project_model_has_none(self) -> None:
        assert settings_of(Plugin(name="bare"), {"bare": {"x": 1}}) is None

    def test_invalid_settings_are_the_plugins_error(self, tmp_path: Path) -> None:
        source = TAG_PLUGIN.replace('prefix: str = ""', "prefix: str")
        plugin = load_plugin(str(write_plugin(tmp_path, "strict_tag.py", source)), tmp_path)
        with pytest.raises(PluginError, match="settings of plugin 'tag' are invalid"):
            settings_of(plugin, {})


def two_deliveries(base: Path, old_tag: str, new_tag: str) -> tuple[str, str]:
    """Two projects naming the tag plugin, whose one object is tagged differently."""
    write_plugin(base / "tools")
    for name, tag in (("old", old_tag), ("new", new_tag)):
        write_tree(
            base,
            {
                f"{name}.ddd.json": project(
                    "P", f"{name}-a.ddd.json", plugins=["tools/tag_plugin.py"]
                ),
                f"{name}-a.ddd.json": component(
                    "A", declare("local", "X", extensions={"tag": {"tag": tag}})
                ),
            },
        )
    return str(base / "old.ddd.json"), str(base / "new.ddd.json")


def dumped(root: str, base: Path, name: str, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["dump", root, "-W", "missing-id=ignore"]) == EXIT_OK
    path = base / name
    path.write_text(capsys.readouterr().out, encoding="utf-8")
    return str(path)


class TestTheCompareHook:
    def test_a_candidate_project_runs_its_own_plugins(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        assert main(["compare", old, new, "-W", "missing-id=ignore"]) == EXIT_FINDINGS
        assert "error[tag/retagged]: 'X' was retagged" in capsys.readouterr().err

    def test_check_with_a_baseline_runs_them_too(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        arguments = ["check", new, "--baseline", old, "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_FINDINGS
        assert "tag/retagged" in capsys.readouterr().err

    def test_an_unchanged_tag_is_no_finding(self, tree: Path) -> None:
        old, new = two_deliveries(tree, "a", "a")
        assert main(["compare", old, new, "-W", "missing-id=ignore"]) == EXIT_OK

    def test_two_dumps_without_the_plugin_say_so(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        old_dump, new_dump = (
            dumped(old, tree, "old.json", capsys),
            dumped(new, tree, "new.json", capsys),
        )
        assert main(["compare", old_dump, new_dump]) == EXIT_OK
        captured = capsys.readouterr().err
        assert "warning[missing-plugin]: the baseline was produced with plugin 'tag'" in captured
        assert "warning[missing-plugin]: the candidate was produced with plugin 'tag'" in captured
        assert "its comparison rules did not run" in captured
        assert "tag/retagged" not in captured

    def test_the_option_loads_the_plugin_for_two_dumps(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        old_dump, new_dump = (
            dumped(old, tree, "old.json", capsys),
            dumped(new, tree, "new.json", capsys),
        )
        monkeypatch.chdir(tree)
        arguments = ["compare", old_dump, new_dump, "--plugin", "tools/tag_plugin.py"]
        assert main(arguments) == EXIT_FINDINGS
        captured = capsys.readouterr().err
        assert "missing-plugin" not in captured
        assert "error[tag/retagged]: 'X' was retagged" in captured

    def test_the_option_is_refused_beside_a_project_candidate(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        monkeypatch.chdir(tree)
        arguments = [
            "compare",
            old,
            new,
            "--plugin",
            "tools/tag_plugin.py",
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_USAGE
        assert "a project description names its own" in capsys.readouterr().err

    def test_a_provisional_override_is_verified_against_the_loaded_plugins(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        old_dump, new_dump = (
            dumped(old, tree, "old.json", capsys),
            dumped(new, tree, "new.json", capsys),
        )
        monkeypatch.chdir(tree)
        relaxed = [
            "compare",
            old_dump,
            new_dump,
            "--plugin",
            "tools/tag_plugin.py",
            "-W",
            "tag/retagged=warning",
        ]
        assert main(relaxed) == EXIT_OK
        assert main(["compare", old_dump, new_dump, "-W", "tag/retagged=warning"]) == EXIT_USAGE
        assert "no loaded plugin registers it" in capsys.readouterr().err

    def test_a_dump_without_the_settings_a_plugin_requires_is_the_plugins_error(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = two_deliveries(tree, "a", "b")
        old_dump, new_dump = (
            dumped(old, tree, "old.json", capsys),
            dumped(new, tree, "new.json", capsys),
        )
        # A dump made with plain TAG_PLUGIN always carries 'prefix' with its default filled
        # in, so relaxing 'prefix' back to required would still find it stated. What the dump
        # never carries is a setting the plugin only started requiring afterwards.
        source = TAG_PLUGIN.replace('prefix: str = ""', 'prefix: str = ""\n    added: str')
        write_plugin(tree / "tools", "strict_tag.py", source)
        monkeypatch.chdir(tree)
        arguments = ["compare", old_dump, new_dump, "--plugin", "tools/strict_tag.py"]
        assert main(arguments) == EXIT_USAGE
        assert "settings of plugin 'tag' are invalid" in capsys.readouterr().err

    def test_a_plugin_without_a_compare_hook_is_nothing(self, tree: Path) -> None:
        from ddd.plugins import run_compare_hooks

        # analysed() always loads the tag plugin, so it must be among the loaded plugins here
        # too - otherwise 'missing-plugin' fires and this stops testing what it says it tests.
        dictionary, bag = analysed(tree, declare("local", "X"))
        plugins = (Plugin(name="bare"), Plugin(name="tag"))
        run_compare_hooks(plugins, dictionary, dictionary, bag, lambda _: None, None)
        assert checks(bag) == []


_GENERATE_SIGNATURE = (
    "    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:\n"
)
RAISING_GENERATE_PLUGIN = TAG_PLUGIN.replace(
    _GENERATE_SIGNATURE, f'{_GENERATE_SIGNATURE}        raise KeyError("nope")\n'
)


class TestGenerate:
    def project_with_tags(self, tree: Path) -> str:
        tagged(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}), declare("local", "Y"))
        return str(tree / "project.ddd.json")

    def test_a_plugin_artefact_is_generated_by_name(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = self.project_with_tags(tree)
        out = tree / "out"
        assert main(["generate", "tag", root, "-o", str(out), "-W", "missing-id=ignore"]) == EXIT_OK
        assert (out / "tags.txt").read_text(encoding="utf-8") == "X t\n"
        assert "wrote" in capsys.readouterr().err

    def test_a_backends_generate_that_raises_is_a_usage_error_naming_the_plugin(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tree / "tools", source=RAISING_GENERATE_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component(
                    "A", declare("local", "X", extensions={"tag": {"tag": "t"}})
                ),
            },
        )
        root = str(tree / "project.ddd.json")
        out = tree / "out"
        arguments = ["generate", "tag", root, "-o", str(out), "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_USAGE
        assert "plugin 'tag' failed in its generate hook" in capsys.readouterr().err

    def test_dry_run_writes_nothing(self, tree: Path) -> None:
        root = self.project_with_tags(tree)
        out = tree / "out"
        arguments = [
            "generate",
            "tag",
            root,
            "-o",
            str(out),
            "--dry-run",
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_OK
        assert not (out / "tags.txt").exists()

    def test_a_name_no_plugin_provides_is_a_usage_error(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = self.project_with_tags(tree)
        arguments = ["generate", "nvm", root, "-o", str(tree / "out"), "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_USAGE
        # _listed() quotes every name it lists (see its docstring), so the single artefact it
        # names here, 'tag', comes back quoted too - matching every other _listed() message.
        assert (
            "'nvm' is not an artefact of this project; it provides: 'tag'"
            in capsys.readouterr().err
        )

    def test_a_plugin_without_a_backend_provides_no_artefact(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tree, "bare.py", BARE_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["bare.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        root = str(tree / "project.ddd.json")
        arguments = ["generate", "bare", root, "-o", str(tree / "out"), "-W", "missing-id=ignore"]
        assert main(arguments) == EXIT_USAGE
        assert "plugin 'bare' provides no artefact" in capsys.readouterr().err

    def test_a_project_with_errors_generates_nothing(self, tree: Path) -> None:
        tagged(tree, declare("input", "X"))
        root = str(tree / "project.ddd.json")
        arguments = ["generate", "tag", root, "-o", str(tree / "out")]
        assert main(arguments) == EXIT_FINDINGS

    def test_the_built_in_pair_does_not_run_plugin_backends(self, tree: Path) -> None:
        root = self.project_with_tags(tree)
        out = tree / "out"
        arguments = [
            "generate",
            "all",
            root,
            "-o",
            str(out),
            "-t",
            str(TEMPLATES),
            "-W",
            "missing-id=ignore",
        ]
        assert main(arguments) == EXIT_OK
        assert not (out / "tags.txt").exists()

    def test_a_path_collision_with_the_c_backend_is_refused(self, tree: Path) -> None:
        dictionary, _ = analysed(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}))
        templates = tree / "templates"
        templates.mkdir()
        (templates / "tags.txt.jinja2").write_text("x\n", encoding="utf-8")
        plugin = load_plugin("tools/tag_plugin.py", tree)
        backends = [CBackend(templates), backend_of(plugin, dictionary, "ddd test")]
        with pytest.raises(
            ValueError, match=re.escape("the tag and c backends would both write 'tags.txt'")
        ):
            render(dictionary, backends, tree / "out")

    @pytest.mark.parametrize(
        ("arguments", "expected"),
        [
            (["generate", "tag", "p.ddd.json"], "tag"),
            (["generate", "c", "p.ddd.json"], None),
            (["generate", "all"], None),
            (["generate"], None),
            (["generate", "--help"], None),
            (["generate", "Not-A-Name", "p.ddd.json"], None),
            (["check", "tag"], None),
        ],
    )
    def test_the_artefact_is_read_off_the_raw_arguments(
        self, arguments: list[str], expected: str | None
    ) -> None:
        assert _plugin_artefact(arguments) == expected


class TestChecksCommand:
    def test_the_plugins_checks_are_listed_after_the_built_in_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_plugin(tmp_path / "tools")
        monkeypatch.chdir(tmp_path)
        assert main(["checks"]) == EXIT_OK
        assert "tag/bad-prefix" not in capsys.readouterr().out
        assert main(["checks", "--plugin", "tools/tag_plugin.py"]) == EXIT_OK
        out = capsys.readouterr().out
        assert out.index("added-object") < out.index("tag/bad-prefix")
        # The column width is the longest identifier of the merged listing - a built-in one,
        # here - so the gap after a shorter plugin identifier is wider than two spaces; the
        # whitespace is matched loosely rather than pinned to that incidental width.
        assert re.search(r"tag/bad-prefix\s+warning\s+a tag is outside the project's prefix", out)
        assert main(["checks", "--plugin", "tools/tag_plugin.py", "--format", "json"]) == EXIT_OK
        listed = json.loads(capsys.readouterr().out)
        assert listed[-1]["check"] == "tag/retagged"


class TestTheLanguageServerAndPlugins:
    def test_hover_resolution_survives_a_hook_that_raises(self, tree: Path) -> None:
        from ddd.lsp.hover import resolve

        write_plugin(tree / "tools", source=RAISING_PLUGIN)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        workspace = load_workspace(tree / "project.ddd.json", DiagnosticBag())
        assert workspace is not None
        assert resolve([workspace]) is None

    def test_hover_resolution_survives_settings_that_do_not_validate(self, tree: Path) -> None:
        """A hover resolves a project that did not read cleanly; its settings may be wrong."""
        from ddd.lsp.hover import resolve

        workspace, bag = tagged(tree, declare("local", "X"), settings={"prefix": 3})
        assert workspace is not None and bag.has_errors
        assert resolve([workspace]) is None

    def test_a_plugin_printing_during_a_request_does_not_reach_the_wire(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """stdout is the json-rpc wire; whatever a plugin prints has to go somewhere else."""
        import io
        from types import SimpleNamespace

        from ddd.lsp.protocol import write_message
        from ddd.lsp.server import serve

        source = TAG_PLUGIN.replace(
            "def check(context: CheckContext) -> None:\n",
            "def check(context: CheckContext) -> None:\n"
            '    print("progress: 100%\\n\\ndone", flush=True)\n',
        )
        write_plugin(tree / "tools", source=source)
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/tag_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        requests = io.BytesIO()
        for message in (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tree.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": (tree / "project.ddd.json").as_uri(),
                        "languageId": "json",
                        "version": 1,
                        "text": "",
                    }
                },
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        ):
            write_message(requests, message)
        requests.seek(0)
        wire = io.BytesIO()
        fake_stdout = io.TextIOWrapper(wire, encoding="utf-8", write_through=True)
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=requests))
        monkeypatch.setattr(sys, "stdout", fake_stdout)
        assert serve() == 0
        written = wire.getvalue()
        assert b"progress" not in written
        assert b'"id": 2' in written
        assert "progress" in capsys.readouterr().err


class TestPluginFilesWithSimilarNames:
    def test_two_files_whose_paths_differ_only_in_punctuation_are_two_plugins(
        self, tmp_path: Path
    ) -> None:
        write_plugin(
            tmp_path, "my-plugin.py", BARE_PLUGIN.replace('name="bare"', 'name="plugin_a"')
        )
        write_plugin(
            tmp_path, "my_plugin.py", BARE_PLUGIN.replace('name="bare"', 'name="plugin_b"')
        )
        assert load_plugin("my-plugin.py", tmp_path).name == "plugin_a"
        assert load_plugin("my_plugin.py", tmp_path).name == "plugin_b"


class TestHashingTheResolvedForms:
    def test_the_dictionary_and_its_objects_hash_despite_the_blocks(self, tree: Path) -> None:
        workspace, bag = tagged(tree, declare("local", "X", extensions={"tag": {"tag": "t"}}))
        assert workspace is not None and not bag.has_errors, messages(bag)
        dictionary = analyze(workspace, bag)
        assert len({*dictionary.objects}) == 1
        assert isinstance(hash(dictionary), int)
        assert isinstance(hash(workspace), int)

    def test_a_structured_variable_hashes_too(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Pair_t",
                            "members": [
                                {
                                    "name": "a",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {"kind": "identity"},
                                }
                            ],
                        }
                    ]
                },
                "a.ddd.json": component("A", declare("local", "P", typename="Pair_t")),
            },
        )
        assert dictionary is not None, messages(bag)
        assert len({*dictionary.instances}) == 1
