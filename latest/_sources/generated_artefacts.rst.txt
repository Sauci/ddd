Generated artefacts
===================

``ddd generate`` runs every consistency check first and only then hands the resolved data
dictionary to the backends, because generating from a project whose components disagree
would produce code that compiles and links and is nevertheless wrong; ``--force`` overrides
that refusal for the case where somebody needs to look at the output of a project that is
still being assembled. What comes out is c code - the definition of every global variable and
the declarations each component is allowed to see - and the a2l description that measurement
and calibration tools read. The two backends never see each other: the c backend does not
know that a2l exists, the a2l backend does not know what a ``uint16_t`` is called, and both
consume the same :doc:`data dictionary </data_dictionary>`.

The two artefacts are not produced the same way, and that asymmetry is deliberate. How many c
files there are, what they are called, which comment marker documents a variable and which
include guard protects a header is a house style that follows from nothing in the data, so
the c sources are rendered from templates the project provides and points ``--template-dir``
at; the argument and the mechanism are on the :doc:`templates` page. An a2l is the opposite
case. Its structure is dictated by ASAM and its reader is a measurement and calibration tool
nobody in the project controls, so there is nothing left for a house style to decide: the a2l
generator is internal, takes no template directory, and writes the same shape of file for
everybody.

Everything on this page is the output of the demonstration project shipped in
``examples/demo``. Its c files are the ones the example templates in ``examples/templates``
produce, which is what every transcript below hands to ``--template-dir``:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates
   wrote       build/gen/ddd_globals.c (created)
   wrote       build/gen/ddd_globals.h (created)
   wrote       build/gen/ddd_types.h (created)
   wrote       build/gen/Controller.h (created)
   wrote       build/gen/SensorHub.h (created)
   wrote       build/gen/UserInterface.h (created)
   wrote       build/gen/EventLogger.h (created)
   wrote       build/gen/DemoDevice.a2l (created)

The project ``DemoDevice`` is made of four components - ``Controller``, ``SensorHub``,
``UserInterface`` and ``EventLogger``, the last one reached through a sub project of its own
- and it declares one object of every kind DDD supports, which is why its output is used
throughout this page.

c code
------

The files come from the templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--template-dir`` is required and has no default, because there is no set of files DDD could
sensibly fall back to. Every ``*.jinja2`` file directly inside that directory is rendered, and
the name of the generated file is the name of its template without that extension, so the
template directory alone says what a run will write. The rest of the mechanism - the names
that mean something special, what a template may import, and what the data model offers it -
is on the :doc:`templates` page; the point here is that the list below is a property of the
example templates and not of the tool.

Those examples are a working set to copy and change rather than a default, and nothing falls
back to them. ``ddd templates-dir`` prints where they are, in the installed package or in a
source checkout:

.. code-block:: text

   $ ddd templates-dir
   /home/you/ddd/examples/templates

Five templates live there, and four of them produce a file:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - template
     - what it renders
   * - ``_macros.jinja2``
     - Nothing on its own: a name starting with an underscore is a helper. It holds the
       banner the other four import, which is how the same header comment appears on every
       generated file without being written five times.
   * - ``ddd_types.h.jinja2``
     - ``ddd_types.h``, the types the generated declarations are written in: ``<stdint.h>``,
       ``<stdbool.h>`` when the project declares a ``boolean``, the headers of the
       :doc:`external types <file_formats/types>` in use - deduplicated, sorted by spelling,
       quoted or angled exactly as declared - and one ``typedef enum`` per enum
       conversion. Every other generated header includes this one and nothing else, so a
       component that includes its own interface header needs no further include to compile.
   * - ``ddd_globals.h.jinja2``
     - ``ddd_globals.h``, an ``extern`` declaration of *every* object of the project, grouped
       by owning component. It exists for one reader only, ``ddd_globals.c``, so that the
       definition file is compiled against declarations and a typo cannot silently create a
       second object. Software components are not meant to include it.
   * - ``ddd_globals.c.jinja2``
     - ``ddd_globals.c``, the single definition of every global variable of the project.
       Compile and link it exactly once; from that point on DDD owns the storage of every
       declared object and a duplicate definition elsewhere fails at link time.
   * - ``{component}.h.jinja2``
     - One header per component - ``Controller.h``, ``SensorHub.h``, ``UserInterface.h`` and
       ``EventLogger.h`` for the demo - carrying the objects that component declared and
       nothing else. This is the file a component includes, and it is where the access rules
       are enforced.

No option renames any of this, and none is needed: a project that wants ``device_globals.c``
renames ``ddd_globals.c.jinja2``, and the ``#include`` line and the include guard that mention
the old name are in the templates next to it. The component headers are the one name a project
does not spell out, since ``{component}`` is filled in from the description files - renaming
that template to ``{component}_if.h.jinja2`` yields ``Controller_if.h`` and the rest without
listing a single component anywhere.

.. note::
   ``ddd generate`` accepts a single component description as well as a project. In that
   case the component name is used where a project name would be, so a component called
   ``Controller`` generates ``Controller.h`` next to the shared files and an a2l file called
   ``Controller.a2l``. Add ``-W missing-producer=ignore``, since the components producing the
   inputs are by definition not part of the file.

The type header
~~~~~~~~~~~~~~~

An enum conversion is the one part of a description that has to become a c type rather than
just a c declaration, and the example templates emit it in a header of its own so that every
component sharing the enum sees the same definition:

.. code-block:: c

   /*
    * ddd_types.h
    *
    * Global variable data dictionary of project 'DemoDevice'.
    * Generated from 'demo.ddd.json' by ddd 0.0.1.
    *
    * DO NOT EDIT - every change is lost the next time DDD runs.
    */
   #ifndef DDD_TYPES_H
   #define DDD_TYPES_H

   #include <stdint.h>
   #include <stdbool.h>

   /* StateA_t */
   typedef enum
   {
       STATE_OFF = 0, /**< powered but not started */
       STATE_INIT = 1,
       STATE_ACTIVE = 2,
       STATE_DEGRADED = 3,
       STATE_FAULT = 15
   } StateA_t;

   #endif /* DDD_TYPES_H */

The variable itself keeps the storage its ``datatype`` asks for - ``StateA`` is declared
``uint8_t``, not ``StateA_t`` - because the size of an enumerated type is up to the compiler
and a global variable whose width depends on the toolchain is not something an interface
description should hand over. The ``typedef`` exists so that the code can be written in terms
of ``STATE_ACTIVE`` instead of ``2``, and the ``enum-conflict`` check makes sure the same
enum name never carries two different sets of enumerators across the project.

The definition file
~~~~~~~~~~~~~~~~~~~

``ddd_globals.c`` is where the memory is. The model hands the templates one group per owning
component, with the measurements and the calibration data of a component in two separate
lists, and the example template writes them in that order so that a diff of the file after a
description change points at the component that changed:

.. code-block:: c

   /* ---------------------------------------------------------------------------
    * Controller - Consumes the raw values and produces the derived ones
    * ------------------------------------------------------------------------ */

   /* measurements */
   /** Measurement with a verbal conversion table */
   uint8_t StateA = 0U;
   /** Measurement used as the input quantity of AxisA [Hz] */
   volatile uint16_t ValueE = 0U;
   /** Signed measurement with a fixed point conversion [degC] */
   int16_t ValueF = -400;
   #if defined(FEATURE_X)
   /** Measurement that only exists when FEATURE_X is defined [V] */
   uint16_t ValueG = 1000U;
   #endif /* defined(FEATURE_X) */
   /** Component local measurement of the controller [%] */
   int16_t ValueH = 0;

   /* calibration data */
   /** Shared axis indexed by ValueE [Hz] (calibration axis, 6 points) */
   const uint16_t AxisA[6] = { 0U, 3200U, 6400U, 12800U, 19200U, 32000U };
   /** Component local axis indexed by ValueA [%] (calibration axis, 4 points) */
   const uint8_t AxisB[4] = { 0U, 60U, 140U, 200U };
   /** Calibratable curve over AxisA [ms] (calibration curve over AxisA) */
   const uint16_t CurveA[6] = { 1200U, 900U, 800U, 750U, 700U, 650U };
   /** Calibratable map over AxisA and AxisB [%] (calibration map over AxisA and AxisB) */
   const int8_t MapA[4][6] = {
       { 20, 24, 28, 30, 32, 30 },
       { 18, 22, 26, 28, 30, 28 },
       { 12, 16, 20, 22, 24, 22 },
       { 6, 10, 14, 16, 18, 16 }
   };
   /** Single calibratable constant [Hz] (calibration parameter) */
   const uint16_t ParameterA = 3200U;

Several details of that excerpt are deliberate, and they fall on both sides of the split
between the data and its presentation. The text of the comment is DDD's: it is assembled from
the ``description``, the ``unit`` in square brackets and, for calibration data, a note saying
what the object is and what it is dimensioned by, so that a reader of the c file does not have
to open the json to find out that ``CurveA`` is indexed by ``AxisA``. What surrounds that text
is the template's, and the examples put it in an ordinary ``/* ... */`` comment; whether the
generated code should instead be documented in the form a documentation generator reads is a
decision about the project's sources rather than about its data, and it is made by writing the
markers that generator expects in the template. The values are DDD's again: every literal
carries the suffix its datatype asks for, in upper case as the coding standards common in the
industry require: ``U`` for ``uint8``, ``uint16`` and ``uint32``, ``ULL`` and ``LL`` for the
64 bit types, ``F`` for ``float32``, nothing for the signed narrow types and for
``float64``. And an object whose description gives no ``init`` is emitted without an
initialiser at all, as ``float ValueC;`` and ``uint16_t ValueD[8];`` are, because an object
of static storage duration without an initialiser is zero initialised by the c standard; a
``"init": null`` in the description means exactly that, and writing the zeros out would only
say the same thing at greater length.

Access rules are a visibility problem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The point of rendering a header per component, rather than one for the whole project, is that
a component cannot write a variable that belongs to somebody else. That is enforced by not
letting it *see* the variable in the first place: a component includes its own header, the
header declares the objects that component declared, and a reference to any other global is an
undeclared identifier that the compiler rejects. The header of ``UserInterface`` looks like
this:

.. code-block:: c

   /*
    * Interface of software component 'UserInterface'.
    *
    * Reads the values of the other components and drives the display
    *
    * Only the variables declared in the DDD description of this component are
    * visible here; everything else is intentionally out of reach.
    */
   #ifndef DDD_COMPONENT_USERINTERFACE_H
   #define DDD_COMPONENT_USERINTERFACE_H

   #include "ddd_types.h"

   /* outputs - written by UserInterface, read by other components */
   /** Bit coded measurement written by the user interface */
   extern uint32_t ValueI;

   /* inputs - produced elsewhere, UserInterface may only read them */
   /** Measurement used as the input quantity of AxisA [Hz] */
   extern volatile uint16_t ValueE;  /* produced by Controller */
   /** Signed measurement with a fixed point conversion [degC] */
   extern int16_t ValueF;  /* produced by Controller */
   /** Floating point measurement without a conversion [degC] */
   extern float ValueC;  /* produced by SensorHub */
   /** Measurement with a verbal conversion table */
   extern uint8_t StateA;  /* produced by Controller */
   /** Array measurement with four elements [V] */
   extern volatile uint16_t ValueB[4];  /* produced by SensorHub */
   #if defined(FEATURE_X)
   /** Measurement that only exists when FEATURE_X is defined [V] */
   extern uint16_t ValueG;  /* produced by Controller */
   #endif /* defined(FEATURE_X) */
   /** Counter written by the event logger */
   extern uint8_t ValueJ;  /* produced by EventLogger */
   /** Shared axis indexed by ValueE [Hz] (calibration axis, 6 points) */
   extern const uint16_t AxisA[6];  /* produced by Controller */

   /* locals - owned exclusively by UserInterface */
   /** Second calibratable curve over the same shared axis [%] (calibration curve over AxisA) */
   extern const uint8_t CurveB[6];
   /** Calibratable array of constants (calibration value block) */
   extern const uint8_t BlockA[8];

   #endif /* DDD_COMPONENT_USERINTERFACE_H */

The three sections mirror the three scopes and each one is labelled with what the component
is allowed to do with it. The guard is one the model offers ready made per component - hence
the ``COMPONENT`` in the middle, which keeps a component called ``types`` from defining
``DDD_TYPES_H`` and preprocessing the types header away - and a template that would rather
write its own is free to, as :doc:`templates` describes. Every input carries the name of the
component that produces it as a trailing comment, which is the piece of information a
developer reading unfamiliar code usually wants next: not only *what* the value is, but *who*
is responsible for it. The locals of ``UserInterface`` appear in this header and in no other,
which is exactly what ``local`` means - and it is worth stressing that ``local`` is a
statement about c visibility only. A local object still lives in the shared ``ddd_globals.c``
and still appears in the a2l, because a calibration engineer has to be able to tune ``CurveB``
whether or not another component may read it.

.. note::
   The enforcement is against accident, not against determination. All these objects have
   external linkage, so a component that writes its own ``extern`` declaration by hand, or
   that includes ``ddd_globals.h``, reaches everything. What the generated headers remove is
   the possibility of doing it *without noticing*: the include line of a foreign header, or
   a hand-written ``extern`` in the middle of a component, is a visible thing that a reviewer
   can object to. The :doc:`cmake integration </build_integration>` reinforces this by putting
   the generated directory on the include path of the components and expecting each of them
   to include its own header.

``--const-inputs``
~~~~~~~~~~~~~~~~~~

Visibility stops a component from touching a variable it never declared, but it does not
stop it from writing to one it declared as an ``input``. ``--const-inputs`` closes that gap
by adding ``const`` to the input declarations of the consumer headers, which turns an
assignment into a diagnostic the compiler issues at the offending line. It is the one c
option left on the command line rather than in a template, because it changes what is
declared and not how it is written: the qualifier is part of the declaration the model hands
over, so any template that prints those declarations honours it. Generating the demo with
``--const-inputs`` opens the inputs section of ``UserInterface.h`` like this:

.. code-block:: c

   /* inputs - produced elsewhere, UserInterface may only read them */
   /** Measurement used as the input quantity of AxisA [Hz] */
   extern const volatile uint16_t ValueE;  /* produced by Controller */
   /** Signed measurement with a fixed point conversion [degC] */
   extern const int16_t ValueF;  /* produced by Controller */
   /** Floating point measurement without a conversion [degC] */
   extern const float ValueC;  /* produced by SensorHub */
   ...

Note that ``volatile`` survives the transformation: ``const volatile`` is the correct
qualification for a value that this translation unit may not write but that something else -
here the producing component - changes underneath it, and dropping the ``volatile`` would let
the optimiser cache a reading in a register. Objects that are already ``const``, the
calibration data, are left alone; a second ``const`` does not compile.

.. warning::
   The definition in ``ddd_globals.c`` stays non-const, because the producing component has
   to be able to write it. The consumer therefore sees ``extern const int16_t ValueF;`` while
   the object is defined as ``int16_t ValueF = -400;``, and c requires that all declarations
   of the same object agree on their type qualifiers. This is a constraint violation, and a
   conforming compiler is entitled to reject it. In practice every embedded toolchain the
   tool has been used with accepts it - the declarations are in different translation units,
   the linker only matches names, and no compiler diagnoses across that boundary - but
   "accepted in practice" is not "correct", which is why the behaviour is opt-in rather than
   the default. The repository verifies the claim rather than asserting it: the container
   target ``compile-const`` regenerates the demo with ``--const-inputs`` and compiles and
   links the result with ``-std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow
   -Wcast-qual -Wstrict-prototypes``.

Conditional declarations
~~~~~~~~~~~~~~~~~~~~~~~~

A declaration may carry a ``condition``, a c preprocessor expression, and the condition
travels with the object into every place it is written - the definition file, the shared
declaration header and the header of every component that declares it - so that the example
templates emit the same ``#if`` around all of them:

.. code-block:: c

   #if defined(FEATURE_X)
   /** Measurement that only exists when FEATURE_X is defined [V] */
   uint16_t ValueG = 1000U;
   #endif /* defined(FEATURE_X) */

They repeat the condition in the ``#endif`` comment because these guards are frequently
nested inside the hand-written ``#if`` blocks of a component, and an unlabelled ``#endif``
several dozen lines below its ``#if`` is a well known way to lose an hour. DDD does not
evaluate the expression and does not need to: it is the compiler that decides whether the
object exists, and because the same condition reaches every file that mentions the object,
the definition and all its declarations appear or disappear together. What DDD does check is
that the components declaring one object agree on the condition - a disagreement is the
``condition-mismatch`` warning, since it means one component expects the variable in a build
where another does not define it.

.. note::
   The demonstration build exercises both states. ``docker compose run --rm compile``
   generates the demo, compiles it, links it and then compares the symbols of the binary
   against ``ddd list --format json``, once without defines and once with ``-DFEATURE_X``::

      == symbols   [base]
      19 of 20 declared variables are defined
        conditional, absent : ValueG
      == symbols   [defines]
      20 of 20 declared variables are defined
        conditional, present: ValueG

Calibration data is const, and volatile when a tool tunes it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Everything that is not a ``measurement`` - a parameter, a value block, an axis, a curve, a
map - is data the software reads and never writes, and it is generated ``const`` for that
reason. The immediate benefit is that a component which tries to write its own calibration
parameter does not compile, which catches the mistake at the point where somebody typed it
rather than in the field. The second is that the linker is free to place the object in read
only memory, which on a flash based target is where a constant that is only ever changed by
reflashing the image belongs.

What ``const`` does not say is whether anything *outside* the compiled code changes the
value while it runs, and that is the question ``volatile`` answers. It is a key of every
definition of every kind, required and without a default, so a parameter, an axis, a curve
and a map state it exactly as a measurement does. The two qualifiers describe two different
things - ``const`` that this software never writes the object, ``volatile`` that somebody
else does - so DDD composes them independently instead of letting one displace the other:

.. code-block:: c

   volatile uint16_t Speed;            /* measurement, "volatile": true  */
   uint16_t Speed;                     /* measurement, "volatile": false */
   const volatile uint16_t Gain = 3U;  /* parameter,   "volatile": true  */
   const uint16_t Gain = 3U;           /* parameter,   "volatile": false */

Every ``extern`` declaration of the object is qualified to match, in ``ddd_globals.h`` and in
the header of each component that declared it, so that the whole image is compiled against
one statement about the value. This is the argument ``--const-inputs`` makes one section
above, applied to the other half of the data: ``const volatile`` is the correct qualification
for a value this translation unit may not write but that something else changes underneath
it, and whether that something else is the producing component or the calibration tool
connected to the running ecu makes no difference to the compiler.

The reason a tuned constant needs the ``volatile`` is that ``const`` is a promise the
compiler is entitled to act on, and it does. Compiled with the gcc 12.2.0 of the project's
own container, ``const uint16_t Gain = 3;`` read by ``apply(x) { return x * Gain; }`` becomes
``lea eax, [rdi+rdi*2]`` at ``-O2``: the 3 has been turned into a shift and an add and no
load of ``Gain`` is left in the function. Declared ``const volatile``, the same source
compiles to ``movzx eax, WORD PTR Gain[rip]`` followed by ``imul eax, edi``, which reads the
object every time it is evaluated. This is not an optimiser level anybody can dial down: at
``-O0`` the body is ``mov eax, 3``, because the c front end substitutes the initialiser while
it parses, before an optimiser has run. Nor is it confined to scalars, since
``pick() { return Curve[2]; }`` on a ``const`` array is ``mov eax, 30`` at ``-O0`` as well.
Across translation units without link time optimisation the load does survive, but the
``const`` still allows the compiler to collapse two source level reads into one and to move
that one across an opaque call, so a value that changes while the software runs cannot be
observed to change between them - and with ``-flto`` it folds outright. Reading the parameter
once into a ram copy at startup is no escape either: ``RamGain = Gain;`` is ``mov eax, 3``.

What that costs is not a write that fails but a write nobody notices. A program that stores 7
through the address of a plain ``const`` object prints, identically at ``-O0``, ``-O2`` and
``-Os``, that memory now holds ``Gain=7`` and that ``apply(1)`` still returns 3, which is
exactly the failure a calibration engineer spends an afternoon on: the tool shows the new
value, reads it back correctly, and the ecu behaves as it did before.

``volatile`` is not free, and what it costs is the read only memory the ``const`` earned. gcc
treats a volatile access as a side effect and takes the object out of the read only category
altogether: ``.section .rodata`` becomes a plain ``.data``, the section flags ``readelf``
reports go from ``A`` to ``WA``, and the class ``nm`` prints goes from ``R`` to ``D``.
Measured on DDD's own generated demo with the flag set quoted above, ``size -A
ddd_globals.o`` moves from ``.rodata 84`` and ``.data 2`` to ``.data 86``. Naming a section
explicitly does not change this - a ``.calib`` section is emitted ``A`` when its contents are
``const`` and ``WA`` when they are ``const volatile``. On a flash target with an ordinary
linker script that means a ram address with a load region in flash and a copy at startup, so
the calibration tool programs a page the code never reads and the next reset overwrites what
the tool wrote. A project that calibrates online therefore places these objects itself, in
its linker script.

DDD states no preference between the two answers and reports nothing about the choice. There
is nothing in a description it could derive one from - unlike the limits, which follow from
the datatype and the conversion - and the two answers have different costs, of which only the
project knows which it is paying. A project that tunes calibration data in a running ecu
writes ``true`` and arranges the placement; a project that changes a constant by reflashing
the image writes ``false`` and keeps its data in flash, where the ``const`` alone puts it.
Both are ordinary, and DDD renders what the description says.

.. note::
   Because the key is required and has no default, a description written before it existed
   gains it on every definition of every kind. There is no phase-in: an omitted ``volatile``
   is reported by the ``schema`` check, one of the five whose severity ``-W`` refuses to
   relax, so ``-W schema=warning`` does not buy a project the time to migrate one component
   at a time. Templates need no change at all, because no template spells a qualifier out:
   ``.definition`` and ``.declaration()`` compose it, and a template that lays a declaration
   out itself reads the two booleans behind it, as :doc:`templates` describes.

.. warning::
   ``const volatile`` propagates into the hand-written code that reads the object. Passing a
   ``const volatile`` array to a helper declared to take a plain ``const`` pointer is
   ``error: passing argument 1 of 'sum' discards 'volatile' qualifier
   [-Werror=discarded-qualifiers]``, and casting the qualifier away is refused in turn by
   ``-Wcast-qual``, which the flag set above includes, so such a helper has to be re-typed
   rather than worked around. The qualifier also buys freshness at the price of coherence:
   the compiler has to re-read the object at every mention, so a set of parameters read at
   several points of one control step can straddle a calibration write and be half old and
   half new, and at ``-O3`` a loop over a ``const volatile`` gain is not vectorised at all.

Regeneration is stable
~~~~~~~~~~~~~~~~~~~~~~

Nothing DDD hands a template varies from run to run: there is no time stamp, no host name and
no user name anywhere in the data model, so a project can write a banner that names the
project, the description file it was generated from and the version of the tool, and be sure
that it says the same thing tomorrow. The example templates put exactly that at the top of
every file they render:

.. code-block:: c

   /*
    * ddd_globals.c
    *
    * Global variable data dictionary of project 'DemoDevice'.
    * Generated from 'demo.ddd.json' by ddd 0.0.1.
    *
    * DO NOT EDIT - every change is lost the next time DDD runs.
    */

A regeneration from unchanged inputs therefore produces byte identical output, and DDD makes
use of that fact: it renders every artefact in memory, compares it with what is already on
disk and only writes the ones that actually differ. The report says which is which, and the
exit code is unaffected:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates
   unchanged   build/gen/ddd_globals.c
   unchanged   build/gen/ddd_globals.h
   unchanged   build/gen/ddd_types.h
   unchanged   build/gen/Controller.h
   unchanged   build/gen/SensorHub.h
   unchanged   build/gen/UserInterface.h
   unchanged   build/gen/EventLogger.h
   unchanged   build/gen/DemoDevice.a2l

This matters because of what a build system does with modification times. DDD sits at the
very bottom of the include graph - here ``ddd_types.h`` is included by every generated header,
which is included by every component - so a generator that rewrites its output on every run
invalidates the whole tree on every run, and an incremental build of a large image
degenerates into a full rebuild. With the comparison in place, only what genuinely changed is
touched. Changing the description of one variable in ``SensorHub`` shows the granularity:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates
   wrote       build/gen/ddd_globals.c (updated)
   wrote       build/gen/ddd_globals.h (updated)
   unchanged   build/gen/ddd_types.h
   unchanged   build/gen/Controller.h
   wrote       build/gen/SensorHub.h (updated)
   unchanged   build/gen/UserInterface.h
   wrote       build/gen/EventLogger.h (updated)
   wrote       build/gen/DemoDevice.a2l (updated)

``Controller.h`` and ``UserInterface.h`` were left alone because neither component declares
that variable, so neither of those components has to be recompiled. ``EventLogger.h`` was
rewritten because ``EventLogger`` reads it and the description text appears in the comment on
its declaration. This granularity is a property of the templates as much as of the tool: a
project that renders one header for everybody instead of one per component gets a correct
build and a coarser one, and that trade is its to make.

``--dry-run`` performs the whole comparison and writes nothing, which answers the question a
ci job asks when the generated code is committed to the repository: is what is checked in
still what the descriptions produce? Note that the exit code continues to report the
consistency checks and nothing else, so a job using it this way has to read the report rather
than the status. Here the output directory did not exist yet, which is why every line says
``created``:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates --dry-run
   would write build/gen/ddd_globals.c (created)
   would write build/gen/ddd_globals.h (created)
   would write build/gen/ddd_types.h (created)
   would write build/gen/Controller.h (created)
   would write build/gen/SensorHub.h (created)
   would write build/gen/UserInterface.h (created)
   would write build/gen/EventLogger.h (created)
   would write build/gen/DemoDevice.a2l (created)

a2l
---

The second artefact is the ASAM MCD-2 MC description, better known by the extension of its
files, and it is what lets a measurement and calibration tool display and tune the data of a
running target. DDD writes **ASAP2 1.6.1** and says so on the second line of the file:

.. code-block:: text

   /* DemoDevice.a2l - generated from 'DemoDevice' by ddd 0.0.1. DO NOT EDIT. */
   ASAP2_VERSION 1 61

   /begin PROJECT DemoDevice "Demonstration project showing every DDD feature"

     /begin HEADER "Demonstration project showing every DDD feature"
       PROJECT_NO DemoDevice
       VERSION "generated by ddd 0.0.1"
     /end HEADER

     /begin MODULE DemoDevice "Demonstration project showing every DDD feature"

       /begin MOD_COMMON "global variables of DemoDevice"
         BYTE_ORDER MSB_LAST
         ALIGNMENT_BYTE 1
         ALIGNMENT_WORD 2
         ALIGNMENT_LONG 4
         ALIGNMENT_INT64 8
         ALIGNMENT_FLOAT32_IEEE 4
         ALIGNMENT_FLOAT64_IEEE 8
       /end MOD_COMMON

The whole project becomes a single ``MODULE`` named after the project, which is the right
granularity here: a module is what a calibration tool connects to, and the components of the
image are one target, not several. ``BYTE_ORDER`` follows ``--byte-order``, which writes
``MSB_LAST`` for ``little`` (the default) and ``MSB_FIRST`` for ``big``; the alignment values
are the natural alignment of each width, which is what a compiler targeting a modern core
does unless it is told to pack. The a2l is written unless ``--no-a2l`` says otherwise, and it
is named after the project, so ``DemoDevice`` produces ``DemoDevice.a2l``.

A project that declares a :doc:`constant vocabulary <file_formats/constants>` gets a
``MOD_PAR`` after the ``MOD_COMMON``, stating one ``SYSTEM_CONSTANT`` per declared constant
in name order, both halves quoted as the format wants them; a project that declares none
gets no empty block. The records themselves still spell every size as a resolved number,
because a ``MATRIX_DIM`` accepts no symbol where it expects a count - the ``MOD_PAR`` is
where a downstream tool finds the name and the value it stands for:

.. code-block:: text

       /begin MOD_PAR "named constants of PumpDevice"
         SYSTEM_CONSTANT "PRESSURE_CELLS" "8"
         SYSTEM_CONSTANT "TREND_SAMPLES" "16"
       /end MOD_PAR

What is emitted for what
~~~~~~~~~~~~~~~~~~~~~~~~

Every object that ends up in the file - which is every object of the project unless its
description asks otherwise, see `Keeping an object out of the a2l`_ - becomes exactly one
record, and the kind of the object decides which. Two structure members are the exception
and produce no record at all: a ``bits`` member, which waits for a build that can report
where its bits sit, and a member of an :doc:`external type <file_formats/types>`, because
the format cannot describe storage whose layout DDD does not know; neither appears in any
``GROUP`` either.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - record
     - emitted for
   * - ``MEASUREMENT``
     - every ``measurement``
   * - ``CHARACTERISTIC ... VALUE``
     - every ``parameter``
   * - ``CHARACTERISTIC ... VAL_BLK``
     - every ``value_block``
   * - ``CHARACTERISTIC ... CURVE``
     - every ``curve``
   * - ``CHARACTERISTIC ... MAP``
     - every ``map``
   * - ``AXIS_PTS``
     - every ``axis``
   * - ``RECORD_LAYOUT``
     - one per datatype and storage category actually used
   * - ``COMPU_METHOD``
     - one per distinct combination of conversion **and** unit
   * - ``COMPU_VTAB``
     - one per enum conversion
   * - ``GROUP``
     - one per component that exports at least one object

The record layouts and the compu methods are shared rather than repeated per object, because
they describe *how* a value is stored and scaled rather than *which* value it is, and two
objects that agree on both have no reason to carry two copies. The seven calibration objects
of the demo share five record layouts, and its twenty objects share eight compu methods:

.. code-block:: text

       /begin RECORD_LAYOUT RL_AXIS_UWORD
         AXIS_PTS_X 1 UWORD INDEX_INCR DIRECT
       /end RECORD_LAYOUT

       /begin RECORD_LAYOUT RL_VALUES_SBYTE
         FNC_VALUES 1 SBYTE ROW_DIR DIRECT
       /end RECORD_LAYOUT

An axis deposits its break points with ``AXIS_PTS_X ... INDEX_INCR``, meaning the points are
stored in increasing index order, one after the other; a parameter, value block, curve or map
deposits its values with ``FNC_VALUES ... ROW_DIR``, meaning row wise, which is how c lays
out a multidimensional array. Both use ``DIRECT`` addressing, since the generated c
declaration is the array itself and not a pointer to it.

The records share a skeleton. A measurement is written as its name, its long identifier, the
a2l datatype, the compu method, a resolution and an accuracy field, and the lower and upper
physical limits:

.. code-block:: text

       /begin MEASUREMENT ValueF "Signed measurement with a fixed point conversion"
         SWORD CM_LIN_DEGC 0 0 -40 150
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueF" 0
       /end MEASUREMENT

The long identifier is the ``description`` of the object, falling back to its name when there
is none, so the free text written once in the json is what the calibration engineer reads in
the tool. Resolution and accuracy are written as ``0`` because DDD describes the conversion
exactly and has nothing approximate to declare. The limits are the physical ``limits`` of the
object, either as the description gave them or derived from the datatype and the conversion
when it did not - ``ValueF`` is an ``sint16`` scaled by ``0.1``, and the description restricts
it to -40 .. 150 degC. A measurement with ``dimensions`` also carries a ``MATRIX_DIM`` - the
demo's array measurement is written as

.. code-block:: text

       /begin MEASUREMENT ValueB "Array measurement with four elements"
         UWORD CM_LIN_V 0 0 0 65.535
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueB" 0
         MATRIX_DIM 4 1 1
       /end MEASUREMENT

and a ``FORMAT`` or a ``DISPLAY_IDENTIFIER`` is appended in the same way when the
description asks for one under its ``a2l`` key.

Conversions, and why ``COEFFS`` looks inverted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``COMPU_METHOD`` is created per distinct pair of conversion and unit, and the unit is part
of the key because two objects scaled by the same factor but measured in different units are
not the same conversion to a calibration tool - one displays ``Hz`` and the other ``%``:

.. code-block:: text

       /begin COMPU_METHOD CM_LIN_HZ "phys = raw * 0.25 + 0"
         RAT_FUNC "%8.3" "Hz"
         COEFFS 0 1 0 0 0 0.25
       /end COMPU_METHOD

       /begin COMPU_METHOD CM_LIN_PCT "phys = raw * 0.5 + 0"
         RAT_FUNC "%8.3" "%"
         COEFFS 0 1 0 0 0 0.5
       /end COMPU_METHOD

The generated names are derived from the conversion and the unit, so ``CM_LIN_HZ`` is
readable in a tool rather than being a serial number, and a unit that is not a valid
identifier is transliterated - ``%`` becomes ``PCT``, ``m/s^2`` becomes ``M_PER_S2``. When two
different conversions share a unit, the second one gets a numeric suffix; the demo carries
both ``CM_LIN_PCT`` (factor 0.5) and ``CM_LIN_PCT_2`` (factor 0.1).

The ``COEFFS`` line is the part that surprises everybody who reads an a2l for the first time.
A description says ``{"kind": "linear", "factor": 0.25, "offset": 0.0}``, which means
``physical = raw * factor + offset``, and yet the coefficients written out are
``0 1 0 0 0 0.25``. The reason is that ``RAT_FUNC`` describes the conversion in the *other*
direction. Its six coefficients ``a b c d e f`` define

.. code-block:: text

   raw = (a * phys^2 + b * phys + c) / (d * phys^2 + e * phys + f)

which is the formula a calibration tool needs when the user types a physical value and the
tool has to work out the bit pattern to write into the target. Substituting the linear case
``phys = raw * factor + offset``, and therefore ``raw = (phys - offset) / factor``, gives
``a = 0``, ``b = 1``, ``c = -offset``, ``d = 0``, ``e = 0``, ``f = factor`` - so the factor
appears in the denominator slot and the offset appears negated. A conversion with a non-zero
offset makes that visible: ``{"factor": 0.25, "offset": -40.0}`` becomes

.. code-block:: text

       /begin COMPU_METHOD CM_LIN_DEGC "phys = raw * 0.25 + -40"
         RAT_FUNC "%8.3" "degC"
         COEFFS 0 1 40 0 0 0.25
       /end COMPU_METHOD

which is why the description string of the record spells the forward formula out: the
``COEFFS`` line is correct but unreadable, and the human reading the file should not have to
invert a rational function in their head to find out that the raw value 0 means -40 degC.

An identity conversion becomes an ``IDENTICAL`` compu method carrying the unit, and an
identity conversion on an object that has no unit either becomes no compu method at all - the
literal keyword ``NO_COMPU_METHOD``, since there is nothing to convert and nothing to
display:

.. code-block:: text

       /begin COMPU_METHOD CM_IDENT_DEGC "physical value in degC"
         IDENTICAL "%8.3" "degC"
       /end COMPU_METHOD

       /begin MEASUREMENT ValueI "Bit coded measurement written by the user interface"
         ULONG NO_COMPU_METHOD 0 0 0 4294967295
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueI" 0
       /end MEASUREMENT

The display format of a generated compu method is ``%8.0`` when both the datatype and the
conversion are integral and ``%8.3`` otherwise. That is a default rather than a claim about
the value: no decimals on a plain counter avoids a column of ``.000``, and three decimals on
a value scaled by 0.25 or 0.001 shows something rather than rounding it to nothing. Where it
matters, say so per object with ``"a2l": {"format": "..."}``, which adds a ``FORMAT`` line to
that record and overrides the compu method for it.

Enumerations
~~~~~~~~~~~~

An enum conversion becomes a verbal table, so that the calibration tool shows
``STATE_DEGRADED`` where the target holds a 3. The table is a ``COMPU_VTAB``, referenced by a
``COMPU_METHOD`` of type ``TAB_VERB``, and it pairs each raw value with the name of its
enumerator - the same names that became the members of ``StateA_t`` in the generated c code,
so that the identifier the c code uses and the text the calibration tool displays are one and
the same string:

.. code-block:: text

       /begin COMPU_VTAB VTAB_StateA_t "values of StateA_t" TAB_VERB 5
         0 "STATE_OFF"
         1 "STATE_INIT"
         2 "STATE_ACTIVE"
         3 "STATE_DEGRADED"
         15 "STATE_FAULT"
       /end COMPU_VTAB

       /begin COMPU_METHOD CM_StateA_t "verbal conversion for StateA_t"
         TAB_VERB "%8.0" ""
         COMPU_TAB_REF VTAB_StateA_t
       /end COMPU_METHOD

       /begin MEASUREMENT StateA "Measurement with a verbal conversion table"
         UBYTE CM_StateA_t 0 0 0 15
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "StateA" 0
       /end MEASUREMENT

The table is written once per enum name rather than once per object, which is the direct
consequence of ``enum-conflict`` being an error: because the project cannot contain two
different definitions of ``StateA_t``, one table can serve every object that uses it. The
upper limit of ``StateA`` is 15 rather than 255, because the limits of an enum-converted
object default to the range its enumerators actually span, and offering the calibration
engineer values that mean nothing is worse than offering too few.

Arrays, ``MATRIX_DIM``, and the reversed index order
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An array shaped measurement or value block gets a ``MATRIX_DIM``, and this is the one place
where the a2l does not simply repeat what the c declaration says. **ASAP2 lists the fastest
running index first, c declares it last.** A declaration of

.. code-block:: c

   uint8_t Table[2][3];

is two rows of three elements: the second subscript is the one that walks over consecutive
addresses, so it is the fastest running index, and it is written last in c. ASAP2 wants the
dimensions in the opposite order, so DDD reverses them:

.. code-block:: text

       /begin MEASUREMENT Table "Two rows of three columns"
         UBYTE NO_COMPU_METHOD 0 0 0 255
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "Table" 0
         MATRIX_DIM 3 2 1
       /end MEASUREMENT

Emitting ``2 3 1`` instead would describe a transposed object, and the failure mode of that
mistake is nasty: the file parses, the tool connects, the display fills with plausible
numbers, and every element but the diagonal ones is read from the wrong address. This is
worth internalising when comparing a generated a2l against a hand-written one, because a
hand-written file that was never validated against a transposed table is exactly where the
discrepancy tends to hide.

``MATRIX_DIM`` in 1.6.1 carries exactly three values, so a one dimensional array is padded
with ones - the demo's ``ValueB[4]`` becomes ``MATRIX_DIM 4 1 1``. An object with more than
three dimensions cannot be expressed at all in this version. DDD writes all of its dimensions
anyway, which is what ASAP2 1.7 expects and what a 1.7 reader will understand, and reports
the situation rather than silently truncating:

.. code-block:: text

   $ ddd generate cube.ddd.json -o build/gen -t templates -W unused-output=ignore
   cube.ddd.json#component.interface[0].definition: warning[a2l-unrepresentable]: 'Cube' has 4 dimensions, but the MATRIX_DIM of ASAP2 1.6.1 carries 3; the extra dimensions are written out and only a 1.7 reader understands them
   1 warning
   wrote       build/gen/ddd_globals.c (created)
   ...

The record that comes out of it carries all four dimensions, again reversed, which is what a
1.7 reader expects and more than a 1.6.1 reader is specified to handle:

.. code-block:: text

       /begin MEASUREMENT Cube "Cube"
         UBYTE NO_COMPU_METHOD 0 0 0 255
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "Cube" 0
         MATRIX_DIM 5 4 3 2
       /end MEASUREMENT

Of the characteristics, only a value block carries a ``MATRIX_DIM``. A curve and a map do
not, because their shape follows from the axes they refer to and the number of points is
already stated in each ``AXIS_DESCR``; writing it a second time would create a second place
for the same fact to be wrong. A parameter is a scalar and has no shape to describe.

A curve, a map and their shared axes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An axis becomes an ``AXIS_PTS`` record, which is an object in its own right: it has an
address, break points stored in the target, and its own conversion and limits. The
``input`` of the axis - the measurement whose value selects the position along it - becomes
the input quantity of the record:

.. code-block:: text

       /begin AXIS_PTS AxisA "Shared axis indexed by ValueE"
         0x00000000 ValueE RL_AXIS_UWORD 0 CM_LIN_HZ 6 0 8000
         SYMBOL_LINK "AxisA" 0
       /end AXIS_PTS

The fields after the name and the long identifier are the address, the input quantity, the
record layout the points are deposited in, a maximum difference of ``0``, the compu method,
the maximum number of axis points, and the physical limits. The maximum is the ``size`` the
description gave, because the array generated for the axis is exactly that long and there is
no room for a calibration tool to add a point. An axis whose description gives no ``input``
gets the keyword ``NO_INPUT_QUANTITY`` instead of a name.

A curve or a map then refers to that axis instead of carrying its own copy of the break
points. The reference is an ``AXIS_DESCR`` of attribute ``COM_AXIS`` - a *common* axis, one
shared between several characteristics - plus an ``AXIS_PTS_REF`` naming the record above:

.. code-block:: text

       /begin CHARACTERISTIC CurveA "Calibratable curve over AxisA"
         CURVE 0x00000000 RL_VALUES_UWORD 0 CM_LIN_MS 0 655.35
         SYMBOL_LINK "CurveA" 0
         /begin AXIS_DESCR
           COM_AXIS ValueE CM_LIN_HZ 6 0 8000
           AXIS_PTS_REF AxisA
         /end AXIS_DESCR
       /end CHARACTERISTIC

       /begin CHARACTERISTIC MapA "Calibratable map over AxisA and AxisB"
         MAP 0x00000000 RL_VALUES_SBYTE 0 CM_LIN_PCT -64 63.5
         SYMBOL_LINK "MapA" 0
         /begin AXIS_DESCR
           COM_AXIS ValueE CM_LIN_HZ 6 0 8000
           AXIS_PTS_REF AxisA
         /end AXIS_DESCR
         /begin AXIS_DESCR
           COM_AXIS ValueA CM_LIN_PCT 4 0 100
           AXIS_PTS_REF AxisB
         /end AXIS_DESCR
       /end CHARACTERISTIC

The shared axis is the point of the exercise: ``CurveA`` and ``CurveB`` are declared by
different components and both refer to ``AxisA``, so the six break points exist once in the
target and recalibrating them moves both curves at the same time, which is what a shared
break point set is supposed to mean. For a map the ``AXIS_DESCR`` records appear in x, y
order, which pairs with the c declaration ``const int8_t MapA[4][6]`` - six columns along the
x axis, four rows along the y axis, deposited ``ROW_DIR``.

.. warning::
   A referenced object is **always** exported, whatever its description says. An
   ``AXIS_PTS_REF`` pointing at an axis that was kept out of the file, or an input quantity
   naming a measurement that was, is a dangling reference, and a dangling reference does not
   make the file smaller - it makes it invalid, and a calibration tool will refuse the whole
   module rather than the one record. DDD therefore starts from the objects marked for export
   and pulls in whatever they point at, transitively: a curve pulls its axis, and the axis
   pulls the measurement it is indexed by. In the following description, ``Speed`` and
   ``SpeedAxis`` are both marked ``{"export": false}`` and both appear in the a2l anyway,
   because ``Fuel`` needs them:

   .. code-block:: text

          /begin MEASUREMENT Speed "Speed"
            UWORD CM_IDENT_HZ 0 0 0 65535
            ECU_ADDRESS 0x00000000
            SYMBOL_LINK "Speed" 0
          /end MEASUREMENT

          /begin AXIS_PTS SpeedAxis "SpeedAxis"
            0x00000000 Speed RL_AXIS_UWORD 0 CM_IDENT_HZ 3 0 65535
            SYMBOL_LINK "SpeedAxis" 0
          /end AXIS_PTS

          /begin CHARACTERISTIC Fuel "Fuel"
            CURVE 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255
            SYMBOL_LINK "Fuel" 0
            /begin AXIS_DESCR
              COM_AXIS Speed CM_IDENT_HZ 3 0 65535
              AXIS_PTS_REF SpeedAxis
            /end AXIS_DESCR
          /end CHARACTERISTIC

   ``{"export": false}`` is therefore a request rather than an instruction, and it is honoured
   exactly when honouring it leaves a valid file behind. It never affects the c code: an
   object kept out of the a2l is still defined and still declared everywhere the c templates
   put it.

One group per component
~~~~~~~~~~~~~~~~~~~~~~~

The component structure of the project is not something the c code can carry - after
compilation and linking there are only symbols - but it is exactly the structure a
calibration engineer wants to navigate by, so it is preserved in the a2l as one ``GROUP`` per
component, listing the objects that component declared:

.. code-block:: text

       /begin GROUP SensorHub "Produces the raw input values of the device"
         ROOT
         /begin REF_MEASUREMENT
           ValueA
           ValueB
           ValueC
           FlagA
         /end REF_MEASUREMENT
       /end GROUP

The groups are ``ROOT`` groups, because DDD does not currently express the sub project
nesting of the description files as nested groups - ``EventLogger`` is reached through a sub
project of its own and still appears as a root group next to the others. A group lists what
its component *declared*, in any scope, so an object read by three components appears in
three groups; that is intentional, since the engineer looking at ``SensorHub`` wants to see
the values it consumes as well as the ones it produces. A component that exports no object at
all produces no group rather than an empty one.

Addresses
~~~~~~~~~

The address of an object is not known until the linker has run, and DDD generates the c code
*before* that. Every record therefore carries ``0x00000000`` unless it is told better:

.. code-block:: text

       /begin MEASUREMENT ValueE "Measurement used as the input quantity of AxisA"
         UWORD CM_LIN_HZ 0 0 0 8000
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueE" 0
       /end MEASUREMENT

Where that zero appears depends on the record, which is a wrinkle of the format rather than
of DDD: a ``MEASUREMENT`` carries its address in a keyed ``ECU_ADDRESS`` line, while an
``AXIS_PTS`` and a ``CHARACTERISTIC`` carry it as the first positional field of the record,
right after the long identifier. Both are shown in the excerpts below.

Two mechanisms exist to fix that up, and DDD offers both because projects are split between
them. The first is ``SYMBOL_LINK``, which names the c symbol the record describes and is
emitted for **every** object, always, whether or not an address is known. It is what an a2l
address patcher - a tool that reads the map file or the debug information of the linked image
and rewrites the ``ECU_ADDRESS`` fields - matches on, so a build that patches its a2l after
linking needs no configuration on the DDD side at all.

The second is ``--address-map``, which lets DDD do the substitution itself. It takes a flat
json object mapping symbol names to addresses, written either as decimal numbers or as
hexadecimal strings, whichever the tool producing it finds easier:

.. code-block:: json

   {
     "ValueE": "0x20000100",
     "AxisA": "0x08004000",
     "ParameterA": 134234112
   }

Running the generator a second time with that map produces the same a2l with the addresses
filled in:

.. code-block:: text

       /begin MEASUREMENT ValueE "Measurement used as the input quantity of AxisA"
         UWORD CM_LIN_HZ 0 0 0 8000
         ECU_ADDRESS 0x20000100
         SYMBOL_LINK "ValueE" 0
       /end MEASUREMENT

       /begin AXIS_PTS AxisA "Shared axis indexed by ValueE"
         0x08004000 ValueE RL_AXIS_UWORD 0 CM_LIN_HZ 6 0 8000
         SYMBOL_LINK "AxisA" 0
       /end AXIS_PTS

       /begin CHARACTERISTIC ParameterA "Single calibratable constant"
         VALUE 0x08004000 RL_VALUES_UWORD 0 CM_LIN_HZ 500 1500
         SYMBOL_LINK "ParameterA" 0
       /end CHARACTERISTIC

This is why DDD is normally run twice per build: once before compiling, to produce the c code
and an a2l with zero addresses, and once after linking, with the map extracted from the
linker output, to produce the a2l that ships. The second run regenerates the c code too, and
because that code has not changed it is not rewritten, so the second run does not invalidate
the build it was produced from.

A symbol the map does not mention keeps address 0 rather than being an error, since a map
produced from a linker output legitimately contains only the objects that ended up in the
image - a conditional object absent from this build has no address to report. An address
outside the range an a2l can hold, on the other hand, is refused before anything is written:

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates --address-map bad.json
   ddd: bad.json: address of 'ValueE' is 8589934591, outside the range 0 .. 0xFFFFFFFF that an a2l address can hold
   $ echo $?
   2

``ECU_ADDRESS`` is an unsigned 32 bit field. A negative value would render as ``0x-0000010``
and a wider one as a 33 bit literal, and either makes the whole file unreadable - so the
range is checked when the map is read, where the offending symbol can still be named, rather
than at formatting time where it could not. The exit code is 2, the one that means the tool
was asked to do something it cannot do, as opposed to 1, which means the project has
findings.

Conditional objects
~~~~~~~~~~~~~~~~~~~

a2l has no notion of preprocessor conditions. There is no way to say "this measurement exists
only when ``FEATURE_X`` is defined", and no way for a calibration tool to find out what was
defined when the image was built. DDD therefore exports a conditional object unconditionally
and states the condition in a comment above the record:

.. code-block:: text

       /* only present in the build when: defined(FEATURE_X) */
       /begin MEASUREMENT ValueG "Measurement that only exists when FEATURE_X is defined"
         UWORD CM_LIN_V 0 0 0 5
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueG" 0
       /end MEASUREMENT

Exporting it is the lesser of the two evils. Leaving it out would mean generating a different
a2l per build configuration, and the a2l would then have to be regenerated - not merely
patched - whenever a define changed; worse, an object that is absent from the file cannot be
distinguished from one that was never declared, so nobody would notice the omission. Leaving
it in costs one record that resolves to nothing in a build where the feature is off, and the
comment tells the reader why. The address information disambiguates the two cases in
practice: if the image was built without ``FEATURE_X``, the symbol is not in the linker
output, the address map extracted from it does not mention the symbol, and the record keeps
its address of 0 - which is not the address of anything DDD declared, and is therefore
recognisable as "this object is not in this build" rather than being confused with a real
variable.

Keeping an object out of the a2l
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``"a2l": {"export": false}`` on a definition keeps it out of the file, subject to the
reference rule above. The demo uses it twice, on scratch data that a calibration tool has no
business displaying:

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "name": "ValueD",
       "kind": "measurement",
       "description": "Component local measurement, kept out of the a2l",
       "datatype": "uint16",
       "conversion": { "kind": "identity" },
       "dimensions": [8],
       "a2l": { "export": false },
       "volatile": false
     }
   }

Note that ``scope`` has nothing to do with it. A ``local`` object is still exported: locality
is a statement about which c file may see the declaration, and a calibration engineer needs
to reach the parameters of a component whether or not another component may read them. Of the
demo's calibration objects, ``ParameterA``, ``AxisB``, ``CurveA``, ``MapA``, ``CurveB`` and
``BlockA`` are all declared ``local`` and all appear in ``DemoDevice.a2l``.

.. note::
   A change to what the a2l says about an object is not invisible to
   :doc:`ddd compare </comparing_deliveries>`: the ``changed-a2l`` check reports it as a
   warning when a candidate delivery is measured against an archived baseline, because a
   calibration file prepared against the previous a2l may no longer apply cleanly.
