FAQ
===

The questions below are the ones a project asks in its first weeks with DDD. Most of them
have the same shape: the tool did something the reader did not expect, and the reason is a
rule that protects either the generated c code or the generated a2l from a file that would
compile, link and then be wrong. Each answer therefore names the check, the option or the
key involved, so that the full story can be looked up in the
:doc:`consistency checks </consistency_checks>`, in the
:doc:`file formats </file_formats/index>` or in the
:doc:`command line interface </command_line_interface>`.

Why must my description files be named ``*.ddd.json``?
------------------------------------------------------

Because a description file has to be recognisable without being opened. An embedded
repository is full of json - compilation databases, tool configurations, package manifests -
and DDD has to be able to say, to a build script, to a linter, to an editor and to a human
reviewing a merge request, which of those files it owns. The double extension does that with
a single pattern, and it is the same pattern a project uses to collect its members:
``"includes": ["components/*.ddd.json"]`` picks up every component of a directory and nothing
else, which is only safe because nothing else can be a description file.

A file with any other name is reported as ``file-extension``, an error by default:

.. code-block:: text

   $ ddd check sensor_hub.json
   sensor_hub.json: error[file-extension]: 'sensor_hub.json' is a DDD description file and has to be named '*.ddd.json'
   1 error

While a project is being migrated, the check can be relaxed like any other, and the run then
continues into the interface checks as usual:

.. code-block:: text

   $ ddd check sensor_hub.json -W file-extension=warning
   sensor_hub.json: warning[file-extension]: 'sensor_hub.json' is a DDD description file and has to be named '*.ddd.json'
   sensor_hub.json#component.interface[0]: warning[unused-output]: 'ValueA' is written by component 'SensorHub' but read by nobody
   sensor_hub.json#component.interface[1]: warning[unused-output]: 'ValueB' is written by component 'SensorHub' but read by nobody
   sensor_hub.json#component.interface[2]: warning[unused-output]: 'ValueC' is written by component 'SensorHub' but read by nobody
   sensor_hub.json#component.interface[3]: warning[unused-output]: 'FlagA' is written by component 'SensorHub' but read by nobody
   5 warnings

.. note::
   The relaxation matters for more than the wording of one line. Reading the files and
   checking the interfaces are two phases, and the second one does not start when the first
   produced an error - a workspace that could not be read has nothing trustworthy to say
   about ownership or agreement. So as long as ``file-extension`` is an error, it is the only
   finding you get; the ``unused-output`` warnings above - what a component read on its own
   has to say about outputs nobody reads - appear only once the file has been renamed or the
   check has been relaxed, and so would a reserved identifier or a duplicate declaration
   further down the same file.

Can I check a single component before it is integrated?
-------------------------------------------------------

Yes, and this is why a component file is accepted wherever a project file is: the team that
writes a component should not have to assemble the whole device to find out that its own
description is malformed. ``ddd check``, ``ddd list`` and ``ddd generate`` all take one
component file just as happily as a project.

Some checks then fire for a reason that is not a defect, because a component read on its own
has no peers. Its inputs are produced by components that are, by definition, not in the file,
which is what ``missing-producer`` reports - an error, so the run fails; its outputs are read
by components that are not there either, which ``unused-output`` reports as a warning; and a
type, unit, section, constant or raster it takes from the project's vocabulary is declared in
a file that is not there. Holding those back is what makes the result meaningful:

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

   $ ddd check examples/demo/components/controller.ddd.json --standalone
   ok: 12 variables in 1 component are consistent

What remains is everything a component can get wrong on its own: reserved and colliding
identifiers, initial values that do not fit their datatype, limits outside the range the
datatype can represent, references to axes that do not exist or are of the wrong
kind. That is the check worth running in the component's own
pipeline, and the cmake integration wires exactly this invocation - the same two overrides -
into the ``<target>.ddd`` target it creates for every registered component (see
:doc:`build integration </build_integration>`).

What is the difference between ``ddd check`` and ``ddd compare``?
-----------------------------------------------------------------

They answer two questions that a project tends to confuse, and neither answer implies the
other. ``ddd check`` asks *do these components fit together*: one writer per variable,
everybody agreeing on what the variable is, every reference resolving. ``ddd compare`` asks
*can this delivery replace the one already out there*, which cannot be answered from the
sources alone, because the previous delivery is not in them - it has to be archived at
release time with ``ddd dump`` and handed back later.

A project can pass the first question and fail the second. Rescaling a value is the classic
case: every component is changed consistently, so the interfaces agree perfectly, and the
result is a software image that reports every value wrong by a constant factor to a
calibration tool still using yesterday's a2l:

.. code-block:: text

   $ ddd check device.ddd.json
   ok: 1 variable in 2 components are consistent

   $ ddd compare baseline.json device.ddd.json
   device.ddd.json: error[changed-interface]: 'InletPressure' is not the same object any more (conversion: linear(factor=0.2, offset=0) != linear(factor=0.1, offset=0)), read by Controller
   1 error
   device.ddd.json cannot replace baseline.json

The other direction happens too: a delivery can be a flawless replacement for the baseline
and still be internally broken, because the baseline says nothing about the components that
were added since. Asking both questions in one exit code is what the ``--baseline`` option of
``ddd check`` is for. The comparison itself is graded and directional - widening a limit is
silent, narrowing it is a warning, changing a datatype is an error - and is described in
:doc:`comparing deliveries </comparing_deliveries>`.

What happened to this variable?
-------------------------------

An id, once written, is never rewritten by DDD itself, so wherever the object is today it
still carries the one it was given, however many times it has since been renamed or moved
from one file or component to another. Searching the tree for it is what finds the object,
under whatever it is called now:

.. code-block:: bash

   git grep k7m2q9xr4t8w -- '*.ddd.json'

The id does not exist before the commit that writes it, which is exactly what ``git log -S``
looks for, so the same id also finds that commit - typically the one that says why, in its
message:

.. code-block:: bash

   git log -S k7m2q9xr4t8w --oneline -- '*.ddd.json'

``git log -S`` will not find a rename by itself: renaming an object edits its ``name``, not
its ``id``, so the id's count of occurrences does not change and there is nothing in that
commit for it to notice. What the object used to be called is exactly what
``ddd compare --renames`` already wrote down when the rename happened, in the ``renames.json``
of that delivery (:doc:`comparing deliveries </comparing_deliveries>`) - the record to keep,
rather than one to reconstruct from git after the fact.

Can I relax a check for one project?
------------------------------------

Yes, with ``-W CHECK=SEVERITY``, repeated as often as needed, where the severity is one of
``error``, ``warning``, ``info`` and ``ignore``; ``--strict`` goes the other way and turns
every warning into an error. ``ddd checks`` lists the identifiers and their defaults, and
both an unknown identifier and an unknown severity are refused as a usage error rather than
being quietly ignored, because a silently misspelled override is a check nobody runs:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W no-such-check=ignore
   ddd: unknown check 'no-such-check'

Seven checks cannot be relaxed - ``file-not-found``, ``json-syntax``, ``file-kind``,
``schema``, ``include-cycle``, ``plugin-not-found`` and ``plugin-invalid`` - and
``ddd checks`` marks them ``(fixed)``. Most of them report that a file could not be read at
all, and a file that could not be read has nothing further to say; the last two report that a
project names a plugin that cannot be found or is not well formed, and a project cannot be
interpreted without the plugins it names. Downgrading any of them would only replace one
clear diagnostic with an unpredictable pile of consequences:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json -W schema=ignore
   ddd: the severity of check 'schema' cannot be changed

There is deliberately no severity section in the project description. A severity is a
decision about how a *build* treats a finding, not a property of the data, and two builds
over the same components may legitimately disagree - the component's own pipeline ignores
``missing-producer``, the image's pipeline must not. The place to record the decision is
therefore the build system, where the ``SEVERITY`` option of ``ddd_generate`` passes the same
overrides:

.. code-block:: cmake

   ddd_generate(firmware.elf NAME DemoDevice
                TEMPLATE_DIRECTORY "${templates}"
                SEVERITY unused-output=ignore)

Two components disagree - whose definition is generated?
--------------------------------------------------------

The producer's. A variable has exactly one owner, the component that declares it ``output``
or ``local``, and that component's declaration is the authoritative one: it is the definition
that reaches the generated c code and the a2l, and the diagnostics point at the deviating
consumer rather than at it. The alternative - first declaration wins, or file order wins -
would make the generated code depend on the order in which a project happens to list its
includes.

What that means in practice depends on *what* the two sides disagree about. A disagreement
about the interface - kind, datatype, unit, conversion, shape, limits, the ``volatile``
qualifier or the axes an object refers to - is a ``definition-mismatch`` error and generation
refuses to run, because two components compiled against two different views of the same memory
is precisely the class of bug DDD exists to prevent. A disagreement about how the a2l
*presents* the object - a format string, a display name - is a ``storage-mismatch`` warning,
since both components can be compiled against the producer's choice without either of them
being wrong about the data. Only two stated values can disagree that way; a consumer that
merely leaves the ``a2l`` block or one of its keys out is not asking for anything and is not
reported:

.. code-block:: text

   $ ddd check device.ddd.json
   controller.ddd.json#component.interface[0].definition: warning[storage-mismatch]: 'InletTemperature': component 'Controller' specifies a different a2l format than 'SensorHub' (a2l format: '%8.3' != '%5.1'); the value of 'SensorHub' is used
       note: sensor_hub.ddd.json#component.interface[0].definition: reference declaration
   1 warning

.. code-block:: c

   /* ddd_globals.c */
   int16_t InletTemperature = -400;

If the disagreement is real and the project needs to see the generated files anyway - to
compare them, or to get an image out of the door while two teams argue - the ``--force``
option of ``ddd generate`` writes the artefacts despite the errors and still exits with 1.
Without it nothing at all is written, so a failed check can never leave a half generated
directory behind.

Why does my consumer not get a ``definition-mismatch`` when it leaves the limits out?
-------------------------------------------------------------------------------------

Because omitting the limits is not a disagreement. ``limits`` has a derived default - the
range the datatype can represent under the declared conversion - so a consumer that simply
does not repeat the producer's physical range is saying nothing about it, and DDD reads that
declaration as agreeing with whatever the producer says. Requiring the range to be repeated
would push every project into copying the same two lines into every consumer, and copied
lines are the ones that drift.

Stating limits that differ from the producer's *is* a disagreement, and it is reported:

.. code-block:: text

   $ ddd check device.ddd.json
   ok: 1 variable in 2 components are consistent

   $ ddd check device.ddd.json    # after the consumer changed its limits to [0, 150]
   controller.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'InletTemperature' is declared differently by component 'Controller' than by 'SensorHub' (limits: [0, 150] != [-40, 150])
       note: sensor_hub.ddd.json#component.interface[0].definition: reference declaration
   1 error

The limits that reach the a2l are the producer's either way - a consumer never widens or
narrows what the calibration tool is shown:

.. code-block:: text

       /begin MEASUREMENT InletTemperature "InletTemperature"
         SWORD CM_LIN_DEGC 0 0 -40 150
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "InletTemperature" 0
       /end MEASUREMENT

Why do I have to write ``conversion`` when it is just the identity?
-------------------------------------------------------------------

Because raw equalling physical is an engineering claim, not an absence of one, and it is the
claim that fails silently when it is wrong: a forgotten scaling on a fixed point value
displays raw counts in the calibration tool without anything looking broken. ``conversion``
is therefore required wherever storage is named by ``datatype`` - on a definition, on a
structure member, on a scalar type - exactly as ``kind`` and ``volatile`` are, and the
identity is an answer to state rather than a default to fall into:

.. code-block:: text

   $ ddd check a.ddd.json
   a.ddd.json#component.interface[0].definition: error[schema]: Value error, a 'datatype' comes with a 'conversion': the identity ({"kind": "identity"}) is an answer to state, not a default to fall into (got: {'name': 'Speed', 'kind': 'measurement', 'datatype': 'uin...)
   1 error

``{}`` and ``{ "kind": "identity" }`` both state it. A declaration naming a ``typename``
states none, because the :doc:`declared type <file_formats/types>` fixes the conversion
along with the datatype, the unit and the limits.

How do I stop every consumer from copying the same datatype and scaling?
------------------------------------------------------------------------

Declare a scalar type in a :doc:`types file <file_formats/types>`, list that file in the
project's ``includes``, and let every declaration name it with ``typename`` instead of
spelling out ``datatype``, ``unit``, ``conversion`` and ``limits`` of its own:

.. code-block:: json

   { "types": [
     { "type": "scalar", "name": "Temperature_t", "datatype": "sint16", "unit": "degC",
       "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
       "limits": { "min": -40, "max": 150 } }
   ] }

.. code-block:: json

   { "scope": "input", "definition": {
       "name": "InletTemperature", "kind": "measurement",
       "typename": "Temperature_t", "volatile": true } }

If all three consumers say ``Temperature_t``, there is nothing left for them to disagree
about. A type fixes exactly ``datatype``, ``unit``, ``conversion`` and ``limits``; ``kind``,
``dimensions``, ``init``, ``volatile`` and ``a2l`` stay on the variable, because two
measurements of one type may well differ in whether an interrupt writes one of them. Naming
a type and then restating what it fixes is an error rather than an override, so "where is
this unit written down" keeps one answer. A type that belongs to one component's published
contract can also be declared inside that
:doc:`component's own description <file_formats/component>`, with the same entry and the
same project wide name; the standalone file is the home of the shared ones.

How do I keep everybody spelling units the same way?
----------------------------------------------------

``unit`` is free text by default, so one quantity can drift into two spellings - ``Nm`` here,
``newton_meter`` there - with each declaration agreeing with itself and the a2l growing one
``COMPU_METHOD`` per spelling. A :doc:`units file <file_formats/units>` pins the spellings
once, listed in the ``includes`` of the project like any other description:

.. code-block:: json

   { "units": ["rpm", { "unit": "Nm", "description": "torque, newton metre" }] }

Declaring the vocabulary is opt-in - without a units file nothing changes - and with one,
every stated unit is checked where it is written, on declarations, structure members and
scalar types alike, with a near miss answered by the declared spelling:

.. code-block:: text

   $ ddd check p.ddd.json
   b.ddd.json#component.interface[0].definition.unit: error[unknown-unit]: 'nm' is not a unit this project declares - did you mean 'Nm'?
   1 error

The empty unit stays always allowed: a dimensionless value states no unit rather than a
spelling of one.

How do I place a variable in a particular memory section?
---------------------------------------------------------

Declare the section in a :doc:`sections file <file_formats/sections>` - its name as the
linker script spells it, whether the running software can write it, and the alignment it
guarantees - and let the producing declaration place its object with the ``section`` key:

.. code-block:: json

   { "sections": [ { "section": ".calib", "access": "read-only", "alignment": 4 } ] }

.. code-block:: json

   { "scope": "local", "definition": {
       "name": "Gain", "kind": "parameter", "datatype": "uint16",
       "conversion": {}, "init": 3, "section": ".calib", "volatile": false } }

Placement is storage, like ``init``: the producer states it, a consumer stating one is
refused as ``consumer-storage``, and a structured variable is placed whole. Naming a section
no file declares is ``unknown-section``, a measurement placed in a ``read-only`` section is
``section-access``, and an object needing stricter alignment than its section guarantees is
``section-alignment``. How the placement is spelled in c - an ``__attribute__``, a pragma -
is the :doc:`templates' <templates>` decision; the example templates write the GCC
attribute.

Where does my editor get the project and the severities from?
-------------------------------------------------------------

From the build. Which project a description file belongs to is not something the file can
say - in the collected CMake mode the project description exists only in the build tree - so
``ddd_generate()`` records it, together with the severity policy, in a ``ddd-build.json``
beside its artefacts, and the language server searches the build directories for that
record: the ones named with ``-b`` (the ``ddd.buildDirectories`` setting in VS Code), or the
conventional directory names next to the workspace. The editor then reports exactly what the
build reports. A file no build claims is checked under the nearest containing project, and a
file with no project at all is checked alone, with the checks that need the whole project
held back. The full story is in :doc:`editor_integration`.

Why does DDD refuse my enum name?
---------------------------------

An enum conversion does not stay inside the description file: it becomes a ``typedef enum``
in the generated c code, wherever the templates put it, and its enumerators become ordinary c
identifiers in the single namespace c has for them. Three rules follow from that, and all
three are checked before any code is generated, so that the finding names the declaration
instead of a compiler naming a line in a generated file nobody wrote.

The name may not be one that the c language, or a header DDD includes, has already claimed.
``reserved-identifier`` covers the C11 and C23 keywords, everything ``<stdint.h>`` declares,
and the identifiers C11 7.1.3 reserves for the implementation - which is why any name
containing a double underscore, or starting with an underscore and a capital letter, is
refused. Beyond that, two enums may not contribute the same enumerator, and no variable may
be named like an enumerator; both are reported as ``name-collision``:

.. code-block:: text

   $ ddd check enums.ddd.json
   enums.ddd.json#component.interface[0].definition.conversion: error[reserved-identifier]: enum name '__state_t' is reserved by the c language
   enums.ddd.json#component.interface[1].definition.conversion: error[name-collision]: enumerator 'OFF' is defined by enum 'Mode_t' and by enum '__state_t'; enumerators of different enums share one c namespace
       note: enums.ddd.json#component.interface[0].definition.conversion: first defined here
   enums.ddd.json#component.interface[2].definition.name: error[name-collision]: 'ON' is declared as a variable and is also an enumerator of enum '__state_t'; both become the same c identifier
       note: enums.ddd.json#component.interface[0].definition.conversion: enumerator declared here
   3 errors

The third rule is about a name being reused rather than refused: two components may declare
the same enum, and they then have to declare the *same* enum, because only one type of that
name is generated. Differing enumerator sets are an ``enum-conflict``, and the finding spells
out both sides so that it is obvious which of the two moved:

.. code-block:: text

   $ ddd check p.ddd.json
   b.ddd.json#component.interface[0].definition.conversion: error[enum-conflict]: enum 'State_t' is defined with different enumerators
       note: here: OFF=0, ON=1, FAULT=2
       note: a.ddd.json#component.interface[0].definition.conversion: first defined as: OFF=0, ON=1
   1 error

How do I keep a variable out of the a2l?
-----------------------------------------

Set ``"a2l": {"export": false}`` on its definition. It is a per object switch, and the usual
reason to reach for it is a value that is meaningless to a calibration engineer: a scratch
buffer, a component internal state, an array so large that it would double the size of the
a2l without ever being looked at. The demo project uses it for ``ValueD``:

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

The variable is then absent from the a2l entirely, including from the ``GROUP`` of the
component that declares it - a group referencing a record that is not in the file would be as
invalid as the record itself being missing. It is emphatically *not* absent from the
generated c code:

.. code-block:: c

   /* ddd_globals.c */
   uint16_t ValueD[8];

That asymmetry is deliberate. ``export`` describes what a calibration tool is shown; it says
nothing about what the software is allowed to use, and a variable that vanished from the
generated definitions would simply stop linking.

Why is my axis in the a2l although I set ``export`` to false?
--------------------------------------------------------------

Because something that *is* exported points at it. A curve or a map does not carry its own
break points: it refers to a shared axis with an ``AXIS_DESCR`` of attribute ``COM_AXIS`` and
an ``AXIS_PTS_REF``, which is what lets several curves over the same break points store them
once. An ``AXIS_PTS_REF`` naming an ``AXIS_PTS`` that is not in the file is a dangling
reference, and a reader rejects the file rather than the record - so honouring ``export`` on
the axis would not produce a smaller a2l, it would produce an unusable one.

DDD therefore pulls an object back in whenever an exported object refers to it, transitively:
a curve pulls its axis, and that axis pulls the measurement named as its input quantity. In
the following file ``SpeedAxis`` carries ``"export": false`` and is exported anyway, because
``InjectionTime`` refers to it:

.. code-block:: text

       /begin AXIS_PTS SpeedAxis "SpeedAxis"
         0x00000000 NO_INPUT_QUANTITY RL_AXIS_UWORD 0 CM_IDENT_RPM 4 0 65535
         SYMBOL_LINK "SpeedAxis" 0
       /end AXIS_PTS

       /begin CHARACTERISTIC InjectionTime "InjectionTime"
         CURVE 0x00000000 RL_VALUES_UWORD 0 CM_IDENT_MS 0 65535
         SYMBOL_LINK "InjectionTime" 0
         /begin AXIS_DESCR
           COM_AXIS NO_INPUT_QUANTITY CM_IDENT_RPM 4 0 65535
           AXIS_PTS_REF SpeedAxis
         /end AXIS_DESCR
       /end CHARACTERISTIC

To keep the axis out, keep its users out: with ``"export": false`` on every curve and map
that refers to it, nothing points at it any more and it disappears with them.

How do I get the real addresses into the a2l?
----------------------------------------------

With ``--address-map``, after linking. The address of a global variable is decided by the
linker, so it cannot exist when the sources are generated - which is why DDD is meant to run
twice per build: once before compiling, to produce the c code and an a2l with placeholder
addresses, and once after linking, to produce the a2l the calibration tool is actually given.

The map is a flat json object of symbol name to address, decimal or hexadecimal, produced
from the linker output by whatever already parses it in your build:

.. code-block:: json

   { "ValueE": "0x20000100", "AxisA": "0x08004000", "ParameterA": 134234112 }

.. code-block:: text

   $ ddd generate all demo.ddd.json -o gen -t templates --address-map addresses.json
   addresses.json: warning[address-missing]: the address map has no entry for 'AxisB', 'BlockA', 'CurveA', 'CurveB', 'FlagA' and 10 others; they reach the a2l at address 0
   1 warning
   ...
   $ sed -n '/MEASUREMENT ValueE/,/end MEASUREMENT/p' gen/DemoDevice.a2l
       /begin MEASUREMENT ValueE "Measurement used as the input quantity of AxisA"
         UWORD CM_LIN_HZ 0 0 0 8000
         ECU_ADDRESS 0x20000100
         SYMBOL_LINK "ValueE" 0
       /end MEASUREMENT

The objects the map leaves out keep address 0 and are named once, in the ``address-missing``
warning - a map from a linker output legitimately lacks what was not linked into this image;
``--strict`` makes the warning an error for a post-link build that wants no hole in its a2l.
Every entry is range checked while the map is read rather than while the a2l is written. A
negative value would otherwise render as ``0x-0000010`` and a wider one as a 33 bit literal,
and either makes the whole file unreadable - from a file that a linker script or a patch tool
wrote, where a wrong entry is exactly the kind of thing that goes unnoticed:

.. code-block:: text

   $ ddd generate all demo.ddd.json -o gen -t templates --address-map bad.json
   ddd: bad.json: address of 'ValueE' is 4294967296, outside the range 0 .. 0xFFFFFFFF that an a2l address can hold

The other route needs no map at all: ``SYMBOL_LINK`` is written for every object, always, so
an a2l address patcher can resolve the symbols against the linked image itself and fill the
addresses in afterwards. Both routes exist because projects differ in which tool owns the
linker output; neither of them requires editing the generated file by hand.

Why is the address of my variable still ``0x00000000``?
--------------------------------------------------------

Because no address was supplied for it. Zero is the placeholder DDD writes when a symbol is
not in the address map, and it is what the whole file gets when no ``--address-map`` is given
at all - a pre-link a2l is a perfectly normal artefact, and refusing to produce one would
make it impossible to look at the description before the software exists.

A lone ``0x00000000`` in an otherwise populated file therefore means that the map does not
mention that symbol, and the usual cause is a spelling difference: the map is keyed by the
exact name of the object as declared, which is also its c identifier and its a2l record name.
A symbol the map does not mention keeps address zero silently, on the grounds that a partial
map is a legitimate thing to hand over:

.. code-block:: text

       /begin MEASUREMENT ValueF "Signed measurement with a fixed point conversion"
         SWORD CM_LIN_DEGC 0 0 -40 150
         ECU_ADDRESS 0x00000000
         SYMBOL_LINK "ValueF" 0
       /end MEASUREMENT

.. note::
   The address does not always appear behind an ``ECU_ADDRESS`` keyword. A ``MEASUREMENT``
   spells it out that way, while a ``CHARACTERISTIC`` and an ``AXIS_PTS`` carry it as their
   address field, the token right after the record type, as in
   ``VAL_BLK 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255``. Both come from the same
   map.

Which a2l version does DDD write?
----------------------------------

ASAP2 1.6.1, declared in the second line of every generated file, and the version is not
selectable:

.. code-block:: text

   /* DemoDevice.a2l - generated from 'DemoDevice' by ddd 0.7.0. DO NOT EDIT. */
   ASAP2_VERSION 1 61

One consequence is worth knowing, because it is the only place where the format is narrower
than the data model. ``MATRIX_DIM`` carries exactly three dimensions in 1.6.1, so an array is
written padded - ``MATRIX_DIM 8 1 1`` for eight elements - and an object with more than three
dimensions cannot be described at all. DDD writes all of its dimensions out anyway, which
only a 1.7 reader understands, and says so:

.. code-block:: text

   $ ddd generate all buffers.ddd.json -o gen -t templates
   buffers.ddd.json#component.interface[1].definition: warning[a2l-unrepresentable]: 'Tesseract' has 4 dimensions, but the MATRIX_DIM of ASAP2 1.6.1 carries 3; the extra dimensions are written out and only a 1.7 reader understands them
   1 warning
   wrote       gen/ddd_globals.c (created)
   ...

The dimensions are also reversed with respect to the c declaration, because ASAP2 lists the
index that runs fastest first while c declares it last: ``uint8_t Cube[2][3][4]`` becomes
``MATRIX_DIM 4 3 2``. Emitting them unchanged would describe a transposed object, and every
calibration tool would address the wrong element.

.. note::
   The generated a2l says which DAQ event carries a measurement, and nothing about the
   protocol that reaches it: an exported measurement with a :doc:`raster
   <file_formats/rasters>` gets an ``IF_DATA XCP`` block naming its event channel, while the
   module level ``DAQ`` list defining the events, the ``PROTOCOL_LAYER`` and the transport
   come from whatever configures the XCP stack. No file DDD writes contains an ``IF_DATA``
   section for CCP.

How large may an array be?
--------------------------

There is no bound: a dimension is any integer of at least one, stated as a number or through
a :doc:`declared constant <file_formats/constants>`, and DDD caps neither the number of
dimensions nor their product. What grows with that product is the work. A structured object
is resolved into one member object per element and member, and those objects are what the
checks walk, what the dumped dictionary records and what the a2l describes, so a structured
object of several million elements takes correspondingly long to check and correspondingly
much space to archive. The generated initialiser grows the same way, because an ``init`` is
spelled out element by element and a scalar one fills every element of the shape: a value
block of a thousand by a thousand elements initialised to ``0`` is a definition holding a
million zeros.

How do I generate for two images built from the same components?
-----------------------------------------------------------------

Write one project description per image, listing the components that image links, and
generate each into its own output directory. The generated artefacts belong to an image, not
to a component: the definition file allocates exactly the variables of that image, and the
a2l describes exactly its memory. Two images are two dictionaries, and mixing them would mean
shipping a calibration description for variables the software does not contain.

.. code-block:: text

   $ ddd generate all sensor_only.ddd.json -o build/sensor -t templates -W unused-output=ignore
   wrote       build/sensor/ddd_globals.c (created)
   wrote       build/sensor/ddd_globals.h (created)
   wrote       build/sensor/ddd_types.h (created)
   wrote       build/sensor/SensorHub.h (created)
   wrote       build/sensor/SensorOnly.a2l (created)

   $ ddd generate all full.ddd.json -o build/full -t templates -W unused-output=ignore -W missing-producer=ignore
   wrote       build/full/ddd_globals.c (created)
   wrote       build/full/ddd_globals.h (created)
   wrote       build/full/ddd_types.h (created)
   wrote       build/full/Controller.h (created)
   wrote       build/full/SensorHub.h (created)
   wrote       build/full/UserInterface.h (created)
   wrote       build/full/FullDevice.a2l (created)

The per-component headers are not interchangeable between the two either, which is easy to
overlook because they carry the same file names. A consumer header names the component that
produces each of its inputs, and that answer depends on what else is in the image:

.. code-block:: c

   /* build/full/Controller.h */
   extern uint8_t ValueA;  /* produced by SensorHub */

   /* build/ctrl/Controller.h - an image that does not link SensorHub */
   extern uint8_t ValueA;  /* produced by <unresolved> */

This is why the cmake integration refuses the ambiguous case instead of letting an include
order decide it: only one ``ddd_generate`` call may hand its headers to the registered
components automatically, and a project with several images has to give
``NO_PROPAGATE_HEADERS`` to *both* calls and link the wanted ``<image>_ddd_headers`` into
each component explicitly. See :doc:`build integration </build_integration>`.

Why does regenerating not retrigger my build?
----------------------------------------------

Because nothing changed, and DDD goes out of its way to make that visible to the build
system. Nothing it hands a template varies from run to run - there is no time stamp, no user
name and no host name anywhere in the model - so the same inputs render byte for byte
identical output; and every rendered file is compared against what is already on disk and
written only when the bytes differ. An unchanged file therefore keeps its modification time,
and make, ninja or any other timestamp driven tool correctly concludes that nothing depending
on it needs rebuilding:

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/docs-check -t examples/templates
   wrote       build/docs-check/ddd_globals.c (created)
   wrote       build/docs-check/ddd_globals.h (created)
   wrote       build/docs-check/ddd_types.h (created)
   wrote       build/docs-check/Controller.h (created)
   wrote       build/docs-check/SensorHub.h (created)
   wrote       build/docs-check/UserInterface.h (created)
   wrote       build/docs-check/EventLogger.h (created)
   wrote       build/docs-check/DemoDevice.a2l (created)

   $ ddd generate all examples/demo/demo.ddd.json -o build/docs-check -t examples/templates
   unchanged   build/docs-check/ddd_globals.c
   unchanged   build/docs-check/ddd_globals.h
   unchanged   build/docs-check/ddd_types.h
   unchanged   build/docs-check/Controller.h
   unchanged   build/docs-check/SensorHub.h
   unchanged   build/docs-check/UserInterface.h
   unchanged   build/docs-check/EventLogger.h
   unchanged   build/docs-check/DemoDevice.a2l

The three statuses - ``created``, ``updated`` and ``unchanged`` - are the generator's report
of what it did, so a build log says which artefacts a change actually touched. ``--dry-run``
prints the same report as ``would write`` and writes nothing, which is the honest way to find
out what a change would do to the generated tree before letting it happen.

.. warning::
   Byte identical means *for the same inputs, the same templates and the same tool*. Editing a
   template rewrites the file it renders, and ``model.generator`` carries the version of the
   tool, so a banner that prints it - as the example templates do - makes an upgrade rewrite
   the whole generated tree and retrigger the build. Both are deliberate: a new template and a
   new generator are changes to the sources of the image.
