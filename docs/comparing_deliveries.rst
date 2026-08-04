Comparing deliveries
====================

A project that passes :doc:`every consistency check </consistency_checks>` is internally
sound: its components agree with each other, every input has a producer, every reference
resolves. That verdict says nothing at all about the software already running in the field,
in a test bench or in somebody else's integration, and about whether the delivery being
prepared can be dropped in where that one sits today. The two are different questions, they
are wrong in different ways, and DDD answers them with two different commands.

Two questions, not one
----------------------

``ddd check`` answers **do these components fit together**. It reads the description files of
the project, resolves them into a :doc:`data dictionary </data_dictionary>` and reports every
disagreement it finds inside that one delivery. Everything it needs is on disk in front of
it, which is why it can run on a developer's machine before the first compilation.

``ddd compare`` answers **can this delivery replace the one already out there**. That is a
question about two deliveries, and it is *directional*: it asks whether everything the
previous delivery offered is still there and still means the same thing, not whether the two
are identical. A delivery that adds ten new measurements is a perfectly good replacement; a
delivery that quietly turns a ``uint16`` into a ``uint32`` is not, even though it is
internally just as consistent as its predecessor.

The two questions stay separate on purpose, because a project can be internally consistent
and still be an invalid replacement, and a project can be a faithful replacement while being
internally broken. Neither answer implies the other.

Why the second question needs an archived dictionary
----------------------------------------------------

The obvious way to compare two deliveries would be to compare their description files, but
the sources of the previous delivery have moved on. The working tree that produced it has
been committed over, the components have been renamed or split, the include patterns now
match different files, and the paths inside them point at a directory layout that no longer
exists. Reconstructing the released delivery from a version control tag is possible in
principle and unreliable in practice, and it is impossible altogether when the delivery came
from another company as a binary with an a2l next to it.

The artefact to archive is therefore not the sources but the **dictionary** they resolve to.
``ddd dump`` writes it as a single self-contained json document, with every value already
worked out: the shape of each object, the limits (as given, or as derived from the datatype
and the conversion), the owning component and the list of components that read it.

.. code-block:: bash

   ddd dump release/pressure.ddd.json > release/PressureLoop-1.4.0.json

.. code-block:: json

   {
     "name": "ValveDuty",
     "kind": "measurement",
     "datatype": "uint8",
     "description": "Commanded valve duty cycle",
     "unit": "%",
     "conversion": {
       "kind": "linear",
       "factor": 0.5,
       "offset": 0.0
     },
     "limits": {
       "min": 0,
       "max": 100
     },
     "shape": [],
     "init": null,
     "volatile": false,
     "condition": null,
     "references": {},
     "owner": "Controller",
     "consumers": [
       "Actuator"
     ],
     "local": false,
     "a2l": {
       "export": true,
       "format": null,
       "display_identifier": null
     }
   }

Nothing in that document refers to a file, a glob or a directory, so it keeps its meaning for
as long as the binary it was archived next to is in use. It carries a ``"format"`` version at
its top level, and its schema is published with ``ddd schema dictionary``, so a delivery
archived today stays readable by a later release of the tool and by tools DDD does not ship.

.. note::
   ``ddd dump`` writes the dictionary to stdout and its diagnostics to stderr, in both output
   formats. That is what makes ``ddd dump project.ddd.json > baseline.json`` safe: a second
   json document can never end up in the archived file.

The workflow
------------

Archiving happens once, at release time, next to the binary and the a2l that were released
with it. Comparing happens on every candidate that comes after it:

.. code-block:: bash

   ddd dump project.ddd.json > baseline.json               # at release time
   ddd compare baseline.json project.ddd.json              # later, for the next delivery
   ddd check project.ddd.json --baseline baseline.json     # both questions, one exit code

.. uml::

   left to right direction

   collections "working tree at release time\n(the ~*.ddd.json files)" as src_old
   collections "working tree today\n(the ~*.ddd.json files)" as src_new
   component "ddd dump" as dump
   artifact "PressureLoop-1.4.0.json\narchived next to the binary" as baseline
   component "ddd compare" as compare
   artifact "verdict\n(build gate)" as verdict

   src_old --> dump
   dump --> baseline : the resolved dictionary,\nself-contained
   baseline --> compare : baseline
   src_new --> compare : candidate
   compare --> verdict : can the candidate\nstand in for the baseline?

``ddd check --baseline`` exists because a ci job wants one command and one exit code. It runs
the consistency checks on the project and, on the same dictionary, the comparison against the
archived one, and reports both sets of findings together. ``ddd compare`` does the same for
its candidate side: when the candidate is a project description rather than a dump, its own
consistency findings are reported alongside the comparison.

**Either side may be a dump or a description.** ``ddd compare`` looks at what a file contains
rather than at its name, so an archived dictionary, a project description and a single
component description are all acceptable on either side. Comparing two archived dumps is the
release-to-release case, comparing a dump with the working tree is the daily case, and
comparing two working trees is how a branch is judged against the trunk it will be merged
into. Nothing has to be staged into a temporary file first.

The comparison checks
---------------------

Every difference between the two dictionaries is graded by what it costs the people who
already depend on the baseline. An error means their software is now wrong, whether or not it
still compiles; a warning means behaviour or tooling changes but no consumer becomes wrong;
information means the candidate offers something the baseline did not. The identifiers below
are the same kind of stable identifier as the consistency checks, and ``ddd checks`` prints
them together with everything else.

.. list-table::
   :header-rows: 1
   :widths: 12 26 62

   * - severity
     - check
     - reported when
   * - error
     - ``removed-object``
     - an object of the baseline is gone and somebody read it
   * - error
     - ``changed-interface``
     - kind, datatype, unit, scaling, shape, axes or locality of an object changed
   * - warning
     - ``removed-unused-object``
     - an object of the baseline is gone; no component read it
   * - warning
     - ``changed-storage``
     - the initial value or volatility of an object changed
   * - warning
     - ``narrowed-limits``
     - the physical limits of an object got tighter, so calibrated data may not fit
   * - warning
     - ``changed-owner``
     - another component produces the object now
   * - warning
     - ``changed-condition``
     - the preprocessor condition of an object changed
   * - warning
     - ``changed-a2l``
     - the a2l entry of an object changed
   * - warning
     - ``project-mismatch``
     - the two sides of a comparison describe differently named projects
   * - info
     - ``added-object``
     - the candidate declares an object the baseline did not

``changed-interface`` is one check rather than seven because the seven properties it covers -
kind, datatype, unit, conversion, shape, the axes an object refers to, and whether it is
component local - are the properties a consumer compiles against and calibrates against. Any
one of them changing makes the consumer wrong in the same way, and the message names which
ones differ. ``changed-storage`` covers the two properties that change how an object behaves
rather than what it means, the initial value and ``volatile``; ``changed-a2l`` covers the
export flag, the display format and the display identifier, which move labels around in a
calibration tool without touching the software.

``volatile`` is graded differently here than it is *inside* a project, where it is interface
and a disagreement is a ``definition-mismatch`` error - see :doc:`consistency_checks`. The
difference is who is left describing the object wrongly. Inside one project two components are
compiled together against one address, so one of them is compiled against an assumption that
does not hold. Between two deliveries there is only one answer at a time and every consumer is
regenerated and recompiled against it, so nobody is left wrong; what changed is how the object
behaves. On a calibration object, ``volatile`` losing
its ``true`` is more than a change of behaviour in the abstract: the compiler is then entitled
to fold the value it was built with into the code that reads it, so the parameter keeps its
address and its a2l entry but stops being tunable while the software runs.

Two removals are distinguished because they cost different things. An object that a component
read cannot simply disappear: the baseline names the components that read it, so DDD knows
that the software which was built against it no longer builds, and that is an error. An
object that no component read may still be named in a calibration dataset, in a measurement
configuration or in an external tool that addresses it by name. DDD cannot see any of those,
so its removal is a warning: it is reported so that somebody who can see them makes the
decision, rather than a build being failed on a suspicion.

A worked example
----------------

The example below is a small project called ``PressureLoop``, with three components: a
``Sensor`` producing the raw measurements, a ``Controller`` computing a valve duty cycle from
them, and an ``Actuator`` consuming that duty cycle. The layout is the ordinary one, a
project file next to a directory of components:

.. code-block:: text

   release/
     pressure.ddd.json           the project
     components/
       sensor.ddd.json
       controller.ddd.json
       actuator.ddd.json

The delivery that went out
~~~~~~~~~~~~~~~~~~~~~~~~~~

``Sensor`` publishes three measurements and keeps one calibration parameter to itself:

.. code-block:: json

   {
     "component": {
       "name": "Sensor",
       "declarations": [
         {
           "scope": "output",
           "definition": {
             "name": "PressureRaw",
             "kind": "measurement",
             "description": "Manifold pressure",
             "datatype": "uint16",
             "unit": "kPa",
             "conversion": { "factor": 0.1 },
             "limits": { "min": 0, "max": 400 },
             "volatile": false
           }
         },
         {
           "scope": "output",
           "definition": {
             "name": "TemperatureRaw",
             "kind": "measurement",
             "description": "Manifold temperature",
             "datatype": "sint16",
             "unit": "degC",
             "conversion": { "factor": 0.1 },
             "limits": { "min": -40, "max": 150 },
             "volatile": false
           }
         },
         {
           "scope": "output",
           "definition": {
             "name": "SupplyVoltage",
             "kind": "measurement",
             "description": "Sensor supply voltage",
             "datatype": "uint16",
             "unit": "V",
             "conversion": { "factor": 0.001 },
             "limits": { "min": 0, "max": 16 },
             "volatile": false
           }
         },
         {
           "scope": "local",
           "definition": {
             "name": "FilterGain",
             "kind": "parameter",
             "description": "Low pass gain of the pressure signal",
             "datatype": "uint8",
             "conversion": { "factor": 0.01 },
             "limits": { "min": 0, "max": 1 },
             "init": 50,
             "volatile": false
           }
         }
       ]
     }
   }

``Controller`` reads ``PressureRaw`` and ``TemperatureRaw`` and produces ``ValveDuty``
(``uint8``, ``%``, factor 0.5, limits 0 to 100); ``Actuator`` reads ``ValveDuty`` and
``SupplyVoltage``. The project is consistent, so it is released, and its dictionary is
archived under the name of the release:

.. code-block:: text

   $ ddd check release/pressure.ddd.json
   ok: 5 variables in 3 components are consistent

   $ ddd dump release/pressure.ddd.json > release/PressureLoop-1.4.0.json

The delivery that wants to replace it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Development continues in ``work/``, and by the time the next delivery is prepared five things
have changed. ``PressureRaw`` was widened from ``uint16`` to ``uint32`` to leave room for a
finer resolution later. ``TemperatureRaw`` was dropped, because the controller now reads the
temperature over the bus instead. The limits of ``ValveDuty`` were tightened from 0 .. 100 to
0 .. 80, to protect a valve that turned out not to like being driven fully open. The limits
of ``SupplyVoltage`` were relaxed from 0 .. 16 to 0 .. 18, so that an 18 V supply variant fits.
And a new measurement, ``AmbientPressure``, was added.

Each of those is a defensible change, and the candidate passes the consistency checks exactly
as its predecessor did, because the components were all updated together:

.. code-block:: text

   $ ddd check work/pressure.ddd.json
   ok: 5 variables in 3 components are consistent

Against the archived dictionary, the same five changes look rather different:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json
   work/pressure.ddd.json: error[changed-interface]: 'PressureRaw' is not the same object any more (datatype: uint32 != uint16), read by Controller
   work/pressure.ddd.json: error[removed-object]: 'TemperatureRaw' is gone, but was read by Controller
   work/pressure.ddd.json: warning[narrowed-limits]: 'ValveDuty': limits tightened from [0, 100] to [0, 80]
   work/pressure.ddd.json: info[added-object]: 'AmbientPressure' is new in PressureLoop (measurement, produced by Sensor)
   2 errors, 1 warning, 1 info
   pressure.ddd.json cannot replace PressureLoop-1.4.0.json

Four findings for five changes. Widening ``PressureRaw`` is an error because every consumer
was compiled against a two-byte object and a calibration tool reads two bytes at its address;
removing ``TemperatureRaw`` is an error because the baseline records that ``Controller`` read
it. Tightening ``ValveDuty`` is a warning, because the code is unaffected but a calibration
dataset holding 90 % no longer fits inside the new range. Adding ``AmbientPressure`` is
information, since nothing that worked against the baseline can be disturbed by an object it
never knew about. And relaxing the limits of ``SupplyVoltage`` produces nothing at all, for
the reason given two sections further down.

The last line names the two **files**, not the two projects, because two deliveries of one
project share its name and naming the projects would print the same word twice.

An object that nobody read
~~~~~~~~~~~~~~~~~~~~~~~~~~

Suppose instead that the only change is the removal of ``FilterGain``, the calibration
parameter that ``Sensor`` declared ``local`` and that therefore no other component ever read:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json
   work/pressure.ddd.json: warning[removed-unused-object]: 'FilterGain' is gone; no component read it, but a calibration dataset or an external tool still might
   1 warning
   pressure.ddd.json can replace PressureLoop-1.4.0.json

No component stops linking, so this is not the error that ``TemperatureRaw`` was, and the
delivery is still a valid replacement. It is not nothing either: the object had a label in
the a2l, a value in every calibration dataset and possibly a line in a test bench
configuration, and all of those now refer to something that has ceased to exist. The message
says so in as many words, and the decision is left to the reader.

Both questions, one exit code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ci job normally does not want to run two commands and combine two exit codes.
``ddd check --baseline`` runs the consistency checks and the comparison over the same
resolved dictionary, and reports everything in one list. Here the five-change candidate
additionally reads a ``ValvePosition`` that nobody produces:

.. code-block:: text

   $ ddd check work/pressure.ddd.json --baseline release/PressureLoop-1.4.0.json
   work/components/actuator.ddd.json#component.declarations[2]: error[missing-producer]: 'ValvePosition' is read by component 'Actuator' but no component declares it as output
   work/pressure.ddd.json: error[changed-interface]: 'PressureRaw' is not the same object any more (datatype: uint32 != uint16), read by Controller
   work/pressure.ddd.json: error[removed-object]: 'TemperatureRaw' is gone, but was read by Controller
   work/pressure.ddd.json: warning[narrowed-limits]: 'ValveDuty': limits tightened from [0, 100] to [0, 80]
   work/pressure.ddd.json: info[added-object]: 'AmbientPressure' is new in PressureLoop (measurement, produced by Sensor)
   work/pressure.ddd.json: info[added-object]: 'ValvePosition' is new in PressureLoop (measurement, produced by nobody)
   3 errors, 1 warning, 2 infos

The consistency findings point at the declaration that caused them, down to the json pointer
inside the file, while the comparison findings point at the project as a whole, because a
difference between two dictionaries belongs to the delivery rather than to one line of one
description file.

Limits: widening is silent, narrowing is not
--------------------------------------------

Limits are the one property where the direction of the change decides the verdict, and that
is why ``SupplyVoltage`` produced no finding above. Its range grew from 0 .. 16 V to
0 .. 18 V, and every value the baseline permitted is still permitted, so there is nothing a
consumer or a calibration dataset can trip over. Reporting it would train the reader to
ignore the check.

The opposite direction is a warning, because a value that used to be legal may not be any
more. A calibration dataset written against the baseline can hold a value outside the new
range, an operator can have a test case that drives the signal there, and a calibration tool
will refuse the write or clip it. Neither the compiler nor the linker has anything to say
about it, which is exactly why the tool must:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json
   work/pressure.ddd.json: warning[narrowed-limits]: 'PressureRaw': limits tightened from [0, 400] to [0, 250]
   1 warning
   pressure.ddd.json can replace PressureLoop-1.4.0.json

That run exits ``0``: a narrowing is worth knowing about and worth a conscious decision, but
it is not by itself a reason to refuse the delivery. A project that wants it to be one turns
it into an error, either individually with ``-W narrowed-limits=error`` or for every warning
at once with ``--strict``.

A symptom is not reported under its cause
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tighter limits are very often a *consequence* of something bigger, and reporting the
consequence next to the cause buries the cause. When the interface of an object has changed,
the narrowing that follows from it is therefore not reported separately. The next section
shows the same 400 to 250 narrowing as above, this time accompanied by a rescaled conversion,
and the ``narrowed-limits`` warning is gone: there is one thing to fix, and once it is fixed
the limits question can be asked again on its own terms.

A rescaled conversion is an error
---------------------------------

Of everything the comparison looks at, a changed conversion is the one that deserves the most
attention, because it is the failure that compiles, links, runs, and reports every value
wrong by a constant factor. Suppose the resolution of ``PressureRaw`` is improved from
0.1 kPa per count to 0.01 kPa per count, and its limits are brought down to 250 kPa to match
what the new raw range can express. The datatype is untouched, so every consumer still
compiles and every access is still to a two-byte object at the same address. The project is
internally consistent, because all its components were updated together:

.. code-block:: text

   $ ddd check work/pressure.ddd.json
   ok: 5 variables in 3 components are consistent

Nothing in the build says a word. What has happened is that a calibration dataset from the
previous delivery, a logged measurement file, a test limit written into a test bench and a
threshold in a diagnostic tool now all mean ten times what they used to. The comparison is
the only place where that can be caught, so it is an error and not a warning:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json
   work/pressure.ddd.json: error[changed-interface]: 'PressureRaw' is not the same object any more (conversion: linear(factor=0.01, offset=0) != linear(factor=0.1, offset=0)), read by Controller
   1 error
   pressure.ddd.json cannot replace PressureLoop-1.4.0.json

The differing properties are spelled out candidate first and baseline second, so
``factor=0.01 != factor=0.1`` reads as "it is 0.01 now, it was 0.1 before". The narrowing of
the limits from 400 to 250 is not listed: it is the symptom of the rescaling, and it is the
rescaling that has to be discussed.

.. warning::
   Rescaling a released object is not a change that can be made compatible by editing the
   description files, because the incompatibility lives in every artefact that was produced
   against the previous scaling. Either the previous scaling is kept, or the object is given
   a new name so that the old and the new value are visibly two different things.

When the baseline is the wrong file
-----------------------------------

A comparison against the wrong archived dump does not fail. It produces a confident, fully
formed report of hundreds of removals and changes that means nothing at all, and the time
lost to reading it is the point of the ``project-mismatch`` warning. Two deliveries of one
project share the project name, so when the two sides name different projects, the most
likely explanation is that the wrong file was picked up:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json
   work/pressure.ddd.json: error[changed-interface]: 'PressureRaw' is not the same object any more (datatype: uint32 != uint16), read by Controller
   work/pressure.ddd.json: error[removed-object]: 'TemperatureRaw' is gone, but was read by Controller
   work/pressure.ddd.json: warning[narrowed-limits]: 'ValveDuty': limits tightened from [0, 100] to [0, 80]
   work/pressure.ddd.json: warning[project-mismatch]: the baseline describes project 'PressureLoop' and the candidate describes 'AirLoop'; the comparison below only makes sense if that rename was intended
   work/pressure.ddd.json: info[added-object]: 'AmbientPressure' is new in AirLoop (measurement, produced by Sensor)
   2 errors, 2 warnings, 1 info
   pressure.ddd.json cannot replace PressureLoop-1.4.0.json

The comparison is carried out anyway, and it is a warning rather than an error, because
renaming a project is a legitimate thing to do and the report is then exactly what the reader
wants. It is a warning that should be looked at before anything below it is believed.

A baseline that cannot be read at all is a different matter, and it stops the run:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.3.0.json work/pressure.ddd.json
   release/PressureLoop-1.3.0.json: error[file-not-found]: in the baseline: file 'release/PressureLoop-1.3.0.json' does not exist
   1 error

The ``in the baseline:`` prefix is there so that a missing or malformed file on the reference
side is never mistaken for a problem with the delivery being judged.

The baseline's own findings are not findings of this run
--------------------------------------------------------

When the baseline is given as a project description rather than as a dump, DDD has to analyse
it to obtain its dictionary, and that analysis produces findings about *that* delivery: an
output nobody read two releases ago, a component that has since been removed, a naming
convention that has since been tightened. Those findings are not this run's business. Reported
here they would be attributed to the candidate, they would appear twice whenever both sides
are the same tree, and a clean delivery could be failed because of the state of its
predecessor.

They are therefore collected in a bag of their own and dropped. Here is an older working tree
whose ``ValveDuty`` was read by nobody:

.. code-block:: text

   $ ddd check v1.3/pressure.ddd.json
   v1.3/components/controller.ddd.json#component.declarations[2]: warning[unused-output]: 'ValveDuty' is written by component 'Controller' but read by nobody
   1 warning

Used as the baseline of a comparison, that warning does not reappear:

.. code-block:: text

   $ ddd compare v1.3/pressure.ddd.json release/pressure.ddd.json
   pressure.ddd.json can replace pressure.ddd.json

The one exception is an error that stops the baseline from being read in the first place, as
in the missing-file example above: those are carried over, because they explain a comparison
that could not happen at all.

In a build pipeline
-------------------

``ddd compare`` and ``ddd check --baseline`` follow the same conventions as every other
command that produces findings: ``0`` when the run is clean, ``1`` when there are findings of
error severity, ``2`` on a usage error, and ``--format json`` for a machine readable report
carrying the same identifiers, severities and messages. In the text format the findings, the
summary and the verdict line all go to stderr and stdout is left empty; with ``--format json``
the report is the whole of stdout and the verdict line is dropped, since a json document that
a job is about to parse must not have a sentence appended to it.

Severities are tuned the same way as everywhere else, so a project that has decided a
narrowing is acceptable but wants the new objects out of its build log can say so:

.. code-block:: text

   $ ddd compare release/PressureLoop-1.4.0.json work/pressure.ddd.json -W narrowed-limits=ignore -W added-object=ignore
   work/pressure.ddd.json: error[changed-interface]: 'PressureRaw' is not the same object any more (datatype: uint32 != uint16), read by Controller
   work/pressure.ddd.json: error[removed-object]: 'TemperatureRaw' is gone, but was read by Controller
   2 errors
   pressure.ddd.json cannot replace PressureLoop-1.4.0.json

A pipeline that treats the comparison as a release gate rather than as a report runs it with
``--strict``, which turns every warning into an error, so that a narrowed limit, a changed
owner or a moved a2l entry also has to be acknowledged before the delivery goes out.

The remaining piece is discipline about the archive itself. The dump has to be produced from
the same sources that produced the binary, stored with it, and named after the release, so
that the question "which delivery is this candidate replacing" has a file as its answer rather
than a memory. Everything else about the comparison follows from that one habit.

.. note::
   ``ddd compare`` reports the difference between two data dictionaries, and a dictionary
   describes data rather than code. A delivery whose comparison is clean can still behave
   differently, because its algorithms changed; what a clean comparison guarantees is that
   everything built, calibrated and measured against the previous delivery still addresses the
   same objects, with the same layout, the same scaling and the same meaning.
