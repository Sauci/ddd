Concept
=======

In a component based embedded software project, the components talk to each other by reading
and writing global variables. That is a perfectly reasonable design for a target with a few
kilobytes of ram and no operating system worth the name: a write costs one store instruction,
a read costs one load, there is no message queue to size and no serialisation to get wrong.
What it costs instead is that the interface between two components exists only by convention.
Nothing in the c code says that ``ValueE`` is written by the controller and read by the user
interface; the compiler sees one ``extern uint16_t`` and is perfectly happy to let anybody
assign to it.

A convention holds for as long as the people who agreed on it remember it, and it stops
holding at exactly the point where the project gets large enough for that to matter. Three
failure modes recur.

An **interface that exists only by convention is not reviewable.** When a component is
delivered by another team or another company, the only description of what it produces and
what it consumes is a header file somebody wrote by hand, a spreadsheet, and eventually a
conversation. There is no artefact an integrator can check before the first build, and no
artefact a supplier can be held to.

A variable with **no single owner is written from two places.** This is the failure that
survives compilation and linking: two components both decide that they are the ones computing
``SharedValue``, the linker resolves both writes to the same address, and the value the
consumers observe depends on the order in which the two producers happen to run. Nothing in
the build reports it, and the symptom appears months later as an intermittent fault.

**Silent drift** is the slowest of the three. A component declares ``ValueF`` as an ``sint16``
scaled by 0.1 degC per bit; six months later its author rescales it to 0.01, and the consumer
- which declared its own ``extern int16_t ValueF`` in its own header, because that is how c
works - keeps multiplying by 0.1. The software compiles, links, runs, and reports every
temperature wrong by a factor of ten. The same drift reaches the calibration engineer, because
the a2l file that describes the scaling to the measurement and calibration tool is maintained
by hand somewhere else again.

DDD removes all three by turning the interface into an artefact rather than an agreement.
Every component describes the variables it produces and consumes in a small json file, DDD
checks that all components agree, and then DDD - not the component authors - writes the c code
that declares and defines those variables, and the a2l file that describes them to the
measurement and calibration tools.


Principles
----------

Four principles decide everything else in the tool. They are worth reading before the file
formats, because most of the questions that come up later - "why can I not just declare it in
my own header?", "why does DDD refuse two writers?", "why is the producer's definition the one
that wins?", "why does DDD not decide what my generated header is called?" - are answered by
one of them.

Every component declares its data interface explicitly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A component ships a ``*.ddd.json`` file listing every global variable it takes part in,
together with what the value *is*: its datatype, its physical unit, the conversion from the
raw stored value to the physical one, its limits, its initial value, whether the software has
to re-read it at every access, and, for calibration data, the axes it is defined over. Nothing
about a shared variable stays implicit, and in particular nothing about it lives in a hand
written header that only one team ever reads.

.. code-block:: json

   {
     "scope": "output",
     "definition": {
       "name": "ValueF",
       "kind": "measurement",
       "description": "Signed measurement with a fixed point conversion",
       "datatype": "sint16",
       "unit": "degC",
       "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
       "limits": { "min": -40, "max": 150 },
       "init": -400,
       "volatile": false
     }
   }

Writing the unit and the conversion down next to the datatype is not decoration: they are part
of the interface in exactly the same way the datatype is. A consumer that reads ``ValueF`` as
raw counts and multiplies by 0.01 is as broken as one that reads it as a ``uint8_t``, and both
are equally invisible to a compiler. Because the declaration is a data file rather than c code,
DDD can compare it against the declaration made by every other component, which is the second
half of the job and the subject of :doc:`consistency_checks`.

The description is also the only place the information is written down. The same declaration
produces the c definition, the comment above it, the ``extern`` declaration in each consumer's
header and the ``MEASUREMENT`` entry of the a2l, so those four cannot disagree with each other.
Changing the scaling is one edit in one file, and everything that depends on it follows on the
next build.

Exactly one component owns each variable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each declaration carries a scope, and a variable may be declared ``output`` by exactly one
component. That component is the **producer** of the variable, and two consequences follow.

The first is that a second writer becomes a build error rather than a race nobody notices, and
that the error names both declarations before anything is compiled. The second is that when
two components describe the same variable differently, the disagreement has a resolution
rather than a discussion: **the producer's declaration is the authoritative one.** It is the
definition that gets generated, and the diagnostic points at the consumer that deviates from
it, which is also the component that has to change. Both appear in the ``inconsistent``
example, whose whole point is to fail:

.. code-block:: text

   $ ddd check examples/inconsistent/project.ddd.json
   examples/inconsistent/component_b.ddd.json#component.interface[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
       note: examples/inconsistent/component_a.ddd.json#component.interface[0]: also written here
   examples/inconsistent/component_c.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'SharedValue' is declared differently by component 'ComponentC' than by 'ComponentA' (datatype: uint16 != sint16, conversion: identity != linear(factor=0.5, offset=0))
       note: examples/inconsistent/component_a.ddd.json#component.interface[0].definition: reference declaration
   examples/inconsistent/component_c.ddd.json#component.interface[1]: error[missing-producer]: 'MissingValue' is read by component 'ComponentC' but no component declares it as output
   examples/inconsistent/component_c.ddd.json#component.interface[2]: error[local-conflict]: 'Scratch' is local to component 'ComponentA' but is also declared as input by component 'ComponentC'
       note: examples/inconsistent/component_a.ddd.json#component.interface[2]: declared local here
   examples/inconsistent/component_a.ddd.json#component.interface[1]: warning[unused-output]: 'UnusedSignal' is written by component 'ComponentA' but read by nobody
   4 errors, 1 warning

Every finding names the file, the path inside it and the check that produced it, and the
findings are collected rather than raised one at a time, so a single run tells an integrator
everything that does not fit. The remaining three findings above belong to the scopes and are
discussed below; :doc:`consistency_checks` covers the full list and how a project changes the
severity of any of them.

Ownership is what makes a project reviewable rather than merely consistent. For every variable
there is one component, one file and one team answerable for what the value means.
:doc:`comparing_deliveries` builds directly on that, because a variable that changed owner
between two deliveries is a fact somebody needs to be told about even when both deliveries are
internally consistent.

Access rules are enforced by what is generated
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A rule that depends on everybody remembering it is not a rule, so DDD does not ask components
to respect the declared scopes. It generates the code so that respecting them is the path of
least resistance and, optionally, the only path that compiles at all.

Every component gets one header containing the declarations of that component and nothing
else, and that header is the only one a component is expected to include. There is deliberately
no project wide header offering everything: ``ddd_globals.h`` declares every object of the
project, but it exists so that the single definition file can be compiled with full prototype
checking, and it says so in its own text rather than leaving the reader to guess. Provided a
component includes its own header, a name it never declared - say ``BlockA``, which belongs to
the user interface - has no declaration on its include path at all, so a reference to it fails
with an ordinary undeclared identifier error, at the point of the mistake, in the component
that made it.

.. code-block:: c

   /* Controller.h, shortened - the whole file has the same three sections */

   /* outputs - written by Controller, read by other components */
   /** Measurement used as the input quantity of AxisA [Hz] */
   extern volatile uint16_t ValueE;
   /** Signed measurement with a fixed point conversion [degC] */
   extern int16_t ValueF;

   /* inputs - produced elsewhere, Controller may only read them */
   /** Scalar measurement with a linear conversion [%] */
   extern uint8_t ValueA;  /* produced by SensorHub */
   /** Array measurement with four elements [V] */
   extern volatile uint16_t ValueB[4];  /* produced by SensorHub */

   /* locals - owned exclusively by Controller */
   /** Component local measurement of the controller [%] */
   extern int16_t ValueH;

Visibility alone cannot stop a component from writing to a variable it legitimately reads,
since a consumer needs the declaration in order to read it at all. ``--const-inputs`` closes
that gap by qualifying inputs ``const`` in the consumer headers, which turns a write to a
foreign variable from a convention into a constraint violation the compiler has to diagnose:

.. code-block:: c

   /* UserInterface.h, generated with --const-inputs */

   /* inputs - produced elsewhere, UserInterface may only read them */
   /** Measurement used as the input quantity of AxisA [Hz] */
   extern const volatile uint16_t ValueE;  /* produced by Controller */
   /** Signed measurement with a fixed point conversion [degC] */
   extern const int16_t ValueF;  /* produced by Controller */

.. note::

   The definition in ``ddd_globals.c`` stays non-const, because the producer has to be able to
   write it. Declaring the same object ``const`` in one translation unit and non-const in
   another is a constraint violation in strict c, even though the usual embedded toolchains
   accept it and generate exactly the code one expects. That is why the stronger enforcement
   is opt-in rather than the default: a project decides for itself whether its toolchain and
   its coding standard allow it.

The same principle runs through the rest of the tool. A component local variable is defined in
``ddd_globals.c`` like any other, so that the project still has exactly one definition per
object, but its declaration appears in the header of its owner and nowhere else. An axis that
a curve refers to is written to the a2l even when the axis itself was marked as not exported,
because an ``AXIS_PTS_REF`` without the ``AXIS_PTS`` it points at would not be a valid a2l file
and the calibration tool would reject the whole thing. In both cases the rule is carried by
what comes out of the generator, not by a sentence in a document that somebody has to have
read.

DDD owns the data, the project owns the presentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What the generated c *says* follows from the declarations. What it *looks like* does not: the
comment style, the banner, the include guards, the section headings and the names of the files
themselves are house style, they differ between projects, and nothing in a description file
decides them. A generator that imposed its own would either be argued with or be worked around
with a post-processing script, so DDD does not: the c sources are rendered from jinja2
templates the project provides. ``ddd generate`` requires ``--template-dir`` and falls back to
nothing, ``ddd templates-dir`` prints a working set of examples to copy into a project and
change, and a project renames a generated file by renaming the template that produces it. Even
the file names above are the example templates': ``ddd_globals.h`` is called that because a
template is called ``ddd_globals.h.jinja2``. :doc:`templates` describes the rules in full.

Owning the presentation is not owning the rules. A component template is handed the
declarations of its own component - already grouped by scope, already spelled in c, already
qualified ``const`` where ``--const-inputs`` says so - and the ownership, the visibility and
the datatypes are settled before any template runs. The example templates write plain c
comments because a comment convention is exactly the kind of decision this principle leaves to
the project; one that documents its generated code differently, or not at all, changes the
comment in the template and nothing else.

The a2l file is the exception that proves the point. Its structure is dictated by ASAM rather
than by a house style: a measurement and calibration tool rejects a ``COMPU_METHOD`` in the
wrong place no matter whose coding standard produced it. There is nothing for a project to
decide there, so there is no template option for the a2l either - that backend carries its own
templates and stays internal.


Vocabulary
----------

The terms below are used with these meanings throughout the documentation, the diagnostics and
the json schemas. They describe the roles the data plays, not the kind of device the software
runs on: DDD is not tied to any industry, and "measurement" or "calibration parameter" say
what a value is *for*, not what it controls.

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - term
     - meaning
   * - project
     - a named set of components and/or sub-projects, described by a file whose top level key
       is ``project``. The project name becomes the a2l project and module name, so it is the
       name the calibration engineer sees.
   * - component
     - a software unit with an explicitly declared data interface, described by a file whose
       top level key is ``component``. One component corresponds to one generated header and
       to one a2l ``GROUP``.
   * - declaration
     - one entry of a component interface: a scope, an optional c preprocessor condition and a
       definition. A component takes part in a variable by declaring it, and only by
       declaring it.
   * - data object
     - the thing being declared: a measurement, a parameter, a value block, a curve, a map or
       an axis. "Variable" and "data object" are used interchangeably; the second is the more
       precise word once calibration data is involved.
   * - scope
     - ownership and visibility of a data object with respect to the declaring component, one
       of ``input``, ``output`` and ``local``.
   * - conversion
     - the rule that maps the raw value stored in the target to the physical value a human
       reads: the identity, a linear factor and offset, or an enumeration.
   * - producer
     - the component that owns a data object, that is the one which declared it ``output`` or
       ``local``. Its declaration is the authoritative one when components disagree.
   * - data dictionary
     - the resolved result: every object with its owner, its consumers, its shape and its
       limits worked out. It is the contract between the checking front end and the output
       backends, and DDD publishes it - see :doc:`data_dictionary`.


scope
-----

A declaration states what the declaring component does with the object, and that single word
is all DDD needs in order to work out ownership, visibility and the direction of every
interface in the project.

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - scope
     - meaning
   * - ``input``
     - the component reads the object, and some other component has to produce it. An input
       that nobody produces is reported as ``missing-producer``, because such a project would
       link only if some hand written translation unit happened to define the symbol, and
       that definition would be outside DDD's control.
   * - ``output``
     - the component owns the object, and exactly one component may do so. Its declaration is
       the authoritative one, and the object appears in the headers of the consumers annotated
       with the name of its producer.
   * - ``local``
     - the component owns the object exclusively and no other component may use it. A second
       component declaring the same name is reported as ``local-conflict`` rather than
       quietly becoming a consumer.

For a measurement, ``output`` has the obvious reading: the component writes the variable at
run time and everybody else reads it. For calibration data - parameters, value blocks, curves,
maps and axes - the software never writes anything at all, since those objects are generated
``const``. ``output`` there means that the component *provides* the data and that other
components may read it; the writing is done by the calibration tool, from outside the
software.

Whether the software has to *notice* that writing is the other half of the answer, and it is
what every definition states as ``volatile``. An object a calibration tool tunes while the
software runs is generated ``const volatile``, because ``const`` alone lets the compiler use
the initial value in place of a read wherever it can see it - within one translation unit at
every optimisation level, ``-O0`` included, and across them under ``-flto`` - and, where the
load does survive, still lets it serve two reads from one of them. Either way the tool writes
a value the software does not pick up. The qualifier
costs the read only section: gcc moves a ``const volatile`` object out of ``.rodata`` into
``.data``, which on a flash target is a question the linker script has to answer. An object
that is never tuned online states ``false``, is generated plain ``const`` and stays in read
only memory. DDD states no preference between the two and reports nothing about the choice;
it renders what the description says.

The demo project uses both readings. ``AxisA`` is declared ``output`` by the controller and
``input`` by the user interface, which defines its own curve ``CurveB`` over the controller's
break points - the axis is stored once and shared, which is what the a2l calls ``COM_AXIS``.
The controller's ``ParameterA``, on the other hand, is ``local``, because it parametrises the
controller and nothing else:

.. code-block:: text

   $ ddd list examples/demo/demo.ddd.json
   VARIABLE    KIND         DATATYPE  UNIT  SHAPE   INIT               PRODUCER               CONSUMERS
   AxisA       axis         uint16    Hz    [6]     [...]              Controller             UserInterface
   AxisB       axis         uint8     %     [4]     [...]              Controller (local)     -
   BlockA      value_block  uint8     -     [8]     [...]              UserInterface (local)  -
   CurveA      curve        uint16    ms    [6]     [...]              Controller (local)     -
   CurveB      curve        uint8     %     [6]     200 (= 100 %)      UserInterface (local)  -
   FlagA       measurement  boolean   -     -       0                  SensorHub              EventLogger
   MapA        map          sint8     %     [4][6]  [...]              Controller (local)     -
   ParameterA  parameter    uint16    Hz    -       3200 (= 800 Hz)    Controller (local)     -
   StateA      measurement  uint8     -     -       0 (= STATE_OFF)    Controller             UserInterface
   ValueA      measurement  uint8     %     -       0 (= 0 %)          SensorHub              Controller
   ValueB      measurement  uint16    V     [4]     0 (= 0 V)          SensorHub              Controller, UserInterface
   ValueC      measurement  float32   degC  -       -                  SensorHub              UserInterface
   ValueD      measurement  uint16    -     [8]     -                  SensorHub (local)      -
   ValueE      measurement  uint16    Hz    -       0 (= 0 Hz)         Controller             UserInterface, EventLogger
   ValueF      measurement  sint16    degC  -       -400 (= -40 degC)  Controller             UserInterface
   ValueG      measurement  uint16    V     -       1000 (= 1 V)       Controller             UserInterface
   ValueH      measurement  sint16    %     -       0 (= 0 %)          Controller (local)     -
   ValueI      measurement  uint32    -     -       0                  UserInterface          EventLogger
   ValueJ      measurement  uint8     -     -       0                  EventLogger            UserInterface
   ValueK      measurement  sint8     -     [3][4]  [...]              EventLogger (local)    -

``local`` is the normal choice for calibration data that only tunes its owning component, and
it is worth preferring over ``output`` whenever it applies: it keeps the object out of every
other component's header, and it lets the tool report a new user as a mistake instead of
silently accepting it.

.. note::

   Scope is a property of a *declaration*, not of an object. The same object is ``output`` in
   the file of its producer and ``input`` in the file of every consumer, and each side states
   the full definition. That redundancy is deliberate: it is precisely what allows DDD to
   notice that the two sides have drifted apart, which a single shared declaration could never
   do.


Position in the build process
-----------------------------

DDD is a command line tool, so that it can be driven from make, from CMake, from a batch file
or from a ci job, and it runs **twice per build**. Understanding why there are two runs
explains most of what the build system integration does.

The first run happens before anything is compiled. It reads the project description, follows
the includes, resolves the declarations of all components into one data dictionary, runs the
consistency checks and - only if they pass - renders the project's c templates and writes a
first a2l file. From then on the compiler has both the definitions of every global variable
and one header per component:

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

The second run happens after linking, and it exists because of one piece of information that
does not exist before then: the address of every object in the target. A measurement and
calibration tool reaches a variable over the debug or xcp interface by address, so an a2l
without addresses describes the software correctly but cannot be used to measure it. The
addresses are decided by the linker, so DDD is handed a symbol to address map extracted from
the linker output and rewrites the a2l with the real values. The map is a flat json object,
with the addresses written in decimal or hexadecimal:

.. code-block:: json

   { "ValueE": "0x20000100", "AxisA": "0x08004000", "CurveA": 134234112 }

.. code-block:: text

   $ ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates --address-map build/addresses.json
   unchanged   build/gen/ddd_globals.c
   unchanged   build/gen/ddd_globals.h
   unchanged   build/gen/ddd_types.h
   unchanged   build/gen/Controller.h
   unchanged   build/gen/SensorHub.h
   unchanged   build/gen/UserInterface.h
   unchanged   build/gen/EventLogger.h
   wrote       build/gen/DemoDevice.a2l (updated)

The second run regenerates everything but writes only what actually changed - which, since the
declarations did not move, is the a2l alone. That property is not a convenience for the console
output. A generated file whose content is identical is left untouched on disk, so its time
stamp does not move and the build system does not rebuild the whole project after the address
import. For the same reason the generated files carry no time stamp of their own, and
regenerating from unchanged inputs produces a byte identical result, which is what makes a
delivery reproducible.

Before the address map is applied every address in the a2l is ``0x00000000``; afterwards the
objects named in the map carry their real address, and the ones that are not named keep zero.
``SYMBOL_LINK`` is emitted in both cases, so a project that would rather patch the addresses
into the a2l with a separate tool after linking can skip the second run entirely and still
have the symbol names in the file:

.. code-block:: text

   /begin MEASUREMENT ValueE "Measurement used as the input quantity of AxisA"
     UWORD CM_LIN_HZ 0 0 0 8000
     ECU_ADDRESS 0x20000100
     SYMBOL_LINK "ValueE" 0
   /end MEASUREMENT

.. uml::

   folder "software repository" as repository {
       collections "component descriptions\n(*.ddd.json)" as component_files
       file "project description\n(demo.ddd.json)" as project_file
       collections "c templates\n(*.jinja2)" as templates
       collections "hand written\nc sources" as c_sources
   }

   component "ddd generate" as ddd_first
   component "ddd generate\n--address-map" as ddd_second
   component "compiler / linker" as toolchain

   artifact "ddd_globals.c, ddd_globals.h,\nddd_types.h, one header\nper component" as generated_c
   artifact "project a2l\n(addresses 0x00000000)" as provisional_a2l
   artifact "firmware image" as image
   file "addresses.json\n(symbol to address)" as address_map
   artifact "project a2l\n(linker addresses)" as final_a2l

   component "measurement and\ncalibration tool" as mc_tool

   component_files --> project_file: collected through\nthe includes key
   project_file --> ddd_first: the consistency\nchecks run here
   templates --> ddd_first: --template-dir: the c files\nand their names come from here
   ddd_first --> generated_c
   ddd_first --> provisional_a2l

   generated_c --> toolchain
   c_sources --> toolchain: each component includes\nits own header only
   toolchain --> image
   image --> address_map: symbol addresses taken\nfrom the linker output

   project_file --> ddd_second
   templates --> ddd_second
   address_map --> ddd_second
   ddd_second --> final_a2l: the c sources are\nregenerated unchanged
   final_a2l --> mc_tool: measure and calibrate\nthe built software

Neither run needs a compiler, a target or a calibration tool to be present, which is what makes
the tool usable from a pipeline that only checks: :doc:`command_line_interface` describes the
exit codes and the machine readable output a ci job consumes, and :doc:`build_integration`
reduces the whole sequence above to two calls in a CMake project.

.. note::

   A project that has no use for an a2l at all can pass ``--no-a2l`` and use DDD purely as the
   owner of its global variables; a project that only wants the verdict, for instance in a
   merge request pipeline, runs ``ddd check`` and generates nothing.


How the tool is put together
----------------------------

The internal structure of DDD deserves a paragraph in a conceptual page because it is visible
from the outside. It is the reason the tool can be relied on to say the same thing about a
project in c as it says in a2l, and the reason a project can generate an output format DDD
does not ship.

Everything DDD knows about a project passes through a single artefact, the **data dictionary**.
The front end - the file formats, the loader that follows the includes and the analysis that
works out ownership, agreement and references - produces it, and mentions neither c nor a2l
anywhere. The backends consume it, and never touch a description file, a glob or a check. The
c backend knows what a ``uint16_t`` is and has never heard of a ``COMPU_METHOD``; the a2l
backend knows what a ``UWORD`` is and has never heard of an include guard.

The two differ in where their templates come from, and that difference is the fourth principle
in code. The c backend is handed a template directory and renders whatever it finds there, so
the shape of the generated c is outside the tool; the a2l backend is self-contained, because
the shape of an a2l file is outside the *project*.

.. uml::

   package "front end - knows no output format" as front_end {
       component "ddd.models\nthe json file formats,\nstorage sizes, value ranges" as models
       component "ddd.loading\nfiles, includes, globs" as loading
       component "ddd.analysis\nownership, agreement,\nreferences" as analysis
   }

   component "ddd.ir.DataDictionary\nthe contract: every object with\nits owner, consumers,\nshape and limits" as dictionary

   package "backends - one output format each" as backends {
       component "ddd.backends.c\nuint16_t, literals, include\nguards; renders the\nproject's templates" as c_backend
       component "ddd.backends.a2l\nUWORD, compu methods,\nrecord layouts; carries\nits own templates" as a2l_backend
   }

   folder "c templates of the project\n(*.jinja2, --template-dir)" as c_templates
   artifact "ddd_globals.c, ddd_globals.h,\nddd_types.h, one header\nper component" as c_files
   artifact "project a2l" as a2l_file

   loading --> models: parses the description\nfiles into
   models --> analysis
   analysis --> dictionary: resolves ownership\nand agreement into
   dictionary --> c_backend
   dictionary --> a2l_backend
   c_templates --> c_backend: name and render\nthe c files
   c_backend --> c_files
   a2l_backend --> a2l_file

Two things follow from that split. The dictionary is **published**: ``ddd dump`` writes it out
as json and ``ddd schema dictionary`` prints its schema, so a generator DDD does not ship - a
header for another language, a csv for a test bench, an ARXML - can consume the resolved data
of a project without depending on anything inside the tool. And a backend is nothing more than
an object with a ``name`` and a ``generate(dictionary, output_dir)`` method
(the ``Backend`` protocol of ``ddd.backends.base``), so adding an output format means adding a
package next
to the two existing ones and listing it where the generate command assembles its backends,
and changing nothing else.

The boundary is not a matter of intent. The test suite walks the import graph and fails the
build if the front end imports a backend, if a backend reaches into the loader or the analysis,
or if one backend imports the other; it also fails if a spelling that belongs to a single
output format - ``uint16_t``, ``UWORD``, ``AXIS_PTS`` - appears anywhere in the file formats.
The layering therefore cannot rot silently, and :doc:`developer_documentation` describes those
guards in detail.

One last property of the front end is easier to appreciate here than in a reference page: the
loader and the analysis never raise on a bad project. They collect as many findings as they
can in one run and report them together, because an integrator assembling a dozen components
wants the list of everything that does not fit, not the first thing that did not.
