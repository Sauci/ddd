"""The CMake module, configured and built rather than read.

``cmake/Ddd.cmake`` is the largest piece of DDD that no unit test can reach: it is CMake code,
and everything else in this suite that touches it checks what the file says, not what it does.
So it is run here, with the ``cmake`` the development requirements install, over the shipped
example and over two small projects written into the temporary directory - one collecting its
components through the link graph and naming a plugin with ``PLUGINS``, one handing the tool a
hand-written project description that names its own plugin. What is asserted is what a build
would see: the files the generation writes, the project description the module assembles,
the schemas it closes over the plugins, and a rebuild that notices an edited plugin.

Not skipped when ``cmake`` is missing: it comes from ``requirements-dev.txt``, and a test that
skips when a tool is absent reports success without having run. The generator is ninja, from
the same requirements: the module refuses a multi-config generator, which is what cmake
defaults to on Windows, and a compiler is named explicitly where ``cl`` is not on the path,
which is a GitHub runner with MinGW's ``gcc`` and no developer prompt.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import EXAMPLES

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(sys.executable).parent
CMAKE = shutil.which("cmake", path=str(SCRIPTS)) or shutil.which("cmake") or str(SCRIPTS / "cmake")
NINJA = shutil.which("ninja", path=str(SCRIPTS)) or shutil.which("ninja") or str(SCRIPTS / "ninja")
DDD = SCRIPTS / ("ddd.exe" if os.name == "nt" else "ddd")
"""The console script of this environment, handed to the module so that it runs this tree."""


def compiler() -> list[str]:
    """``-DCMAKE_C_COMPILER=gcc`` where MSVC is not set up but MinGW is, else cmake's own pick."""
    if shutil.which("cl") is None and (gcc := shutil.which("gcc")):
        return [f"-DCMAKE_C_COMPILER={Path(gcc).as_posix()}"]
    return []


LAYOUT = EXAMPLES / "layout"
PLUGIN = EXAMPLES / "plugins" / "ddd_layout.py"
TEMPLATES = EXAMPLES / "templates"


def cmake(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """One cmake invocation, its output kept for the failure message."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}
    return subprocess.run(
        [CMAKE, *arguments], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def configure(source: Path, build: Path, *definitions: str) -> subprocess.CompletedProcess[str]:
    run = cmake(
        "-S",
        str(source),
        "-B",
        str(build),
        f"-DDDD_EXECUTABLE={DDD.as_posix()}",
        *definitions,
        cwd=source,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return run


def build(build_dir: Path, *targets: str) -> str:
    target = ["--target", *targets] if targets else []
    run = cmake("--build", str(build_dir), *target, cwd=build_dir)
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout + run.stderr


def closed_over_layout(schema_file: Path) -> bool:
    """Whether the component schema published carries the layout plugin's model."""
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    measurement = schema["$defs"]["Measurement"]["properties"]["extensions"]
    return "layout" in measurement.get("properties", {})


def edit_plugin(plugin: Path) -> None:
    """A change a build has to notice: the header the plugin writes changes its first line."""
    source = plugin.read_text(encoding="utf-8")
    phrase = "one entry per stamped object, by key"
    assert source.count(phrase) == 1, "the example plugin no longer writes that header line"
    plugin.write_text(source.replace(phrase, phrase + ", edited"), encoding="utf-8")


class TestTheShippedExample:
    def test_it_configures_builds_and_checks_each_component_alone(self, tmp_path: Path) -> None:
        """The example the build integration page shows is the example the suite builds."""
        configure(EXAMPLES / "cmake", tmp_path / "build")
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "firmware.elf"
        assert (generated / "ddd_globals.c").is_file()
        assert (generated / "DemoDevice.a2l").is_file()
        assert (generated / "DemoDevice.ddd.json").is_file(), "the collected project description"
        # The per-component target runs the standalone check, which a lone component passes.
        build(tmp_path / "build", "sensor_hub.ddd")


class TestACollectedProjectWithPlugins:
    def write(self, tmp_path: Path) -> tuple[Path, Path]:
        """A component carrying the layout plugin's blocks, collected into an image naming it."""
        component = tmp_path / "storage.ddd.json"
        shutil.copy(LAYOUT / "storage.ddd.json", component)
        plugin = tmp_path / "ddd_layout.py"
        shutil.copy(PLUGIN, plugin)
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Collected LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{component.as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME LayoutDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             SCHEMA_DIRECTORY "${{CMAKE_CURRENT_BINARY_DIR}}/schemas"
             PLUGINS "{plugin.as_posix()}")
""",
            encoding="utf-8",
        )
        return component, plugin

    def test_the_plugin_reaches_the_project_the_schemas_and_the_artefacts(
        self, tmp_path: Path
    ) -> None:
        component, plugin = self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "img"
        described = json.loads((generated / "LayoutDevice.ddd.json").read_text(encoding="utf-8"))
        assert described["project"]["plugins"] == [plugin.as_posix()]
        assert described["project"]["includes"] == [component.as_posix()]
        assert (generated / "ddd_layout.h").is_file(), "the plugin's artefact, under generate all"
        assert closed_over_layout(tmp_path / "build" / "schemas" / "ddd_component.schema.json")

    def test_an_edited_plugin_regenerates(self, tmp_path: Path) -> None:
        """The plugin file is a dependency of the generation, so its edit reaches the header."""
        _, plugin = self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        header = tmp_path / "build" / "ddd" / "img" / "ddd_layout.h"
        before = header.read_text(encoding="utf-8")
        edit_plugin(plugin)
        build(tmp_path / "build")
        after = header.read_text(encoding="utf-8")
        assert after != before and "by key, edited" in after.splitlines()[0]


class TestAHandWrittenProject:
    def write(self, tmp_path: Path) -> Path:
        """The layout example as shipped, its project naming ``../plugins/ddd_layout.py``."""
        shutil.copytree(LAYOUT, tmp_path / "layout")
        shutil.copytree(EXAMPLES / "plugins", tmp_path / "plugins")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Hand LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_executable(img main.c)
ddd_generate(img
             PROJECT "{(tmp_path / "layout" / "project.ddd.json").as_posix()}"
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             SCHEMA_DIRECTORY "${{CMAKE_CURRENT_BINARY_DIR}}/schemas")
""",
            encoding="utf-8",
        )
        return tmp_path / "plugins" / "ddd_layout.py"

    def test_the_projects_own_plugins_close_the_schemas_and_produce_their_artefact(
        self, tmp_path: Path
    ) -> None:
        self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        assert (tmp_path / "build" / "ddd" / "img" / "ddd_layout.h").is_file()
        assert closed_over_layout(tmp_path / "build" / "schemas" / "ddd_component.schema.json")

    def test_an_edited_plugin_regenerates_through_the_sources(self, tmp_path: Path) -> None:
        """``ddd sources`` names the plugin, which is how the module learns to depend on it."""
        plugin = self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        header = tmp_path / "build" / "ddd" / "img" / "ddd_layout.h"
        before = header.read_text(encoding="utf-8")
        edit_plugin(plugin)
        build(tmp_path / "build")
        assert header.read_text(encoding="utf-8") != before

    def test_plugins_beside_project_is_refused(self, tmp_path: Path) -> None:
        """Two lists of plugins would be two sources of truth."""
        self.write(tmp_path)
        listing = tmp_path / "CMakeLists.txt"
        listing.write_text(
            listing.read_text(encoding="utf-8").replace(
                '/schemas")', '/schemas"\n             PLUGINS "x.py")'
            ),
            encoding="utf-8",
        )
        run = cmake(
            "-S",
            str(tmp_path),
            "-B",
            str(tmp_path / "build"),
            f"-DDDD_EXECUTABLE={DDD.as_posix()}",
            cwd=tmp_path,
        )
        assert run.returncode != 0
        assert "PLUGINS cannot be given together with PROJECT" in run.stderr


@pytest.mark.parametrize("tool", [CMAKE, str(DDD)])
def test_the_tools_this_module_runs_exist(tool: str) -> None:
    """Said out loud, so that a missing tool is this failure and not a hundred cryptic ones."""
    assert Path(tool).is_file(), f"{tool} is not installed in this environment"
