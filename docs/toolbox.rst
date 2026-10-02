The toolbox
===========

Some work is done once rather than in every build: bringing what a project already has into
DDD, or taking DDD's descriptions somewhere else. That is what the toolbox is for. Its tools
are commands under ``ddd tool``, and ``ddd tool from-elf`` is the first.

From an ELF image
-----------------

A project that adopts DDD rarely starts from nothing: its variables already exist, in C,
compiled into an image. ``ddd tool from-elf`` reads a linked ELF image and its DWARF debug
information, and prints the DDD declaration of every C variable it is asked for - as far as
the image states it, and checked by DDD itself before it is printed, the way
``ddd check --standalone`` checks a component. It needs an image built with debug information
(``-g``); pyelftools, which reads it, is installed with DDD.

A variable is named as it is in C, or matched with a glob such as ``'Cal_*'``, and a
``static`` that several compilation units define is taken from one of them by naming its unit
first, ``cal.c:Gain``. What the tool prints is the ``interface`` of a component, ready to paste
into one; ``examples/firmware/firmware.elf`` is an image of the tests' fixture, built for a
Cortex-M4:

.. code-block:: text

   $ ddd tool from-elf examples/firmware/firmware.elf Cal_Gain Enum_State
   [
     {
       "scope": "output",
       "definition": {
         "name": "Cal_Gain",
         "kind": "parameter",
         "datatype": "uint16",
         "conversion": {
           "kind": "identity"
         },
         "init": 300,
         "volatile": false
       }
     },
     {
       "scope": "output",
       "definition": {
         "name": "Enum_State",
         "kind": "measurement",
         "datatype": "uint8",
         "conversion": {
           "kind": "enum",
           "name": "State_t",
           "enumerators": {
             "STATE_OFF": 0,
             "STATE_ON": 1,
             "STATE_FAULT": 200
           }
         },
         "init": 1,
         "volatile": false
       }
     }
   ]
   examples/firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   1 info
   $ echo $?
   0

``Enum_State`` is a ``uint8`` because this target makes an enum as small as its values: the
datatype is the one the image states, never the one its C spelling suggests elsewhere.
``--scope input`` prints the same entries as a consumer states them, without the initial value
and the section; ``-o FILE`` writes them into a file instead of standard output.

What an image states, and what it does not
------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - key
     - where it comes from
   * - ``kind``
     - the variable's ``const``: a ``measurement`` without it; with it a ``parameter``, or a
       ``value_block`` for an array. Nothing in an image tells a curve, a map or an axis from
       any other array, so none is inferred.
   * - ``datatype``
     - the encoding and size DWARF states: ``long``, plain ``char`` and an enum follow the
       target that built the image.
   * - ``conversion``
     - the identity, or an ``enum`` conversion carrying the enumerators in declaration order,
       named after the typedef closest to the enum, else its tag.
   * - ``dimensions``
     - the array's extents, in C order.
   * - ``init``
     - the image's own bytes, in its byte order; an array of one value as that value, a
       ``float32`` in the fewest digits that read it back. None for a variable in a section
       without contents, whose bytes the image does not hold: ``.bss`` starts at zero, a
       ``.noinit`` section is not initialised at all, and ``section`` says which.
   * - ``section``
     - stated only where the variable's section is not one of the toolchain's defaults. It is
       the image's output section, which is the name the source used when the linker script
       kept it, and the project has to declare it in a sections file.
   * - ``volatile``
     - the qualifier.
   * - ``typename`` and ``types``
     - a structure, its members, bitfields and nested structures, one ``types`` entry per
       structure.
   * - ``unit``, ``description``, ``limits``, ``id``, ``raster``, the ``a2l`` block
     - nothing in an image states them. They are left out, and the run says so once:
       ``elf-not-inferred``.

Structures
----------

A variable of a structure names it as its ``typename``, and ``--component NAME`` prints a whole
component file, with a ``types`` entry for every structure the variables reach:

.. code-block:: text

   $ ddd tool from-elf examples/firmware/firmware.elf Struct_Inlet --component Inlet
   {
     "component": {
       "name": "Inlet",
       "types": [
   ...
       "interface": [
         {
           "scope": "output",
           "definition": {
             "name": "Struct_Inlet",
             "kind": "measurement",
             "typename": "Inlet_t",
             "volatile": false
           }
         }
       ]
     }
   }
   main.c:57: warning[elf-name-synthesized]: an anonymous structure is named 'Inlet_t_pair_t', after the first thing that reaches it; rename it if the source has a better name
   examples/firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   main.c:63: info[elf-boolean-bitfield]: 'Inlet_t.ready' is a _Bool bitfield, described as a uint8 one of the same width: DDD refuses a boolean bitfield
   1 warning, 2 infos

The list output has nowhere to put a ``types`` entry, and says so (``elf-types-omitted``). A
structure's entry belongs once in a project: where two components need it, move it into a
shared types file rather than pasting it into both.

A structure is named by the typedef closest to it, else by its tag, and an anonymous one after
the first thing that reaches it (``elf-name-synthesized``). Two structures of one name that
differ - one per compilation unit, each unit's own - are ``elf-type-conflict``, and no
variable reaching either is printed. A ``_Bool`` bitfield is described as a ``uint8`` one
(``elf-boolean-bitfield``), since DDD refuses a boolean bitfield, and ``const`` or ``volatile``
on a member is dropped (``elf-qualifier-dropped``): DDD qualifies whole objects. A structured
object states no initial value, as DDD requires; values the image holds for one are dropped
and said to be (``elf-init-dropped``).

The layout of a structure
~~~~~~~~~~~~~~~~~~~~~~~~~

DDD states member order, datatypes and widths, never offsets, and the compiler lays out the
structure it generates. Nothing in the a2l depends on that, but the structure DDD generates can
lay out differently from the source's where the source asked for a layout its members do not
imply - and DWARF records none of those requests directly. The tool warns about the two traces
it can read: bits skipped where the next bitfield would have fit, which an unnamed or zero
width bitfield leaves (``elf-bitfield-gap``), and an alignment the source states
(``elf-alignment``). Packing - ``#pragma pack``, ``packed`` - is not detected: whether an
offset is packed or merely the target's own alignment depends on the ABI.

What the tool cannot describe
-----------------------------

A variable that cannot be described is not printed, and a run with one exits ``1`` and writes
nothing, unless ``--force`` asks for what could be described:

.. code-block:: text

   $ ddd tool from-elf examples/firmware/firmware.elf Type_Pointer Tls_Counter Cal_Gain
   main.c:106: error[elf-no-storage]: 'Tls_Counter' has no address in the image: it is thread-local, with an address of its own in every thread
   main.c:38: error[elf-type-unsupported]: 'Type_Pointer' is a pointer, which DDD cannot state
   examples/firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   2 errors, 1 info
   $ echo $?
   1

A finding about a variable is shown at its declaration in the C source, as the image recorded
the path. An image that cannot be used at all - not ELF, without DWARF, a relocatable object
rather than a linked image, one whose types sit in DWARF type units (``-fdebug-types-section``),
one built with gcc's link-time optimisation (``-flto``), one whose debug information is
compressed with zstd rather than zlib (``-gz=zlib``), or a damaged file - is a usage error,
exit ``2``, and the message names the flag to build it with or without where one would do. So
are a malformed argument and an ``-o`` naming the image, refused before the image is read.

The findings
~~~~~~~~~~~~

They are the tool's own rather than checks of the catalogue: ``ddd checks`` does not list them
and ``-W`` does not take them. DDD's own findings on the declarations are reported beside them
under DDD's identifiers.

.. list-table::
   :header-rows: 1
   :widths: 30 12 58

   * - finding
     - severity
     - when
   * - ``elf-symbol-missing``
     - error
     - a name or a pattern matches no variable of the image's debug information; where the
       symbol table holds the name and no unit's debug information does, the unit defining it
       was built without ``-g``
   * - ``elf-symbol-ambiguous``
     - error
     - several compilation units define the name, other than as one variable at one
       address; ``UNIT:NAME`` takes one. A tentative definition two units share
       (``-fcommon``) is one variable
   * - ``elf-no-storage``
     - error
     - the variable has no address: only declared, folded into a constant or removed by the
       compiler, thread-local, at a location that is not a fixed address, discarded by the
       linker - which leaves its address at 0, or at all ones, where no symbol of its name
       sits - or at an address no section of the image holds
   * - ``elf-type-unsupported``
     - error
     - a type DDD cannot state - a pointer, a union, a ``long double`` wider than eight bytes,
       a ``const`` array of structures - named at the member where it occurs
   * - ``elf-type-conflict``
     - error
     - one name stands for two different structures or enums
   * - ``elf-init-unsupported``
     - error
     - an initial value DDD has no spelling for, such as NaN, or one whose bytes run past
       the end of the section holding it
   * - ``elf-init-dropped``
     - warning
     - a structured object whose values the image holds
   * - ``elf-bitfield-gap``
     - warning
     - bits skipped where the next bitfield would have fit
   * - ``elf-alignment``
     - warning
     - an alignment the source states
   * - ``elf-qualifier-dropped``
     - warning
     - ``const`` or ``volatile`` on a structure member
   * - ``elf-section``
     - warning
     - a section the output states, once per name
   * - ``elf-name-synthesized``
     - warning
     - an anonymous structure or enum given a name
   * - ``elf-types-omitted``
     - warning
     - the list output holds a structured object, whose type only ``--component`` prints
   * - ``elf-boolean-bitfield``
     - info
     - a ``_Bool`` bitfield described as a ``uint8`` one
   * - ``elf-not-inferred``
     - info
     - once per run: what an image never states
