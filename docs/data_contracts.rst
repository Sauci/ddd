Data contracts
==============

DDD is a chain of parts that hand data to one another: the loader reads the description
files from disk, the analysis resolves and checks what was read, and the backends turn the
result into c code and into a2l. Those parts share no domain logic at all - the c backend
has never heard of a2l, the analysis has never heard of either, and none of them reaches
into the loader. What holds the chain together instead is a small set of *data contracts*:
the exact descriptions of the json documents that enter and leave the tool, and of the
resolved data that travels between the front end and the backends.

Every contract is described exactly once, as a pydantic model in the ``ddd.models`` package,
and that one description is shared by every producer and every consumer of the data. The
loader validates a file against it, the checks read the objects it produced, ``ddd schema``
exports its json schema, and the reference at the bottom of this page is generated from it.
Two parts of DDD can therefore never disagree about a file format, and the schema an editor
validates a description file against while it is being typed is not a second, hand
maintained copy of the rules: it is derived from the rules themselves, so a field that
changes cannot leave its documentation or its schema behind.

.. uml::

   left to right direction

   package "ddd.models" {
       rectangle "ProjectFile\n(*.ddd.json)" as project_model
       rectangle "ComponentFile\n(*.ddd.json)" as component_model
       rectangle "NamingFile\n(*.ddd.json)" as naming_model
   }

   package "ddd.ir" {
       rectangle "DataDictionary\n(ddd dump)" as dictionary_model
   }

   component "loading" as loader
   component "analysis" as analysis
   component "c backend" as c_backend
   component "a2l backend" as a2l_backend
   component "compare" as comparison

   project_model --> loader
   component_model --> loader
   naming_model --> loader
   loader --> analysis
   analysis --> dictionary_model
   dictionary_model --> c_backend
   dictionary_model --> a2l_backend
   dictionary_model --> comparison

The data dictionary on the right of the diagram is the same idea applied to data that does
not have to be a file at all, and it is important enough to have :doc:`a page of its own
<data_dictionary>`. The three contracts on the left are the files a project actually
contains, and they are described in prose, with examples, under :doc:`file formats
<file_formats/index>`. What follows here is the discipline all of them are held to, and the
generated reference for every model.

Validation at the boundary
--------------------------

A description file is written by a person, in an editor, usually while thinking about
something else. It is therefore checked the moment it enters DDD, before anything reads a
single field of it, and the resolved data dictionary is validated once more before it is
handed to a backend. The point of validating at the boundary rather than at the point of use
is where the problem gets reported: a missing datatype noticed while a jinja template is
rendering says something about the template, whereas the same problem noticed at the
boundary says which file, which declaration and which field.

A violated contract is a *finding*, not a crash. The loader turns every pydantic validation
error into a diagnostic of the ``schema`` check, located at the json path that carries the
offending value, and carries on reading whatever else it can:

.. code-block:: text

   $ ddd check sensor_hub.ddd.json
   sensor_hub.ddd.json#component.declarations[0].definition.name: error[schema]: String should match pattern '^[A-Za-z_][A-Za-z0-9_]*$' (got: '2Value')
   sensor_hub.ddd.json#component.declarations[1].definition.name: error[schema]: String should have at most 128 characters (got: 'ValueXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX...)
   2 errors

Both problems are in one file and both are reported by one run, because an author who has to
run the tool once per mistake stops running the tool. ``schema`` is one of the few checks
whose severity cannot be relaxed: a file DDD cannot read has nothing further to say about
itself, so downgrading the finding would only delay the failure.

Unknown fields are rejected
---------------------------

Every model refuses keys it does not know. A key DDD silently ignored would be worse than
one it refuses, because the author would go on believing the field had an effect: a mistyped
``dimension`` instead of ``dimensions`` does not produce a smaller array, it produces a
scalar, and neither the generated code nor the a2l would ever hint at why.

.. code-block:: text

   $ ddd check controller.ddd.json
   controller.ddd.json#component.declarations[0].definition.dimension: error[schema]: Extra inputs are not permitted (got: [4])
   1 error

The same rule applies at the top level of a file: a document with neither a ``project`` nor
a ``component`` key, or with both, is refused rather than guessed at.

Identifiers are constrained
---------------------------

Anything DDD will later write into a c file or into an a2l file as a *name* - a project
name, a component name, an object name, an enum name, an enumerator, an a2l display
identifier - has to match ``^[A-Za-z_][A-Za-z0-9_]*$`` and may be at most 128 characters
long. The pattern is the c identifier rule, because a name that is not one cannot become a
variable. The length is the tighter of the two limits DDD has to satisfy: c compilers are
generous, but ASAP2 1.6.1 caps an identifier at 128 characters, and a name that cannot be
put into the a2l is of no use in a project that generates one.

Constraining a value rather than passing it through also keeps one description file from
being able to damage somebody else's build. The a2l ``FORMAT`` string is checked against
``^%\d*\.\d+$`` for exactly that reason: it is written into a quoted a2l literal, and a
quote or a backslash in it would unbalance the string so that no calibration tool would
parse the file at all - a whole delivery lost to one typo in one description. For the same
reason a preprocessor ``condition`` may not contain a line break, ``/*``, ``*/``, ``//`` or
``#``: it is emitted verbatim into ``#if`` and into the trailing ``#endif`` comment of every
generated file, and a comment marker there would close that trailer early and leave whatever
follows it as live code.

Numbers must be finite
----------------------

Every number DDD reads - a limit, an initial value, a conversion factor or offset - is
refused if it is infinite or NaN. Neither survives the trip to an output, since there is no c
literal and no a2l number for either, and NaN is actively dangerous on the way there: every
comparison against it is false, so a NaN limit passes every range check in silence instead
of failing one. Python's json reader accepts ``NaN``, ``Infinity`` and ``-Infinity`` even
though json itself does not, so the loader refuses them explicitly, before pydantic ever
sees the document:

.. code-block:: text

   $ ddd check event_logger.ddd.json
   event_logger.ddd.json: error[json-syntax]: 'Infinity' is not valid json; DDD has no representation for it
   1 error

Whole numbers are kept whole for a related reason: a number is read as an ``int`` first and
only then as a float, because the range of a 64 bit datatype does not survive a float, and a
limit rendered as 18446744073709551616 - one more than ``uint64`` can hold - is a value the
calibration tool would refuse.

Nothing changes behind a caller's back
--------------------------------------

Every contract model is frozen: once a document has been validated, no part of DDD modifies
it. The analysis therefore cannot quietly "fix up" a consumer's declaration to match the
producer's, and a backend cannot normalise something on its way into a template. Where a
derived value is needed - the limits a datatype and a conversion imply, the shape a curve
takes from its axis - it is computed into the :doc:`data dictionary <data_dictionary>`,
which is a separate document, so that the difference between what an author wrote and what
DDD concluded stays visible instead of being overwritten.

Publishing the schemas
----------------------

Because the contracts are pydantic models, their json schema is derived mechanically -
including the field documentation and the rejection of unknown properties - and
``ddd schema`` prints it:

.. code-block:: bash

   ddd schema project
   ddd schema component
   ddd schema naming
   ddd schema dictionary
   ddd schema component -o .vscode/ddd_component.schema.json

Pointing an editor at those files gives the whole team the validation and the hover
documentation of the contract while a description file is being written, which is where a
typo is cheapest to fix. Writing them out with ``-o`` keeps the line endings exactly as
generated, so a schema checked in from Windows does not differ from the same schema checked
in from linux.

Reference
---------

The following is generated from the contracts themselves. Each model carries three things,
which answer three different questions. The **field list** says what may be written and what
it means. The **json schema** says exactly what a validator will accept - the precise
pattern, length and range every field is held to - and is the fragment an editor uses. The
**entity relationship diagram** says how the models fit together, which neither of the other
two shows: that a ``Declaration`` holds exactly one of the six kinds of data object, and that
the same ``Limits`` and ``A2lObjectOptions`` hang off every one of them.

.. Models carrying an identifier field switch the rendered constraint list off. The
   constraint would be written into the page as ``pattern = ^[A-Za-z_][A-Za-z0-9_]*$``,
   which docutils reads as two references to targets that do not exist ('A-Za-z_' is a
   valid reference name followed by an underscore), and the documentation is built with
   warnings as errors. The same information is in the json schema shown below each model.

Project description
~~~~~~~~~~~~~~~~~~~

.. autopydantic_model:: ddd.models.ProjectFile

.. autopydantic_model:: ddd.models.Project
   :field-show-constraints: False

Software component description
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autopydantic_model:: ddd.models.ComponentFile

.. autopydantic_model:: ddd.models.Component
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Declaration

Structured datatype description
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :doc:`types file <file_formats/types>`. A member states which shape it has and carries only
the keys that shape needs; what it never carries is a bit position or an offset, because c leaves
both to the compiler.

.. autopydantic_model:: ddd.models.TypesFile

.. autopydantic_model:: ddd.models.StructType
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Member
   :field-show-constraints: False

Data objects
~~~~~~~~~~~~

The ``definition`` of a declaration is a tagged union discriminated on ``kind``, and ``kind``
is required on every definition - a measurement states ``"kind": "measurement"`` like every
other. A defaulted discriminator would leave a bare definition matching more than one variant
in the published schema, which an editor validating the file reports as an ambiguity; stating
it keeps the schema and the loader in agreement. :class:`ddd.models.DataObject` holds what all six
kinds have in common, and the six models after it document only what their own kind adds;
the json schema shown with each of them is nevertheless the complete document a declaration
of that kind is validated against. Where a field carries an alias, the alias is the key that
belongs in the json file - ``volatile``, not ``is_volatile``.

.. autopydantic_model:: ddd.models.DataObject
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Measurement

.. autopydantic_model:: ddd.models.Parameter

.. autopydantic_model:: ddd.models.ValueBlock

.. autopydantic_model:: ddd.models.Axis

.. autopydantic_model:: ddd.models.Curve
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Map
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Limits

.. autopydantic_model:: ddd.models.A2lObjectOptions

Conversions
~~~~~~~~~~~

The ``conversion`` of a data object is a second tagged union, again discriminated on
``kind``, and again ``kind`` may be left out when the shape of the block makes it
unambiguous: a block carrying ``enumerators`` or a ``name`` is an enum, one carrying
``factor`` or ``offset`` is linear, and an empty one is the identity.

.. autopydantic_model:: ddd.models.IdentityConversion

.. autopydantic_model:: ddd.models.LinearConversion

.. autopydantic_model:: ddd.models.EnumConversion
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Enumerator
   :field-show-constraints: False

Naming convention
~~~~~~~~~~~~~~~~~

A naming convention is a third kind of ``*.ddd.json`` file, pointed at by the ``naming`` key
of a project rather than listed among its ``includes``. It describes a name as an ordered
sequence of segments, which is what lets DDD point at the part of a name that is wrong and
complete a name that is half typed; see :doc:`naming conventions <naming_conventions>`.

.. autopydantic_model:: ddd.models.NamingFile

.. autopydantic_model:: ddd.models.NamingConvention

.. autopydantic_model:: ddd.models.Segment
   :field-show-constraints: False

.. autopydantic_model:: ddd.models.Token
