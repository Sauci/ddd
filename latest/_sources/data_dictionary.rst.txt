Data dictionary
===============

The data dictionary is the resolved form of a project: every data object with its owner, its
users, its shape, its limits and its scaling already worked out. It is the contract between
the checking front end of DDD and its output backends, and it is the only thing they share.
Everything before it - loading the description files, resolving the declarations, running
the :doc:`consistency checks <consistency_checks>` - produces a dictionary; everything after
it - the c backend, the a2l backend, whatever is added next - consumes one and nothing else.
A backend therefore never reaches into the loader or into the analysis, and if it needs to
know something, that something is a field of the dictionary rather than a second calculation
performed in a template.

That arrangement is worth having for two reasons. The first is that two backends cannot
disagree about what a project contains: the shape a c array is declared with and the
``MATRIX_DIM`` written into the a2l are read from one field, so they cannot drift apart -
each backend only has to order the indices the way its own format wants them, c with the
last index running fastest and ASAP2 with the first. The second is that the work of
resolving a project is done once, in a place that reports findings, instead of once per
output format in a place that can only crash.

DDD publishes the dictionary rather than keeping it to itself. ``ddd dump`` writes it out as
json, and ``ddd schema dictionary`` prints its json schema, so a generator DDD does not ship
- a report, a database importer, a header for a language DDD knows nothing about - can
consume a checked project without importing python and without depending on any of the
implementation:

.. code-block:: bash

   ddd dump examples/demo/demo.ddd.json > dictionary.json
   ddd schema dictionary > dictionary.schema.json

.. code-block:: text

   $ ddd dump examples/demo/demo.ddd.json
   {
     "format": 1,
     "name": "DemoDevice",
     "description": "Demonstration project showing every DDD feature",
     "source": "demo.ddd.json",
     "components": [
       {
         "name": "Controller",
         "description": "Consumes the raw values and produces the derived ones",
         "source": "controller.ddd.json",
         "declarations": [
           {
             "name": "ValueA",
             "scope": "input",
             "condition": null
           },
   ...

``ddd dump`` is the one command whose standard output *is* the payload, so its findings go
to standard error and the redirection above works whether or not the project has any. The
same file is what :doc:`comparing two deliveries <comparing_deliveries>` needs: archive the
dictionary of a delivery next to its binary, and a later ``ddd compare`` can answer whether
the next delivery may replace it, long after the sources of the first one have moved on.

What is already resolved
------------------------

The value of the dictionary is what a backend no longer has to work out. By the time a
backend sees it:

The **limits are filled in.** ``limits`` is never absent. A declaration that states its
physical limits keeps them; one that does not gets the full range its datatype and
conversion imply, computed once. A backend writing ``LOWER_LIMIT`` and ``UPPER_LIMIT`` into
an a2l therefore never has to decide what a missing limit means, and cannot decide it
differently from anybody else.

The **shape is a tuple of dimensions**, empty for a scalar, and it is complete even when the
description file never stated it. A measurement or a value block declares its ``dimensions``
and an axis its ``size``, but a curve and a map deliberately do not repeat the size of their
tables: they name the axes they are interpolated over, and the shape follows from those. The
demo project declares ``CurveA`` like this - no limits, no dimensions:

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
       "init": [1200, 900, 800, 750, 700, 650],
       "volatile": false
     }
   }

and the dictionary hands the backends this:

.. code-block:: json

   {
     "name": "CurveA",
     "kind": "curve",
     "datatype": "uint16",
     "description": "Calibratable curve over AxisA",
     "unit": "ms",
     "conversion": { "kind": "linear", "factor": 0.01, "offset": 0.0 },
     "limits": { "min": 0.0, "max": 655.35 },
     "shape": [6],
     "init": [1200, 900, 800, 750, 700, 650],
     "volatile": false,
     "condition": null,
     "references": { "axis": "AxisA" },
     "owner": "Controller",
     "consumers": [],
     "local": true,
     "a2l": { "export": true, "format": null, "display_identifier": null }
   }

The six points come from ``AxisA``, and the limits from the full ``uint16`` range through
the linear conversion: 65535 raw counts of 0.01 ms are 655.35 ms. The ``kind`` of the
conversion, left out of the description because a block carrying a ``factor`` can only be
linear, is spelled out. Both blocks above are folded onto fewer lines than the files
themselves use; the values are exactly the ones in ``examples/demo`` and in the dump of it.

The **owner and the consumers are worked out.** ``owner`` names the component whose
declaration was taken as the authoritative one, ``consumers`` lists the components that
declared the object as an input, and ``local`` says whether the owner keeps it to itself.
This is what lets the c backend group the definitions by owning component and emit a header
per component that contains that component's interface and nothing else, and what lets the
a2l backend build one ``GROUP`` per component - without either of them knowing anything
about scopes, ownership rules or how a disagreement between two components is settled.
Where components disagreed, the **producing component's declaration is the one that
survives**: the analysis reports the disagreement against the deviating consumer and puts
the producer's definition into the dictionary, so a backend never sees two versions of one
object.

The **condition is the producing declaration's.** A variable that only exists when a
preprocessor symbol is defined carries that expression here, which is what the c backend
wraps in ``#if`` and what the a2l backend notes in a comment, a2l having no notion of
conditional compilation.

The **objects are sorted by name** and the enumerations are collected, de-duplicated and
sorted by name as well, so that a generated file depends on the content of a project and not
on the order in which its files happened to be read. Together with the include patterns
being expanded in sorted order and the generated files carrying no time stamp, that is what
makes a regeneration without an input change produce a byte identical result - and therefore
what lets a build system skip the recompilation. The components, by contrast, keep the order
in which the project included them, and the declarations of a component keep the order the
author wrote them in, because that order is information: it is how the interface of a
component reads in its own file, and it is how it reads in its generated header.

.. note::
   ``owner`` may be ``null``, but only for a project that is already known to be
   inconsistent and is being generated anyway with ``ddd generate --force``. Every other
   field is always present.

The format field
----------------

A dumped dictionary is meant to be archived next to a delivery and read back by a later
version of DDD, possibly years later. The ``format`` field stamps the shape of the document
- currently ``1`` - and changes only when that shape changes, not with every release of the
tool.

It exists so that a later reader can say *this file is newer than I understand* rather than
misread it. DDD accepts a dictionary whose format is the one it knows or older, and refuses
one that is newer:

.. code-block:: text

   $ ddd compare baseline.json demo.ddd.json
   baseline.json#format: error[schema]: in the baseline: this dictionary is in format 2, and this DDD understands up to 1; use a newer DDD to read it
   1 error

Refusing is the only safe answer: reading the file anyway would compare a delivery against
fields this version does not know about, and quietly report every one of them as unchanged -
which is precisely the verdict that would let a broken delivery out of the door. The rule is
one-directional on purpose, so that a new DDD keeps reading the dictionaries archived by
older ones.

That is also why a field of the dictionary may keep a default the description files no longer
allow. ``volatile`` has to be stated by every definition an author writes, but the dictionary
still defaults it to ``false``, so a dictionary dumped by an older DDD still reads back and can
still be compared against, instead of a required field turning every archived document into a
file this version refuses.

.. warning::
   A dictionary is a snapshot of a project, not a description of it. ``ddd generate`` and
   ``ddd check`` read description files; the dictionary is what ``ddd compare`` reads back
   and what a foreign generator consumes. Treat it as an artefact of a build - archive it,
   do not edit it, and do not maintain a project in it.

Consuming it from another tool
------------------------------

The document is plain json, described by a published schema, and it round-trips: a
dictionary written by ``ddd dump`` and read back is the same dictionary, and a backend fed
the reloaded document produces byte identical output. Both properties are asserted by the
test suite (``tests/test_backends.py``), because they are the whole point of publishing the
contract - a third party generating from a dumped dictionary has to get what DDD would have
got.

``ddd schema dictionary`` prints the whole thing, definitions included; its top level, which
is where a consumer starts, is this:

.. code-block:: json

   {
     "additionalProperties": false,
     "description": "The resolved data of one project.",
     "properties": {
       "format": {
         "default": 1,
         "title": "Format",
         "type": "integer"
       },
       "name": {
         "maxLength": 128,
         "minLength": 1,
         "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
         "title": "Name",
         "type": "string"
       },
       "description": {
         "default": "",
         "title": "Description",
         "type": "string"
       },
       "source": {
         "default": "",
         "title": "Source",
         "type": "string"
       },
       "components": {
         "default": [],
         "items": {
           "$ref": "#/$defs/ResolvedComponent"
         },
         "title": "Components",
         "type": "array"
       },
       "objects": {
         "default": [],
         "items": {
           "$ref": "#/$defs/ResolvedObject"
         },
         "title": "Objects",
         "type": "array"
       },
       "enums": {
         "default": [],
         "items": {
           "$ref": "#/$defs/EnumConversion"
         },
         "title": "Enums",
         "type": "array"
       }
     },
     "required": [
       "name"
     ],
     "title": "DataDictionary",
     "type": "object"
   }

``additionalProperties`` is ``false`` here as it is everywhere else in DDD, so a consumer
validating against the schema finds a key it was not expecting instead of skipping it.
``enums`` carries the distinct enumerations the objects use, so a consumer that wants to
emit a type per enumeration - which is what the c backend offers its templates as
``model.enums`` - does not have to walk every object and de-duplicate them itself. The
conversions themselves are the same models the description files use, and they are documented
with the other :doc:`data contracts <data_contracts>`.

Reference
---------

The dictionary is a pydantic model like every other contract, which means it is validated
when the analysis hands it over: a bug in the front end surfaces at that boundary rather
than half way through a jinja template.

.. autopydantic_model:: ddd.ir.DataDictionary
   :field-show-constraints: False

.. autopydantic_model:: ddd.ir.ResolvedObject
   :field-show-constraints: False

.. autopydantic_model:: ddd.ir.ResolvedComponent
   :field-show-constraints: False

.. autopydantic_model:: ddd.ir.ComponentDeclaration
   :field-show-constraints: False
