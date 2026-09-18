Developer documentation
=======================

This page is for whoever has to change DDD rather than use it: to add an output format, to
add a check, or to understand why the code is arranged the way it is before moving something
in it.

DDD is a front end and a set of backends with one contract between them. The front end
reads the description files, resolves the project and reports every disagreement it finds;
each backend turns the resolved result into files of one output format. The front end never
mentions c or a2l, and a backend never touches the loader or the checks. That is not a style
preference: a code generator whose layers leak becomes a generator in which nobody can
change the c output without wondering what it does to the a2l, and in which a rule about
ownership ends up being re-implemented, slightly differently, in a jinja template.

Layers
------

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * - layer
     - knows about
     - does not know about
   * - ``src/ddd/models/``
     - the json file formats, storage sizes, value ranges
     - c, a2l
   * - ``src/ddd/loading.py``
     - files, includes, globs, encodings
     - what the data means
   * - ``src/ddd/analysis.py``
     - ownership, agreement between components, references
     - how anything is rendered
   * - ``src/ddd/ir.py``
     - **the contract**: the resolved data dictionary
     - how it is rendered
   * - ``src/ddd/plugins.py``
     - the plugin contract: the blocks, the hooks
     - the loader, the analysis, any backend
   * - ``src/ddd/backends/c/``
     - ``uint16_t``, literals, include guards, rendering the project's templates
     - a2l, the loader, the checks, what the generated files are called
   * - ``src/ddd/backends/a2l/``
     - ``UWORD``, compu methods, record layouts, its own templates
     - c, the loader, the checks
   * - ``src/ddd/lsp/``
     - the language server protocol, a document's bytes and positions in it
     - any output format

The analysis row says "how anything is rendered" rather than "any output format" for a
reason: two of the checks are about what an output format can carry, so the module states
the three dimensions ``MATRIX_DIM`` holds in ASAP2 1.6.1 and the range of a c ``int`` on a
32 bit target, and says so in the findings it reports. What it does not know is how a
``MATRIX_DIM`` or an ``int`` is written, which is what the row is about.

The last two backend rows are deliberately not symmetric. The a2l backend carries its own templates,
because ASAP2 is a format ASAM defines and a project has nothing to decide about it; the c
backend carries none, because what generated c looks like is a house style. It is constructed
with the template directory ``--template-dir`` names, works out what to render from the file
names it finds there, and therefore does not know before a run which files that run produces.
Those naming rules are part of the interface a project depends on: :doc:`templates` documents
them, and the module docstring of ``src/ddd/backends/c/backend.py`` states them again next to
the code that implements them.

Six smaller modules sit beside them. ``diagnostics.py`` holds the severity policy and the
registry of every check, and is what both the loader and the analysis report through.
``compare.py`` answers the directional question of whether one dictionary may replace
another, and is the second consumer of the contract next to the backends. ``cli.py`` is the
only module that knows about argument parsing, exit codes and where output goes; it is also
where the backends a ``ddd generate`` run uses are assembled, and it reaches every layer
above through an import inside the handler that needs it rather than at the top of the file,
so that ``ddd --version`` and ``ddd --help`` - which a cmake configure step asks for once per
project and a pre-commit hook once per file - are answered without building a single
contract. ``names.py`` is what makes that possible: the handful of spellings argparse reads
while it is still deciding what was asked for, in a module that imports nothing, each of them
the one definition of its name. ``identity.py`` makes an object
identity and writes one into a description file textually, so that ``ddd id --assign``
produces a diff of one line per object rather than a reformatted document. ``build_info.py``
is the hand-off from a build to an editor: which project description was configured, and
under which severity policy, neither of which any ``*.ddd.json`` file records.

``src/ddd/lsp/`` is a layer of its own rather than a smaller module: nine modules that speak
the language server protocol over a pipe, locate a json pointer in the bytes of a document
(``ranges.py``, which ``identity.py`` reuses rather than growing a second scanner), find the
projects a file belongs to and turn the findings into what an editor underlines. It is a
second front end over the same loader and analysis, and knows about no output format.
:doc:`editor_integration` describes what it offers a client.

The two contract pages describe the data that travels between the layers: the input file
formats under :doc:`data contracts <data_contracts>`, and the resolved form under
:doc:`data dictionary <data_dictionary>`.

The split is enforced by a test
-------------------------------

A layering that lives only in the documentation rots the first time somebody is in a hurry,
so DDD asserts it. ``tests/test_backends.py`` parses the layered modules - ``loading.py``,
``analysis.py``, ``ir.py``, ``diagnostics.py``, everything under ``backends/`` and
``plugins.py`` - with ``ast``, collects the ``ddd.*`` modules each one imports, and fails if
the import graph disagrees with the table above:

* ``loading.py``, ``analysis.py``, ``ir.py`` and ``diagnostics.py`` import no backend,
* nothing under ``backends/`` imports ``ddd.loading`` or ``ddd.analysis``,
* the c backend does not import the a2l backend, and the a2l backend does not import the
  c one,
* both backends satisfy the ``ddd.backends.base.Backend`` protocol, and every datatype
  is spelled by both of them, so a new datatype cannot be added to the contract while one
  output format silently has no name for it,
* ``plugins.py`` imports no loader, analysis or backend at runtime, so a plugin sees exactly
  what a backend sees, and the ``Backend`` protocol it names is only imported there under
  ``TYPE_CHECKING``.

A second test in the same file reads the text of ``src/ddd/models/`` and fails if a spelling
that belongs to a single output format - ``uint16_t``, ``UWORD``, ``COMPU_``, ``AXIS_PTS``,
``stdint`` - has leaked into the input contract. The one documented exception is
``src/ddd/models/reserved.py``, which lists the c keywords and the names ``<stdint.h>``
claims: which identifiers a c compiler takes for itself is a property of the input format,
because generating c is not optional in DDD. It is a file of its own precisely so that the
guard can stay strict about everything else.

.. note::
   The word ``measurement`` is deliberately not on that list. It is DDD's own term for an
   online value and part of the input file format; that the a2l keyword ``MEASUREMENT``
   happens to coincide with it is not a leak.

What a backend is
-----------------

A backend is anything with a ``name`` and a ``generate(dictionary, output_dir)`` method, as
described by the protocol in ``src/ddd/backends/base.py``:

.. code-block:: python

   @runtime_checkable
   class Backend(Protocol):
       """Turns a data dictionary into files."""

       name: str

       def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
           """Render every artefact of this backend; nothing is written to disk."""
           ...

That signature carries two decisions worth knowing. First, ``generate`` receives the resolved
:class:`ddd.ir.DataDictionary` and nothing else: no workspace, no diagnostic bag, no command
line arguments. Anything it needs about the project has to be a field of the contract, which
is what stops one output format from acquiring its own private view of what a project means.
Second, a backend *renders* but does not *write*. It returns fully rendered ``GeneratedFile``
objects, and the driver decides what happens to them, which is what makes three things
possible in one place rather than in every backend:

* two artefacts claiming the same path are refused with a message naming the backends
  involved, instead of one silently overwriting the other,
* a file whose content has not changed is left alone, so that a regeneration does not
  trigger a rebuild of everything downstream,
* ``--dry-run`` is a parameter of the writing step rather than a flag every backend has to
  honour correctly.

What a backend needs about the *run* rather than about the project is settled when it is
constructed, and the constructor is a backend's own business. That is where the two differ:

.. code-block:: python

   class CBackend:
       def __init__(
           self, template_dir: Path, options: COptions | None = None, generator: str = "ddd"
       ) -> None: ...

   class A2lBackend:
       def __init__(self, options: A2lOptions | None = None, generator: str = "ddd") -> None: ...

The template directory comes first for the c backend because it is the one argument that has
no default: a run without ``--template-dir`` is a usage error of ``ddd generate``, never a
fallback to a built-in set of templates, and there is nothing for the constructor to fall back
to either. The a2l backend takes no such argument at all, since its templates are part of the
package.

Adding an output format
~~~~~~~~~~~~~~~~~~~~~~~

A format DDD does not ship is a :doc:`plugin's <plugins>` backend: the project names the
plugin, ``ddd generate <name>`` runs it, and nothing inside the tool changes. Adding a
*built-in* one - a header for another language, a csv, an ARXML - means adding a package next
to the existing two and registering it as an artefact of the generate command:

#. Create ``src/ddd/backends/<format>/`` with a class exposing ``name`` and ``generate``.
   Follow the shape of the existing two: a ``model.py`` that turns the dictionary into
   whatever the templates want to iterate over, a ``types.py`` mapping every
   ``ddd.models.Datatype`` to the spelling of that format, and an ``options.py`` for what
   the command line can tune. Then decide where the templates come from, which is the one
   design question a new backend has to answer for itself: ship a ``templates/`` directory
   inside the package if the format is specified elsewhere, as a2l is, or take a template
   directory as the first constructor argument if the format is a house style, as c is. Use
   ``ddd.backends.base.make_environment`` and ``render_template`` either way, so the jinja
   settings - in particular ``StrictUndefined``, which turns a typo in a template into an
   error rather than into an empty string - are the same as everywhere else.
#. Export it from ``src/ddd/backends/__init__.py``.
#. Register the artefact in ``src/ddd/cli.py``: an entry in the tuple ``_build_parser``
   turns into the ``generate`` subcommands, a ``render_<format>`` flag set by
   ``_add_generate_arguments`` together with the options that configure it, and the branch
   of ``_command_generate`` that appends the backend when the flag is set. Add the name to
   ``BUILT_IN_GENERATED`` in ``src/ddd/plugins.py`` as well: any other lowercase name is
   taken for a plugin's artefact before the parser is built, and a name that is both is a
   conflicting subparser. That tuple is the one to edit rather than ``BUILT_IN_ARTEFACTS``,
   which derives from it by adding ``all``; the choices of ``--without`` and what
   ``ddd artefacts`` reports as built-in are read from it too, so both follow on their own.
#. Add it to the protocol assertion in ``tests/test_backends.py``, and to the lists of
   artefacts ``tests/test_cli.py`` and ``tests/test_plugins.py`` enumerate. The import graph
   tests pick the new package up on their own, so the first thing the suite will tell you is
   whether the new backend reached into the front end.

The front end changes in those two places and nowhere else, and neither of the existing
backends is touched. ``cmake/Ddd.cmake`` asks for ``all`` on every build, so the new artefact
reaches every cmake project from the moment it exists; a build that does not want it needs a
new option on ``ddd_generate`` appending ``--without <format>``, the way ``NO_A2L`` appends
``--without a2l``.

Diagnostics never raise
-----------------------

The loader and the analysis report through a ``ddd.diagnostics.DiagnosticBag`` and do
not raise. An exception escaping from the middle of a run would end it with a bare python
message and throw away everything already collected, and the author would fix one problem,
run again, and be told about the next one. Collecting instead means a run reports as much as
it can: a file that cannot be read, a file that is not utf-8, json nested deeper than python
can parse, a path the operating system cannot represent - each comes back as a located
finding, and the rest of the project is still checked.

Two consequences for anyone adding a check. A check is an entry in the ``CHECKS`` registry
in ``src/ddd/diagnostics.py`` - an identifier, a default severity and a one line description
- plus the code that adds the finding; the identifier is part of the public interface of the
tool, since it is what ``-W`` and ``--strict`` address and what a ci job matches on, and
``ddd checks`` prints the registry as it stands (see :doc:`consistency checks
<consistency_checks>`). And a check that cannot be relaxed has to say so: the eight entries
marked ``overridable=False`` are the ones after which nothing further can be said about the
file, or the project, at all, and every other check has to survive being set to ``ignore``.

What the calibration tools actually implement
---------------------------------------------

Structured data can be written into an a2l two ways, and the choice is not a matter of taste.
ASAP2 has a typedef family - ``TYPEDEF_STRUCTURE``, ``STRUCTURE_COMPONENT``, ``INSTANCE`` - that
describes a structure once and instantiates it, which is the obvious fit for a project with
twenty instances of one type. The alternative is to flatten: one ordinary object per leaf, named
after the path to it, at the address of the instance plus the offset of the member.

The native form was tested against **CANape 15** before any of it was built, with hand written
a2l files, and it is not usable there:

* ``ASAP2_VERSION 1 71`` is **refused outright** - ``unknown ASAP2 version 1.71`` - so the
  version DDD declares cannot simply be raised. ``1 70`` is accepted.
* at ``1 61`` and ``1 70`` a file containing a ``TYPEDEF_STRUCTURE`` and two ``INSTANCE`` of it
  **loads without a warning and contains no objects at all**. Loading is not evidence of support.
* the grammar does know the keyword: a ``SYMBOL_TYPE_LINK`` inside the structure is a syntax
  error on its own line, not on the enclosing block, so the body is being parsed and validated.
  It accepts the shape and exposes nothing for it.
* a ``GROUP`` referencing members through their instance loads, and is **empty**.

So the a2l flattens, and two further constraints come out of the same exercise. Do not emit
``ASAP2_VERSION 1 71``, since ``1 61`` carries everything a flattened structure needs. And do not
rely on a tool to report a bad reference: CANape silently dropped one it could not resolve, which
means a mistake in a generated name costs an object with no diagnostic anywhere, and the burden
of catching it sits here.

INCA has not been tested. Since it is generally the more conservative of the two, flattening is
what a project targeting both can rely on.

The coverage gate
-----------------

Coverage runs with every test run, over statements **and** branches, and a gap fails the
run:

.. code-block:: text

   [tool.pytest.ini_options]
   addopts = "-q --cov --cov-report=term-missing --cov-fail-under=100"

   [tool.coverage.run]
   source = ["ddd"]
   branch = true

The reasoning is that a line nobody executes is a line nobody has ever seen behave - and in
a code generator, an unexercised branch means an output nobody has ever looked at. The two
consequences are worth stating plainly, because they change how the gate is met. The gate is
what found the dead code this project used to carry, in the shape of unused properties on
the analysis and contract types; the fix was deleting them, not writing tests for them. And
the paths that only a coverage run reaches - unreadable files, malformed json, relaxed
severities, odd float literals - are collected in ``tests/test_edge_cases.py`` rather than
being scattered through the suite that describes behaviour.

Five suites guard things a type checker cannot. ``tests/test_backends.py`` walks the import
graph, as described above. ``tests/test_cmake.py`` configures and builds the cmake module -
over the shipped example, over a collected project naming a plugin, over a hand written one
and over a project written to exercise the keywords of one call - with the ``cmake`` the
development requirements install, so that the module is held to
what it does rather than to what it says. A configure and a build cost seconds each, which
makes that file a third of the suite's runtime, so the classes whose tests ask several
questions of one tree configure and build it once, in a class-scoped fixture, and each test
reads one answer out of what it left behind. ``tests/test_hardening.py`` holds one test per defect that once
reached a customer-facing artefact or verdict - a transposed a2l array, a header that does
not compile, a legal name rejected, a description file that ended the run with a python
traceback - grouped by what was at stake rather than by module. ``tests/test_documentation.py``
asserts that every check identifier, every command, every object kind and every datatype is
named in ``README.md`` and in ``SPEC.md``, that the README invents no check that is not
registered, and that no link in either points at a file that no longer exists. And
``tests/test_transcripts.py`` re-runs the documentation: every ``$ ddd`` command a page runs
over the shipped examples, and the whole tutorial through ``bash``, has to print the lines the
page shows beneath it. A page that shows commands and runs none of them fails as well, unless
each of those commands ends in a comment marking it as an illustration, so that no page can
quietly leave the harness by naming files the examples do not ship. It is the stronger of the
two documentation guards - a claim about what the tool prints is checked against what it
prints - so a reworded diagnostic fails there first. What it does *not* run is counted rather
than left to be discovered: a page that runs one of its commands has the rest read as
illustrations, and ``SILENTLY_SHOWN`` in that file records how many such commands each page
has - 51 of the 170 shown, and three of the eighty-four runs pinning an exit status. A page
that gains one fails until somebody writes the new number down.

Running the checks
------------------

.. code-block:: bash

   python -m pytest              # the suite, the coverage gate and the documentation checks
   python -m pytest --no-cov     # quicker, while working on a single test
   python -m pytest --co --no-cov  # what would run, without the gate weighing a run of none
   python -m ruff check .
   python -m ruff format .
   python -m mypy

``mypy`` runs in strict mode over ``src/ddd`` and ``tools/`` with the pydantic plugin;
``ruff`` lints the sources, the tests, the release machinery and the documentation
configuration with a line length of 100. The whole suite takes a couple of minutes in a warm
checkout - longer in a fresh environment, where ``tests/test_cmake.py`` configures and builds
the module - so ``--no-cov`` and a ``-k`` are what a single test is worth running under, and
the whole of it is what a commit is worth running under. Not ``-q``: the ``addopts`` in
``pyproject.toml`` carry one already, pytest counts them, and a second drops the summary - the
"N passed" line and the coverage total both - leaving the exit code as the only statement of
what happened. And ``--no-cov`` beside ``--co``: coverage is in the ``addopts`` too, so a
collection-only run measures a run of nothing and prints ``Required test coverage of 100% not
reached`` before exiting 0, which reads as a failure and is not one.

Nothing in the suite skips, and a test in ``tests/test_documentation.py`` holds it to that:
no ``pytest.skip``, ``skipif``, ``importorskip`` or ``xfail`` anywhere under ``tests/``. A
test that skips reports success without having run, so what it covers is covered on somebody
else's machine and nowhere else. Two places used to do it. Validating the examples against
the committed schemas needed ``jsonschema``, and skipped everywhere except on the machine of
whoever happened to have it installed; it is a development dependency instead. A case about a
second spelling of an output directory made a directory junction, which is a windows feature,
and skipped on the ubuntu cells of the matrix - so the page said every cell ran everything
while a third of them ran that one nowhere. A platform makes the *spelling* of such a path
differ, not the behaviour under test, so ``tests/conftest.py`` offers ``directory_link``: a
junction on Windows, a symbolic link elsewhere, and a path whose ``resolve()`` is another path
on both.

The same file carries the positive controls under the guards that read the pages with a
regex. A guard looping over what a pattern found passes when it found nothing, which is how
the count of the checks whose severity is fixed went stale: the sentence it counts was
reworded, the pattern stopped matching, and the suite stayed green. So each such guard has a
test beside it asserting that the pattern still recognises something - and the two transcript
tests, which are parametrized over sets computed at import, have one too, because pytest
answers a parametrize over nothing with a skip rather than a failure.

The repository also ships a small linux image, which is what the generated c code is
actually compiled with - a generator whose output no compiler has ever accepted is a
generator with no evidence behind it. Run it from a WSL shell, where docker speaks linux
containers:

.. code-block:: bash

   docker compose run --rm test        # pytest with the coverage gate
   docker compose run --rm coverage    # same, plus build/htmlcov/index.html
   docker compose run --rm lint        # ruff check, ruff format --check and mypy
   docker compose run --rm compile     # generate, compile, link and verify the symbols
   docker compose run --rm cmake       # build examples/cmake through cmake/Ddd.cmake
   docker compose run --rm docs        # build this documentation

The image serves ``ddd gui`` too: an earlier stage of ``docker/Dockerfile`` compiles the pages,
and only the pages reach the image, installed with the package - no node. A service runs the
working tree, though, and with it the pages compiled there, if any - except ``gui``, which clears
``PYTHONPATH`` to run the image's own code and pages instead, over the checkout's project files
still: an edit made in the browser writes back into the working tree, the file keeping its owner
and permissions although the service runs as root like every other. ``docker compose up gui``
builds the image first, since the code it serves is the image's, and starts it listening beyond
the container's loopback and publishes the same port number on the
host's loopback, ``-p 127.0.0.1:8123:8123`` - a different one would misdirect the Host header
``ddd gui`` checks - so the address it prints opens in a browser there.

The ``compile`` service is the one that keeps the c backend honest. It generates the demo
project, writes one translation unit per generated header that includes it twice - which
proves that every header is self contained and that its include guard works - compiles
everything with ``-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow
-Wcast-qual -Wstrict-prototypes``, links all objects into one binary, and finally compares
``nm`` against ``ddd dump --format json`` so that every variable DDD promised is defined
exactly once and nothing else is. The last four steps run twice, once plain and once with
the conditional declarations enabled, so both states of a ``#if`` guarded variable are
covered. It renders the example templates, which is what makes them evidence rather than a
sketch: the set a project starts from is the set a compiler has accepted. ``TEMPLATES`` points
the service at any other directory, so a project can put its own templates through the same
treatment.

Continuous integration
----------------------

``.github/workflows/ci.yml`` runs the commands above - the suite with its coverage gate,
``ruff`` twice and ``mypy`` - on every push to ``master`` and every pull request, in two jobs,
and five more the commands above do not cover. ``extension`` installs node and the package,
runs ``npm ci``, ``npm test`` and ``npm run package`` in ``editors/vscode``, and uploads the
``.vsix`` it produced. Its tests start a real language server, which is why it installs the
python package as well as compiling typescript, and packaging the extension there proves that
the artefact a customer is handed can be produced at all.

``gui`` builds and tests the browser interface on ubuntu and windows: it installs the package and
node, generates the TypeScript types from ``ddd schema``, runs Biome, the type check and Vitest
with its coverage gate, compiles the pages, and drives them in Chromium against a real
``ddd gui`` with Playwright. On ubuntu it then builds the wheel and the sdist with the pages it
compiled, checks that the wheel carries them the way the release build checks its own, and
uploads both as ``ddd-tool-<commit>``: what installs a branch without node. The release build
still compiles the pages again, into the wheel it publishes - an artifact expires, and needs a
GitHub account to reach.

``container`` builds the image behind ``docker compose``, checks that the package installed in
it carries the pages of ``ddd gui`` and that neither node nor npm reached it, and runs the
``generate`` service in it. Nothing built the image for a long time, and it is the local
equivalent of every other job here: a ``COPY`` of a directory removed three releases earlier
failed the build on its first line, and every service with it, while ci stayed green - ci
installs the package itself and never came near the image.
The service run after it is the other half of what broke then: the image built, and the
service exited with a usage error from an option set two releases old. The five other services
are not run here; what they exercise is either covered by a job above or, for ``compile``, the
run a contributor does locally. The pages are asked for with ``python -I``, which leaves out
the working tree a service puts first on the path: a clean checkout has no compiled pages, so
without it the check would read the checkout rather than the image.

``dev-build`` and ``dev-publish`` put a development build of the last commit of every push to
``master``, and of every push to this repository's own pull requests, on TestPyPI, as
:ref:`development-builds` below describes.

The suite runs across a matrix of ubuntu and windows on python 3.12, 3.13 and 3.14, which is
the six combinations the classifiers in ``pyproject.toml`` advertise. That is not thoroughness
for its own sake: a path handling defect that only appeared on linux has already reached a
user of this project, having passed the whole suite on windows first. A test in
``tests/test_documentation.py`` keeps the matrix and those classifiers in agreement, so
advertising a new interpreter without testing it fails.

The two python jobs install the project with ``pip install -e ".[dev]"`` rather than running
it out of ``src`` - the extension job installs ``pip install -e .``, since what it needs is a
``ddd`` on the path to launch. That is deliberate too, and it is the cheapest check in the
file: it exercises the packaging metadata, which the tests themselves never touch, so a
dependency list that no longer builds fails here rather than for whoever installs the
distribution.

Style and types are checked once rather than per platform, since neither varies by platform.
``publish.yml`` runs the suite again before it builds a release, which is not redundant: a
release can be cut from a commit this workflow never saw, and an upload to an index is
permanent.

Nothing in the toolchain moves on its own. Every ``uses:`` is pinned by a major tag, the
extension's and the browser interface's lock files pin their dependencies exactly, and
``ruff`` and ``mypy`` are capped to a minor in ``requirements-dev.txt`` - those two are gates
rather than libraries, so a release of either fails the lint job on the day it is published
rather than on the day somebody upgrades it. What proposes the moves instead is
``.github/dependabot.yml``, weekly, for the actions, the requirements files, the extension and
the browser interface: a bump then arrives as a pull request that ci has already run, which is
the difference between upgrading a tool and discovering on a release day that one has moved on
without you. A test holds every action to one version across the three workflows, and both
caps to being caps.

.. _development-builds:

Development builds
~~~~~~~~~~~~~~~~~~

The last commit of every push to ``master``, and of every push to one of this repository's own
pull requests, is published to `TestPyPI <https://test.pypi.org/project/ddd-tool/>`_ as a
development build, so that such a commit installs with ``pip install`` - its compiled pages
included, and no Node.js anywhere - without the GitHub account an artifact needs, and after the
artifact has expired; TestPyPI is itself pruned now and then, though, so a development build is
no archive. A commit that was not the last of its push has no build of its own. A run in which
any other job fails publishes nothing, and neither does one that a newer push cancels before its
upload has begun; a ``dev-publish`` that fails once its upload has begun leaves on TestPyPI
whatever it had uploaded.

``dev-build`` waits for every other job of the run - ``test``, ``lint``, ``container``,
``extension`` and ``gui`` - so that a commit any of them fails is never a build anybody is
pointed at; a test holds a job added to ``ci.yml`` to joining the list. It checks the commit
out - a pull request's own head, not the merge ``gui`` tests it as - and fails at once, with an
error saying to merge ``master`` into the branch, when that head has no
``tools/dev_version.py``: a pull request whose branch was cut before development builds
existed. It then stamps the development version into the checkout, compiles the pages and
builds the wheel and the sdist as the release build does, type check included, and checks that
the wheel carries the pages. ``dev-publish`` uploads what it built, and writes the run's
summary. They are two jobs for the reason ``publish.yml`` builds a release in one job and
uploads it in another: ``npm ci`` runs the install scripts of every package the pages depend on,
and a build runs whatever its backend is, so none of that runs in the job that can ask for a
token to publish with. That job checks nothing out, and takes nothing it is handed on trust:
the version has to be this run's; ``dist/`` has to hold that version's wheel and sdist and
nothing else - a file left there for a later run's version would otherwise be uploaded under it,
and that run's own upload refused; and the wheel has to name this run's commit and declare
requirements an install line can print as they are. All of it is checked before the upload.

**The version is the next patch, as a development release numbered by the run.** After 0.10.0,
run 57 publishes ``0.10.1.dev57``. The commit cannot be part of the version: PEP 440 refuses
``0.10.0-<sha>``, and PyPI and TestPyPI both refuse a local label such as ``0.10.0+g<sha>``. The
build's metadata carries it instead, as the ``Commit`` link of the project, and the run's
summary maps the version to it. The base is the next patch because ``0.10.0.dev57`` would sort
before 0.10.0 itself, beneath the release every such commit came after. The run number grows
across every branch, so every run publishes a version of its own; a re-run keeps its number,
and turns ``skip-existing`` on. That is on for any second attempt, not only one where
``dev-publish`` itself had already failed: a first attempt that fails in a job ``dev-build``
waits for never reaches ``dev-publish`` at all, and the re-run that finally does reach it is on
``skip-existing`` as well - so it passes over a file already there under that version even
though it is trying to upload it for the first time. A first attempt skips nothing: a file
already on TestPyPI under its version came from another run, and the upload fails on it rather
than passing over it with a summary naming somebody else's build. So a first attempt whose
upload is refused because the file exists means investigate before re-running - not with
*Re-run failed jobs*, not with *Re-run all jobs*, and not by re-running ``dev-publish`` alone:
any second attempt would pass over the file and write a summary naming it as its own build.
Find out why the number was reused instead.
Renaming ``ci.yml`` is one way: it restarts the run numbers - and its registration below names
the file - so its uploads are refused until the numbers, or the next release, move past the
versions already published.

``tools/dev_version.py`` writes that version into the job's own checkout, and nothing it
rewrites is committed. It writes it into the three places the installed package compares at
run time: ``pyproject.toml``; ``src/ddd/__init__.py``, so that ``ddd --version`` prints ``ddd
0.10.1.dev57``, in the format it always has; and ``cmake/Ddd.cmake``, whose
``DDD_MODULE_VERSION`` the module compares with that output by exact string, refusing a tool of
any other release. Nothing compares the other spellings, listed under
:ref:`publishing-a-release`, at run time: the extension's manifest and lock file reach no
installed package, and the rest is prose - the README's included, which the wheel carries as
its description. The script refuses a version with no next patch, and a release candidate is
one: a run whose commit states a candidate in ``__version__`` fails ``dev-build`` - every run of
``master`` for as long as the candidate stands there - while a pull request branched before it
still builds. ``tests/test_documentation.py`` holds the script to all of this, and runs the
checks ``dev-publish`` makes.

The run's summary gives the two commands that install the build, for instance:

.. code-block:: text

   pip install "jinja2<4,>=3.1" "pydantic<3,>=2.7"
   pip install --no-deps --index-url https://test.pypi.org/simple/ ddd-tool==0.10.1.dev57

The first installs the runtime dependencies from PyPI; the second installs ddd-tool alone,
from TestPyPI. They are two on purpose: given both indexes at once, pip takes each name's
highest version from either, and anybody can upload a lookalike to TestPyPI. ``dev-publish``
writes both, and nothing of it is taken from ``dev-build`` unchecked: an output of a job can span
lines, and the build could have handed over one that closes the code fence and prints an
install line of its own. The first line is read off the ``Requires-Dist`` of the checked
wheel, by the runner's own python reading the workflow's own lines, and held to quoted
requirements of letters, digits and the signs a specifier needs - so a runtime requirement with
an environment marker, whose strings need quotes, would be refused until the pattern is widened
for it. The second is written from the version the job checked.

**The publisher is a third registration.** The upload authenticates with trusted publishing,
as a release does, so TestPyPI has to know this workflow as well as ``publish.yml``. Register,
on ``test.pypi.org``, project ``ddd-tool``, owner ``Sauci``, repository ``ddd``, workflow
``ci.yml`` and environment ``testpypi-dev``, which GitHub creates the first time the job names
it. Leave that environment without a deployment branch policy, since a pull request's run
publishes from it as well as a push to ``master``. Until the registration exists the upload
fails with ``invalid-publisher`` and every job before it passes; once it does, re-running the
run publishes it, as it does for a release.

Only this repository's runs publish. A pull request from a fork is given no token to publish
with, and a fork's own push to its ``master`` has no publisher, so both skip the two jobs rather
than failing at the upload; a dispatch publishes nothing either. Within the repository,
``testpypi-dev`` is anybody's who can push a branch, as every environment here is:
:ref:`publishing-a-release` says what that means for pypi.org, and what closes it.

Building this documentation
---------------------------

.. code-block:: bash

   pip install -e ".[docs]"
   sphinx-build -b html docs build/docs/html -W --keep-going

Warnings are errors, which matters more here than in most projects: the reference sections
are generated from the sources - ``autoprogram`` renders the command line from the argument
parser itself, ``autodoc_pydantic`` renders the file formats from the contracts - so a
renamed option or a changed field cannot leave its documentation behind, and a reference
that no longer resolves fails the build instead of quietly disappearing from the page.

Two programs have to be on the path as well, and each fails visibly rather than silently
dropping a figure: ``dot`` from graphviz draws the entity relationship diagram of every model
on the :doc:`file format pages <file_formats/index>`, and ``plantuml`` draws the ``.. uml::``
diagrams. Without a plantuml installation, ``docs/conf.py`` still names one, so the build
reports a warning per diagram - which under ``-W`` is a failure. Both are apt packages, and
both are in the image behind ``docker compose run --rm docs``, which carries the python
requirements above as well and is the way to build the documentation without installing any
of it.

Publishing this documentation
-----------------------------

``.github/workflows/docs.yml`` builds the html and publishes it to
`GitHub Pages <https://sauci.github.io/ddd/>`_. It runs on every pull request, and deploys on
two events: a push to ``master``, and a published release. The deployment is a push to the
``gh-pages`` branch with the workflow's own token, and Pages serves that branch directly;
nothing else authenticates, and no deployment environment is involved.

The site keeps one directory per version, and a menu in the bottom left corner of every page
switches between them:

.. list-table::
   :header-rows: 1

   * - Directory
     - Written by
     - Rewritten
   * - ``latest``
     - a push to ``master``
     - every push
   * - ``v0.5.0``, ``v0.6.0``, ...
     - publishing that release
     - never

Old documentation describes old code, so nothing rebuilds a released version. That is not
only a saving: a tag from two years ago would have to keep building under the sphinx of the
day, and the run that failed would be the one publishing the *current* release.

A build produces one version and the site is all of them, so the versions that are not being
built have to come from somewhere: the ``gh-pages`` branch holds them. The branch is the site
rather than an archive of it - Pages is configured to serve it, so the push at the end of the
job is the publish, and there is no second copy to disagree with. It used to be one of two
publishes, the branch and an artifact handed to ``deploy-pages``, and the two parted twice
without a red step anywhere; the run now ends by reading the page it published back from the
site, and fails if it is not served within five minutes. The branch is created by the first
deployment; there is nothing to set up in the repository.

The menu cannot be baked into a page at build time, or a version released today would be
missing from the menu of every page built before it - which is the menu somebody reading an
old page is looking at. So ``docs/_templates/versions.html`` renders an empty menu and
``docs/_static/js/versions.js`` fills it in on load from ``versions.json`` at the root of the
site, which the workflow rewrites from what is on disk on every deployment. A build with no
such file above it - a local one, a pull request one - shows no menu at all, which is honest:
there is nothing to switch to.

The root of the site redirects to the newest release rather than to ``latest``. Somebody
arriving without a version in the url wants the documentation of what they can install, not
``master``'s account of features that are not released yet - and not a release candidate
either: the newest *release* is the newest tag whose version carries nothing after the
numbers, so ``v0.10.0rc1`` is published, listed in the menu under its own version, and left
out of that choice until ``v0.10.0`` follows it. Before the first release there is nothing
else to land on, so the root points at ``latest``.

That rule is ``tools/site_versions.py``, which the deploy job runs, rather than a heredoc
inside the workflow: ``tests/test_documentation.py`` pins the orderings it produces - the
candidate, the release it leads to, and a hotfix on the older line published after it - which
is what nothing could do while it was a workflow step.

The workflow installs graphviz and plantuml from apt, so publishing needs nothing but a stock
runner: there is no prepared image to keep in step with the sources. Only html is built. A pdf
would want a LaTeX distribution, roughly a gigabyte of packages, and nothing asks for one -
``docs/conf.py`` still carries the LaTeX settings, so ``sphinx-build -M latexpdf docs output``
produces one for whoever does.

Two things are worth knowing before the first run.

**Pages has to be pointed at the branch by hand, once.** In *Settings* → *Pages*, set
*Source* to *Deploy from a branch* and choose ``gh-pages`` at its root. The workflow pushes
the branch whether or not anything serves it, so with the setting missing the push succeeds
and the *Read back what was published* step fails five minutes later, naming that setting.
There is nothing to change in the repository to fix it: correct the setting and re-run.

**A pull request builds but never deploys.** The deploy job names the branch and the release
event it publishes, rather than resting on the event alone, because a pull request from a
fork proposes arbitrary content: without that condition, opening one would be enough to
publish somebody else's revision as the product's documentation.

.. _publishing-a-release:

Publishing a release
--------------------

``.github/workflows/publish.yml`` builds, checks and uploads the distribution. It never
holds an API token: the upload authenticates with `trusted publishing
<https://docs.pypi.org/trusted-publishers/>`_, where GitHub mints a short lived OIDC token
and the index decides whether the claims in it match a publisher somebody registered.

Two things follow from that, and both have bitten this project.

**The two indices are separate registrations.** TestPyPI and PyPI are different services with
different accounts and different publisher configurations. A publisher registered on
``pypi.org`` has no effect whatsoever on ``test.pypi.org``, even though the pages look
identical. The workflow uploads to whichever the job names, so each needs its own:

.. list-table::
   :header-rows: 1

   * - field
     - ``test.pypi.org`` registration
     - ``pypi.org`` registration
   * - PyPI project name
     - ``ddd-tool``
     - ``ddd-tool``
   * - owner
     - ``Sauci``
     - ``Sauci``
   * - repository
     - ``ddd``
     - ``ddd``
   * - workflow name
     - ``publish.yml``
     - ``publish.yml``
   * - environment name
     - ``testpypi``
     - ``pypi``

The environment name is the field most easily got wrong, because it is the GitHub
*deployment environment* of the job rather than anything about the index: the job publishing
to TestPyPI declares ``environment: name: testpypi``, so the registration has to say
``testpypi`` too.

Until the project exists on an index, its registration is a **pending** publisher, which is
also what creates the project on first upload. Note what the page itself warns: a pending
publisher does not reserve the name, so anybody may take it first. Once the project exists
the registration becomes an ordinary publisher, and a project that already exists needs the
publisher configured *on the project* rather than as a pending one.

**The configuration is read at upload time, not at commit time.** A run that failed with
``invalid-publisher`` will succeed on a plain re-run once the registration is corrected -
there is nothing to change in the repository and no new commit to push.

A ``workflow_dispatch`` run with ``target: testpypi`` is the dry run; publishing to PyPI
happens on a published GitHub release tagged ``v<version>``, and the build refuses to go on
unless that tag is exactly ``v`` followed by the version in ``pyproject.toml``. The prefix is
checked rather than stripped, because the documentation site publishes a release under a
directory named after its tag and lists only the ones beginning with ``v``.

A dispatch with ``target: pypi`` runs only from a ``v*`` tag, and is checked against
``pyproject.toml`` there exactly as a release is. On any other ref the job is skipped: the
same run started on a branch would have built whatever that branch's ``pyproject.toml`` said
and uploaded it under no tag, with no ``.vsix`` and no documentation directory - and an index
accepts a file name once and for ever, so the only way back is the next version number.

**The version is spelled in ten files, and a test holds five of them together.**
``src/ddd/__init__.py`` is where it lives: ``docs/conf.py`` imports ``__version__`` rather than
restating it, and the banner of every generated file carries it from there. ``pyproject.toml``,
which the release tag is checked against, and ``editors/vscode/package.json``, which the
extension is packaged with, repeat it, and a test each asserts that they agree with
``__version__``. ``editors/vscode/package-lock.json`` records it twice more - in its own header
and in the entry for the root package - and a test now asserts that both agree with
``__version__`` as well. Nothing else would: what ``npm ci`` compares with the manifest is the
*dependencies*, not the root package's own version, so a bump that edits only the manifest
packaged a ``.vsix`` whose lock file still said the version before. ``cmake/Ddd.cmake`` states
it as ``DDD_MODULE_VERSION``, because the module refuses a ``ddd`` of another release and so
has to know its own - a release that bumps the package and not the module refuses itself - and
a test asserts that too. The other five files spell it out as text and nothing
derives it for them: the wheel file name in ``README.md`` and in :doc:`getting_started`, the two
``ddd --version`` transcripts of that page - only the first of which the transcript test re-runs,
since the second carries a trailing comment and is shown rather than run - and the banner of a
generated file quoted in :doc:`getting_started`, :doc:`generated_artefacts`,
:doc:`faq` and :doc:`templates`. Bumping the version means walking all ten in the release
commit.

The publishing jobs name a deployment environment - ``pypi`` and ``testpypi`` in
``publish.yml``, ``testpypi-dev`` in ``ci.yml``. As this repository stands, none carries a
deployment branch policy and none has a protection rule, so nothing in the settings decides
which ref may publish: the workflow does, and a workflow is whatever the ref it runs from says.
A pull request from one of this repository's branches runs that branch's own ``ci.yml``, and a
dispatch runs the dispatched branch's own ``publish.yml`` - where the condition keeping
``publish-pypi`` to a release or a ``v*`` tag lives, so a branch that edits it out publishes to
pypi.org. Anybody who can push a branch here can therefore publish to TestPyPI through
``testpypi-dev`` or ``testpypi``, and to pypi.org through ``pypi``. The development builds add no
route to pypi.org: the token ``ci.yml`` is given names ``ci.yml``, and the publisher on
``pypi.org`` names ``publish.yml`` and ``pypi`` alone. What stands between a pushed branch and
pypi.org is the ``pypi`` environment's protection, and today there is none.

That protection is the maintainer's to set, in *Settings* → *Environments* → ``pypi``: a
required reviewer, who approves every deployment to it, or a deployment rule limited to ``v*``
tags, under *Selected branches and tags*. Against somebody who can push a branch it is the only
lock, not a second one - the workflow's condition is theirs to edit. A tag rule stops a branch
but not a pushed tag, unless a tag ruleset also restricts who may create ``v*`` tags; a required
reviewer stops both. An environment restricted to the default branch instead is the whole of
what a release is not - a release runs from its tag - and rejects the release after a green
build, with *not allowed to deploy ... due to environment protection rules*.

Delivering the editor extension
-------------------------------

The same workflow packages ``editors/vscode`` and attaches the ``ddd-<version>.vsix`` to the
release. That asset is the whole of how the extension is delivered: a permanent url needing
no account and no network policy exception, installed with ``code --install-extension
ddd-<version>.vsix`` or through **Install from VSIX...** in the Extensions view.

The job runs after the tag check rather than beside it, because it names the file it uploads
after the tag; a test pins that ordering.

**It is deliberately not published to the Visual Studio Marketplace.** A step that would have
done so existed until 0.6.0 and never once worked: the marketplace has no equivalent of
trusted publishing, so it needed a personal access token from an Azure DevOps organisation
owning a ``sauci`` publisher, and neither the organisation nor the publisher was ever
created. It failed on every release it ran on while the rest of the pipeline reported success
around it, and four pages meanwhile told a customer to search the Extensions view for an item
that answered 404.

Publishing there again is a decision with a prerequisite, not a step to restore. The
publisher is created once at https://marketplace.visualstudio.com/manage against an Azure
DevOps organisation; its id has to be the ``publisher`` field of
``editors/vscode/package.json``, which is what makes the extension ``sauci.ddd``. The token
is a personal access token scoped *Marketplace* → *Manage*, issued against *All accessible
organizations* rather than a single one - a token scoped to one authenticates and is then
refused when it publishes, which reads as a wrong password rather than a wrong scope. It
expires within a year, and the failure lands on a release that has already uploaded to PyPI.
Whoever takes that on puts the install instructions back on the four pages at the same time;
a test refuses the two halves separately.

The browser interface
---------------------

``ddd gui`` serves pages compiled from ``gui/``, a Vite project in TypeScript and React, into
``src/ddd/gui/static/``. git ignores the compiled pages, and Node.js is needed where they are
compiled, never where ddd is installed. The release build compiles them before it builds the
wheel, which then carries them. The ``gui`` job of ci does the same and uploads the wheel as
``ddd-tool-<commit>``, so every branch ci runs on installs without Node.js as well, and
``dev-build`` does it again for the :ref:`development build <development-builds>` of the last
commit of a push to ``master`` or to a pull request, which TestPyPI serves to anybody. The image
behind ``docker compose`` compiles them in a build stage of its own, thrown away with its
Node.js: the image carries the pages and no Node.js. A source checkout needs Node.js 24 to build
them, with the package installed so that its types can be generated:

.. code-block:: text

   cd gui
   npm ci
   npm run schemas     # TypeScript types, from ddd schema all
   npm run build       # the pages, and third-party-licenses.txt beside them
   npm run watch       # rebuilds on every change; reload the page ddd gui serves

``npm run lint`` and ``npm run typecheck`` are the frontend's ruff and mypy, and ``npm test``
runs Vitest with a 100 % gate over the modules that hold logic - ``src/api``, ``src/lib`` and
``src/state``. The screens are covered by ``npm run e2e``: Playwright drives the real ``ddd gui``
over a copy of ``examples/demo``, started with the interpreter ``DDD_PYTHON`` names, and
``PLAYWRIGHT_CHANNEL=msedge`` drives the installed Edge on a machine without Playwright's own
Chromium. The build refuses a bundled package whose licence is not MIT, ISC, Apache-2.0,
BSD-2-Clause or BSD-3-Clause. The project screen's canvas is drawn with ``@xyflow/react`` and
laid out with ``@dagrejs/dagre``, both MIT like every other bundled package.
