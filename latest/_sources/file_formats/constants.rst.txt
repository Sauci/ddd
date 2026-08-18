Constant vocabulary
===================

A ``constants`` file declares named integer constants, so that a size lives in one place and
is shared by name. An array dimension is commonly a named constant of the c project - stated
once, and used by every loop that walks the array - and a bare number in a description
restates that constant and drifts from it silently. With the vocabulary declared, a shape
names the constant where it would state the number, the generated c declares the array by
that name, and the a2l records the constant for the calibration tool.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_constants.schema.json",
     "constants": [
       { "name": "PRESSURE_CELLS", "value": 8,
         "description": "cells of the pressure manifold" },
       { "name": "AXIS_POINTS", "value": 16 }
     ]
   }

``name`` is a c identifier: it reaches the generated code as an identifier of its own, so
the length cap, ``reserved-identifier`` and ``name-collision`` apply to it like to any other
name. ``value`` is an integer of at least 1, written as a number and as a literal only: an
expression would put a parser and an evaluation order into a description format, and a
constant cannot name another constant - what cannot be written cannot cycle. ``description``
is where the meaning of a size is written down once, instead of being implied by every
object that happens to be dimensioned by it. The file is listed in the ``includes`` of a
project like any other description, and ``ddd schema constants`` prints its published
contract. ``examples/vocabulary`` is a ready to run project that declares one next to its
:doc:`unit vocabulary <units>` and :doc:`memory sections <sections>`; it checks clean.

A shape then names a constant where it would state a number: an entry of ``dimensions``, or
the ``size`` of an axis, is either an integer or the name of a declared constant, and a list
mixes the two freely - ``[3, 4]`` and ``["PRESSURE_CELLS", 4]`` are both shapes, on a
declaration and on a structure member alike:

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "name": "ManifoldPressure",
       "kind": "measurement",
       "datatype": "uint16",
       "unit": "kPa",
       "conversion": { "kind": "linear", "factor": 0.1, "offset": 0.0 },
       "dimensions": ["PRESSURE_CELLS"],
       "volatile": true
     }
   }

Like a section, a constant is a reference rather than a spelling: naming one that no file
declares is refused whether or not any constants file exists, with the nearest declared name
suggested, and the finding lands on the dimension entry that names it:

.. code-block:: text

   $ ddd check p.ddd.json
   a.ddd.json#component.interface[0].definition.dimensions[0]: error[unknown-constant]: 'CellPressure' is dimensioned by 'PRESURE_CELLS', which is not a constant any file of this project declares - did you mean 'PRESSURE_CELLS'?
   1 error

A constant declared a second time, in the same file or another, is refused rather than merged - a
size that depends on which file loads first is exactly what the vocabulary exists to
prevent:

.. code-block:: text

   $ ddd check p.ddd.json
   two.ddd.json#constants[0]: error[duplicate-constant]: constant 'PRESSURE_CELLS' is already declared
       note: one.ddd.json#constants[0]: first declared here
   1 error

A name and its value are different spellings of one size, so declarations of one object have
to agree on the spelling (``definition-mismatch``), exactly as conversions compare as
written: ``[8]`` here and ``["PRESSURE_CELLS"]`` there generate different c, and the
spelling is what reaches every consumer's header. The delivery comparison holds the same
line - a dimension compares as its spelling *and* its value, so renaming the constant an
array is dimensioned by is a ``changed-interface`` even while the number stands. A baseline
archived before dictionary format 4 recorded no spellings, so against such a baseline only
the values are compared: adopting a constant for a size that stands reads clean, and a
changed size is still a ``changed-interface``.

What the outputs make of it
---------------------------

The generated c declares a constant-dimensioned array by the constant's name, in its
definition and in every declaration, and the templates receive the declared constants under
``model.constants`` to emit however the house style spells one. The shipped example
templates write each as a ``#define`` in the types header, so the arrays compile against the
same header that declares their sizes:

.. code-block:: c

   /* ddd_types.h */
   #define PRESSURE_CELLS 8 /**< cells of the pressure manifold */

   /* ddd_globals.c */
   volatile uint16_t ManifoldPressure[PRESSURE_CELLS] __attribute__((section(".fast_ram")));

``ddd list`` shows the spelling too - the ``SHAPE`` column of ``ManifoldPressure`` reads
``[PRESSURE_CELLS]`` - while every record of the a2l spells its sizes as resolved numbers,
because a ``MATRIX_DIM`` accepts no symbol where it expects a count. The declared constants
themselves reach the a2l as one ``SYSTEM_CONSTANT`` per constant, in name order, inside the
``MOD_PAR`` of the module:

.. code-block:: text

   /begin MOD_PAR "named constants of PumpDevice"
     SYSTEM_CONSTANT "PRESSURE_CELLS" "8"
   /end MOD_PAR

The :doc:`data dictionary </data_dictionary>` carries both halves: every resolved object
states its numeric ``shape`` beside ``dimensions``, the same shape as the project spells it,
and the declared constants are recorded whole at the top level, so a generator consuming the
dictionary can emit them the way the shipped templates do.
