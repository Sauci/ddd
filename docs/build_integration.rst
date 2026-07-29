Build integration
=================

DDD is not a tool somebody runs by hand before a release; it is a step of the build, in the
same way the compiler is. The generated globals have to be regenerated whenever a component
changes its declarations, the check has to fail the build rather than a review, and the a2l
that goes out with an image has to be the one generated from the components that image
actually links. Two integrations are shipped for that: a cmake module that turns the whole
workflow into two calls, and a docker image that proves the generated c really compiles.

cmake
-----

Which components an image is made of is already written down in the build system - it is the
link graph. A project description that repeats that list by hand is a second source of truth,
and it drifts the day somebody links a new component without remembering the json file. The
cmake module therefore reads the list out of the link graph: a component registers its own
description on its own target, and an image collects the descriptions of everything it links.

The module lives in ``cmake/Ddd.cmake`` and is found through ``CMAKE_MODULE_PATH``. Because a
project may be built against several installations of the tool, the directory is printed by
the tool itself rather than guessed:

.. code-block:: text

   $ ddd cmake-dir
   /home/you/ddd/cmake

.. code-block:: cmake

   list(APPEND CMAKE_MODULE_PATH "/path/to/ddd/cmake")   # what `ddd cmake-dir` printed
   include(Ddd)

Including the module looks for the ``ddd`` executable and remembers it in the cache variable
``DDD_EXECUTABLE``. Configure with ``-DDDD_EXECUTABLE=<path>`` to pin a particular
installation - the one of a virtual environment, or a small wrapper script running
``python -m ddd``.

Registering a component
~~~~~~~~~~~~~~~~~~~~~~~

``ddd_add_component(<target> JSON <file>...)`` attaches one or more description files to the
target of a component. The files must be named ``*.ddd.json`` and, unless they live in the
build tree and are generated later, must exist at configure time; a violation of either is a
fatal error, because the alternative is an image whose data dictionary is quietly incomplete.

Registering a component also creates the on-demand target ``<target>.ddd``, which checks that
component on its own - useful long before it is integrated, and useful to a supplier who does
not have the rest of the project at all. That check runs with ``missing-producer`` and
``unused-output`` switched off, because a component in isolation has nobody on the other side
of its interface; everything else, from datatypes and conversions to initial values and axis
references, is verified as usual.

Generating an image
~~~~~~~~~~~~~~~~~~~

``ddd_generate(<image> ...)`` collects the descriptions of every component in the link closure
of the image, writes the project description tying them together, runs the generator, and
links the result back into the image. It has to be called in the ``CMakeLists.txt`` that
defines the image, and after the components have been added, because it hands the generated
headers to the components registered up to that point.

The example below is ``examples/cmake/CMakeLists.txt`` from the source distribution, with its
comments removed; it is what the ``cmake`` compose service configures and builds:

.. code-block:: cmake

   cmake_minimum_required(VERSION 3.30)
   project(DddCMakeExample LANGUAGES C)

   list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake")
   include(Ddd)

   set(CMAKE_C_STANDARD 11)
   set(CMAKE_C_STANDARD_REQUIRED ON)
   add_compile_options(-Wall -Wextra -Wpedantic -Werror)

   set(descriptions "${CMAKE_CURRENT_SOURCE_DIR}/../demo")

   add_library(sensor_hub STATIC components/sensor_hub.c)
   ddd_add_component(sensor_hub JSON "${descriptions}/components/sensor_hub.ddd.json")

   add_library(controller STATIC components/controller.c)
   target_link_libraries(controller PRIVATE sensor_hub)
   ddd_add_component(controller JSON "${descriptions}/components/controller.ddd.json")

   add_library(user_interface STATIC components/user_interface.c)
   target_link_libraries(user_interface PRIVATE controller)
   ddd_add_component(user_interface JSON "${descriptions}/components/user_interface.ddd.json")

   add_library(event_logger STATIC components/event_logger.c)
   ddd_add_component(event_logger JSON "${descriptions}/subsystems/logging/event_logger.ddd.json")

   add_executable(firmware.elf main.c)
   target_link_libraries(firmware.elf PRIVATE user_interface event_logger)

   ddd_generate(firmware.elf NAME DemoDevice)

``sensor_hub.c`` then writes ``#include "SensorHub.h"`` and nothing else: the header DDD
generated for that component is the only one on its include path, so a component cannot reach
a variable it never declared. The include directory travels to the components automatically,
which is what keeps the integration down to two lines per component.

The project description that ties the collected components together is written into the output
directory as ``<NAME>.ddd.json``. It is an ordinary project file, so what an image was
generated from can be read afterwards, and checked, dumped or compared like any other.

Collection follows the link graph
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The description files are attached to a component target as a *transitive usage requirement*:
they travel through the link graph the same way an include directory or a compile definition
does. An image therefore collects exactly the components it links - no more, and, more
importantly, no less. An image linking only ``sensor_hub`` gets ``SensorHub.h`` and an a2l
holding SensorHub's variables, and ``controller`` does not appear in it at all.

That mechanism is the custom transitive property ``DDD_JSON``, built on the
``TRANSITIVE_LINK_PROPERTIES`` feature introduced in **CMake 3.30** - hence the minimum
version. The module checks it and stops with a fatal error on an older cmake instead of
carrying on, because an older cmake would silently collect an incomplete set of components,
and an incomplete data dictionary is exactly the failure DDD exists to prevent.

The property is resolved at generate time, when the link graph is known but nothing has been
compiled yet, so the generation never waits for an object file. There is no dependency cycle
either, even though the components depend on the headers generated out of their own
descriptions: unlike a tool that reads compiled objects, DDD only ever reads the json files.

A hand written project description
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A project that already maintains its own project description - because it is also built with
another build system, or because it deliberately lists more than the image links - passes it
with ``PROJECT <file>``. That mode needs neither cmake 3.30 nor ``ddd_add_component``, and the
a2l is then named after the project name inside the description, so a ``NAME`` given as well
is ignored with a status message.

A hand written project pulls its components in through ``includes``, possibly with wildcards,
so the project file alone would be a wholly insufficient dependency. The module therefore asks
the tool which files the project is really built out of, with ``ddd sources`` (see
:doc:`command_line_interface`), and uses the answer twice: as the dependencies of the
generation step, so that editing a component regenerates the globals and the a2l, and as
``CMAKE_CONFIGURE_DEPENDS``, so that adding a file matching an ``includes`` wildcard re-runs
configure and picks the new component up. If the tool cannot resolve the project yet, the
module says so and falls back to depending on the project file alone rather than refusing to
configure at all.

The targets it creates
~~~~~~~~~~~~~~~~~~~~~~

The helper targets are named after the image without its file extension, because an image is
usually named like its artefact: ``firmware.elf`` yields ``firmware_ddd_headers``.

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - target
     - what it is
   * - ``<image>_ddd_generation``
     - custom target running the generator. Depends on the collected description files, so it
       re-runs when a component changes its declarations and not otherwise.
   * - ``<image>_ddd_headers``
     - interface library carrying the include directory of the generated headers, and
       depending on the generation. Every registered component links it, so a component
       includes its interface header without knowing where the image put it.
   * - ``<image>_ddd_globals``
     - object library compiling the single definition file, linked into the image. It is an
       object library on purpose: a static library would drop the members whose symbols
       nobody references, and a measurement that only the calibration tool ever reads has no
       referencing code at all.
   * - ``<image>_ddd_check``
     - runs ``ddd check`` on the collected project on its own, for a ci job that wants the
       verdict without producing artefacts. Checking is part of generating anyway - the
       generator refuses to write anything when the interfaces disagree.
   * - ``<component>.ddd``
     - one per registered component, checking that component alone (see above).

Only ``<prefix>_globals.c``, ``<prefix>_globals.h``, ``<prefix>_types.h`` and the a2l are
declared as outputs of the generator. The per-component headers are written next to them, but
their names come from inside the description files and are therefore unknown at configure
time - which is precisely why a consumer depends on ``<image>_ddd_headers`` rather than on an
individual header path.

The path of the generated a2l is published as the ``DDD_A2L`` property of the image, so that a
post-build step can pick it up without rebuilding the path by hand:

.. code-block:: cmake

   get_target_property(a2l firmware.elf DDD_A2L)
   install(FILES "${a2l}" DESTINATION delivery)

.. note::
   Multi-config generators are refused with a fatal error: the project description and the
   generated sources are written to configuration-agnostic paths, which the configurations
   would fight over. Use a single-config generator such as Ninja.

Options
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - option
     - meaning
   * - ``PROJECT <file>``
     - use this project description instead of collecting the link closure.
   * - ``NAME <name>``
     - project name, and therefore the name of the a2l file. Defaults to the image name
       without its extension, with anything that is not a c identifier replaced, because the
       name ends up as the a2l project and module name. Ignored together with ``PROJECT``.
   * - ``OUTPUT_DIRECTORY <dir>``
     - where the generated files go; defaults to ``${CMAKE_CURRENT_BINARY_DIR}/ddd/<image>``.
   * - ``PREFIX <prefix>``
     - base name of the shared files; defaults to ``ddd``, giving ``ddd_globals.c``.
   * - ``ADDRESS_MAP <file>``
     - the symbol to address map filling the addresses into the a2l.
   * - ``BYTE_ORDER little|big``
     - byte order reported in the a2l.
   * - ``SEVERITY <check=level>...``
     - severity overrides, exactly like ``-W`` on the command line. They apply to both the
       generation and the check target.
   * - ``LINK_LIBRARIES <target>...``
     - usage requirements for compiling the generated definition file, for a project whose
       compiler flags come from an interface library.
   * - ``DEPENDS <file>...``
     - additional files that retrigger the generation.
   * - ``CONST_INPUTS``
     - declare input variables ``const`` in the consumer headers.
   * - ``NO_A2L``
     - do not generate the a2l file; no ``DDD_A2L`` property is set then.
   * - ``STRICT``
     - treat DDD warnings as errors.
   * - ``NO_PROPAGATE_HEADERS``
     - do not hand the generated headers to the registered components.

``NO_PROPAGATE_HEADERS`` is the option a project building **several** images from the same
components cannot avoid. A component's interface header is generated for one link closure, so
two images produce two different sets of headers for the same component, and whichever include
directory reached it first would silently decide which set it compiles against. Rather than
letting an include order settle that, the second ``ddd_generate()`` stops the configure step
with a fatal error. Such a project gives ``NO_PROPAGATE_HEADERS`` to **both** calls and links
the wanted ``<image>_ddd_headers`` into each component explicitly - opting out of only one of
the two would leave the same ambiguity in place, because the automatic set still reaches every
registered component rather than only the ones that image links.

docker
------

Generated c code is only worth something if a compiler accepts it, and "it compiled on my
machine" is not a statement anybody can act on. The repository therefore ships a small linux
image whose whole purpose is to generate, compile, link and inspect the result on a defined
toolchain, and a compose file that gives every routine job a name.

The image (``docker/Dockerfile``) is ``python:3.12-slim-bookworm`` with gcc and libc6-dev to
compile the generated sources, binutils for the ``nm`` that inspects them afterwards, and
ninja plus a cmake from pypi to build the cmake example - debian bookworm still ships cmake
3.25, which is older than the 3.30 the module needs. DDD itself is installed with its
development extra, and ``docker/compile.sh`` is installed as the command ``ddd-compile``.

.. note::
   The image is a linux image, so on a Windows host run docker from a WSL shell, where docker
   speaks linux containers:

   .. code-block:: bash

      wsl -d Ubuntu
      cd /mnt/c/path/to/ddd        # the working tree, seen from inside WSL
      docker compose build

.. code-block:: bash

   docker compose run --rm check           # ddd check on the demo project
   docker compose run --rm generate        # ddd generate into build/gen
   docker compose run --rm compile         # generate + compile + link + verify
   docker compose run --rm compile-const   # the same, with --const-inputs
   docker compose run --rm cmake           # configure and build examples/cmake
   docker compose run --rm test            # pytest with the coverage gate
   docker compose run --rm coverage        # the same, plus build/htmlcov/index.html
   docker compose run --rm lint            # ruff check, ruff format --check, mypy
   docker compose run --rm docs            # this documentation, into build/docs/html
   docker compose run --rm ddd ddd list examples/demo/demo.ddd.json

The working tree is bind mounted at ``/work`` and ``PYTHONPATH=/work/src`` makes it shadow the
copy installed into the image, so a change to the sources takes effect without rebuilding
anything. The ``docs`` service installs the documentation extra into that mount and runs
``sphinx-build`` with ``-W``, so a warning - a broken cross reference, a directive that does
not render - fails the build rather than producing a page nobody looks at twice. There is also
a ``shell`` service, which is the same container with an interactive bash in it.

What the compile service proves
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``compile`` runs ``docker/compile.sh``, which is deliberately more suspicious than a plain
build:

#. it generates the demo project into ``build/gen`` and writes the variable list next to it
   with ``ddd list --format json``;
#. it writes one translation unit per generated header which includes that header **twice**,
   which proves both that every header is self contained - it compiles with nothing included
   before it - and that its include guard works;
#. it compiles everything with
   ``-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual
   -Wstrict-prototypes``, so a conversion the generator got wrong is a compile error and not a
   silent truncation on the target;
#. it links all the objects into one binary and runs it, which is where a duplicated
   definition or a declaration without a definition behind it would show up - the link step is
   what actually tests the promise that every variable is defined exactly once;
#. it compares the output of ``nm`` on the generated definition file against the variable list
   from step 1 (``docker/verify_symbols.py``): every declared variable must be defined exactly
   once, nothing that DDD never declared may be defined, and a variable behind a preprocessor
   condition is allowed to be absent and is reported as such.

Steps 2 to 5 run twice, once plain and once with the extra defines from the ``CDEFS``
environment variable - ``-DFEATURE_X`` in the shipped compose file - so that conditional
declarations are covered in both of their states.

The script takes the project and the output directory as arguments, so it also runs on a real
project rather than only on the demo, and the environment variables ``CDEFS``, ``GENFLAGS``,
``CFLAGS`` and ``CC`` change the defines, the ``ddd generate`` flags, the warning set and the
compiler:

.. code-block:: bash

   docker compose run --rm compile ddd-compile path/to/project.ddd.json build/mine

.. warning::
   The container runs as root, so files it writes under ``build/`` belong to root when the
   mount is a real linux filesystem. The base image is also still referenced by tag: pin it to
   a digest before a result from it is used to release something, as the comment at the top of
   ``docker/Dockerfile`` describes.
