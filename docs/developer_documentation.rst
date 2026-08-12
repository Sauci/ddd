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
     - any output format
   * - ``src/ddd/ir.py``
     - **the contract**: the resolved data dictionary
     - how it is rendered
   * - ``src/ddd/backends/c/``
     - ``uint16_t``, literals, include guards, rendering the project's templates
     - a2l, the loader, the checks, what the generated files are called
   * - ``src/ddd/backends/a2l/``
     - ``UWORD``, compu methods, record layouts, its own templates
     - c, the loader, the checks

The last two rows are deliberately not symmetric. The a2l backend carries its own templates,
because ASAP2 is a format ASAM defines and a project has nothing to decide about it; the c
backend carries none, because what generated c looks like is a house style. It is constructed
with the template directory ``--template-dir`` names, works out what to render from the file
names it finds there, and therefore does not know before a run which files that run produces.
Those naming rules are part of the interface a project depends on: :doc:`templates` documents
them, and the module docstring of ``src/ddd/backends/c/backend.py`` states them again next to
the code that implements them.

Three smaller modules sit beside them. ``diagnostics.py`` holds the severity policy and the
registry of every check, and is what both the loader and the analysis report through.
``compare.py`` answers the directional question of whether one dictionary may replace
another, and is the second consumer of the contract next to the backends. ``cli.py`` is the
only module that knows about argument parsing, exit codes and where output goes; it is also
where the backends a ``ddd generate`` run uses are assembled.

The two contract pages describe the data that travels between the layers: the input file
formats under :doc:`data contracts <data_contracts>`, and the resolved form under
:doc:`data dictionary <data_dictionary>`.

The split is enforced by a test
-------------------------------

A layering that lives only in the documentation rots the first time somebody is in a hurry,
so DDD asserts it. ``tests/test_backends.py`` parses every module under ``src/ddd`` with
``ast``, collects the ``ddd.*`` modules each one imports, and fails if the import graph
disagrees with the table above:

* ``loading.py``, ``analysis.py``, ``ir.py`` and ``diagnostics.py`` import no backend,
* nothing under ``backends/`` imports ``ddd.loading`` or ``ddd.analysis``,
* the c backend does not import the a2l backend, and the a2l backend does not import the
  c one,
* both backends satisfy the ``ddd.backends.base.Backend`` protocol, and every datatype
  is spelled by both of them, so a new datatype cannot be added to the contract while one
  output format silently has no name for it.

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

Adding one - a header for another language, a csv, an ARXML - means adding a package next to
the existing two and touching nothing else:

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
#. Add it to the list of backends that ``_command_generate`` in ``src/ddd/cli.py`` builds,
   together with the option that selects or configures it.
#. Add it to the protocol assertion in ``tests/test_backends.py``. The import graph tests
   pick the new package up on their own, so the first thing the suite will tell you is
   whether the new backend reached into the front end.

Nothing in the front end changes, and neither of the existing backends is touched.

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
<consistency_checks>`). And a check that cannot be relaxed has to say so: the five entries
marked ``overridable=False`` are the ones after which nothing further can be said about the
file at all, and every other check has to survive being set to ``ignore``.

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

Three suites guard things a type checker cannot. ``tests/test_backends.py`` walks the import
graph, as described above. ``tests/test_hardening.py`` holds one test per defect that once
reached a customer-facing artefact or verdict - a transposed a2l array, a header that does
not compile, a legal name rejected, a description file that ended the run with a python
traceback - grouped by what was at stake rather than by module. ``tests/test_documentation.py``
asserts that every check identifier, every command, every object kind and every datatype is
named in ``README.md`` and in ``SPEC.md``, that the README invents no check that is not
registered, and that no link in either points at a file that no longer exists.

Running the checks
------------------

.. code-block:: bash

   python -m pytest              # the suite, the coverage gate and the documentation checks
   python -m pytest --no-cov     # quicker, while working on a single test
   python -m ruff check .
   python -m ruff format .
   python -m mypy

``mypy`` runs in strict mode over ``src/ddd`` with the pydantic plugin; ``ruff`` lints the
sources, the tests and the documentation configuration with a line length of 100. The suite
runs in a few seconds, so there is no reason to run anything less than all of it.

Nothing in the suite skips. A test that skips when a tool is absent reports success without
having run, and the one place that used to do it - validating the examples against the
committed schemas, which needs ``jsonschema`` - was skipping everywhere except on the machine
of whoever happened to have it installed. It is a development dependency instead.

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

The ``compile`` service is the one that keeps the c backend honest. It generates the demo
project, writes one translation unit per generated header that includes it twice - which
proves that every header is self contained and that its include guard works - compiles
everything with ``-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow
-Wcast-qual -Wstrict-prototypes``, links all objects into one binary, and finally compares
``nm`` against ``ddd list --format json`` so that every variable DDD promised is defined
exactly once and nothing else is. The last three steps run twice, once plain and once with
the conditional declarations enabled, so both states of a ``#if`` guarded variable are
covered. It renders the example templates, which is what makes them evidence rather than a
sketch: the set a project starts from is the set a compiler has accepted. ``TEMPLATES`` points
the service at any other directory, so a project can put its own templates through the same
treatment.

Continuous integration
----------------------

``.github/workflows/ci.yml`` runs exactly the commands above - the suite with its coverage
gate, ``ruff`` twice and ``mypy`` - on every push to ``master`` and every pull request.

The suite runs across a matrix of ubuntu and windows on python 3.12 and 3.13, which is the
four combinations the classifiers in ``pyproject.toml`` advertise. That is not thoroughness
for its own sake: a path handling defect that only appeared on linux has already reached a
user of this project, having passed the whole suite on windows first. A test in
``tests/test_documentation.py`` keeps the matrix and those classifiers in agreement, so
advertising a new interpreter without testing it fails.

Each job installs the project with ``pip install -e ".[dev]"`` rather than running it out of
``src``. That is deliberate too, and it is the cheapest check in the file: it exercises the
packaging metadata, which the tests themselves never touch, so a dependency list that no
longer builds fails here rather than for whoever installs the distribution.

Style and types are checked once rather than per platform, since neither varies by platform.
``publish.yml`` runs the suite again before it builds a release, which is not redundant: a
release can be cut from a commit this workflow never saw, and an upload to an index is
permanent.

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
both are in the image behind ``docker compose run --rm docs``, which is the way to build the
documentation without installing either.

Publishing this documentation
-----------------------------

``.github/workflows/docs.yml`` builds the html and publishes it to
`GitHub Pages <https://sauci.github.io/ddd/>`_. It runs on every pull request, and deploys on
two events: a push to ``master``, and a published release. The deployment authenticates the
same way the release upload does, with a short lived OIDC token rather than a stored secret.

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
   * - ``v0.2.0``, ``v0.3.0``, ...
     - publishing that release
     - never

Old documentation describes old code, so nothing rebuilds a released version. That is not
only a saving: a tag from two years ago would have to keep building under the sphinx of the
day, and the run that failed would be the one publishing the *current* release.

Since a deployment replaces the whole site, the versions that are not being built have to
come from somewhere. The ``gh-pages`` branch is that archive - storage rather than the
published thing, restored at the start of the job and pushed back at the end of it. Pages
still serves the artifact the workflow uploads, so its ``Source`` setting stays on
*GitHub Actions*. The branch is created by the first deployment; there is nothing to set up.

The menu cannot be baked into a page at build time, or a version released today would be
missing from the menu of every page built before it - which is the menu somebody reading an
old page is looking at. So ``docs/_templates/versions.html`` renders an empty menu and
``docs/_static/js/versions.js`` fills it in on load from ``versions.json`` at the root of the
site, which the workflow rewrites from what is on disk on every deployment. A build with no
such file above it - a local one, a pull request one - shows no menu at all, which is honest:
there is nothing to switch to.

The root of the site redirects to the newest release rather than to ``latest``. Somebody
arriving without a version in the url wants the documentation of what they can install, not
``master``'s account of features that are not released yet.

The workflow installs graphviz and plantuml from apt, so publishing needs nothing but a stock
runner: there is no prepared image to keep in step with the sources. Only html is built. A pdf
would want a LaTeX distribution, roughly a gigabyte of packages, and nothing asks for one -
``docs/conf.py`` still carries the LaTeX settings, so ``sphinx-build -M latexpdf docs output``
produces one for whoever does.

Two things are worth knowing before the first run.

**Pages has to be switched on by hand, once.** In *Settings* → *Pages*, set *Source* to
*GitHub Actions*. The workflow's token may deploy to a site but may not create one, so until
that setting is made the deployment step fails with a message about a missing Pages site.
There is nothing to change in the repository to fix it: correct the setting and re-run.

**A pull request builds but never deploys.** The deploy job names the branch and the release
event it publishes, rather than resting on the event alone, because a pull request from a
fork proposes arbitrary content: without that condition, opening one would be enough to
publish somebody else's revision as the product's documentation.

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
if that tag disagrees with the version in ``pyproject.toml``.
