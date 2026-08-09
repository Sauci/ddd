Memory sections
===============

Each data object of an embedded project lives in a memory with a character of its own - RAM,
flash, calibratable ROM behind an emulation overlay, NVM - and the linker places it there by
section. A ``sections`` file declares the sections a project uses, and a definition names
one of them; DDD checks the placement and carries it into the generated c.

.. code-block:: json

   {
     "$schema": "../../schemas/ddd_sections.schema.json",
     "sections": [
       { "section": ".fast_ram", "access": "read-write", "alignment": 4 },
       { "section": ".calib", "access": "read-only", "alignment": 4,
         "description": "calibration flash, tool writable through the emulation overlay" }
     ]
   }

``section`` is the name as the linker script spells it - a linker name rather than a c
identifier, so ``.calib`` is a normal spelling. ``access`` is ``read-write`` or
``read-only`` *from the running software's point of view*; whether a calibration tool can
write a read-only section - an emulation overlay, a calibratable flash - is the target's
business and deliberately not modelled, because the object's ``volatile`` already states
what the software has to assume. ``alignment`` is what the section guarantees, in bytes, a
power of two. The file is listed in the ``includes`` of a project like any other
description, and ``ddd schema sections`` prints its published contract.

A definition then states its ``section`` - a storage key like ``init``: the producer states
it, a consumer stating one is refused as ``consumer-storage``, and a structured variable is
placed whole, its members having no placement of their own. An object without a ``section``
goes wherever the toolchain's defaults put it, which is what makes placement adoptable
gradually.

.. code-block:: json

   {
     "scope": "output",
     "definition": {
       "name": "Speed",
       "kind": "measurement",
       "datatype": "uint16",
       "conversion": {},
       "volatile": true,
       "section": ".fast_ram"
     }
   }

Unlike a unit, a section is a reference rather than a spelling: naming one that no file
declares is refused whether or not any sections file exists, because a section without
declared properties is a name the checks below can say nothing about:

.. code-block:: text

   $ ddd check p.ddd.json
   a.ddd.json#component.interface[2].definition.section: error[unknown-section]: 'Bad' is placed in '.calibb', which is not a section any file of this project declares - did you mean '.calib'?
   1 error

Two checks tie placement to what the description already says. A measurement is written by
the software, so placing one in a read-only section is an error; a calibration object may
live in either - ``const`` data in RAM is a mirrored calibration:

.. code-block:: text

   $ ddd check p.ddd.json
   a.ddd.json#component.interface[2].definition.section: error[section-access]: 'Bad' is a measurement, which the software writes, but '.calib' is read-only
   1 error

And an object whose datatype needs stricter alignment than its section guarantees is
reported - as a warning, because for a structure the need is estimated as the strictest of
its members' datatypes and the compiler's word on the real layout is final:

.. code-block:: text

   $ ddd check p.ddd.json
   a.ddd.json#component.interface[1].definition.section: warning[section-alignment]: 'Gain' needs an alignment of 4, but '.calib' guarantees 2
   1 warning

The generated c carries the placement in whatever spelling the toolchain wants, which is the
templates' business like the rest of the house style; the shipped example templates spell
the GCC attribute, with the attribute between the declarator and the initialiser:

.. code-block:: c

   uint16_t Speed __attribute__((section(".fast_ram")));
   const uint32_t Gain __attribute__((section(".calib"))) = 3U;

Templates also receive the placed objects grouped per section under ``model.sections``,
ordered strictest alignment first with names breaking ties, so that a project wanting
padding-minimal layout can emit each section's data in that order. Describing the layout in
the a2l with ``MOD_PAR`` / ``MEMORY_SEGMENT`` is planned: a segment's address and size exist
only after linking, so they will arrive with the address information rather than being
restated in the vocabulary - the linker script already owns them, and a copy would drift.
