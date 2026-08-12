Project description
===================

A project is a named set of components and sub-projects. It carries no data of its own,
because the data belongs to the components that produce and consume it; what it carries is the
answer to the only question a component cannot answer alone - *which components are supposed
to fit together*. That question has no single answer in a code base where several images are
built out of an overlapping set of components, which is why the membership lives in a file of
its own rather than in the components, and why a component never names the project it belongs
to.

The project file is what a build script points DDD at, and it is the file whose name ends up
on the generated a2l. ``examples/demo/demo.ddd.json`` is a complete one:

.. code-block:: json

   {
     "project": {
       "name": "DemoDevice",
       "description": "Demonstration project showing every DDD feature",
       "includes": [
         "components/*.ddd.json",
         "subsystems/logging/logging.ddd.json"
       ]
     }
   }

.. code-block:: text

   $ ddd check demo.ddd.json
   ok: 20 variables in 4 components are consistent

The keys
--------

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - Identifier of the project. It is not decoration: the generated a2l file is called
       ``<name>.a2l`` and the ``PROJECT`` and ``MODULE`` inside it are called ``<name>`` too,
       so this is the name the calibration engineer sees in the measurement tool. It has to be
       usable as an identifier - letters, digits and underscore, not starting with a digit,
       at most 128 characters.
   * - ``description``
     - ``""``
     - Free text. It becomes the long identifier of the a2l ``PROJECT``, its ``HEADER`` and
       its ``MODULE``, so it is worth writing one sentence that means something to whoever
       opens the file in a calibration tool.
   * - ``includes``
     - ``[]``
     - Paths to the component and sub-project files that make up the project, relative to
       this file. Wildcards are expanded.

The identifier rule is tighter than what a c compiler would accept, and deliberately so:
ASAP2 1.6.1 limits an identifier to 128 characters, and a name DDD cannot write into the a2l
is of no use in a project that generates one. The tighter of the two rules is the one that is
enforced everywhere, so a name that passes the check cannot fail later in a backend.

An ``includes`` list may be left out entirely. ``{"project": {"name": "Bare"}}`` is a valid
project with no members, and DDD says so rather than treating it as a mistake:

.. code-block:: text

   $ ddd check bare.ddd.json
   ok: 0 variables in 0 components are consistent

includes
--------

Each entry of ``includes`` is a path, and every path in a description file is relative to
**the file that contains it** rather than to the current directory. That is what makes a
project relocatable: a subsystem can be moved, vendored or included as a git submodule
without a single path being rewritten, and two people running the tool from different
directories read the same set of files. An absolute path is taken as it stands, for the case
where a component genuinely lives outside the project tree.

Wildcards
~~~~~~~~~

Shell style wildcards are expanded: ``*`` for any part of a name, ``?`` for a single
character, and ``**`` for any number of directory levels. With ``components/*.ddd.json``,
adding a component to the project is a matter of adding its file - nobody has to remember to
edit the project as well, and nobody can forget to.

.. code-block:: json

   {
     "project": {
       "name": "Wildcards",
       "includes": ["**/*.ddd.json", "c/comp?.ddd.json"]
     }
   }

.. code-block:: text

   $ ddd check top.ddd.json
   ok: 2 variables in 2 components are consistent

One file is deliberately left out of a pattern's matches: the project file that contains the
pattern. It sits exactly where a
``*.ddd.json`` pattern next to the project would sweep it up, and it is not an include - a
project including itself would be a cycle. Excluding it is what lets the shortest possible
project file work at all.

A pattern that matches nothing is reported, because the usual cause is a directory that was
renamed or a component that never arrived:

.. code-block:: text

   $ ddd check empty.ddd.json
   empty.ddd.json#project.includes[0]: error[include-empty]: pattern 'variants/*.ddd.json' matches no file
   1 error

``include-empty`` is an error by default but can be relaxed, because a pattern that is
legitimately empty in one variant of a project is a normal thing to allow - a project built
for several targets may have an ``optional/*.ddd.json`` that only some of them fill.

Components and sub-projects in the same list
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``includes`` does not distinguish between components and other projects. The kind of every
included file is detected from its top level key, so a subsystem developed by a separate team
can be delivered as a project of its own and pulled in as a single entry. The demo does
exactly that: ``subsystems/logging/logging.ddd.json`` is a project, and it brings its own
component with it.

.. code-block:: json

   {
     "project": {
       "name": "Logging",
       "description": "Sub project of its own, developed by a separate team",
       "includes": [
         "event_logger.ddd.json"
       ]
     }
   }

The nesting has no depth limit and no effect on the result: the components of a sub-project
become components of the including project, and are checked against all the others exactly as
if they had been listed directly. What the sub-project keeps is its own file layout and its
own relative paths, which is the point - it can be checked and delivered on its own, and it
does not need to know who includes it.

A file reached twice is loaded once
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Include graphs in a real project are rarely trees. Two subsystems commonly share a component,
and both list it; a wildcard in one project and an explicit path in another commonly land on
the same file. DDD resolves every path to a canonical absolute form before using it, so the
two spellings are recognised as the same file and it is loaded once:

.. code-block:: json

   { "project": { "name": "Top",   "includes": ["left.ddd.json", "right.ddd.json"] } }
   { "project": { "name": "Left",  "includes": ["shared/*.ddd.json"] } }
   { "project": { "name": "Right", "includes": ["shared/common.ddd.json"] } }

.. code-block:: text

   $ ddd check top.ddd.json
   ok: 1 variable in 1 component are consistent

Without that rule the component would be loaded twice under the same name and the run would
fail with ``duplicate-component`` - a finding about the shape of the include graph rather than
about anything wrong with the project. Diamond shaped graphs are therefore not merely
tolerated but expected.

The check that does fire is the one that matters: two **different** files declaring the same
component name. That is a real collision, since a component name decides the name of the
generated header, and the second file would silently overwrite the first:

.. code-block:: text

   $ ddd check project.ddd.json
   second.ddd.json#component: error[duplicate-component]: component 'Sensing' is declared twice
       note: first.ddd.json#component: first declared here
   1 error

Cycles are reported, not followed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A project that includes a project that includes the first one is a mistake that is easy to
make when subsystems are refactored, and it is one a naive loader would answer with a hang or
a stack overflow. DDD carries the chain of projects it is currently inside, and reports the
cycle as an ordinary finding, naming the whole chain so that the entry to remove is obvious:

.. code-block:: text

   $ ddd check a.ddd.json
   b.ddd.json#project.includes[0]: error[include-cycle]: include cycle: a.ddd.json -> b.ddd.json -> a.ddd.json
   1 error

``include-cycle`` is one of the checks whose severity cannot be relaxed. The others are
relaxable because a project may reasonably decide it can live with the finding; there is no
way to live with a cycle, since following it is the only alternative and it does not
terminate.

What the project is built out of
--------------------------------

The set of files that were actually read is more than the project file, and a build system
needs all of them to know when the generated artefacts are out of date. ``ddd sources`` prints
them, one absolute path per line, sorted and without duplicates - the root file, every
sub-project and every component:

.. code-block:: text

   $ ddd sources demo.ddd.json
   /home/you/ddd/examples/demo/components/controller.ddd.json
   /home/you/ddd/examples/demo/components/sensor_hub.ddd.json
   /home/you/ddd/examples/demo/components/user_interface.ddd.json
   /home/you/ddd/examples/demo/demo.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/event_logger.ddd.json
   /home/you/ddd/examples/demo/subsystems/logging/logging.ddd.json

This is the list that has to become the dependency list of the generation step. Depending on
the project file alone would be wrong in the direction that hurts: editing a component would
not regenerate anything, and the build would carry on with headers describing a project that
no longer exists. The :doc:`cmake integration </build_integration>` wires this up on its own.

.. note::
   ``ddd check`` and ``ddd generate`` accept a **component** file wherever they accept a
   project file, which is what lets a component be checked before it is integrated. There is
   no project around it, so the inputs it declares have no producer; add
   ``-W missing-producer=ignore`` for that run. The generated a2l is then named after the
   component instead of after a project.
