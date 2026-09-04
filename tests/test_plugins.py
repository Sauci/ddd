"""Tests of the plugin mechanism: the object, loading, the keys, the blocks and the hooks.

The example plugin under ``examples/plugins`` is tested separately; what is tested here is
the api it is written against, with a plugin small enough to live in this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.diagnostics import (
    CHECKS,
    CheckInfo,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.loading import load_workspace
from ddd.models import ComponentFile, ProjectFile
from ddd.plugins import Plugin, PluginInvalidError, PluginNotFoundError, load_plugin

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
