Type description
================

A ``types`` file declares the types a project names. There are two of them: a **structure**,
which lays several values out in one c object, and a **scalar type**, which fixes what one
number means and says nothing about where it is stored. A declared type has two possible
homes, and the entries are the same in both: the standalone file this page describes, and
the ``types`` list a :doc:`component <component>` may carry for the types it publishes.
The choice between them is ownership, not visibility - either home puts the name in the
same project wide namespace. The standalone file is the home of shared types, because a
type with no single owner has no component to live inside: the point of declaring
``Temperature_t`` once is that two components can agree on it without either of them owning it.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_types.schema.json",
     "types": [
       {
         "type": "scalar",
         "name": "Temperature_t",
         "description": "A temperature as every component of this project agrees to see it",
         "datatype": "uint16",
         "unit": "degC",
         "conversion": { "factor": 0.1, "offset": -40 },
         "limits": { "min": -40, "max": 150 }
       },
       {
         "type": "struct",
         "name": "Sample_t",
         "description": "One reading and the instant it was taken",
         "members": [
           {
             "name": "value",
             "member": "value",
             "description": "The reading itself",
             "typename": "Temperature_t"
           },
           {
             "name": "timestamp",
             "member": "value",
             "description": "Milliseconds since the last reset",
             "datatype": "uint32",
             "conversion": { "kind": "identity" },
             "unit": "ms"
           }
         ]
       }
     ]
   }

The file is listed in the ``includes`` of a project, next to its components:

.. code-block:: json

   { "project": { "name": "StructuredDevice", "includes": ["types.ddd.json", "sensing.ddd.json", "monitoring.ddd.json"] } }

``examples/structures`` is exactly that, ready to run: a types file with those two entries and
three more, a component that declares variables of them, and a second component that reads the
structured output, so the interface has its two sides:

.. code-block:: text

   $ ddd check examples/structures/project.ddd.json
   ok: 9 variables in 2 components are consistent

A types file on its own is not a project, so pointing ``ddd check`` straight at one is refused
rather than half-processed. There is nothing to resolve or generate from a layout that no
component has instantiated, and validating the file against the published schema - which
``ddd schema types`` prints - is what an editor is for:

.. code-block:: text

   $ ddd check examples/structures/types.ddd.json
   examples/structures/types.ddd.json: error[file-kind]: this is a structured datatype description; list it in the 'includes' of the project that uses it instead of analysing it on its own
   1 error

Two kinds of entry
------------------

Every entry says which of the two it is, in a required ``type`` key, and that key decides which
of the others the entry may carry:

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - ``type``
     - what the entry declares
   * - ``scalar``
     - a name for what a number means: a ``datatype``, and the ``unit``, ``conversion`` and
       ``limits`` that go with it.
   * - ``struct``
     - a name for a layout: the ``members``, in the order the generated c declares them.

Both carry a ``name`` and an optional ``description``, and nothing else is shared, because
nothing else means the same thing to both. Which of the two an entry is, is stated rather than
inferred from the keys that happen to be present, for the reason the member shapes below give
as well: a file that omits a key by mistake should be told which shape it failed to describe
instead of silently becoming another one. An entry with no ``type`` is therefore refused where
it sits, rather than tried against each shape in turn and reported against whichever one it
came closest to:

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0]: error[schema]: Unable to extract tag using discriminator 'type' (got: {'name': 'S_t', 'members': [{'name': 'a', 'member': 'valu...)
   1 error

Two keys name the storage
-------------------------

``datatype`` takes one of the eleven base datatypes a
:doc:`variable definition <variable_definition>` lists, and nothing else; ``typename`` takes
the name of a type this project declares. Exactly one of the two is stated wherever storage
is named - on a member of a structure and on the definition of a variable alike - never
both, never neither:

.. code-block:: text

   $ ddd check project.ddd.json
   a.ddd.json#component.interface[0].definition: error[schema]: Value error, storage is named exactly once: 'datatype' for a base datatype, 'typename' for a type the project declares (got: {'name': 'Count', 'kind': 'measurement', 'volatile': Fals...)
   1 error

Two keys rather than one union, so that each stays what it says. The published schema keeps
``datatype`` at exactly eleven values: an editor completes and documents precisely them, and
a mistyped ``uint166`` is refused as it is typed rather than reported as a type nobody
declares a build later. And a declaration tells its reader at the use site whether storage
is base or declared - ``"typename": "Int16_t"`` is unambiguous however much the name
dresses like storage, because the key already says it is declared.

A ``typename`` cannot spell a base datatype, in any case. A type called ``uint16`` - or
``UINT16`` - would wear the name of storage it is not, and every declaration naming it would
read like a typo:

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0].scalar.name: error[schema]: Value error, 'UINT16' spells a base datatype; a declared type carries a name of its own, so that reading a declaration tells the two apart (got: 'UINT16')
   1 error

A ``typename`` that names no type any file of the project declares is answered by the
``unknown-type`` check, with the question a reader would have asked:

.. code-block:: text

   $ ddd check project.ddd.json
   a.ddd.json#component.interface[0].definition.typename: error[unknown-type]: 'Count' is declared as 'unit16', which is neither a base datatype nor a type any file of this project declares - did you mean 'uint16' or 'uint64' or 'sint16'?
   1 error

Scalar types
------------

.. list-table::
   :header-rows: 1
   :widths: 18 15 67

   * - key
     - default
     - meaning
   * - ``type``
     - required
     - ``"scalar"``.
   * - ``name``
     - required
     - The name components write in their ``typename``. It has to be distinct from every other
       type of the project.
   * - ``description``
     - ``""``
     - Free text saying what the type *is*, offered to the c templates.
   * - ``datatype``
     - required
     - The storage, as one of the base datatypes.
   * - ``unit``
     - ``""``
     - The physical unit, as free text: ``rpm``, ``degC``, ``%``.
   * - ``conversion``
     - identity
     - How the stored number maps to the physical one; see :doc:`conversions`.
   * - ``limits``
     - derived
     - ``min`` and ``max`` in physical units, derived from the datatype and the conversion when
       left out.

A scalar type is agreement by naming rather than by copying. Three components consuming an
engine speed each used to write out the datatype, the unit, the scaling and the limits, and
DDD's job was to notice when one of the three was wrong. If all three say ``Speed_t`` instead,
there is nothing left for them to disagree about - which is a check turned into a construction,
and the reason the four keys above are exactly the ones a scalar type fixes. ``kind``,
``dimensions``, ``init``, ``volatile`` and the ``a2l`` block stay on the variable, because they
are properties of one object rather than of the type: two measurements of one type may well
differ in whether an interrupt writes one of them.

Naming a type and then restating what it fixes is an error rather than an override, so the
question "where is this unit written down" keeps one answer. The rule is the same on a member
of a structure as on the definition of a variable, because the confusion it prevents is the
same one:

.. code-block:: text

   $ ddd check project.ddd.json
   sensing.ddd.json#component.interface[0].definition: error[schema]: Value error, 'Temperature_t' is a declared type and already fixes what this value means, so 'limits' may not be stated here as well (got: {'name': 'Inlet', 'kind': 'measurement', 'typename': 'Tem...)
   types.ddd.json#types[1].struct.members[0]: error[schema]: Value error, 'Temperature_t' is a declared type and already fixes what this value means, so 'unit' may not be stated here as well (got: {'name': 'value', 'member': 'value', 'typename': 'Tempera...)
   2 errors

The ``datatype`` of a scalar type is a base datatype and not another declared name, so a scalar
type cannot be defined in terms of a second one. A chain of names would have to be resolved,
could form a cycle, and buys nothing that a reader of the single entry could not already see.

A scalar type is a name for a meaning and not for a storage class, so it is not spelled out as
a c typedef: a member or a variable of ``Temperature_t`` is declared ``uint16_t``, and the unit,
the scaling and the limits travel to the a2l, which is where they are read. Nothing in the
generated c would ever consult the name, and a typedef per scalar type would put an identifier
into the c namespace for no reader to use.

Structures
----------

A ``struct`` entry carries ``members``, at least one, and their order is the order the generated
c declares them in. Every member states which shape it has, in the ``member`` key:

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - ``member``
     - what it is
   * - ``value``
     - a base ``datatype`` or a declared ``typename``, optionally an array through
       ``dimensions``. The ordinary case, and the one that nests a structure: a member whose
       ``typename`` names a structure *is* that structure, laid out inside this one.
   * - ``bits``
     - a base ``datatype`` and a width in ``bits``: a c bitfield. Consecutive bit members
       share a storage unit.

Each shape permits exactly the keys it needs and refuses the rest, and the refusal is worth
more than it looks. ``bits`` together with ``dimensions`` has no single meaning, since an array
of bitfields is not something c can express, so accepting the pair and quietly ignoring one
half would put a structure in the generated c that the description does not describe. A
forgotten ``bits`` is the same problem in the other direction: it would turn a one bit flag
into a full width member and move every offset after it.

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0].struct.members[0]: error[schema]: Value error, a 'bits' member needs a 'bits' (got: {'name': 'ready', 'member': 'bits', 'datatype': 'uint16'})
   types.ddd.json#types[0].struct.members[1]: error[schema]: Value error, a 'value' member has no 'bits' (got: {'name': 'history', 'member': 'value', 'datatype': 'uint1...)
   2 errors

A member says what its bytes *mean* as well as where they are, because once a structure is
flattened into the a2l each member is an object like any other and needs a unit and a range.
So a member carries ``unit``, ``conversion``, ``limits`` and an ``a2l`` block of its own, or
names a scalar type that fixes them, and never both. Which of the two to reach for is a
question of whether the answer is shared: a unit written on a member says it for that member of
that structure, and a ``Temperature_t`` says it once for everything in the project that names
it. The ``a2l`` block sits on the member rather than on the structure because that is the
granularity the file ends up with - keeping one member out of the a2l, or giving one member a
display format, is a decision about that member alone.

What a member does not say
~~~~~~~~~~~~~~~~~~~~~~~~~~

A member states no ``kind``, and that is the scope of ``const`` rather than an oversight.
Whether an object is measured or calibrated decides whether the generated definition is
``const``, and ``const`` qualifies a whole c object - there is no way to make half a structure
constant. The *declaration* therefore decides, once, for all the members at once, and a
structure whose members are half measured and half calibrated is not something this file can
express rather than something DDD has to report afterwards. A component that needs both writes
two structures, which is what ``examples/structures`` does with ``Sensor_t`` for what the
software measures and ``SensorCal_t`` for what the calibration tool may change.

A member states no ``init`` and no ``volatile`` for the same kind of reason: both belong to a
variable rather than to a type. Two variables of one structure may perfectly well start at
different values, so the initial value is written where the variable is. And ``volatile`` is
answered by the object that has an address, which a structured variable is however many members
it has: it answers once, in its own declaration, and the answer covers the whole of it. A
types file describes a layout and not a variable, so there is nothing in it for either key to
belong to.

Bitfields
~~~~~~~~~

A bitfield has to fit its storage and has to sit in an integer. Seventeen bits do not fit a
``uint16``, and c allows a bitfield only in an integer type, so ``float32``, ``boolean`` and a
declared type are all refused - a scalar type would in any case bring limits that the width
contradicts:

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0].struct.members[0]: error[schema]: Value error, a bitfield of 17 bits does not fit in 'uint16', which holds 16 (got: {'name': 'wide', 'member': 'bits', 'datatype': 'uint16', ...)
   types.ddd.json#types[0].struct.members[1]: error[schema]: Value error, a bitfield needs an integer datatype, got 'float32'; only an integer can carry one in c (got: {'name': 'counted', 'member': 'bits', 'datatype': 'float3...)
   types.ddd.json#types[0].struct.members[2]: error[schema]: Value error, a 'bits' member has no 'dimensions' (got: {'name': 'flags', 'member': 'bits', 'datatype': 'uint8', ...)
   3 errors

The limits of a bitfield are derived from its **width** and not from the datatype carrying it.
A two bit ``mode`` offered to a calibration tool as ``0 .. 65535`` is worse than no limits at
all, because the tool then lets somebody enter a value the field cannot store and the software
reads back something else. ``faultCount`` in the example is four bits wide inside a ``uint16``
and comes out ``0 .. 15``; a signed field spends one bit on the sign, so a ``sint8 : 4`` runs
``-8 .. 7``. Stated ``limits`` win over the derivation, as everywhere else.

A ``bits`` member gives a width and no position, and that too is deliberate. C leaves the
allocation order within a storage unit implementation defined: whether ``ready : 1`` lands in
the least or the most significant bit is a property of the compiler and the target, not of the
description. Stating a position here would be stating something DDD cannot honour.

Member order is significant
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The members are laid out in the order the file lists them, because that is the order the
generated c declares them in and therefore the order the compiler lays out. Reordering the
members of a structure that has already been delivered moves every address after the change,
and nothing in the description changes value or name, so the diff of the json is the only place
the move is visible before the next build measures it.

Where the members sit is not stated here
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A structure's members have offsets, and those follow from the target's alignment rules and from
whatever packing the build applies - which means the honest source for them is the build
itself and not a model of it. DDD reads the real layout back out of the compiled result rather
than predicting it, on exactly the principle that already applies to addresses: ``ddd generate``
writes ``0x00000000`` into the a2l until a build tells it otherwise, and ``--address-map`` takes
the answer keyed on the access path of each member. A predicted offset would be indistinguishable
from a measured one and wrong on the first target whose alignment differs.

A variable of a declared type
-----------------------------

A component declares a structured variable by naming the structure: ``typename`` where a plain
declaration states its ``datatype``, and everything else about the declaration is what it
always was - the scope, the kind, the description, ``volatile``:

.. code-block:: json

   {
     "scope": "output",
     "definition": {
       "name": "Inlet",
       "kind": "measurement",
       "description": "The inlet sensor as this ecu sees it",
       "typename": "Sensor_t",
       "volatile": true
     }
   }

The structures reach ``ddd_types.h``, each after every structure it nests, because c needs the
nested one complete first and a template has to be able to write them out in the order it is
given them. A member that names a scalar type is declared with that type's storage, and a
member that names a structure is declared with the structure:

.. code-block:: c

   /* Sample_t - One reading and the instant it was taken */
   typedef struct
   {
       uint16_t value; /**< The reading itself */
       uint32_t timestamp; /**< Milliseconds since the last reset */
   } Sample_t;

   /* Status_t - Flags packed into one word, as c bitfields */
   typedef struct
   {
       uint16_t ready : 1; /**< Set once the sensor has produced a first reading */
       uint16_t mode : 2; /**< Which of the three operating modes is active */
       uint16_t faultCount : 4; /**< Faults seen since the last reset, saturating */
   } Status_t;

   /* Sensor_t - Everything one sensor measures */
   typedef struct
   {
       Sample_t latest; /**< The most recent reading */
       Status_t status; /**< The flags of this sensor */
       uint16_t history[8]; /**< The last eight readings, oldest first */
   } Sensor_t;

The variable itself is one c object, and the qualifiers are the ones any other declaration of
that kind and that ``volatile`` would get - which is the whole point of the kind belonging to
the declaration rather than to the members:

.. code-block:: c

   /** The inlet sensor as this ecu sees it */
   volatile Sensor_t Inlet;
   /** What the calibration tool may change about the inlet sensor */
   const volatile SensorCal_t InletCal;

Flattened into the a2l
~~~~~~~~~~~~~~~~~~~~~~

A structure does not become an a2l structure. It is flattened into one ordinary object per
member, named by the c expression that reads that member, so that the a2l, the generated c and
a map file all spell one thing one way. The reasoning is on the
:doc:`developer documentation </developer_documentation>` page and is not a matter of taste:
ASAP2 has a typedef family for the native form, and the calibration tools this project targets
load a file that uses it without a warning and then display nothing for it.

.. code-block:: text

   /begin MEASUREMENT Inlet.latest.value "The reading itself"
     UWORD CM_LIN_DEGC 0 0 -40 150
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "Inlet.latest.value" 0
   /end MEASUREMENT

The offset in ``SYMBOL_LINK`` is ``0`` and means it: the offset of a symbol from itself. The
name carries the whole path, so the address a build reports for ``Inlet.latest.value`` is the
address of that member and nothing has to be added to it. The limits ``-40 150`` and the
``CM_LIN_DEGC`` come from ``Temperature_t``, which the member names and the enclosing structure
never repeats. Each leaf also joins the ``GROUP`` of the component that declares the variable,
so a structured variable is not a hole in that component's measurement list.

An array is treated differently depending on what it is an array of, and the difference is
whether one record can honestly describe the whole of it. An array of **values** stays one
object with a ``MATRIX_DIM``, because its elements are consecutive and one address plus a shape
says where all of them are:

.. code-block:: text

   /begin MEASUREMENT Inlet.history "The last eight readings, oldest first"
     UWORD CM_LIN_DEGC 0 0 -40 150
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "Inlet.history" 0
     MATRIX_DIM 8 1 1
   /end MEASUREMENT

An array of **structures** contributes one set of leaves per element - ``Inlet.cell[0].raw``,
``Inlet.cell[1].raw`` and so on - because the members of ``cell[0]`` and ``cell[1]`` sit a whole
structure apart and no single record describes both at once. The same holds for a variable whose
own ``dimensions`` make it an array of structures.

Calibration members go the same way, as ``CHARACTERISTIC`` rather than ``MEASUREMENT``, since
the kind is the variable's and every leaf of one variable has it:

.. code-block:: text

   /begin CHARACTERISTIC InletCal.warnLimit "Reading above which the sensor reports a fault"
     VALUE 0x00000000 RL_VALUES_UWORD 0 CM_LIN_DEGC -40 150
     SYMBOL_LINK "InletCal.warnLimit" 0
   /end CHARACTERISTIC

.. note::
   A ``bits`` member reaches no a2l at all. ``&s.ready`` does not compile, so no build can
   report where that member is, and a ``SYMBOL_LINK`` carries a byte offset with nowhere to put
   a bit position: leaving the mask out would claim the whole word, and writing zero would
   claim nothing. Both are wrong answers dressed up as output, so the member waits for a build
   that can say. Everything else about it is generated as usual - the c declaration, the width,
   the limits derived from that width - and ``Status_t`` in the example is therefore fully
   described in ``ddd_types.h`` and absent from ``StructuredDevice.a2l``.

Checks over the types
---------------------

Four findings are specific to these files, and two that already existed now reach type names as
well. All six are errors.

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - check
     - what it means
   * - ``duplicate-type``
     - two files declare a type of the same name. Which of two layouts, or of two units, the
       generated c would get is not something an include order should decide, so the second is
       refused rather than allowed to win.
   * - ``unknown-type``
     - a ``typename`` names no type any file of the project declares,
       whether it is written on a member or on a declaration. It is refused rather than skipped:
       a member of unknown size makes every offset after it wrong, and wrong offsets are
       addresses that point at the wrong bytes without anything looking broken.
   * - ``type-kind``
     - a declared type is used where its shape does not fit - a structure named by a ``curve``,
       a ``map``, an ``axis`` or a ``value_block``, all of which refer to other objects or are
       an array of one datatype, or a structured declaration carrying an ``init``, since the
       initial value of a structure is written by the code that starts it.
   * - ``type-cycle``
     - structures nest each other, directly or through others. A structure that contains itself
       has no size at all, and the finding names the chain because that says which member to
       remove.
   * - ``reserved-identifier``
     - a type name is a c keyword, or is declared by one of the headers the generated code
       includes. A structure becomes a typedef in ``ddd_types.h``, so the rule that already
       applied to variable, component and enum names applies here unchanged.
   * - ``name-collision``
     - a type name and a variable name are the same. C keeps a typedef name at file scope in the
       same namespace as the variables, so ``uint16_t Sample_t;`` beside
       ``typedef struct { ... } Sample_t;`` is a redeclaration rather than two things.

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0]: error[type-cycle]: structured datatypes nest each other: A_t -> B_t -> A_t
   types.ddd.json#types[2].members[0]: error[unknown-type]: member 'gone' names datatype 'Missing_t', which is neither a base datatype nor a type any file of this project declares
   2 errors

A cycle is reported once however many routes lead into it, and against the structure the cycle
closes on rather than whichever one the search happened to start from - a sound structure
nesting a recursive one reaches the same cycle, and keying the report on where the walk began
would report it once per route.

``type-kind`` is reported against the declaration and not against the type, because the type is
usually perfectly good and the use made of it is not; the note points at the declaration of the
type so that both ends are on screen:

.. code-block:: text

   $ ddd check project.ddd.json
   sensing.ddd.json#component.interface[0].definition: error[type-kind]: 'History' is declared as the structure 'Sample_t', but a 'value_block' refers to other objects or is an array of one datatype, and a structure is neither; a structured object is 'measurement' or 'parameter'
       note: types.ddd.json#types[0]: declared here
   sensing.ddd.json#component.interface[1].definition: error[type-kind]: 'Preset' is declared as the structure 'Sample_t', but the initial value of a structure is written by the code that starts it
       note: types.ddd.json#types[0]: declared here
   2 errors

``duplicate-type`` and ``name-collision`` both name the other place, since the fix is to rename
one of the two and the author needs to see both before choosing which:

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0]: error[duplicate-type]: type 'Temperature_t' is already declared
       note: shared.ddd.json#types[0]: first declared here
   1 error

.. code-block:: text

   $ ddd check project.ddd.json
   sensing.ddd.json#component.interface[0].definition.name: error[name-collision]: 'Sample_t' is declared as a variable and is also the name of a type; the types header makes that a typedef name, which c keeps in the same namespace as the variable
       note: types.ddd.json#types[0]: type declared here
   types.ddd.json#types[1].name: error[reserved-identifier]: type name 'uint8_t' is reserved by the c language
   2 errors
