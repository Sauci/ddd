"""Tests of the plugin mechanism: the object, loading, the keys, the blocks and the hooks.

The example plugin under ``examples/plugins`` is tested separately; what is tested here is
the api it is written against, with a plugin small enough to live in this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import Plugin, PluginInvalid, PluginNotFound, load_plugin

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
        with pytest.raises(PluginNotFound, match="does not exist"):
            load_plugin("nowhere.py", tmp_path)

    def test_a_missing_module_is_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(PluginNotFound, match="not an importable module"):
            load_plugin("ddd_no_such_plugin_module", tmp_path)

    def test_a_file_that_raises_on_import_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "broken.py", "raise RuntimeError('boom')\n")
        with pytest.raises(PluginInvalid, match="failed to import: boom"):
            load_plugin("broken.py", tmp_path)

    def test_a_module_whose_own_import_is_missing_is_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The module exists; something it needs does not. That is not 'not found'."""
        write_plugin(tmp_path, "needs_dep.py", "import ddd_no_such_dependency\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            with pytest.raises(PluginInvalid, match="failed to import"):
                load_plugin("needs_dep", tmp_path)
        finally:
            sys.modules.pop("needs_dep", None)

    def test_a_module_that_raises_on_import_is_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_plugin(tmp_path, "raises_on_import.py", "raise RuntimeError('boom')\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            with pytest.raises(PluginInvalid, match="failed to import: boom"):
                load_plugin("raises_on_import", tmp_path)
        finally:
            sys.modules.pop("raises_on_import", None)

    def test_a_module_without_a_plugin_object_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "empty.py", "X = 1\n")
        with pytest.raises(PluginInvalid, match="exposes no PLUGIN"):
            load_plugin("empty.py", tmp_path)

    def test_a_plugin_object_of_the_wrong_type_is_invalid(self, tmp_path: Path) -> None:
        write_plugin(tmp_path, "wrong.py", "PLUGIN = object()\n")
        with pytest.raises(PluginInvalid, match="exposes no PLUGIN"):
            load_plugin("wrong.py", tmp_path)
