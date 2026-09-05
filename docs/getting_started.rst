Getting started
===============

DDD manages the **global variables** through which the components of an embedded software
project talk to each other. Every component describes, in a small json file, the variables it
produces, the variables it consumes and the variables it keeps to itself; DDD collects those
descriptions, checks that all components agree about every shared variable, and generates the
c code that allocates the data as well as the a2l file that measurement and calibration tools
read. Because the definitions then come from a single place, the access rules stop being a
matter of discipline: a component can only reach a variable that DDD put into the header
generated for it.

This page installs the tool and walks through a complete two-component project, from the
first json file to the generated sources and to the diagnostic you get when the two components
disagree. Everything shown here is the actual output of the tool; typing along takes about ten
minutes and needs nothing but python.

Installation
------------

DDD is a python package and needs **python 3.12 or newer**; its only runtime dependencies are
pydantic, which parses and validates the description files, and jinja2, which renders the
generated artefacts. Both are installed with it, and nothing else is required - in particular
no compiler, since DDD writes c code but never builds it.

.. code-block:: bash

   pip install ddd-tool                              # from an index
   pip install ./ddd_tool-0.7.0-py3-none-any.whl     # from a delivered wheel, no network

The second form is the one to use behind a firewall or in an air-gapped build environment: the
wheel carries everything DDD needs apart from pydantic and jinja2, which have to be reachable
in some form as well. Once the installation succeeded, the tool answers with the release it
was built from, and that release is what the header of every generated file mentions:

.. code-block:: text

   $ ddd --version
   ddd 0.7.0

.. note::
   The distribution is called ``ddd-tool`` because the name ``ddd`` was already taken on the
   index. Only the name of the distribution differs: the command is ``ddd``, the importable
   package is ``ddd``, and the description files are ``*.ddd.json``. Nothing else in this
   documentation ever refers to ``ddd-tool`` again.

Running from a source checkout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The examples of this documentation live in the source distribution rather than in the wheel,
and while evaluating the tool it is often convenient not to install anything at all. From a
checkout or an unpacked sdist, the package runs directly out of ``src``:

.. code-block:: text

   $ PYTHONPATH=src python -m ddd --version
   ddd 0.7.0

``PYTHONPATH=src python -m ddd`` and ``ddd`` are the same program invoked in two ways, and
every command shown below works with either. The transcripts use the installed form for
readability; if you follow along in a checkout, put ``PYTHONPATH=src python -m`` in front of
each of them. A checkout also gives you a bigger project to look at than the one built on this
page - ``examples/demo/demo.ddd.json`` exercises every kind of data object DDD knows:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json
   ok: 20 variables in 4 components are consistent

Your first project
------------------

The project built here is a cabin thermostat made of two components. **SensorHub** reads the
temperature sensor and publishes the conditioned value; **Controller** reads that value and
decides when to heat. That is the smallest arrangement in which the interesting question
arises at all - one component owns a variable, another one depends on it - and it is the
arrangement DDD exists for.

Create a directory for it, with a subdirectory for the components. Nothing about this layout is
prescribed; it merely lets the project file collect its members with a single pattern:

.. code-block:: text

   thermostat/
   +- thermostat.ddd.json          the project
   +- components/
   |  +- sensor_hub.ddd.json       the component that produces
   |  +- controller.ddd.json       the component that consumes
   +- templates/                   the c templates, copied in a moment

The project description
~~~~~~~~~~~~~~~~~~~~~~~

A project is a name and a list of members. It carries no data of its own, because the data
belongs to the components, and it is the file a build script points DDD at.

.. code-block:: json

   {
     "project": {
       "name": "Thermostat",
       "description": "A cabin thermostat built out of two components",
       "includes": ["components/*.ddd.json"]
     }
   }

The paths in ``includes`` are relative to the file that contains them, so the project can be
moved as a whole, and the shell wildcards ``*``, ``?`` and ``**`` are expanded, so adding a
component is a matter of adding its file. The name of the project is not decoration: it becomes
the name of the generated a2l file and the ``PROJECT`` and ``MODULE`` names inside it.

.. note::
   Every file DDD reads must be named ``*.ddd.json``. In a repository already full of json,
   that double extension says at a glance which files belong to DDD, and it lets a build
   script, an editor or a linter match them with one pattern. A description file with another
   name is reported under the ``file-extension`` check.

The component that produces
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``components/sensor_hub.ddd.json`` declares one variable with scope ``output``, which means
that SensorHub owns it and writes it, and that exactly one component in the whole project may
say so:

.. code-block:: json

   {
     "component": {
       "name": "SensorHub",
       "description": "Reads the sensors and publishes their conditioned values",
       "interface": [
         {
           "scope": "output",
           "definition": {
             "kind": "measurement",
             "name": "CabinTemperature",
             "description": "Temperature measured in the cabin",
             "datatype": "sint16",
             "unit": "degC",
             "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
             "limits": { "min": -40.0, "max": 85.0 },
             "init": 0,
             "volatile": true
           }
         }
       ]
     }
   }

The definition says more than a c declaration could. ``datatype`` is the storage the target
uses, while ``conversion`` says what the stored number *means*: with a factor of 0.1 the raw
value 235 is 23.5 degC, which is why the physical ``limits`` may be given as -40 and 85 rather
than as raw counts. That pair of statements is what lets DDD generate an a2l in which the
calibration tool shows degrees rather than counts, and it is also one of the things the other
components have to agree with. ``volatile`` is a property of the c definition, stated by every
definition whatever its kind, and it says whether the compiler may assume it already knows the
value: it is ``true`` here because the temperature is written by an interrupt while another task
reads it, so the compiler must not cache it in a register. The key has no default and may not be
left out, since nothing else in the description implies the answer; a definition without it is
refused under the ``schema`` check.

The component that consumes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``components/controller.ddd.json`` declares the same variable with scope ``input``, and adds a
calibration parameter of its own with scope ``local``:

.. code-block:: json

   {
     "component": {
       "name": "Controller",
       "description": "Decides when to heat, from the cabin temperature",
       "interface": [
         {
           "scope": "input",
           "definition": {
             "kind": "measurement",
             "name": "CabinTemperature",
             "description": "Temperature measured in the cabin",
             "datatype": "sint16",
             "unit": "degC",
             "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
             "limits": { "min": -40.0, "max": 85.0 },
             "volatile": true
           }
         },
         {
           "scope": "local",
           "definition": {
             "kind": "parameter",
             "name": "HeaterOnThreshold",
             "description": "Temperature below which the heater is switched on",
             "datatype": "sint16",
             "unit": "degC",
             "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
             "limits": { "min": -40.0, "max": 85.0 },
             "init": 180,
             "volatile": true
           }
         }
       ]
     }
   }

Repeating the definition of ``CabinTemperature`` in the consumer looks redundant, and it is the
point of the exercise: the consumer states what it *expects* to read, DDD compares that with
what the producer promises to write, and a disagreement becomes a finding instead of a field
report. Where the two sides differ, the declaration of the producing component is the
authoritative one - its definition is what gets generated, and the diagnostic points at the
consumer that deviates.

``HeaterOnThreshold`` is a different animal. Its ``kind`` is ``parameter``, so the software
never writes it and the calibration tool does: DDD generates it ``const`` and describes it in the
a2l as a ``CHARACTERISTIC`` the tool may change. That second half is what a calibration object's
``volatile`` is about. The threshold here is meant to be tuned while the device runs, and
``const`` on its own would not allow that: the compiler is entitled to fold the 180 into the code
that reads it, which it does even without optimisation wherever it can see the 180, so the tool
would write a new value the software never picks up. The price is the read only memory: a value the
compiler has to re-read is no longer constant data, so it leaves ``.rodata`` for ``.data``, and
on a flash target that is a ram address the project has to place deliberately in its linker
script. A project whose parameters only ever change with a new build states ``false`` instead and
keeps them in flash; DDD renders what the description says and reports nothing about the choice.
Its scope is ``local``, so it belongs to Controller alone and no other component will ever see
it - the right choice for data that only parametrises the component that owns it. ``init`` is a
raw value, so 180 means 18.0 degC.

Checking the project
~~~~~~~~~~~~~~~~~~~~

``ddd check`` answers one question: do these components fit together. It reads the project,
follows the includes, resolves every reference and runs every consistency check:

.. code-block:: text

   $ ddd check thermostat.ddd.json
   components/controller.ddd.json#component.interface[1].definition.name: info[missing-id]: 'HeaterOnThreshold' has no 'id', so a later delivery that renames it reports a removal and an unrelated addition; 'ddd id --assign' writes one
   components/sensor_hub.ddd.json#component.interface[0].definition.name: info[missing-id]: 'CabinTemperature' has no 'id', so a later delivery that renames it reports a removal and an unrelated addition; 'ddd id --assign' writes one
   2 infos

The components fit together - nothing above ``info`` was found - and the two declarations that
produce a variable are told what they still lack. An ``id`` is the identity of a variable over
the life of the project: it is what lets a later delivery rename ``CabinTemperature`` and still
be recognised as carrying the same object, rather than as having removed one variable and added
an unrelated other. Because that identity has to stay stable, it is written once, by the tool,
into every producing definition that has none:

.. code-block:: text

   $ ddd id --assign components/*.ddd.json
   wrote 2 ids

Each of the two definitions now carries a line like ``"id": "gbr9fq0et6js"`` - twelve
characters drawn at random, so yours differ from any shown here - and every later run leaves
it alone. With the identities in place, the check says nothing more than a single line when
there is nothing to say:

.. code-block:: text

   $ ddd check thermostat.ddd.json
   ok: 2 variables in 2 components are consistent

The exit code is 0 here and 1 as soon as there is an error, which is what makes the command a
build gate rather than a report; 2 is reserved for a usage mistake, so a mistyped option can
never be confused with a project that failed its checks.

``ddd list`` shows the same run from the other side - not whether the project is consistent, but
what it actually contains, which is the view a newcomer to an existing project wants first:

.. code-block:: text

   $ ddd list thermostat.ddd.json
   VARIABLE           KIND         DATATYPE  UNIT  SHAPE  INIT             PRODUCER            CONSUMERS
   CabinTemperature   measurement  sint16    degC  -      0 (= 0 degC)     SensorHub           Controller
   HeaterOnThreshold  parameter    sint16    degC  -      180 (= 18 degC)  Controller (local)  -

Getting the templates
~~~~~~~~~~~~~~~~~~~~~

Before anything can be generated, the project has to say what the generated c should look
like. Which comment style, which banner, how the include guards are spelled, whether a
variable is commented at all - none of that follows from the data, all of it is a
house style, and it differs from one project to the next. DDD therefore renders the c sources
from jinja2 templates the project provides, and asks for them with ``-t``: a required option,
with no default and no fallback, so nothing is ever generated from templates the project did
not choose.

.. code-block:: text

   $ ddd generate all thermostat.ddd.json -o gen
   usage: ddd generate all [-h] [-W CHECK=SEVERITY] [--strict]
                           [--format {text,json}] -o OUTPUT_DIR -t TEMPLATE_DIR
                           [--const-inputs] [--byte-order {little,big}]
                           [--address-map ADDRESS_MAP] [--dry-run] [--force]
                           project
   ddd generate all: error: the following arguments are required: -t/--template-dir

A project that has no templates yet starts from the set DDD ships as an example.
``ddd templates-dir`` prints where that set is installed - inside the package in a normal
installation, ``examples/templates`` in a source checkout - so copying it needs no path
written by hand:

.. code-block:: text

   $ cp -r "$(ddd templates-dir)" templates
   $ ls templates
   _macros.jinja2
   ddd_globals.c.jinja2
   ddd_globals.h.jinja2
   ddd_types.h.jinja2
   {component}.h.jinja2

Those five names are the whole configuration. Every ``*.jinja2`` file in the directory is
rendered to a file named like it without that extension, so ``ddd_globals.c.jinja2`` produces
``ddd_globals.c`` and renaming a template is how a generated file gets renamed. A name
starting with an underscore is a helper: ``_macros.jinja2`` holds the banner the other
templates import and produces no file of its own. A name containing ``{component}`` is
rendered once per component, with the placeholder replaced by the component name, which is how
one template produces both ``SensorHub.h`` and ``Controller.h``.

None of this touches the a2l. Its structure is dictated by ASAM and read by tools that expect
exactly that structure, so there is nothing in it for a project to style: the a2l generator is
internal and takes no templates at all.

Generating the code
~~~~~~~~~~~~~~~~~~~

``ddd generate`` runs exactly the same checks and then writes the artefacts into the directory
given with ``-o``, which is normally somewhere in the build tree rather than in the source tree:

.. code-block:: text

   $ ddd generate all thermostat.ddd.json -o gen -t templates
   wrote       gen/ddd_globals.c (created)
   wrote       gen/ddd_globals.h (created)
   wrote       gen/ddd_types.h (created)
   wrote       gen/Controller.h (created)
   wrote       gen/SensorHub.h (created)
   wrote       gen/Thermostat.a2l (created)

Run it a second time without touching the description files and nothing is written at all:

.. code-block:: text

   $ ddd generate all thermostat.ddd.json -o gen -t templates
   unchanged   gen/ddd_globals.c
   unchanged   gen/ddd_globals.h
   unchanged   gen/ddd_types.h
   unchanged   gen/Controller.h
   unchanged   gen/SensorHub.h
   unchanged   gen/Thermostat.a2l

A generated file whose content did not change keeps its time stamp, and the generated files
carry no time stamp of their own, so a regeneration that changes nothing does not make ``make``
or ``ninja`` recompile the components that include those headers. In a project where every
component depends on the generated headers, that is the difference between an incremental build
and a full one.

What the generated files are for
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The names of the five c files come from the templates - three of them are a template name
without its ``.jinja2``, the two component headers come from the ``{component}`` one - and only
the a2l is named by DDD itself, after the project:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - file
     - what it is for
   * - ``ddd_globals.c``
     - the single definition of every variable of the project. Compile and link it exactly
       once; it is the only place where the storage exists.
   * - ``<Component>.h``
     - the interface of one component, and nothing else. This is the file a component's
       sources include.
   * - ``ddd_globals.h``
     - the declaration of every variable of the project. It exists so that ``ddd_globals.c``
       can be compiled with full prototype checking; components are not meant to include it.
   * - ``ddd_types.h``
     - ``<stdint.h>``, ``<stdbool.h>`` and one ``typedef enum`` per enum conversion, included
       by all of the above.
   * - ``<Project>.a2l``
     - the ASAP2 description of the same data for the measurement and calibration tool.

``ddd_globals.c`` is the whole point of the exercise: it is where the global variables of the
project physically live, grouped by the component that owns them, and it is generated rather
than written by hand so that no variable can be defined twice or defined by the wrong team.

.. code-block:: c

   /*
    * ddd_globals.c
    *
    * Global variable data dictionary of project 'Thermostat'.
    * Generated from 'thermostat.ddd.json' by ddd 0.7.0.
    *
    * DO NOT EDIT - every change is lost the next time DDD runs.
    */
   #include "ddd_globals.h"

   /*
    * Definition of every global variable of the project.  Compile and link this
    * file exactly once; DDD is the only owner of these storage locations.
    */

   /* ---------------------------------------------------------------------------
    * Controller - Decides when to heat, from the cabin temperature
    * ------------------------------------------------------------------------ */
   /** Temperature below which the heater is switched on [degC] (calibration parameter) */
   const volatile int16_t HeaterOnThreshold = 180;

   /* ---------------------------------------------------------------------------
    * SensorHub - Reads the sensors and publishes their conditioned values
    * ------------------------------------------------------------------------ */
   /** Temperature measured in the cabin [degC] */
   volatile int16_t CabinTemperature = 0;

The two component headers are where the access rules become physical. ``SensorHub.h`` contains
the variable SensorHub owns and nothing else - SensorHub's sources include this one header and
have no way of naming ``HeaterOnThreshold``, because no declaration of it is on their include
path:

.. code-block:: c

   /*
    * SensorHub.h
    *
    * Global variable data dictionary of project 'Thermostat'.
    * Generated from 'thermostat.ddd.json' by ddd 0.7.0.
    *
    * DO NOT EDIT - every change is lost the next time DDD runs.
    */
   /*
    * Interface of software component 'SensorHub'.
    *
    * Reads the sensors and publishes their conditioned values
    *
    * Only the variables declared in the DDD description of this component are
    * visible here; everything else is intentionally out of reach.
    */
   #ifndef DDD_COMPONENT_SENSORHUB_H
   #define DDD_COMPONENT_SENSORHUB_H

   #include "ddd_types.h"

   /* outputs - written by SensorHub, read by other components */
   /** Temperature measured in the cabin [degC] */
   extern volatile int16_t CabinTemperature;

   #endif /* DDD_COMPONENT_SENSORHUB_H */

``Controller.h`` describes the same variable from the consuming side, and says in a comment who
produces it, so that a reader of the code knows where the value comes from without opening the
description files. The local parameter appears in its own section, and only here:

.. code-block:: c

   /*
    * Controller.h
    *
    * Global variable data dictionary of project 'Thermostat'.
    * Generated from 'thermostat.ddd.json' by ddd 0.7.0.
    *
    * DO NOT EDIT - every change is lost the next time DDD runs.
    */
   /*
    * Interface of software component 'Controller'.
    *
    * Decides when to heat, from the cabin temperature
    *
    * Only the variables declared in the DDD description of this component are
    * visible here; everything else is intentionally out of reach.
    */
   #ifndef DDD_COMPONENT_CONTROLLER_H
   #define DDD_COMPONENT_CONTROLLER_H

   #include "ddd_types.h"

   /* inputs - produced elsewhere, Controller may only read them */
   /** Temperature measured in the cabin [degC] */
   extern volatile int16_t CabinTemperature;  /* produced by SensorHub */

   /* locals - owned exclusively by Controller */
   /** Temperature below which the heater is switched on [degC] (calibration parameter) */
   extern const volatile int16_t HeaterOnThreshold;

   #endif /* DDD_COMPONENT_CONTROLLER_H */

Controller can read ``CabinTemperature`` and can also write it, since the declaration in its
header is not ``const``; ``ddd generate c --const-inputs`` declares inputs ``extern const`` in the
consumer headers instead, so that writing to a variable owned by somebody else stops compiling
rather than being caught in review. It is opt-in because the definition in ``ddd_globals.c``
stays non-const, which strict c calls a constraint violation even though the usual embedded
toolchains accept it.

Everything about the shape of those files - the banner, the plain c comments, the section
headings, the note naming the producer - comes from the templates copied into the project a
moment ago, and they are now the project's to change. Renaming ``ddd_globals.c.jinja2`` renames
the definition file; a project that wants its generated code documented differently writes
that into its own templates rather than asking DDD for an option; and a
project that wants one more generated file adds one more template. What the templates are given
to work with is the subject of :doc:`templates`.

The last artefact is the a2l, generated from the very same declarations, so the calibration
tool sees the physical values the description promised rather than raw counts:

.. code-block:: text

   /begin COMPU_METHOD CM_LIN_DEGC "phys = raw * 0.1 + 0"
     RAT_FUNC "%8.3" "degC"
     COEFFS 0 1 0 0 0 0.1
   /end COMPU_METHOD

   /begin MEASUREMENT CabinTemperature "Temperature measured in the cabin"
     SWORD CM_LIN_DEGC 0 0 -40 85
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "CabinTemperature" 0
   /end MEASUREMENT

The address is ``0x00000000`` because it is not known before the link step. The ``SYMBOL_LINK``
entry is always written, so that an address patcher can fill the addresses in after linking;
alternatively, ``ddd generate a2l --address-map addresses.json`` takes a symbol to address map
produced from the linker output and writes the real addresses straight away.

When the components disagree
----------------------------

So far the two components agreed, which is the uninteresting case. Change the ``datatype`` of
``CabinTemperature`` in ``components/controller.ddd.json`` from ``sint16`` to ``uint16`` - the
kind of change that happens when a signal is reworked in one component and the other one is not
told - and check the project again:

.. code-block:: text

   $ ddd check thermostat.ddd.json
   components/controller.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'CabinTemperature' is declared differently by component 'Controller' than by 'SensorHub' (datatype: uint16 != sint16)
       note: components/sensor_hub.ddd.json#component.interface[0].definition: reference declaration
   components/controller.ddd.json#component.interface[0].definition.limits: warning[limits-out-of-range]: limits [-40, 85] exceed the range [0, 6553.5] that uint16 can represent with this conversion
   1 error, 1 warning

Read the first finding from the left. The location is not just a file name but a path into the
file - ``#component.interface[0].definition`` - because a description file has no line an
editor could jump to that means anything on its own, whereas that path is exactly where the
offending value sits. Then comes the severity and the identifier of the check,
``definition-mismatch``: the identifier is part of the public interface of the tool and does
not change within a major version, so a build script can raise or lower this particular check
with ``-W definition-mismatch=warning`` without becoming sensitive to the wording. Then the
message names both components and, in brackets, the single attribute that differs.

The **note** on the second line is the other half of the diagnostic. A disagreement has two
sides, and printing only one of them would leave the reader to guess where the other
declaration is; the note points at the declaration of the *producing* component and calls it
the reference declaration, which also states which of the two DDD would have believed. Without
this line, the natural next step would be a repository-wide search for the variable name.

The warning underneath is not a second problem but a consequence of the first, and it shows how
much the tool actually understands about the data: the limits are physical, the conversion maps
raw to physical, and an unsigned 16-bit variable scaled by 0.1 simply cannot represent -40 degC.
It is a warning rather than an error because limits are a statement of intent about the data
rather than something the c compiler will ever see.

Nothing was generated during that run. ``ddd generate`` runs the checks first and writes no file
at all when one of them fails, because half-generated sources that describe a project nobody
agreed on are worse than no sources:

.. code-block:: text

   $ ddd generate all thermostat.ddd.json -o gen2 -t templates
   components/controller.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'CabinTemperature' is declared differently by component 'Controller' than by 'SensorHub' (datatype: uint16 != sint16)
       note: components/sensor_hub.ddd.json#component.interface[0].definition: reference declaration
   components/controller.ddd.json#component.interface[0].definition.limits: warning[limits-out-of-range]: limits [-40, 85] exceed the range [0, 6553.5] that uint16 can represent with this conversion
   1 error, 1 warning

.. warning::
   ``--force`` generates in spite of the errors, using the producer's definition
   wherever the components disagree, and still exits with 1. It exists for the case where a
   developer needs the headers to keep working while a disagreement is being sorted out
   between teams, and it is the wrong thing to put in a ci job: the exit code stays 1 precisely
   so that a pipeline which ignores it has to say so explicitly.

Put ``sint16`` back and the project is clean again. That loop - describe, check, generate - is
the whole daily workflow; everything else DDD offers is either a different question about the
same descriptions or a way of hooking this loop into a build system.

Where to go next
----------------

:doc:`concept` explains the model this page used without naming it: what a project, a
component, a declaration and a scope are, what the data dictionary is and why the producer is
the authority on a definition. It is the page to read before designing the description files
of a real project.

:doc:`templates` is the reference for the templates this page copied without looking inside
them: the data model they render, the naming rules that decide which file each of them
produces, and what a project changes first when the generated code has to look like the rest of
its sources.

:doc:`file_formats/index` is the reference for everything a description file may contain. The
thermostat used measurements and a parameter; the file formats also cover value blocks, curves,
maps and their shared axes, enum conversions, preprocessor conditions and the per-object a2l
settings.

:doc:`command_line_interface` documents every command and every option, including the ones this
page only mentioned in passing: ``--const-inputs``, ``--address-map``, the ``-W`` severity
overrides, the machine readable ``--format json`` output for a ci job, and the commands that
answer questions ``check`` does not - ``ddd compare`` for whether a delivery may replace its
predecessor, and ``ddd dump`` for the resolved data dictionary itself.
