Unit vocabulary
===============

A ``units`` file declares the units a project spells. ``unit`` is free text everywhere it is
written - DDD cannot know that ``Nm`` and ``newton_meter`` mean the same thing - and without
a vocabulary the drift is invisible: each object agrees with itself, the a2l grows one
``COMPU_METHOD`` per spelling, and the calibration tool shows two units for one quantity.
The vocabulary is the opt-in that pins the spellings once, for the whole project.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_units.schema.json",
     "units": [
       "rpm",
       { "unit": "Nm", "description": "torque, newton metre" },
       { "unit": "degC", "description": "temperature" }
     ]
   }

An entry is a bare spelling, or an object adding a ``description`` - which is where the
meaning of a unit is written down once, instead of being implied by every object that
happens to use it. Case counts: ``mV`` and ``MV`` are different units. The file is listed in
the ``includes`` of a project like any other description, and ``ddd schema units`` prints
its published contract. ``examples/vocabulary`` is a ready to run project that declares a
vocabulary like this next to its :doc:`memory sections <sections>` and
:doc:`constants <constants>`; it checks clean, so it is the file set to start a project of
your own from.

With a vocabulary declared, every stated unit - on a declaration, on a structure member, on
a scalar type - is checked where it is written:

.. code-block:: text

   $ ddd check p.ddd.json
   a.ddd.json#component.interface[0].definition.unit: error[unknown-unit]: 'newton_meter' is not a unit this project declares
   1 error

A near miss is answered with the declared spelling - ``'nm' ... did you mean 'Nm'?`` - and
the empty unit is always allowed: a dimensionless value states no unit rather than a
spelling of one. A project without a units file keeps its units free; introducing a
vocabulary into a grown project can start with ``-W unknown-unit=warning`` until the
spellings are settled.

A unit declared a second time, in the same file or another, is refused rather than merged:

.. code-block:: text

   $ ddd check p.ddd.json
   two.ddd.json#units[0]: error[duplicate-unit]: unit 'Nm' is already declared
       note: one.ddd.json#units[0]: first declared here
   1 error
