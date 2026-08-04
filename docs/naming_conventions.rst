Naming conventions
==================

Most teams already agree that a variable name means something. One part says what the value
*is* - a measurement, a flag, a counter, a calibratable parameter - one part says what it is
*about*, and one part says how it was *conditioned*, raw or filtered or converted to the
physical quantity. That agreement usually lives in a slide, a wiki page or in the head of
whoever wrote the first component, and it decays exactly as fast as the team grows. DDD can
hold the agreement in a ``*.ddd.json`` file instead, check every declared name against it on
every run, explain an unfamiliar name to whoever reads it, and complete a name in the shell
while it is being typed.

The convention is optional. A project that does not point at one is checked for everything
else and never sees a naming finding; nothing else in the tool depends on it.

Why a sequence of segments and not one regular expression
---------------------------------------------------------

A regular expression can decide whether a name is acceptable, and that is all it can do. When
``vl_InletTemperature_flt`` fails to match ``^(val|flg|cnt)_[A-Z][A-Za-z0-9]*(_(raw|flt))?$``,
the expression has no way of saying that it was the *first* part that went wrong, that the
first part is called the role, that the roles are ``val``, ``flg`` and ``cnt``, or that ``val``
is one edit away from what was typed. It fails as a whole, so it can only report the whole
name.

The same limitation shows up from the other side. A calibration engineer looking at
``val_InletTemperature_flt`` for the first time wants to know what ``val`` and ``flt`` stand
for; an expression that merely accepts the name carries none of that. And a developer half way
through typing ``val_Inlet`` wants the shell to offer the endings that are still allowed, which
an expression cannot enumerate either, because a match is a yes-or-no answer over a complete
string.

DDD therefore describes a name as an ordered sequence of **segments** joined by a fixed
**separator**, and says for each segment what may stand there. Because the description is
positional, the tool always knows which position it is looking at:

* a rejected name can be **located** - the offending part is underlined with carets and named
  after its segment, and the vocabulary of that segment is offered as the correction,
* an accepted name can be **explained** - each part is printed next to the meaning the
  convention gives it,
* a partially typed name can be **completed** - at any position the allowed tokens are known,
  so a shell can offer them.

This is why the segmented form is required rather than merely convenient: it is the only form
that supports the two things beyond validation that make a convention worth writing down.

The convention file
-------------------

A convention is a json file whose top level key is ``naming``, named ``*.ddd.json`` like the
other description files so that one pattern still matches everything belonging to DDD. It is
not listed in the ``includes`` of a project - a project points at it with its ``naming`` key -
and a convention that is listed in ``includes`` anyway is not left to fail obscurely as a file
that is neither a project nor a component, but is recognised for what it is:

.. code-block:: text

   $ ddd check wrong-include.ddd.json
   convention.ddd.json: error[file-kind]: this is a naming convention; point the 'naming' key of the project at it instead of listing it in 'includes'
   1 error

The full example below is ``examples/naming/convention.ddd.json``:

.. code-block:: json

   {
     "naming": {
       "name": "demo-convention",
       "description": "Names are <role>_<Subject>[_<Subject>...][_<qualifier>]",
       "separator": "_",
       "segments": [
         {
           "name": "role",
           "description": "what part the value plays in the software",
           "tokens": [
             { "value": "val", "description": "a measured or computed value" },
             { "value": "flg", "description": "a boolean flag" },
             { "value": "cnt", "description": "a counter" },
             { "value": "par", "description": "a calibratable parameter" },
             { "value": "axs", "description": "axis break points" },
             { "value": "crv", "description": "a calibratable curve" },
             { "value": "map", "description": "a calibratable map" },
             { "value": "tbl", "description": "a calibratable value block" }
           ]
         },
         {
           "name": "subject",
           "description": "what the value is about, in upper camel case",
           "pattern": "^[A-Z][A-Za-z0-9]*$",
           "repeatable": true
         },
         {
           "name": "qualifier",
           "description": "how the value is conditioned",
           "optional": true,
           "tokens": [
             { "value": "raw", "description": "unconditioned, straight from the source" },
             { "value": "flt", "description": "filtered" },
             { "value": "phys", "description": "converted to the physical quantity" },
             { "value": "req", "description": "a request, not a measurement" },
             { "value": "max", "description": "an upper bound" },
             { "value": "min", "description": "a lower bound" }
           ]
         }
       ]
     }
   }

The ``naming`` object itself carries five keys:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - How the convention calls itself. It is printed next to every explained name, so that a
       reader who sees two different verdicts knows which set of rules produced each.
   * - ``description``
     - ``""``
     - Free text for the humans reading the file.
   * - ``separator``
     - ``"_"``
     - The string that joins the segments. A name is split on it before its parts are judged.
   * - ``segments``
     - required
     - The ordered positions of a name; at least one.
   * - ``case_sensitive``
     - ``true``
     - Whether a token has to be spelled exactly as the convention spells it.

With ``case_sensitive`` set to ``false``, a token typed in another case is accepted and still
resolves to its meaning, and the completion offers the token as the convention spells it, so
the canonical spelling is what ends up on the command line.

segments
~~~~~~~~

A segment is one position in a name. It carries either a controlled **vocabulary** of tokens
with their meanings, or a **pattern** for a free position - never both, and never neither. A
segment with both would leave it undecided which of the two decides, and a segment with
neither would accept anything, which is indistinguishable from not describing the position at
all; both are refused when the file is read.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - key
     - default
     - meaning
   * - ``name``
     - required
     - What this position means, in c identifier form. It is what the messages call the
       position: *is not a known* **role**, *does not match the* **subject** *pattern*.
   * - ``description``
     - ``""``
     - Shown when a name is explained and when a required position is missing, so a
       description here is what a newcomer actually reads.
   * - ``tokens``
     - ``[]``
     - The controlled vocabulary of this position. Each token is an object with a ``value``
       and an optional ``description``; the completions and the "did you mean" suggestions
       come from here.
   * - ``pattern``
     - ``null``
     - A regular expression for a free position, matched against the whole part. Use it where
       the vocabulary is open, typically for the descriptive part of a name.
   * - ``optional``
     - ``false``
     - A trailing position that a name may leave out.
   * - ``repeatable``
     - ``false``
     - The position may be filled more than once, for a multi-word descriptive part.

The pattern is compiled while the convention file is read rather than when the first name is
judged. A typo in the expression is therefore reported as a finding about the convention,
against the file and the segment it belongs to, instead of surfacing as a crash somewhere in
the middle of a project check.

The rules that keep a name splittable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Splitting a name into positions only works if the split is unique. Three rules make sure of
that, and all three are enforced when the convention file is loaded rather than when a name
happens to run into them:

* **``optional`` may only appear at the end.** If a required segment followed an optional one,
  a name that is one part short would fit two readings - the optional part left out, or the
  required part left out - and the tool would have no basis for choosing. The message names
  the segment that breaks the rule: ``segment 'subject' is required but follows an optional
  one, so a name could not be split unambiguously``.
* **At most one segment may be ``repeatable``.** With two stretchable positions, a name with
  spare parts could be divided between them in several ways, and the explanation of the name
  would depend on an arbitrary choice. The message lists the offenders: ``only one segment may
  be repeatable, got role, subject``.
* **A token may not contain the separator.** The name is split on the separator first, so such
  a token could never appear as a single part; the completion would offer it and the check
  would then reject it, which is the tool contradicting itself. It is refused outright:
  ``token 'val_raw' of segment 'role' contains the separator '_', so no name could ever match
  it``. For the same reason a token may not contain whitespace.

.. note::
   These are ``schema`` findings against the convention file, and ``schema`` is one of the
   checks whose severity cannot be relaxed - a convention that cannot be interpreted has
   nothing further to say. ``ddd name`` on such a file exits with ``2``, the usage exit code,
   rather than pretending to judge names against rules it could not read.

The machine readable form of all of this is available with ``ddd schema naming``, which prints
the json schema of the convention file.

How a name is judged
--------------------

A name is first split on the separator, and the resulting parts are then laid over the
segments. Because a convention may have trailing optional segments and one repeatable segment,
several **layouts** can accommodate the same number of parts: with the demo convention above,
three parts can be read as role + subject + qualifier, or as role + subject + subject.

DDD does not decide that greedily. It enumerates every layout the convention allows for that
number of parts, judges the name under each, and keeps the layout the name actually fits. This
matters for a very ordinary case - a multi-word subject:

.. code-block:: text

   $ ddd name -c convention.ddd.json val_Inlet_Temperature
   val_Inlet_Temperature  (demo-convention)
     val                      role         a measured or computed value
     Inlet                    subject      what the value is about, in upper camel case
     Temperature              subject      what the value is about, in upper camel case

A greedy reading would hand ``Temperature`` to the qualifier, find it in none of the six
qualifiers and blame the author for a name the convention allows. Trying all layouts and
keeping the one that fits removes that entire class of false findings. When no layout fits,
the layout with the fewest problems is the one reported, so the diagnostics point at the
reading that was closest to working rather than at an arbitrary one.

Layouts that use more of the optional segments are tried first, which is what makes a part that
could be read either as a vocabulary token or as free text be reported as the token, together
with its meaning. That is the reading a human would give it, and it is the one that produces
the more useful explanation.

A name that stops before a required position is a different kind of failure from a name with a
wrong part, and is reported as such - there is nothing to underline, so the missing position is
named instead, with its description:

.. code-block:: text

   $ ddd name -c convention.ddd.json val
   val

     the subject part is missing: what the value is about, in upper camel case

.. note::
   ``repeatable`` widens how many parts a position may take; it does not make the position
   optional. A repeatable segment still has to appear at least once, which is why the subject
   is reported as missing above.

Explaining a name
-----------------

``ddd name -c CONV NAME...`` takes one or more names and prints, for each, what the convention
makes of it. For a name that fits, the output is the reading of the name: the convention that
judged it, then one line per part with the position it occupies and what that part means.

.. code-block:: text

   $ ddd name -c convention.ddd.json val_InletTemperature_flt
   val_InletTemperature_flt  (demo-convention)
     val                      role         a measured or computed value
     InletTemperature         subject      what the value is about, in upper camel case
     flt                      qualifier    filtered

The meaning printed for a part comes from the token's ``description`` where the position has a
vocabulary, and from the segment's ``description`` where it is a free position. This is the
half of the job that has nothing to do with policing: a calibration engineer who meets
``crv_InletCompensation`` in a measurement tool can ask the same command what it is, and the
answer comes from the file the developers maintain rather than from a glossary that drifts.

Locating what is wrong
----------------------

For a name that does not fit, the output points at the part at fault, and offers the closest
tokens of that position as a correction. Several names can be looked at in one call:

.. code-block:: text

   $ ddd name -c convention.ddd.json vl_InletTemperature_flt flg_Valid_fltr
   vl_InletTemperature_flt
   ^^
     'vl' is not a known role (val, flg, cnt, par, axs, crv, map, tbl) - did you mean 'val'?
   flg_Valid_fltr
             ^^^^
     'fltr' is not a known qualifier (raw, flt, phys, req, max, min) - did you mean 'flt'?

The carets sit under the offending part because the tool knows the offset of that part in the
whole name, and the message names the position and lists its vocabulary because the convention
described that position rather than the name as a whole. Up to three suggestions are offered,
taken from the vocabulary of the position and ordered by closeness to what was typed; a part
that resembles nothing in the vocabulary simply gets no suggestion rather than a misleading
one.

``ddd name`` exits with ``0`` when every name fits, ``1`` when at least one does not, and ``2``
when the convention file itself could not be read - which makes it usable as a small gate of
its own, for instance over the names in a review. With ``--format json`` it prints the same
verdict machine readably, including the offset and length of every part, the segment it was
judged against, its meaning, the problem and the suggestions, so a ci job or an editor
integration can render it however it likes.

Completing a partially typed name
---------------------------------

``ddd complete -c CONV PREFIX`` prints the names the prefix could grow into, one candidate per
line. It is meant to be called by a shell completion, and it is built around that: it **always
exits zero and never prints a diagnostic**, because a completion that reports an error is worse
than one that offers nothing - the error would land in the middle of the line being typed. A
missing or unreadable convention file therefore produces no output and exit code ``0``.

With nothing typed yet, the vocabulary of the first position is offered:

.. code-block:: text

   $ ddd complete -c convention.ddd.json ''
   val
   flg
   cnt
   par
   axs
   crv
   map
   tbl

A partially typed part is filtered on, so a single character is usually enough:

.. code-block:: text

   $ ddd complete -c convention.ddd.json v
   val

Once the subject has been typed, the offer moves on to what may follow it. A free position has
no vocabulary of its own, so there would be nothing to propose there; instead of giving up, the
completion checks that what stands in the free position is acceptable and then offers the
vocabulary of the *next* position:

.. code-block:: text

   $ ddd complete -c convention.ddd.json val_Inlet
   val_Inlet_raw
   val_Inlet_flt
   val_Inlet_phys
   val_Inlet_req
   val_Inlet_max
   val_Inlet_min

A prefix that ends in the separator asks for the next position outright, and a further
character narrows it down to one:

.. code-block:: text

   $ ddd complete -c convention.ddd.json val_InletTemperature_
   val_InletTemperature_raw
   val_InletTemperature_flt
   val_InletTemperature_phys
   val_InletTemperature_req
   val_InletTemperature_max
   val_InletTemperature_min

   $ ddd complete -c convention.ddd.json val_InletTemperature_f
   val_InletTemperature_flt

Only positions that are reachable **given the parts already typed** are offered, which is what
keeps the completion and the check from ever contradicting each other: a candidate the
completion proposes is a name the same convention accepts. The other side of that rule is that
a prefix which is already wrong yields nothing at all - ``xyz_Inlet`` starts with a role that
does not exist, and ``val_inlet`` has a subject that does not match the pattern, so neither has
a valid continuation to offer:

.. code-block:: text

   $ ddd complete -c convention.ddd.json xyz_Inlet
   $ ddd complete -c convention.ddd.json val_inlet
   $

.. note::
   An empty offer also happens in a perfectly healthy situation: ``val_`` asks for the subject,
   which is a free position with no vocabulary, so there is nothing to enumerate. Silence from
   the completion means "nothing to propose here", not "this is wrong" - the judgement of a
   name is ``ddd name``'s job, and ``ddd complete`` deliberately never speaks for it.

Shell completion
~~~~~~~~~~~~~~~~

The repository ships a bash completion script in ``completion/ddd.bash``, which also works in
zsh through ``bashcompinit``. It needs to know which convention to complete against, and takes
it from the ``DDD_CONVENTION`` environment variable - the natural place for it, since a
developer works on one project at a time and the setting then belongs in the shell profile
alongside the rest of the project environment:

.. code-block:: bash

   export DDD_CONVENTION=/path/to/convention.ddd.json
   source /path/to/ddd/completion/ddd.bash

   ddd name val_Inlet<TAB>          # offers the qualifiers once the subject is typed

Three properties of the script are worth knowing, because they are what makes it unobtrusive:

* It only completes names for the ``name`` subcommand. Everywhere else it leaves the reply
  untouched and the shell falls back to file name completion (``-o default``), so registering
  it does not break the completion of ``ddd check <TAB>``.
* It registers with ``-o nospace``. A completed segment is rarely the end of a name, so the
  cursor stays glued to the separator and the next ``TAB`` carries on where this one stopped.
* It reads the candidates as data, with ``mapfile``, and not through ``compgen -W``. ``compgen
  -W`` would re-parse the list as shell words and perform command substitution on it, which
  means a token from somebody else's convention file would run in your shell the moment
  ``TAB`` was pressed. ``ddd complete`` has already filtered on the prefix, so ``compgen``
  would add nothing anyway.

Every early return in the script leaves the reply untouched for the same reason the command
always exits zero: an unset ``DDD_CONVENTION``, a convention file that has been moved away, or
a ``ddd`` that is not on the path all result in the shell's normal behaviour rather than in
noise on the command line.

The convention in the project
-----------------------------

Checking names by hand is a reminder, not a rule. A project makes the convention binding by
pointing at it with its ``naming`` key, after which every declared name is checked on every
run, by everybody, as part of the ordinary :doc:`consistency checks </consistency_checks>`:

.. code-block:: json

   {
     "project": {
       "name": "NamedDevice",
       "description": "A project whose names follow a convention, checked on every run",
       "naming": "convention.ddd.json",
       "includes": [
         "sensing.ddd.json"
       ]
     }
   }

The path is relative to the project file that contains it, like every other path in a
description file. ``examples/naming/`` is exactly this project, and it passes:

.. code-block:: text

   $ ddd check project.ddd.json
   ok: 7 variables in 1 component are consistent

The point of putting the convention in the project rather than on the command line is that the
verdict does not depend on who runs the tool. Whoever checks the project - the developer, the
integrator, the ci job - gets the same answer as whoever wrote it, and nobody has to remember a
flag. The convention file is also part of the project's inputs for the build system:
``ddd sources`` lists it next to the description files, so editing the convention makes the
generated artefacts out of date exactly as editing a component does.

.. code-block:: text

   $ ddd sources project.ddd.json
   /home/you/ddd/examples/naming/convention.ddd.json
   /home/you/ddd/examples/naming/project.ddd.json
   /home/you/ddd/examples/naming/sensing.ddd.json

A name that does not follow the convention is reported as the ``naming`` check, an error by
default. Had the component declared ``InletPressure_raw`` and ``cnt_InletSensorFaults_fltr``
instead:

.. code-block:: json

   {
     "component": {
       "name": "Sensing",
       "declarations": [
         {
           "scope": "local",
           "definition": { "name": "InletPressure_raw", "kind": "measurement", "datatype": "uint16",
                          "volatile": false }
         },
         {
           "scope": "local",
           "definition": { "name": "cnt_InletSensorFaults_fltr", "kind": "measurement",
                          "datatype": "uint16", "volatile": false }
         }
       ]
     }
   }

.. code-block:: text

   $ ddd check project.ddd.json
   sensing.ddd.json#component.declarations[0].definition.name: error[naming]: 'InletPressure' is not a known role (val, flg, cnt, par, axs, crv, map, tbl)
       note: InletPressure_raw
             ^^^^^^^^^^^^^ ^^^
   sensing.ddd.json#component.declarations[0].definition.name: error[naming]: 'raw' does not match the subject pattern ^[A-Z][A-Za-z0-9]*$
       note: InletPressure_raw
             ^^^^^^^^^^^^^ ^^^
   sensing.ddd.json#component.declarations[1].definition.name: error[naming]: 'fltr' is not a known qualifier (raw, flt, phys, req, max, min) - did you mean 'flt'?
       note: cnt_InletSensorFaults_fltr
                                   ^^^^
   3 errors

The finding carries the same underlined name that ``ddd name`` prints, as a note under a
location that points at the exact declaration in the exact file - a two-part name against a
three-part convention produces one finding per offending part, so both problems of
``InletPressure_raw`` are reported rather than only the first. ``naming`` is a check like any
other, so a project adopting a convention on an existing code base can relax it while the
renaming is under way:

.. code-block:: text

   $ ddd check project.ddd.json -W naming=warning
   sensing.ddd.json#component.declarations[0].definition.name: warning[naming]: 'InletPressure' is not a known role (val, flg, cnt, par, axs, crv, map, tbl)
       note: InletPressure_raw
             ^^^^^^^^^^^^^ ^^^
   sensing.ddd.json#component.declarations[0].definition.name: warning[naming]: 'raw' does not match the subject pattern ^[A-Z][A-Za-z0-9]*$
       note: InletPressure_raw
             ^^^^^^^^^^^^^ ^^^
   sensing.ddd.json#component.declarations[1].definition.name: warning[naming]: 'fltr' is not a known qualifier (raw, flt, phys, req, max, min) - did you mean 'flt'?
       note: cnt_InletSensorFaults_fltr
                                   ^^^^
   3 warnings

which no longer fails the run, while ``-W naming=ignore`` silences it entirely and ``--strict``
would turn it back into an error along with every other warning.

.. note::
   The convention of the **root** project is the one that applies. A sub-project pulled in
   through ``includes`` cannot impose its own convention on the project that includes it -
   otherwise a component would be judged by different rules depending on which image it is
   built into, and a shared component could never be renamed to satisfy both. Checking that
   sub-project on its own still applies its convention. For the same reason, checking a single
   component file directly applies no convention at all: a component file has no ``naming``
   key, because a component does not get to choose the rules of the project it is delivered
   into.

Only variable names are checked
-------------------------------

The convention applies to the names of the data objects - measurements, parameters, value
blocks, curves, maps and axes - and to nothing else. Component names are not subject to it, and
neither are enum type names or enumerator names.

The reason is that these live in different namespaces with different conventions. A component
is called ``Sensing`` or ``UserInterface``, and the generated header takes its name from it;
a variable is called ``val_InletTemperature_flt``. A convention written for variables asks for
a role token followed by an upper camel case subject, and every component name in every project
would fail it on the first part - which would not be a finding about the project, it would be a
finding about applying the wrong rule. Restricting the check to variable names is therefore not
a limitation to be lifted later; it is what makes the check mean something.

.. warning::
   A convention constrains names, not identifiers. A name that follows the convention perfectly
   can still be rejected by the ``reserved-identifier`` check for colliding with a c keyword or
   with something the generated code's includes already declare, or by ``name-collision`` when
   two distinct names would produce the same c identifier or the same generated file. Those
   checks are about what the c compiler will accept and are described with the other
   :doc:`consistency checks </consistency_checks>`; they are never relaxed by a convention and
   never replaced by one.
