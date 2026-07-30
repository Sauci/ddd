Variable definition
===================

The ``definition`` object of a declaration is where a variable is actually described. It is
the same object whatever the component and whatever the scope, and it deliberately says more
than a c declaration could: a c declaration knows how many bytes a value occupies, but not
what the number in those bytes *means*. ``uint16_t Speed;`` and ``uint16_t Pressure;`` are the
same declaration; ``uint16`` scaled by 0.25 in Hz between 0 and 8000 and ``uint16`` scaled by
0.001 in bar between 0 and 5 are two different things, and the difference is exactly what a
calibration tool needs, what a consuming component has to agree with, and what a review of two
json files can actually catch.

.. code-block:: json

   {
     "name": "ValueE",
     "description": "Measurement used as the input quantity of AxisA",
     "datatype": "uint16",
     "unit": "Hz",
     "conversion": { "kind": "linear", "factor": 0.25 },
     "limits": { "min": 0, "max": 8000 },
     "init": 0,
     "volatile": true
   }

The common attributes
---------------------

Every kind of data object carries the attributes below. The kind specific ones - ``kind``
itself, ``dimensions``, ``volatile``, ``size``, ``input``, ``axis``, ``x_axis``, ``y_axis`` -
are described in the sections that follow, and a key that does not belong to the kind that was
selected is rejected rather than ignored.

.. list-table::
   :header-rows: 1
   :widths: 18 15 67

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - The identifier of the object, used unchanged as the c identifier and as the a2l name.
       Letters, digits and underscore, not starting with a digit, at most 128 characters -
       the ASAP2 1.6.1 limit, which is tighter than what a c compiler would accept and is
       therefore the one enforced.
   * - ``kind``
     - ``measurement``
     - What sort of object this is: ``measurement``, ``parameter``, ``value_block``, ``axis``,
       ``curve`` or ``map``. Omitting it gives a measurement, so the simplest possible
       definition is a name and a datatype.
   * - ``datatype``
     - required
     - The storage the target uses: ``bool``, ``uint8``, ``int8``, ``uint16``, ``int16``,
       ``uint32``, ``int32``, ``uint64``, ``int64``, ``float32`` or ``float64``.
   * - ``description``
     - ``""``
     - Free text. It is offered to the c templates as the text of the comment above the
       generated declaration - what surrounds it is theirs to decide - and it is the long
       identifier of the a2l object, so it is the sentence a calibration engineer reads next
       to the value. An object without one gets its own name as the a2l long identifier,
       which is legal and useless.
   * - ``unit``
     - ``""``
     - The physical unit, as free text: ``Hz``, ``degC``, ``%``. It is shown in the c comment
       in brackets, and it is part of the a2l ``COMPU_METHOD``. Components sharing a variable
       have to agree on it, because two components using the same variable in different units
       is the failure that compiles and links and is wrong by a constant factor.
   * - ``conversion``
     - identity
     - How the stored number maps to the physical one; see :doc:`conversions`.
   * - ``limits``
     - derived
     - An object with ``min`` and ``max``, in **physical** units. When it is left out, DDD
       derives the limits from the datatype and the conversion, so the a2l always carries a
       range.
   * - ``init``
     - ``null``
     - The initial value, in **raw** units. ``null`` means no initialiser is written at all
       and the startup code zero-initialises the object.
   * - ``a2l``
     - export
     - Per object settings for the a2l backend, and nothing else reads them.

.. note::
   ``limits`` and ``init`` are on different sides of the conversion, and that is not an
   inconsistency but the only arrangement that works. Limits are what a calibration engineer
   types into a tool, so they are physical; the initial value is what the compiler writes into
   the image, so it is raw. With a factor of 0.1 a variable whose limits are ``-40`` and
   ``150`` degC is initialised with ``-400``, which is -40.0 degC.

Datatypes
~~~~~~~~~

The datatype names are DDD's own, not c's, because a description file is not a c file and the
same description generates a2l as well. Each one maps to a c type and to an ASAP2 type:

.. list-table::
   :header-rows: 1
   :widths: 16 12 20 22 30

   * - datatype
     - bytes
     - c
     - a2l
     - raw range
   * - ``bool``
     - 1
     - ``bool``
     - ``UBYTE``
     - 0 .. 1
   * - ``uint8``
     - 1
     - ``uint8_t``
     - ``UBYTE``
     - 0 .. 255
   * - ``int8``
     - 1
     - ``int8_t``
     - ``SBYTE``
     - -128 .. 127
   * - ``uint16``
     - 2
     - ``uint16_t``
     - ``UWORD``
     - 0 .. 65535
   * - ``int16``
     - 2
     - ``int16_t``
     - ``SWORD``
     - -32768 .. 32767
   * - ``uint32``
     - 4
     - ``uint32_t``
     - ``ULONG``
     - 0 .. 4294967295
   * - ``int32``
     - 4
     - ``int32_t``
     - ``SLONG``
     - -2147483648 .. 2147483647
   * - ``uint64``
     - 8
     - ``uint64_t``
     - ``A_UINT64``
     - 0 .. 18446744073709551615
   * - ``int64``
     - 8
     - ``int64_t``
     - ``A_INT64``
     - -9223372036854775808 .. 9223372036854775807
   * - ``float32``
     - 4
     - ``float``
     - ``FLOAT32_IEEE``
     - the IEEE 754 single range
   * - ``float64``
     - 8
     - ``double``
     - ``FLOAT64_IEEE``
     - the IEEE 754 double range

The c spellings come from ``<stdint.h>`` and ``<stdbool.h>``. The model tells the templates
which of the two a project actually needs - ``model.needs_stdbool`` is false for a project
without a ``bool`` - so the example templates include neither header for nothing. Literals are
written with the suffix the type asks for, so the generated code survives ``-Wconversion``:
``0U`` for the unsigned types, ``1.5F`` for ``float32``, ``18446744073709551615ULL`` for
``uint64``.

Names, and what a name may not be
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The name is used unchanged in the generated c, which means the description file can produce
code that does not compile, and DDD checks for that rather than letting the compiler explain
it in a generated file nobody wants to read. A name that is a c keyword, or that
``<stdint.h>`` or ``<stdbool.h>`` already declare, is refused:

.. code-block:: text

   $ ddd check reserved.ddd.json
   reserved.ddd.json#component.declarations[0].definition.name: error[reserved-identifier]: variable name 'signed' is reserved by the c language
   reserved.ddd.json#component.declarations[1].definition.name: error[reserved-identifier]: variable name 'uint8_t' is reserved by the c language
   2 errors

So is a name that collides with something else DDD itself generates - an enumerator of an enum
conversion lives in the same c namespace as a variable:

.. code-block:: text

   $ ddd check enumcoll.ddd.json
   enumcoll.ddd.json#component.declarations[0].definition.name: error[name-collision]: 'STATE_OFF' is declared as a variable and is also an enumerator of enum 'S_t'; both become the same c identifier
       note: enumcoll.ddd.json#component.declarations[1].definition.conversion: enumerator declared here
   1 error

Two names differing only in case compile perfectly well and are merely a warning, because they
are legal and occasionally intended - but they are also the classic way for a value to be read
from the wrong variable for a year:

.. code-block:: text

   $ ddd check similar.ddd.json
   similar.ddd.json#component.declarations[1].definition.name: warning[name-similar]: 'valuea' and 'ValueA' differ only in upper/lower case
       note: similar.ddd.json#component.declarations[0].definition: other variable
   1 warning

If the project points at a :doc:`naming convention </naming_conventions>`, the name is checked
against it as well, and the finding says which *part* of the name is wrong.

Initial values
~~~~~~~~~~~~~~

``init`` is a raw value: a scalar, or a nested list matching the shape of the object. Leaving
it out is not the same as writing ``0``. With ``init`` absent no initialiser is generated at
all, and the object lands in the zero-initialised section that the startup code clears, which
for a large array is the difference between a few bytes of image and a few kilobytes:

.. code-block:: c

   /** Floating point measurement without a conversion [degC] */
   float ValueC;
   /** Component local measurement, kept out of the a2l */
   uint16_t ValueD[8];

A **scalar given for an array shaped object initialises every element**, which is what makes a
table of a hundred identical starting values one character long instead of a hundred. The demo
uses it for ``CurveB``, whose ``"init": 200`` covers all six points of the axis it lies over:

.. code-block:: c

   /** Second calibratable curve over the same shared axis [%] (calibration curve over AxisA) */
   const uint8_t CurveB[6] = { 200U, 200U, 200U, 200U, 200U, 200U };

Everything about an initial value is checked against the object it belongs to. A value outside
the raw range of the datatype, a fractional value in an integer object, and a nested list of
the wrong shape are all errors, each naming what it actually is:

.. code-block:: text

   $ ddd check ranges.ddd.json
   ranges.ddd.json#component.declarations[0].definition.init: error[init-invalid]: init value 300 does not fit into uint8 (0 .. 255)
   ranges.ddd.json#component.declarations[2].definition.init: error[init-invalid]: init value 1.5 is written as a fractional number, but 'Fractional' has the integer datatype uint8
   ranges.ddd.json#component.declarations[1].definition.limits: warning[limits-out-of-range]: limits [0, 200] exceed the range [0, 127.5] that uint8 can represent with this conversion
   2 errors, 1 warning

The warning in that transcript is the same idea applied to ``limits``: a ``uint8`` scaled by
0.5 reaches 127.5, so a maximum of 200 is a promise the storage cannot keep. It is a warning
rather than an error because limits are a statement of intent about the data and never reach
the compiler - but it is the finding that stops a calibration engineer from entering a value
the software will silently wrap. Limits are also checked for being the right way round:
``min`` greater than ``max`` is refused when the file is read.

.. code-block:: text

   $ ddd check misc.ddd.json
   misc.ddd.json#component.declarations[0].definition.limits: error[schema]: Value error, min (10) is greater than max (5) (got: {'min': 10, 'max': 5})
   1 error

The a2l block
~~~~~~~~~~~~~

The ``a2l`` object holds what one object asks of the a2l backend. Nothing else in DDD reads
it, and a project generating no a2l can ignore it entirely.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - key
     - default
     - meaning
   * - ``export``
     - ``true``
     - Set to ``false`` to keep the object out of the a2l. The c code is generated as usual;
       only the calibration tool never sees it.
   * - ``format``
     - ``null``
     - The a2l ``FORMAT`` string: ``%``, the total display width, a dot, the number of decimal
       places, as in ``"%8.3"``. It overrides the display format the conversion would
       otherwise imply.
   * - ``display_identifier``
     - ``null``
     - An alternative name for the calibration tool to show, for a variable whose c identifier
       is unhelpful or too long to read in a measurement list.

.. code-block:: json

   {
     "name": "ValueLong",
     "description": "Long name shown shorter in the tool",
     "datatype": "uint16",
     "unit": "Hz",
     "conversion": { "factor": 0.25 },
     "a2l": { "format": "%8.3", "display_identifier": "ValLong" }
   }

.. code-block:: text

   /begin MEASUREMENT ValueLong "Long name shown shorter in the tool"
     UWORD CM_LIN_HZ 0 0 0 16383.75
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "ValueLong" 0
     FORMAT "%8.3"
     DISPLAY_IDENTIFIER ValLong
   /end MEASUREMENT

``export: false`` is the right setting for a component internal scratch variable that would
only clutter the measurement list. The demo uses it twice, on ``ValueD`` and ``ValueK``; both
reach the c templates like every other object, and neither appears anywhere in
``DemoDevice.a2l``, not even in the ``GROUP`` of the component that owns them.

.. warning::
   ``export: false`` on an **axis** that a curve or a map refers to is overruled. The
   ``CHARACTERISTIC`` of the curve carries an ``AXIS_PTS_REF`` naming that axis, and an
   ``AXIS_PTS_REF`` without the ``AXIS_PTS`` it points at would not be a valid a2l file - the
   calibration tool would refuse the whole file, not just the one object. A referenced axis is
   therefore always exported.

The ``format`` string is constrained rather than passed through, and a value that does not
match is refused when the file is read:

.. code-block:: text

   $ ddd check badfmt.ddd.json
   badfmt.ddd.json#component.declarations[0].definition.a2l.format: error[schema]: String should match pattern '^%\d*\.\d+$' (got: '%8')
   1 error

The reason is that the value ends up inside a quoted a2l string literal. A quote or a backslash
in it would unbalance that literal and no calibration tool would parse the file at all, which
would cost a whole delivery for one typo in one description.

Kinds of data object
--------------------

``kind`` decides what the object *is*, and with it how it is stored and what the a2l calls it.
The division that matters is between the one kind the software writes and the five it does
not: a ``measurement`` is an online value that the software produces and the calibration tool
only observes, while everything else is calibration data - the software never writes it, so it
is generated ``const`` and ends up in read only memory where a calibration tool can change it
between sessions.

.. list-table::
   :header-rows: 1
   :widths: 18 24 30 28

   * - kind
     - extra keys
     - c
     - a2l
   * - ``measurement``
     - ``dimensions``, ``volatile``
     - writable variable
     - ``MEASUREMENT``
   * - ``parameter``
     - -
     - ``const`` scalar
     - ``CHARACTERISTIC ... VALUE``
   * - ``value_block``
     - ``dimensions`` (required)
     - ``const`` array
     - ``CHARACTERISTIC ... VAL_BLK``
   * - ``axis``
     - ``size`` (required), ``input``
     - ``const`` array ``[size]``
     - ``AXIS_PTS``
   * - ``curve``
     - ``axis`` (required)
     - ``const`` array ``[size of the axis]``
     - ``CHARACTERISTIC ... CURVE``
   * - ``map``
     - ``x_axis``, ``y_axis`` (required)
     - ``const`` array ``[size of y][size of x]``
     - ``CHARACTERISTIC ... MAP``

Every example below is taken from ``examples/demo/``, and every generated fragment is what
``ddd generate examples/demo/demo.ddd.json -o build/gen -t examples/templates`` actually
writes - the c ones as the example templates render them, the a2l ones as DDD writes them.

measurement
~~~~~~~~~~~

A measurement is a value the software computes and writes, declared with
``"kind": "measurement"`` like every other kind. Two keys are its own: ``dimensions``, a list of array
dimensions that is empty for a scalar, and ``volatile``, which puts the c keyword of the same
name on the definition for a value written by an interrupt or by another task, so that the
compiler does not cache it in a register.

.. code-block:: json

   {
     "scope": "output",
     "definition": {
       "name": "ValueB",
       "description": "Array measurement with four elements",
       "datatype": "uint16",
       "unit": "V",
       "dimensions": [4],
       "conversion": { "factor": 0.001 },
       "init": 0,
       "volatile": true
     }
   }

.. code-block:: c

   /** Array measurement with four elements [V] */
   volatile uint16_t ValueB[4] = { 0U, 0U, 0U, 0U };

.. code-block:: text

   /begin MEASUREMENT ValueB "Array measurement with four elements"
     UWORD CM_LIN_V 0 0 0 65.535
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "ValueB" 0
     MATRIX_DIM 4 1 1
   /end MEASUREMENT

``ValueB`` gives no ``limits``, so the pair ``0 65.535`` in the a2l is derived: a ``uint16``
reaches 65535 and the factor is 0.001. ``MATRIX_DIM`` lists the dimensions in the a2l's x, y, z
order, which is the reverse of the c subscripts - a ``uint8_t M3[2][3][4]`` becomes
``MATRIX_DIM 4 3 2``. ASAP2 1.6.1 carries three dimensions there; an object with more is
generated anyway, with a ``a2l-unrepresentable`` warning saying that only a 1.7 reader will
understand the extra ones.

parameter
~~~~~~~~~

A parameter is a single calibratable constant: one value the software reads and the
calibration tool writes. It has no extra keys at all - a scalar has no shape and a constant
has no volatility.

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "kind": "parameter",
       "name": "ParameterA",
       "description": "Single calibratable constant",
       "datatype": "uint16",
       "unit": "Hz",
       "conversion": { "factor": 0.25 },
       "limits": { "min": 500, "max": 1500 },
       "init": 3200
     }
   }

.. code-block:: c

   /** Single calibratable constant [Hz] (calibration parameter) */
   const uint16_t ParameterA = 3200U;

.. code-block:: text

   /begin CHARACTERISTIC ParameterA "Single calibratable constant"
     VALUE 0x00000000 RL_VALUES_UWORD 0 CM_LIN_HZ 500 1500
     SYMBOL_LINK "ParameterA" 0
   /end CHARACTERISTIC

The raw ``init`` of 3200 is 800 Hz with a factor of 0.25, comfortably inside the physical
limits of 500 and 1500 that the calibration tool will enforce. ``local`` is the usual scope
for a parameter, since data that only tunes one component has no business being visible to the
others.

value_block
~~~~~~~~~~~

A value block is an array of calibratable constants that is not indexed by an axis - a bit
mask table, a set of coefficients, a lookup with an index the software computes itself.
``dimensions`` is required, since an array with no shape is a contradiction.

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "kind": "value_block",
       "name": "BlockA",
       "description": "Calibratable array of constants",
       "datatype": "uint8",
       "dimensions": [8],
       "init": [0, 12, 28, 52, 84, 124, 180, 255]
     }
   }

.. code-block:: c

   /** Calibratable array of constants (calibration value block) */
   const uint8_t BlockA[8] = { 0U, 12U, 28U, 52U, 84U, 124U, 180U, 255U };

.. code-block:: text

   /begin CHARACTERISTIC BlockA "Calibratable array of constants"
     VAL_BLK 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255
     SYMBOL_LINK "BlockA" 0
     MATRIX_DIM 8 1 1
   /end CHARACTERISTIC

``dimensions`` may have more than one entry, and the c declaration then has one subscript per
entry, in the order they are written: ``"dimensions": [2, 3]`` gives ``const uint8_t
Block2D[2][3]`` and a ``MATRIX_DIM 3 2 1``.

axis
~~~~

An axis is the set of break points a curve or a map is interpolated over. It exists as an
object of its own rather than as a property of the curve, and that is the single most useful
thing about the way DDD models tables: **several curves and maps over the same break points
store them once**, and a calibration engineer who moves a break point moves it for all of
them. That is what the a2l calls a ``COM_AXIS``, a common axis.

``size`` is required and gives the number of points. ``input`` optionally names the
measurement that indexes the axis - the physical quantity the tool should show along it. It has
to be a measurement, and it has to exist.

.. code-block:: json

   {
     "scope": "output",
     "definition": {
       "kind": "axis",
       "name": "AxisA",
       "description": "Shared axis indexed by ValueE",
       "datatype": "uint16",
       "unit": "Hz",
       "conversion": { "factor": 0.25 },
       "limits": { "min": 0, "max": 8000 },
       "size": 6,
       "input": "ValueE",
       "init": [0, 3200, 6400, 12800, 19200, 32000]
     }
   }

.. code-block:: c

   /** Shared axis indexed by ValueE [Hz] (calibration axis, 6 points) */
   const uint16_t AxisA[6] = { 0U, 3200U, 6400U, 12800U, 19200U, 32000U };

.. code-block:: text

   /begin AXIS_PTS AxisA "Shared axis indexed by ValueE"
     0x00000000 ValueE RL_AXIS_UWORD 0 CM_LIN_HZ 6 0 8000
     SYMBOL_LINK "AxisA" 0
   /end AXIS_PTS

The scope of an axis follows the same rule as everything else. ``AxisA`` is an ``output`` of
``Controller`` because ``UserInterface`` also puts a curve over it and therefore declares it as
an ``input``; ``AxisB``, which only ``Controller`` uses, is ``local``. Omitting ``input``
is allowed and produces ``NO_INPUT_QUANTITY`` in its place - honest, and less useful to whoever
opens the file.

curve
~~~~~

A curve is a one dimensional calibratable table laid over one axis. It names that axis with
``axis`` and gives **no shape of its own**:

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "kind": "curve",
       "name": "CurveA",
       "description": "Calibratable curve over AxisA",
       "datatype": "uint16",
       "unit": "ms",
       "conversion": { "factor": 0.01 },
       "axis": "AxisA",
       "init": [1200, 900, 800, 750, 700, 650]
     }
   }

.. code-block:: c

   /** Calibratable curve over AxisA [ms] (calibration curve over AxisA) */
   const uint16_t CurveA[6] = { 1200U, 900U, 800U, 750U, 700U, 650U };

.. code-block:: text

   /begin CHARACTERISTIC CurveA "Calibratable curve over AxisA"
     CURVE 0x00000000 RL_VALUES_UWORD 0 CM_LIN_MS 0 655.35
     SYMBOL_LINK "CurveA" 0
     /begin AXIS_DESCR
       COM_AXIS ValueE CM_LIN_HZ 6 0 8000
       AXIS_PTS_REF AxisA
     /end AXIS_DESCR
   /end CHARACTERISTIC

The ``[6]`` in the c declaration was never written down anywhere: DDD takes it from
``AxisA``, whose ``size`` is 6. Repeating the size on the curve would be a second place for it
to be wrong, and a table with one more entry than its axis is the kind of mistake that reads
correctly and interpolates rubbish. Since the shape is derived, the init data is checked
against it:

.. code-block:: text

   $ ddd check badshape.ddd.json
   badshape.ddd.json#component.declarations[1].definition.init: error[init-invalid]: 'CurveS' has the shape [3] given by its axes: init has 2 elements, expected 3
   1 error

The ``AXIS_DESCR`` block is where the sharing becomes visible. ``COM_AXIS`` says that the break
points are not stored inside this characteristic but somewhere else, and ``AXIS_PTS_REF``
says where. ``CurveB`` in the demo carries exactly the same block, pointing at the same
``AxisA``, and the six break points exist once in the image.

map
~~~

A map is a two dimensional calibratable table over two axes, named with ``x_axis`` and
``y_axis``. Like a curve it declares no shape.

.. code-block:: json

   {
     "scope": "local",
     "definition": {
       "kind": "map",
       "name": "MapA",
       "description": "Calibratable map over AxisA and AxisB",
       "datatype": "int8",
       "unit": "%",
       "conversion": { "factor": 0.5 },
       "x_axis": "AxisA",
       "y_axis": "AxisB",
       "init": [
         [20, 24, 28, 30, 32, 30],
         [18, 22, 26, 28, 30, 28],
         [12, 16, 20, 22, 24, 22],
         [6, 10, 14, 16, 18, 16]
       ]
     }
   }

``AxisA`` has 6 points and ``AxisB`` has 4, and the generated array is ``[4][6]`` - **the size
of y first, then the size of x**. That is the row major layout, the one a2l calls ``ROW_DIR``:
a row of the c array is a row of the table, so a whole row of y is contiguous in memory and
the interpolation walks it the way the hardware likes. Written in the same order in the json,
the init data reads exactly like the table it is:

.. code-block:: c

   /** Calibratable map over AxisA and AxisB [%] (calibration map over AxisA and AxisB) */
   const int8_t MapA[4][6] = {
       { 20, 24, 28, 30, 32, 30 },
       { 18, 22, 26, 28, 30, 28 },
       { 12, 16, 20, 22, 24, 22 },
       { 6, 10, 14, 16, 18, 16 }
   };

.. code-block:: text

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

The two ``AXIS_DESCR`` blocks are in x, y order, which is the a2l's convention and the
opposite of the c subscripts - one more reason not to have written the shape by hand. The
limits ``-64 63.5`` are derived, as ``MapA`` gives none: an ``int8`` scaled by 0.5 covers
-64 to 63.5.

References between objects
~~~~~~~~~~~~~~~~~~~~~~~~~~

``axis``, ``x_axis``, ``y_axis`` and ``input`` name other objects, and the object they name may
be declared by **any** component of the project - which is what makes a shared axis possible
in the first place. Both halves of such a reference are checked: that the name exists at all,
and that it points at the right kind of thing.

.. code-block:: text

   $ ddd check refs.ddd.json
   refs.ddd.json#component.declarations[1].definition.axis: error[unknown-reference]: curve 'CurveMissing' refers to 'NoSuchAxis' as its axis, but no component declares 'NoSuchAxis'
   refs.ddd.json#component.declarations[2].definition.axis: error[reference-kind]: the axis of curve 'CurveWrong' must be of kind 'axis', but 'NotAnAxis' is of kind 'parameter'
   2 errors

.. code-block:: text

   $ ddd check axinput.ddd.json
   axinput.ddd.json#component.declarations[1].definition.input: error[reference-kind]: the input of axis 'Ax1' must be of kind 'measurement', but 'NotAMeas' is of kind 'parameter'
   axinput.ddd.json#component.declarations[2].definition.input: error[unknown-reference]: axis 'Ax2' refers to 'Nowhere' as its input, but no component declares 'Nowhere'
   2 errors

Getting the kind wrong is the more interesting of the two, because it is the one that would
otherwise produce an a2l a calibration tool accepts and then misreads: an ``AXIS_PTS_REF``
pointing at a ``CHARACTERISTIC`` is not break points, it is a table being read as if it were.
