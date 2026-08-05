Consistency checks
==================

The global variables of a component based project are declared in as many files as there are
components, and nothing in the c language ties those declarations together: a component that
reads ``SharedValue`` as an unscaled ``uint16`` and a component that writes it as an ``sint16``
in percent with a factor of 0.5 compile perfectly well, link without a word, and produce a
value that is wrong by a factor of two - or by 65536, once the sign bit travels. The
disagreement is invisible to the compiler because each translation unit only ever sees its own
opinion of the variable. DDD sees all of them, because every declaration passes through it
before a single line of c is written, and that is what the consistency checks are for: they
are the only place in the tool chain where "these two components do not mean the same thing by
this name" can still be said cheaply, on a source file, with a location, instead of expensively,
at link time or in the calibration lab.

The same checks run on every command that resolves a project - ``check``, ``generate``, ``list``
and ``dump`` - so the artefacts can never be generated from inputs that were not checked.
``ddd generate`` refuses to write anything while an error is outstanding, unless it is told to
with ``--force``:

.. code-block:: text

   $ ddd generate examples/inconsistent/project.ddd.json -o build/gen -t examples/templates
   ...
   4 errors, 1 warning
   $ echo $?
   1

What a check is
---------------

A check is a rule with a **stable identifier** and a **default severity**. The identifier is
the kebab-case name that appears in every finding - ``multiple-producers``,
``definition-mismatch``, ``unused-output`` - and it is part of the tool interface rather than
an implementation detail: a build script pins it in a severity override, a ci job greps for it,
a code review discusses it. Identifiers therefore do not change once they have been published.
A check may be added in a later release, and the wording of a message may improve, but a name
a project has written into its build files keeps meaning what it meant.

The authoritative list is the one the tool prints itself, which is also how the tables further
down should be read after a DDD upgrade:

.. code-block:: text

   $ ddd checks
   file-not-found         error    a referenced file does not exist (fixed)
   json-syntax            error    a file is not valid json (fixed)
   file-kind              error    a file is neither a project nor a component description (fixed)
   file-extension         error    a description file is not named '*.ddd.json'
   schema                 error    a file does not match the DDD contract (fixed)
   include-cycle          error    projects include each other recursively (fixed)
   include-empty          error    an include pattern matches no file
   duplicate-component    error    two different files declare the same component name
   duplicate-type         error    two different files declare the same type name
   ...

The ``(fixed)`` marker means the severity of that check cannot be changed; the reason is in
`Severity policy`_ below.

Anatomy of a finding
~~~~~~~~~~~~~~~~~~~~

Every finding is one line, in a shape an editor or a log parser can pick apart, followed by
zero or more indented notes:

.. code-block:: text

   $ ddd check examples/inconsistent/project.ddd.json
   examples/inconsistent/component_b.ddd.json#component.interface[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
       note: examples/inconsistent/component_a.ddd.json#component.interface[0]: also written here
   ...

The part before the first colon is the location: the path of the description file, relative to
the working directory when it lies below it, followed by ``#`` and a dotted json pointer into
the document. The pointer is what makes a finding actionable in a project of a hundred
components - ``component.interface[0]`` is the first entry of the ``interface`` array,
and ``component.interface[0].definition`` narrows it further to the definition object inside
it. A finding about the file as a whole rather than about a place inside it carries a line and
a column instead, because for a file that does not parse there is no pointer to give:

.. code-block:: text

   $ ddd check broken.ddd.json
   broken.ddd.json:4:22: error[json-syntax]: Expecting value
   1 error

Then comes ``severity[check]``, and then the message. The notes are the second half of the
story: almost every disagreement is a disagreement *between two places*, and a finding that
pointed at only one of them would send its reader hunting for the other. The note therefore
names the declaration the finding was measured against - "also written here", "reference
declaration", "declared local here" - with a location of its own. The ``naming`` check uses the
same mechanism to underline the part of a name that is wrong:

.. code-block:: text

   $ ddd check project.ddd.json
   sensing.ddd.json#component.interface[0].definition.name: error[naming]: 'vl' is not a known role (val, flg, cnt, par, axs, crv, map, tbl) - did you mean 'val'?
       note: vl_InletTemperature_flt
             ^^

Findings are printed errors first, then warnings, then information, and within one severity by
file and by position in the file, so that fixing one finding does not shuffle the others around
in the next run. The run ends with a one line summary (``4 errors, 1 warning``) or, when a
project is entirely clean, with a statement of what was checked:

.. code-block:: text

   $ ddd check examples/demo/demo.ddd.json
   ok: 20 variables in 4 components are consistent

All of this goes to **stderr** - every finding, every note and the closing summary or ``ok:``
line. Stdout is reserved for whatever the command was asked to produce: the dictionary of
``ddd dump``, the table of ``ddd list``, the schema of ``ddd schema``. The two streams never
carry each other's content, which is what makes
``ddd dump project.ddd.json > baseline.json`` safe - the findings cannot end up inside the
artefact.

Severity policy
---------------

Not every project is at the same point in its life. A project being migrated onto DDD starts
with descriptions that are incomplete on purpose; a component being developed on its own cannot
see the components that produce its inputs; a project approaching a release wants the build to
fail on what was merely a warning last month. Each check therefore carries a default severity
which the project can change, per run, with ``-W`` (long form ``--severity``), repeatable:

.. code-block:: bash

   ddd check project.ddd.json -W unused-output=info
   ddd check project.ddd.json -W missing-producer=ignore -W unused-output=ignore
   ddd check project.ddd.json --strict

The four levels are:

``error``
   The finding fails the run: the exit code becomes 1, and ``ddd generate`` writes nothing.

``warning``
   The finding is printed and counted, but the run still succeeds. Something is suspect and a
   human should look at it.

``info``
   The finding is printed and counted, and nothing else happens. Useful to keep a rule visible
   without letting it interrupt anybody.

``ignore``
   The finding is not produced at all. It appears neither in the text output, nor in the json
   output, nor in the summary counts.

``--strict`` reports as an error everything that would be reported as a warning. It is applied
*after* the ``-W`` overrides, on the effective severity, and that order is what makes the two
options composable: a project can turn its warnings into errors and still exempt the one check
it has consciously decided to live with.

.. code-block:: text

   $ ddd check examples/inconsistent/project.ddd.json --strict -W unused-output=info
   ...
   examples/inconsistent/component_a.ddd.json#component.interface[1]: info[unused-output]: 'UnusedSignal' is written by component 'ComponentA' but read by nobody
   4 errors, 1 info

The policy belongs to the project rather than to the engineer who happens to be typing: whoever
checks the project should get the same verdict as the build server, so the overrides are best
written once into the build system - the CMake integration takes them as ``SEVERITY`` and
``STRICT`` arguments, see :doc:`build_integration` - instead of being remembered by hand.

.. note::
   Checking a single component before it is integrated is the one case where a relaxed policy
   is the normal thing to do, because the components producing its inputs and consuming its
   outputs are by definition not part of the file:

   .. code-block:: text

      $ ddd check examples/demo/components/controller.ddd.json
      examples/demo/components/controller.ddd.json#component.interface[0]: error[missing-producer]: 'ValueA' is read by component 'Controller' but no component declares it as output
      examples/demo/components/controller.ddd.json#component.interface[1]: error[missing-producer]: 'ValueB' is read by component 'Controller' but no component declares it as output
      examples/demo/components/controller.ddd.json#component.interface[2]: warning[unused-output]: 'ValueE' is written by component 'Controller' but read by nobody
      ...
      2 errors, 5 warnings

      $ ddd check examples/demo/components/controller.ddd.json -W missing-producer=ignore -W unused-output=ignore
      ok: 12 variables in 1 component are consistent

The five checks whose severity is fixed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Five checks cannot be relaxed: ``file-not-found``, ``json-syntax``, ``file-kind``, ``schema``
and ``include-cycle``. They are the ones that report that a description could not be *read*,
and a file that cannot be read has nothing further to say. Downgrading them would not make the
project more permissive, it would make the rest of the run meaningless: a file that is not
valid json contributes no declarations, so every variable it produces would be reported as
having no producer and every name it defines would look free. The tool would bury the one real
finding - "this file has a comma too many on line 4" - under a page of consequences.

The same reasoning explains why the two other load time checks *are* relaxable.
``file-extension`` and ``include-empty`` complain about a file tree DDD can read perfectly
well, it just does not like the shape of it: a description named ``foo.json`` instead of
``foo.ddd.json`` is fully understood, and an include pattern that is legitimately empty in one
variant of a project is a normal thing to allow.

Trying to change a fixed check is a usage error rather than a silently ignored request, as is
naming a check or a severity that does not exist - the value of stable identifiers would be
lost if a typo in a build script quietly disabled a rule:

.. code-block:: text

   $ ddd check examples/inconsistent/project.ddd.json -W schema=warning
   ddd: the severity of check 'schema' cannot be changed
   $ echo $?
   2

   $ ddd check examples/inconsistent/project.ddd.json -W typo=warning
   ddd: unknown check 'typo'

   $ ddd check examples/inconsistent/project.ddd.json -W unused-output=fatal
   ddd: unknown severity 'fatal' for check 'unused-output', expected one of error, warning, info, ignore

.. note::
   As long as a load time check reports an error, the interface checks do not run at all: the
   project has not been assembled, so there is nothing to compare. On a project that is broken
   in both ways the findings therefore arrive in two waves - repair the file tree, and the
   interface findings appear on the next run. Where the offending check is one of the two
   relaxable ones, ``-W file-extension=warning`` is enough to let the second wave through
   immediately.

The checks
----------

The tables below list the checks as ``ddd checks`` reports them, grouped by their default
severity. The identifier and the default severity are the two things a project pins; the third
column says what the tool is actually looking at when the check fires.

Errors
~~~~~~

An error means the project is wrong, in the sense that generating from it would produce c code
or an a2l file that does not do what the description says - or that does not compile at all.

.. list-table::
   :header-rows: 1
   :widths: 24 14 62

   * - Check
     - Default
     - Fires when
   * - ``file-not-found``
     - error (fixed)
     - a file named on the command line or reached through an ``includes`` pattern does not
       exist, is a directory, or cannot be read.
   * - ``json-syntax``
     - error (fixed)
     - a description file is not valid json, is nested too deeply to read, or is not valid
       utf-8. The finding carries the line and the column the parser stopped at.
   * - ``file-kind``
     - error (fixed)
     - the top level of the document is not a json object, or carries neither ``project`` nor
       ``component``, or carries both. A naming convention listed in ``includes`` is recognized
       as such and reported with the advice to point the ``naming`` key at it instead.
   * - ``file-extension``
     - error
     - a description file is not named ``*.ddd.json``. Relaxable with
       ``-W file-extension=warning`` while a project is being migrated.
   * - ``schema``
     - error (fixed)
     - the document does not match the DDD contract: a missing or unknown key, a value of the
       wrong type, a datatype that does not exist. One finding per violated constraint, each
       pointing at the offending key. It also fires on an archived dictionary written by a
       newer DDD than the one reading it.
   * - ``include-cycle``
     - error (fixed)
     - a project includes a file which, directly or indirectly, includes it again. A diamond -
       the same component reached through two paths - is not a cycle and is quietly used once.
   * - ``include-empty``
     - error
     - an ``includes`` pattern matches no file, which usually means a renamed directory or a
       typo rather than a component that genuinely has no description.
   * - ``duplicate-component``
     - error
     - two different files declare a component of the same name. Component names have to be
       unique: each component gets a generated header named after it.
   * - ``duplicate-type``
     - error
     - two different files declare a type of the same name. Which of two answers the generated
       c would get is not something an include order should decide, so the second is refused
       rather than allowed to win.
   * - ``unknown-type``
     - error
     - a ``datatype`` names neither one of the base datatypes nor a type any file of the
       project declares - on a component declaration or on a structure member alike. It is
       refused rather than skipped, because an object of unknown storage has no limits, no
       size and nothing later to check against. The nearest known name is suggested, which is
       what answers a transposition like ``unit16`` that the contract cannot catch on its own.
   * - ``type-kind``
     - error
     - a declared type is used where its shape does not fit: a declaration naming a structure
       while being a curve, a map, an axis or a value block, all of which refer to other
       objects or are arrays of one datatype, or one stating an ``init``, which for a
       structure is written by the code that starts it rather than by the description.
   * - ``type-cycle``
     - error
     - structures nest each other, directly or through others. The finding names the chain,
       ``A -> B -> C -> A``, because that says which member to remove; a structure that
       contains itself has no size at all.
   * - ``reserved-identifier``
     - error
     - a component, variable, type, enum or enumerator name is a c keyword, or is declared by one of
       the headers the generated code includes (everything ``<stdint.h>`` and ``<stdbool.h>``
       bring in, so ``uint16_t`` is out), or is reserved for the implementation by C11 7.1.3 -
       any name containing a double underscore, or starting with an underscore followed by a
       capital letter.
   * - ``name-collision``
     - error
     - two names that are distinct in the description files would become the same c identifier
       or the same generated file: an enumerator and a variable, a variable and the name of an
       enum or of a declared type (both of which the types header makes typedef names, in the
       same file scope namespace as the variables), an enumerator claimed by two enums (all
       enumerators share one c namespace), or two component names differing only in case, which
       ask for the same header on a case insensitive filesystem.
   * - ``duplicate-declaration``
     - error
     - one component declares the same variable twice, for instance once as ``input`` and once
       as ``output``. The second declaration is ignored for the rest of the run.
   * - ``consumer-storage``
     - error
     - an ``input`` declaration states ``init``. What a variable starts out as is decided by
       the component that produces it, so a component that only reads it is claiming storage it
       does not own - which is a different thing from the disagreements above, and is reported
       where the claim is written rather than where it is overruled. Relaxable, so a project
       migrating existing descriptions can lower it while the ``init`` keys are removed.
   * - ``multiple-producers``
     - error
     - a variable is declared ``output`` by more than one component. Exactly one component owns
       the storage of a variable; two definitions would not even link.
   * - ``missing-producer``
     - error
     - a variable is read as ``input`` but no component declares it as an output. The generated
       consumer header would declare a symbol nobody defines.
   * - ``local-conflict``
     - error
     - a variable declared ``local`` by one component is also declared by another. ``local`` is
       a promise that the variable is nobody else's business, and DDD keeps it out of the
       shared headers accordingly.
   * - ``definition-mismatch``
     - error
     - two components describe the same variable differently in a property that changes what
       the value *means*: kind, datatype, unit, declared shape, conversion, volatility,
       physical limits, or the axis references of a curve or a map. A consumer that simply
       omits ``limits`` is not disagreeing and is not reported, because they are derived from
       the datatype and the conversion when nobody states them. ``volatile`` cannot be left
       out that way: every definition of every kind has to state it, so a difference there is
       always two components saying two different things rather than one of them saying
       nothing at all.
   * - ``enum-conflict``
     - error
     - the same enum type name is defined with different enumerators. One c enum is generated
       per name, so only one set of enumerators could survive.
   * - ``unknown-reference``
     - error
     - a curve, a map or an axis refers by name to an object no component declares.
   * - ``reference-kind``
     - error
     - a reference points at an object of the wrong kind, for example the ``axis`` of a curve
       naming a measurement instead of an axis.
   * - ``init-invalid``
     - error
     - an initial value does not fit its datatype - out of range, written as a fraction for an
       integer, neither 0 nor 1 for a bool - or an initialiser has a shape the variable does
       not have (for a curve or a map, the shape given by its axes), or an enumerator does not
       fit the datatype of the variable, or does not fit into a c ``int``, which every
       enumerator has to (C11 6.7.2.2).
   * - ``naming``
     - error
     - a declared variable name does not follow the naming convention the project points at.
       Only variable names are checked; see :doc:`naming_conventions`.

Warnings
~~~~~~~~

A warning means the project generates, and what it generates is well defined, but something in
it is either a smell or a decision somebody should have taken consciously.

.. list-table::
   :header-rows: 1
   :widths: 24 14 62

   * - Check
     - Default
     - Fires when
   * - ``storage-mismatch``
     - warning
     - two components describe the same variable differently in a property that shapes how
       the a2l presents it - a ``format`` string, a ``display_identifier`` - rather than the
       meaning of the value. This is a warning and not an error because the outcome is
       defined: the producer's value is the one that is generated, and the message says so.
   * - ``condition-mismatch``
     - warning
     - the declarations of one variable carry different preprocessor conditions, so the
       components do not agree on when the variable exists at all. The producer's condition is
       the one that guards the generated definition.
   * - ``unused-output``
     - warning
     - a variable is declared ``output`` by its producer and read by no component. Either a
       consumer forgot to declare it, or the variable exists for measurement only, in which
       case ``local`` says so more honestly.
   * - ``enum-duplicate-value``
     - warning
     - two enumerators of one enum share the same numeric value. Legal c, and occasionally
       intended as an alias, but a calibration tool can no longer display the raw value
       unambiguously.
   * - ``limits-out-of-range``
     - warning
     - the declared physical limits are wider than what the datatype can represent through the
       conversion, so part of the declared range is unreachable.
   * - ``name-similar``
     - warning
     - two variables differ only in upper and lower case. They are distinct in c, and confusing
       everywhere else.
   * - ``a2l-unrepresentable``
     - warning
     - an exported object cannot be fully described by the a2l version DDD writes: today that is
       an array of more than three dimensions, which the ``MATRIX_DIM`` of ASAP2 1.6.1 cannot
       carry. The extra dimensions are written out and only a 1.7 reader understands them.

Information
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 14 62

   * - Check
     - Default
     - Fires when
   * - ``empty-component``
     - info
     - a component declares no variable at all. Perfectly legal - a component may have no global
       interface - but worth saying out loud, because the usual cause is a description file that
       was registered before it was written.

Checks of the delivery comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The remaining checks of the registry answer a different question - whether one delivery can
replace another - and fire only for ``ddd compare`` and for ``ddd check --baseline``. They obey
exactly the same policy: same identifiers, same ``-W`` and ``--strict``, same exit codes.
:doc:`comparing_deliveries` explains the grading; the identifiers are listed here so that the
registry can be read in one place.

.. list-table::
   :header-rows: 1
   :widths: 24 14 62

   * - Check
     - Default
     - Fires when
   * - ``removed-object``
     - error
     - an object of the baseline is gone and a component read it.
   * - ``changed-interface``
     - error
     - the kind, datatype, unit, scaling, shape, axes or locality of an object changed.
   * - ``removed-unused-object``
     - warning
     - an object of the baseline is gone that no component read - a calibration dataset or an
       external tool still might.
   * - ``changed-storage``
     - warning
     - the initial value or the volatility of an object changed. A calibration object whose
       ``volatile`` went from ``true`` to ``false`` is the case worth reading twice: it keeps
       its address and a tool can still write to it, but the compiler is now entitled to fold
       the initial value into the code that reads it, so tuning it while the software runs
       stops working.
   * - ``narrowed-limits``
     - warning
     - the physical limits of an object got tighter, so calibrated data may no longer fit.
       Widening is silent, because every value the baseline allowed still fits.
   * - ``changed-owner``
     - warning
     - another component produces the object now.
   * - ``changed-condition``
     - warning
     - the preprocessor condition of an object changed.
   * - ``changed-a2l``
     - warning
     - the a2l entry of an object changed.
   * - ``project-mismatch``
     - warning
     - the two sides of the comparison describe differently named projects, so the baseline is
       probably not the predecessor of this candidate.
   * - ``added-object``
     - info
     - the candidate declares an object the baseline did not.

The producing component wins
----------------------------

Two components can describe the same variable, and one of the two descriptions has to be the
one that is generated. DDD does not average them and does not simply take the first one it
read: the declaration of the **producing** component is the reference. The rule is not
arbitrary. The producer is the component that owns the storage - its declaration is where the
definition is emitted, its initial value is the one the linker puts into the image, its
condition is the one that decides whether the variable exists at all. A consumer only ever
describes what it expects to find, and when expectation and reality differ, reality is what the
hardware will do.

Two things follow. The first is that the diagnostic points at the **deviating consumer**, with
a note referring back to the producer, so that the finding lands on the file that has to
change:

.. code-block:: text

   examples/inconsistent/component_c.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'SharedValue' is declared differently by component 'ComponentC' than by 'ComponentA' (datatype: uint16 != sint16, conversion: identity != linear(factor=0.5, offset=0))
       note: examples/inconsistent/component_a.ddd.json#component.interface[0].definition: reference declaration

The second is that a property which merely shapes how the a2l *presents* the object does not
have to stop the build, precisely because the outcome is defined. Given a producer and a
consumer that ask for different display formats,

.. code-block:: json

   { "scope": "output", "definition": { "name": "ValueA", "kind": "measurement", "datatype": "uint16", "volatile": false } }

.. code-block:: json

   { "scope": "input", "definition": { "name": "ValueA", "kind": "measurement", "datatype": "uint16", "a2l": { "format": "%8.3" }, "volatile": false } }

the check names the value that is going to be used:

.. code-block:: text

   consumer.ddd.json#component.interface[0].definition: warning[storage-mismatch]: 'ValueA': component 'Consumer' specifies a different a2l than 'Producer' (format='%8.3' != unset); the value of 'Producer' is used
       note: producer.ddd.json#component.interface[0].definition: reference declaration

Two other properties used to be settled this way, and left in opposite directions.

``init`` is not a losing opinion but a claim over storage the component does not own: reading
a variable gives it no say in what the variable starts as. A consumer stating one is refused
outright, as ``consumer-storage``, where the claim is written rather than where it is
overruled.

``volatile`` went the other way and became interface. It reaches every consumer's own header
as a type qualifier - ``extern volatile uint16_t ValueA`` - and that is what tells that
component's code not to cache the value and not to expect two reads to agree. Every
declaration of the variable therefore has to say the same thing, and a disagreement is a
``definition-mismatch`` error. There is no leaving it out, either: unlike ``limits``, which
DDD derives when a declaration omits them, there is nothing here to derive, so the key is
required on every definition of every kind and a definition without it does not load at all.
That is reported as ``schema``, one of the five checks whose severity cannot be relaxed, which
is why a project adopting this version of DDD adds the key everywhere in one go rather than
phasing it in.

``export`` is not compared at all. Which signals a calibration engineer needs to see is not the
producer's to decide alone, so any component may ask for an object to reach the a2l and asking
wins over declining - see :doc:`the component file format <file_formats/component>`.

.. note::
   When *no* component produces a variable - which is reported on its own as
   ``missing-producer`` - the first declaration the tool read stands in as the reference, so
   that the remaining checks still have something to compare the others against. This is why a
   project with a missing producer reports both the missing producer and any disagreement
   between its consumers, instead of hiding the second finding behind the first.

A project that does not check out
---------------------------------

``examples/inconsistent`` is a deliberately broken project of three components, kept in the
repository so that the checks can be seen firing on something small. The project file only
collects them:

.. code-block:: json

   {
     "project": {
       "name": "BrokenProject",
       "description": "Deliberately inconsistent project, used to demonstrate the checks",
       "includes": [
         "component_a.ddd.json",
         "component_b.ddd.json",
         "component_c.ddd.json"
       ]
     }
   }

``ComponentA`` writes ``SharedValue`` as an ``sint16`` in percent with a factor of 0.5, writes
``UnusedSignal``, and keeps a ``local`` variable ``Scratch``. ``ComponentB`` writes
``SharedValue`` as well. ``ComponentC`` reads ``SharedValue`` as an unscaled ``uint16``, reads
a ``MissingValue`` nobody writes, and reads ``ComponentA``'s ``Scratch``. Checking the project
gives:

.. code-block:: text

   $ ddd check examples/inconsistent/project.ddd.json
   examples/inconsistent/component_b.ddd.json#component.interface[0]: error[multiple-producers]: 'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed
       note: examples/inconsistent/component_a.ddd.json#component.interface[0]: also written here
   examples/inconsistent/component_c.ddd.json#component.interface[0].definition: error[definition-mismatch]: 'SharedValue' is declared differently by component 'ComponentC' than by 'ComponentA' (datatype: uint16 != sint16, conversion: identity != linear(factor=0.5, offset=0))
       note: examples/inconsistent/component_a.ddd.json#component.interface[0].definition: reference declaration
   examples/inconsistent/component_c.ddd.json#component.interface[1]: error[missing-producer]: 'MissingValue' is read by component 'ComponentC' but no component declares it as output
   examples/inconsistent/component_c.ddd.json#component.interface[2]: error[local-conflict]: 'Scratch' is local to component 'ComponentA' but is also declared as input by component 'ComponentC'
       note: examples/inconsistent/component_a.ddd.json#component.interface[2]: declared local here
   examples/inconsistent/component_a.ddd.json#component.interface[1]: warning[unused-output]: 'UnusedSignal' is written by component 'ComponentA' but read by nobody
   4 errors, 1 warning

Five findings, and each one is a different kind of mistake.

**multiple-producers.** Two components claim to write ``SharedValue``. In c that is two
definitions of one symbol, which the linker rejects outright or, under a permissive setting,
silently merges; in the project it means that nobody is responsible for the value. The finding
lands on ``ComponentB`` because ``ComponentA`` was seen first, and the note points at the other
writer. The fix is an organisational decision rather than a textual one: exactly one component
owns the value and the other declares it as ``input`` - which is also what makes the data flow
of the project visible in the first place.

**definition-mismatch.** ``ComponentC`` reads the same name as an unscaled ``uint16``. Both
halves of the disagreement matter: the datatype changes how many bytes are read and how the
sign bit is interpreted, and the missing conversion means the consumer would understand a raw
200 as 200 percent where the producer meant 100. The finding points at the consumer and the
note at the producer, because the producer's declaration is the reference. The fix is to copy
the producer's datatype and conversion into the consumer - or, if the consumer is right and the
producer is wrong, to change the producer and let the check point at the next component that
has not followed.

**missing-producer.** ``ComponentC`` reads ``MissingValue`` and no component writes it. The
generated consumer header would declare a symbol that has no definition anywhere, and the
mistake would surface at link time as an undefined reference, several minutes and one full
build later. Either a component declares it as ``output``, or the read is stale and the
declaration goes.

**local-conflict.** ``Scratch`` is ``local`` to ``ComponentA``, which is a promise that no
other component depends on it: DDD keeps it out of the shared headers and out of the interface
of the project, so ``ComponentA`` may rename or delete it freely. ``ComponentC`` reading it
breaks that promise. Either the variable is genuinely shared, in which case ``ComponentA``
declares it as ``output``, or it is not, in which case ``ComponentC`` has to do without.

**unused-output.** ``UnusedSignal`` is written and read by nobody. Only a warning, because a
value may legitimately exist for measurement alone, and because the consumer may be a component
that is not integrated yet. If it is measurement only, declaring it ``local`` says so and
removes the warning; if a consumer was forgotten, this is the reminder.

With all five addressed - ``ComponentB`` reading ``SharedValue`` instead of writing it,
``ComponentC`` adopting the producer's datatype and conversion, dropping its read of ``Scratch``
and reading ``UnusedSignal`` instead of the ``MissingValue`` nobody produces - the same command
says:

.. code-block:: text

   $ ddd check project.ddd.json
   ok: 3 variables in 3 components are consistent

Exit codes and ci
-----------------

DDD is meant to be a build step, so the verdict is in the exit code and not only in the text:

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Code
     - Meaning
   * - ``0``
     - The run succeeded. There may still have been warnings or information findings - they are
       printed and counted, but they do not fail the run. ``--strict`` is how a project changes
       that.
   * - ``1``
     - At least one finding was reported with the severity ``error``, whatever its default
       severity was. ``ddd generate`` additionally wrote nothing, unless ``--force`` was given.
   * - ``2``
     - The command was used wrongly: an unknown check identifier or severity in ``-W``, an
       attempt to change one of the fixed checks, a missing or unrecognized argument, an output
       directory that cannot be written to. Nothing was checked, which is why this case is
       deliberately distinguishable from "checked, and found wanting".

A ci job therefore needs no output parsing at all to decide whether it passes:

.. code-block:: bash

   ddd check project.ddd.json --strict || exit 1

``--format json`` is for the other half of the job - annotating a merge request, feeding a
dashboard, turning findings into editor markers. It replaces the human readable rendering
rather than accompanying it: the findings become one document on **stdout** and stderr stays
empty, so a job can consume the whole of stdout without having to recognise where the
document begins:

.. code-block:: text

   $ ddd check project.ddd.json --format json
   {
     "diagnostics": [
       {
         "check": "multiple-producers",
         "severity": "error",
         "message": "'SharedValue' is written by component 'ComponentB' and by component 'ComponentA'; exactly one writer is allowed",
         "location": {
           "path": "C:/work/project/component_b.ddd.json",
           "pointer": "component.interface[0]",
           "line": null,
           "column": null
         },
         "notes": [
           {
             "message": "also written here",
             "location": {
               "path": "C:/work/project/component_a.ddd.json",
               "pointer": "component.interface[0]",
               "line": null,
               "column": null
             }
           }
         ]
       },
       ...
     ],
     "summary": {
       "error": 4,
       "warning": 1,
       "info": 0
     }
   }

Every finding carries the information the text form carries, in fields that are stable:
``check`` is the identifier, ``severity`` is the severity the finding was *reported with* once
the policy had been applied, and ``location`` is an absolute, forward-slashed path together
with the json pointer and, where the finding has one, a line and a column. The notes of a
finding have the same shape as the finding itself. The ``summary`` object closes the document
with the counts a dashboard usually wants; a check set to ``ignore`` contributes to none of
them. The exit code is unaffected by ``--format json``, so a job can consume the document and
still let the code decide the verdict.

Finally, the registry itself is machine readable, which is how a build script can confirm that
the identifiers it pins still exist after a DDD upgrade, instead of discovering it through a
usage error:

.. code-block:: text

   $ ddd checks --format json
   [
     {
       "check": "file-not-found",
       "default_severity": "error",
       "description": "a referenced file does not exist",
       "overridable": false
     },
     ...
   ]

``overridable`` is the machine readable form of the ``(fixed)`` marker: ``false`` for the five
load time checks whose severity cannot be changed, ``true`` for every other check.
