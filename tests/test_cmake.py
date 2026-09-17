"""The CMake module, configured and built rather than read.

``cmake/Ddd.cmake`` is the largest piece of DDD that no unit test can reach: it is CMake code,
and everything else in this suite that touches it checks what the file says, not what it does.
So it is run here, with the ``cmake`` the development requirements install, over the shipped
example and over small projects written into the temporary directory - one collecting its
components through the link graph and naming a plugin with ``PLUGINS``, one handing the tool a
hand-written project description that names its own plugin, and several written to exercise
one keyword each. What is asserted is what a build would see: the files the generation writes,
the project description the module assembles, the schemas it closes over the plugins, and a
rebuild that notices an edited plugin.

A configure and a build cost seconds each, and this file is a third of the suite's runtime,
so a class whose tests ask several questions of one tree configures and builds it once in a
class-scoped fixture and hands each test what that left behind. A class whose tests need
different calls, or that edit the tree and build again, keeps a tree per test - which is what
the ``tmp_path`` ones below are.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from conftest import EXAMPLES, declare
from ddd import __version__

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


def attempt(source: Path, build: Path, *definitions: str) -> subprocess.CompletedProcess[str]:
    """One configure, whether or not it is expected to succeed."""
    return cmake(
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


def configure(source: Path, build: Path, *definitions: str) -> subprocess.CompletedProcess[str]:
    run = attempt(source, build, *definitions)
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


BUILD_PAGE = ROOT / "docs" / "build_integration.rst"
"""The page whose recipes two of the classes below run rather than paraphrase."""


def example_project(tmp_path: Path) -> Path:
    """``examples/cmake`` beside the description and template directories it points at.

    Copied rather than built in place, because these tests edit the ``CMakeLists.txt`` the
    page shows; the relative paths it reaches its neighbours by are rewritten to the copies.
    """
    source = tmp_path / "example"
    shutil.copytree(EXAMPLES / "cmake", source)
    shutil.copytree(EXAMPLES / "demo", tmp_path / "demo")
    shutil.copytree(TEMPLATES, tmp_path / "templates")
    listing = source / "CMakeLists.txt"
    text = listing.read_text(encoding="utf-8")
    for spelling, replacement in (
        ("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake", (ROOT / "cmake").as_posix()),
        ("${CMAKE_CURRENT_SOURCE_DIR}/../demo", (tmp_path / "demo").as_posix()),
        ("${CMAKE_CURRENT_SOURCE_DIR}/../templates", (tmp_path / "templates").as_posix()),
    ):
        assert spelling in text, f"the example no longer names {spelling}"
        text = text.replace(spelling, replacement)
    listing.write_text(text, encoding="utf-8")
    return source


def documented_block(opening: str) -> str:
    """The code block of the build page that begins with ``opening``, dedented.

    Read out of the page rather than copied into this file: what these tests run then *is*
    what the page tells a reader to write, and a page that drifts from it fails here.
    """
    lines = BUILD_PAGE.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip().startswith(opening))
    indent = len(lines[start]) - len(lines[start].lstrip())
    block: list[str] = []
    for line in lines[start:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        block.append(line[indent:] if line.strip() else "")
    return "\n".join(block).rstrip() + "\n"


@dataclass(frozen=True)
class Dropped:
    """What the five steps of the class below left behind, for its two tests to read."""

    generated: Path
    built: bool
    """Whether the header of the component that later left was there while it was linked."""

    cleaned: tuple[bool, bool]
    """After ``ninja -t clean``: whether the header, and whether a declared output, survived."""

    described: dict[str, Any]
    """The collected project description, once the component had left the link graph."""

    rebuilt: tuple[int, str]
    """The exit code and output of the build after that, which has to fail."""


class TestAComponentThatLeavesTheImage:
    """The header of a component dropped from the link graph goes with it.

    ``ddd generate`` wrote what it rendered and removed nothing, and the module can declare
    only the files the template names give away - a per-component header's name comes out of
    a description file, which is not read at configure time. So dropping a component from
    ``target_link_libraries`` left its header in the output directory, on the include path of
    every component, and a translation unit went on compiling against the interface of a
    component the image no longer links. ``ninja -t clean`` did not take it either.
    """

    def write(self, tmp_path: Path) -> Path:
        return example_project(tmp_path)

    def drop_the_event_logger(self, source: Path) -> None:
        """The trigger: the image stops linking one of its four components.

        ``missing-producer`` is relaxed with it, because ``UserInterface`` reads a value
        ``EventLogger`` produced: an image that deliberately links a subset of a project is
        exactly the run that relaxes it, and without that the generation would refuse to
        write anything and the question of what it leaves behind would never arise.
        """
        listing = source / "CMakeLists.txt"
        text = listing.read_text(encoding="utf-8")
        linked = "target_link_libraries(firmware.elf PRIVATE user_interface event_logger)"
        schemas = 'SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas")'
        assert linked in text, "the example no longer links event_logger into the image"
        assert schemas in text, (
            "the example's ddd_generate() call no longer ends on SCHEMA_DIRECTORY"
        )
        text = text.replace(linked, linked.replace(" event_logger", ""))
        relaxed = schemas[:-1] + '\n             SEVERITY "missing-producer=ignore")'
        listing.write_text(text.replace(schemas, relaxed), encoding="utf-8")

    @pytest.fixture(scope="class")
    @staticmethod
    def dropped(tmp_path_factory: pytest.TempPathFactory) -> Dropped:
        """One story, told once: build, drop the component, clean, regenerate, build again.

        Both questions below are about the same five steps of the same tree - what the drop
        takes away, and what a clean in the middle of it does not lose - and each of them
        configuring and building the four-component example on its own costs seven seconds.
        """
        story = TestAComponentThatLeavesTheImage()
        source = story.write(tmp_path_factory.mktemp("leaving"))
        build_dir = source.parent / "build"
        configure(source, build_dir)
        build(build_dir)
        generated = build_dir / "ddd" / "firmware.elf"
        built = (generated / "EventLogger.h").is_file()
        story.drop_the_event_logger(source)
        # The clean before the regeneration: what it leaves behind is what the next
        # generation has to know it once wrote.
        build(build_dir, "clean")
        cleaned = (
            (generated / "EventLogger.h").is_file(),
            (generated / "ddd_globals.c").exists(),
        )
        build(build_dir, "firmware_ddd_generation")
        described = json.loads((generated / "DemoDevice.ddd.json").read_text(encoding="utf-8"))
        run = cmake("--build", str(build_dir), cwd=build_dir)
        return Dropped(
            generated=generated,
            built=built,
            cleaned=cleaned,
            described=described,
            rebuilt=(run.returncode, run.stdout + run.stderr),
        )

    def test_its_header_is_removed_and_stops_compiling(self, dropped: Dropped) -> None:
        """The whole build first, which is what proves the header was usable: ``event_logger.c``
        includes ``EventLogger.h`` and compiled against it. After the drop it cannot, which is
        what keeps the include path to the components of the image the build page describes.
        """
        generated = dropped.generated
        assert dropped.built, "the header of a linked component was never written"
        includes = dropped.described["project"]["includes"]
        assert not any("event_logger" in entry for entry in includes)
        assert not (generated / "EventLogger.h").exists(), "the header of a component that left"
        assert (generated / "SensorHub.h").is_file(), "the components that stayed keep theirs"

        code, output = dropped.rebuilt
        assert code != 0, "a component the image no longer links still compiled"
        assert "EventLogger.h" in output

    def test_a_clean_does_not_lose_what_the_next_build_has_to_take_back(
        self, dropped: Dropped
    ) -> None:
        """``ninja -t clean`` removes the files the module declared and leaves the
        per-component headers it never knew about, so the record of them has to survive it -
        which it does, being no more a declared output than they are."""
        assert dropped.cleaned == (True, False), (
            "a clean either took the header it does not know the name of, or left the "
            "declared outputs it does"
        )
        assert not (dropped.generated / "EventLogger.h").exists(), "the generation after it"
        assert (dropped.generated / "ddd_globals.c").is_file()


class TestACollectedProjectWithPlugins:
    """Two of these share one configure and one build.

    Both ask what the same tree came out as - the project the module wrote, the schemas it
    closed over the plugin, the artefacts, and the table the list target prints - and a
    configure and a build of even this small project cost four seconds together. The two that
    have a tree of their own are the two that cannot share one: one subtracts the a2l from
    the call, the other edits the plugin and builds again.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, str]:
        """The tree, its component, its plugin, and what the list target printed."""
        source = tmp_path_factory.mktemp("collected")
        component, plugin = TestACollectedProjectWithPlugins().write(source)
        configure(source, source / "build")
        build(source / "build")
        return source, component, plugin, build(source / "build", "img_ddd_list")

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
        self, built: tuple[Path, Path, Path, str]
    ) -> None:
        source, component, plugin, _ = built
        generated = source / "build" / "ddd" / "img"
        described = json.loads((generated / "LayoutDevice.ddd.json").read_text(encoding="utf-8"))
        assert described["project"]["plugins"] == [plugin.as_posix()]
        assert described["project"]["includes"] == [component.as_posix()]
        assert (generated / "ddd_layout.h").is_file(), "the plugin's artefact, under generate all"
        assert closed_over_layout(source / "build" / "schemas" / "ddd_component.schema.json")

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

    def test_the_list_target_lists_the_image_with_its_plugins_loaded(
        self, built: tuple[Path, Path, Path, str]
    ) -> None:
        """The image's project names the plugin the blocks belong to, so the table comes out
        with every block placed - and nothing has to be generated or compiled first."""
        listed = built[3]
        assert "EngineHours" in listed
        assert "unknown-extension" not in listed


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


OPENS_A_COMMENT = "opens a comment /* inside"
"""The one piece of prose that turns every generated comment into a build failure.

``-Wcomment`` is in ``-Wall`` and reports ``"/*" within comment``; with ``-Werror`` beside it -
the set ``docker/compile.sh`` and ``docs/generated_artefacts.rst`` verify the generated code
with - a single description carrying it stops the build in the definition file and in every
header that repeats it. Nothing shipped carries one, so only a project written here can prove
the escape."""


class TestGeneratedCommentsUnderTheVerifiedWarningSet:
    """The generated code compiled the way the repository says it verifies it."""

    def write(self, tmp_path: Path) -> None:
        described = {
            "component": {
                "name": "Store",
                "description": OPENS_A_COMMENT,
                "constants": [{"name": "STORE_CELLS", "value": 4, "description": OPENS_A_COMMENT}],
                "interface": [
                    {
                        "scope": "local",
                        "definition": {
                            "name": "StoreValue",
                            "kind": "measurement",
                            "description": OPENS_A_COMMENT,
                            "unit": OPENS_A_COMMENT,
                            "datatype": "uint8",
                            "conversion": {"kind": "identity"},
                            "volatile": False,
                        },
                    }
                ],
            }
        }
        (tmp_path / "store.ddd.json").write_text(json.dumps(described, indent=2), encoding="utf-8")
        (tmp_path / "store.c").write_text('#include "Store.h"\n', encoding="utf-8")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Comments LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(NOT MSVC)
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual
                        -Wstrict-prototypes)
else()
    add_compile_options(/W4 /WX)
endif()
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(tmp_path / "store.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME CommentDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}")
""",
            encoding="utf-8",
        )

    def test_a_description_that_opens_a_comment_compiles(self, tmp_path: Path) -> None:
        """A description, a unit, a component and a constant, each carrying ``/*``.

        The definition file, the shared header, the types header and the component's own
        header all repeat the same prose, so the compiler answers for every template the
        examples ship rather than for the one the assertion below reads.
        """
        self.write(tmp_path)
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "img"
        assert "/ * inside" in (generated / "ddd_globals.c").read_text(encoding="utf-8")


class TestEveryGeneratedHeaderCompilesAlone:
    """``docker/compile.sh``'s own proof, over the projects it used to fail on.

    The shipped verification writes one translation unit per generated header - the header
    included twice, and nothing else - so that every header is shown to be self contained and
    to survive being included a second time. That leaves a header with nothing in it a
    translation unit with nothing in it, which ``-Wpedantic -Werror`` refuses (``ISO C
    forbids an empty translation unit``), and three legitimate projects ended there: one whose
    objects are all floating point, one that declares no object at all, and the layout
    example, whose plugin writes a table naming objects no include of its own declares.
    Compiled through cmake rather than by hand so that the flag set is the one every other
    test in this file uses, and so that MSVC - where the same defect is ``C4206`` - is
    answered for as well.
    """

    def generated(self, tmp_path: Path, project: Path) -> Path:
        output = tmp_path / "gen"
        run = subprocess.run(
            [str(DDD), "generate", "all", str(project), "-o", str(output), "-t", TEMPLATES],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        return output

    def compile_alone(self, tmp_path: Path, output: Path) -> None:
        """One translation unit per generated header, beside the generated sources."""
        units = tmp_path / "units"
        units.mkdir()
        sources = sorted(output.glob("*.c"))
        headers = sorted(output.glob("*.h"))
        assert headers, "nothing was generated to compile"
        for header in headers:
            unit = units / f"tu_{header.stem}.c"
            unit.write_text(f'#include "{header.name}"\n' * 2, encoding="utf-8")
            sources.append(unit)
        listed = "\n    ".join(f'"{source.as_posix()}"' for source in sources)
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Alone LANGUAGES C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(NOT MSVC)
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual
                        -Wstrict-prototypes)
else()
    add_compile_options(/W4 /WX)
endif()
add_library(alone STATIC
    {listed})
target_include_directories(alone PRIVATE "{output.as_posix()}")
""",
            encoding="utf-8",
        )
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")

    def project(self, tmp_path: Path, *includes: str) -> Path:
        description = tmp_path / "project.ddd.json"
        description.write_text(
            json.dumps({"project": {"name": "P", "includes": list(includes)}}), encoding="utf-8"
        )
        return description

    def test_a_project_whose_objects_are_all_floating_point_compiles(self, tmp_path: Path) -> None:
        """No integer datatype, so nothing asked for ``<stdint.h>`` and the types header was
        a guard around nothing - which every other generated header includes and nothing
        else, so two translation units ended there rather than one."""
        (tmp_path / "f.ddd.json").write_text(
            json.dumps(
                {
                    "component": {
                        "name": "F",
                        "interface": [declare("local", "Fx", "float32")],
                    }
                }
            ),
            encoding="utf-8",
        )
        output = self.generated(tmp_path, self.project(tmp_path, "f.ddd.json"))
        assert "#include <stdint.h>" in (output / "ddd_types.h").read_text(encoding="utf-8")
        self.compile_alone(tmp_path, output)

    def test_an_image_registering_no_component_compiles(self, tmp_path: Path) -> None:
        """The cmake module calls an empty ``includes`` list a project DDD accepts, and it
        is - an image that registers no component yet. Everything it generates was empty."""
        output = self.generated(tmp_path, self.project(tmp_path))
        assert "This project does not define any global variable" in (
            output / "ddd_globals.c"
        ).read_text(encoding="utf-8")
        self.compile_alone(tmp_path, output)

    def test_the_layout_examples_plugin_header_compiles(self, tmp_path: Path) -> None:
        """The plugin's table takes the address and the size of every stamped object and
        included no declaration of any of them, so the one artefact the example exists to
        show was the one the shipped harness could not compile."""
        shutil.copytree(LAYOUT, tmp_path / "layout")
        shutil.copytree(EXAMPLES / "plugins", tmp_path / "plugins")
        output = self.generated(tmp_path, tmp_path / "layout" / "project.ddd.json")
        assert '#include "ddd_globals.h"' in (output / "ddd_layout.h").read_text(encoding="utf-8")
        self.compile_alone(tmp_path, output)


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
             NAME Ignored
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
        configured = configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        assert (tmp_path / "build" / "ddd" / "img" / "ddd_layout.h").is_file()
        assert closed_over_layout(tmp_path / "build" / "schemas" / "ddd_component.schema.json")
        # Named, like the a2l, after the project inside the file rather than after the image.
        dictionary = tmp_path / "build" / "ddd" / "img" / "LayoutDevice.dictionary.json"
        assert json.loads(dictionary.read_text(encoding="utf-8"))["plugins"] == ["layout"]
        # The call gives NAME as well, which this mode has no use for: the name inside the
        # file is what everything is named after, and saying so is better than renaming
        # nothing in silence.
        assert not (tmp_path / "build" / "ddd" / "img" / "Ignored.a2l").exists()
        assert "NAME is ignored with PROJECT" in configured.stdout, configured.stdout

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
    """The build writes the resolved dictionary beside what it generated out of it.

    The first two share a configure and a build: they ask two questions of one tree, and this
    file pays for a tree in seconds. The three below have their own, because each wants a
    different call - one without the dictionary, one whose description is edited after the
    build, one with a severity override.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
        """The tree, what configure printed, and what the first build said."""
        source = tmp_path_factory.mktemp("dictionary")
        TestTheDictionary().write(source)
        configured = configure(source, source / "build")
        return source, configured.stdout, build(source / "build")

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
        self, built: tuple[Path, str, str]
    ) -> None:
        source, configured, _ = built
        generated = source / "build" / "ddd" / "img"
        printed = re.search(r"DDD_DICTIONARY=(.*)", configured)
        assert printed is not None, configured
        assert Path(printed.group(1).strip()) == generated / "StoreDevice.dictionary.json"
        # From outside the build directory the step runs in: the dictionary may not depend on
        # where the tool was started, so a dump from anywhere is the one the build wrote.
        dumped = subprocess.run(
            [str(DDD), "dump", str(generated / "StoreDevice.ddd.json")],
            cwd=source,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"},
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert dumped.returncode == 0, dumped.stderr
        written = (generated / "StoreDevice.dictionary.json").read_text(encoding="utf-8")
        assert written == dumped.stdout

    def test_a_finding_is_reported_once(self, built: tuple[Path, str, str]) -> None:
        """The dictionary comes out of the generation's own run, so the build log carries each
        finding once, rather than once for every command that analysed the project."""
        output = built[2]
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


class TestTheDocumentedAddressMapRecipe:
    """The two-run flow of the build page, run: three builds, and what the a2l ends up with.

    Every build after the first used to fail. The recipe extracts every defined symbol of the
    image, and an address outside ``0 .. 0xFFFFFFFF`` was refused whether or not DDD knew the
    symbol - so on a 64 bit host the hundred entries of the c runtime above 4 GB stopped the
    generation with a usage error, and the a2l kept ``ECU_ADDRESS 0x00000000`` for ever. Only
    the symbols the a2l states an address for are weighed now.

    Two adaptations, both of them the page's own subject. The image is linked at a base a 32
    bit ``ECU_ADDRESS`` can hold, because this host would otherwise place *DDD's own*
    variables above 4 GB, which is not a thing the tool can do anything about - "what a host
    build of an embedded project runs into first". And ``address-missing`` is lowered to
    ``info`` rather than left to ``STRICT``, because this project has the two objects a symbol
    lister cannot answer for: a structure member, addressed under its access path, and one a
    condition compiled out of the image - the page says a project adds the first itself, and
    the specification calls the second a legitimate omission.
    """

    def write(self, tmp_path: Path) -> Path:
        source = example_project(tmp_path)
        recipe = documented_block("set(address_map")
        assert 'ADDRESS_MAP "${address_map}"' in recipe, "the page no longer names the map so"
        (source / "cmake").mkdir()
        (source / "cmake" / "AddressMap.cmake").write_text(
            documented_block("# cmake/AddressMap.cmake"), encoding="utf-8"
        )
        listing = source / "CMakeLists.txt"
        text = listing.read_text(encoding="utf-8")
        schemas = 'SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas")'
        assert schemas in text
        text = text.replace(
            "ddd_generate(firmware.elf",
            recipe.split("ddd_generate(")[0] + "ddd_generate(firmware.elf",
        ).replace(
            schemas,
            schemas[:-1] + '\n             ADDRESS_MAP "${address_map}"'
            '\n             STRICT\n             SEVERITY "address-missing=info")',
        )
        text += "\n" + "add_custom_command(" + recipe.split("add_custom_command(", 1)[1]
        # A 64 bit image is based above 4 GB - 0x140000000 on Windows, and wherever the loader
        # cares to put a position independent executable on linux - which no ECU_ADDRESS holds;
        # an embedded image is not, and it is an embedded image the a2l describes. A GNU
        # toolchain from end to end, since the recipe reads the nm of binutils as the page
        # says, but the option is the object format's rather than the toolchain's: `ld` writing
        # PE takes a base to write at, `ld` writing ELF places a non relocatable executable at
        # 0x400000 on its own and has no `--image-base` at all.
        text += (
            "\nif(WIN32 AND NOT MSVC)\n"
            '    target_link_options(firmware.elf PRIVATE "-Wl,--image-base,0x400000")\n'
            "elseif(NOT MSVC)\n"
            '    target_link_options(firmware.elf PRIVATE "-no-pie")\n'
            "endif()\n"
        )
        listing.write_text(text, encoding="utf-8")
        return source

    def test_three_builds_settle_with_the_addresses_in_the_a2l(self, tmp_path: Path) -> None:
        source = self.write(tmp_path)
        configure(source, tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "firmware.elf"

        build(tmp_path / "build")
        a2l = (generated / "DemoDevice.a2l").read_text(encoding="utf-8")
        assert "ECU_ADDRESS 0x00000000" in a2l, "the first build runs before anything is linked"
        extracted = json.loads((generated / "addresses.json").read_text(encoding="utf-8"))
        assert "ValueA" in extracted, "the step extracts the symbols of the image"
        assert any(name.startswith("_") for name in extracted), "the c runtime's among them"

        output = build(tmp_path / "build")
        assert "address-missing" in output, "the two objects a symbol lister cannot answer for"
        a2l = (generated / "DemoDevice.a2l").read_text(encoding="utf-8")
        assert f"ECU_ADDRESS 0x{int(extracted['ValueA'], 16):08X}" in a2l

        # "nothing is recompiled, nothing is relinked, and the flow settles after one extra
        # round rather than chasing its own tail" - the page's own sentence about this flow.
        assert "no work to do" in build(tmp_path / "build")


class TestAKeywordGivenNoValue:
    """``ADDRESS_MAP ${DDD_MAP}`` with ``DDD_MAP`` unset is the ordinary CMake mistake.

    Neither function read ``KEYWORDS_MISSING_VALUES``, so the keyword was dropped in silence
    and the call ran as if it had never been given: the a2l came out with every
    ``ECU_ADDRESS 0x00000000``, no map was seeded and none was a dependency, so the two-run
    flow the map was configured for never happened - and ``PROJECT`` without a value fell
    into the collected mode, generating something else entirely.
    """

    def write(self, tmp_path: Path, call: str) -> Path:
        component = tmp_path / "store.ddd.json"
        described = {"component": {"name": "Store", "interface": [declare("local", "Level")]}}
        component.write_text(json.dumps(described, indent=2), encoding="utf-8")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Missing LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
{call.format(component=component.as_posix(), templates=TEMPLATES.as_posix())}
""",
            encoding="utf-8",
        )
        return tmp_path

    @pytest.mark.parametrize(
        ("call", "keyword"),
        [
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" ADDRESS_MAP ${{DDD_MAP}})',
                "ADDRESS_MAP",
                id="the address map of the two-run flow",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" PROJECT ${{DDD_PROJECT}})',
                "PROJECT",
                id="the project description, which decides the mode",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                "ddd_generate(img TEMPLATE_DIRECTORY ${{DDD_TEMPLATES}})",
                "TEMPLATE_DIRECTORY",
                id="the required keyword",
            ),
            pytest.param(
                "ddd_add_component(store JSON ${{DDD_FILES}})\n"
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}")',
                "JSON",
                id="the descriptions of a component",
            ),
        ],
    )
    def test_it_is_refused_and_named(self, tmp_path: Path, call: str, keyword: str) -> None:
        source = self.write(tmp_path, call)
        run = attempt(source, tmp_path / "build")
        assert run.returncode != 0, run.stdout + run.stderr
        # Rewrapped: cmake folds a message to its own width, so the sentence arrives with
        # newlines and two-space indents wherever it happened to break.
        assert f'"{keyword}" was given no value' in " ".join(run.stderr.split())

    def test_a_keyword_with_a_value_still_configures(self, tmp_path: Path) -> None:
        """The positive control: the same call with the variable set is not refused."""
        source = self.write(
            tmp_path,
            'ddd_add_component(store JSON "{component}")\n'
            'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" ADDRESS_MAP ${{DDD_MAP}})',
        )
        # A map in the source tree has to exist: there, a missing file is a mistake of its own.
        (tmp_path / "map.json").write_text("{}\n", encoding="utf-8")
        configure(source, tmp_path / "build", f"-DDDD_MAP={(tmp_path / 'map.json').as_posix()}")


VENDOR_TYPES = """#ifndef KEYWORD_VENDOR_H
#define KEYWORD_VENDOR_H
typedef struct { unsigned short revision; } VendorState_t;
#endif
"""
"""A header no registered component publishes the directory of: only ``LINK_LIBRARIES`` does."""


@dataclass(frozen=True)
class Configured:
    """What one configure and three builds of one tree left behind, for the class below."""

    generated: Path
    configured: str
    checked: str
    """The output of building ``<stem>_ddd_check`` before anything else was built."""

    after_check: list[str]
    """What was in the output directory once the check target had run, by file name."""

    built: str
    rebuilt: str
    """The build after a ``DEPENDS`` file was rewritten and nothing else."""


class TestTheKeywordsOfOneCall:
    """Five keywords, a property and a target, asked of one project configured once.

    A configure and a build cost seconds each, and this file is a third of the suite's
    runtime, so every keyword answered by its own tree is a keyword that goes on being
    untested instead. These are the ones that can share a project: they are the arguments of
    one call, they do not contradict each other, and what each does is visible in the tree the
    build leaves behind. The class is configured and built once, by the fixture below, and
    each test reads one answer out of it. ``STRICT`` and ``NO_PROPAGATE_HEADERS`` are not here
    because a project exercising them is a build that fails, which is a project of its own.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def built(tmp_path_factory: pytest.TempPathFactory) -> Configured:
        source = tmp_path_factory.mktemp("keywords")
        (source / "vendor").mkdir()
        (source / "vendor" / "vendor_types.h").write_text(VENDOR_TYPES, encoding="utf-8")
        (source / "extra.txt").write_text("the file DEPENDS names\n", encoding="utf-8")
        (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        # Includes nothing: what needs the vendor header here is the *definition* file, which
        # is the translation unit LINK_LIBRARIES reaches.
        (source / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (source / "store.ddd.json").write_text(
            json.dumps(
                {
                    "component": {
                        "name": "Store",
                        "description": "one component, so the call has something to generate",
                        "types": [
                            {
                                "type": "external",
                                "name": "VendorState_t",
                                "description": "defined by the vendor's own header",
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
                        ],
                        "interface": [declare("local", "Level", "uint16", id="ab3cd4ef5gh6")],
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        # The image is named so that the defaulted NAME has something to sanitise: the stem
        # names the helper targets as written, and the project name has to be a c identifier.
        (source / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Keywords LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(vendor INTERFACE)
target_include_directories(vendor INTERFACE "${{CMAKE_CURRENT_SOURCE_DIR}}/vendor")
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(source / "store.ddd.json").as_posix()}")
add_executable(2nd-image.elf main.c)
target_link_libraries(2nd-image.elf PRIVATE store)
ddd_generate(2nd-image.elf
             OUTPUT_DIRECTORY generated
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             BYTE_ORDER big
             LINK_LIBRARIES vendor
             DEPENDS "${{CMAKE_CURRENT_SOURCE_DIR}}/extra.txt")
get_target_property(a2l 2nd-image.elf DDD_A2L)
message(STATUS "DDD_A2L=${{a2l}}")
""",
            encoding="utf-8",
        )
        build_dir = source / "build"
        configured = configure(source, build_dir)
        generated = build_dir / "generated"
        # Before anything else, so that what the check target leaves behind is only what
        # configure wrote there.
        checked = build(build_dir, "2nd-image_ddd_check")
        after_check = sorted(path.name for path in generated.iterdir())
        output = build(build_dir)
        (source / "extra.txt").write_text("rewritten by the test\n", encoding="utf-8")
        return Configured(
            generated=generated,
            configured=configured.stdout,
            checked=checked,
            after_check=after_check,
            built=output,
            rebuilt=build(build_dir),
        )

    def test_the_name_defaults_to_the_image_sanitised_into_an_identifier(
        self, built: Configured
    ) -> None:
        """``2nd-image.elf`` is not a c identifier and the a2l project name has to be one, so
        the hyphen becomes an underscore and the leading digit gains an ``N``. The helper
        targets are named after the stem as written - ``2nd-image_ddd_check`` is what the
        fixture built - because a target name is nobody's identifier."""
        assert (built.generated / "N2nd_image.a2l").is_file()
        assert (built.generated / "N2nd_image.ddd.json").is_file(), "the collected project"
        assert (built.generated / "N2nd_image.dictionary.json").is_file()

    def test_the_output_directory_is_where_the_files_are(self, built: Configured) -> None:
        """A relative ``OUTPUT_DIRECTORY`` is resolved against the build directory, which is
        the only place a generated file may go."""
        assert (built.generated / "ddd_globals.c").is_file()
        assert built.generated.name == "generated"
        assert not (built.generated.parent / "ddd" / "2nd-image.elf").exists(), (
            "the default output directory was used beside the one the call named"
        )

    def test_the_byte_order_reaches_the_a2l(self, built: Configured) -> None:
        a2l = (built.generated / "N2nd_image.a2l").read_text(encoding="utf-8")
        assert "BYTE_ORDER MSB_FIRST" in a2l, "BYTE_ORDER big is MSB_FIRST in ASAP2"

    def test_the_a2l_property_names_the_file_that_was_written(self, built: Configured) -> None:
        """What a post-build step reads to install or publish the a2l, so it has to be the
        path the generator actually wrote - the a2l is named from inside the description."""
        printed = re.search(r"DDD_A2L=(.*)", built.configured)
        assert printed is not None, built.configured
        assert Path(printed.group(1).strip()) == built.generated / "N2nd_image.a2l"

    def test_link_libraries_reaches_the_definition_file(self, built: Configured) -> None:
        """The definition file includes the types header, which includes the vendor header.
        Nothing registered publishes that directory - the vendor library is linked by no
        component - so the build compiled only because ``LINK_LIBRARIES`` handed it over."""
        types = (built.generated / "ddd_types.h").read_text(encoding="utf-8")
        assert '#include "vendor_types.h"' in types
        assert "ddd_globals.c.obj" in built.built or "ddd_globals.c.o" in built.built, built.built

    def test_depends_retriggers_the_generation(self, built: Configured) -> None:
        """A file the project names with ``DEPENDS`` - a linker script, a header the templates
        read - is a dependency of the generation and nothing else changed between the two
        builds the fixture ran."""
        assert "Generating the data dictionary of 2nd-image.elf" in built.rebuilt, built.rebuilt

    def test_the_check_target_checks_without_generating(self, built: Configured) -> None:
        """What a ci job runs for the verdict alone: the whole project under the same policy,
        and not one artefact written."""
        assert "are consistent" in built.checked, built.checked
        # Both of these are written by the configure step, not by the build: the record of
        # what the build runs, and the project description assembled from the link closure.
        assert built.after_check == ["N2nd_image.ddd.json", "ddd-build.json"], (
            "the check target generated something, which is what it exists not to do"
        )


class TestTheComponentCheckTarget:
    """What ``ninja <target>.ddd`` says about a component that is wrong in the two ways it can be.

    A description that does not parse at all was skipped at configure time:
    ``_ddd_is_component_file`` answered FALSE for it, which is the answer it owes a
    *vocabulary* file, so the target was created with no command on it and ``ninja
    store.ddd`` said ``no work to do`` about a file that does not parse - and went on saying
    it, the target being built at configure time, until somebody configured again.  The other
    way, a description that reads and does not hold together, was pinned nowhere: the shipped
    example's target is built in this file, and it passes.

    One configure for both, because the two components are two targets of one project and
    neither test touches the other's file.
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def source(tmp_path_factory: pytest.TempPathFactory) -> Path:
        source = tmp_path_factory.mktemp("check-targets")
        # What an editor leaves behind mid-edit, and a merge conflict leaves for longer.
        (source / "store.ddd.json").write_text("{ broken", encoding="utf-8")
        (source / "bad.ddd.json").write_text(
            json.dumps(
                {
                    "component": {
                        "name": "Bad",
                        "description": "reads, and does not hold together",
                        "interface": [
                            declare("local", "Level", "uint8", init=300, id="ab3cd4ef5gh6")
                        ],
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        for name in ("store", "bad"):
            (source / f"{name}.c").write_text(f"int {name}(void) {{ return 0; }}\n", "utf-8")
        (source / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Broken LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(source / "store.ddd.json").as_posix()}")
add_library(bad STATIC bad.c)
ddd_add_component(bad JSON "{(source / "bad.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store bad)
ddd_generate(img
             NAME BrokenDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}")
""",
            encoding="utf-8",
        )
        configure(source, source / "build")
        return source

    def test_a_description_that_does_not_parse_is_reported_and_the_repair_is_checked(
        self, source: Path
    ) -> None:
        """Configured over the broken file, so the target is the one that configure built.

        The second half is what the target being empty hid: the file is repaired without
        configuring again - which is what a developer does, the editor being where both
        happen - and the same target has to run the check over the repaired file.
        """
        run = cmake("--build", str(source / "build"), "--target", "store.ddd", cwd=source)
        assert run.returncode != 0, "a component that does not parse passed its own check target"
        assert "json-syntax" in run.stdout + run.stderr

        described = {
            "component": {
                "name": "Store",
                "interface": [declare("local", "Level", id="ab3cd4ef5gh6")],
            }
        }
        (source / "store.ddd.json").write_text(json.dumps(described, indent=2), encoding="utf-8")
        assert "1 component" in build(source / "build", "store.ddd")

    def test_a_component_that_fails_its_own_check_fails_its_target(self, source: Path) -> None:
        """``init: 300`` on a ``uint8``: an error of the component alone, which is what the
        standalone check is for. The target has to carry the exit code out of the tool."""
        run = cmake("--build", str(source / "build"), "--target", "bad.ddd", cwd=source)
        assert run.returncode != 0, "a component whose own check fails passed its check target"
        assert "init-invalid" in run.stdout + run.stderr


class TestStrict:
    """``STRICT`` is what a ci build wants and a developer build does not: a warning stops it.

    The positive control is two classes up: ``TestTheDictionary`` builds a project with this
    very warning, without ``STRICT``, and the build passes with the warning in its log; and
    ``TestTheDocumentedAddressMapRecipe`` builds a clean project *with* ``STRICT``. What was
    pinned nowhere is that the keyword reaches the generation at all.
    """

    def test_a_warning_stops_the_build_and_writes_nothing(self, tmp_path: Path) -> None:
        described = {"component": {"name": "Store", "interface": [declare("output", "Level")]}}
        (tmp_path / "store.ddd.json").write_text(json.dumps(described, indent=2), encoding="utf-8")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Strict LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(tmp_path / "store.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME StrictDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             STRICT)
""",
            encoding="utf-8",
        )
        configure(tmp_path, tmp_path / "build")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        assert run.returncode != 0, "STRICT let a build through on a warning"
        assert "unused-output" in run.stdout + run.stderr
        assert not (tmp_path / "build" / "ddd" / "img" / "ddd_globals.c").exists(), (
            "the generation wrote its artefacts and then failed"
        )


class TestPropagatingTheHeaders:
    """``NO_PROPAGATE_HEADERS``, which a project with two images has to give to both.

    Every other test in this file takes the propagation: a component includes its generated
    header and nothing in its own ``CMakeLists`` says where that header is. This one is the
    other half - what a project gets when it opts out, and what it then has to write itself -
    and the refusal that makes opting out compulsory for the second image.
    """

    OPT_OUT = "\n             NO_PROPAGATE_HEADERS"

    def write(self, tmp_path: Path, tail: str, options: str = OPT_OUT) -> None:
        described = {"component": {"name": "Store", "interface": [declare("local", "Level")]}}
        (tmp_path / "store.ddd.json").write_text(json.dumps(described, indent=2), encoding="utf-8")
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        # Includes the header generated for it, which is what the propagation is for.
        (tmp_path / "store.c").write_text('#include "Store.h"\n', encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Propagation LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(tmp_path / "store.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME StoreDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"{options})
{tail.format(templates=TEMPLATES.as_posix())}
""",
            encoding="utf-8",
        )

    def test_a_component_is_not_handed_the_headers_and_says_so(self, tmp_path: Path) -> None:
        """Nothing else tells the compiler where ``Store.h`` is, so the component's own
        translation unit is where the opt-out becomes visible."""
        self.write(tmp_path, "")
        configure(tmp_path, tmp_path / "build")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        assert run.returncode != 0, "the headers were propagated after all"
        assert "Store.h" in run.stdout + run.stderr

    def test_linking_them_by_hand_is_what_the_page_tells_a_project_to_do(
        self, tmp_path: Path
    ) -> None:
        """The interface library is still there and still carries the include directory; what
        ``NO_PROPAGATE_HEADERS`` withdraws is only the automatic link into every component."""
        self.write(tmp_path, "target_link_libraries(store PRIVATE img_ddd_headers)")
        configure(tmp_path, tmp_path / "build")
        build(tmp_path / "build")
        assert (tmp_path / "build" / "ddd" / "img" / "Store.h").is_file()

    def test_a_second_image_may_not_hand_the_components_a_second_set(self, tmp_path: Path) -> None:
        """Two images propagating would give one component two sets of headers, and whichever
        include directory came first would silently decide which interface it compiles
        against. The second call refuses, naming the first image."""
        self.write(
            tmp_path,
            "add_executable(second.elf main.c)\n"
            "target_link_libraries(second.elf PRIVATE store)\n"
            "ddd_generate(second.elf\n"
            "             NAME SecondDevice\n"
            '             TEMPLATE_DIRECTORY "{templates}")',
            # The first image propagates, which is the default and what makes the second's
            # propagation the ambiguity: opting *both* out is the answer the message gives.
            options="",
        )
        run = attempt(tmp_path, tmp_path / "build")
        assert run.returncode != 0, "a second image propagated its headers over the first's"
        said = " ".join(run.stderr.split())
        assert "already compile against the headers generated for" in said, said
        assert "NO_PROPAGATE_HEADERS to *both*" in said


class TestAToolOfAnotherRelease:
    """The module and the ``ddd`` it drives have to be one release.

    ``ddd cmake-dir`` and the header of the module invite a project to copy ``Ddd.cmake`` into
    its own tree, where it then sits beside whichever ``ddd`` the environment has: 0.10.0's
    module with 0.9.0's tool, say.  Nothing compared the two.  The configure step passed -
    ``schema all``, ``build-info`` and ``sources`` are older than either release - and the
    first *build* failed with argparse's ``unrecognized arguments: --dictionary``, which names
    the option and not the mismatch behind it; the other way round, the build quietly ran with
    the old module's option set.  Every other test in this file is the positive control: they
    all configure against the ``ddd`` of this tree, whose version the module states.
    """

    def fake_tool(self, tmp_path: Path, version: str) -> Path:
        """A ``ddd`` that answers ``--version`` and nothing else, as the handshake needs."""
        if os.name == "nt":
            tool = tmp_path / "ddd.bat"
            tool.write_text(f"@echo ddd {version}\n", encoding="utf-8")
        else:
            tool = tmp_path / "ddd.sh"
            tool.write_text(f'#!/bin/sh\necho "ddd {version}"\n', encoding="utf-8")
            tool.chmod(0o755)
        return tool

    def write(self, tmp_path: Path) -> None:
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Mismatch LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_executable(img main.c)
""",
            encoding="utf-8",
        )

    def test_the_include_refuses_it_naming_both_versions(self, tmp_path: Path) -> None:
        """Refused where the module is included, before a single target is defined: the
        mismatch is a property of the pair, not of anything a call says."""
        self.write(tmp_path)
        tool = self.fake_tool(tmp_path, "0.0.1")
        run = cmake(
            "-S",
            str(tmp_path),
            "-B",
            str(tmp_path / "build"),
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={NINJA}",
            f"-DDDD_EXECUTABLE={tool.as_posix()}",
            *compiler(),
            cwd=tmp_path,
        )
        assert run.returncode != 0, "a tool of another release configured without a word"
        said = " ".join(run.stderr.split())
        assert "0.0.1" in said and __version__ in said, said
        assert tool.as_posix() in said.replace("\\", "/"), "the message does not name the tool"


@pytest.mark.parametrize("tool", [CMAKE, NINJA, str(DDD)])
def test_the_tools_this_module_runs_exist(tool: str) -> None:
    """Said out loud, so that a missing tool is this failure and not a hundred cryptic ones."""
    assert Path(tool).is_file(), f"{tool} is not installed in this environment"


def test_a_c_compiler_this_module_builds_with_exists() -> None:
    """The fourth tool, which the three above left out.

    Every test here configures and builds, so cmake needs a C compiler; without one the first
    ``configure()`` fails inside its own assertion and prints cmake's whole output, which
    says what is missing somewhere in forty lines. ``compiler()`` picks MinGW's gcc when MSVC
    is not set up and otherwise leaves the choice to cmake, so either one being on the path
    is what this module needs.
    """
    assert shutil.which("cl") or shutil.which("gcc"), (
        "no C compiler on the path: cmake needs one to configure, and every test in this "
        "module configures. Install MinGW's gcc or run from an MSVC developer shell"
    )
