Command line interface
======================

DDD has no daemon, no editor plug-in and no state of its own: everything it does happens
while a project is being built or delivered, so it is a plain command line tool that reads
json files, writes files or a report, and exits. That is what makes it usable from wherever
the build already lives - a makefile, a cmake project (see :doc:`build_integration`), a batch
file on an engineer's machine, or a ci job that never sees a terminal.

The same discipline governs the output. The findings - everything the tool has to say about
a project - are written to standard error, one line per finding followed by a summary, while
what a command actually produces (a listing, the dumped dictionary, a json schema, the list
of source files, completion candidates) goes to standard output. The two never mix, so
nothing has to be filtered out of a redirection: ``ddd dump project.ddd.json >
baseline.json`` archives the dictionary and nothing else, even on a run that had something to
say about it.

For a job that files findings rather than reads them, seven commands understand
``--format json``: ``check``, ``compare``, ``generate``, ``list``, ``dump``, ``sources`` and
``checks``. That leaves out ``schema``, ``cmake-dir`` and ``templates-dir``, whose output is
machine readable already. In json the diagnostics become part of the document the
command prints, next to whatever else it has to report:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates --format json
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
       ``ddd sources`` also exits ``1`` when the file it was pointed at cannot be read at all.
   * - ``2``
     - the invocation itself was wrong: an unknown command or option, a required option left
       out, an unknown check identifier or severity, an attempt to relax a check that cannot
       be relaxed, an output directory that cannot be
       written into. The project was never examined, so the absence of findings means nothing
       here.

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
       command and one exit code cover both questions.
   * - ``ddd compare BASELINE CANDIDATE``
     - report whether the candidate delivery can stand in for the baseline. Either side may be
       an archived dictionary or a project description.
   * - ``ddd generate FILE -o DIR -t TEMPLATES``
     - check the project and, if it is consistent, write the c sources and the a2l file into
       ``DIR``. ``-t`` names the directory of jinja2 templates the c sources are rendered
       from; it is required and has no default, because which files the project wants and
       what they look like is not something DDD can guess. ``--dry-run`` reports what would be
       written without writing anything, ``--force`` generates in spite of errors.
   * - ``ddd list FILE``
     - print the table of variables with their kind, datatype, unit, shape, initial value
       with its physical reading, producer and consumers - the quickest answer to "who
       writes this?".
   * - ``ddd dump FILE``
     - print the resolved data dictionary, the contract every backend consumes. This is what
       gets archived next to a delivery and handed to ``ddd compare`` later.
   * - ``ddd schema KIND``
     - print the json schema of ``component``, ``dictionary``, ``project``, ``sections``,
       ``types`` or ``units``, for an editor that offers completion inside a ``*.ddd.json``
       file or for a validator in a ci job; ``all`` writes every schema into a directory.
   * - ``ddd sources FILE``
     - list every description file the project is built out of, for the dependency list of a
       build system.
   * - ``ddd lsp``
     - run the language server, speaking the Language Server Protocol on stdin and stdout,
       so an editor reports the checks while a description file is being written; see
       :doc:`editor_integration`.
   * - ``ddd build-info FILE -o FILE``
     - record which project description a build runs DDD on and under which severity policy,
       the ``ddd-build.json`` an editor reads; ``ddd_generate()`` calls it at configure
       time, so a hand-rolled build is the only caller that needs it directly.
   * - ``ddd checks``
     - list every check with its identifier, its default severity and whether it can be
       relaxed.
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

The ``-t`` of ``generate`` has no default at all: an invocation that leaves it out is refused
rather than falling back to templates of DDD's own.

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen
   usage: ddd generate [-h] [-W CHECK=SEVERITY] [--strict] [--format {text,json}]
                       -o OUTPUT_DIR -t TEMPLATE_DIR [--const-inputs] [--no-a2l]
                       [--byte-order {little,big}] [--address-map ADDRESS_MAP]
                       [--dry-run] [--force]
                       project
   ddd generate: error: the following arguments are required: -t/--template-dir

A default would have to be somebody's house style, and a project that inherited one without
choosing it would find out which one only by reading the generated code; :doc:`templates`
makes that case at length. The a2l is unaffected, since its structure is ASAM's rather than
the project's: the a2l backend is internal and there is no template directory to give it.

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
file, and nobody reads its outputs yet, so the two checks about the other side of the
interface have to be switched off - while everything DDD can decide from the file alone still
applies.

.. code-block:: text

   $ ddd check examples/demo/components/controller.ddd.json
   examples/demo/components/controller.ddd.json#component.interface[0]: error[missing-producer]: 'ValueA' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[1]: error[missing-producer]: 'ValueB' is read by component 'Controller' but no component declares it as output
   examples/demo/components/controller.ddd.json#component.interface[2]: warning[unused-output]: 'ValueE' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[3]: warning[unused-output]: 'ValueF' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[4]: warning[unused-output]: 'StateA' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[5]: warning[unused-output]: 'ValueG' is written by component 'Controller' but read by nobody
   examples/demo/components/controller.ddd.json#component.interface[8]: warning[unused-output]: 'AxisA' is written by component 'Controller' but read by nobody
   2 errors, 5 warnings

   $ ddd check examples/demo/components/controller.ddd.json -W missing-producer=ignore -W unused-output=ignore
   ok: 12 variables in 1 component are consistent

A check identifier or a severity that DDD does not know is a usage error rather than a silent
no-op, because the opposite behaviour would let a typo in a ci script disable a check for
years without anybody noticing:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W no-such-check=ignore
   ddd: unknown check 'no-such-check'

   $ ddd check examples/demo/demo.ddd.json -W unused-output=nope
   ddd: unknown severity 'nope' for check 'unused-output', expected one of error, warning, info, ignore

Both exit with ``2``. Five checks cannot be relaxed at all - ``file-not-found``,
``json-syntax``, ``file-kind``, ``schema`` and ``include-cycle`` - because a file that cannot
be read has nothing further to say, and a run that carried on regardless would report the
absence of findings about a project it never saw. ``ddd checks`` marks those ``(fixed)``, and
an attempt to override one is refused rather than ignored:

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
fatal. This is what ``cmake/Ddd.cmake`` uses to make a hand written project description watch
its own components, described in :doc:`build_integration`.

With ``--format json`` the same list arrives as the ``sources`` array of a json document, next
to the diagnostics and their summary, exactly as the other commands report them.

Reference
---------

The reference below is generated from the argument parser of the tool itself, so an option
that is added, renamed or removed cannot leave its documentation behind.

.. autoprogram:: ddd.cli:_build_parser()
   :prog: ddd
