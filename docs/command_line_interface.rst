Command line interface
======================

DDD is a plain command line tool: it reads json files, writes files or a report, and exits,
and everything a build or a delivery needs from it happens in one such run. That is what
makes it usable from wherever the build already lives - a makefile, a cmake project (see
:doc:`build_integration`), a batch file on an engineer's machine, or a ci job that never sees
a terminal. The one command that does not exit is ``ddd lsp``, the language server an editor
keeps running (see :doc:`editor_integration`), and the one file the tool leaves behind for
its own use is the ``ddd-build.json`` that ``ddd build-info`` writes for that server.

The same discipline governs the output. The findings - everything the tool has to say about
a project - are written to standard error, one line per finding followed by a summary, while
what a command actually produces (a listing, the dumped dictionary, a json schema, the list
of source files) goes to standard output. The two never mix, so
nothing has to be filtered out of a redirection: ``ddd dump project.ddd.json >
baseline.json`` archives the dictionary and nothing else, even on a run that had something to
say about it.

For a job that files findings rather than reads them, eight commands understand
``--format json``: ``check``, ``compare``, ``generate``, ``list``, ``dump``, ``sources``,
``artefacts`` and ``checks``. That leaves out ``schema`` and ``build-info``, whose output is json already,
``lsp``, which speaks json-rpc, ``cmake-dir`` and ``templates-dir``, which print one path, and
``id``, which reports the files it skipped and one total rather than findings. In json the
diagnostics become part of the document the command prints, next to whatever else it has to
report:

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen -t examples/templates --format json
   {
     "diagnostics": [],
     "summary": {
       "error": 0,
       "warning": 0,
       "info": 0
     },
     "generated": [
       {
         "path": "build/gen/ddd_globals.c",
         "status": "created"
       },
       {
         "path": "build/gen/ddd_globals.h",
         "status": "created"
       },
       ...
       {
         "path": "build/gen/DemoDevice.a2l",
         "status": "created"
       }
     ]
   }

The one exception is ``ddd dump``, whose standard output is itself the payload: there the json
diagnostics go to standard error, so that both formats leave the dictionary alone.

The exit code is the same everywhere, which lets a build system treat DDD like a compiler:

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - code
     - meaning
   * - ``0``
     - the command did what it was asked and found nothing worth reporting.
   * - ``1``
     - findings: at least one diagnostic of severity ``error`` survived the severity policy.
       ``ddd sources`` and ``ddd artefacts`` also exit ``1`` when the root file cannot be read
       at all, and ``ddd id`` when one of the files it was given was not readable as json and
       had to be skipped, which it reports without a diagnostic.
   * - ``2``
     - the command line itself was wrong: a missing or malformed argument, an unknown
       severity, or an unknown check that names no plugin, in ``-W``, a fixed check
       overridden, or a missing ``-t`` where the c sources are part of the run - raised
       before any analysis, so the project was never examined and nothing but the error
       is printed. A usage error raised by a step that follows the analysis instead - a
       plugin hook that raises, an override naming a plugin check no loaded plugin
       registers, a ``--renames`` file or an artefact that cannot be written, an address
       map that cannot be read, ``--plugin`` refused beside a description, or a run that
       would write nothing - reports the findings of the run first, in the requested
       format, before the error follows; the exit code is still ``2``.

The commands
------------

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - command
     - purpose
   * - ``ddd check FILE``
     - run every consistency check on a project or on a single component; with ``--baseline``
       also answer whether that project can still replace a published delivery, so that one
       command and one exit code cover both questions, and with ``--standalone`` judge a
       component on its own, holding back the checks that need the rest of the project.
   * - ``ddd compare BASELINE CANDIDATE``
     - report whether the candidate delivery can stand in for the baseline. Either side may be
       an archived dictionary or a project description; ``--plugin`` loads the plugins of an
       archived candidate, since only a project description names its own, and ``--renames``
       also writes the old-to-new name pairs the identities revealed, for migrating datasets
       and recordings.
   * - ``ddd generate c|a2l|all|<plugin> FILE -o DIR``
     - check the project and, if it is consistent, write the named artefact into ``DIR``:
       ``c`` renders the c sources, ``a2l`` writes the a2l file, ``all`` produces both and
       the artefact of every plugin the project names that provides one, and the name of such
       a plugin runs its backend alone. Each
       artefact takes only its own options - ``-t`` names the directory of jinja2
       templates the c sources are rendered from, required wherever c is rendered and with no
       default, because which files the project wants and what they look like is not
       something DDD can guess; ``--address-map`` and ``--byte-order`` belong to the a2l.
       ``all`` alone takes ``--without c`` or ``--without a2l``, repeatable, which leaves that
       built-in artefact out while still producing the plugins' - the run a build wants when
       the a2l is written later, once the addresses are known. Naming ``c`` instead is not the
       same thing: it produces no plugin artefact at all, and says nothing about it.
       Subtracting an artefact takes its options with it, so ``--without a2l`` beside an
       ``--address-map`` is refused rather than quietly ignored, and a run that has subtracted
       the c neither wants nor accepts ``-t``.
       ``--dry-run`` reports what would be written without writing anything, ``--force``
       generates in spite of errors.
   * - ``ddd list FILE``
     - print the table of variables with their kind, datatype, unit, shape, initial value
       with its physical reading, producer and consumers - the quickest answer to "who
       writes this?".
   * - ``ddd dump FILE``
     - print the resolved data dictionary, the contract every backend consumes. This is what
       gets archived next to a delivery and handed to ``ddd compare`` later.
   * - ``ddd id --assign FILE...``
     - write an ``id`` into every producing declaration of the given description files that
       has none, editing them in place; a declaration that has one is left alone, so a second
       run changes nothing. The identity is what lets ``ddd compare`` report a rename as a
       rename, and what ``missing-id`` asks for.
   * - ``ddd schema KIND``
     - print the json schema of ``component``, ``constants``, ``dictionary``, ``project``,
       ``rasters``, ``sections``, ``types`` or ``units``, for an editor that offers completion
       inside a
       ``*.ddd.json`` file or for a validator in a ci job; ``all`` writes every schema into
       a directory; ``--plugin`` closes the ``extensions`` property of ``component`` and
       ``project`` over the named plugins' models.
   * - ``ddd sources FILE``
     - list every file the project is built out of - the description files and the modules of
       the plugins it names - for the dependency list of a build system. It reports its
       findings without letting them change its exit code.
   * - ``ddd artefacts [FILE]``
     - list the artefacts ``generate`` accepts for this project: the built-in ``c`` and
       ``a2l``, and the name of every plugin it names that provides one. What each writes is
       not listed, because a plugin's file names follow from the resolved project rather than
       from the plugin alone - ``ddd generate all --dry-run`` reports those. A plugin that
       provides no backend is no artefact of its own; it is named in a note rather than left
       out in silence, which would read as the plugin having failed to load. Such a plugin is
       not idle: the block it contributes is part of the vocabulary a project's own templates
       read, and those are rendered by ``c``. With ``--plugin`` and no file it answers the same question for a
       build that has not assembled its project description yet.
   * - ``ddd lsp``
     - run the language server, speaking the Language Server Protocol on stdin and stdout,
       so an editor reports the checks while a description file is being written; see
       :doc:`editor_integration`.
   * - ``ddd build-info FILE -o FILE``
     - record which project description a build runs DDD on and under which severity policy,
       the ``ddd-build.json`` an editor reads; ``ddd_generate()`` calls it at configure
       time, so a hand-rolled build is the only caller that needs it directly.
   * - ``ddd checks``
     - list every check with its identifier, its default severity, whether it can be relaxed
       (``(fixed)`` if not), whether it needs every component of a project (``(project)``)
       and whether it grades a delivery comparison rather than one project (``(comparison)``);
       ``--plugin`` lists a named plugin's own checks after the built-in ones.
   * - ``ddd cmake-dir``
     - print the directory holding ``Ddd.cmake``, so that a ``CMakeLists.txt`` finds the
       integration module of the installation it is actually using.
   * - ``ddd templates-dir``
     - print the directory holding the example c templates, to copy into a project as a
       starting point for its own. They are an example and not a default: no run of
       ``generate`` falls back to them.

``FILE`` is a project description or a single component description in every command that
takes one. A component checks, lists, dumps and generates on its own, which is what lets a
supplier verify a component long before an integrator ever sees it.

The ``-t`` of the c-rendering artefacts has no default at all: an invocation that renders c
without it is refused rather than falling back to templates of DDD's own.

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen
   ddd: the c sources are part of this run, so -t/--template-dir is required

A default would have to be somebody's house style, and a project that inherited one without
choosing it would find out which one only by reading the generated code; :doc:`templates`
makes that case at length. The a2l is the opposite case, since its structure is ASAM's rather
than the project's: the a2l backend is internal and there is no template directory to give
it - which is why ``ddd generate a2l``, the run a build repeats after linking to fill the
addresses in, does not even accept one.

``cmake-dir`` and ``templates-dir`` exist for a related reason. Neither the cmake module nor
the example templates have a fixed path once DDD is installed - a wheel, an editable install
and a source checkout put them in three different places - so a project asks the tool it is
actually running where they are instead of hard-coding a guess:

.. code-block:: text

   $ ddd templates-dir
   /home/you/ddd/examples/templates

How both directories are used from a ``CMakeLists.txt`` is in :doc:`build_integration`.

Severity options
----------------

``check``, ``compare``, ``generate``, ``list`` and ``dump`` all reach the same analysis, so
they all take the same two options for deciding how loud a finding is: ``-W CHECK=SEVERITY``
(repeatable, also spelled ``--severity``) sets one check to ``error``, ``warning``, ``info``
or ``ignore``, and ``--strict`` reports every warning as an error.

The reason the policy lives on the command line rather than in the description files is that
the same finding means different things in different places. A component checked on its own
has no counterpart: the components producing its inputs are by definition not part of the
file, nobody reads its outputs yet, and the types, units, sections, constants and rasters it
names are declared in files it was not handed - so the checks that need the rest of the
project have to be held back, while everything DDD can decide from the file alone still
applies. That is what ``ddd check --standalone`` does, in one option rather than in a list of
``-W`` a build has to keep in step with the registry; :doc:`consistency_checks` names the
checks it covers, and an explicit ``-W`` on the same run still wins over it.

.. code-block:: text

   $ ddd check examples/demo/components/controller.ddd.json
   examples/demo/components/controller.ddd.json#component.interface[0]: error[missing-producer]: 'ValueA' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[1]: error[missing-producer]: 'ValueB' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[2]: warning[unused-output]: 'ValueE' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[3]: warning[unused-output]: 'ValueF' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[4]: warning[unused-output]: 'StateA' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[5]: warning[unused-output]: 'StateName' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[6]: warning[unused-output]: 'ValueG' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[10]: warning[unused-output]: 'AxisA' is written by component 'Controller' but read by nobody
   2 errors, 6 warnings

   $ ddd check examples/demo/components/controller.ddd.json --standalone
   ok: 14 variables in 1 component are consistent

A check identifier or a severity that DDD does not know is a usage error rather than a silent
no-op, because the opposite behaviour would let a typo in a ci script disable a check for
years without anybody noticing:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W no-such-check=ignore
   ddd: unknown check 'no-such-check'

   $ ddd check examples/demo/demo.ddd.json -W unused-output=nope
   ddd: unknown severity 'nope' for check 'unused-output', expected one of error, warning, info, ignore

Both exit with ``2``. Eight checks cannot be relaxed at all - ``file-not-found``,
``json-syntax``, ``file-kind``, ``schema``, ``include-cycle``, ``include-depth``,
``plugin-not-found`` and
``plugin-invalid`` - because a file that cannot be read has nothing further to say, a
project cannot be interpreted without the plugins it names, or an include tree DDD refuses
to follow stays unread whatever the finding is reported as - and a run that carried on
regardless would report the absence of findings about a project it never saw. ``ddd checks``
marks those ``(fixed)``, and an attempt to override one is refused rather than ignored:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W schema=ignore
   ddd: the severity of check 'schema' cannot be changed

``--strict`` is the other end of the same dial: it turns every warning into an error, which is
what a delivery build wants, while the daily build of the same project stays readable. The
full list of checks, with the reasoning behind each default severity, is in
:doc:`consistency_checks`.

The sources of a project
------------------------

A project description does not name its components on the command line; it pulls them in
through ``includes``, possibly through wildcards, and possibly through further project files.
A build system that made the generated code depend on the project file alone would therefore
be wrong in the ordinary case: editing a component would change nothing the build can see, and
the image would happily link yesterday's globals and ship yesterday's a2l.

``ddd sources`` closes that gap. It prints one absolute path per line: the project file
itself and every description it includes however deeply:

.. code-block:: text

   $ ddd sources examples/demo/demo.ddd.json
   /home/you/ddd/examples/demo/components/controller.ddd.json
   /home/you/ddd/examples/demo/components/sensor_hub.ddd.json
   /home/you/ddd/examples/demo/components/user_interface.ddd.json
   /home/you/ddd/examples/demo/demo.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/event_logger.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/logging.ddd.json

The paths are absolute and always written with forward slashes, on Windows as well, so the
list can be pasted into a makefile, a ninja file or a cmake dependency list without being
translated first, and a file reached over two different include paths appears once.

The command is deliberately more tolerant than the others: a project whose interfaces disagree
still has a well defined set of source files, and a build system asking what to watch deserves
an answer even while the project does not check out. Only a file that cannot be read at all is
fatal. Tolerant is not silent: a finding the load turned up - a missing include, say - is
reported on stderr after the listing, so a configure step hears about it from the run that
found it rather than from whichever DDD command the build runs next. This is what
``cmake/Ddd.cmake`` uses to make a hand written project description watch its own components,
described in :doc:`build_integration`.

With ``--format json`` the same list arrives as the ``sources`` array of a json document, next
to the diagnostics and their summary, exactly as the other commands report them.

Reference
---------

The reference below is generated from the argument parser of the tool itself, so an option
that is added, renamed or removed cannot leave its documentation behind.

.. autoprogram:: ddd.cli:_build_parser()
   :prog: ddd
