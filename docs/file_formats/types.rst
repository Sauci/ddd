Structured datatype description
===============================

A ``types`` file declares composite datatypes - structures - that the rest of a project refers
to by name. It is a file of its own rather than a section of a component, because a structure is
usually shared: the point of declaring ``Sensor_t`` once is that two components can agree on it
without either of them owning it.

.. note::
   The format below is read, validated and checked. Referring to a structure from a component
   declaration - instantiating one as a variable - is the next step and is not available yet, so
   for the moment a ``types`` file describes structures without any variable having one.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_types.schema.json",
     "types": [
       {
         "name": "Status_t",
         "description": "Flags packed into one word, as c bitfields",
         "members": [
           {
             "name": "ready",
             "member": "bits",
             "kind": "measurement",
             "description": "Set once the sensor has produced a first reading",
             "datatype": "uint16",
             "bits": 1
           },
           {
             "name": "mode",
             "member": "bits",
             "kind": "measurement",
             "description": "Which of the three operating modes is active",
             "datatype": "uint16",
             "bits": 2
           }
         ]
       }
     ]
   }

The file is listed in the ``includes`` of a project, next to its components:

.. code-block:: json

   { "project": { "name": "StructuredDevice", "includes": ["types.ddd.json", "sensing.ddd.json"] } }

``examples/structures`` is the whole of the above, ready to run:

.. code-block:: text

   $ ddd check examples/structures/project.ddd.json
   ok: 2 variables in 1 component are consistent

A structure on its own is not a project, so pointing ``ddd check`` straight at a ``types`` file
is refused rather than half-processed - there is nothing to resolve or generate from it, and
validating it against the published schema is what an editor is for.

Three kinds of member
---------------------

Every member states which shape it has, in the ``member`` key. It is stated rather than inferred
from which other keys are present, so that a file which omits a key by mistake is told which
member shape it failed to describe instead of silently becoming another one.

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - ``member``
     - what it is
   * - ``value``
     - a ``datatype``, optionally an array through ``dimensions``. The ordinary case.
   * - ``bits``
     - a ``datatype`` and a width in ``bits``: a c bitfield. Consecutive bit members share a
       storage unit.
   * - ``struct``
     - another declared structure, named by ``type``, nested in this one.

Each shape permits exactly the keys it needs and refuses the rest. ``bits`` together with
``dimensions`` is an example worth spelling out: an array of bitfields is not something c can
express, so accepting the pair and quietly ignoring one half would put a structure in the
generated c that the description does not describe. A ``value`` or ``bits`` member also states
its ``kind``, ``measurement`` or ``parameter``, which decides whether a calibration tool may
write it; the other object kinds refer to further objects, which a member has no way to do.

A bitfield has to fit its storage and has to sit in an integer: ``17`` bits do not fit a
``uint16``, and c allows a bitfield only in an integer type, so ``float32`` and ``boolean`` are
refused.

Member order is significant
---------------------------

The members are laid out in the order the file lists them, because that is the order the
generated c declares them in and therefore the order the compiler lays out. Reordering the
members of a structure that has already been delivered moves every address after the change.

Where the bits are is not stated here
-------------------------------------

A ``bits`` member gives a width and no position, and that is deliberate rather than an omission.
C leaves the allocation order within a storage unit implementation defined: whether ``ready : 1``
lands in the least or the most significant bit is a property of the compiler and the target, not
of the description. Stating a position here would be stating something DDD cannot honour.

The same is true of offsets. A structure's members have offsets, and those follow from the
target's alignment rules and from whatever packing the build applies - which means the honest
source for both is the build itself, not a model of it. DDD reads the real layout back out of
the compiled result rather than predicting it, on the same principle that already applies to
addresses: ``ddd generate`` puts ``0x00000000`` in the a2l until a build tells it otherwise.

One consequence reaches the a2l, and the reasoning behind it is on the
:doc:`developer documentation </developer_documentation>` page: a structure does not become an
a2l structure. It is flattened into one ordinary object per member, because the calibration tools
this project targets accept the native form and then display nothing for it.

Checks over the structures
--------------------------

Three findings are specific to this file, and all three are errors:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - check
     - what it means
   * - ``duplicate-type``
     - two files declare a structure of the same name. Which of two layouts the generated c
       would get is not something an include order should decide.
   * - ``unknown-type``
     - a ``struct`` member nests a structure no file declares. A member of unknown size makes
       every offset after it wrong, and wrong offsets are addresses that point at the wrong
       bytes without anything looking broken.
   * - ``type-cycle``
     - structures nest each other, directly or through others. The finding names the chain,
       because that says which member to remove:

.. code-block:: text

   $ ddd check project.ddd.json
   types.ddd.json#types[0]: error[type-cycle]: structured datatypes nest each other: A_t -> B_t -> A_t
   types.ddd.json#types[2].members[0]: error[unknown-type]: member 'gone' nests structured datatype 'Missing_t', which no file of this project declares
   2 errors

A cycle is reported once however many routes lead into it, and against the structure the cycle
closes on rather than whichever one the search happened to start from.
