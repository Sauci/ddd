File formats
============

Everything DDD reads is json, and every file it reads has to be named ``*.ddd.json``. Plain
json says nothing about who owns a file: a repository of any size already contains
``package.json``, ``compile_commands.json``, launch configurations and test fixtures, and a
description that hides among them is a description nobody finds. The double extension makes a
DDD file recognisable at a glance to a human, and matchable with a single pattern by a build
script, an editor or a linter - which is also how a project collects its components in the
first place, since ``"includes": ["components/*.ddd.json"]`` only works if the naming is a
rule rather than a habit. A file with any other name is reported under the ``file-extension``
check:

.. code-block:: text

   $ ddd check plain.json
   plain.json: error[file-extension]: 'plain.json' is a DDD description file and has to be named '*.ddd.json'
   1 error

It is an error rather than a hard failure, so a project migrating an existing set of files can
relax it for as long as the rename is under way, and lower it back afterwards:

.. code-block:: text

   $ ddd check plain.json -W file-extension=warning
   plain.json: warning[file-extension]: 'plain.json' is a DDD description file and has to be named '*.ddd.json'
   plain.json#component: info[empty-component]: component 'Plain' declares no variable
   1 warning, 1 info

The second run says more than the first, and the reason is worth knowing early: reading the
files and analysing them are two phases, and the analysis does not start while the reading
phase has reported an error. There is no point resolving references between components that
could not all be read, and a hundred consequential findings would bury the one that has to be
fixed first. So a run that fails to read something reports exactly what stopped it, and the
rest of the checks appear once it is out of the way.

What kind of file this is
-------------------------

DDD does not ask the file name what a file contains; the **top level key** decides. A file
whose top level key is ``project`` is a :doc:`project description <project>`, one whose top
level key is ``component`` is a :doc:`component description <component>`, one whose top level
key is ``types`` is a :doc:`structured datatype description <types>`, and one whose top level
key is ``naming`` is a :doc:`naming convention </naming_conventions>`. Nothing else appears at
that level, and a file has to carry exactly one of them.

Detecting the kind from the content rather than from the path is what lets ``includes`` name
components and sub-projects in the same list, and what lets ``ddd check`` be pointed at either
a whole project or a single component file without being told which of the two it is getting.
The price is that a file with two top level keys is ambiguous, so it is refused rather than
guessed at, and a file with none of them is refused with the keys it does have printed next to
the message, because the usual cause is a file that was never meant for DDD at all:

.. code-block:: text

   $ ddd check both.ddd.json
   both.ddd.json: error[file-kind]: file has 'project' and 'component' at the top level; it must have exactly one
   1 error

   $ ddd check neither.ddd.json
   neither.ddd.json: error[file-kind]: missing top level key, one of 'project', 'component', 'types' (found: components, version)
   1 error

Unknown keys are rejected
-------------------------

Every object in every description file is closed: a key DDD does not know is an error, not
something quietly ignored. The reason is that the alternative fails silently and in the worst
possible way. A misspelled ``definiton`` leaves a declaration without the definition it was
meant to carry, a misspelled ``volatille`` produces a variable the compiler is free to cache
in a register, and a misspelled ``limits`` puts the full range of the datatype into the a2l and
lets a calibration engineer enter a value the software cannot handle - all three from a file
that looked perfectly correct in review. Closing the objects turns every one of those into a
finding that names the offending key and points at it:

.. code-block:: text

   $ ddd check typo.ddd.json
   typo.ddd.json#component.declarations[0].definition: error[schema]: Field required
   typo.ddd.json#component.declarations[0].definiton: error[schema]: Extra inputs are not permitted (got: {'name': 'ValueA', 'datatype': 'uint8'})
   2 errors

The location after the ``#`` is a path into the json document rather than a line number,
because a line number in a file that is often generated or reformatted means very little,
whereas ``component.declarations[0].definiton`` is exactly where the key sits whatever the
formatting. Both halves of the mistake are reported: the key that should not be there, and the
key that is now missing because of it.

.. note::
   ``schema`` is one of the five checks whose severity cannot be changed, along with
   ``file-not-found``, ``json-syntax``, ``file-kind`` and ``include-cycle``. A file that
   cannot be interpreted has nothing further to say, and a component whose description failed
   to validate is not added to the project at all - so the remaining checks are never handed a
   half-read file to draw conclusions from. The full list is on the
   :doc:`consistency checks </consistency_checks>` page.

The json itself is read strictly as well. ``NaN``, ``Infinity`` and ``-Infinity``, which
python's json reader would otherwise accept, are refused: none of them is json, and none of
them survives the trip to an output, since there is no c literal and no a2l number for either.
NaN is worse than merely unrepresentable, because every comparison against it is false, so a
NaN limit would pass every range check in silence instead of failing one. A byte order mark in
front of the file is accepted, on the other hand, since it is what several Windows editors and
PowerShell redirection put there and the file is otherwise perfectly good json.

The schema is published
-----------------------

The pages that follow are the prose form of a contract the tool publishes in machine readable
form as well. ``ddd schema`` prints the json schema of each file format, so an editor can
offer completion and validation while a description is being written, and a ci job can
validate the files without running DDD at all:

.. code-block:: bash

   ddd schema project      # the project description
   ddd schema component    # the component description, and every kind of data object in it
   ddd schema types        # the structured datatype description
   ddd schema naming       # the naming convention
   ddd schema dictionary   # the resolved data dictionary, the contract the backends consume

``-o FILE`` writes to a file instead of to stdout, which is the form a build script uses:

.. code-block:: text

   $ ddd schema project -o project.schema.json
   wrote project.schema.json

The first four describe the files you write; the last describes what DDD makes of them and
is documented with the :doc:`data dictionary </data_dictionary>`. The closed objects described
above appear in all of them as ``"additionalProperties": false``, so a validating editor
rejects a misspelled key at the moment it is typed rather than at the next build.

.. toctree::
   :maxdepth: 2

   project
   component
   variable_definition
   conversions
   types
