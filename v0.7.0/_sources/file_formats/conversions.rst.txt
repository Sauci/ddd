Conversions
===========

A ``uint16`` in an embedded image is sixteen bits and nothing more. Whether those bits are a
frequency in quarter hertz, a temperature in tenths of a degree with an offset, or the number
three standing for the word ``STATE_DEGRADED`` is a fact that lives outside the c code - in a
comment, in a header of magic constants, or in the memory of whoever wrote the driver. That
fact is what a calibration engineer needs in order to read the value at all, and what a
consuming component has to agree with in order to use it correctly, so DDD makes it part of
the definition:

.. code-block:: json

   { "kind": "identity" }
   { "kind": "linear", "factor": 0.25, "offset": -40.0 }
   { "kind": "enum", "name": "StateA_t", "enumerators": { "STATE_OFF": 0, "STATE_FAULT": 15 } }

The conversion is the rule that maps the **raw** value - the number in the storage the target
allocates - to the **physical** value, the quantity the number stands for. It is what makes
the a2l show 23.5 degC where the image holds 235, and it is one of the attributes on which the
components sharing a variable have to agree: a rescaling that only one side knows about is the
failure that compiles, links, runs, and reports every value wrong by a constant factor.

``kind`` may be omitted when the shape of the object makes it unambiguous. An object with
``enumerators`` or a ``name`` is an enum, one with a ``factor`` or an ``offset`` is linear, and
one with neither is the identity. That is why ``{"factor": 0.001}`` is a complete conversion,
and it is the form most of ``examples/demo/`` uses. Spelling ``kind`` out is never wrong and
is worth doing wherever the file is read more often than it is written.

identity
--------

``physical == raw``: the stored number *is* the quantity. It is stated like every other
conversion - a ``conversion`` is required wherever storage is named by ``datatype``, and
``{}`` is its shortest spelling - because raw equalling physical is an engineering claim
about the data, and a forgotten scaling on a fixed point value displays raw counts without
anything looking broken. Use it for counters, bit fields, flags, and for floating point
values that already carry the physical quantity.

``linear`` with ``factor`` 1 and ``offset`` 0 is *not* the identity: conversions compare as
written, so two components spelling the no-op the two ways disagree
(``definition-mismatch``), and the a2l carries what was written - a ``RAT_FUNC`` against an
``IDENTICAL``.

The identity is not the absence of a conversion, though, and the a2l shows the difference. An
object with no unit gets ``NO_COMPU_METHOD``, because there is genuinely nothing to say about
how to read it:

.. code-block:: text

   /begin MEASUREMENT FlagA "Boolean measurement"
     UBYTE NO_COMPU_METHOD 0 0 0 1
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "FlagA" 0
   /end MEASUREMENT

An object that *does* carry a unit gets a ``COMPU_METHOD`` of type ``IDENTICAL``, whose whole
content is that unit and a display format - so the calibration tool labels the axis of its
plot and the column of its list, which is the entire point of having written ``"unit":
"degC"`` in the first place:

.. code-block:: text

   /begin COMPU_METHOD CM_IDENT_DEGC "physical value in degC"
     IDENTICAL "%8.3" "degC"
   /end COMPU_METHOD

   /begin MEASUREMENT ValueC "Floating point measurement without a conversion"
     FLOAT32_IEEE CM_IDENT_DEGC 0 0 -50 90
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "ValueC" 0
   /end MEASUREMENT

linear
------

``physical = raw * factor + offset``. This is the scaling of a fixed point value: the reason an
integer datatype can carry a fractional quantity, and by far the most common conversion in a
real project. ``factor`` defaults to ``1.0`` and ``offset`` to ``0.0``, so
``{"factor": 0.25}`` and ``{"offset": -40}`` are both complete.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``factor``
     - ``1.0``
     - The resolution: how much physical quantity one count of the raw value is worth. May be
       negative; may not be zero.
   * - ``offset``
     - ``0.0``
     - The physical value that raw zero stands for.

``factor`` must not be zero, and a file that says otherwise is refused when it is read:

.. code-block:: text

   $ ddd check zerofactor.ddd.json
   zerofactor.ddd.json#component.interface[0].definition.conversion: error[schema]: Value error, factor must not be zero (got: {'kind': 'linear', 'factor': 0})
   1 error

A factor of zero would map every raw value in the image onto the same physical value, which
makes the variable unreadable, and it has no inverse - the calibration tool going the other
way computes ``raw = (physical - offset) / factor`` and would divide by zero. Neither the c
code nor the a2l could be generated meaningfully, so the value is rejected at the source
rather than producing an output that fails somewhere downstream.

What the a2l looks like
~~~~~~~~~~~~~~~~~~~~~~~

A linear conversion becomes a ``COMPU_METHOD`` of type ``RAT_FUNC``. Its ``COEFFS`` look
inverted at first sight, and they are: ASAP2 defines the rational function as a mapping from
the **physical** value to the raw one, ``f(x) = (a·x² + b·x + c) / (d·x² + e·x + f)``, so the
six coefficients ``0 1 -offset 0 0 factor`` spell out ``raw = (physical - offset) / factor``,
which is DDD's rule read backwards. The description string above the coefficients carries the
rule in the readable direction:

.. code-block:: text

   /begin COMPU_METHOD CM_LIN_DEGC "phys = raw * 0.1 + 0"
     RAT_FUNC "%8.3" "degC"
     COEFFS 0 1 0 0 0 0.1
   /end COMPU_METHOD

   /begin MEASUREMENT ValueF "Signed measurement with a fixed point conversion"
     SWORD CM_LIN_DEGC 0 0 -40 150
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "ValueF" 0
   /end MEASUREMENT

With a non-zero offset the sign becomes visible. A conversion of ``factor 0.5, offset -40``
produces ``COEFFS 0 1 40 0 0 0.5`` - the offset negated, exactly as the inverted reading
requires.

enum
----

Some values are not measured but named: a state machine, a fault code, an operating mode. An
enum conversion is a verbal conversion table - the raw value *is* the physical value, and what
the conversion adds is a name for each of them. It requires an integer datatype, since a state
machine cannot be in state 2.5 and no calibration tool would know what to display for it:

.. code-block:: text

   $ ddd check enumfloat.ddd.json
   enumfloat.ddd.json#component.interface[0].definition: error[schema]: Value error, enum conversion 'E_t' requires an integer datatype, got 'float32' (got: {'name': 'EnumOnFloat', 'datatype': 'float32', 'conversio...)
   1 error

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - The name of the generated c type. It is shared across the project: two objects with the
       same enum name are the same enumeration and must agree.
   * - ``enumerators``
     - required
     - The named values, at least one, in either of the two spellings below. Names have to be
       unique within the enum.

Two spellings
~~~~~~~~~~~~~

The short one is a plain json object mapping each name to its value. It is the form to use
when the names speak for themselves, and it keeps a twenty-entry fault code list readable:

.. code-block:: json

   {
     "name": "Mode",
     "kind": "measurement",
     "description": "Short form",
     "datatype": "uint8",
     "conversion": {
       "kind": "enum",
       "name": "Mode_t",
       "enumerators": { "MODE_OFF": 0, "MODE_RUN": 1, "MODE_FAULT": 15 }
     },
     "volatile": false
   }

The long one is a list of objects, which costs more lines and buys a ``description`` per
enumerator - the sentence that explains what the state actually means to somebody who did not
write the state machine:

.. code-block:: json

   {
     "name": "Level",
     "kind": "measurement",
     "description": "Long form",
     "datatype": "uint8",
     "conversion": {
       "name": "Level_t",
       "enumerators": [
         { "name": "LEVEL_LOW",  "value": 0, "description": "below the working range" },
         { "name": "LEVEL_OK",   "value": 1, "description": "inside the working range" },
         { "name": "LEVEL_HIGH", "value": 2, "description": "above the working range" }
       ]
     },
     "volatile": false
   }

The two are the same thing to DDD - the short form is expanded into the long one with empty
descriptions - so a project can start with the short spelling and grow into the long one
where it turns out to be worth the space. Note that the conversion of the second example above
omits its ``kind``: a conversion carrying ``enumerators`` cannot be anything else. The
``kind`` next to the name of the object is the other one - what sort of data object this is -
and that one is always stated.

What it generates
~~~~~~~~~~~~~~~~~

In c, each distinct enum reaches the templates as one entry of ``model.enums``, and the
example templates turn it into one ``typedef enum`` with the descriptions as comments on the
enumerators. The variable itself keeps its declared datatype, so the storage is exactly the
``uint8`` that was asked for rather than whatever width the compiler would pick for an enum;
the generated type is there for the application code to use for the constants and in its
switch statements.

.. code-block:: c

   /* Level_t */
   typedef enum
   {
       LEVEL_LOW = 0, /**< below the working range */
       LEVEL_OK = 1, /**< inside the working range */
       LEVEL_HIGH = 2 /**< above the working range */
   } Level_t;

   /* Mode_t */
   typedef enum
   {
       MODE_OFF = 0,
       MODE_RUN = 1,
       MODE_FAULT = 15
   } Mode_t;

In the a2l, the enum becomes a ``COMPU_VTAB`` holding the table and a ``COMPU_METHOD`` of type
``TAB_VERB`` pointing at it, so the calibration tool shows the name and not the number:

.. code-block:: text

   /begin COMPU_VTAB VTAB_Mode_t "values of Mode_t" TAB_VERB 3
     0 "MODE_OFF"
     1 "MODE_RUN"
     15 "MODE_FAULT"
   /end COMPU_VTAB

   /begin COMPU_METHOD CM_Mode_t "verbal conversion for Mode_t"
     TAB_VERB "%8.0" ""
     COMPU_TAB_REF VTAB_Mode_t
   /end COMPU_METHOD

One name, one enumeration
~~~~~~~~~~~~~~~~~~~~~~~~~

Because the enum name becomes a c type name shared by the whole project, two components using
that name for two different sets of values is an error, and the finding prints both sets so
that the difference does not have to be hunted for:

.. code-block:: text

   $ ddd check project.ddd.json
   b.ddd.json#component.interface[0].definition.conversion: error[enum-conflict]: enum 'State_t' is defined with different enumerators
       note: here: STATE_OFF=0, STATE_ON=2
       note: a.ddd.json#component.interface[0].definition.conversion: first defined as: STATE_OFF=0, STATE_ON=1
   1 error

Two components declaring the **same** set of values are fine, and only one entry reaches the
templates for them. Where they differ only in how well they are documented, the better
documented spelling is the one that reaches the generated code - so a consumer that spelled
the enum out with descriptions improves the header for everybody, and a producer that used the
short form loses nothing:

.. code-block:: c

   typedef enum
   {
       STATE_OFF = 0, /**< powered but idle */
       STATE_ON = 1 /**< running */
   } State_t;

Two further things are checked. Every enumerator has to fit into the datatype of the object,
which is an error, since the constant would otherwise be truncated silently:

.. code-block:: text

   $ ddd check dupenum.ddd.json
   dupenum.ddd.json#component.interface[1].definition: error[init-invalid]: enumerator(s) N_A=200 of enum 'N_t' do not fit into int8
   dupenum.ddd.json#component.interface[0].definition.conversion: warning[enum-duplicate-value]: enum 'M_t': M_A, M_B all have the value 1
   1 error, 1 warning

And two enumerators sharing a value is a warning rather than an error, because it is legal c
and occasionally intended - an alias for a state that has been renamed - but it makes the a2l
table ambiguous, since the calibration tool has two names to choose from for the same reading.

Limits, and where they come from when nobody writes them
--------------------------------------------------------

``limits`` are physical and optional, and DDD always ends up with a pair, because an a2l object
without a range is not something a calibration tool can work with. When the definition gives
none, the limits are derived from the datatype and the conversion - the full raw range of the
storage, run through the conversion:

* **identity** - the raw range of the datatype, unchanged. A ``uint8`` gives 0 .. 255.
* **linear** - the conversion applied to both ends of the raw range. A ``uint8`` with
  ``factor 0.5, offset -40`` gives -40 .. 87.5.
* **enum** - the smallest and the largest enumerator value. The values in between do not have
  to be contiguous, and the range is about what the tool may display, not about what the
  storage could hold.

A **negative factor swaps the two ends**, and DDD swaps them back: the conversion of the
smallest raw value is then the largest physical value, and limits with ``min`` above ``max``
would be rejected by the very validation that keeps hand-written limits sane. An ``sint8`` with
``factor -0.25, offset 10`` runs from raw -128, which is 42, down to raw 127, which is -21.75,
and the derived limits come out in the order a reader expects:

.. code-block:: json

   {
     "name": "Inverted",
     "kind": "measurement",
     "datatype": "sint8",
     "unit": "bar",
     "conversion": { "factor": -0.25, "offset": 10 },
     "volatile": false
   }

.. code-block:: text

   /begin COMPU_METHOD CM_LIN_BAR "phys = raw * -0.25 + 10"
     RAT_FUNC "%8.3" "bar"
     COEFFS 0 1 -10 0 0 -0.25
   /end COMPU_METHOD

   /begin MEASUREMENT Inverted "Inverted"
     SBYTE CM_LIN_BAR 0 0 -21.75 42
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "Inverted" 0
   /end MEASUREMENT

Derived limits are what most of ``examples/demo/`` relies on for its calibration data:
``CurveA`` is a ``uint16`` scaled by 0.01 and gets ``0 655.35``, ``CurveB`` is a ``uint8``
scaled by 0.5 and gets ``0 127.5``, ``MapA`` is an ``sint8`` scaled by 0.5 and gets
``-64 63.5``. Writing the limits out by hand is worth doing when the *intended* range is
narrower than what the storage can hold - ``ParameterA`` is a ``uint16`` scaled by 0.25 and
could reach 16383.75, but the project means it to stay between 500 and 1500 Hz, and only the
description file knows that.

.. warning::
   Explicit limits are checked against the range the storage can actually represent, but only
   as a warning: ``limits-out-of-range`` fires when a ``uint8`` scaled by 0.5 is given a
   maximum of 200, which is beyond the 127.5 it can reach. It is a warning because limits
   never reach the c compiler - they are a statement of intent about the data - but it is the
   finding that stops a calibration engineer from entering a value the software will silently
   wrap.

One compu method per conversion and unit
----------------------------------------

Conversions are not written out once per object. Two objects with the same conversion **and**
the same unit share one ``COMPU_METHOD``, whatever their kind and whatever their datatype, so
the a2l stays readable and the calibration tool has one entry to configure rather than twenty
identical ones. In the demo, ``ValueA``, ``AxisB``, ``CurveB`` and ``MapA`` all use
``CM_LIN_PCT`` - a measurement, an axis, a curve and a map, over two datatypes and one
conversion.

The unit is part of the identity because it is part of what the method says; the name is built
from it, which is why ``CM_LIN_HZ``, ``CM_LIN_DEGC`` and ``CM_LIN_V`` read the way they do. Two
different conversions in the same unit therefore want the same name, and the second gets a
numbered suffix - the demo scales one percentage by 0.5 and another by 0.1, and ends up with
``CM_LIN_PCT`` and ``CM_LIN_PCT_2``. The display format that goes with a method is derived from
the datatype and the conversion, ``%8.0`` where every physical value is whole and ``%8.3``
otherwise; a single object can override it with its own ``a2l.format``, which is described with
the :doc:`variable definition <variable_definition>`.
