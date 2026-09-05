Measurement rasters
===================

A calibration tool measuring over XCP does not read a variable whenever it likes: the target
sends values cyclically, in a *DAQ event* the tool subscribes to, and each event belongs to a
task of the running software. A ``rasters`` file declares the events the target offers, and a
measurement names the one its producing component updates it in; DDD writes that event into
the generated a2l, so the tool preselects the right one rather than leaving an engineer to
guess which task moves the signal.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_rasters.schema.json",
     "rasters": [
       { "raster": "1ms", "event": 0, "cycle": "1ms", "description": "fast control task" },
       { "raster": "10ms", "event": 1, "cycle": "10ms", "description": "control task" },
       { "raster": "crank", "event": 3, "description": "crank synchronous, not cyclic" }
     ]
   }

``raster`` is the name a definition refers to, one word without whitespace, and it is also
the short name the a2l gives the event - a field eight characters wide, which is where the
limit comes from. It is not a
protocol limit: XCP itself length-prefixes an event channel name and carries far more. A
longer one is refused rather than shortened, because two names shortened to the same eight
would collide in a calibration tool rather than here, where the author can still do something
about it. No file DDD writes carries an event name today, and the limit applies anyway, so
that a rasters file written now still loads once the module level ``DAQ`` block does.
``event`` is the event channel number the target's XCP configuration assigned, 0 to 65535 and
distinct across the project. ``cycle`` is the period, spelled the way an XCP event period is
carried: a count from 1 to 255 times a decade from 1 ns to 1 s - ``100us``, ``10ms``, ``1s``,
``1500us`` rather than ``1.5ms``, ``2s`` but not ``300s``, and ``255ms`` but not ``256ms``.
It is optional: an event with no period is not cyclic, which is what a crank synchronous or
an on-change raster is, and that is a description rather than an omission. ``description`` is
free text.

The file is project wide, listed in the ``includes`` of a project like any other description;
``ddd schema rasters`` prints its published contract. It has no place inside a component, for
the reason the :doc:`unit vocabulary <units>` and the :doc:`memory sections <sections>` have
none: an event channel number is a property of the target's XCP configuration, and a
component declaring one would be asserting a number it does not decide.

Naming a raster
---------------

A definition states its ``raster``, and a component states a default for everything it
produces:

.. code-block:: json

   {
     "component": {
       "name": "Controller",
       "raster": "10ms",
       "interface": [
         {
           "scope": "output",
           "definition": {
             "name": "EngineSpeed", "kind": "measurement", "datatype": "uint16",
             "unit": "rpm", "conversion": { "kind": "identity" }, "volatile": true
           }
         },
         {
           "scope": "output",
           "definition": {
             "name": "FuelRate", "kind": "measurement", "datatype": "uint16",
             "unit": "mg", "conversion": { "kind": "identity" }, "volatile": true,
             "raster": "1ms"
           }
         }
       ]
     }
   }

``EngineSpeed`` is measured in the 10 ms event because its component says so, and ``FuelRate``
overrides that with its own. Two levels and no third: one image mixes components running at
different rates, so a project wide default would be wrong for most of them, and "why is this
signal in the 10 ms event" is a question worth keeping to one place to look.

The raster follows the **producer**, because it is the producing task that updates the value.
A component reading a variable somebody else writes states no raster for it - doing so is
refused as ``consumer-raster``, the way stating an ``init`` or a ``section`` is - and its own
default does not reach a variable it merely reads. A default reaches no calibration object
either: no DAQ list carries a ``CHARACTERISTIC``, so a ``raster`` written on one is refused as
``raster-kind``, while a default that happens to cover one simply does not apply. A structured
variable carries one raster for the whole object, and every member inherits it.

A measurement that names no raster, whose component names none either, reaches the a2l exactly
as it did before there were rasters at all: described, but with no preselected event. Adoption
is gradual, one component at a time.

What reaches the a2l
--------------------

Each exported measurement with a raster carries the event it belongs to - here
``EngineSpeed`` as the component above declares it, before an address map has been applied:

.. code-block:: text

   /begin MEASUREMENT EngineSpeed "EngineSpeed"
     UWORD CM_IDENT_RPM 0 0 0 65535
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "EngineSpeed" 0
     /begin IF_DATA XCP
       /begin DAQ_EVENT VARIABLE
         /begin DEFAULT_EVENT_LIST
           EVENT 1
         /end DEFAULT_EVENT_LIST
       /end DAQ_EVENT
     /end IF_DATA
   /end MEASUREMENT

It is a ``DEFAULT_EVENT_LIST`` rather than a fixed one: the raster is the event the tool
preselects, and the engineer may still move the signal, so a raster that turns out wrong is
corrected in the tool rather than by regenerating the file.

.. note::
   DDD writes which event a measurement belongs to, and not what the events are or how a tool
   reaches the target. The module level ``DAQ`` block defining the event channels, the
   ``PROTOCOL_LAYER`` and the transport - ``XCP_ON_CAN``, ``XCP_ON_ETH`` - describe the
   target's XCP implementation rather than its data, and come from whatever configures the
   XCP stack. The ``cycle`` a raster declares is carried in the
   :doc:`data dictionary </data_dictionary>` for a generator that writes that block; DDD does
   not write it to the a2l.

``examples/vocabulary`` is a ready to run project declaring rasters next to its
:doc:`units <units>`, :doc:`sections <sections>` and :doc:`constants <constants>`; it checks
clean.
