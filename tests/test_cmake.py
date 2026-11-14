"""The CMake module, configured and built rather than read.

``cmake/Ddd.cmake`` is the largest piece of DDD that no unit test can reach: it is CMake code,
and everything else in this suite that touches it checks what the file says, not what it does.
So it is run here, with the ``cmake`` the development requirements install, over the shipped
example and over small projects written into the temporary directory - one collecting its
components through the link graph and naming a plugin with ``PLUGINS``, one handing the tool a
hand-written project description that names its own plugin, and several written to exercise
one keyword each. What is asserted is what a build would see: the files the generation writes,
the project description the module assembles, the schemas it closes over the plugins, a
rebuild that notices an edited plugin, and what the build after an edit compiles and what the
image it links then reads.

A configure and a build cost seconds each, and this file is a third of the suite's runtime,
so a class whose tests ask several questions of one tree configures and builds it once in a
class-scoped fixture and hands each test what that left behind. A class whose tests need
different calls, or that edit the tree and build again, keeps a tree per test - which is what
the ``tmp_path`` ones below are.

Not skipped when ``cmake`` is missing: it comes from ``requirements-dev.txt``, and a test that
skips when a tool is absent reports success without having run. The generator is ninja, from
the same requirements: the module refuses a multi-config generator, which is what cmake
defaults to on Windows, and a compiler is named explicitly where ``cl`` is not on the path,
which is a GitHub runner with MinGW's ``gcc`` and no developer prompt. The story of the build
after an edit is told under the platform's Makefile generator as well, with a ``make`` no
requirements file installs: GNU make on Linux, and MinGW's ``mingw32-make`` beside that ``gcc``
on Windows.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
from build_address_fixtures import ORACLE, PROJECT, SYMBOLS, addresses_of, oracle_of, root_of

from conftest import EXAMPLES, declare
from ddd import __version__
from test_cli import NO_ADDRESS_SOURCE, a2l_addresses

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


def cmake(*arguments: str, cwd: Path, site: Path | None = None) -> subprocess.CompletedProcess[str]:
    """One cmake invocation, its output kept for the failure message. ``site`` is a directory
    the tool may import modules from, as an installed plugin is."""
    path = os.pathsep.join([str(ROOT / "src"), *([str(site)] if site else [])])
    env = {**os.environ, "PYTHONPATH": path, "PYTHONUTF8": "1"}
    return subprocess.run(
        [CMAKE, *arguments], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


MAKE = "MinGW Makefiles" if os.name == "nt" else "Unix Makefiles"
"""The platform's Makefile generator, which the module takes like any single-config one."""


def make_program() -> str:
    """The ``make`` that :data:`MAKE` runs: ``mingw32-make`` on Windows, from the MinGW whose
    ``gcc`` the suite compiles with there, else ``make``; its bare name where none is found,
    which :func:`test_the_tools_this_module_runs_exist` then names as missing."""
    name = "mingw32-make" if os.name == "nt" else "make"
    gcc = shutil.which("gcc")
    beside = shutil.which(name, path=str(Path(gcc).parent)) if gcc else None
    return beside or shutil.which(name) or name


MAKE_PROGRAMS = {"Ninja": NINJA, MAKE: make_program()}
"""The build tool each generator the suite configures with runs, by the generator's name."""

TO_THE_SECOND = {MAKE} if os.name == "nt" else set()
"""The generators whose build tool may compare files' times to the whole second - a ``make``
built for Windows - to which a file edited in the second a build ended is no newer than what
that build wrote, nor a header the next build writes than the object the last one compiled
from it. A :class:`Story` sets its whole tree back after each of their builds (:func:`set_back`)
rather than wait for the clock to leave that second."""

SET_BACK_NS = 2_000_000_000
"""How far :func:`set_back` moves every file back: two whole seconds, so that what is written
next is newer to the second, even on a filesystem keeping times to two seconds."""


def set_back(root: Path) -> None:
    """Every file below ``root`` older by :data:`SET_BACK_NS`, each by the same amount, so that
    their order - which a build reads - is kept, and what is written next, by the test or by the
    build after, is newer than all of them to the second."""
    for path in root.rglob("*"):
        if path.is_file():
            times = path.stat()
            os.utime(path, ns=(times.st_atime_ns - SET_BACK_NS, times.st_mtime_ns - SET_BACK_NS))


def attempt(
    source: Path,
    build: Path,
    *definitions: str,
    generator: str = "Ninja",
    site: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """One configure, whether or not it is expected to succeed."""
    return cmake(
        "-S",
        str(source),
        "-B",
        str(build),
        "-G",
        generator,
        f"-DCMAKE_MAKE_PROGRAM={MAKE_PROGRAMS[generator]}",
        f"-DDDD_EXECUTABLE={DDD.as_posix()}",
        *compiler(),
        *definitions,
        cwd=source,
        site=site,
    )


def configure(
    source: Path, build: Path, *definitions: str, generator: str = "Ninja"
) -> subprocess.CompletedProcess[str]:
    run = attempt(source, build, *definitions, generator=generator)
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


def address_map_recipe(image: str) -> tuple[str, str]:
    """The build page's address map recipe, for ``image`` where the page writes
    ``firmware.elf``: what comes before the ``ddd_generate`` call, which names the map, and the
    step after the link that extracts it, running the page's ``cmake/AddressMap.cmake``."""
    recipe = documented_block("set(address_map")
    assert 'ADDRESS_MAP "${address_map}"' in recipe, "the page no longer names the map so"
    before = recipe.split("ddd_generate(")[0]
    step = "add_custom_command(" + recipe.split("add_custom_command(", 1)[1]
    return before.replace("firmware.elf", image), step.replace("firmware.elf", image)


def based_low(image: str) -> str:
    """The link options basing ``image`` where a 32 bit ``ECU_ADDRESS`` holds its addresses.

    A 64 bit image is based above 4 GB - 0x140000000 on Windows, and wherever the loader cares
    to put a position independent executable on linux - which no ECU_ADDRESS holds; an
    embedded image is not, and it is an embedded image the a2l describes. A GNU toolchain from
    end to end, since the recipe reads the nm of binutils as the page says, but the option is
    the object format's rather than the toolchain's: `ld` writing PE takes a base to write at,
    `ld` writing ELF places a non relocatable executable at 0x400000 on its own and has no
    `--image-base` at all.
    """
    return (
        "if(WIN32 AND NOT MSVC)\n"
        f'    target_link_options({image} PRIVATE "-Wl,--image-base,0x400000")\n'
        "elseif(NOT MSVC)\n"
        f'    target_link_options({image} PRIVATE "-no-pie")\n'
        "endif()\n"
    )


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

    ``ddd generate`` wrote what it rendered and removed nothing, and the module declares the
    headers of the components an image links as it finds them when configured - so once a
    component is dropped from ``target_link_libraries`` and the configure has run again,
    nothing declares its header any more. It stayed in the output directory, on the include
    path of every component, and a translation unit went on compiling against the interface
    of a component the image no longer links. ``ninja -t clean`` did not take it either.
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
        """``ninja -t clean`` removes the files the module declares, and the configure ninja
        runs before it no longer declares the header of the component that left: the clean
        leaves that header, so the record of it has to survive the clean too - which it does,
        being declared by nothing."""
        assert dropped.cleaned == (True, False), (
            "a clean either took the header of the component that left, or left the outputs "
            "the module declares"
        )
        assert not (dropped.generated / "EventLogger.h").exists(), "the generation after it"
        assert (dropped.generated / "ddd_globals.c").is_file()


STORY_GENERATORS = ["Ninja", MAKE]
"""The generators the story of the build after an edit is told under: ninja, which restats
what a step wrote, and the platform's make, which has nothing of the kind."""

Linked = Literal[
    "before the call", "after the call", "from the parent", "through a library defined later"
]
"""Where the image of a :class:`Story` is linked to its components (``Shape.linked``)."""


@dataclass(frozen=True)
class Shape:
    """How a :class:`Story` hands the module its components, a field for each way it can differ.

    A case a later edit needs - a plugin a project names, an include that is a wildcard - is one
    more value of a field rather than one more branch of the listing.
    """

    project: bool = False
    """A hand written project lists the components (``PROJECT``); otherwise they are collected
    from the link graph."""

    registered: bool = True
    """The components register their descriptions on their targets, which collecting them
    needs; a hand written project may do without, linking the headers into its libraries
    itself."""

    spare_linked: bool = False
    """The image links ``spare`` as well, a component a hand written project may leave out."""

    subdirectory: bool = False
    """The image is defined and generated in ``app/``, which the top directory adds once the
    components are defined; the two late links below put it there too."""

    linked: Linked = "before the call"
    """Where the image is linked to ``bundle``: before or after the call, in the directory
    calling ``ddd_generate``; from the parent, the top directory linking it once ``app/`` is
    done; or through a library defined later, the image linking in ``app/`` a ``platform`` the
    top directory defines afterwards."""

    described_by_the_build: bool = False
    """The logger's description is copied into the build tree by the build, so it is not there
    when the build is first configured."""

    units_by_the_build: bool = False
    """The device's units file is copied into the build tree by the build, as the logger's
    description is above: a vocabulary the first configure cannot read."""

    registered_late: bool = False
    """The top directory registers the components once the directory generating the image is
    done, the image linking them in time."""

    traced: Literal["", "before the image", "after the image"] = ""
    """The image links ``trace`` in a build with debug information alone,
    ``$<$<CONFIG:Debug,RelWithDebInfo>:trace>``: a component the top directory defines and
    registers before it adds ``app/``, or once ``app/`` is done."""

    build_type: str = ""
    """``CMAKE_BUILD_TYPE``, which a ``$<CONFIG:...>`` link is read for; none where empty."""

    own_templates: bool = False
    """The story copies the shipped templates into ``templates/`` and generates from that copy,
    which a test may then edit."""

    includes: tuple[str, ...] = (
        "components/sensor.ddd.json",
        "components/logger.ddd.json",
        "components/units.ddd.json",
    )
    """What a hand written project includes, relative to it: the image's components, which live
    in ``components/`` apart from every other description a pattern could match."""

    plugins: tuple[str, ...] = ()
    """The plugins of the project, a ``.py`` spec relative to the source directory: given with
    ``PLUGINS`` when collected, written into its ``plugins`` when hand written."""

    logger_file: str = "logger.ddd.json"
    """The name of the logger's description in ``components/``, whose case the tool does not
    mind - though ``ddd_add_component`` does, so only a hand written project spells it
    otherwise."""

    address_map: bool = False
    """The a2l takes its addresses from ``ADDRESS_MAP``, the map the build page's recipe extracts
    from the image once it is linked, the image based where an ``ECU_ADDRESS`` holds them."""

    severity: tuple[str, ...] = ()
    """``SEVERITY`` is given, each ``check=level`` of it."""

    strict: bool = False
    """``STRICT`` is given, so that a warning stops the build - ``address-missing`` among them."""

    copied: str = ""
    """The image property - ``DDD_DICTIONARY``, ``DDD_A2L`` - naming a generated file a step of
    the project copies to ``copied`` beside the image, depending on the file by its path alone,
    for a target ``copy`` built by default."""

    def in_a_subdirectory(self) -> bool:
        """Whether the image is defined and generated in ``app/`` rather than at the top."""
        return self.subdirectory or self.linked in (
            "from the parent",
            "through a library defined later",
        )


STORY_SHAPES = {
    "collected": Shape(),
    "linked after the call": Shape(linked="after the call"),
    "in a subdirectory": Shape(subdirectory=True),
    "project": Shape(project=True, registered=False),
}
"""The shapes the whole story is told for, under the names their tests are listed by."""

IN_CAPITALS = Shape(
    project=True,
    registered=False,
    logger_file="logger.DDD.JSON",
    includes=(
        "components/sensor.ddd.json",
        "components/logger.DDD.JSON",
        "components/units.ddd.json",
    ),
)
"""A hand written project whose logger's description is spelled in capitals, as a project kept
on a filesystem that does not mind may have it."""

LINKING_MORE_THAN_IT_NAMES = Shape(project=True, spare_linked=True)
"""A hand written project whose components register too, for their own check targets, and
whose image links one the project leaves out."""

DESCRIBED_BY_THE_BUILD = Shape(described_by_the_build=True)
"""Collected, with the logger's description written by the build."""

UNITS_BY_THE_BUILD = Shape(units_by_the_build=True)
"""Collected, with the device's units file written by the build."""

LINKED_LATE = {
    "from the parent": Shape(linked="from the parent"),
    "through a library defined later": Shape(linked="through a library defined later"),
}
"""The shapes whose image reaches its components only once the directory generating it is done."""

REGISTERED_LATE = Shape(subdirectory=True, registered_late=True)
"""The image generated in ``app/``, linked in time, its components registered once ``app/`` is
done."""

TRACE_C = "int trace(void);\n\nint trace(void)\n{\n    return 0;\n}\n"
"""The traced component's code, which reads no generated header."""

MAPPED = Shape(address_map=True, strict=True)
"""Collected, under ``STRICT``, the a2l's addresses read out of the map the page's recipe
extracts after the link."""

COMPILED = re.compile(r"Building C object \S*?(\w+\.c)\.o(?:bj)?\b")
"""A compile in a build's log, read back as the c file compiled, whichever generator wrote it."""

SENSOR_C = """#include "Sensor.h"

void sensor_step(void);

void sensor_step(void)
{{
    Sample = {value}u;
}}
"""
"""The writer, whose stored value is the edit a story makes to the c."""

LOGGER_C = """#include "Logger.h"

unsigned long logger_reads(void);

unsigned long logger_reads(void)
{
    return (unsigned long)Sample;
}
"""
"""The reader, never edited: it reads what its header said when it was last compiled."""

STORY_MAIN = """#include <stdio.h>

void sensor_step(void);
unsigned long logger_reads(void);

int main(void)
{
    sensor_step();
    printf("logged %lu\\n", logger_reads());
    return 0;
}
"""

STORY_UNITS = {"units": [{"unit": "rpm", "description": "rotational speed"}]}
"""The device's vocabulary: registered, read by the generation, and naming no component."""


@dataclass(frozen=True)
class Step:
    """One build of a :class:`Story`, and what the image it left behind printed."""

    code: int
    output: str
    compiled: frozenset[str]
    """The c files the build compiled, by name: ``logger.c`` for its object, ``.o`` or ``.obj``."""

    printed: str
    """What the image printed when run after the build, or nothing where the build failed."""

    def generated(self) -> bool:
        return "Generating the data dictionary" in self.output

    def did_nothing(self) -> bool:
        """Nothing configured, generated, compiled, linked or read after the link, and a build
        that succeeded: one with nothing to do, read off what it did rather than off the words
        one build tool has for that. A build whose CMake re-run failed prints ``Configuring
        incomplete`` and compiles nothing, which is no build with nothing to do."""
        return (
            self.code == 0
            and "Configuring done" not in self.output
            and not self.generated()
            and not self.compiled
            and "Linking" not in self.output
            and "Reading the addresses of the a2l" not in self.output
        )


class Story:
    """``Sensor`` writes ``Sample`` and ``Logger`` reads it, in an image printing what it read.

    The link graph has every kind of edge the components of an image are found through: the
    image links ``bundle``, an interface library carrying the device's units, which links the
    sensor by its alias ``story::writer``; the sensor links the logger privately, which a
    static library passes on as ``$<LINK_ONLY:logger>``; and the logger links the sensor back
    by its own name, so the two use each other and the sensor is met under two names.
    ``Spare`` is registered and, unless the shape says otherwise, linked by no image, as the
    component of another image is. The image's components are described in ``components/``,
    ``Spare`` beside it.

    The :class:`Shape` is how the module is handed the components. A build is read back as a
    :class:`Step`, and the image is run after it, so that what the reader was compiled against
    is asked of the image rather than of the build's log.
    """

    def __init__(
        self, root: Path, shape: Shape, generator: str, *, configured: bool = True
    ) -> None:
        self.source = root
        self.site: Path | None = None
        """A directory the tool imports plugins from by their module name, where there is one."""
        self.components = root / "components"
        self.build_dir = root / "build"
        self.shape = shape
        self.generator = generator
        self.components.mkdir(parents=True, exist_ok=True)
        self.describe("uint8")
        self.write_sensor(200)
        (root / "logger.c").write_text(LOGGER_C, encoding="utf-8")
        (root / "spare.c").write_text("int spare(void) { return 0; }\n", encoding="utf-8")
        spare = {"component": {"name": "Spare", "interface": [declare("local", "SpareCount")]}}
        (root / "spare.ddd.json").write_text(json.dumps(spare, indent=2), encoding="utf-8")
        units = self.components / "units.ddd.json"
        units.write_text(json.dumps(STORY_UNITS, indent=2), encoding="utf-8")
        if shape.own_templates:
            shutil.copytree(TEMPLATES, root / "templates")
        if shape.traced:
            (root / "trace.c").write_text(TRACE_C, encoding="utf-8")
            trace = {"component": {"name": "Trace", "interface": [declare("local", "Traces")]}}
            (root / "trace.ddd.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        if shape.project:
            project = {"project": {"name": "StoryDevice", "includes": list(shape.includes)}}
            if shape.plugins:
                project["project"]["plugins"] = list(shape.plugins)
            (root / "project.ddd.json").write_text(json.dumps(project), encoding="utf-8")
        images = root / "app" if shape.in_a_subdirectory() else root
        images.mkdir(exist_ok=True)
        (images / "main.c").write_text(STORY_MAIN, encoding="utf-8")
        if shape.address_map:
            (images / "cmake").mkdir()
            (images / "cmake" / "AddressMap.cmake").write_text(
                documented_block("# cmake/AddressMap.cmake"), encoding="utf-8"
            )
        if shape.in_a_subdirectory():
            (images / "CMakeLists.txt").write_text(self.image(), encoding="utf-8")
        (root / "CMakeLists.txt").write_text(self.listing(), encoding="utf-8")
        self.configured = self.reconfigure() if configured else ""
        """What the first configure printed, unless the story was written to be configured by
        the test, with :meth:`attempt`."""

    def generation(self) -> str:
        """The ``ddd_generate`` call, and the links a hand written project makes after it."""
        templates = f'TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"'
        if self.shape.own_templates:
            templates = 'TEMPLATE_DIRECTORY "${CMAKE_SOURCE_DIR}/templates"'
        if self.shape.address_map:
            templates += ' ADDRESS_MAP "${address_map}"'
        if self.shape.strict:
            templates += " STRICT"
        if self.shape.severity:
            templates += f" SEVERITY {' '.join(self.shape.severity)}"
        if self.shape.project:
            generation = (
                f'ddd_generate(img PROJECT "${{CMAKE_SOURCE_DIR}}/project.ddd.json" {templates})\n'
            )
            if self.shape.registered:
                return generation
            return (
                f"{generation}"
                "target_link_libraries(sensor PRIVATE img_ddd_headers)\n"
                "target_link_libraries(logger PRIVATE img_ddd_headers)\n"
            )
        plugins = "".join(f' "${{CMAKE_SOURCE_DIR}}/{spec}"' for spec in self.shape.plugins)
        plugins = f" PLUGINS{plugins}" if plugins else ""
        return f"ddd_generate(img NAME StoryDevice {templates}{plugins})\n"

    def registrations(self) -> str:
        """Each component's description on its target, where the shape registers them; the
        logger's, and the units file, are written by the build where it says so."""
        if not self.shape.registered:
            return ""
        here = "${CMAKE_CURRENT_SOURCE_DIR}"
        logger = f'"{here}/components/{self.shape.logger_file}"'
        units = f'"{here}/components/units.ddd.json"'
        written = ""
        if self.shape.described_by_the_build:
            copied, logger = logger, '"${CMAKE_CURRENT_BINARY_DIR}/logger.ddd.json"'
            written += self.written_by_the_build(copied, logger)
        if self.shape.units_by_the_build:
            copied, units = units, '"${CMAKE_CURRENT_BINARY_DIR}/units.ddd.json"'
            written += self.written_by_the_build(copied, units)
        return (
            f"{written}"
            f'ddd_add_component(sensor JSON "{here}/components/sensor.ddd.json")\n'
            f"ddd_add_component(logger JSON {logger})\n"
            f"ddd_add_component(bundle JSON {units})\n"
            f'ddd_add_component(spare JSON "{here}/spare.ddd.json")\n'
        )

    @staticmethod
    def written_by_the_build(copied: str, written: str) -> str:
        """The step of the build copying a description into the build tree."""
        return (
            f"add_custom_command(OUTPUT {written}\n"
            f'                   COMMAND "${{CMAKE_COMMAND}}" -E copy {copied} {written}\n'
            f"                   DEPENDS {copied}\n"
            "                   VERBATIM)\n"
        )

    def image(self) -> str:
        """Where the image is defined, linked and generated, in the order the shape says, and
        the page's recipe around the call where the a2l takes its addresses from a map."""
        linked = self.shape.linked
        spare = " spare" if self.shape.spare_linked else ""
        link = {
            "from the parent": "",
            "through a library defined later": "target_link_libraries(img PRIVATE platform)\n",
        }.get(linked, f"target_link_libraries(img PRIVATE bundle{spare})\n")
        if self.shape.traced:
            link += 'target_link_libraries(img PRIVATE "$<$<CONFIG:Debug,RelWithDebInfo>:trace>")\n'
        calls = [link, self.generation()]
        before, after = "", ""
        if self.shape.address_map:
            before, step = address_map_recipe("img")
            after = step + based_low("img")
        if self.shape.copied:
            copy = "${CMAKE_CURRENT_BINARY_DIR}/copied"
            after += (
                f"get_target_property(generated img {self.shape.copied})\n"
                f'add_custom_command(OUTPUT "{copy}"\n'
                '                   COMMAND "${CMAKE_COMMAND}" -E copy "${generated}"\n'
                f'                           "{copy}"\n'
                '                   DEPENDS "${generated}"\n'
                "                   VERBATIM)\n"
                f'add_custom_target(copy ALL DEPENDS "{copy}")\n'
            )
        return (
            "add_executable(img main.c)\n"
            + before
            + "".join(reversed(calls) if linked == "after the call" else calls)
            + after
        )

    def listing(self) -> str:
        """The top directory's ``CMakeLists.txt``: the components, then the image or the
        subdirectory defining it, and whatever the top directory links, defines or registers
        once that is done."""
        image = self.image()
        if self.shape.in_a_subdirectory():
            image = "add_subdirectory(app)\n" + {
                "from the parent": "target_link_libraries(img PRIVATE bundle)\n",
                "through a library defined later": (
                    "add_library(platform INTERFACE)\n"
                    "target_link_libraries(platform INTERFACE bundle)\n"
                ),
            }.get(self.shape.linked, "")
        registrations = self.registrations()
        if self.shape.registered_late:
            image, registrations = image + registrations, ""
        trace = (
            "add_library(trace STATIC trace.c)\n"
            'ddd_add_component(trace JSON "${CMAKE_CURRENT_SOURCE_DIR}/trace.ddd.json")\n'
        )
        if self.shape.traced == "before the image":
            image = trace + image
        elif self.shape.traced == "after the image":
            image += trace
        return f"""cmake_minimum_required(VERSION 3.30)
project(Story LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(sensor STATIC sensor.c)
add_library(story::writer ALIAS sensor)
add_library(logger STATIC logger.c)
target_link_libraries(sensor PRIVATE logger)
target_link_libraries(logger PRIVATE sensor)
add_library(bundle INTERFACE)
target_link_libraries(bundle INTERFACE story::writer)
add_library(spare STATIC spare.c)
{registrations}{image}"""

    def reshape(self, shape: Shape) -> None:
        """The project's ``CMakeLists.txt`` rewritten for another shape of the same layout, as
        a developer edits it: the build that follows configures again."""
        self.shape = shape
        if shape.in_a_subdirectory():
            (self.source / "app" / "CMakeLists.txt").write_text(self.image(), encoding="utf-8")
        (self.source / "CMakeLists.txt").write_text(self.listing(), encoding="utf-8")

    def description(self, name: str) -> Path:
        """Where the description of ``name``, ``"sensor"`` or ``"logger"``, is written."""
        return self.components / (
            self.shape.logger_file if name == "logger" else f"{name}.ddd.json"
        )

    def describe(self, datatype: str, *more: dict[str, Any]) -> None:
        """Both descriptions, ``Sample`` of ``datatype`` in each, and whatever more the sensor
        declares beside it. A description this leaves as it was is not written at all."""
        for name, scope, extra in (("Sensor", "output", more), ("Logger", "input", ())):
            described = {
                "component": {
                    "name": name,
                    "interface": [declare(scope, "Sample", datatype), *extra],
                }
            }
            path = self.description(name.lower())
            text = json.dumps(described, indent=2)
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                path.write_text(text, encoding="utf-8")

    def write_sensor(self, value: int) -> None:
        (self.source / "sensor.c").write_text(SENSOR_C.format(value=value), encoding="utf-8")

    def write_plugin(self, source: str) -> None:
        """The project's plugin, ``plug.py``, as the source says."""
        (self.source / "plug.py").write_text(source, encoding="utf-8")

    def attempt(self) -> subprocess.CompletedProcess[str]:
        """A configure of the tree, whether or not it is expected to succeed."""
        build_type = (
            [f"-DCMAKE_BUILD_TYPE={self.shape.build_type}"] if self.shape.build_type else []
        )
        return attempt(
            self.source, self.build_dir, *build_type, generator=self.generator, site=self.site
        )

    def reconfigure(self) -> str:
        """Configures the tree again, and answers with what the configure printed."""
        run = self.attempt()
        assert run.returncode == 0, run.stdout + run.stderr
        return run.stdout + run.stderr

    def images(self) -> Path:
        """The build directory the image is linked into, and generated in."""
        return self.build_dir / "app" if self.shape.in_a_subdirectory() else self.build_dir

    def image_file(self) -> Path:
        return self.images() / ("img.exe" if os.name == "nt" else "img")

    def a2l(self) -> str:
        """The a2l as the last build left it."""
        return (self.images() / "ddd" / "img" / "StoryDevice.a2l").read_text(encoding="utf-8")

    def placed(self) -> dict[str, int]:
        """Where the image the last build linked has each record of the a2l, as ``nm`` reads it
        - never through the map the build extracted, nor through DDD's reader."""
        found = addresses_of(self.image_file())
        return {symbol: found[symbol] for symbol in a2l_addresses(self.a2l())}

    def build(self) -> Step:
        run = self.build_target()
        output = run.stdout + run.stderr
        printed = ""
        if run.returncode == 0:
            image = self.image_file()
            shown = subprocess.run([str(image)], capture_output=True, text=True, check=False)
            assert shown.returncode == 0, shown.stdout + shown.stderr
            printed = shown.stdout.strip()
        return Step(run.returncode, output, frozenset(COMPILED.findall(output)), printed)

    def build_target(self, *targets: str) -> subprocess.CompletedProcess[str]:
        """One build, of the targets named or of everything, whether or not it succeeds; where
        the build tool reads times to the second, the tree is set back before the test edits
        anything (:data:`TO_THE_SECOND`)."""
        target = ["--target", *targets] if targets else []
        run = cmake("--build", str(self.build_dir), *target, cwd=self.build_dir, site=self.site)
        if self.generator in TO_THE_SECOND:
            set_back(self.source)
        return run


@dataclass(frozen=True)
class AfterAnEdit:
    """What the builds of one story left behind, in order, for the class below to read."""

    widened: Step
    """``Sample`` widened from ``uint8`` to ``uint16`` in both descriptions, the writer storing
    1234, which a byte cannot hold."""

    settled: Step
    """The build after it, nothing touched."""

    elsewhere: Step
    """``Sensor`` given a local of its own, which ``Logger.h`` does not show."""


class TestTheBuildAfterAnEdit:
    """Review focus 5: a build after an edit rebuilds what the edit changed, and no more.

    The object of a component reading a generated header waited for the generation and did
    not depend on what it rewrote, since the module declared no per-component header: ninja
    looks at every input before it runs anything, so the build after a datatype change
    compiled the writer and the definitions, relinked, and kept the reader compiled for the
    old type - exit 0, and only the build after that one compiled the reader again. Both
    modes, an image linked after the call that generates it, which is the link graph the
    module can only read once the directory is done, and an image generated in a directory of
    its own; and an image reaching its components only once that directory is done, which the
    configure refuses.
    """

    @pytest.fixture(
        scope="class",
        params=[
            pytest.param((shape, generator), id=f"{name}, {generator}")
            for name, shape in STORY_SHAPES.items()
            for generator in STORY_GENERATORS
        ],
    )
    @staticmethod
    def edited(
        request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
    ) -> AfterAnEdit:
        """One story per shape and generator: build, widen, build twice, edit the writer's
        description alone, build."""
        shape, generator = request.param
        story = Story(tmp_path_factory.mktemp("story"), shape, generator)
        first = story.build()
        assert first.code == 0 and first.printed == "logged 200", first.output
        story.describe("uint16")
        story.write_sensor(1234)
        widened = story.build()
        settled = story.build()
        story.describe("uint16", declare("local", "Ticks", "uint16"))
        return AfterAnEdit(widened, settled, story.build())

    def test_a_datatype_widened_in_both_descriptions_reaches_the_reader_in_one_build(
        self, edited: AfterAnEdit
    ) -> None:
        """``logger.c`` is not edited and has to be compiled again all the same, its header
        having changed: compiled against the old one, it reads the low byte of 1234."""
        widened = edited.widened
        assert widened.code == 0, widened.output
        assert "logger.c" in widened.compiled, widened.output
        assert widened.printed == "logged 1234"

    def test_the_build_after_it_has_nothing_to_do(self, edited: AfterAnEdit) -> None:
        """Every header the generation writes is one it declares, and the other way round: a
        header declared and never written - the one of a component another image links, say -
        is a generation at every build."""
        assert edited.settled.did_nothing(), edited.settled.output

    def test_an_edit_the_readers_header_does_not_show_recompiles_the_writer_alone(
        self, edited: AfterAnEdit
    ) -> None:
        """A local of ``Sensor`` rewrites ``Sensor.h`` and the definitions, and leaves
        ``Logger.h`` as it was, so ``sensor.c`` is compiled again, without an edit of its own,
        and ``logger.c`` is not: the granularity the generated headers are written for."""
        elsewhere = edited.elsewhere
        assert elsewhere.code == 0, elsewhere.output
        assert {"sensor.c", "ddd_globals.c"} <= elsewhere.compiled, elsewhere.output
        assert "logger.c" not in elsewhere.compiled, elsewhere.output

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_description_touched_and_left_as_it_was_runs_the_generation_once(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A run that changes nothing leaves every file it would write as it was. Ninja looks
        at them again after the run and finds nothing to do; make has nothing of the kind, so
        the first file of the generation stayed older than the description, and every build
        after ran the whole analysis again - while CMake touched each other file of it after
        each run, ``ddd_types.h`` among them, and every component compiled again."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        os.utime(story.description("sensor"))
        touched = story.build()
        assert touched.code == 0 and touched.generated(), touched.output
        assert not touched.compiled, touched.output
        assert story.build().did_nothing()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_file_of_the_generation_deleted_by_hand_is_written_again(
        self, tmp_path: Path, generator: str
    ) -> None:
        """Ninja makes a declared file that is missing. Make, with a stamp the step's one output,
        does not: every build stops on the file until the stamp goes, and the rule of the file's
        own claims to generate nothing in the meantime. Deleting the stamp is the way back."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        generated = story.images() / "ddd" / "img"
        (generated / "ddd_globals.c").unlink()
        deleted = story.build()
        if generator == "Ninja":
            assert deleted.code == 0 and deleted.generated(), deleted.output
        else:
            assert deleted.code != 0, deleted.output
            assert "Generating ddd/img/ddd_globals.c" not in deleted.output, deleted.output
            assert story.build().code != 0
            (generated / "ddd-generation.stamp").unlink()
            assert story.build().printed == "logged 200"
        assert (generated / "ddd_globals.c").is_file()

    @pytest.mark.parametrize(
        "shape",
        [
            pytest.param(Shape(copied="DDD_DICTIONARY"), id="the dictionary"),
            pytest.param(
                Shape(address_map=True, strict=True, copied="DDD_A2L"),
                id="the a2l written after the link",
            ),
        ],
    )
    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_step_reading_a_generated_file_by_its_path_reads_it_fresh(
        self, tmp_path: Path, generator: str, shape: Shape
    ) -> None:
        """A step of the project depending on a file of the generation by its path alone - the
        copy of the dictionary a delivery archives, say. Under make the file was the output of
        no rule once a stamp was the step's: in a fresh tree the step had nothing to make it
        with, and after an edit it copied the file the build before had left."""
        story = Story(tmp_path, shape, generator)
        copied = story.images() / "copied"
        first = story.build_target("copy")
        assert first.returncode == 0, first.stdout + first.stderr
        assert "Sample" in copied.read_text(encoding="utf-8")
        story.describe("uint8", declare("local", "Fresh"))
        again = story.build_target("copy")
        assert again.returncode == 0, again.stdout + again.stderr
        assert "Fresh" in copied.read_text(encoding="utf-8")

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_component_registered_after_the_directory_is_done_is_refused_as_such(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The image links its components in time, and the top directory registers them only
        once the directory generating it is done: no link was made late, and no library defined
        late, so the refusal names what did come late."""
        run = Story(tmp_path, REGISTERED_LATE, generator, configured=False).attempt()
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "through a link made" not in said, said
        assert (
            'ddd_generate: the component(s) "Logger", "Sensor" of "img" were registered after '
            f'"{(tmp_path / "app").as_posix()}" - where ddd_generate() is called - was done, on '
            "targets the image links in time. Their headers are not declared as outputs of the "
            "generation, so the build after one of them changed would compile the components "
            "reading it against the old one. Register the image's components before "
            "ddd_generate() is called, which is also what hands them its headers."
        ) in said

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_link_for_another_build_type_is_no_late_link(
        self, tmp_path: Path, generator: str
    ) -> None:
        """``$<$<CONFIG:Debug,RelWithDebInfo>:trace>``, with ``trace`` defined once ``app/`` is
        done: a Release image does not link it, as CMake reads the link for the one build type a
        single-config generator has, and the module reads it so too. It was taken whatever its
        condition, and the Release configure refused a component its image does not link."""
        shape = Shape(subdirectory=True, traced="after the image", build_type="Release")
        story = Story(tmp_path, shape, generator)
        assert story.build().printed == "logged 200"
        assert story.build().did_nothing()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_link_for_this_build_type_made_late_is_refused_saying_how_links_are_read(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The same link in a Debug configure is one the image makes, through a library defined
        late, and is refused; the refusal says how a link behind an expression is read."""
        shape = Shape(subdirectory=True, traced="after the image", build_type="Debug")
        run = Story(tmp_path, shape, generator, configured=False).attempt()
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert 'reaches the component(s) "Trace" through a link made' in said, said
        assert (
            "A link behind a generator expression is taken whatever the expression comes to, "
            "the names being read when the build is configured, before CMake evaluates any; one "
            "behind $<CONFIG:...> alone is read for the CMAKE_BUILD_TYPE configured."
        ) in said

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_link_for_another_build_type_declares_no_header(
        self, tmp_path: Path, generator: str
    ) -> None:
        """With ``trace`` defined in time, the Release generation declared ``Trace.h``, which it
        never writes, the image not linking ``trace``: under ninja a byproduct missing after the
        run is one to make, so the generation ran at every build."""
        shape = Shape(subdirectory=True, traced="before the image", build_type="Release")
        story = Story(tmp_path, shape, generator)
        assert story.build().printed == "logged 200"
        assert story.build().did_nothing()

    @pytest.mark.parametrize(
        "shape", [pytest.param(shape, id=name) for name, shape in LINKED_LATE.items()]
    )
    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_component_reached_after_the_directory_is_done_stops_the_configure(
        self, tmp_path: Path, shape: Shape, generator: str
    ) -> None:
        """The components are named once the directory calling ``ddd_generate`` is done, and
        an image linked to them only after that - by the directory above, or through a library
        it defines later - reached none of them then: their headers would go undeclared, and
        the build after one of them changed would compile its reader against the old one. The
        configure stops instead, once the top directory is done, naming them."""
        run = Story(tmp_path, shape, generator, configured=False).attempt()
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert (
            'ddd_generate: "img" reaches the component(s) "Logger", "Sensor" through a link '
            f'made, or a library defined, after "{(tmp_path / "app").as_posix()}" - where '
            "ddd_generate() is called - was done. Their headers are not declared as "
            "outputs of the generation, so the build after one of them changed would compile "
            "the components reading it against the old one. Link the image's components, and "
            "define every library on the way to them, before that directory is done - or call "
            "ddd_generate() where they are."
        ) in said

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_hand_written_project_may_link_a_component_it_does_not_name(
        self, tmp_path: Path, generator: str
    ) -> None:
        """With ``PROJECT`` the components are the project's, whatever the image links, so the
        link graph is not asked about: a component registered for its own check target and
        linked, but left out of the project, is no late link, and the build after a change is
        right all the same."""
        story = Story(tmp_path, LINKING_MORE_THAN_IT_NAMES, generator)
        assert story.build().code == 0
        story.describe("uint16")
        story.write_sensor(1234)
        widened = story.build()
        assert widened.code == 0, widened.output
        assert widened.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_component_named_like_a_file_of_the_generation_is_refused_by_name(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A component named ``ddd_types`` has ``{component}.h.jinja2`` render ``ddd_types.h``,
        which ``ddd_types.h.jinja2`` renders too: ninja refused to load a build declaring that
        file twice, naming no component, and went on refusing once the description was put
        right, the build being one that could no longer configure itself again. The configure
        refuses it instead, naming the component and the template, and the build after the
        repair configures again by itself."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        spare = tmp_path / "spare.ddd.json"
        named = spare.read_text(encoding="utf-8")
        spare.write_text(named.replace('"Spare"', '"ddd_types"'), encoding="utf-8")
        story.reshape(Shape(spare_linked=True))
        refused = story.build()
        said = " ".join(refused.output.split())
        assert refused.code != 0, said
        assert (
            'ddd_generate: the component "ddd_types" of "img" would have "{component}.h.jinja2" '
            'render "ddd_types.h", which "ddd_types.h.jinja2" renders already: ninja refuses a '
            "build that declares one file twice. Rename the component, or one of the templates."
        ) in said
        spare.write_text(named, encoding="utf-8")
        assert story.build().code == 0

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_project_spelling_a_description_in_capitals_has_its_header_declared(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The names of a hand written project's components are read off the json files
        ``ddd sources`` lists, and the tool takes a description's suffix whatever its case, so
        the module does too: ``logger.DDD.JSON`` names ``Logger``, whose header is declared, and
        the widened ``Sample`` reaches its reader in one build."""
        story = Story(tmp_path, IN_CAPITALS, generator)
        assert story.build().code == 0
        story.describe("uint16")
        story.write_sensor(1234)
        widened = story.build()
        assert widened.code == 0, widened.output
        assert "logger.c" in widened.compiled, widened.output
        assert widened.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_description_unreadable_when_configured_is_read_after_its_repair(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A component's name is read when the build is configured, and a description that
        does not parse then - mid edit, or mid merge - names none: its header goes undeclared.
        The file is a dependency of the configure while it does not parse, so the build after
        its repair configures again, reads the name, and compiles the reader when the repair
        changed its header."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        story.description("logger").write_text("{ broken", encoding="utf-8")
        story.reconfigure()
        story.describe("uint16")
        story.write_sensor(1234)
        repaired = story.build()
        assert repaired.code == 0, repaired.output
        assert repaired.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_description_the_build_writes_is_named_by_the_configure_that_finds_it(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A description generated into the build tree is not there when the build is first
        configured, so it names no component yet, and no configure came by itself once the
        build had written it: under ninja, until somebody configured by hand, the build after
        its header changed compiled the reader against the old one. The file is watched now, so
        the build after the one that wrote it configures first, by itself, and names it."""
        story = Story(tmp_path, DESCRIBED_BY_THE_BUILD, generator)
        written = (story.build_dir / "logger.ddd.json").as_posix()
        said = " ".join(story.configured.split())
        assert "CMake Warning" not in said, said
        assert (
            f'-- ddd_add_component: "{written}" does not exist yet, so neither the component it '
            "may describe nor its kind can be read; the first build to find it there configures "
            "again, and reads both."
        ) in said
        assert story.build().code == 0
        story.describe("uint16")
        story.write_sensor(1234)
        widened = story.build()
        assert widened.code == 0, widened.output
        assert "Configuring done" in widened.output, widened.output
        assert widened.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_vocabulary_the_build_writes_is_not_checked_as_a_component(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A file that is not there yet says nothing about its kind, and was checked by its
        target's ``.ddd`` as a component - which a units file the build writes is not, a
        ``file-kind`` error until somebody configured again by hand. The configure that finds
        it now comes by itself, and reads it for a vocabulary, which is checked in context."""
        story = Story(tmp_path, UNITS_BY_THE_BUILD, generator)
        assert story.build().printed == "logged 200"
        checked = story.build_target("bundle.ddd")
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "file-kind" not in checked.stdout + checked.stderr

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_an_output_directory_deleted_is_written_again_by_the_build(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The output directory holds what the configure writes - the record of the build,
        and the project description collected out of the link graph - which no step of the
        build writes again: the build stopped on that description, missing and with no rule
        to make it, and nothing said that a configure would mend it. The record is watched,
        so the build configures again by itself, and generates the rest."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        output = story.images() / "ddd" / "img"
        shutil.rmtree(output)
        rebuilt = story.build()
        assert rebuilt.code == 0, rebuilt.output
        assert "Configuring done" in rebuilt.output, rebuilt.output
        assert rebuilt.printed == "logged 200"
        assert (output / "ddd-build.json").is_file()
        assert story.build().did_nothing()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_an_edited_vocabulary_file_runs_the_generation_and_no_configure(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A registered units file names no component and, unlike a description that does not
        parse, is no dependency of the configure step: its edit runs the generation, which
        reads it, and configures nothing again."""
        story = Story(tmp_path, STORY_SHAPES["collected"], generator)
        assert story.build().code == 0
        units = story.components / "units.ddd.json"
        text = units.read_text(encoding="utf-8")
        units.write_text(text.replace("speed", "speed, per minute"), encoding="utf-8")
        edited = story.build()
        assert edited.code == 0 and edited.generated(), edited.output
        assert "Configuring done" not in edited.output, edited.output


BANNER = '{% include "inc/banner.jinja2" %}\n'
"""What a template writes to include a helper kept in a subdirectory of the template directory."""


class TestTheTemplateDirectory:
    """What the module reads out of the template directory is what the tool renders from it.

    The templates were globbed as a pattern, so a checkout in ``pr[1]`` read its own directory
    as a character class and found no template in it; a helper below the directory, which
    jinja finds and a template includes, was no dependency, so its edit built to ``no work to
    do`` over the old text; and a template removed re-ran the configure and left the file it
    had rendered on the include path, nothing having changed that the generation depends on.
    """

    def story(self, root: Path, generator: str) -> Story:
        """A story generating from a copy of the shipped templates, unconfigured."""
        return Story(root, Shape(own_templates=True), generator, configured=False)

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_checkout_spelled_like_a_pattern_finds_its_templates(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The templates are found, the generation depends on them, so an edit of one of them
        regenerates, and the build after has nothing to do. The record in the output directory
        is watched by a glob of its own path, spelled as that path alone: read as a pattern, the
        glob would match nothing and watch nothing, and a deleted output directory stop the
        build under ninja, the project description missing with no rule to make it."""
        story = self.story(tmp_path / "pr[1]", generator)
        story.reconfigure()
        assert story.build().printed == "logged 200"
        assert story.build().did_nothing()
        definitions = tmp_path / "pr[1]" / "templates" / "ddd_globals.c.jinja2"
        definitions.write_text(
            definitions.read_text(encoding="utf-8") + "/* an edit of the template */\n", "utf-8"
        )
        edited = story.build()
        assert edited.code == 0 and edited.generated(), edited.output
        globals_c = story.images() / "ddd" / "img" / "ddd_globals.c"
        assert "an edit of the template" in globals_c.read_text(encoding="utf-8")
        shutil.rmtree(story.images() / "ddd" / "img")
        rebuilt = story.build()
        assert rebuilt.code == 0 and rebuilt.printed == "logged 200", rebuilt.output

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_helper_in_a_subdirectory_is_a_dependency_of_the_generation(
        self, tmp_path: Path, generator: str
    ) -> None:
        story = self.story(tmp_path, generator)
        templates = tmp_path / "templates"
        (templates / "inc").mkdir()
        helper = templates / "inc" / "banner.jinja2"
        helper.write_text("/* the first banner */\n", encoding="utf-8")
        definitions = templates / "ddd_globals.c.jinja2"
        definitions.write_text(BANNER + definitions.read_text(encoding="utf-8"), "utf-8")
        story.reconfigure()
        assert story.build().code == 0
        globals_c = story.images() / "ddd" / "img" / "ddd_globals.c"
        assert "the first banner" in globals_c.read_text(encoding="utf-8")
        helper.write_text("/* the second banner */\n", encoding="utf-8")
        edited = story.build()
        assert edited.code == 0 and edited.generated(), edited.output
        assert "the second banner" in globals_c.read_text(encoding="utf-8")
        assert story.build().did_nothing()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_template_removed_takes_the_file_it_rendered_with_it(
        self, tmp_path: Path, generator: str
    ) -> None:
        story = self.story(tmp_path, generator)
        extra = tmp_path / "templates" / "extra.h.jinja2"
        extra.write_text("/* rendered by a template the project removes */\n", "utf-8")
        story.reconfigure()
        assert story.build().code == 0
        rendered = story.images() / "ddd" / "img" / "extra.h"
        assert rendered.is_file()
        extra.unlink()
        removed = story.build()
        assert removed.code == 0 and removed.generated(), removed.output
        assert not rendered.exists(), "the file of a template removed stays on the include path"
        assert story.build().did_nothing()


WILDCARDS = {
    "a wildcard": (("components/*.ddd.json",), "components"),
    "a recursive wildcard": (("components/**/*.ddd.json",), "components/deeper/still"),
    "a wildcard of a sub-project, spelled in capitals, in a directory of its own": (
        ("parts/Sub.DDD.JSON",),
        "components",
    ),
    "an absolute wildcard": (("{root}/components/*.ddd.json",), "components"),
    "a wildcard spelled with the platform's separator": (
        (f"components{os.sep}*.ddd.json",),
        "components",
    ),
}
"""A hand written project including the descriptions of ``components/`` by a wildcard - its
own, a recursive one, or one of a project it includes - and the directory a file the wildcard
matches is written into. ``project.ddd.json`` and ``spare.ddd.json`` beside the components are
matched by none."""

STAMP_PLUGIN = """from __future__ import annotations

from pydantic import BaseModel, field_validator

from ddd.plugins import Plugin


class Stamp(BaseModel):
    tag: str

    @field_validator("tag")
    @classmethod
    def own_code(cls, value: str) -> str:
        {body}
        return value


PLUGIN = Plugin(name="stamp", object_model=Stamp)
"""
"""A plugin whose model validates the block ``Ticks`` carries; ``{body}`` is what its validator
does, and each edit of it is a different file."""

SYNTAX_ERROR = "def broken(:\n"

PLUGIN_PROJECT = Shape(project=True, registered=False, plugins=("plug.py",))
"""A hand written project naming a plugin of its own, which the story writes."""

MODULE_PROJECT = Shape(project=True, registered=False, plugins=("storypkg",))
"""A hand written project naming a plugin by its module name, a package the story writes."""

UNMATCHED = Shape(
    project=True,
    registered=False,
    includes=(*Shape().includes, "nothing/*.ddd.json"),
)
"""A hand written project with an include that matches no file: an ``include-empty`` finding."""

RELAXED = Shape(
    project=True,
    registered=False,
    includes=UNMATCHED.includes,
    severity=("include-empty=ignore",),
)
"""The same project, the call relaxing that check."""


def plugged(root: Path, generator: str, body: str = "pass") -> Story:
    """A story of ``PLUGIN_PROJECT`` whose component carries a block of the plugin ``plug.py``
    writes, so that the plugin's own model runs on a file of the project."""
    story = Story(root, PLUGIN_PROJECT, generator, configured=False)
    story.describe("uint8", declare("local", "Ticks", extensions={"stamp": {"tag": "t"}}))
    story.write_plugin(STAMP_PLUGIN.format(body=body))
    story.configured = story.reconfigure()
    return story


class TestAWildcardThatStartsOrStopsMatching:
    """A file an ``includes`` wildcard starts matching is a component of the project, and one
    it stops matching is not: the build that follows each says so. Both left the build with
    nothing to do while the wildcards went unwatched: the files watched were those the
    configure listed, a file created later was not among them, and a deletion left the
    generation with the same command and fewer inputs."""

    @pytest.mark.parametrize(
        ("includes", "directory"),
        [pytest.param(*case, id=name) for name, case in WILDCARDS.items()],
    )
    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_the_next_build_follows_the_file_in_and_out_of_the_match(
        self, tmp_path: Path, generator: str, includes: tuple[str, ...], directory: str
    ) -> None:
        includes = tuple(entry.format(root=tmp_path.as_posix()) for entry in includes)
        shape = Shape(project=True, registered=False, includes=includes)
        story = Story(tmp_path, shape, generator, configured=False)
        (tmp_path / "parts").mkdir()
        (tmp_path / "parts" / "Sub.DDD.JSON").write_text(
            json.dumps({"project": {"name": "Sub", "includes": ["../components/*.ddd.json"]}}),
            encoding="utf-8",
        )
        story.configured = story.reconfigure()
        assert story.build().code == 0
        # A configure finding the same files leaves the list alone, and the build nothing to do.
        story.reconfigure()
        assert story.build().did_nothing()
        globals_c = story.images() / "ddd" / "img" / "ddd_globals.c"
        assert "LateCount" not in globals_c.read_text(encoding="utf-8")
        late = tmp_path / directory / "late.ddd.json"
        late.parent.mkdir(parents=True, exist_ok=True)
        late.write_text(
            json.dumps(
                {"component": {"name": "Late", "interface": [declare("local", "LateCount")]}}
            ),
            encoding="utf-8",
        )
        started = story.build()
        assert started.code == 0 and started.generated(), started.output
        assert "LateCount" in globals_c.read_text(encoding="utf-8")
        assert story.build().did_nothing()
        late.unlink()
        stopped = story.build()
        assert stopped.code == 0 and stopped.generated(), stopped.output
        assert "LateCount" not in globals_c.read_text(encoding="utf-8")
        assert story.build().did_nothing()

    @pytest.mark.parametrize(
        ("pattern", "directory"),
        [
            pytest.param("components/*.ddd.json", "components", id="a wildcard"),
            pytest.param("components/**/*.ddd.json", "components/deeper", id="a recursive one"),
        ],
    )
    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_checkout_in_a_directory_spelled_like_a_pattern_is_watched_all_the_same(
        self, tmp_path: Path, generator: str, pattern: str, directory: str
    ) -> None:
        """The tool reads the directory of the project as a directory, so the watch does: a
        checkout in ``proj [v2]`` is no character class, which matched nothing, and no wildcard
        reaching the directory above it."""
        root = tmp_path / "outer" / "proj [v2]"
        shape = Shape(project=True, registered=False, includes=(pattern,))
        story = Story(root, shape, generator)
        assert story.build().code == 0
        late = root / directory / "late.ddd.json"
        late.parent.mkdir(parents=True, exist_ok=True)
        late.write_text(
            json.dumps(
                {"component": {"name": "Late", "interface": [declare("local", "LateCount")]}}
            ),
            encoding="utf-8",
        )
        started = story.build()
        assert started.code == 0 and started.generated(), started.output
        globals_c = story.images() / "ddd" / "img" / "ddd_globals.c"
        assert "LateCount" in globals_c.read_text(encoding="utf-8")

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_missing_include_is_a_warning_and_no_reason_to_refuse_to_configure(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The tool lists an include that does not exist, and says so on its standard error:
        the file is nothing to watch, and the configure warns and goes on, the build deciding
        what the project is worth."""
        shape = Shape(
            project=True, registered=False, includes=("components/*.ddd.json", "later.ddd.json")
        )
        story = Story(tmp_path, shape, generator, configured=False)
        configured = story.reconfigure()
        assert "CMake Warning" in configured, configured
        assert "later.ddd.json" in configured, configured

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_sub_project_whose_includes_is_no_list_is_a_warning_too(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The tool reports the schema error and lists the file all the same, so the watch
        reads a file whose ``includes`` is an object, and finds nothing in it to watch."""
        shape = Shape(
            project=True, registered=False, includes=("components/*.ddd.json", "sub.json")
        )
        story = Story(tmp_path, shape, generator, configured=False)
        (tmp_path / "sub.json").write_text(
            json.dumps({"project": {"name": "Sub", "includes": {"a": "b"}}}), encoding="utf-8"
        )
        configured = story.reconfigure()
        assert "CMake Warning" in configured, configured

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_recursive_wildcard_is_watched_below_its_own_directory_alone(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A file the name of which fits ``**/*.ddd.json`` but which lies outside ``components/``
        is no match, and the build after it has nothing to do."""
        shape = Shape(project=True, registered=False, includes=("components/**/*.ddd.json",))
        story = Story(tmp_path, shape, generator)
        assert story.build().code == 0
        (tmp_path / "elsewhere").mkdir()
        (tmp_path / "elsewhere" / "other.ddd.json").write_text("{}", encoding="utf-8")
        assert story.build().did_nothing()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_project_including_nothing_has_nothing_to_watch_and_configures(
        self, tmp_path: Path, generator: str
    ) -> None:
        shape = Shape(project=True, registered=False, includes=())
        story = Story(tmp_path, shape, generator, configured=False)
        story.reconfigure()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_vocabulary_file_gained_or_lost_reaches_the_a2l_written_after_the_link(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A units file adds no object, so the c is as it was and the image is not linked
        again, and a file that left leaves every input of the a2l step as it was: the list of the
        project's files is what tells it, and it reads the map again all the same."""
        shape = Shape(
            project=True,
            registered=False,
            address_map=True,
            includes=("components/*.ddd.json",),
        )
        story = Story(tmp_path, shape, generator)
        assert story.build().code == 0
        spare = {"units": [{"unit": "mph", "description": "road speed"}]}
        (story.components / "more.ddd.json").write_text(json.dumps(spare), encoding="utf-8")
        gained = story.build()
        assert gained.code == 0, gained.output
        assert "Reading the addresses of the a2l out of the address map" in gained.output
        assert "Linking" not in gained.output, gained.output
        assert story.build().did_nothing()
        (story.components / "more.ddd.json").unlink()
        lost = story.build()
        assert lost.code == 0, lost.output
        assert "Reading the addresses of the a2l out of the address map" in lost.output
        assert story.build().did_nothing()


class TestAPluginThatBreaksStillWatchedByTheBuild:
    """A plugin that stops importing, or whose model raises, is a defect to report and a file
    to keep watching.

    ``ddd sources`` listed the plugins that loaded, so the configure the edit ran dropped the
    broken file from what the generation depends on: the build said ``no work to do`` with the
    old artefacts, and so did every later one - the repair, and the edit of a component after
    it - until something else configured again. The module also printed the tool's stderr only
    when it exited non-zero, so the defect, a finding, reached nobody.
    """

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    @pytest.mark.parametrize(
        ("broken", "reported"),
        [
            pytest.param(SYNTAX_ERROR, "invalid syntax", id="stops importing"),
            pytest.param(
                STAMP_PLUGIN.format(body='raise RuntimeError("validator defect")'),
                "validator defect",
                id="its model raises",
            ),
        ],
    )
    def test_the_build_after_the_edit_fails_and_the_one_after_its_repair_runs(
        self, tmp_path: Path, generator: str, broken: str, reported: str
    ) -> None:
        """The edit is noticed: the configure it runs warns, the generation stops loudly, the
        repair is generated, and an edit of a component after that reaches the image."""
        story = plugged(tmp_path, generator)
        assert "CMake Warning" not in story.configured, story.configured
        assert story.build().code == 0
        story.write_plugin(broken)
        edited = story.build()
        assert edited.code != 0, edited.output
        assert "CMake Warning" in edited.output and reported in edited.output, edited.output
        story.write_plugin(STAMP_PLUGIN.format(body="pass") + "\n# repaired\n")
        repaired = story.build()
        assert repaired.code == 0 and repaired.generated(), repaired.output
        assert "CMake Warning" not in repaired.output, repaired.output
        assert story.build().did_nothing()
        story.describe("uint16", declare("local", "Ticks", extensions={"stamp": {"tag": "t"}}))
        story.write_sensor(1234)
        widened = story.build()
        assert widened.code == 0, widened.output
        assert widened.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_validator_raising_at_the_first_configure_is_warned_about_and_mended(
        self, tmp_path: Path, generator: str
    ) -> None:
        """The first configure meets the defect: it prints a warning and exits 0, the build
        fails loudly, and once the plugin is mended a component's edit reaches the image
        rather than ``no work to do``: the configure listed what the project names, the
        plugin's file among it, so the mending ran it again."""
        story = plugged(tmp_path, generator, 'raise RuntimeError("validator defect")')
        said = " ".join(story.configured.split())
        assert "CMake Warning" in said, said
        assert "validator defect" in said, said
        # The tool's trailing newline is stripped, so the warning ends where its text does.
        assert "1 error\nCall Stack" in story.configured, story.configured
        assert story.build().code != 0
        story.write_plugin(STAMP_PLUGIN.format(body="pass"))
        mended = story.build()
        assert mended.code == 0 and mended.printed == "logged 200", mended.output
        story.describe("uint16", declare("local", "Ticks", extensions={"stamp": {"tag": "t"}}))
        story.write_sensor(1234)
        widened = story.build()
        assert widened.code == 0, widened.output
        assert widened.printed == "logged 1234"

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_plugin_deleted_is_noticed_and_its_return_is_generated(
        self, tmp_path: Path, generator: str
    ) -> None:
        story = plugged(tmp_path, generator)
        assert story.build().code == 0
        (tmp_path / "plug.py").unlink()
        assert story.build().code != 0
        story.write_plugin(STAMP_PLUGIN.format(body="pass"))
        returned = story.build()
        assert returned.code == 0 and returned.generated(), returned.output

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_project_the_tool_cannot_resolve_stays_a_dependency_of_the_configure(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A root that parses and fails its schema lists nothing: the configure warns, and the
        project file is the one thing it can watch, so the edit repairing it configures again
        and the build after it is the right one."""
        story = Story(tmp_path, PLUGIN_PROJECT, generator, configured=False)
        story.write_plugin(STAMP_PLUGIN.format(body="pass"))
        project = tmp_path / "project.ddd.json"
        named = project.read_text(encoding="utf-8")
        project.write_text(named.replace('"includes"', '"included"'), encoding="utf-8")
        configured = story.reconfigure()
        assert "CMake Warning" in configured, configured
        # Not "yet": a file that has yet to exist, or to parse, is refused before the tool is asked.
        said = f'ddd_generate: cannot resolve the sources of "{project.as_posix()}" ('
        assert said in " ".join(configured.split()), configured
        project.write_text(named, encoding="utf-8")
        repaired = story.build()
        assert repaired.code == 0 and repaired.printed == "logged 200", repaired.output
        assert "Configuring done" in repaired.output, repaired.output

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_package_named_by_its_module_stops_importing_and_is_mended(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A module spelling that fails to import is in no ``sys.modules``, so the file its
        import recorded was never there to list: the configure the breaking edit ran dropped
        the package, and the build after it, and after its repair, had nothing to do. The
        finder locates it without running it, so every file of it stays listed - ``impl.py``,
        where the shared code lives, as much as ``__init__.py``."""
        site = tmp_path / "site"
        package = site / "storypkg"
        package.mkdir(parents=True)
        init = "from storypkg.impl import PLUGIN\n"
        story = Story(tmp_path, MODULE_PROJECT, generator, configured=False)
        story.site = site
        (package / "__init__.py").write_text(init, encoding="utf-8")
        (package / "impl.py").write_text(STAMP_PLUGIN.format(body="pass"), encoding="utf-8")
        story.configured = story.reconfigure()
        assert story.build().code == 0
        (package / "__init__.py").write_text("def broken(:\n", encoding="utf-8")
        edited = story.build()
        assert edited.code != 0, edited.output
        assert "invalid syntax" in edited.output, edited.output
        (package / "__init__.py").write_text(init + "# repaired\n", encoding="utf-8")
        repaired = story.build()
        assert repaired.code == 0 and repaired.generated(), repaired.output
        assert story.build().did_nothing()
        (package / "impl.py").write_text(
            STAMP_PLUGIN.format(body="pass") + "\n# edited\n", encoding="utf-8"
        )
        again = story.build()
        assert again.code == 0 and again.generated(), again.output

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_check_the_call_relaxes_is_not_warned_of_at_the_configure(
        self, tmp_path: Path, generator: str
    ) -> None:
        """``ddd sources`` grades what it says by the ``SEVERITY`` and ``STRICT`` of the call:
        a project relaxing a load-time check there had a warning at every configure that it
        could not silence."""
        said = " ".join(Story(tmp_path / "loud", UNMATCHED, generator).configured.split())
        assert "CMake Warning" in said and "include-empty" in said, said
        relaxed = Story(tmp_path / "quiet", RELAXED, generator).configured
        assert "CMake Warning" not in relaxed, relaxed

    def test_a_failed_build_is_not_a_build_with_nothing_to_do(self) -> None:
        """A CMake re-run that fails prints ``Configuring incomplete`` and compiles nothing,
        which read as a build that had nothing to do; and so did one that read the addresses
        of the a2l again, and did nothing else."""
        failed = Step(1, "-- Configuring incomplete, errors occurred!", frozenset(), "")
        assert not failed.did_nothing()
        reread = "[100%] Reading the addresses of the a2l out of the address map of img"
        assert not Step(0, reread, frozenset(), "logged 200").did_nothing()
        assert Step(0, "ninja: no work to do.", frozenset(), "").did_nothing()


class TestTheMapReadOnceTheImageIsLinked:
    """``ADDRESS_MAP`` with the build page's recipe, under ``STRICT``: the a2l a build writes
    holds the addresses of the image that build linked.

    The generation before the link wrote the a2l, reading the map the link before it had
    extracted, so each build's a2l carried the addresses of the image linked before it: every
    address 0 on the first build of a clean tree, and after an edit that moved a variable, the
    address it had - with no finding, not even under ``STRICT``, and nothing in the file to
    tell. An object a description gained was missing from that map, so under ``STRICT`` the
    generation stopped before anything compiled, and since only a link rewrites the map, every
    build after it stopped the same way. The map is read once the image is linked now, by
    ``<stem>_ddd_a2l``, as ``ADDRESSES_FROM_IMAGE`` reads the image; and an a2l written with
    nothing to read its addresses from says so itself, no finding being able to.
    """

    @pytest.mark.parametrize(
        ("shape", "addressed"),
        [
            pytest.param(MAPPED, True, id="its addresses read from the map"),
            pytest.param(Shape(strict=True), False, id="no address source"),
        ],
    )
    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_clean_trees_first_build_is_said_for_what_it_is(
        self, tmp_path: Path, generator: str, shape: Shape, addressed: bool
    ) -> None:
        """With the map, the first build of a clean tree gives the a2l of the image it linked,
        rather than one of zeros a second build would correct; without an address source the
        a2l can only be one of zeros, and the line under its version says so."""
        story = Story(tmp_path, shape, generator)
        first = story.build()
        assert first.code == 0, first.output
        head = story.a2l().splitlines()[:3]
        recorded = a2l_addresses(story.a2l())
        assert recorded, "the story has records to address"
        if addressed:
            assert recorded == story.placed()
            assert NO_ADDRESS_SOURCE not in head
        else:
            assert set(recorded.values()) == {0}
            assert head[1:] == ["ASAP2_VERSION 1 61", NO_ADDRESS_SOURCE]

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_an_array_grown_and_built_once_is_at_this_links_addresses(
        self, tmp_path: Path, generator: str
    ) -> None:
        """``Buffer`` grows from 2 to 40 elements in one build, and the variables the linker
        places after it move: the a2l says where they are now."""
        story = Story(tmp_path, MAPPED, generator)
        story.describe("uint8", declare("local", "Buffer", dimensions=[2]))
        assert story.build().code == 0
        before = story.placed()
        story.describe("uint8", declare("local", "Buffer", dimensions=[40]))
        grown = story.build()
        assert grown.code == 0, grown.output
        after = story.placed()
        assert after != before, "nothing moved, so the story does not tell the two apart"
        assert a2l_addresses(story.a2l()) == after

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_an_object_added_still_builds(self, tmp_path: Path, generator: str) -> None:
        """``Ticks`` is new to the sensor, so the map the last link extracted has no entry for
        it: nothing reads that map before the link any more, and the one this link extracts
        has it."""
        story = Story(tmp_path, MAPPED, generator)
        assert story.build().code == 0
        story.describe("uint8", declare("local", "Ticks", "uint16"))
        added = story.build()
        assert added.code == 0, added.output
        assert "Ticks" in story.placed()
        assert a2l_addresses(story.a2l()) == story.placed()

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_map_written_without_a_link_is_read_again_and_nothing_else_runs(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A map may be written otherwise than by a step of the link - by hand, say - so the
        step after the link depends on it as well as on the image; the generation before the
        link, which does not read it, does not run for it, nor does anything it orders."""
        story = Story(tmp_path, MAPPED, generator)
        assert story.build().code == 0
        address_map = story.images() / "ddd" / "img" / "addresses.json"
        entries = json.loads(address_map.read_text(encoding="utf-8"))
        entries["Sample"] = "0x00500000"
        address_map.write_text(json.dumps(entries), encoding="utf-8")
        reread = story.build()
        assert reread.code == 0, reread.output
        assert "Reading the addresses of the a2l out of the address map of img" in reread.output
        assert not reread.generated() and not reread.compiled, reread.output
        assert "Linking" not in reread.output
        assert a2l_addresses(story.a2l())["Sample"] == 0x00500000

    @pytest.mark.parametrize("generator", STORY_GENERATORS)
    def test_a_map_touched_and_left_as_it_was_is_read_once(
        self, tmp_path: Path, generator: str
    ) -> None:
        """A read of the map that changes nothing leaves the a2l as it was. Under make, which
        looks at no file again once a step has run, the a2l stayed older than the map, and
        every build after read the map again - the one rerun the pages stated."""
        story = Story(tmp_path, MAPPED, generator)
        assert story.build().code == 0
        os.utime(story.images() / "ddd" / "img" / "addresses.json")
        touched = story.build()
        assert touched.code == 0, touched.output
        assert "Reading the addresses of the a2l out of the address map of img" in touched.output
        assert story.build().did_nothing()


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

    def test_a_table_keeping_its_counts_compiles_with_them_in_front(self, tmp_path: Path) -> None:
        """The flat declaration, its initialiser and the extern in the component header agree
        with one another under the full warning set - ``-Wconversion`` included, which is what
        a count spelled as a constant's name meets - and a static assertion pins the size the
        counts add ahead of the data. ``tests/test_point_counts.py::TestTheC`` is what checks
        the values and their order."""
        (tmp_path / "k.ddd.json").write_text(
            json.dumps({"constants": [{"name": "NX", "value": 8}]}), encoding="utf-8"
        )
        (tmp_path / "t.ddd.json").write_text(
            json.dumps(
                {
                    "component": {
                        "name": "T",
                        "interface": [
                            declare("output", "AX", "uint16", kind="axis", size="NX"),
                            declare("output", "AY", "uint16", kind="axis", size=11),
                            declare("output", "M", "uint32", kind="map", x_axis="AX", y_axis="AY"),
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )
        description = tmp_path / "project.ddd.json"
        description.write_text(
            json.dumps(
                {
                    "project": {
                        "name": "P",
                        "includes": ["k.ddd.json", "t.ddd.json"],
                        "point_counts": "leading",
                    }
                }
            ),
            encoding="utf-8",
        )
        output = self.generated(tmp_path, description)
        (output / "check_counts.c").write_text(
            '#include "T.h"\n'
            '_Static_assert(sizeof M == (2 + 8 * 11) * sizeof(uint32_t), "counts ahead of M");\n'
            '_Static_assert(sizeof AX == (1 + 8) * sizeof(uint16_t), "count ahead of AX");\n',
            encoding="utf-8",
        )
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

    def test_a_checkout_under_a_non_ascii_directory_builds(self, tmp_path: Path) -> None:
        """``ddd sources`` writes UTF-8 whatever the console's code page is, and the module has
        to read it as UTF-8: decoded in the code page, ``Müller`` became other characters, and
        the build asked ninja for a description at a path that does not exist. Every leg runs
        it; the windows legs are the ones whose code page is not UTF-8."""
        root = tmp_path / "Müller-project"
        root.mkdir()
        self.write(root)
        configure(root, root / "build")
        build(root / "build")
        generated = root / "build" / "ddd" / "img"
        assert (generated / "ddd_layout.h").is_file()
        graph = (root / "build" / "build.ninja").read_text(encoding="utf-8")
        assert (root / "layout" / "project.ddd.json").as_posix() in graph

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


def cxx_compiler() -> list[str]:
    """``-DCMAKE_CXX_COMPILER=g++`` beside the gcc :func:`compiler` names, where it names one."""
    if shutil.which("cl") is None and (gcc := shutil.which("gcc")):
        gxx = shutil.which("g++", path=str(Path(gcc).parent))
        if gxx is not None:
            return [f"-DCMAKE_CXX_COMPILER={Path(gxx).as_posix()}"]
    return []


class TestAProjectThatEnablesNoC:
    """The definitions the templates render are C, compiled by an object library of the module's,
    which a directory with no C cannot build: under ``project(<name> LANGUAGES CXX)`` CMake
    stopped at it, unable to determine its linker language - a target of the module's named, and
    not the language the project left out. What counts is whether C is enabled in the directory
    calling ``ddd_generate``, once that directory is done: a sibling enabling it does not help
    that directory, and an ``enable_language(C)`` after the call, in it, does."""

    GENERATION = (
        "add_library(store STATIC store.cpp)\n"
        'ddd_add_component(store JSON "${CMAKE_CURRENT_SOURCE_DIR}/store.ddd.json")\n'
        "add_executable(img main.cpp)\n"
        "target_link_libraries(img PRIVATE store)\n"
        f'ddd_generate(img TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}")\n'
    )
    """A component and an image in C++, generated where they are."""

    def write(self, tmp_path: Path, tail: str, generating: Path) -> Path:
        """The top ``CMakeLists.txt``, a C++ project, ending with ``tail``; the component and the
        image in ``generating``, a directory of their own or the top one."""
        described = {"component": {"name": "Store", "interface": [declare("local", "Level")]}}
        generating.mkdir(parents=True, exist_ok=True)
        (generating / "store.ddd.json").write_text(json.dumps(described), encoding="utf-8")
        (generating / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
        (generating / "store.cpp").write_text("int store() { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.30)\n"
            "project(Cxx LANGUAGES CXX)\n"
            f'list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")\n'
            f"include(Ddd)\n{tail}",
            encoding="utf-8",
        )
        return generating

    def refusal(self, directory: Path) -> str:
        return (
            f'ddd_generate: the templates in "{TEMPLATES.as_posix()}" render C - "ddd_globals.c" '
            f"- the definitions of the image's variables, and C is not enabled in \""
            f'{directory.as_posix()}", where ddd_generate() is called. Enable it there, or in a '
            "directory above it, before that directory is done: project(<name> LANGUAGES C CXX), "
            "or enable_language(C)."
        )

    def test_it_is_refused_naming_the_language(self, tmp_path: Path) -> None:
        self.write(tmp_path, self.GENERATION, tmp_path)
        run = attempt(tmp_path, tmp_path / "build", *cxx_compiler())
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "can not determine linker language" not in said, said
        assert self.refusal(tmp_path) in said

    def test_c_enabled_in_a_sibling_directory_alone_is_refused_too(self, tmp_path: Path) -> None:
        """The language CMake reads for the directory calling ``ddd_generate`` is that
        directory's own: C enabled in a sibling passed a check of the languages enabled anywhere,
        and CMake then stopped generating, missing ``CMAKE_C_COMPILE_OBJECT``."""
        (tmp_path / "clib").mkdir()
        (tmp_path / "clib" / "CMakeLists.txt").write_text(
            "enable_language(C)\nadd_library(clib STATIC clib.c)\n", encoding="utf-8"
        )
        (tmp_path / "clib" / "clib.c").write_text("int clib(void) { return 0; }\n", "utf-8")
        generating = self.write(
            tmp_path, "add_subdirectory(clib)\nadd_subdirectory(fw)\n", tmp_path / "fw"
        )
        (generating / "CMakeLists.txt").write_text(self.GENERATION, encoding="utf-8")
        run = attempt(tmp_path, tmp_path / "build", *cxx_compiler())
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "CMAKE_C_COMPILE_OBJECT" not in said, said
        assert self.refusal(generating) in said

    def test_c_enabled_after_the_call_in_its_directory_builds(self, tmp_path: Path) -> None:
        """CMake builds the object library once the directory has C, which it reads when the
        directory is done: refused at the call, this layout was refused for nothing."""
        self.write(tmp_path, self.GENERATION + "enable_language(C)\n", tmp_path)
        configure(tmp_path, tmp_path / "build", *cxx_compiler())
        build(tmp_path / "build")
        assert (tmp_path / "build" / "ddd" / "img" / "ddd_globals.c").is_file()


class TestAProjectFileReadWhenConfigured:
    """``PROJECT`` is read when the build is configured - the files it is made of, its plugins,
    its name - so it has to exist, and parse, by then.

    A file in the build tree was let through as one the build might write later, and the call
    then said it could not resolve the project *yet* and that the generation would depend on
    that file alone - and stopped the configure on CMake's own ``file failed to open for
    reading``. A file that does not parse got the same line, and then ``has neither a project
    nor a component name``. Neither was a fallback: both are refused now, naming the file and
    why it has to be there. A project that parses and that the tool cannot resolve all the same
    still falls back, as :class:`TestAPluginThatBreaksStillWatchedByTheBuild` shows.
    """

    def write(self, tmp_path: Path, project: str) -> Path:
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.20)
project(Read LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_executable(img main.c)
ddd_generate(img PROJECT "{project}" TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}")
""",
            encoding="utf-8",
        )
        return tmp_path

    def test_one_the_build_would_write_is_refused_naming_it(self, tmp_path: Path) -> None:
        source = self.write(tmp_path, "${CMAKE_BINARY_DIR}/later.ddd.json")
        run = attempt(source, tmp_path / "build")
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "will depend on that file alone" not in said, said
        assert (
            f'ddd_generate: PROJECT names "{(tmp_path / "build" / "later.ddd.json").as_posix()}", '
            "which does not exist. The project description is read when the build is configured "
            "- the files it is made of, its plugins and its name - so it has to exist, and "
            "parse, by then: a file the build has yet to write is no project description."
        ) in said

    def test_one_that_does_not_parse_is_refused_saying_so(self, tmp_path: Path) -> None:
        project = tmp_path / "project.ddd.json"
        project.write_text('{"project": {"name": "Read",', encoding="utf-8")
        source = self.write(tmp_path, project.as_posix())
        run = attempt(source, tmp_path / "build")
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "will depend on that file alone" not in said, said
        assert (
            f'ddd_generate: PROJECT names "{project.as_posix()}", which does not parse as json. '
            "The project description is read when the build is configured - the files it is "
            "made of, its plugins and its name - so it has to exist, and parse, by then:"
        ) in said

    def test_one_that_names_nothing_is_refused_saying_so(self, tmp_path: Path) -> None:
        """A root that parses and names no project: the a2l and the dictionary are named after
        that name, so the call cannot declare them. It was warned of as a project the generation
        would depend on alone, a fallback the call then did not take, stopping on ``has neither
        a project nor a component name``."""
        project = tmp_path / "project.ddd.json"
        project.write_text(json.dumps({"project": {"includes": []}}), encoding="utf-8")
        source = self.write(tmp_path, project.as_posix())
        run = attempt(source, tmp_path / "build")
        said = " ".join((run.stdout + run.stderr).split())
        assert run.returncode != 0, said
        assert "will depend on that file alone" not in said, said
        assert (
            f'ddd_generate: PROJECT names "{project.as_posix()}", which gives its project - or '
            "its component - no name. The project description is read when the build is "
            "configured - the files it is made of, its plugins and its name - so it has to exist, "
            "and parse, by then: the a2l and the dictionary are named after that name."
        ) in said


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
    """The build page's address map recipe, run: one build, what the a2l ends up with, and the
    build after it.

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
        before, step = address_map_recipe("firmware.elf")
        (source / "cmake").mkdir()
        (source / "cmake" / "AddressMap.cmake").write_text(
            documented_block("# cmake/AddressMap.cmake"), encoding="utf-8"
        )
        listing = source / "CMakeLists.txt"
        text = listing.read_text(encoding="utf-8")
        schemas = 'SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas")'
        assert schemas in text
        text = text.replace(
            "ddd_generate(firmware.elf", before + "ddd_generate(firmware.elf"
        ).replace(
            schemas,
            schemas[:-1] + '\n             ADDRESS_MAP "${address_map}"'
            '\n             STRICT\n             SEVERITY "address-missing=info")',
        )
        text += "\n" + step + "\n" + based_low("firmware.elf")
        listing.write_text(text, encoding="utf-8")
        return source

    def test_one_build_gives_the_addresses_and_the_next_has_nothing_to_do(
        self, tmp_path: Path
    ) -> None:
        source = self.write(tmp_path)
        configure(source, tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "firmware.elf"

        output = build(tmp_path / "build")
        extracted = json.loads((generated / "addresses.json").read_text(encoding="utf-8"))
        assert "ValueA" in extracted, "the step extracts the symbols of the image"
        assert any(name.startswith("_") for name in extracted), "the c runtime's among them"
        assert "Reading the addresses of the a2l out of the address map of firmware.elf" in output
        assert "address-missing" in output, "the two objects a symbol lister cannot answer for"
        a2l = (generated / "DemoDevice.a2l").read_text(encoding="utf-8")
        assert f"ECU_ADDRESS 0x{int(extracted['ValueA'], 16):08X}" in a2l

        # "nothing is extracted, read, compiled or linked again" - the page's own sentence
        # about the build after it.
        assert "no work to do" in build(tmp_path / "build")

    def test_two_file_local_statics_of_one_name_do_not_collide(self, tmp_path: Path) -> None:
        """Two translation units, each with its own ``static int cntr_50ms_decimate_5`` - the
        report this recipe was fixed for. Without ``--extern-only`` the listing carries both
        under the same name, and ``load_address_map`` refuses a symbol named twice with two
        addresses; kept to global symbols only, the file-local statics never reach the map."""
        source = self.write(tmp_path)
        for suffix, function in (("a", "bump_a"), ("b", "bump_b")):
            (source / f"statics_{suffix}.c").write_text(
                "static int cntr_50ms_decimate_5 = 1;\n"
                "\n"
                f"int {function}(void)\n"
                "{\n"
                "    return cntr_50ms_decimate_5++;\n"
                "}\n",
                encoding="utf-8",
            )
        listing = source / "CMakeLists.txt"
        text = listing.read_text(encoding="utf-8")
        marker = "add_executable(firmware.elf main.c)"
        assert marker in text
        text = text.replace(
            marker, marker + "\ntarget_sources(firmware.elf PRIVATE statics_a.c statics_b.c)"
        )
        listing.write_text(text, encoding="utf-8")

        configure(source, tmp_path / "build")
        # One build links, extracts the map and reads it: the read the duplicate used to fail.
        build(tmp_path / "build")
        generated = tmp_path / "build" / "ddd" / "firmware.elf"
        extracted = json.loads((generated / "addresses.json").read_text(encoding="utf-8"))
        assert "cntr_50ms_decimate_5" not in extracted


NOT_ELF = "is not an ELF image this tool can read: Magic number does not match"
"""How DDD's reader refuses an image that is not ELF, a PE file included: the first four bytes
are where it stops."""

PRE_LINK = (
    "ddd_globals.c",
    "ddd_globals.h",
    "ddd_types.h",
    "Engine.h",
    "AddressFixture.dictionary.json",
)
"""What the run before the link writes into the directory the a2l is written into after it."""


def oracle(image: Path) -> dict[str, int]:
    """Where the toolchain put every symbol the a2l carries: ``nm``'s address of its variable,
    plus the compiler's own ``offsetof`` of it, which ``oracle.c`` compiled into the image - read
    back as the address fixtures read theirs, and never through DDD's reader."""
    carried = json.loads(SYMBOLS.read_text(encoding="utf-8"))["addressed"]
    found = addresses_of(image)
    offsets = zip(carried, oracle_of(image, sys.byteorder), strict=True)
    return {symbol: found[root_of(symbol)] + offset for symbol, offset in offsets}


@dataclass(frozen=True)
class Built:
    """One build of the class below, and what it left behind."""

    code: int
    output: str
    a2l: str
    """The a2l once the build was over, or nothing where there was none."""

    oracle: dict[str, int]
    """What the toolchain says of the image the build linked, where it linked ELF."""

    written: dict[str, int | None]
    """When each file of the run before the link was last written, or None where it is gone."""


@dataclass(frozen=True)
class FromTheImage:
    """What one configure and the builds after it left behind, for the class below."""

    configured: str
    generated: Path
    elf: bool
    builds: list[Built]
    """The first build, the same again, one after an edit that relinks the image, and one after
    a description edit the c does not see - or the first alone, where the image is not ELF."""

    def linked_elf(self) -> bool:
        """Whether the host's toolchain linked an ELF image, which is what DDD reads.

        MinGW's gcc, which the windows cells build with, links PE: there the step after the
        link refuses the image in the reader's words and the build stops with no a2l, which is
        asserted here before answering no - so that a test with nothing more to ask of such a
        host has still checked what it gets."""
        if self.elf:
            return True
        (first,) = self.builds
        assert first.code != 0, first.output
        assert NOT_ELF in first.output, first.output
        assert first.a2l == ""
        return False


class TestAddressesFromTheImage:
    """``ADDRESSES_FROM_IMAGE``: the a2l written once the image is linked, out of that image.

    One configure and four builds of one tree, the class fixture's story: the build that gives
    the whole a2l, the same build again, one after an edit that relinks the image, and one after
    a description edit that reaches the a2l and none of the c. The project is the address
    fixtures' - bitfields before value members, arrays of structures in one and two dimensions -
    built by the host's toolchain into an image that also carries ``oracle.c``, so that what the
    toolchain says of every symbol is read back out of the very image the a2l was read from.

    That needs a host whose toolchain links ELF, as every linux cell's does. MinGW's gcc, which
    the windows cells build with, links PE, which DDD does not read: what a build gets there is
    the step after the link refusing the image in the reader's words, and that is what each test
    asserts there instead (``FromTheImage.linked_elf``) - a test that skipped would report
    success without having run.
    """

    def write(self, source: Path, options: str = "", tail: str = "") -> None:
        """The address fixtures' project and oracle, and an image of them both."""
        shutil.copytree(PROJECT.parent, source / "project")
        shutil.copy(ORACLE, source / "oracle.c")
        (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (source / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(FromImage LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_executable(img main.c oracle.c)
ddd_generate(img
             PROJECT "${{CMAKE_CURRENT_SOURCE_DIR}}/project/project.ddd.json"
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             ADDRESSES_FROM_IMAGE{options})
{tail}
get_target_property(a2l img DDD_A2L)
message(STATUS "DDD_A2L=${{a2l}}")
""",
            encoding="utf-8",
        )

    @staticmethod
    def image(build_dir: Path) -> Path:
        return build_dir / ("img.exe" if os.name == "nt" else "img")

    @pytest.fixture(scope="class")
    @staticmethod
    def story(tmp_path_factory: pytest.TempPathFactory) -> FromTheImage:
        """One story, told once: build, build again, relink, edit a description."""
        source = tmp_path_factory.mktemp("from-image")
        TestAddressesFromTheImage().write(source)
        build_dir = source / "build"
        # With debug information, which the image has to carry and an empty build type omits.
        configured = configure(source, build_dir, "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        generated = build_dir / "ddd" / "img"
        image = TestAddressesFromTheImage.image(build_dir)

        def built() -> Built:
            run = cmake("--build", str(build_dir), cwd=build_dir)
            a2l = generated / "AddressFixture.a2l"
            paths = [generated / name for name in PRE_LINK]
            return Built(
                code=run.returncode,
                output=run.stdout + run.stderr,
                a2l=a2l.read_text(encoding="utf-8") if a2l.exists() else "",
                oracle=oracle(image) if image.read_bytes()[:4] == b"\x7fELF" else {},
                written={
                    path.name: path.stat().st_mtime_ns if path.exists() else None for path in paths
                },
            )

        builds = [built()]
        elf = image.read_bytes()[:4] == b"\x7fELF"
        if elf:
            builds.append(built())
            # An initialised array more: the image relinks, and what follows it moves.
            (source / "main.c").write_text(
                "int Padding[64] = {1};\n\nint main(void) { return Padding[0]; }\n",
                encoding="utf-8",
            )
            builds.append(built())
            types = source / "project" / "types.ddd.json"
            text = types.read_text(encoding="utf-8")
            assert text.count('"factor": 0.1,') == 1, "Temperature_t's factor is no longer 0.1"
            types.write_text(text.replace('"factor": 0.1,', '"factor": 0.2,'), encoding="utf-8")
            builds.append(built())
        return FromTheImage(configured.stdout, generated, elf, builds)

    def test_one_build_gives_the_a2l_the_toolchain_gives(self, story: FromTheImage) -> None:
        """Every symbol at ``nm``'s address of its variable plus the compiler's own
        ``offsetof``, the value members after bitfields and the elements of ``Grid`` included:
        no map to extract, no second build to read it."""
        if not story.linked_elf():
            return
        first = story.builds[0]
        assert first.code == 0, first.output
        assert a2l_addresses(first.a2l) == first.oracle
        assert len(first.oracle) == 46

    def test_the_a2l_property_names_the_file_the_step_writes(self, story: FromTheImage) -> None:
        """Unchanged: what a step installing or publishing the a2l reads."""
        printed = re.search(r"DDD_A2L=(.*)", story.configured)
        assert printed is not None, story.configured
        assert Path(printed.group(1).strip()) == story.generated / "AddressFixture.a2l"

    def test_a_second_build_runs_no_step(self, story: FromTheImage) -> None:
        if not story.linked_elf():
            return
        assert "ninja: no work to do." in story.builds[1].output

    def test_a_relink_reads_the_addresses_again(self, story: FromTheImage) -> None:
        """``main.c`` gains an initialised array, which the linker places before the definition
        file's variables without an initial value: they move, and the a2l says where to, as the
        toolchain does."""
        if not story.linked_elf():
            return
        first, _, relinked, _ = story.builds
        assert "Reading the addresses of the a2l out of img" in relinked.output
        assert relinked.oracle != first.oracle
        assert a2l_addresses(relinked.a2l) == relinked.oracle

    def test_the_step_after_the_link_leaves_what_the_step_before_it_wrote(
        self, story: FromTheImage
    ) -> None:
        """Review Focus 5: the a2l is written into the directory the run before the link wrote
        the c, the headers and the dictionary into, and the relink's step left every one of
        them as it was - not rewritten, not taken back - so nothing was compiled again."""
        if not story.linked_elf():
            return
        first, _, relinked, _ = story.builds
        assert None not in first.written.values()
        assert relinked.written == first.written
        assert "ddd_globals.c" not in relinked.output

    def test_a_description_the_a2l_reads_reruns_the_step_without_a_relink(
        self, story: FromTheImage
    ) -> None:
        """A conversion's factor reaches the a2l and none of the c: the c is left as it was, so
        nothing compiles or links, and the step reads the image again all the same. It updates
        the a2l rather than creating it: the run before the link, which the factor reran for
        the dictionary, left the a2l the step had written where it was."""
        if not story.linked_elf():
            return
        redescribed = story.builds[3]
        assert "Reading the addresses of the a2l out of img" in redescribed.output
        a2l = (story.generated / "AddressFixture.a2l").as_posix()
        assert f"wrote       {a2l} (updated)\n" in redescribed.output
        assert "Linking" not in redescribed.output
        assert "      COEFFS 0 1 40 0 0 0.2\n" in redescribed.a2l

    @pytest.mark.parametrize(
        ("keyword", "said"),
        [
            pytest.param(
                'ADDRESS_MAP "${CMAKE_CURRENT_BINARY_DIR}/map.json"',
                "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with ADDRESS_MAP: "
                "the a2l takes its addresses from one of the two.",
                id="ADDRESS_MAP",
            ),
            pytest.param(
                "NO_A2L",
                "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with NO_A2L: the "
                "addresses it reads out of the image are the a2l's.",
                id="NO_A2L",
            ),
        ],
    )
    def test_a_keyword_it_contradicts_is_refused_at_configure_time(
        self, tmp_path: Path, keyword: str, said: str
    ) -> None:
        self.write(tmp_path, options=f"\n             {keyword}")
        run = attempt(tmp_path, tmp_path / "build")
        assert run.returncode != 0, run.stdout + run.stderr
        # Rewrapped: cmake folds a message to its own width.
        assert said in " ".join(run.stderr.split())

    def test_under_strict_a_symbol_the_image_cannot_place_stops_the_build(
        self, tmp_path: Path
    ) -> None:
        """The definition file compiled without debug information, as a project's flags for
        generated code may have it: no symbol of the a2l has an address in the image, and the
        build stops rather than ship an a2l whose every address is 0. A unit reading ``Cells``
        through its component's header, as a consumer does, is compiled with it, so the image's
        debug information declares ``Cells`` there, and the note still names -g."""
        (tmp_path / "consumer.c").write_text(
            '#include "Engine.h"\n\nunsigned consumed(void) { return Cells[0].raw; }\n',
            encoding="utf-8",
        )
        self.write(
            tmp_path,
            options="\n             STRICT",
            tail=(
                "target_compile_options(img_ddd_globals PRIVATE -g0)\n"
                "target_sources(img PRIVATE consumer.c)"
            ),
        )
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        assert run.returncode != 0, output
        assert not (tmp_path / "build" / "ddd" / "img" / "AddressFixture.a2l").exists()
        if self.image(tmp_path / "build").read_bytes()[:4] != b"\x7fELF":
            assert NOT_ELF in output, output
            return
        assert (
            "error[address-missing]: the image has no address for 'Cells[0].raw', 'Cells[0].v', "
            "'Cells[1].raw', 'Cells[1].v', 'Cells[2].raw' and 41 others; they reach the a2l at "
            "address 0\n"
            "    note: the image's debug information only declares 'Cells'; the symbol table "
            "holds it, so the unit defining it was built without debug information (-g)\n"
        ) in output

    def test_a_byte_order_the_image_contradicts_stops_the_build(self, tmp_path: Path) -> None:
        """``BYTE_ORDER`` reaches the step after the link, where the image says otherwise."""
        other = {"little": "big", "big": "little"}[sys.byteorder]
        self.write(tmp_path, options=f"\n             BYTE_ORDER {other}")
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        assert run.returncode != 0, output
        image = self.image(tmp_path / "build")
        if image.read_bytes()[:4] != b"\x7fELF":
            assert NOT_ELF in output, output
            return
        assert (
            f"ddd: --byte-order {other} contradicts '{image.as_posix()}', which is "
            f"{sys.byteorder} endian\n"
        ) in output

    def test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step(
        self, tmp_path: Path
    ) -> None:
        """The layout example as ``TestACollectedProjectWithPlugins`` builds it, the keyword
        added. Collected, the descriptions travel the link graph as a generator expression, and
        the step depends on them as the run before the link does, and on the ``.py`` plugin
        ``PLUGINS`` names: an edited plugin or conversion reaches the a2l and relinks nothing,
        and reruns the step all the same. The plugin's own header, which the run before the
        link wrote beside the a2l, is still there after it."""
        component, plugin = TestACollectedProjectWithPlugins().write(
            tmp_path, options="\n             ADDRESSES_FROM_IMAGE"
        )
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        generated = tmp_path / "build" / "ddd" / "img"
        a2l = generated / "LayoutDevice.a2l"
        image = self.image(tmp_path / "build")
        if image.read_bytes()[:4] != b"\x7fELF":
            assert run.returncode != 0, output
            assert NOT_ELF in output, output
            assert not a2l.exists()
            return
        assert run.returncode == 0, output
        found = addresses_of(image)
        assert a2l_addresses(a2l.read_text(encoding="utf-8")) == {
            name: found[name] for name in ("CoolantTemperature", "EngineHours", "ServiceCount")
        }
        assert (generated / "ddd_layout.h").is_file()

        edit_plugin(plugin)
        replugged = build(tmp_path / "build")
        assert "Reading the addresses of the a2l out of img" in replugged
        assert "Linking" not in replugged

        described = json.loads(component.read_text(encoding="utf-8"))
        (coolant,) = [
            entry["definition"]
            for entry in described["component"]["interface"]
            if entry["definition"]["name"] == "CoolantTemperature"
        ]
        coolant["conversion"]["factor"] = 0.2
        component.write_text(json.dumps(described, indent=2), encoding="utf-8")
        redescribed = build(tmp_path / "build")
        assert "Reading the addresses of the a2l out of img" in redescribed
        assert "Linking" not in redescribed
        assert "COEFFS 0 1 0 0 0 0.2" in a2l.read_text(encoding="utf-8")


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
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" ADDRESS_MAP "${{DDD_MAP}}")',
                "ADDRESS_MAP",
                id="the address map, quoted as every recipe quotes it",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" PROJECT "${{DDD_PROJECT}}")',
                "PROJECT",
                id="the project description, quoted",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" NAME "${{DDD_NAME}}")',
                "NAME",
                id="a single value keyword, quoted",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" SEVERITY "${{DDD_SEVERITY}}")',
                "SEVERITY",
                id="a multi value keyword, quoted",
            ),
            pytest.param(
                'ddd_add_component(store JSON "${{DDD_FILES}}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}")',
                "JSON",
                id="the descriptions of a component, quoted",
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

    def test_a_quoted_keyword_is_refused_with_the_whole_sentence(self, tmp_path: Path) -> None:
        source = self.write(
            tmp_path,
            'ddd_add_component(store JSON "{component}")\n'
            'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" ADDRESS_MAP "${{DDD_MAP}}")',
        )
        run = attempt(source, tmp_path / "build")
        assert run.returncode == 1, run.stdout + run.stderr
        assert (
            'ddd_generate: "ADDRESS_MAP" was given no value. A variable that expands to nothing '
            "leaves the keyword with no argument, which reads exactly like a keyword that was "
            "never given - so the call would quietly have done something else. Give it a value, "
            "or leave the keyword out."
        ) in " ".join(run.stderr.split())

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

    @pytest.mark.parametrize("function", ["ddd_generate", "ddd_add_component"])
    def test_the_check_weighs_the_keywords_its_call_parses(self, function: str) -> None:
        """``_ddd_refuse_empty_keywords`` is handed the option, one-value and multi-value lists
        of the ``cmake_parse_arguments`` beside it spelled again - a test of the build page reads
        those lists literally. A keyword added to one and not the other would take an empty
        value unrefused, or have its values counted to the keyword before it."""
        module = (ROOT / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")
        body = module.split(f"function({function} ", 1)[1].split("\nendfunction()", 1)[0]
        lists = r'\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\)'
        parsed = re.search(r"cmake_parse_arguments\(PARSE_ARGV 1 arg" + lists, body)
        weighed = re.search(
            r'_ddd_refuse_empty_keywords\(\s*"' + function + r'" \$\{ARGC\}' + lists, body
        )
        assert parsed is not None, f"{function} no longer parses its arguments in one call"
        assert weighed is not None, f"{function} no longer weighs its arguments' values"
        assert weighed.groups() == parsed.groups()

    def test_an_empty_argument_after_a_single_value_is_no_value_of_it(self, tmp_path: Path) -> None:
        """A keyword taking one value has it after one argument, as cmake_parse_arguments reads
        the call: an empty argument after it is no value of that keyword, nor of any other."""
        source = self.write(
            tmp_path,
            'ddd_add_component(store JSON "{component}")\n'
            'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" NAME Named "${{DDD_NOTHING}}")',
        )
        configure(source, tmp_path / "build")

    @pytest.mark.parametrize(
        ("call", "keyword"),
        [
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" '
                'SEVERITY "unused-output=info" "${{DDD_SEVERITY}}" "missing-producer=ignore")',
                "SEVERITY",
                id="a severity among others",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" '
                'SEVERITY "${{DDD_SEVERITY}}" "unused-output=info")',
                "SEVERITY",
                id="a severity before another",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}" "${{DDD_FILES}}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}")',
                "JSON",
                id="a description",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" '
                'PLUGINS "${{CMAKE_CURRENT_SOURCE_DIR}}/plug.py" "${{DDD_PLUGINS}}")',
                "PLUGINS",
                id="a plugin",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" '
                'LINK_LIBRARIES store "${{DDD_LIBRARIES}}")',
                "LINK_LIBRARIES",
                id="a library",
            ),
            pytest.param(
                'ddd_add_component(store JSON "{component}")\n'
                'ddd_generate(img TEMPLATE_DIRECTORY "{templates}" '
                'DEPENDS "${{CMAKE_CURRENT_SOURCE_DIR}}/main.c" "${{DDD_DEPENDS}}")',
                "DEPENDS",
                id="a file the generation depends on",
            ),
        ],
    )
    def test_an_empty_value_among_values_is_refused(
        self, tmp_path: Path, call: str, keyword: str
    ) -> None:
        """A variable that expanded to nothing among a keyword's values drops out of the list
        without a word - ``SEVERITY "unused-output=info" "${RAISE}"`` with ``RAISE`` mistyped is
        a policy quietly weaker than the call says - so every one is refused, not only the one
        right after the keyword."""
        source = self.write(tmp_path, call)
        (tmp_path / "plug.py").write_text(
            "from ddd.plugins import Plugin\n\nPLUGIN = Plugin(name='plug')\n", encoding="utf-8"
        )
        run = attempt(source, tmp_path / "build")
        said = " ".join(run.stderr.split())
        assert run.returncode != 0, run.stdout + run.stderr
        assert (
            f'"{keyword}" was given an empty value among its values. A variable that expands to '
            "nothing there drops out of the list without a word, so the call would quietly have "
            "done without it. Give it a value, or leave it out."
        ) in said


class TestAProjectFileRegisteredAsAComponent:
    """A project description is no component, and ``ddd_add_component`` once took it as one.

    The file was collected into the generation, but only the file itself was watched: an
    edit to what it includes, or to a plugin it names, built to ``no work to do`` over a
    generated source that no longer matched the project. A supplier handing over a project
    is registered through ``PROJECT`` of ``ddd_generate``, which follows its includes, and
    the registration here is refused, naming that keyword.
    """

    def write(self, tmp_path: Path, *registered: Path) -> subprocess.CompletedProcess[str]:
        """A configure registering the files on one target, in the order given."""
        (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (tmp_path / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        spelled = " ".join(f'"{path.as_posix()}"' for path in registered)
        (tmp_path / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Supplied LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_add_component(store JSON {spelled})
""",
            encoding="utf-8",
        )
        return attempt(tmp_path, tmp_path / "build")

    def supplied(self, tmp_path: Path) -> Path:
        supplied = tmp_path / "supplier.ddd.json"
        supplied.write_text(json.dumps({"project": {"name": "Supplier"}}), encoding="utf-8")
        return supplied

    def component(self, tmp_path: Path, file: str, name: str, **more: object) -> Path:
        """A component file of the given name, with whatever more its component carries."""
        described = {"component": {"name": name, "interface": [declare("local", "Level")]}}
        described["component"].update(more)
        path = tmp_path / file
        path.write_text(json.dumps(described, indent=2), encoding="utf-8")
        return path

    def test_it_is_refused_naming_project(self, tmp_path: Path) -> None:
        supplied = self.supplied(tmp_path)
        run = self.write(tmp_path, supplied)
        assert run.returncode != 0, run.stdout + run.stderr
        assert (
            f'ddd_add_component: "{supplied.as_posix()}" registered on target "store" describes '
            "a project, and a component is not one. Name a project file with PROJECT of "
            "ddd_generate(), which follows what it includes."
        ) in " ".join(run.stderr.split())

    def test_one_registered_second_is_refused_as_well(self, tmp_path: Path) -> None:
        """Every file of the call is read, not only the first."""
        supplied = self.supplied(tmp_path)
        run = self.write(tmp_path, self.component(tmp_path, "store.ddd.json", "Store"), supplied)
        assert run.returncode != 0, run.stdout + run.stderr
        assert f'"{supplied.as_posix()}" registered on target "store" describes a project' in (
            " ".join(run.stderr.split())
        )

    def test_a_component_named_or_filed_as_a_project_is_registered(self, tmp_path: Path) -> None:
        """What makes a file a project is its top level key: a component whose file is named
        ``project.ddd.json``, whose name is ``project``, or which carries a block keyed
        ``project`` - the extension of a plugin of that name - is a component."""
        named = self.component(tmp_path, "project.ddd.json", "project")
        keyed = self.component(tmp_path, "keyed.ddd.json", "Keyed", extensions={"project": {}})
        run = self.write(tmp_path, named, keyed)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "describes a project" not in run.stdout + run.stderr


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


class TestTheCheckTargetUnderTheDefaultPolicy:
    """``<target>.ddd`` checks a component under the default policy, whatever the image asks.

    One component may be linked into several images and ``ddd_add_component`` has no ``STRICT``
    nor ``SEVERITY`` keyword, so the target has no image whose policy it could take. The build page
    says so, and says that a supplier's check is therefore not the build's: green where the
    image is red under ``STRICT``, and red where the image relaxed a check the component trips.
    """

    @staticmethod
    def project(root: Path, interface: list[dict[str, object]], options: str) -> Path:
        (root / "store.ddd.json").write_text(
            json.dumps({"component": {"name": "Store", "interface": interface}}, indent=2),
            encoding="utf-8",
        )
        (root / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (root / "store.c").write_text("int store(void) { return 0; }\n", encoding="utf-8")
        (root / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(Policy LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_library(store STATIC store.c)
ddd_add_component(store JSON "{(root / "store.ddd.json").as_posix()}")
add_executable(img main.c)
target_link_libraries(img PRIVATE store)
ddd_generate(img
             NAME PolicyDevice
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             {options})
""",
            encoding="utf-8",
        )
        configure(root, root / "build")
        return root / "build"

    def test_a_warning_the_image_makes_an_error_passes_the_target(self, tmp_path: Path) -> None:
        directory = self.project(
            tmp_path, [declare("local", "Speed"), declare("local", "SPEED")], "STRICT"
        )
        image = cmake("--build", str(directory), "--target", "img", cwd=tmp_path)
        assert image.returncode != 0, "STRICT let the image through on a warning"
        output = build(directory, "store.ddd")
        assert "name-similar" in output, "the target no longer reports the finding"

    def test_an_error_the_image_relaxes_still_fails_the_target(self, tmp_path: Path) -> None:
        interface = [declare("local", "Level", "uint8", init=300, id="ab3cd4ef5gh6")]
        directory = self.project(tmp_path, interface, "SEVERITY init-invalid=warning")
        build(directory, "img")
        run = cmake("--build", str(directory), "--target", "store.ddd", cwd=tmp_path)
        assert run.returncode != 0, "the target took the image's relaxation"
        assert "init-invalid" in run.stdout + run.stderr

    def test_the_build_page_says_which_policy_the_target_applies(self) -> None:
        page = " ".join(BUILD_PAGE.read_text(encoding="utf-8").split())
        assert "cannot drift apart" not in page, "the page still promises the three agree"
        assert "under the default severity policy" in page
        assert "not the build's" in page


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

    def test_a_tool_upgraded_where_it_stands_is_asked_again(self, tmp_path: Path) -> None:
        """``pip install -U`` into the environment ``DDD_EXECUTABLE`` names, or an editable
        install whose checkout moved on: the same path answers with another release. The
        handshake was kept in the cache by the path, so the configure of the same tree went on
        as if nothing had changed, and only a fresh build tree refused the pair. A wrapper
        reading its release from a file beside it is that tool: the wrapper itself keeps its
        size and its time, so nothing short of asking it tells the two answers apart."""
        self.write(tmp_path)
        arguments = self.wrapped(tmp_path)
        first = cmake(*arguments, cwd=tmp_path)
        assert first.returncode == 0, first.stdout + first.stderr
        (tmp_path / "release.txt").write_text("ddd 0.0.1\n", encoding="utf-8")
        again = cmake(*arguments, cwd=tmp_path)
        assert again.returncode != 0, "a tool upgraded in place configured without a word"
        said = " ".join(again.stderr.split())
        assert "0.0.1" in said and __version__ in said, said

    def test_a_configure_asks_once_however_often_the_module_is_included(
        self, tmp_path: Path
    ) -> None:
        """The module has no include guard, and a project may include it in every directory
        that calls it: the question was asked at each include. A global property keeps the
        answer for the configure run alone, so the next configure asks again."""
        self.write(tmp_path)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "CMakeLists.txt").write_text("include(Ddd)\n", encoding="utf-8")
        listing = tmp_path / "CMakeLists.txt"
        listing.write_text(
            listing.read_text(encoding="utf-8") + "add_subdirectory(sub)\ninclude(Ddd)\n",
            encoding="utf-8",
        )
        arguments = self.wrapped(tmp_path)
        asked = tmp_path / "asked.txt"
        first = cmake(*arguments, cwd=tmp_path)
        assert first.returncode == 0, first.stdout + first.stderr
        assert len(asked.read_text(encoding="utf-8").splitlines()) == 1
        again = cmake(*arguments, cwd=tmp_path)
        assert again.returncode == 0, again.stdout + again.stderr
        assert len(asked.read_text(encoding="utf-8").splitlines()) == 2

    def wrapped(self, tmp_path: Path) -> tuple[str, ...]:
        """A configure of ``tmp_path`` with a ``ddd`` wrapper that answers ``--version`` with
        what ``release.txt`` beside it says - this release, until a test writes another - and
        notes each time it is asked in ``asked.txt``."""
        if os.name == "nt":
            tool = tmp_path / "ddd.bat"
            tool.write_text(
                '@echo asked>>"%~dp0asked.txt"\n@type "%~dp0release.txt"\n', encoding="utf-8"
            )
        else:
            tool = tmp_path / "ddd.sh"
            tool.write_text(
                '#!/bin/sh\necho asked >> "$(dirname "$0")/asked.txt"\n'
                'cat "$(dirname "$0")/release.txt"\n',
                encoding="utf-8",
            )
            tool.chmod(0o755)
        (tmp_path / "release.txt").write_text(f"ddd {__version__}\n", encoding="utf-8")
        return (
            "-S",
            str(tmp_path),
            "-B",
            str(tmp_path / "build"),
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={NINJA}",
            f"-DDDD_EXECUTABLE={tool.as_posix()}",
            *compiler(),
        )


@pytest.mark.parametrize("tool", [CMAKE, NINJA, MAKE_PROGRAMS[MAKE], str(DDD)])
def test_the_tools_this_module_runs_exist(tool: str) -> None:
    """Said out loud, so that a missing tool is this failure and not a hundred cryptic ones.
    The make is the one no requirements file installs: GNU make on Linux, and on Windows the
    ``mingw32-make`` of the MinGW whose gcc the suite compiles with."""
    assert Path(tool).is_file(), f"{tool} is not installed in this environment"


def test_a_c_compiler_this_module_builds_with_exists() -> None:
    """The fifth tool, which the four above leave out.

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
