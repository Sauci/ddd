Templates
=========

The c code DDD generates is rendered from templates the *project* provides. ``ddd generate
c`` and ``ddd generate all`` therefore take a required ``-t/--template-dir``: there is no
built-in default and there is no fallback, so a run that leaves the option out is a usage
mistake rather than a run that silently produces somebody else's idea of c code. Only ``ddd
generate a2l`` goes without, because it renders no c at all.

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen
   ddd: the c sources are part of this run, so -t/--template-dir is required

Why the templates belong to the project
---------------------------------------

What a variable is called, what type it has, which component owns it and which components
read it - all of that follows from the description files, and DDD resolves and checks it.
None of what a c file *looks like* follows from it. Whether the file opens with a banner and
what that banner says, what a comment above a declaration looks like, whether the
include guard is ``DDD_GLOBALS_H`` or a name your coding standard derives from the module
number, whether the file is called ``ddd_globals.c`` or ``proj_data.c``, in which order the
sections appear, how deep the indentation is - every one of those is a house style, settled
per project, usually by a coding standard that is older than DDD and applies to the
hand-written code as well.

A generator that decided them would impose the habits of the project it was first written
for on every project after it. The consequence is familiar: either the generated files are
patched after each run, which makes regeneration unsafe, or the generator grows one option
per habit until it carries a flag for the guard, one for the comment style, one for the
banner text and one for each file name. DDD instead supplies the resolved data and lets the
project write the file, so a project that wants a particular documentation convention writes
it, a project that wants its MISRA deviation record above every ``volatile`` writes that, and
neither has to argue
with the tool or with the other.

What stays with DDD is everything that is not a matter of taste: reading and validating the
descriptions, resolving producers against consumers, computing shapes and limits, ordering
the objects so that a diff stays readable, and defusing any text that ends up inside a
comment. The templates only spell out the result. This is also why there is no option for
naming the generated files: a project renames one by renaming its template, which is one
mechanism instead of a second one bolted on top of it.

The a2l file is not templated
-----------------------------

Only the c backend takes a template directory. The a2l generator is internal and has no
template option at all, because the structure of an ASAP2 file is dictated by ASAM rather
than by a project: its readers are measurement and calibration tools that implement the
standard, and a house style in that file is not a preference, it is a file the tool refuses.
The distinction is the whole argument on this page in one line - the c code is read by your
developers, so your project decides how it reads; the a2l file is read by a program, so the
standard decides. What the standard leaves to the target - the ``A2ML``, an ``EPK``, a
``MEMORY_SEGMENT`` - is a text file of the project's own, pasted at the head of the module by
``--a2l-module-fragment``; see :ref:`the a2l's module fragment <a2l-module-fragment>`. See
:doc:`generated artefacts <generated_artefacts>` for what the a2l backend produces.

Why jinja2
----------

The templates are `jinja2 <https://jinja.palletsprojects.com/>`_ templates. It is the
template engine most people who will edit them have already met, it is documented well
enough that nobody has to read DDD's source to use it, and it is text-oriented rather than
markup-oriented: a template is the c file you want, with holes in it, which is what makes a
template reviewable by the same people who review the c code.

The environment DDD renders in is set up for source files rather than for web pages.
Autoescaping is off, since escaping html entities into c would corrupt it; ``trim_blocks``
and ``lstrip_blocks`` are on, so a ``{% for %}`` on a line of its own does not leave a blank
line and an indented ``{% if %}`` does not leave its indentation behind; the trailing newline
of a template is kept, and a rendered file that does not end in one gets one added.
Undefined values are strict, which is the subject of a section of its own below.

A template directory is code
----------------------------

That environment is an ordinary ``jinja2.Environment`` and not a sandboxed one, so a template
runs with the privileges of the run that renders it: ``ddd generate c -t tools/templates`` is
running what is in ``tools/templates``, exactly as naming a :doc:`plugin <plugins>` runs the
plugin's module. The plugin rule is easy to accept - a plugin is obviously python - and this
one is easy to miss, because a template reads as data: it is the c file you want with holes
in it, and the holes are expressions the engine evaluates. Both are the same bargain, and it
is the ordinary one for a build: the templates of a repository are as much part of what
``cmake``, ``make`` or a ci job executes as its scripts are. Review a template directory the
way you review a plugin, point ``-t`` at one you would run a build out of, and treat a
template arriving from elsewhere as you would treat a patch.

How the template directory is read
----------------------------------

Four rules decide what is rendered and what the result is called. They are deliberately
mechanical, because a build system has to derive the set of generated files from the template
directory alone, without running the tool first - which is what lets ``ddd_generate`` in the
:doc:`cmake integration <build_integration>` declare the outputs of the generation step
before it has ever run.

#. Every ``*.jinja2`` file directly inside the template directory is rendered.
#. The generated file is named like its template without the ``.jinja2`` extension, so
   ``ddd_globals.c.jinja2`` produces ``ddd_globals.c``. The template a given file came out of
   is therefore always identifiable from the file name alone.
#. A template whose name starts with an underscore is a **helper**: it produces no file of
   its own and exists to be imported by the others.
#. A template whose name contains ``{component}`` is rendered **once per component**, with
   the placeholder replaced by the component name.

The example directory shipped with DDD contains one template of each kind:

.. code-block:: text

   templates/
       _macros.jinja2
       ddd_globals.c.jinja2
       ddd_globals.h.jinja2
       ddd_types.h.jinja2
       {component}.h.jinja2

Applied to the demonstration project in ``examples/demo``, which is made of the four
components ``Controller``, ``SensorHub``, ``UserInterface`` and ``EventLogger``, those five
templates produce the following:

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - template
     - generated file
   * - ``_macros.jinja2``
     - nothing - a helper, imported by the four others
   * - ``ddd_globals.c.jinja2``
     - ``ddd_globals.c``
   * - ``ddd_globals.h.jinja2``
     - ``ddd_globals.h``
   * - ``ddd_types.h.jinja2``
     - ``ddd_types.h``
   * - ``{component}.h.jinja2``
     - ``Controller.h``, ``SensorHub.h``, ``UserInterface.h``, ``EventLogger.h``

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen -t examples/templates
   <project>: info[byte-order-defaulted]: no --byte-order and no --image was given, so the a2l states MSB_LAST, little endian, as a default; a big endian target needs --byte-order big (the BYTE_ORDER of ddd_generate in cmake), and an image states its own
   1 info
   wrote       build/gen/ddd_globals.c (created)
   wrote       build/gen/ddd_globals.h (created)
   wrote       build/gen/ddd_types.h (created)
   wrote       build/gen/Controller.h (created)
   wrote       build/gen/SensorHub.h (created)
   wrote       build/gen/UserInterface.h (created)
   wrote       build/gen/EventLogger.h (created)
   wrote       build/gen/DemoDevice.a2l (created)

The a2l file at the end comes from the other backend and is unaffected by the templates. A
directory in which nothing is left to render - one holding only helpers, for instance - is
refused with a message saying so, rather than quietly producing no c code at all.

What a template receives
------------------------

A template is rendered with a small, fixed context, and everything else is reached by
traversing it. All of it is a c-shaped view of the resolved :doc:`data dictionary
<data_dictionary>` - the same data ``ddd dump`` publishes, with the resolving already
done: producers matched, limits derived, conditions validated, objects ordered. A template
reads answers, it never computes them; a tool that wants the data without the c slant
reads the dictionary itself.

``model``
   The whole project, prepared for c. Always present.

``filename``
   The name of the file this rendering produces, relative to the output directory:
   ``ddd_globals.c``, or ``Controller.h`` for a per-component rendering. It is passed in
   rather than left to the template to reconstruct, so that a banner can print the name of
   the file it is in without knowing which of the two rules produced it.

``header``
   Present **only** in a ``{component}`` template: the component being rendered. A template
   without the placeholder never sees it, which is what makes the mistake of iterating over
   the components inside a per-component template fail immediately instead of silently
   writing every component into every file.

The model
~~~~~~~~~

``model`` carries the project as flat sequences, already ordered and already safe to print:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - attribute
     - what it holds
   * - ``model.project``
     - The project name, or the component name when a single component is generated.
   * - ``model.source``
     - The name of the description file the dictionary was read from, for the banner.
   * - ``model.generator``
     - The tool and version that produced the file, such as ``ddd 0.11.0``.
   * - ``model.constants``
     - One entry per :doc:`declared constant <file_formats/constants>`, in name order, each
       with ``.name``, ``.value``, ``.literal`` and ``.description``; empty when the project
       declares none. Offered so the template can emit them however the house style spells
       one - the example templates write each as a ``#define`` in the types header - because
       an array dimensioned by a constant renders its ``array_suffix`` with the constant's
       *name*, which therefore has to be declared before the first array that uses it.
       ``.value`` is the number and nothing else, for a template that does its own
       formatting; ``.literal`` is that value as a c literal, which is what to render where
       the value is simply to be emitted. Which literal depends on the value's range alone,
       and never on whether a narrower or an unsigned type would hold it:

       * from ``-2147483648`` to ``2147483647`` it is written bare, ``5`` as ``5``. The most
         negative of them is the unary minus applied to ``2147483648``, which c types as a
         ``long`` or a ``long long`` and not as an ``int``;
       * anywhere else up to the 64 bit signed ends it takes ``LL``: ``2147483648`` renders
         as ``2147483648LL``, ``4294967295`` as ``4294967295LL`` although an ``unsigned int``
         holds it, and ``-2147483649`` as ``-2147483649LL``;
       * ``-9223372036854775808`` renders as ``(-9223372036854775807LL - 1)``, because c has
         no negative literal and the unary minus would be applied to a literal too large for
         any signed type;
       * above ``9223372036854775807`` it takes ``ULL``, ``18446744073709551615`` as
         ``18446744073709551615ULL``, because a compiler otherwise reads it as unsigned and
         says so;
       * a number with a fraction is a ``double`` literal, as it looks.
   * - ``model.enums``
     - One entry per enum conversion, each with ``.name`` and ``.enumerators``; an
       enumerator has ``.name``, ``.value`` and ``.description``.
   * - ``model.structures``
     - One entry per :doc:`declared structure <file_formats/types>`, each after every
       structure it nests, with ``.name``, ``.comment`` and ``.members``. A member has
       ``.name``, ``.c_type``, ``.datatype``, ``.array_suffix``, ``.bits`` - the width of a
       bitfield, or nothing - ``.comment`` and ``.declaration``, the last being the member as
       it goes into a ``typedef struct``, ``uint16_t value`` or ``uint8_t ready : 1``,
       without the semicolon. Empty when the project declares no structure; the example
       templates emit each as a ``typedef struct`` in the types header, after the enums.
   * - ``model.groups``
     - The objects to be *defined*, grouped by owning component: ``.name``,
       ``.description``, ``.measurements``, ``.calibration`` and ``.variables``, the last
       being the two lists one after the other. A component owning nothing has no group, and
       objects no component declares as an output end up in a final group called
       ``<unresolved>``.
   * - ``model.sections``
     - The placed objects grouped per :doc:`linker section <file_formats/sections>`, one
       entry per section with ``.name`` and ``.objects``, strictest alignment first so that
       data of one section packs without padding. A placed object is in its component's group
       as well, so a template that walks ``model.groups`` and ``model.sections`` and defines
       every object it meets defines it twice: take the definitions from ``model.groups`` and
       the placement from here. An object without a ``section`` is in its group only, and the
       sequence is empty when the project places nothing.
   * - ``model.headers``
     - One entry per component, in project order, whether or not the component declares
       anything. These are the interfaces, described below.
   * - ``model.needs_stdint``, ``model.needs_stdbool``
     - Whether any datatype of the project needs that standard header, for a type header that
       includes it only when something uses it. The shipped example renders
       ``model.needs_stdbool`` and includes ``<stdint.h>`` unconditionally: every other
       generated header includes the type header and nothing else, so a type header that is
       empty - a project whose objects are all floating point, or one that declares no object
       at all - leaves those headers empty too, and ``-Wpedantic`` refuses an empty
       translation unit.
   * - ``model.external_includes``
     - The headers of the :doc:`external types <file_formats/types>` in use, deduplicated and
       sorted by spelling, each ready to paste after ``#include``: ``"my_driver.h"`` with its
       quotes for the quoted form, ``<os_types.h>`` as written for the angle form. Empty when
       no structure has an external member; the example templates emit them in the types
       header after the standard includes, before the first structure that needs them.
   * - ``model.guard(*parts)``
     - A normalised include guard, e.g. ``model.guard("ddd", "globals")`` for
       ``DDD_GLOBALS_H``: the parts are joined, upper cased, a run of anything that is not a
       letter or a digit becomes one underscore, the underscores at either end are dropped,
       a leading digit is prefixed, and ``_H`` is appended.
       Offered rather than imposed - a template that has its own convention writes it out.
   * - ``model.options``
     - What the command line let the caller decide, which for the c backend is nothing:
       everything that used to be an option is now a property of the template you write.

The two groupings answer two different questions, which is why both exist. ``model.groups``
is about *ownership* and drives the file that allocates the memory; ``model.headers`` is
about *visibility* and drives the file each component includes.

A variable
~~~~~~~~~~

The entries of ``.measurements``, ``.calibration`` and ``.variables`` are the objects
themselves:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - attribute
     - what it holds
   * - ``.name``
     - The object name, exactly as it appears in the description.
   * - ``.definition``
     - The complete definition without the trailing semicolon, qualifier, type, declarator
       and initialiser included: ``volatile uint16_t Speed[4] = { ... }``, or
       ``const volatile uint16_t Gain = 3U`` for calibration data the description declares
       volatile. The template adds the semicolon, which is what lets it put something between
       the two.
   * - ``.declaration()``
     - The matching ``extern`` declaration, again without the semicolon, carrying the same
       qualifier the definition does. It takes no argument: a ``const=`` keyword, which
       ``--const-inputs`` needed, was removed in 0.12.0 and is refused in a sentence saying so.
   * - ``.comment``
     - The description, the unit in square brackets and, for calibration data, a note saying
       what the object is and what it is dimensioned by - or nothing at all if the
       description says nothing. It is plain text without comment markers, already collapsed
       to one line and already defused, so that a ``*/`` in a description cannot end the
       comment the template opens around it and a ``/*`` cannot open one inside it - which
       ``-Wcomment``, and so ``-Wall``, reports.
   * - ``.condition``
     - The preprocessor condition the object is guarded by, or nothing. It is validated on
       the way in so that it is safe to emit verbatim into both ``#if`` and the ``#endif``
       trailer.
   * - ``.section``
     - The name of the :doc:`linker section <file_formats/sections>` the producing
       declaration placed the object in - the name alone, as the linker script spells it -
       or nothing when the object is unplaced. How a placement is spelled in c, an
       ``__attribute__`` or a pragma, is the template's decision; the example templates
       write the GCC attribute between the declarator and the initialiser.
   * - ``.owner``, ``.consumers``
     - The component that produces the object and the components that read it, for a comment
       that says where a value comes from.
   * - ``.unit``
     - The physical unit, exactly as the a2l states it: empty when the object has none, and
       for a structured variable, whose members state their own.
   * - ``.conversion``
     - What turns the raw value into the physical one, as the a2l states it, or nothing for a
       structured variable. ``.conversion.kind`` is ``identity``, ``linear``, ``enum`` or
       ``string``. A ``linear`` one has ``.conversion.factor`` and ``.conversion.offset``
       (physical = raw * factor + offset), each also as a c literal in
       ``.conversion.factor_literal`` and ``.conversion.offset_literal``, and
       ``.conversion.coefficients``, the six numbers of the a2l's rational function
       (``0 1 -offset 0 0 factor``) with ``.conversion.coefficient_literals`` beside them. An
       ``enum`` one has ``.conversion.name`` and ``.conversion.enumerators``, each with
       ``.name``, ``.value`` and ``.description``: the enum's entries in ``model.enums``, so an
       object whose own copy documents less states the copy the types header declares. A field
       a kind does not have is empty.
   * - ``.limits``
     - The range the a2l states: the limits the description states, or what the datatype and
       the conversion imply. ``.limits.min`` and ``.limits.max``, each also as a c literal in
       ``.limits.min_literal`` and ``.limits.max_literal``; nothing for a structured variable.

``.kind``, ``.c_type``, ``.datatype``, ``.array_suffix``, ``.qualifier``, ``.initializer``,
``.dimensions``, ``.point_counts`` and ``.extensions`` are there as well, for a template that
would rather lay the declaration out itself than take ``.definition`` whole - ``.extensions``
being the resolved block of every :doc:`plugin <plugins>` the project loads, keyed by plugin
name, for a template that renders what a plugin decided. ``.c_type`` and ``.datatype`` are the
same type in two vocabularies:
the ISO spelling (``uint16_t``) that ``.definition`` and the example templates use, and the
description's own (``uint16``). A project whose platform header already provides the
description's names - AUTOSAR's ``Platform_Types.h`` spells them exactly - renders
``.datatype`` and needs no mapping in its templates; for a structured variable, and for a
structure member of another structure or of an external type, the two fields agree, because
that spelling was the project's own to begin with. ``.array_suffix`` spells each dimension as the project spells it - a
dimension stated as a :doc:`declared constant <file_formats/constants>` renders as that
name, ``[PRESSURE_CELLS]``, in ``.definition`` and ``.declaration(...)`` alike; for a table
whose point counts are stored ``leading``, it is instead the flat suffix that has room for
the counts ahead of the values, such as ``[1 + (8)]`` for an axis of 8 points. ``.dimensions`` is the shape ``.array_suffix`` was rendered from, in declaration
order and in the project's own spelling, so a template computing anything from the shape does
not have to parse the suffix back apart. ``.point_counts`` is the counts such a table stores
ahead of its values, in storage order - x, then y - and spelled like ``.dimensions``; empty
for every object that stores none. ``.initializer`` lays its braces out over the resolved
numeric shape - or, again for a table with leading counts, over the counts followed by the
values, which is always present even when the description gives no ``init``, since the
counts can never be left to implicit zero initialisation. ``.qualifier`` is derived rather than stored, from the two answers a
declaration can give about who writes the object: ``.constant`` is true for calibration data,
which the software never writes and which is therefore generated ``const``, and ``.volatile``
is what the description states on the definition, on every kind, to say that something
outside the compiled code - an interrupt, another core, a calibration tool - changes the
value while it runs. Either, both or neither may hold, and ``.qualifier`` is simply the one
or two keywords that follow, with their trailing space. A template that composes its own
declaration is better off testing the two booleans than matching text against the string they
produce, and they are also what a MISRA deviation record above every ``volatile`` object, or
a section attribute on the tunable data alone, is written from.

``.unit``, ``.conversion`` and ``.limits`` are the values the a2l is written from, taken from
the same place, so a template that writes a scale macro, a table or a header of its own cannot
disagree with the a2l. The example ``{component}.h`` template uses them: beside each input and
output whose conversion is ``linear`` it writes two macros, named after the variable with a
double underscore and a suffix::

   extern int16_t Speed;  /* produced by Prod */
   #define Speed__FACTOR (0.1)
   #define Speed__OFFSET (-40.0)

A rescale of the conversion changes that header, so every file that includes it is compiled
again; a reader that multiplies by ``Speed__FACTOR`` follows the rescale, and one that wrote
the number itself does not, which no check of the descriptions can see. The names carry a
double underscore because DDD refuses one in every name a project writes - a variable, a type,
a constant, an enumerator - so no name the generated c holds can be one of them; the values
are parenthesised so that a negative offset cannot join the sign in front of it. The names are
sound C, which reserves a name that begins with two underscores, or with one and a capital
letter, but not one that holds two further in. C++ reserves that too, so a C++ unit including
the header meets ``Speed__FACTOR`` as a name reserved to the implementation; a project whose
readers are C++ renames the macros in the two lines of the ``scale`` macro of
``_macros.jinja2`` that spell them. The example
writes nothing for any other kind of conversion: an ``identity`` and a ``string`` have no
scale, and the ``typedef enum`` of an ``enum`` is already in the types header. A project whose
templates were copied before this one keeps the headers it had, and gains the macros by
copying the two lines and the macro of ``_macros.jinja2``.

A component header
~~~~~~~~~~~~~~~~~~

``header``, and every entry of ``model.headers``, describes the interface of one component:
``.name``, ``.description`` and ``.guard``, plus the three lists ``.outputs``, ``.inputs``
and ``.locals`` and the convenience ``.is_empty``, which is true when the component declares
nothing and lets the template say so rather than emit a header that is only a guard.

``.guard`` is ``DDD_COMPONENT_CONTROLLER_H`` for a component called ``Controller``. The word
``component`` in the middle is deliberate: without it a component named ``types`` would
define ``DDD_TYPES_H`` before ``ddd_types.h`` was ever included, and the whole type header
would preprocess away.

A name with an underscore at an edge cannot take that form, which drops the underscore and would
give ``Valve`` and ``Valve_`` one guard, so that a file including both finds the second header
preprocessed away. Such a name has a prefix of its own, and the name without its edge
underscores after it: ``DDD_COMPONENTS_TRAILING_VALVE_H`` for ``Valve_``,
``DDD_COMPONENTS_LEADING_VALVE_H`` for ``_valve`` and ``DDD_COMPONENTS_BOTH_VALVE_H`` for
``_valve_``. No guard holds a double underscore, which C++ reserves wherever it stands and
DDD refuses in every name a project writes. Every other name keeps the guard it had.

Each entry of the three lists is a declaration rather than a bare object, because the same
variable is declared differently in different headers:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - attribute
     - what it holds
   * - ``.line``
     - The complete declaration, semicolon included, qualified as the definition is. Most
       templates need nothing else.
   * - ``.condition``
     - The preprocessor condition of this declaration, or nothing.
   * - ``.variable``
     - The object behind the declaration, with everything the previous table lists - which is
       how a header comments a declaration with ``.variable.comment`` or names its producer
       with ``.variable.owner``.

``.const`` of a header entry, which said whether ``--const-inputs`` had added a ``const``, was
removed in 0.12.0 with the option and is refused in a sentence saying so; ``.line`` is the
declaration.

Helpers, and what a subdirectory is for
---------------------------------------

Four generated files that all begin with the same banner should describe that banner once.
That is what a helper template is for: a name starting with an underscore renders nothing on
its own and exists to be imported. The example set keeps its banner in ``_macros.jinja2``,
and every other template opens with:

.. code-block:: jinja

   {% import "_macros.jinja2" as macros %}
   {{- macros.banner(filename, model) }}

The macro takes what it needs as arguments, which is why the plain ``import`` is enough here.
A helper that reads ``model`` or ``filename`` directly instead of receiving them has to be
imported ``with context``, the standard jinja2 rule: an import without it gives the imported
template a context of its own, in which those names do not exist.

A template in a *subdirectory* of the template directory is never rendered, but it can still
be imported and included. Only the top level is scanned, so a project is free to keep
fragments, per-target variants or a vendor's original copies below the directory without
each of them turning into a generated file it has to explain.

A mistake in a template stops the run
-------------------------------------

Undefined names are strict. Reading an attribute that does not exist - ``model.grops`` for
``model.groups``, ``variable.commment`` for ``variable.comment`` - raises instead of
rendering as an empty string, and the run ends with one line naming the template, the line
and the attribute, and exit status 2 - a usage error, since the template is the caller's:

.. code-block:: text

   ddd: cannot render template 'ddd_globals.c.jinja2', line 14: 'ddd.backends.c.model.CodeModel object' has no attribute 'grops'

This is worth the noise. The alternative, which is jinja2's default, is that the typo
produces nothing at all: the loop body disappears, the file is generated, the build succeeds,
and a variable is missing from a header that everybody trusts. A failure at generation time
is read by the person who just edited the template; a variable silently missing from an
interface is found much later by somebody else.

How the files reach the disk
----------------------------

Every generated file is written as utf-8 with LF line endings and no byte order mark, on every
platform. Descriptions carry units and prose in any language, so utf-8 is the only sane
choice, and fixed line endings mean that a file generated on Windows and the same file
generated in a linux container are byte for byte identical - which matters as soon as
generated code is compared across machines or checked in. The one exception is not a
template's to make: the a2l, which no template renders, opens with a byte order mark, because
its own format has no other way of stating an encoding
(:doc:`generated_artefacts`).

A file whose content has not changed is left untouched rather than rewritten, so its
timestamp does not move and the compilation of everything that includes it is not triggered
again. Regenerating a project that has not changed therefore reports:

.. code-block:: text

   $ ddd generate all examples/demo/demo.ddd.json -o build/gen -t examples/templates
   <project>: info[byte-order-defaulted]: no --byte-order and no --image was given, so the a2l states MSB_LAST, little endian, as a default; a big endian target needs --byte-order big (the BYTE_ORDER of ddd_generate in cmake), and an image states its own
   1 info
   unchanged   build/gen/ddd_globals.c
   unchanged   build/gen/ddd_globals.h
   unchanged   build/gen/ddd_types.h
   unchanged   build/gen/Controller.h
   unchanged   build/gen/SensorHub.h
   unchanged   build/gen/UserInterface.h
   unchanged   build/gen/EventLogger.h
   unchanged   build/gen/DemoDevice.a2l

Getting started
---------------

Start from the example templates rather than from an empty directory. They are shipped with
the tool, and their location is printed by the tool itself rather than guessed, because a
project may be built against several installations:

.. code-block:: text

   $ ddd templates-dir
   /home/you/ddd/examples/templates

That is what a source checkout answers; an installed wheel answers with the copy inside the
package - ``/home/you/.venv/lib/python3.13/site-packages/ddd/templates``.

Copy that directory into the project, next to the description files or wherever the coding
standard says generated-code templates live, and check it in - it is source code of the
project now:

.. code-block:: bash

   cp -r "$(ddd templates-dir)" tools/ddd_templates
   ddd generate all project.ddd.json -o build/gen -t tools/ddd_templates

Then adapt. Rename a template to rename the file it produces, edit the banner, change the
comment markers, replace ``model.guard(...)`` with whatever your standard asks for, delete a
template whose output the project does not want and add one for output it does. Nothing
refers back to the copy that was taken: ``ddd templates-dir`` is a starting point, never a
fallback. In a cmake build the directory is passed to ``ddd_generate`` as its required
``TEMPLATE_DIRECTORY``; see :doc:`build integration <build_integration>`.

The example templates
---------------------

.. literalinclude:: ../examples/templates/_macros.jinja2
   :language: jinja
   :caption: _macros.jinja2 - the shared banner, imported by every other template

.. literalinclude:: ../examples/templates/ddd_types.h.jinja2
   :language: jinja
   :caption: ddd_types.h.jinja2 - the standard includes, the constants, the enum and structure typedefs

.. literalinclude:: ../examples/templates/ddd_globals.c.jinja2
   :language: jinja
   :caption: ddd_globals.c.jinja2 - the single definition of every global variable

.. literalinclude:: ../examples/templates/ddd_globals.h.jinja2
   :language: jinja
   :caption: ddd_globals.h.jinja2 - the declarations that definition file is compiled against

.. literalinclude:: ../examples/templates/{component}.h.jinja2
   :language: jinja
   :caption: {component}.h.jinja2 - the interface header, rendered once per component

A link may drop a definition
----------------------------

Compiling the definitions as one unit and linking it into the image keeps them out of an
archive's selective pull, but not out of the linker's collection of sections. A link with
``--gc-sections`` drops a definition no code references, with or without ``-fdata-sections``,
and an object nobody but the calibration tool reads goes with it: the a2l then
carries its object at address 0 or, given the image with ``--image``, reports it
``address-missing``. Linking the demo this way gave the same result on this host with
``-fdata-sections`` and without it.

The example template ``ddd_globals.c.jinja2`` puts ``DDD_RETAIN`` before every definition, and
it is empty unless the project defines it, so that the c is what it was without it. On ELF a
project that links with ``--gc-sections`` defines it as ``__attribute__((used, retain))``, which
with gcc 15.2.0, binutils 2.46 and ``-fdata-sections`` kept every object of the demo where the
empty macro kept none, and ``used`` alone kept none; it needs a gcc that knows ``retain`` and a
binutils that keeps such a section, and the definition goes on the compiler's command line
(``-D``) or in a header the build includes first. On PE gcc ignores ``retain``, so the macro
does not keep a definition there, and a reference to the object from code that is linked, or a
linker script that keeps the section, does. A project that writes its own definition template
spells the same thing in it.

.. note::
   How these examples comment the generated code is not a recommendation. A different
   documentation convention, a MISRA deviation record, a traceability tag or no comment at
   all is exactly the kind of decision the
   templates exist to leave to the project.
