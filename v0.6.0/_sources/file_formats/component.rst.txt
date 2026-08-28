Component description
=====================

A component description is the data interface of one software component, written down. It says
which global variables the component reads, which ones it writes and which ones it keeps to
itself, and it says everything about each of them that a c compiler and a calibration tool
need to know. It is written by the team that owns the component, it lives next to that
component's sources, and it is the only thing another team has to read in order to depend on
it.

The file that ends up being interesting is not this one on its own but this one next to all
the others: because every component states both what it produces and what it expects to
consume, DDD can compare the two sides of every shared variable and report a disagreement
before it becomes a field report. That comparison is what the :doc:`consistency checks
</consistency_checks>` do; this page describes what the file itself may contain.

.. code-block:: json

   {
     "component": {
       "name": "Controller",
       "description": "Consumes the raw values and produces the derived ones",
       "interface": [
         {
           "scope": "output",
           "condition": "defined(FEATURE_X)",
           "definition": {
             "name": "ValueG",
             "kind": "measurement",
             "description": "Measurement that only exists when FEATURE_X is defined",
             "datatype": "uint16",
             "unit": "V",
             "conversion": { "factor": 0.001 },
             "limits": { "min": 0, "max": 5 },
             "init": 1000,
             "volatile": false
           }
         }
       ]
     }
   }

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - Identifier of the component. It becomes the name of the header DDD generates for it -
       ``Controller`` gives ``Controller.h`` - and the name of the a2l ``GROUP`` that collects
       the component's objects in the calibration tool.
   * - ``description``
     - ``""``
     - Free text. It is repeated in the banner of the generated header and becomes the long
       identifier of the a2l ``GROUP``.
   * - ``interface``
     - required
     - The data interface: one entry per data object the component reads, writes or owns.
       Required with no default, so a component with nothing to declare says so with an
       explicit ``[]`` rather than with a key that might merely have been forgotten.
   * - ``types``
     - none
     - The declared types this component publishes, a non-empty list whose entries are
       exactly those of a :doc:`types file <types>`. See `Types and constants of the
       component`_.
   * - ``constants``
     - none
     - The declared constants this component publishes, a non-empty list whose entries are
       exactly those of a :doc:`constants file <constants>`. See `Types and constants of
       the component`_.

A component whose ``interface`` is the empty list is legal - a component may exist before it
has any data, or may genuinely have none - but it is reported at severity ``info``, because
far more often it means a file that was started and never finished:

.. code-block:: text

   $ ddd check emptycomp.ddd.json
   emptycomp.ddd.json#component: info[empty-component]: component 'Nothing' declares no variable
   1 info

What is
checked about a component name is that two of them cannot end up asking for the same generated
file, which on
a case insensitive file system means names differing only in case:

.. code-block:: text

   $ ddd check project.ddd.json
   b.ddd.json#component.name: error[name-collision]: components 'Sensorhub' and 'SensorHub' differ only in upper/lower case, so they ask for the same generated header
       note: a.ddd.json#component.name: other component
   1 error

interface
---------

Each entry of ``interface`` binds one data object to this component, and consists of three
things: **what** is being declared, **how** this component relates to it, and **when** it
exists at all.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``scope``
     - required
     - ``input``, ``output`` or ``local`` - the relationship between this component and the
       object.
   * - ``condition``
     - ``null``
     - A single c preprocessor expression. The generated declaration and definition are
       wrapped in ``#if`` / ``#endif`` with it.
   * - ``definition``
     - required
     - The :doc:`variable definition <variable_definition>` - name, kind, datatype, unit,
       conversion, limits, initial value and a2l settings.

The same variable is normally declared by several components: once by the one that writes it
and once by each one that reads it. That repetition is not redundancy, it is the whole
mechanism. The consumer states what it *expects*, the producer states what it *promises*, and
DDD compares the two. Where they differ, the declaration of the **producing** component is the
authoritative one: its definition is what gets generated, and the finding points at the
consumer that deviates.

Declaring the same variable twice inside **one** component is a different matter, and always a
mistake - there is no second opinion to have with oneself:

.. code-block:: text

   $ ddd check dupdecl.ddd.json
   dupdecl.ddd.json#component.interface[1]: error[duplicate-declaration]: component 'Dup' declares 'V' twice (as local and as local)
       note: dupdecl.ddd.json#component.interface[0]: first declared here
   1 error

scope
-----

The scope is what turns a set of variable descriptions into an interface with rules. It says
who owns a variable and who may see it, and DDD enforces both - the first through its checks,
the second through what it puts into which generated header.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - scope
     - meaning
   * - ``input``
     - The component reads the object. Some other component has to declare it as ``output``,
       otherwise the interface has a hole and ``missing-producer`` says so.
   * - ``output``
     - The component owns the object and writes it. Exactly one component in the project may
       say this about a given object; a second one is ``multiple-producers``. Other components
       may read it.
   * - ``local``
     - The component owns the object exclusively. No other component may declare it at all,
       in any scope; one that tries is ``local-conflict``.

For a measurement, ``output`` means what it sounds like: the software writes the variable. For
calibration data, which the software never writes, ``output`` means that the component
*provides* the data and other components may read it - a shared axis is the typical case, as
in the demo where ``Controller`` owns ``AxisA`` and ``UserInterface`` reads it in order to put
a second curve over the same break points. For data that only parametrises the component that
owns it, ``local`` is the normal choice, and it is the one that keeps the interface small.

The three scopes are what ``examples/inconsistent/`` exists to demonstrate; every rule above
appears in one run:

.. code-block:: text

   $ ddd check project.ddd.json
   component_b.ddd.json#component.interface[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
       note: component_a.ddd.json#component.interface[0]: also written here
   component_c.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'SharedValue' is declared differently by component 'ComponentC' than by 'ComponentA' (datatype: uint16 != sint16, conversion: identity != linear(factor=0.5, offset=0))
       note: component_a.ddd.json#component.interface[0].definition: reference declaration
   component_c.ddd.json#component.interface[1]: error[missing-producer]: 'MissingValue' is read by component 'ComponentC' but no component declares it as output
   component_c.ddd.json#component.interface[2]: error[local-conflict]: 'Scratch' is local to component 'ComponentA' but is also declared as input by component 'ComponentC'
       note: component_a.ddd.json#component.interface[2]: declared local here
   component_a.ddd.json#component.interface[1]: warning[unused-output]: 'UnusedSignal' is written by component 'ComponentA' but read by nobody
   4 errors, 1 warning

What the scope does to the generated code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Checks catch a wrong description; visibility catches wrong code. Every variable of the project
is defined exactly once, in the definition file, but each component gets a header containing
only what *it* declared, grouped by scope and annotated with who produces what. Those files
are the project's own templates rendered - the example ones call them ``ddd_globals.c`` and
``<Component>.h``, and :doc:`templates </templates>` explains how a project changes that. This
is ``Controller.h`` from the demo, shortened to the parts that matter:

.. code-block:: c

   /* outputs - written by Controller, read by other components */
   /** Measurement used as the input quantity of AxisA [Hz] */
   extern volatile uint16_t ValueE;
   /** Shared axis indexed by ValueE [Hz] (calibration axis, 6 points) */
   extern const uint16_t AxisA[6];

   /* inputs - produced elsewhere, Controller may only read them */
   /** Scalar measurement with a linear conversion [%] */
   extern uint8_t ValueA;  /* produced by SensorHub */
   /** Array measurement with four elements [V] */
   extern volatile uint16_t ValueB[4];  /* produced by SensorHub */

   /* locals - owned exclusively by Controller */
   /** Component local measurement of the controller [%] */
   extern int16_t ValueH;
   /** Single calibratable constant [Hz] (calibration parameter) */
   extern const uint16_t ParameterA;

The qualifiers there belong to the object rather than to the scope. ``ValueE`` and ``ValueB``
are ``volatile`` because their definitions say so, and that has to reach every reader: a
consumer whose header declared them plain would be free to read them once and keep the value.
``AxisA`` and ``ParameterA`` are ``const`` because they are calibration data, and they are not
also ``volatile`` only because every calibration object of the demo states
``"volatile": false``; a project whose tool retunes a running ecu states ``true`` and reads
``extern const volatile uint16_t ParameterA;`` here instead.

A source file of ``Controller`` includes this one header and nothing else, so it simply has no
way of naming a variable that belongs to ``SensorHub`` and was not declared as one of its own
inputs - the access rule is enforced by the compiler rather than by review. Reading a foreign
input is possible by construction, since that is what an input is; *writing* one still
compiles here, because the declaration is not ``const``. ``ddd generate c --const-inputs``
declares inputs ``extern const`` instead, which stops that too, at the cost of a definition
that stays non-const - strictly a constraint violation, accepted by the usual embedded
toolchains, and therefore opt-in. An input that is volatile becomes ``extern const volatile``,
since the qualifier the object asked for is not dropped for the one the option adds. It is an
option rather than a matter for the templates because it changes what is declared and not how
the declaration is written. The whole picture is on the
:doc:`generated artefacts </generated_artefacts>` page.

condition
---------

Some variables only exist in some builds: a diagnostic buffer in a development image, a
feature behind a compile time switch, a signal that only the variant with the second sensor
produces. ``condition`` carries that, as a c preprocessor expression:

.. code-block:: json

   {
     "scope": "output",
     "condition": "defined(FEATURE_X)",
     "definition": {
       "name": "ValueG",
       "kind": "measurement",
       "description": "Measurement that only exists when FEATURE_X is defined",
       "datatype": "uint16",
       "unit": "V",
       "conversion": { "factor": 0.001 },
       "limits": { "min": 0, "max": 5 },
       "init": 1000,
       "volatile": false
     }
   }

The expression travels with the object into every place it is written - the definition and the
declaration in every header that carries the variable - and is emitted verbatim, so that the
example templates can put the same guard around all of them, with the condition repeated in a
comment on the ``#endif`` so that a long guarded region stays readable:

.. code-block:: c

   #if defined(FEATURE_X)
   /** Measurement that only exists when FEATURE_X is defined [V] */
   uint16_t ValueG = 1000U;
   #endif /* defined(FEATURE_X) */

a2l has no notion of preprocessor conditions - the file describes one built image, and DDD
generates it before the build has happened. The object is therefore exported anyway, with the
condition written above it as a comment, so that a calibration engineer who cannot find the
symbol in the image knows immediately why:

.. code-block:: text

   /* only present in the build when: defined(FEATURE_X) */
   /begin MEASUREMENT ValueG "Measurement that only exists when FEATURE_X is defined"
     UWORD CM_LIN_V 0 0 0 5
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "ValueG" 0
   /end MEASUREMENT

One expression, and nothing else
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A condition has to be a **single** preprocessor expression. Surrounding whitespace is
stripped, and a condition that is empty or only whitespace is the same as no condition at all;
but a line break and the comment markers ``/*``, ``*/`` and ``//`` are refused, and so is
``#``:

.. code-block:: text

   $ ddd check cond.ddd.json
   cond.ddd.json#component.interface[1].condition: error[schema]: Value error, a condition is a single expression and cannot contain a line break (got: 'defined(A)\n#undef NDEBUG')
   cond.ddd.json#component.interface[2].condition: error[schema]: Value error, a condition cannot contain '/*' (got: 'defined(B) /* sneaky */')
   2 errors

The reason is that the text goes into somebody else's translation unit unchanged. A line break
would let a description file put arbitrary preprocessor directives - an ``#undef``, an
``#include``, a redefinition of a macro from a different component - inside the guarded region
of a file that team never sees. A comment marker would close the trailing
``#endif /* ... */`` early and leave whatever followed it as live code. Neither is something
the author of one component should be able to do to everybody else's build, and neither has
any legitimate use in an expression that is only ever meant to say *when* a variable exists.
Everything a real condition needs is still there: ``defined(FEATURE_X) && !defined(NO_FEATURE_X)``
is accepted as written.

When the components disagree about the condition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A condition belongs to the declaration, not to the variable, so two components can put
different conditions on the same variable. That is almost always a mistake - the variable
exists in the builds the producer says it exists in, and a consumer guarded by a different
symbol will either fail to link or quietly disappear - so it is reported, and the producer's
condition is the one that is generated:

.. code-block:: text

   $ ddd check project.ddd.json
   consumer.ddd.json#component.interface[0].condition: warning[condition-mismatch]: 'ValueX': component 'Consumer' uses condition 'defined(FEATURE_Y)' while 'Producer' uses 'defined(FEATURE_X)'
       note: producer.ddd.json#component.interface[0]: reference declaration
   1 warning

It is a warning rather than an error because the case does occur legitimately: a consumer whose
own code is guarded by a wider condition may reasonably repeat the narrower one imprecisely,
and a project migrating from one feature macro to another goes through a state where the two
spellings coexist. What DDD refuses to do is decide silently, which is why the message names
both conditions and says which one won.

.. note::
   ``storage-mismatch`` applies the same principle to how the a2l presents an object - a
   ``format`` string, a ``display_identifier``: a difference between components is reported,
   and the producer's value is the one that is used. Anything that would make the consumers
   actually *wrong* - datatype, unit, conversion, shape, limits, kind, ``volatile`` - is an
   error instead, under ``definition-mismatch``. ``volatile`` is in that list because it is
   interface and not storage: it reaches every consumer's own header as
   ``extern volatile uint16_t ValueB[4]``, and that is what tells the code reading the object
   not to keep the value it read the first time. A producer saying ``true`` and a consumer
   saying ``false`` is two components compiled against two different meanings of the same
   address.

   Two keys of the block sit outside that. ``init`` is refused on a consumer altogether, as
   ``consumer-storage``: a component that only reads a variable has no say in what it starts
   as. ``export`` is compared by nobody, because any component may ask for an object to reach
   the a2l and asking wins over declining.

Types and constants of the component
------------------------------------

A component **may** declare the types and the constants it publishes inside its own
description, in two optional keys whose entries are exactly those of the standalone files: a
``types`` list as a :doc:`types file <types>` writes it, and a ``constants`` list as a
:doc:`constants file <constants>` writes it. This is the pump of ``examples/vocabulary``,
shortened to the parts that matter:

.. code-block:: json

   {
     "component": {
       "name": "Pump",
       "types": [
         {
           "type": "scalar",
           "name": "Torque_t",
           "description": "A torque as the pump publishes it: hundredths of a newton metre",
           "datatype": "uint16",
           "unit": "Nm",
           "conversion": { "kind": "linear", "factor": 0.01, "offset": 0.0 }
         }
       ],
       "constants": [
         { "name": "PRESSURE_CELLS", "value": 8,
           "description": "cells of the pressure manifold" }
       ],
       "interface": [
         {
           "scope": "local",
           "definition": {
             "name": "TorqueLimit",
             "kind": "parameter",
             "description": "Torque above which the pump is derated",
             "typename": "Torque_t",
             "init": 250,
             "section": ".calib",
             "volatile": false
           }
         }
       ]
     }
   }

Declaring them here co-locates a library's contract in one file; it does **not** scope it.
The names join the same project wide namespace as those of the standalone files, every
consistency check applies to them unchanged - ``duplicate-type`` and ``duplicate-constant``
across both homes, ``reserved-identifier``, ``name-collision``, the unit vocabulary - and
any component of the project may name them, exactly as if a types or constants file had
declared them. Which home to choose is therefore a question of ownership rather than of
visibility: a type or constant that belongs to one component's published contract reads
best next to the interface that uses it, and one shared between several components, with no
single owner to live inside, stays in a standalone file. ``units`` and ``sections`` are
project wide vocabularies with no owner at all, so neither may appear inside a component:

.. code-block:: text

   $ ddd check own_units.ddd.json
   own_units.ddd.json#component.units: error[schema]: Extra inputs are not permitted (got: ['rpm'])
   1 error

A name declared twice is refused wherever the second declaration lives, embedded or
standalone, with a note at whichever home declared it first:

.. code-block:: text

   $ ddd check project.ddd.json
   shared.ddd.json#types[0]: error[duplicate-type]: type 'Torque_t' is already declared
       note: pump.ddd.json#component.types[0]: first declared here
   1 error

Checking a component on its own
-------------------------------

``ddd check`` and ``ddd generate`` accept a component file directly, which is what lets a team
check its own description before integrating it into a project. The inputs of that component
have no producer in such a run, by definition, so silence the check that would otherwise
dominate the output:

.. code-block:: text

   $ ddd check controller.ddd.json -W missing-producer=ignore
   controller.ddd.json#component.interface[2]: warning[unused-output]: 'ValueE' is written by component 'Controller' but read by nobody
   controller.ddd.json#component.interface[3]: warning[unused-output]: 'ValueF' is written by component 'Controller' but read by nobody
   controller.ddd.json#component.interface[4]: warning[unused-output]: 'StateA' is written by component 'Controller' but read by nobody
   controller.ddd.json#component.interface[5]: warning[unused-output]: 'ValueG' is written by component 'Controller' but read by nobody
   controller.ddd.json#component.interface[8]: warning[unused-output]: 'AxisA' is written by component 'Controller' but read by nobody
   5 warnings

``unused-output`` is the mirror image of the same situation and can be silenced the same way;
it is a warning, so the run still exits zero. Everything else applies unchanged: the schema,
the reserved identifiers, the references between curves, maps and axes, the initial values
against the datatypes and against the shapes. What cannot be checked this way is precisely
what the project is for - whether the other components agree.

The types and constants the component declares inline resolve in such a run, which is the
practical payoff of the co-location: a self-contained library file answers ``ddd check`` and
``ddd list`` on its own, and only the references that genuinely live elsewhere stay open.
The pump of ``examples/vocabulary`` names its own ``Torque_t`` and ``PRESSURE_CELLS`` and
leans on the project only for its sections and for one shared size:

.. code-block:: text

   $ ddd check pump.ddd.json
   pump.ddd.json#component.interface[0].definition.section: error[unknown-section]: 'PumpSpeed' is placed in '.fast_ram', which is not a section any file of this project declares
   pump.ddd.json#component.interface[1].definition.section: error[unknown-section]: 'ManifoldPressure' is placed in '.fast_ram', which is not a section any file of this project declares
   pump.ddd.json#component.interface[2].definition.dimensions[0]: error[unknown-constant]: 'PressureTrend' is dimensioned by 'TREND_SAMPLES', which is not a constant any file of this project declares
   pump.ddd.json#component.interface[3].definition.section: error[unknown-section]: 'TorqueLimit' is placed in '.calib', which is not a section any file of this project declares
   4 errors

   $ ddd check pump.ddd.json -W unknown-section=ignore -W unknown-constant=ignore
   ok: 3 variables in 1 component are consistent
