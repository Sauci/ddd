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
import re
import shutil
import subprocess
import sysconfig
from pathlib import Path

import pytest

from conftest import EXAMPLES, declare

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(sysconfig.get_path("scripts"))
"""Where this interpreter's console scripts live: the venv's bin, or Scripts beside python.exe."""
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
        "-G",
        "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={NINJA}",
        f"-DDDD_EXECUTABLE={DDD.as_posix()}",
        *compiler(),
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


def add_an_unproduced_input(description: Path) -> None:
    """An input no component produces: ``missing-producer``, an error of the analysis rather
    than of the reading, so the project still resolves to a dictionary that could be dumped."""
    written = json.loads(description.read_text(encoding="utf-8"))
    written["component"]["interface"].append(declare("input", "Unproduced"))
    description.write_text(json.dumps(written, indent=2), encoding="utf-8")


class TestTheShippedExample:
    def test_it_configures_builds_and_checks_each_component_alone(self, tmp_path: Path) -> None:
        """The example the build integration page shows is the example the suite builds."""
        configure(EXAMPLES / "cmake", tmp_path / "build")
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "firmware.elf"
        assert (generated / "ddd_globals.c").is_file()
        assert (generated / "DemoDevice.a2l").is_file()
        assert (generated / "DemoDevice.ddd.json").is_file(), "the collected project description"
        assert (generated / "DemoDevice.dictionary.json").is_file(), "the dictionary it resolves to"
        # The per-component target runs the standalone check, which a lone component passes.
        build(tmp_path / "build", "sensor_hub.ddd")


class TestACollectedProjectWithPlugins:
    def write(self, tmp_path: Path, options: str = "") -> tuple[Path, Path]:
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
             PLUGINS "{plugin.as_posix()}"{options})
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

    def test_no_a2l_keeps_the_plugins_artefact(self, tmp_path: Path) -> None:
        """NO_A2L subtracts the a2l from the run; it does not narrow the run to the c artefact.

        Narrowing is what it used to do, and 'all' is the only artefact that produces the
        plugins' output, so a build asking for no a2l silently got no plugin artefact either -
        and nothing failed, because a plugin's files are not declared outputs.
        """
        self.write(tmp_path, options="\n             NO_A2L")
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "img"
        assert (generated / "ddd_layout.h").is_file(), "the plugin's artefact, with no a2l asked"
        assert (generated / "ddd_globals.c").is_file()
        assert not (generated / "LayoutDevice.a2l").exists(), "the a2l is what was subtracted"

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

    def test_the_list_target_lists_the_image_with_its_plugins_loaded(self, tmp_path: Path) -> None:
        """The image's project names the plugin the blocks belong to, so the table comes out
        with every block placed - and nothing has to be generated or compiled first."""
        self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        output = build(tmp_path / "build", "img_ddd_list")
        assert "EngineHours" in output
        assert "unknown-extension" not in output


VENDOR_HEADER = """#ifndef VENDOR_TYPES_H
#define VENDOR_TYPES_H
#ifndef VENDOR_PROFILE
#error "VENDOR_PROFILE is not defined; the component declaring the type publishes it."
#endif
typedef struct { unsigned short revision; } VendorState_t;
#endif
"""
"""A hand written header that refuses to compile without the flag its component publishes."""


def component(name: str, *, owns_the_type: bool) -> dict:
    """One component description, optionally declaring the external type and a struct using it."""
    body: dict = {
        "name": name,
        "description": name + " of the vendor block",
        "interface": [
            {
                "scope": "local",
                "definition": {
                    "name": name + "Value",
                    "kind": "measurement",
                    "description": "a plain local, so the component declares something",
                    "datatype": "uint8",
                    "conversion": {"kind": "identity"},
                    "volatile": False,
                },
            }
        ],
    }
    if owns_the_type:
        body["types"] = [
            {
                "type": "external",
                "name": "VendorState_t",
                "description": "the vendor's own type, defined by its own header",
                "header": "vendor_types.h",
            },
            {
                "type": "struct",
                "name": "VendorBlock_t",
                "description": "carries the vendor state",
                "members": [
                    {
                        "name": "state",
                        "member": "value",
                        "description": "opaque to DDD",
                        "typename": "VendorState_t",
                    }
                ],
            },
        ]
    return {"component": body}


class TestTheCompileUsageReachesEveryComponent:
    """The half of the propagation the shipped example cannot demonstrate.

    ``examples/cmake`` proves that a registered component's include directories travel, because
    its vendor header is findable no other way. Compile definitions and options travel by the
    same mechanism, and nothing shipped depends on one, so a regression could drop them in
    silence. Here the component declaring the type also publishes a flag its header refuses to
    compile without, and a component that links neither has to receive both.
    """

    def write(self, tmp_path: Path) -> None:
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "vendor_types.h").write_text(VENDOR_HEADER, encoding="utf-8")
        for spelling, name in (("owner", "Owner"), ("stranger", "Stranger")):
            (tmp_path / (spelling + ".c")).write_text(
                '#include "' + name + '.h"' + chr(10), encoding="utf-8"
            )
            (tmp_path / (spelling + ".ddd.json")).write_text(
                json.dumps(component(name, owns_the_type=name == "Owner"), indent=2),
                encoding="utf-8",
            )
        (tmp_path / "main.c").write_text("int main(void) { return 0; }" + chr(10), encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Usage LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(owner STATIC owner.c)
target_include_directories(owner PUBLIC "${{CMAKE_CURRENT_SOURCE_DIR}}/vendor")
target_compile_definitions(owner PUBLIC VENDOR_PROFILE=1)
ddd_add_component(owner JSON "{(tmp_path / "owner.ddd.json").as_posix()}")
add_library(stranger STATIC stranger.c)
ddd_add_component(stranger JSON "{(tmp_path / "stranger.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE owner stranger)
ddd_generate(img
             NAME UsageDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}")
""",
            encoding="utf-8",
        )

    def test_a_component_compiles_under_flags_it_never_asked_for(self, tmp_path: Path) -> None:
        """``stranger`` links nothing, yet must read the vendor header the way ``owner`` does.

        Its generated header includes ``ddd_types.h``, which includes the vendor header, which
        refuses to compile without the flag ``owner`` publishes. The build therefore passes only
        if both the include directory and the compile definition were collected and handed on.
        """
        self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        types = (tmp_path / "build" / "ddd" / "img" / "ddd_types.h").read_text(encoding="utf-8")
        assert '#include "vendor_types.h"' in types


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
        # Named, like the a2l, after the project inside the file rather than after the image.
        dictionary = tmp_path / "build" / "ddd" / "img" / "LayoutDevice.dictionary.json"
        assert json.loads(dictionary.read_text(encoding="utf-8"))["plugins"] == ["layout"]

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
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={NINJA}",
            f"-DDDD_EXECUTABLE={DDD.as_posix()}",
            *compiler(),
            cwd=tmp_path,
        )
        assert run.returncode != 0
        assert "PLUGINS cannot be given together with PROJECT" in run.stderr


class TestTheDictionary:
    """The build writes the resolved dictionary beside what it generated out of it."""

    def write(self, tmp_path: Path, options: str = "") -> Path:
        """One component collected into an image, which prints where its dictionary goes."""
        description = tmp_path / "store.ddd.json"
        described = {"component": {"name": "Store", "interface": [declare("output", "Level")]}}
        description.write_text(json.dumps(described, indent=2), encoding="utf-8")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Dictionary LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{description.as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME StoreDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"{options})
get_target_property(dictionary img DDD_DICTIONARY)
message(STATUS "DDD_DICTIONARY=${{dictionary}}")
""",
            encoding="utf-8",
        )
        return description

    def test_it_is_what_the_collected_project_dumps_where_the_property_says(
        self, tmp_path: Path
    ) -> None:
        self.write(tmp_path)
        configured = configure(tmp_path, tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "img"
        printed = re.search(r"DDD_DICTIONARY=(.*)", configured.stdout)
        assert printed is not None, configured.stdout
        assert Path(printed.group(1).strip()) == generated / "StoreDevice.dictionary.json"
        build(tmp_path / "build")
        # From outside the build directory the step runs in: the dictionary may not depend on
        # where the tool was started, so a dump from anywhere is the one the build wrote.
        dumped = subprocess.run(
            [str(DDD), "dump", str(generated / "StoreDevice.ddd.json")],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"},
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert dumped.returncode == 0, dumped.stderr
        written = (generated / "StoreDevice.dictionary.json").read_text(encoding="utf-8")
        assert written == dumped.stdout

    def test_a_finding_is_reported_once(self, tmp_path: Path) -> None:
        """The dictionary comes out of the generation's own run, so the build log carries each
        finding once, rather than once for every command that analysed the project."""
        self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        output = build(tmp_path / "build")
        assert output.count("warning[unused-output]") == 1, output

    def test_no_dictionary_leaves_out_the_file_and_the_property(self, tmp_path: Path) -> None:
        self.write(tmp_path, options="\n             NO_DICTIONARY")
        configured = configure(tmp_path, tmp_path / "build")
        assert "DDD_DICTIONARY=dictionary-NOTFOUND" in configured.stdout
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "img"
        assert (generated / "ddd_globals.c").is_file()
        assert not (generated / "StoreDevice.dictionary.json").exists()

    def test_a_run_that_fails_its_checks_keeps_the_last_dictionary(self, tmp_path: Path) -> None:
        """The dictionary is written with the artefacts or not at all: a failing run leaves it
        describing the artefacts that are still beside it.

        A dump of its own beside the generation would not guarantee that - a finding of the
        analysis stops no dump - so this holds because the generation writes it.
        """
        description = self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        dictionary = tmp_path / "build" / "ddd" / "img" / "StoreDevice.dictionary.json"
        before = dictionary.read_bytes()
        add_an_unproduced_input(description)
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path / "build")
        assert run.returncode != 0, run.stdout + run.stderr
        assert "missing-producer" in run.stdout + run.stderr
        assert dictionary.read_bytes() == before

    def test_severity_reaches_the_dictionary_as_it_reaches_the_artefacts(
        self, tmp_path: Path
    ) -> None:
        """An error relaxed with ``SEVERITY`` lets the generation through, dictionary included:
        whatever writes the dictionary has to apply the policy the build was given."""
        description = self.write(
            tmp_path, options='\n             SEVERITY "missing-producer=warning"'
        )
        add_an_unproduced_input(description)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        dictionary = tmp_path / "build" / "ddd" / "img" / "StoreDevice.dictionary.json"
        objects = json.loads(dictionary.read_text(encoding="utf-8"))["objects"]
        assert "Unproduced" in {entry["name"] for entry in objects}


@pytest.mark.parametrize("tool", [CMAKE, NINJA, str(DDD)])
def test_the_tools_this_module_runs_exist(tool: str) -> None:
    """Said out loud, so that a missing tool is this failure and not a hundred cryptic ones."""
    assert Path(tool).is_file(), f"{tool} is not installed in this environment"
